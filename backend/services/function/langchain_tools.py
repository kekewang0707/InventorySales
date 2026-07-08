"""LangChain 工具转换层 — 将 ToolRegistry 工具转为 StructuredTool 列表。

每个工具包装为异步 StructuredTool，通过 RunnableConfig 获取 db session，
与 FastAPI 的依赖注入模式解耦。
"""

from typing import Any, Dict, Optional

from pydantic import Field, create_model
from langchain_core.tools import StructuredTool
from langchain_core.runnables import RunnableConfig

from .registry import ToolRegistry

# JSON Schema type → Python/Pydantic type 映射
_TYPE_MAP: Dict[str, type] = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
    "array": list,
    "object": dict,
}


def _build_args_model(tool_name: str, parameters: dict) -> type:
    """从 JSON Schema parameters 动态创建 Pydantic 模型。"""
    properties = parameters.get("properties", {})
    required = set(parameters.get("required", []))

    fields: Dict[str, tuple] = {}
    for prop_name, prop_schema in properties.items():
        python_type = _TYPE_MAP.get(prop_schema.get("type", "string"), str)
        default = ... if prop_name in required else None
        description = prop_schema.get("description", "")
        fields[prop_name] = (
            Optional[python_type] if default is None else python_type,
            Field(default=default, description=description),
        )

    model_name = f"{tool_name}_args".replace(" ", "_").replace("-", "_")
    return create_model(model_name, **fields)


def build_langchain_tools(registry: ToolRegistry) -> list[StructuredTool]:
    """将 ToolRegistry 中的所有工具转换为 LangChain StructuredTool 列表。"""
    lc_tools: list[StructuredTool] = []

    for name, tool in registry._tools.items():
        args_model = _build_args_model(name, tool.parameters)

        # 写入工具的描述：去掉"需要确认"等让 LLM 犹豫的措辞
        desc = tool.description
        if tool.security == "write":
            desc = desc.replace("（需要用户二次确认后才执行）", "。直接调用即可，系统会自动弹出确认框。")

        def _make_func(tool_name: str):
            async def _run(config: RunnableConfig, **kwargs) -> str:
                db = config.get("configurable", {}).get("db")
                if db is None:
                    return f"错误：工具 '{tool_name}' 无法获取数据库连接"

                t = registry.get_tool(tool_name)
                if t is None:
                    return f"错误：未知工具 '{tool_name}'"

                if t.security == "write" and t.write_handler:
                    return await t.write_handler(kwargs, db)
                elif t.handler:
                    return await t.handler(kwargs, db)
                else:
                    return f"错误：工具 '{tool_name}' 未配置处理函数"
            return _run

        structured_tool = StructuredTool(
            name=name,
            description=desc,
            args_schema=args_model,
            coroutine=_make_func(name),
            metadata={"security": tool.security},
        )
        lc_tools.append(structured_tool)

    return lc_tools
