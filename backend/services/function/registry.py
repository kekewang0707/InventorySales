"""ToolRegistry — 工具注册表，统一管理工具定义、执行、路由"""
import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger('backend.services.function')


@dataclass
class _ToolEntry:
    name: str
    description: str
    parameters: dict
    security: str  # "query" | "write"
    handler: Optional[Callable] = None        # 查询类 handler(params, db) → str
    write_handler: Optional[Callable] = None   # 写入类 handler(params, db) → str
    summarize_handler: Optional[Callable] = None  # 写入类摘要(params) → str


class ToolRegistry:
    """工具注册表 — 统一管理工具定义、执行、离线匹配"""

    def __init__(self):
        self._tools: Dict[str, _ToolEntry] = {}

    def register(self, name: str, description: str, parameters: dict, *,
                 security: str = "query",
                 handler: Optional[Callable] = None,
                 write_handler: Optional[Callable] = None,
                 summarize_handler: Optional[Callable] = None):
        self._tools[name] = _ToolEntry(
            name=name, description=description, parameters=parameters,
            security=security, handler=handler,
            write_handler=write_handler, summarize_handler=summarize_handler,
        )

    @property
    def openai_definitions(self) -> list:
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
        return {n for n, e in self._tools.items() if e.security == "query"}

    @property
    def write_tools(self) -> set:
        return {n for n, e in self._tools.items() if e.security == "write"}

    def has(self, name: str) -> bool:
        return name in self._tools

    def is_write(self, name: str) -> bool:
        e = self._tools.get(name)
        return e is not None and e.security == "write"

    def is_query(self, name: str) -> bool:
        e = self._tools.get(name)
        return e is not None and e.security == "query"

    async def execute_query(self, name: str, params: dict, db) -> str:
        """执行查询类工具"""
        e = self._tools.get(name)
        if e is None or e.handler is None:
            return f"未知查询操作: {name}"
        try:
            return await e.handler(params, db)
        except Exception as err:
            logger.exception("执行查询 tool %s 失败", name)
            return f"执行查询时出错: {err}"

    async def execute_write(self, name: str, params: dict, db) -> str:
        """执行确认后的写入操作"""
        e = self._tools.get(name)
        if e is None or e.write_handler is None:
            return f"未知写入操作: {name}"
        try:
            return await e.write_handler(params, db)
        except Exception as err:
            logger.exception("执行写入 tool %s 失败", name)
            return f"执行操作时出错: {err}"

    def summarize_write(self, name: str, params: dict) -> str:
        """生成写入操作的摘要文本"""
        e = self._tools.get(name)
        if e is None or e.summarize_handler is None:
            return f"{name}({params})"
        try:
            return e.summarize_handler(params)
        except Exception:
            return f"{name}({params})"
