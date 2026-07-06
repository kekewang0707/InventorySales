"""AI 快捷操作核心服务 — 文本 ReAct 模式（Thought -> Action -> Observation）

v1.1.0 新增：多轮对话记忆（服务端 Session + SQLite 持久化）
"""
import asyncio
import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple

from openai import OpenAI
from sqlalchemy import select, delete

from backend.config import (
    OPENAI_API_KEY,
    OPENAI_MODEL,
    OPENAI_BASE_URL,
    is_openai_configured,
)
from backend.services import audit_service
from backend.models.ai_session import AiSession, AiSessionMessage
from .function import (
    tools,
)

logger = logging.getLogger(__name__)
_handler = logging.StreamHandler()
_handler.setLevel(logging.INFO)
_handler.setFormatter(logging.Formatter("BACKEND: %(message)s"))
logger.addHandler(_handler)
logger.setLevel(logging.INFO)
logger.propagate = False

# ============================================================
# Session / 对话历史 数据结构
# ============================================================


@dataclass
class SessionMessage:
    role: str       # "user" | "assistant" | "tool_call" | "tool_result"
    content: str    # 消息文本 / 工具调用描述 / 工具返回结果


@dataclass
class ConversationSession:
    session_id: str
    messages: List[SessionMessage]
    created_at: datetime
    last_active: datetime
    title: str = ""


# ============================================================
# 全局状态
# ============================================================

# --- Session 缓存 ---
_MAX_SESSIONS = 30
_MAX_SESSION_MESSAGES = 30
_SESSION_LOCK_CLEANUP_INTERVAL = 60
_STALE_SESSION_AGE_HOURS = 168       # 7 天
_sessions: Dict[str, ConversationSession] = {}

# --- Session 级别的锁，保证并发安全 ---
_session_locks: Dict[str, asyncio.Lock] = {}
_op_counter = 0

# --- Pending Action（写入确认） ---
@dataclass
class PendingAction:
    tool_name: str
    params: dict
    text_summary: str
    prompt: str = ""
    history: str = ""
    llm_response: str = ""
    session_id: str = ""               # v1.1.0: 关联的会话 ID
    confirm_message: str = ""          # v1.1.0: 确认前生成的 summary 消息
    created_at: datetime = field(default_factory=datetime.now)


_pending_actions: Dict[str, PendingAction] = {}
_PENDING_TTL = timedelta(minutes=5)
_MAX_REACT_ITERATIONS = 10

# 默认 ReAct 提示词模板
DEFAULT_REACT_PROMPT = """你是一个具备推理和行动能力的AI助手。

## 可用工具
{tools}

## 工作流程
请严格按照以下格式进行回应，每次只能执行一个步骤：

**Thought:** 分析当前问题，思考需要什么信息或采取什么行动。
**Action:** 选择一个行动，格式必须是以下之一：
- `{{tool_name}}[{{tool_input}}]` - 调用指定工具
- `Finish[最终答案]` - 当你有足够信息给出最终答案时

## 重要提醒
1. 每次回应必须包含Thought和Action两部分
2. 工具调用的格式必须严格遵循：工具名[参数]
3. 只有当你确信有足够信息回答问题时，才使用Finish
4. 如果工具返回的信息不够，继续使用其他工具或相同工具的不同参数
{history_section}
## 当前任务
**Question:** {question}

## 执行历史
{history}

现在开始你的推理和行动："""


# ============================================================
# Session 管理 — 并发锁
# ============================================================


def _get_session_lock(session_id: str) -> asyncio.Lock:
    """获取 session 级别的锁（lazy 初始化）。"""
    if session_id not in _session_locks:
        _session_locks[session_id] = asyncio.Lock()
    return _session_locks[session_id]


def _cleanup_orphan_locks():
    """移除已不存在会话的锁对象，防止内存泄漏。"""
    dead = [sid for sid in _session_locks if sid not in _sessions]
    for sid in dead:
        _session_locks.pop(sid, None)


def _maybe_cleanup_locks():
    """每 _SESSION_LOCK_CLEANUP_INTERVAL 次操作清理一次孤儿锁。"""
    global _op_counter
    _op_counter += 1
    if _op_counter % _SESSION_LOCK_CLEANUP_INTERVAL == 0:
        _cleanup_orphan_locks()


# ============================================================
# Session 管理 — 数据读写
# ============================================================


