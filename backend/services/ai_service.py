"""AI 快捷操作核心服务 — ReAct 模式（Reason + Act）"""
import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from openai import OpenAI

from backend.config import (
    OPENAI_API_KEY,
    OPENAI_MODEL,
    OPENAI_BASE_URL,
    is_openai_configured,
)
from backend.services import audit_service
from .function import (
    _tools,
    FUNCTION_DEFINITIONS,
    _QUERY_TOOLS,
    _WRITE_TOOLS,
)


logger = logging.getLogger(__name__)
_handler = logging.StreamHandler()
_handler.setLevel(logging.INFO)
_handler.setFormatter(logging.Formatter("BACKEND: %(message)s"))
logger.addHandler(_handler)
logger.setLevel(logging.INFO)
logger.propagate = False


# ---- Pending Action Session ----


@dataclass
class PendingAction:
    tool_name: str
    params: dict
    text_summary: str
    messages: list = field(default_factory=list)
    assistant_msg: Optional[dict] = None
    tool_call_id: str = ""
    created_at: datetime = field(default_factory=datetime.now)


_pending_actions: Dict[str, PendingAction] = {}
_PENDING_TTL = timedelta(minutes=5)
_MAX_REACT_ITERATIONS = 10


def _clean_expired():
    now = datetime.now()
    expired = [k for k, v in _pending_actions.items()
               if now - v.created_at > _PENDING_TTL]
    for k in expired:
        _pending_actions.pop(k, None)


# ---- 工具执行路由（委托给 function 包） ----


async def _execute_query_tool(tool_name: str, params: dict, db) -> str:
    """委托 function 包执行查询类 tool"""
    return await _tools.execute_query(tool_name, params, db)


def _summarize_write_tool(tool_name: str, params: dict) -> str:
    """委托 function 包生成写入摘要"""
    return _tools.summarize_write(tool_name, params)


async def _execute_write_tool(tool_name: str, params: dict, db) -> str:
    """委托 function 包执行写入操作"""
    return await _tools.execute_write(tool_name, params, db)

_SYSTEM_PROMPT_TEMPLATE = """\
你是一个工厂销售出库管理系统的 AI 助手，系统名为 InventorySales。
你可以使用工具查询产品、客户、送货单、对账单、操作日志等信息。
工具执行结果会以文本形式返回，请根据结果组织自然语言回复。

当前日期：{today}

核心约束：
- 查询类工具 → 直接调用，根据返回结果组织回答。
- 写入类工具（create_*, advance_*）→ 先通过工具返回操作摘要引导用户确认，不要自行执行。
- 可以连续调用多个查询工具来回答复杂问题。
- 日期格式统一使用 YYYY-MM-DD。
- 货币单位是元（CNY），保留两位小数。
- 当用户问"今天"时使用 {today}；"最近"默认为最近 7 天。
- 结果为空时明确告知用户。
- 回复时用中文，语言简洁自然，关键信息（数字、名称、金额）放在前面。
- 对列表类结果做简要汇总，不要逐条朗读全部数据。"""


# ---- 构建消息 ----

def _build_system_prompt() -> str:
    today_str = datetime.now().strftime("%Y-%m-%d")
    return _SYSTEM_PROMPT_TEMPLATE.format(today=today_str)
def _extract_query(text: str) -> str:
    cleaned = re.sub(
        r"(查|搜|找|查询|搜索|查看|列出|显示|打印|给[我]?看)",
        "", text
    ).strip()
    return cleaned if cleaned else text


def _extract_date(text: str) -> Optional[date]:
    today = date.today()
    if any(w in text for w in ["今天", "今日"]):
        return today
    if any(w in text for w in ["昨天", "昨日"]):
        return today - timedelta(days=1)
    if any(w in text for w in ["本周", "这周"]):
        return today - timedelta(days=today.weekday())
    if any(w in text for w in ["本月", "这个月"]):
        return date(today.year, today.month, 1)
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return None


