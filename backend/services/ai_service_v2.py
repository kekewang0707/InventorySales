"""AI 服务 v2 — 基于 LangGraph ReAct Agent + Human-in-the-Loop。

替代旧版自定义 ReAct 文本协议，使用 LangGraph create_react_agent。
保持与旧版 ai_service 完全相同的公开 API 签名。
"""

import logging
import re
import uuid
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional

from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.types import Command

from backend.config import is_openai_configured
from backend.models.ai_session import AiSession, AiSessionMessage
from backend.services.agent_factory import build_agent, WRITE_TOOL_NAMES
from backend.services.agent_state import (
    get_checkpointer,
    build_config,
    ensure_session_exists,
    touch_session,
    get_session_messages as _get_checkpoint_messages,
)

logger = logging.getLogger(__name__)
_handler = logging.StreamHandler()
_handler.setLevel(logging.INFO)
_handler.setFormatter(logging.Formatter("BACKEND: %(message)s"))
logger.addHandler(_handler)
logger.setLevel(logging.INFO)
logger.propagate = False

# ReAct 迭代上限
_MAX_REACT_ITERATIONS = 10

# ============================================================
# 会话元数据管理（AiSession 表）
# ============================================================

_MAX_SESSIONS = 30
_STALE_SESSION_AGE_HOURS = 168  # 7 天

# Session 元数据缓存（用于快速列表查询）
_sessions_meta: Dict[str, dict] = {}


async def load_sessions_from_db(db: AsyncSession):
    """从 DB 加载所有 AiSession 元数据到内存缓存。应用启动时调用。"""
    global _sessions_meta
    rows = await db.execute(
        select(AiSession).order_by(AiSession.last_active.desc()).limit(_MAX_SESSIONS)
    )
    sessions = rows.scalars().all()
    _sessions_meta = {}
    for s in sessions:
        _sessions_meta[s.session_id] = {
            "session_id": s.session_id,
            "created_at": s.created_at,
            "last_active": s.last_active,
            "title": s.title or "",
        }
    logger.info("Loaded %d AI session metadata from DB", len(_sessions_meta))


async def cleanup_stale_sessions(db: AsyncSession, max_age_hours: int = _STALE_SESSION_AGE_HOURS):
    """清理超过 max_age_hours 未活跃的会话（DB + 内存）。"""
    cutoff = datetime.now() - timedelta(hours=max_age_hours)
    stale = [
        sid for sid, m in _sessions_meta.items()
        if m["last_active"] < cutoff
    ]
    if not stale:
        return

    await db.execute(delete(AiSession).where(AiSession.session_id.in_(stale)))
    await db.commit()
    for sid in stale:
        _sessions_meta.pop(sid, None)
    logger.info("Cleaned up %d stale session(s) older than %dh", len(stale), max_age_hours)


def get_all_sessions_info() -> list[dict]:
    """返回活跃会话的元信息列表（供前端 tab 展示）。

    结合内存元数据和最近消息预览。
    """
    result = []
    for sid, meta in _sessions_meta.items():
        result.append({
            "session_id": sid,
            "message_count": meta.get("message_count", 0),
            "first_message": meta.get("first_message", ""),
            "title": meta.get("title", ""),
            "last_active": meta["last_active"].isoformat() if isinstance(meta["last_active"], datetime) else str(meta["last_active"]),
            "created_at": meta["created_at"].isoformat() if isinstance(meta["created_at"], datetime) else str(meta["created_at"]),
        })
    result.sort(key=lambda x: x["last_active"], reverse=True)
    return result


async def rename_session(session_id: str, title: str, db: AsyncSession) -> bool:
    """修改会话标题。"""
    await db.execute(
        update(AiSession)
        .where(AiSession.session_id == session_id)
        .values(title=title)
    )
    await db.commit()
    if session_id in _sessions_meta:
        _sessions_meta[session_id]["title"] = title
    return True


async def delete_session(session_id: str, db: AsyncSession) -> bool:
    """删除会话（DB + 内存元数据）。"""
    if session_id not in _sessions_meta:
        return False
    await db.execute(delete(AiSession).where(AiSession.session_id == session_id))
    await db.commit()
    _sessions_meta.pop(session_id, None)
    return True


async def get_session_messages(session_id: str, db: AsyncSession) -> list[dict]:
    """获取指定会话的消息列表（优先从 LangGraph checkpoint 读取）。"""
    return await _get_checkpoint_messages(session_id, db)