async def _get_or_create_session(db, session_id: str = "") -> Tuple[str, ConversationSession]:
    """根据 session_id 获取已有会话，或创建新会话。返回 (session_id, session)。"""
    await _evict_sessions_if_needed(db)
    if session_id and session_id in _sessions:
        session = _sessions[session_id]
        session.last_active = datetime.now()
        return session_id, session
    # 创建新会话（写内存 + 写 DB）
    new_id = uuid.uuid4().hex
    session = ConversationSession(
        session_id=new_id,
        messages=[],
        created_at=datetime.now(),
        last_active=datetime.now(),
        title="",
    )
    _sessions[new_id] = session
    db.add(AiSession(session_id=new_id, created_at=session.created_at, last_active=session.last_active))
    await db.commit()
    _maybe_cleanup_locks()
    return new_id, session


def _build_prompt_with_history(question: str, session: ConversationSession, tools_desc: str) -> str:
    """构建包含对话历史的 LLM prompt。"""
    # 从 session 消息构建对话历史块
    history_lines = []
    for msg in session.messages:
        if msg.role == "user":
            history_lines.append(f"user: {msg.content}")
        elif msg.role == "assistant":
            history_lines.append(f"assistant: {msg.content}")

    history_section = ""
    if history_lines:
        history_section = "\n## 对话历史\n" + "\n".join(history_lines) + "\n"

    return DEFAULT_REACT_PROMPT.format(
        tools=tools_desc,
        question=question,
        history="（新的一轮对话，初始无执行历史）",
        history_section=history_section,
    )


async def _append_message_with_retry(db, session: ConversationSession, msg: SessionMessage,
                                      max_retries: int = 3):
    """带重试的消息追加。先写内存（不会失败），再写 DB（失败时指数退避重试）。"""
    session.messages.append(msg)
    session.last_active = datetime.now()

    last_exc = None
    for attempt in range(max_retries):
        try:
            seq = len(session.messages)
            db_msg = AiSessionMessage(
                session_id=session.session_id,
                seq=seq,
                role=msg.role,
                content=msg.content,
            )
            db.add(db_msg)
            await db.commit()

            # 裁剪：超过上限时保留首条 + 最新 N-1 条
            if len(session.messages) > _MAX_SESSION_MESSAGES:
                trimmed_count = len(session.messages) - _MAX_SESSION_MESSAGES + 1
                first = session.messages[0]
                keep_from = trimmed_count + 1
                session.messages = [first] + session.messages[keep_from:]
                session.messages.insert(1, SessionMessage(
                    role="assistant",
                    content=f"...（省略了 {trimmed_count} 条历史消息）..."
                ))
            return
        except Exception as e:
            last_exc = e
            await db.rollback()
            if attempt < max_retries - 1:
                await asyncio.sleep(0.1 * (attempt + 1))
                continue

    # 全部重试失败：从内存回滚
    session.messages.pop()
    logger.warning("Failed to append message after %d retries: %s", max_retries, last_exc)
    raise last_exc


async def _evict_sessions_if_needed(db):
    """超出 _MAX_SESSIONS 上限时，淘汰 last_active 最早的会话（内存 + DB 同步删除）。"""
    if len(_sessions) <= _MAX_SESSIONS:
        return
    sorted_sessions = sorted(_sessions.items(), key=lambda kv: kv[1].last_active)
    evict_count = len(_sessions) - _MAX_SESSIONS
    to_evict = [sid for sid, _ in sorted_sessions[:evict_count]]
    for sid in to_evict:
        _sessions.pop(sid, None)
    if to_evict:
        await db.execute(delete(AiSession).where(AiSession.session_id.in_(to_evict)))
        await db.commit()
        _cleanup_orphan_locks()
        logger.info("Evicted %d stale session(s), remaining: %d", evict_count, len(_sessions))


async def load_sessions_from_db(db):
    """从 DB 加载所有会话到内存 _sessions，在应用 startup 时调用。"""
    rows = await db.execute(
        select(AiSession).order_by(AiSession.last_active.desc()).limit(_MAX_SESSIONS)
    )
    sessions = rows.scalars().all()
    for s in sessions:
        msg_rows = await db.execute(
            select(AiSessionMessage)
            .where(AiSessionMessage.session_id == s.session_id)
            .order_by(AiSessionMessage.seq)
        )
        msgs = msg_rows.scalars().all()
        session = ConversationSession(
            session_id=s.session_id,
            messages=[SessionMessage(role=m.role, content=m.content) for m in msgs],
            created_at=s.created_at,
            last_active=s.last_active,
            title=s.title or "",
        )
        _sessions[s.session_id] = session
    logger.info("Loaded %d AI sessions from DB", len(sessions))