async def _try_offline(text: str, db) -> dict:
    """离线规则匹配 — 关键词 + 正则"""
    # 特殊规则：创建送货单
    if re.search(r"(创建送货单|新建送货单|开送货单)", text):
        return {
            "action": "error",
            "reply": "请详细描述送货单信息：客户、送货日期和产品明细（产品ID、数量、单价）",
            "confirm_id": None,
            "tool_calls": None,
        }

    patterns = [
        (re.compile(r"(查产品|搜产品|找产品|有哪些产品|产品列表)"), "search_product", {"query": _extract_query(text)}),
        (re.compile(r"(查客户|搜客户|找客户|有哪些客户|客户列表)"), "search_customer", {"query": _extract_query(text)}),
        (re.compile(r"(送货单|出库单|今天.*送货|最近.*送货)"), "list_delivery_notes", _list_dn_offline_params(text)),
        (re.compile(r"(对账单|对账|账单)"), "get_statement", {"start_date": date(datetime.now().year, datetime.now().month, 1).isoformat(), "end_date": datetime.now().strftime("%Y-%m-%d")}),
        (re.compile(r"(统计|概况|概览|总[计共])"), "get_statistics", {}),
        (re.compile(r"(操作日志|操作记录|审计日志|历史记录)"), "get_recent_logs", {}),
    ]
    for pattern, tool_name, params in patterns:
        if not pattern.search(text):
            continue
        reply = await _tools.execute_query(tool_name, params, db)
        return {
            "action": "queried",
            "reply": f"{reply}\n\n(离线模式)",
            "confirm_id": None,
            "tool_calls": None,
        }

    return {
        "action": "error",
        "reply": "暂不支持该指令。您可以尝试：查询产品、查询客户、查看送货单、查看对账单等。",
        "confirm_id": None,
        "tool_calls": None,
    }


def _list_dn_offline_params(text: str) -> dict:
    d = _extract_date(text)
    if d:
        return {"start_date": d.isoformat(), "end_date": (d + timedelta(days=1)).isoformat()}
    return {"page": 1}

    # ====================================================================
#  ReAct 主循环
# ====================================================================

async def _call_llm(messages: list):
    import asyncio

    # 打印本轮 LLM 调用消息（去除非 ASCII 字符的敏感信息）
    logger.info("=== LLM 请求 === role_count=%d", len(messages))
    for i, m in enumerate(messages):
        role = m.get("role", "?")
        content_preview = (m.get("content") or "")[:200]
        if m.get("tool_calls"):
            tools = [tc["function"]["name"] for tc in m["tool_calls"]]
            logger.info("  [%d] role=%s tool_calls=%s | content=%s", i, role, tools, content_preview[:120])
        elif m.get("role") == "tool":
            logger.info("  [%d] role=%s tool_result=%s...", i, role, (content_preview[:120]))
        else:
            logger.info("  [%d] role=%s | %s", i, role, content_preview[:200])

    def _sync_call():
        client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            tools=FUNCTION_DEFINITIONS,
            tool_choice="auto",
        )
        return response.choices[0].message

    result = await asyncio.to_thread(_sync_call)
    if hasattr(result, 'tool_calls') and result.tool_calls:
        tc = result.tool_calls[0]
        logger.info("=== LLM 回复 (tool_call) === name=%s args=%s", tc.function.name, tc.function.arguments[:300])
    elif hasattr(result, 'content') and result.content:
        logger.info("=== LLM 回复 (text) === %s", result.content[:300])
    else:
        logger.info("=== LLM 回复 === (空或无 tool_calls)")
    return result