async def _update_session_meta(session_id: str, db: AsyncSession, first_message: str = ""):
    """更新内存中的会话元数据。"""
    if session_id in _sessions_meta:
        _sessions_meta[session_id]["last_active"] = datetime.now()
        if first_message and not _sessions_meta[session_id].get("first_message"):
            _sessions_meta[session_id]["first_message"] = first_message[:80]
    else:
        # 新会话，从 DB 加载或创建
        row = await db.execute(select(AiSession).where(AiSession.session_id == session_id))
        s = row.scalar_one_or_none()
        if s:
            _sessions_meta[session_id] = {
                "session_id": s.session_id,
                "created_at": s.created_at,
                "last_active": datetime.now(),
                "title": s.title or "",
                "first_message": first_message[:80] if first_message else "",
            }

    # 淘汰最旧的会话
    if len(_sessions_meta) > _MAX_SESSIONS:
        sorted_sessions = sorted(
            _sessions_meta.items(),
            key=lambda kv: kv[1]["last_active"] if isinstance(kv[1]["last_active"], datetime) else datetime.min
        )
        evict_count = len(_sessions_meta) - _MAX_SESSIONS
        for sid, _ in sorted_sessions[:evict_count]:
            _sessions_meta.pop(sid, None)


# ============================================================
# Pending Approval 管理（中断恢复）
# ============================================================

# confirm_id → {session_id, tool_name, tool_args}
_pending_approvals: Dict[str, dict] = {}
_PENDING_TTL = timedelta(minutes=5)


def _clean_expired_approvals():
    """清理过期的 pending approvals（每次注册前调用）。"""
    now = datetime.now()
    expired = []
    for cid, info in _pending_approvals.items():
        created_str = info.get("created_at", "")
        if created_str:
            try:
                created = datetime.fromisoformat(created_str)
                if now - created > _PENDING_TTL:
                    expired.append(cid)
            except (ValueError, TypeError):
                expired.append(cid)
    for cid in expired:
        _pending_approvals.pop(cid, None)


# ============================================================
# Agent 执行辅助函数
# ============================================================

def _extract_final_answer(state: dict) -> str:
    """从 agent 状态中提取最终的 AI 回复文本。"""
    messages = state.get("messages", [])
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.content and not msg.tool_calls:
            return msg.content
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.content:
            return str(msg.content)
    return "操作完成"


def _extract_pending_tool_calls(state: dict) -> list[dict]:
    """从 agent 状态的最后一条 AI 消息中提取待执行的 tool_calls。

    LangGraph 的 interrupt_before 在工具执行前保存状态，
    此时最后一条 AIMessage 中会有未执行的 tool_calls。
    """
    messages = state.get("messages", [])
    if not messages:
        return []
    last_msg = messages[-1]
    if isinstance(last_msg, AIMessage) and hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
        return [
            {"name": tc["name"], "args": tc["args"]}
            for tc in last_msg.tool_calls
        ]
    return []


async def _has_stale_interrupt(checkpointer, session_id: str) -> bool:
    """检查 session 的 checkpoint 中是否有未完成的 tool_calls。

    当 interrupt_before=["tools"] 暂停执行后，checkpoint 的最后一条消息
    是带有 tool_calls 的 AIMessage，但没有对应的 ToolMessage。这说明上次
    请求被中断后未正常恢复（用户取消、服务器重启等）。
    """
    try:
        checkpoint_tuple = await checkpointer.aget_tuple(
            {"configurable": {"thread_id": session_id}}
        )
    except Exception:
        return False

    if not checkpoint_tuple or not checkpoint_tuple.checkpoint:
        return False

    channel_values = checkpoint_tuple.checkpoint.get("channel_values", {})
    messages = channel_values.get("messages", [])

    if not messages:
        return False

    last_msg = messages[-1]
    # 如果最后一条消息是 AIMessage 且带有 tool_calls，说明工具被中断未执行
    if (isinstance(last_msg, AIMessage)
            and hasattr(last_msg, "tool_calls")
            and last_msg.tool_calls):
        return True

    return False


def _generate_tool_summary(tool_name: str, args: dict) -> str:
    """生成写入操作的摘要文本（供用户确认）。"""
    from backend.services.function.registration import tools
    return tools.summarize_write(tool_name, args)


# ============================================================
# 公开入口：handle_command / execute_pending
# ============================================================

