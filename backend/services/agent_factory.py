"""LangGraph ReAct Agent 工厂。

配置：
- ChatOpenAI 指向 DeepSeek（兼容 OpenAI API）
- 所有查询 + 写入工具
- interrupt_before=["tools"] 暂停所有工具执行（human-in-the-loop）
- AsyncSqliteSaver 持久化 checkpoint
"""

import logging
from typing import Optional

from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage

from backend.config import OPENAI_API_KEY, OPENAI_MODEL, OPENAI_BASE_URL
from backend.services.function.langchain_tools import build_langchain_tools
from backend.services.function.registration import tools as legacy_tools

logger = logging.getLogger(__name__)

# 写入工具名集合（供 ai_service_v2 判断是否需要用户确认）
WRITE_TOOL_NAMES: set[str] = legacy_tools.write_tools

# 系统提示词
_SYSTEM_PROMPT = """你是一个库存销售管理助手，你必须通过调用工具来完成用户的所有请求。

核心规则：
1. 用户说"创建送货单"→ 立即调用 create_delivery_note 工具
2. 用户说"查询产品"→ 立即调用 search_product 工具
3. 用户说"查询客户"→ 立即调用 search_customer 工具
4. 用户说"查看送货单"→ 立即调用 list_delivery_notes 工具
5. 写入工具（create_delivery_note、advance_note_status）直接调用，系统会弹出确认框
6. 不要用自然语言模拟工具执行结果，必须真正调用工具
7. 用中文简洁总结结果"""


def _build_llm() -> ChatOpenAI:
    """构建 ChatOpenAI 实例，指向 DeepSeek 的 OpenAI 兼容端点。"""
    return ChatOpenAI(
        model=OPENAI_MODEL,        # "deepseek-chat"
        api_key=OPENAI_API_KEY,
        base_url=OPENAI_BASE_URL,  # "https://api.deepseek.com/v1"
        temperature=0,
        verbose=False,
    )


async def build_agent(checkpointer: Optional[AsyncSqliteSaver] = None):
    """构建 LangGraph ReAct Agent。

    interrupt_before=["tools"] 让图在执行任何工具前暂停。
    ai_service_v2 在中断时按工具类型分流：
    - 查询工具 → 自动恢复继续执行
    - 写入工具 → 返回 needs_confirm 等待用户确认

    Args:
        checkpointer: 可选的 AsyncSqliteSaver。若为 None，内部会通过 agent_state 获取。

    Returns:
        (agent_graph, checkpointer) 元组
    """
    if checkpointer is None:
        from backend.services.agent_state import get_checkpointer
        checkpointer = await get_checkpointer()

    llm = _build_llm()
    lc_tools = build_langchain_tools(legacy_tools)

    logger.info(
        "Building agent: model=%s, tools=%d, write_tools=%s",
        OPENAI_MODEL, len(lc_tools), sorted(WRITE_TOOL_NAMES),
    )

    agent = create_react_agent(
        model=llm,
        tools=lc_tools,
        checkpointer=checkpointer,
        interrupt_before=["tools"],
        state_modifier=SystemMessage(content=_SYSTEM_PROMPT),
    )

    return agent, checkpointer