async def _run_react_loop(
    messages: list,
    db,
    max_iterations: int = _MAX_REACT_ITERATIONS,
) -> dict:
    """ReAct 主循环：Reason → Act → Observe → Reason...

    返回 dict（与 handle_command 返回格式一致）。
    """
    for iteration in range(max_iterations):
        logger.info("ReAct iteration %d/%d", iteration + 1, max_iterations)

        msg = await _call_llm(messages)

        if msg.tool_calls and len(msg.tool_calls) > 0:
            tc = msg.tool_calls[0]
            try:
                tool_name = tc.function.name
                params = json.loads(tc.function.arguments)
            except (json.JSONDecodeError, AttributeError) as e:
                return {
                    "action": "error",
                    "reply": f"解析指令失败: {e}",
                    "confirm_id": None,
                    "tool_calls": None,
                }

            # 构建 assistant message（带 tool_calls）
            assistant_msg = {
                "role": "assistant",
                "content": msg.content,
            }
            # OpenAI API 要求 tool_calls 中的 function.arguments 是 JSON 字符串
            assistant_msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tool_name,
                        "arguments": tc.function.arguments,
                    },
                }
            ]

            if tool_name in _WRITE_TOOLS:
                # ---- 写入类：暂存，返回确认 ----
                logger.info("=== 写工具 (需确认) === %s params=%s", tool_name, json.dumps(params, ensure_ascii=False)[:300])
                summary = _summarize_write_tool(tool_name, params)
                confirm_id = uuid.uuid4().hex
                _clean_expired()
                _pending_actions[confirm_id] = PendingAction(
                    tool_name=tool_name,
                    params=params,
                    text_summary=summary,
                    messages=list(messages),        # 保存当前对话
                    assistant_msg=assistant_msg,    # 保存触发写入的 assistant 消息
                    tool_call_id=tc.id,
                )
                await audit_service.log_create(
                    db, "ai_command", 0,
                    {"user_text": messages[-1].get("content", ""),
                     "tool_call": {"name": tool_name, "arguments": params},
                     "status": "pending_confirm"},
                )
                return {
                    "action": "needs_confirm",
                    "reply": summary,
                    "confirm_id": confirm_id,
                    "tool_calls": [{"name": tool_name, "arguments": params}],
                }

            elif tool_name in _QUERY_TOOLS:
                # ---- 查询类：执行并 feed back ----
                logger.info("=== 执行查询工具 === %s params=%s", tool_name, json.dumps(params, ensure_ascii=False)[:200])
                result_text = await _execute_query_tool(tool_name, params, db)
                logger.info("=== 工具结果 === tool=%s result=%s", tool_name, result_text[:200])

                messages.append(assistant_msg)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result_text,
                })
                # 继续下一轮 Reason
                continue

            else:
                return {
                    "action": "error",
                    "reply": f"未知操作: {tool_name}",
                    "confirm_id": None,
                    "tool_calls": None,
                }

        else:
            # ---- LLM 返回最终文本 ----
            reply_text = (msg.content or "").strip()
            if not reply_text:
                logger.warning("=== LLM 返回了空回复 ===")
                return {
                    "action": "error",
                    "reply": "AI 返回了空回复",
                    "confirm_id": None,
                    "tool_calls": None,
                }
            logger.info("=== ReAct 结束 === reply=%s", reply_text[:300])
            return {
                "action": "queried",
                "reply": reply_text,
                "confirm_id": None,
                "tool_calls": None,
            }

    # 到达最大迭代次数
    logger.warning("=== ReAct 达到最大迭代次数 %d ===", max_iterations)
    return {
        "action": "error",
        "reply": "指令处理超时，请尝试分解为更简单的步骤",
        "confirm_id": None,
        "tool_calls": None,
    }


# ---- 公开入口 ----

async def handle_command(text: str, db) -> dict:
    """处理用户 AI 指令 — ReAct 模式

    返回 dict:
    - action: "queried" | "needs_confirm" | "error"
    - reply: 自然语言回复
    - confirm_id: 写入操作暂存的 session ID
    - tool_calls: 触发写入的 tool 信息
    """
    text = text.strip()
    if not text:
        return {
            "action": "error",
            "reply": "请输入指令",
            "confirm_id": None,
            "tool_calls": None,
        }

    # 没有 API Key → 离线模式
    if not is_openai_configured():
        return await _try_offline(text, db)

    # 构建初始 messages
    messages = [
        {"role": "system", "content": _build_system_prompt()},
        {"role": "user", "content": text},
    ]

    # ReAct 主循环；若 LLM 调用失败，降级到离线模式
    try:
        return await _run_react_loop(messages, db)
    except Exception as e:
        logger.warning("ReAct loop failed, falling back to offline: %s", e)
        return await _try_offline(text, db)


async def execute_pending(confirm_id: str, db) -> dict:
    """执行已确认的待处理操作，并将结果喂回 LLM 生成自然语言回复

    返回 dict:
    - action: "executed" | "error"
    - reply: LLM 生成的自然语言回复
    """
    _clean_expired()
    action = _pending_actions.pop(confirm_id, None)
    if not action:
        return {
            "action": "error",
            "reply": "确认已过期或无效，请重新输入指令",
        }

    # 1. 执行写入操作
    tool_result = await _execute_write_tool(action.tool_name, action.params, db)

    # 2. 恢复对话上下文，追加 assistant + tool result
    messages = action.messages
    messages.append(action.assistant_msg)
    messages.append({
        "role": "tool",
        "tool_call_id": action.tool_call_id,
        "content": tool_result,
    })

    # 3. 再调用一次 LLM，让其基于结果生成自然语言回复
    logger.info("=== 确认后继续 ReAct === tool=%s result=%s", action.tool_name, tool_result[:200])
    try:
        msg = await _call_llm(messages)
    except Exception as e:
        logger.warning("LLM call after confirm failed: %s", e)
        return {
            "action": "executed",
            "reply": tool_result,
        }

    reply = (msg.content or "").strip()

    # 审计日志
    await audit_service.log_create(
        db, "ai_command", 0,
        {"confirmed_tool": action.tool_name,
         "params": action.params,
         "result": reply or tool_result},
    )

    return {
        "action": "executed",
        "reply": reply or tool_result,
    }