async def handle_command(text: str, db: AsyncSession, session_id: str = "") -> dict:
    """处理用户文本指令（基于 LangGraph ReAct Agent）。

    使用 interrupt_before=["tools"] 暂停工具执行，根据工具类型分流：
    - 查询工具 → 自动恢复继续执行
    - 写入工具 → 返回 needs_confirm 等待用户确认

    修复：发送新命令前，检查并清理该 session 上的旧中断状态。

    Returns:
        {action, reply, confirm_id, tool_calls, session_id}
    """
    text = text.strip()
    if not text:
        return {"action": "error", "reply": "请输入指令", "confirm_id": None,
                "tool_calls": None, "session_id": session_id}

    # 离线降级
    if not is_openai_configured():
        result = await _try_offline(text, db)
        result["session_id"] = session_id
        return result

    # 确保 session 存在
    sid, is_new = await ensure_session_exists(db, session_id)
    await _update_session_meta(sid, db, first_message=text)

    try:
        checkpointer = await get_checkpointer()
        agent, _ = await build_agent(checkpointer)
        config = build_config(sid, db)

        logger.info("Invoking agent for session=%s, text=%s", sid, text[:100])

        # --- 清理该 session 上的旧中断状态 ---
        # 从 checkpoint 中检测（而非内存中的 _pending_approvals），
        # 因为服务器重启后内存清空但 checkpoint 持久化。
        # 如果 checkpoint 有未解决的 tool_calls，先取消再处理新命令。
        if await _has_stale_interrupt(checkpointer, sid):
            logger.info("Detected stale interrupt in checkpoint for session=%s, clearing...", sid)
            # 清理内存中的旧记录
            stale = [c for c, i in _pending_approvals.items() if i.get("session_id") == sid]
            for c in stale:
                _pending_approvals.pop(c, None)
            # 用 Command(resume=False) 拒绝旧中断
            try:
                await agent.ainvoke(Command(resume=False), config=config)
                logger.info("Stale interrupt cleared for session=%s", sid)
            except Exception as e:
                logger.warning("Failed to clear stale interrupt: %s", e)

        # 正常处理当前命令
        current_input = {"messages": [HumanMessage(content=text)]}

        for iteration in range(_MAX_REACT_ITERATIONS):
            logger.info("Agent iteration %d/%d for session=%s", iteration + 1, _MAX_REACT_ITERATIONS, sid)

            final_state = await agent.ainvoke(current_input, config=config)

            # 检查是否被中断（interrupt_before=["tools"]）
            pending_calls = _extract_pending_tool_calls(final_state)

            if not pending_calls:
                # Agent 正常结束
                final_answer = _extract_final_answer(final_state)
                await touch_session(db, sid)
                logger.info("Agent finished for session=%s, answer_len=%d", sid, len(final_answer))
                return {
                    "action": "queried",
                    "reply": final_answer,
                    "confirm_id": None,
                    "tool_calls": None,
                    "session_id": sid,
                }

            # 有 pending tool calls → 检查是否有写入工具
            write_calls = [tc for tc in pending_calls if tc["name"] in WRITE_TOOL_NAMES]

            if write_calls:
                # 写入工具 → 需要用户确认
                tool_call = write_calls[0]
                _clean_expired_approvals()
                confirm_id = uuid.uuid4().hex
                _pending_approvals[confirm_id] = {
                    "session_id": sid,
                    "tool_name": tool_call["name"],
                    "tool_args": tool_call["args"],
                    "created_at": datetime.now().isoformat(),
                }
                summary = _generate_tool_summary(tool_call["name"], tool_call["args"])
                await touch_session(db, sid)
                logger.info("Agent interrupted before '%s', confirm_id=%s", tool_call["name"], confirm_id)
                return {
                    "action": "needs_confirm",
                    "reply": summary,
                    "confirm_id": confirm_id,
                    "tool_calls": [{"name": tool_call["name"], "arguments": tool_call["args"]}],
                    "session_id": sid,
                }

            # 全部是查询工具 → 自动恢复
            logger.info("Auto-resuming for query tools: %s",
                       [tc["name"] for tc in pending_calls])
            current_input = Command(resume=True)

        logger.warning("Agent reached max iterations for session=%s", sid)
        return {
            "action": "error",
            "reply": "指令处理超时，请尝试分解为更简单的步骤",
            "confirm_id": None,
            "tool_calls": None,
            "session_id": sid,
        }

    except Exception as e:
        logger.warning("LangGraph agent failed, falling back to offline: %s", e)
        result = await _try_offline(text, db)
        result["session_id"] = sid
        return result