async def cleanup_stale_sessions(db, max_age_hours: int = _STALE_SESSION_AGE_HOURS):
    """清理长时间未活动的会话（默认 7 天）。"""
    cutoff = datetime.now() - timedelta(hours=max_age_hours)
    stale = [sid for sid, s in _sessions.items() if s.last_active < cutoff]
    if not stale:
        return
    await db.execute(delete(AiSession).where(AiSession.session_id.in_(stale)))
    await db.commit()
    for sid in stale:
        _sessions.pop(sid, None)
    if _session_locks:
        _cleanup_orphan_locks()
    logger.info("Cleaned up %d stale session(s) older than %dh", len(stale), max_age_hours)



async def get_session_messages(session_id: str, db) -> list[dict]:
    """获取指定会话的消息列表。"""
    if session_id in _sessions:
        session = _sessions[session_id]
        return [
            {"role": msg.role, "content": msg.content}
            for msg in session.messages
        ]
    # Fallback: try DB directly
    rows = await db.execute(
        select(AiSessionMessage)
        .where(AiSessionMessage.session_id == session_id)
        .order_by(AiSessionMessage.seq)
    )
    msgs = rows.scalars().all()
    return [{"role": m.role, "content": m.content} for m in msgs]



async def rename_session(session_id: str, title: str, db) -> bool:
    """修改会话的自定义标题（内存 + DB）。"""
    if session_id in _sessions:
        _sessions[session_id].title = title
    await db.execute(
        __import__("sqlalchemy").update(AiSession)
        .where(AiSession.session_id == session_id)
        .values(title=title)
    )
    await db.commit()
    return True

def get_all_sessions_info() -> list[dict]:
    """返回所有活跃会话的元信息列表（用于前端 tab 展示）。"""
    result = []
    for sid, session in _sessions.items():
        first_msg = ""
        if session.messages and session.messages[0].content:
            first_msg = session.messages[0].content[:80]
        result.append({
            "session_id": sid,
            "message_count": len(session.messages),
            "first_message": first_msg,
            "title": session.title,
            "last_active": session.last_active.isoformat(),
            "created_at": session.created_at.isoformat(),
        })
    result.sort(key=lambda x: x["last_active"], reverse=True)
    return result


async def delete_session(session_id: str, db) -> bool:
    """从内存和 DB 中删除指定会话。"""
    if session_id not in _sessions:
        return False
    # 先删 DB，成功后再删内存
    await db.execute(delete(AiSession).where(AiSession.session_id == session_id))
    await db.commit()
    _sessions.pop(session_id, None)
    if session_id in _session_locks:
        _session_locks.pop(session_id, None)
    return True

# ============================================================
# Pending Action 管理
# ============================================================


def _clean_expired():
    now = datetime.now()
    expired = [k for k, v in _pending_actions.items()
               if now - v.created_at > _PENDING_TTL]
    for k in expired:
        _pending_actions.pop(k, None)


# ============================================================
# ReAct 文本协议解析
# ============================================================


_ACTION_RE = re.compile(r"\*{0,2}Action:\*{0,2}\s+(\w+)\[(.*?)\]", re.DOTALL)


def _parse_output(text: str) -> dict:
    m = _ACTION_RE.search(text)

    if not m:
        return {"type": "error", "message": "无法解析 LLM 输出的 Action"}
    thought_match = re.search(r"\*{0,2}Thought:\*{0,2}\s+(.*)", text)
    action_match = re.search(r"\*{0,2}Action:\*{0,2}\s+(.*)", text)

    action = action_match.group(1).strip() if action_match else None
    if action.startswith("Finish"):
        final_answer = _parse_action_input(action)
        return {"type": "finish", "answer": final_answer}
    action_name, action_input = _parse_action(action)
    return {"type": "tool", "name": action_name, "input": action_input}


def _parse_action(action_text: str) -> Tuple[Optional[str], Optional[str]]:
    """解析行动文本，提取工具名称和输入"""
    match = re.match(r"(\w+)\[(.*)\]", action_text)
    if match:
        return match.group(1), match.group(2)
    return None, None


def _parse_action_input(action_text: str) -> str:
    """解析行动输入"""
    match = re.match(r"\w+\[(.*)\]", action_text)
    return match.group(1) if match else ""


