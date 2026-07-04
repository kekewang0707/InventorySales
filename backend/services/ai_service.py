"""AI 快捷操作核心服务 — 文本 ReAct 模式（Thought -> Action -> Observation）"""
import asyncio
import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from typing import Dict, Optional, Tuple

from openai import OpenAI

from backend.config import (
    OPENAI_API_KEY,
    OPENAI_MODEL,
    OPENAI_BASE_URL,
    is_openai_configured,
)
from backend.services import audit_service
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

## 当前任务
**Question:** {question}

## 执行历史
{history}

现在开始你的推理和行动："""


# ---- Pending Action Session ----


@dataclass
class PendingAction:
    tool_name: str
    params: dict
    text_summary: str
    prompt: str = ""
    history: str = ""
    llm_response: str = ""
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


# ---- ReAct 文本协议解析 ----


_ACTION_RE = re.compile(r"Action:\s+(\w+)\[(.*?)\]", re.DOTALL)


def _parse_output(text: str) -> dict:
    m = _ACTION_RE.search(text)

    if not m:
        return {"type": "error", "message": "无法解析 LLM 输出的 Action"}
    thought_match = re.search(r"Thought: (.*)", text)
    action_match = re.search(r"Action: (.*)", text)

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


# ---- 工具执行路由（委托给 function 包） ----


async def _execute_query_tool(tool_name: str, params: dict, db) -> str:
    return await tools.execute_query(tool_name, params, db)


def _summarize_write_tool(tool_name: str, params: dict) -> str:
    return tools.summarize_write(tool_name, params)


async def _execute_write_tool(tool_name: str, params: dict, db) -> str:
    return await tools.execute_write(tool_name, params, db)


# ---- 文本 LLM 调用 ----


async def _call_llm_text(prompt: str) -> str:
    logger.info("=== LLM 请求 === prompt_len=%d", len(prompt))

    def _sync_call():
        client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
        res = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
        return res.choices[0].message.content or ""

    result = await asyncio.to_thread(_sync_call)
    logger.info("=== LLM 回复 === %s", result[:500])
    return result


# ---- ReAct 主循环（文本协议） ----


async def _run_react_loop(question: str, db) -> dict:
    tools_desc = tools.get_tools_description()
    history = ""

    for iteration in range(_MAX_REACT_ITERATIONS):
        logger.info("ReAct iteration %d/%d", iteration + 1, _MAX_REACT_ITERATIONS)
        prompt = DEFAULT_REACT_PROMPT.format(tools=tools_desc, question=question, history=history)
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


# ---- 公开入口 ----


async def handle_command(text: str, db) -> dict:
    text = text.strip()
    if not text:
        return {"action": "error", "reply": "请输入指令", "confirm_id": None, "tool_calls": None}
    if not is_openai_configured():
        return await _try_offline(text, db)
    try:
        return await _run_react_loop(text, db)
    except Exception as e:
        logger.warning("ReAct loop failed, falling back to offline: %s", e)
        return await _try_offline(text, db)


async def execute_pending(confirm_id: str, db) -> dict:
    _clean_expired()
    action = _pending_actions.pop(confirm_id, None)
    if not action:
        return {"action": "error", "reply": "确认已过期或无效，请重新输入指令"}
    tool_result = await _execute_write_tool(action.tool_name, action.params, db)
    history = action.history
    params_json = json.dumps(action.params, ensure_ascii=False)
    history += "\n**Action:** %s[%s]\n**Observation:** %s\n" % (action.tool_name, params_json, tool_result)
    prompt = DEFAULT_REACT_PROMPT.format(tools=tools.get_tools_description(), question="（上一步操作已完成，请总结结果）",
                                         history=history)
    try:
        response = await _call_llm_text(prompt)
        reply_action = _parse_output(response)
        reply = reply_action["answer"] if reply_action["type"] == "finish" else response
    except Exception as e:
        logger.warning("LLM call after confirm failed: %s", e)
        reply = tool_result
    await audit_service.log_create(db, "ai_command", 0,
                                   {"confirmed_tool": action.tool_name, "params": action.params, "result": reply})
    return {"action": "executed", "reply": reply}


# ---- 离线降级 ----


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
