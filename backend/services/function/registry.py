"""ToolRegistry — 工具注册表，统一管理工具定义、执行、路由

原生工具系统 API：
  - register_tool(tool)  注册 Tool 对象（推荐）
  - register_function()  直接注册函数（简便）
  - unregister() / list_tools() / clear() / get_tools_description()
  - global_registry      全局单例
同时保留 InventorySales 专用方法：
  - openai_definitions / query_tools / write_tools
  - execute_query() / execute_write() / summarize_write()
"""
import logging
from typing import Any, Callable, Dict, Optional

from .base import Tool

logger = logging.getLogger('backend.services.function')


class ToolRegistry:
    """工具注册表 — 统一管理工具定义、执行路由、离线匹配和 OpenAI function calling 格式生成。"""

    def __init__(self):
        self._tools: Dict[str, Tool] = {}

    # ==================== 注册 / 注销 ====================

    def register_tool(self, tool: Tool):
        """注册一个 Tool 对象（推荐方式）。"""
        self._tools[tool.name] = tool

    def register_function(self, name: str, description: str, func: Callable[[str], str]):
        """直接注册一个函数作为工具（简便方式，参数/返回均为字符串）。"""
        wrapper = Tool(name=name, description=description,
                       parameters={"type": "object", "properties": {
                           "input": {"type": "string", "description": "输入参数"}
                       }, "additionalProperties": False},
                       handler=lambda params, db: func(params.get("input", "")),
                       security="query")
        self._tools[name] = wrapper

    def unregister(self, name: str):
        """注销工具。"""
        self._tools.pop(name, None)

    def clear(self):
        """清空所有工具。"""
        self._tools.clear()

    # ==================== 查询 ====================

    def has(self, name: str) -> bool:
        return name in self._tools

    def is_write(self, name: str) -> bool:
        e = self._tools.get(name)
        return e is not None and e.security == "write"

    def is_query(self, name: str) -> bool:
        e = self._tools.get(name)
        return e is not None and e.security == "query"

    def list_tools(self) -> list:
        """列出所有已注册工具的名称和基本信息。"""
        return [{"name": t.name, "description": t.description, "security": t.security}
                for t in self._tools.values()]

    def get_tool(self, name: str) -> Optional[Tool]:
        """获取指定名称的 Tool 对象。"""
        return self._tools.get(name)

    def get_tools_description(self) -> str:
        """获取所有可用工具的格式化描述字符串（用于构建提示词）。"""
        descriptions = []
        for t in self._tools.values():
            descriptions.append(f"- {t.name}: {t.description}")
        return "\n".join(descriptions) if descriptions else "暂无可用工具"

    # ==================== OpenAI function calling 格式 ====================

    @property
    def openai_definitions(self) -> list:
        """返回 OpenAI function calling 格式的工具定义列表。"""
        return [
            {"type": "function", "function": {
                "name": e.name,
                "description": e.description,
                "parameters": e.parameters,
            }}
            for e in self._tools.values()
        ]

    @property
    def query_tools(self) -> set:
        """返回所有查询类工具的名称集合。"""
        return {n for n, e in self._tools.items() if e.security == "query"}

    @property
    def write_tools(self) -> set:
        """返回所有写入类工具的名称集合。"""
        return {n for n, e in self._tools.items() if e.security == "write"}

    # ==================== 执行 ====================

    async def execute_query(self, name: str, params: dict, db) -> str:
        """执行查询类工具。"""
        e = self._tools.get(name)
        if e is None or e.handler is None:
            return f"未知查询操作: {name}"
        try:
            return await e.handler(params, db)
        except Exception as err:
            logger.exception("执行查询 tool %s 失败", name)
            return f"执行查询时出错: {err}"

    async def execute_write(self, name: str, params: dict, db) -> str:
        """执行确认后的写入操作。"""
        e = self._tools.get(name)
        if e is None or e.write_handler is None:
            return f"未知写入操作: {name}"
        try:
            return await e.write_handler(params, db)
        except Exception as err:
            logger.exception("执行写入 tool %s 失败", name)
            return f"执行操作时出错: {err}"

    def summarize_write(self, name: str, params: dict) -> str:
        """生成写入操作的摘要文本。"""
        e = self._tools.get(name)
        if e is None or e.summarize_handler is None:
            return f"{name}({params})"
        try:
            return e.summarize_handler(params)
        except Exception:
            return f"{name}({params})"

    def execute_tool(self, name: str, input_text: str) -> str:
        """简易执行接口：字符串入、字符串出（兼容 HelloAgents 风格）。"""
        e = self._tools.get(name)
        if e is None:
            return f"错误：未找到名为 '{name}' 的工具。"
        if e.handler is not None:
            import asyncio
            try:
                return asyncio.run(e.handler({"input": input_text}, None))
            except Exception as ex:
                return f"错误：执行工具 '{name}' 时发生异常: {ex}"
        return f"错误：工具 '{name}' 无可用的查询处理函数。"


# 全局工具注册表单例
global_registry = ToolRegistry()
