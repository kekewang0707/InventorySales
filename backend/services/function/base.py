"""Tool 工具基类 — 描述一个工具的名称、参数 schema 和执行路由。"""
from typing import Callable, Optional


class Tool:
    """工具基类。

    描述一个工具的名称、描述、参数 schema（OpenAI function calling 格式）、
    安全等级（query/write），以及执行时委托的处理函数。
    """

    def __init__(self, name: str, description: str, parameters: dict, *,
                 security: str = "query",
                 handler: Optional[Callable] = None,
                 write_handler: Optional[Callable] = None,
                 summarize_handler: Optional[Callable] = None):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.security = security
        self.handler = handler          # 查询类 handler(params, db) → str
        self.write_handler = write_handler   # 写入类 handler(params, db) → str
        self.summarize_handler = summarize_handler  # 写入类摘要(params) → str
