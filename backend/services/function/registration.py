"""工具注册 — 创建 _tools 单例并注册所有查询/写入工具。

注册完成后导出 FUNCTION_DEFINITIONS（OpenAI function calling 格式）、
_QUERY_TOOLS 和 _WRITE_TOOLS 供外部使用。
"""
from .registry import ToolRegistry
from . import handlers

_tools = ToolRegistry()

_tools.register("search_product", "按名称或规格型号搜索产品", {
    "type": "object", "properties": {
        "query": {"type": "string", "description": "搜索关键词（名称或型号）"},
        "page": {"type": "integer", "description": "页码，默认1"},
    }, "required": ["query"], "additionalProperties": False,
}, handler=handlers.handle_search_product)

_tools.register("search_customer", "按名称或电话搜索客户", {
    "type": "object", "properties": {
        "query": {"type": "string", "description": "搜索关键词（名称或电话）"},
        "page": {"type": "integer", "description": "页码，默认1"},
    }, "required": ["query"], "additionalProperties": False,
}, handler=handlers.handle_search_customer)

_tools.register("get_customer", "查看客户详情", {
    "type": "object", "properties": {
        "customer_id": {"type": "integer", "description": "客户ID"},
    }, "required": ["customer_id"], "additionalProperties": False,
}, handler=handlers.handle_get_customer)

_tools.register("get_product", "查看产品详情", {
    "type": "object", "properties": {
        "product_id": {"type": "integer", "description": "产品ID"},
    }, "required": ["product_id"], "additionalProperties": False,
}, handler=handlers.handle_get_product)

_tools.register("list_delivery_notes", "查询送货单列表，可按客户、日期范围筛选", {
    "type": "object", "properties": {
        "customer_id": {"type": "integer", "description": "客户ID（可选）"},
        "start_date": {"type": "string", "description": "开始日期 YYYY-MM-DD（可选）"},
        "end_date": {"type": "string", "description": "结束日期 YYYY-MM-DD（可选）"},
        "page": {"type": "integer", "description": "页码，默认1"},
    }, "additionalProperties": False,
}, handler=handlers.handle_list_delivery_notes)

_tools.register("get_delivery_note", "查看送货单详情，包含明细行和产品信息", {
    "type": "object", "properties": {
        "note_id": {"type": "integer", "description": "送货单ID"},
    }, "required": ["note_id"], "additionalProperties": False,
}, handler=handlers.handle_get_delivery_note)

_tools.register("get_statement", "查询客户对账单，支持指定客户或全部客户", {
    "type": "object", "properties": {
        "customer_id": {"type": "integer", "description": "客户ID，不传则查询全部客户"},
        "start_date": {"type": "string", "description": "开始日期 YYYY-MM-DD"},
        "end_date": {"type": "string", "description": "结束日期 YYYY-MM-DD"},
    }, "required": ["start_date", "end_date"], "additionalProperties": False,
}, handler=handlers.handle_get_statement)

_tools.register("get_recent_logs", "查看最近操作日志", {
    "type": "object", "properties": {
        "entity_type": {"type": "string", "description": "实体类型: product/customer/delivery_note（可选）"},
        "action": {"type": "string", "description": "操作类型: create/update/delete（可选）"},
        "limit": {"type": "integer", "description": "返回条数，默认10"},
    }, "additionalProperties": False,
}, handler=handlers.handle_get_recent_logs)

_tools.register("get_statistics", "查看系统统计概览：产品总数、客户总数、送货单总数、本月金额", {
    "type": "object", "properties": {},
    "additionalProperties": False,
}, handler=handlers.handle_get_statistics)

_tools.register("create_delivery_note", "创建送货单（需要用户二次确认后才执行）", {
    "type": "object", "properties": {
        "customer_id": {"type": "integer", "description": "客户ID"},
        "delivery_date": {"type": "string", "description": "送货日期 YYYY-MM-DD"},
        "items": {
            "type": "array", "description": "送货明细行",
            "items": {"type": "object", "properties": {
                "product_id": {"type": "integer", "description": "产品ID"},
                "quantity": {"type": "number", "description": "数量"},
                "unit_price": {"type": "number", "description": "单价"},
            }, "required": ["product_id", "quantity", "unit_price"], "additionalProperties": False},
        },
        "remark": {"type": "string", "description": "备注（可选）"},
    }, "required": ["customer_id", "delivery_date", "items"], "additionalProperties": False,
}, security="write", write_handler=handlers.handle_create_delivery_note,
   summarize_handler=handlers.summarize_create_delivery_note)

_tools.register("advance_note_status", "推进送货单状态：draft→saved→reviewed（需要用户二次确认后才执行）", {
    "type": "object", "properties": {
        "note_id": {"type": "integer", "description": "送货单ID"},
    }, "required": ["note_id"], "additionalProperties": False,
}, security="write", write_handler=handlers.handle_advance_note_status,
   summarize_handler=handlers.summarize_advance_note_status)

# ---- 导出供外部使用 ----

FUNCTION_DEFINITIONS = _tools.openai_definitions
_QUERY_TOOLS = _tools.query_tools
_WRITE_TOOLS = _tools.write_tools