async def execute_pending(confirm_id: str, db: AsyncSession) -> dict:
    """用户确认后，恢复执行被中断的 Agent Graph。

    使用 LangGraph 的 Command(resume=True) 让写入工具继续执行，
    工具执行完成后 Agent 自动产生自然语言摘要。

    Returns:
        {action, reply, session_id}
    """
    _clean_expired_approvals()
    approval = _pending_approvals.pop(confirm_id, None)

    if not approval:
        return {"action": "error", "reply": "确认已过期或无效，请重新输入指令",
                "session_id": ""}

    sid = approval["session_id"]
    tool_name = approval["tool_name"]

    try:
        checkpointer = await get_checkpointer()
        agent, _ = await build_agent(checkpointer)
        config = build_config(sid, db)

        logger.info("Resuming agent for session=%s after confirming '%s'", sid, tool_name)

        # Command(resume=True) → 工具继续执行
        final_state = await agent.ainvoke(
            Command(resume=True),
            config=config,
        )

        final_answer = _extract_final_answer(final_state)
        await touch_session(db, sid)

        logger.info("Agent resumed and finished for session=%s", sid)

        return {
            "action": "executed",
            "reply": final_answer,
            "session_id": sid,
        }

    except Exception as e:
        logger.error("Failed to resume agent for confirm_id=%s: %s", confirm_id, e)
        return {"action": "error", "reply": f"执行失败: {e}", "session_id": sid}


# ============================================================
# 离线降级（保留旧版逻辑）
# ============================================================

def _extract_query(text: str) -> str:
    # 长的词优先替换，避免 "查询" 被拆成 "查" + "询" 只替换一半
    cleaned = re.sub(r"(查询|搜索|查看|列出|显示|打印|查|搜|找|给[我]?看)", "", text).strip()
    return cleaned if cleaned else text


def _extract_date(text: str) -> Optional[date]:
    today = date.today()
    if any(w in text for w in ["今天", "今日"]): return today
    if any(w in text for w in ["昨天", "昨日"]): return today - timedelta(days=1)
    if any(w in text for w in ["本周", "这周"]): return today - timedelta(days=today.weekday())
    if any(w in text for w in ["本月", "这个月"]): return date(today.year, today.month, 1)
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    if m: return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return None


def _list_dn_offline_params(text: str) -> dict:
    d = _extract_date(text)
    if d: return {"start_date": d.isoformat(), "end_date": (d + timedelta(days=1)).isoformat()}
    return {"page": 1}


async def _try_offline(text: str, db: AsyncSession) -> dict:
    """离线降级：正则匹配常见查询模式。"""
    from backend.services.function.registration import tools

    if re.search(r"(创建送货单|新建送货单|开送货单)", text):
        return {"action": "error", "reply": "请详细描述送货单信息：客户、送货日期和产品明细（产品ID、数量、单价）",
                "confirm_id": None, "tool_calls": None}

    patterns = [
        (re.compile(r"(查产品|搜产品|找产品|查询产品|搜索产品|有哪些产品|产品列表)"), "search_product", {"query": _extract_query(text)}),
        (re.compile(r"(查客户|搜客户|找客户|查询客户|搜索客户|有哪些客户|客户列表)"), "search_customer", {"query": _extract_query(text)}),
        (re.compile(r"(送货单|出库单|今天.*送货|最近.*送货)"), "list_delivery_notes", _list_dn_offline_params(text)),
        (re.compile(r"(对账单|对账|账单)"), "get_statement",
         {"start_date": date(datetime.now().year, datetime.now().month, 1).isoformat(),
          "end_date": datetime.now().strftime("%Y-%m-%d")}),
        (re.compile(r"(统计|概况|概览|总[计共])"), "get_statistics", {}),
        (re.compile(r"(操作日志|操作记录|审计日志|历史记录)"), "get_recent_logs", {}),
    ]
    for pattern, tool_name, params in patterns:
        if not pattern.search(text): continue
        reply = await tools.execute_query(tool_name, params, db)
        return {"action": "queried", "reply": f"{reply}\n\n(离线模式)", "confirm_id": None, "tool_calls": None}

    return {"action": "error", "reply": "暂不支持该指令。您可以尝试：查询产品、查询客户、查看送货单、查看对账单等。",
            "confirm_id": None, "tool_calls": None}