def _parse_tool_input(tool_name: str, input_text: str) -> dict:
    if not input_text:
        return {}
    if input_text.startswith("{"):
        try:
            return json.loads(input_text)
        except json.JSONDecodeError:
            pass
    if "=" in input_text:
        params = {}
        for part in input_text.split(","):
            part = part.strip()
            if "=" in part:
                k, v = part.split("=", 1)
                params[k.strip()] = v.strip()
        return params
    return {"query": input_text}


# ============================================================
# 工具执行路由（委托给 function 包）
# ============================================================


async def _execute_query_tool(tool_name: str, params: dict, db) -> str:
    return await tools.execute_query(tool_name, params, db)


def _summarize_write_tool(tool_name: str, params: dict) -> str:
    return tools.summarize_write(tool_name, params)


async def _execute_write_tool(tool_name: str, params: dict, db) -> str:
    return await tools.execute_write(tool_name, params, db)


# ============================================================
# 文本 LLM 调用
# ============================================================


async def _call_llm_text(prompt: str) -> str:
    logger.info("=== LLM 请求 === prompt_len=%d", len(prompt))

    def _sync_call():
        client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
        res = client.chat.completions.create(
            model=OPENAI_MODEL,
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
        return res.choices[0].message.content or ""

    result = await asyncio.to_thread(_sync_call)
    logger.info("=== LLM 回复 === %s", result[:500])
    return result


# ============================================================
# ReAct 主循环（文本协议）
# ============================================================


async def _run_react_loop(question: str, db, session: Optional[ConversationSession] = None) -> dict:
    tools_desc = tools.get_tools_description()
    history = ""  # 当前 ReAct 循环内的 tool observation 历史，跨迭代累积

    # 构建跨轮对话历史（排除当前轮的 user 消息，避免与 ## 当前任务 重复）
    history_section = ""
    if session:
        history_lines = []
        # 排除最后的当前问题（它在 ## 当前任务 中单独展示）
        hist_msgs = session.messages[:-1] if session.messages else []
        for msg in hist_msgs:
            if msg.role == "user":
                history_lines.append(f"user: {msg.content}")
            elif msg.role == "assistant":
                history_lines.append(f"assistant: {msg.content}")
        if history_lines:
            history_section = "\n## 对话历史\n" + "\n".join(history_lines) + "\n"


    for iteration in range(_MAX_REACT_ITERATIONS):
        logger.info("ReAct iteration %d/%d", iteration + 1, _MAX_REACT_ITERATIONS)

        # 每次迭代都用最新的 history（累积的 tool observation）
        prompt = DEFAULT_REACT_PROMPT.format(
            tools=tools_desc,
            question=question,
            history=history,
            history_section=history_section,
        )

        response = await _call_llm_text(prompt)
        action = _parse_output(response)

        if action["type"] == "error":
            return {"action": "error", "reply": action["message"], "confirm_id": None, "tool_calls": None}
        if action["type"] == "finish":
            logger.info("=== ReAct 结束 === %s", action["answer"][:300])
            return {"action": "queried", "reply": action["answer"], "confirm_id": None, "tool_calls": None}

        tool_name = action["name"]
        tool_input = action["input"]
        if not tools.has(tool_name):
            history += "\n**Observation:** 错误：未知工具 '" + tool_name + "'\n"
            continue

        if tools.is_write(tool_name):
            params = _parse_tool_input(tool_name, tool_input)
            summary = _summarize_write_tool(tool_name, params)
            confirm_id = uuid.uuid4().hex
            _clean_expired()
            _pending_actions[confirm_id] = PendingAction(
                tool_name=tool_name, params=params, text_summary=summary,
                prompt=prompt, history=history, llm_response=response,
            )
            await audit_service.log_create(db, "ai_command", 0,
                                           {"user_text": question,
                                            "tool_call": {"name": tool_name, "arguments": params},
                                            "status": "pending_confirm"})
            return {"action": "needs_confirm", "reply": summary, "confirm_id": confirm_id,
                    "tool_calls": [{"name": tool_name, "arguments": params}]}

        logger.info("=== 执行查询工具 === %s input=%s", tool_name, tool_input)
        params = _parse_tool_input(tool_name, tool_input)
        try:
            result_text = await _execute_query_tool(tool_name, params, db)
        except Exception as e:
            result_text = f"执行出错: {e}"
        logger.info("=== 工具结果 === %s", result_text[:200])
        history += "\n**Observation:** " + result_text + "\n"

    logger.warning("=== ReAct 达到最大迭代次数 %d ===", _MAX_REACT_ITERATIONS)
    return {"action": "error", "reply": "指令处理超时，请尝试分解为更简单的步骤", "confirm_id": None, "tool_calls": None}


# ============================================================
# 公开入口
# ============================================================


async def handle_command(text: str, db, session_id: str = "") -> dict:
    text = text.strip()
    if not text:
        return {"action": "error", "reply": "请输入指令", "confirm_id": None,
                "tool_calls": None, "session_id": session_id}

    # 获取/创建会话
    sid, session = await _get_or_create_session(db, session_id)
    session.last_active = datetime.now()
    lock = _get_session_lock(sid)

    async with lock:
        # 追加用户消息（写内存 + 写 DB）
        await _append_message_with_retry(db, session, SessionMessage(role="user", content=text))

        if not is_openai_configured():
            result = await _try_offline(text, db)
            result["session_id"] = sid
            if result["action"] == "queried":
                await _append_message_with_retry(db, session, SessionMessage(role="assistant", content=result["reply"]))
            return result

        try:
            result = await _run_react_loop(text, db, session)
            result["session_id"] = sid

            if result["action"] == "queried":
                await _append_message_with_retry(db, session, SessionMessage(role="assistant", content=result["reply"]))
            elif result["action"] == "needs_confirm":
                cid = result.get("confirm_id")
                if cid and cid in _pending_actions:
                    _pending_actions[cid].session_id = sid

            return result
        except Exception as e:
            logger.warning("ReAct loop failed, falling back to offline: %s", e)
            result = await _try_offline(text, db)
            result["session_id"] = sid
            if result["action"] == "queried":
                await _append_message_with_retry(db, session, SessionMessage(role="assistant", content=result["reply"]))
            return result


async def execute_pending(confirm_id: str, db) -> dict:
    _clean_expired()
    action = _pending_actions.pop(confirm_id, None)
    if not action:
        return {"action": "error", "reply": "确认已过期或无效，请重新输入指令",
                "session_id": ""}

    tool_result = await _execute_write_tool(action.tool_name, action.params, db)
    history = action.history
    params_json = json.dumps(action.params, ensure_ascii=False)
    history += "\n**Action:** %s[%s]\n**Observation:** %s\n" % (action.tool_name, params_json, tool_result)
    prompt = DEFAULT_REACT_PROMPT.format(
        tools=tools.get_tools_description(),
        question="（上一步操作已完成，请总结结果）",
        history=history,
        history_section="",
    )
    try:
        response = await _call_llm_text(prompt)
        reply_action = _parse_output(response)
        reply = reply_action["answer"] if reply_action["type"] == "finish" else response
    except Exception as e:
        logger.warning("LLM call after confirm failed: %s", e)
        reply = tool_result

    # 将执行结果追加到关联的 session
    if action.session_id and action.session_id in _sessions:
        session = _sessions[action.session_id]
        # 追加用户的确认消息 + AI 的执行结果
        await _append_message_with_retry(db, session, SessionMessage(role="user", content="确认执行"))
        await _append_message_with_retry(db, session, SessionMessage(role="assistant", content=reply))

    await audit_service.log_create(db, "ai_command", 0,
                                   {"confirmed_tool": action.tool_name, "params": action.params, "result": reply})
    return {"action": "executed", "reply": reply, "session_id": action.session_id}


# ============================================================
# 离线降级
# ============================================================


def _extract_query(text: str) -> str:
    cleaned = re.sub(r"(查|搜|找|查询|搜索|查看|列出|显示|打印|给[我]?看)", "", text).strip()
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


async def _try_offline(text: str, db) -> dict:
    if re.search(r"(创建送货单|新建送货单|开送货单)", text):
        return {"action": "error", "reply": "请详细描述送货单信息：客户、送货日期和产品明细（产品ID、数量、单价）", "confirm_id": None,
                "tool_calls": None}

    patterns = [
        (re.compile(r"(查产品|搜产品|找产品|有哪些产品|产品列表)"), "search_product", {"query": _extract_query(text)}),
        (re.compile(r"(查客户|搜客户|找客户|有哪些客户|客户列表)"), "search_customer", {"query": _extract_query(text)}),
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

    return {"action": "error", "reply": "暂不支持该指令。您可以尝试：查询产品、查询客户、查看送货单、查看对账单等。", "confirm_id": None, "tool_calls": None}
