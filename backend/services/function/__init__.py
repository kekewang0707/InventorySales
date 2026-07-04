"""function — AI 工具函数注册表与处理函数。

提供 ToolRegistry 注册表、预注册的查询/写入工具、以及所有处理函数的导入接口。
兼容 HelloAgents 工具系统 API 风格。
"""
import logging

_logger = logging.getLogger('backend.services.function')
_handler = logging.StreamHandler()
_handler.setLevel(logging.INFO)
_handler.setFormatter(logging.Formatter("BACKEND: %(message)s"))
_logger.addHandler(_handler)
_logger.setLevel(logging.INFO)
_logger.propagate = False

from .base import Tool
from .registry import ToolRegistry, global_registry
from .registration import (
    tools,
    FUNCTION_DEFINITIONS,
    _QUERY_TOOLS,
    _WRITE_TOOLS,
)

from .handlers import (
    handle_search_product,
    handle_search_customer,
    handle_get_customer,
    handle_get_product,
    handle_list_delivery_notes,
    handle_get_delivery_note,
    handle_get_statement,
    handle_get_recent_logs,
    handle_get_statistics,
    handle_create_delivery_note,
    handle_advance_note_status,
    summarize_create_delivery_note,
    summarize_advance_note_status,
)

__all__ = [
    'Tool', 'ToolRegistry', 'global_registry',
    'tools', 'FUNCTION_DEFINITIONS',
    '_QUERY_TOOLS', '_WRITE_TOOLS',
    'handle_search_product', 'handle_search_customer',
    'handle_get_customer', 'handle_get_product',
    'handle_list_delivery_notes', 'handle_get_delivery_note',
    'handle_get_statement', 'handle_get_recent_logs',
    'handle_get_statistics',
    'handle_create_delivery_note', 'handle_advance_note_status',
    'summarize_create_delivery_note', 'summarize_advance_note_status',
]
