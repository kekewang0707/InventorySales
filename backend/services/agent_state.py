"""Agent 状态管理 — 桥接 LangGraph checkpoint 与 AiSession 模型。

- 管理 AsyncSqliteSaver 全局单例
- thread_id ↔ session_id 映射
- 构建 RunnableConfig（注入 thread_id + db session）
- 从 checkpoint 提取消息列表
"""

import logging
import uuid
from datetime import datetime
from typing import Optional

import aiosqlite
from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from backend.config import get_data_dir
from backend.models.ai_session import AiSession

logger = logging.getLogger(__name__)

# Checkpoint DB 路径（与主业务 DB 分离）
_CHECKPOINT_DB_PATH = str(get_data_dir() / "langgraph_checkpoints.db")

# 全局单例
_checkpointer: Optional[AsyncSqliteSaver] = None
_checkpointer_conn: Optional[aiosqlite.Connection] = None


async def get_checkpointer() -> AsyncSqliteSaver:
    """获取或创建全局 AsyncSqliteSaver 单例。

    使用 aiosqlite 直接创建连接，传入 AsyncSqliteSaver 构造器。
    这样可以保持连接在应用生命周期内一直存活。
    """
    global _checkpointer, _checkpointer_conn
    if _checkpointer is None:
        _checkpointer_conn = await aiosqlite.connect(_CHECKPOINT_DB_PATH)
        _checkpointer = AsyncSqliteSaver(_checkpointer_conn)
        await _checkpointer.setup()
        logger.info("LangGraph checkpointer initialized at %s", _CHECKPOINT_DB_PATH)
    return _checkpointer


async def close_checkpointer():
    """关闭 checkpointer 和底层数据库连接（应用关闭时调用）。"""
    global _checkpointer, _checkpointer_conn
    if _checkpointer_conn:
        await _checkpointer_conn.close()
        _checkpointer_conn = None
    _checkpointer = None
    logger.info("LangGraph checkpointer closed")


def build_config(session_id: str, db: AsyncSession) -> dict:
    """构建 LangGraph 的 RunnableConfig。

    - thread_id: 对应 session_id，保证同一会话的 checkpoint 可持续
    - db: 注入到 configurable，供工具函数使用
    - recursion_limit: 最大图执行步数（默认 50，足够多轮工具调用）
    """
    return {
        "configurable": {
            "thread_id": session_id,
            "db": db,
        },
        "recursion_limit": 50,
    }


async def ensure_session_exists(db: AsyncSession, session_id: str = "") -> tuple[str, bool]:
    """确保 AiSession 行存在。

    - 若 session_id 非空且已存在 → 更新 last_active，返回 (session_id, False)
    - 若 session_id 非空但不存在 → 用该 ID 创建，返回 (session_id, True)
    - 若 session_id 为空 → 生成新 ID 创建，返回 (new_id, True)
    """
    if session_id:
        row = await db.execute(
            select(AiSession).where(AiSession.session_id == session_id)
        )
        existing = row.scalar_one_or_none()
        if existing:
            existing.last_active = datetime.now()
            await db.commit()
            return session_id, False
        # 用提供的 session_id 创建新会话
        db.add(AiSession(
            session_id=session_id,
            created_at=datetime.now(),
            last_active=datetime.now(),
            title="",
        ))
        await db.commit()
        return session_id, True

    # 生成新 ID
    new_id = uuid.uuid4().hex
    db.add(AiSession(
        session_id=new_id,
        created_at=datetime.now(),
        last_active=datetime.now(),
        title="",
    ))
    await db.commit()
    return new_id, True


async def touch_session(db: AsyncSession, session_id: str):
    """更新会话的 last_active 时间戳。"""
    await db.execute(
        update(AiSession)
        .where(AiSession.session_id == session_id)
        .values(last_active=datetime.now())
    )
    await db.commit()


# ---- 消息序列化（从 LangGraph checkpoint → 前端格式） ----

def _map_lc_role(msg) -> str:
    """LangChain 消息类型 → 简单角色字符串。"""
    if isinstance(msg, HumanMessage):
        return "user"
    if isinstance(msg, AIMessage):
        return "assistant"
    if isinstance(msg, ToolMessage):
        return "tool_result"
    return "unknown"


def _serialize_content(msg) -> str:
    """提取 LangChain 消息的文本内容。"""
    content = msg.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in content
        )
    return str(content)


async def get_session_messages(session_id: str, db: AsyncSession) -> list[dict]:
    """从 LangGraph checkpoint 中提取会话消息列表。

    过滤规则：
    - HumanMessage → "user"
    - AIMessage（无 tool_calls） → "assistant"（实际文本回复）
    - AIMessage（有 tool_calls） → 跳过（中间状态，无意义显示）
    - ToolMessage → "tool_result"
    """
    checkpointer = await get_checkpointer()
    config = {"configurable": {"thread_id": session_id}}
    try:
        checkpoint_tuple = await checkpointer.aget_tuple(config)
    except Exception:
        checkpoint_tuple = None

    if checkpoint_tuple and checkpoint_tuple.checkpoint:
        channel_values = checkpoint_tuple.checkpoint.get("channel_values", {})
        messages = channel_values.get("messages", [])
        result = []
        for msg in messages:
            # 跳过带 tool_calls 的 AIMessage（中间过程，不展示）
            if isinstance(msg, AIMessage) and hasattr(msg, "tool_calls") and msg.tool_calls:
                continue
            # 跳过 ToolMessage（工具执行结果，最终 AI 回复已包含摘要）
            if isinstance(msg, ToolMessage):
                continue
            result.append({
                "role": _map_lc_role(msg),
                "content": _serialize_content(msg),
            })
        return result

    # 回退：从旧 AiSessionMessage 表读取（兼容重构前的历史数据）
    from backend.models.ai_session import AiSessionMessage
    rows = await db.execute(
        select(AiSessionMessage)
        .where(AiSessionMessage.session_id == session_id)
        .order_by(AiSessionMessage.seq)
    )
    msgs = rows.scalars().all()
    return [{"role": m.role, "content": m.content} for m in msgs]
