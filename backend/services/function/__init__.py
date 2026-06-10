"""function — 工具函数注册表与处理函数"""
import logging

_logger = logging.getLogger('backend.services.function')
_handler = logging.StreamHandler()
_handler.setLevel(logging.INFO)
_handler.setFormatter(logging.Formatter("BACKEND: %(message)s"))
_logger.addHandler(_handler)
_logger.setLevel(logging.INFO)
_logger.propagate = False

from .registry import ToolRegistry, _ToolEntry
from .registration import (
    _tools,
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
    'ToolRegistry', '_tools', 'FUNCTION_DEFINITIONS',
    '_QUERY_TOOLS', '_WRITE_TOOLS',
    'handle_search_product', 'handle_search_customer',
    'handle_get_customer', 'handle_get_product',
    'handle_list_delivery_notes', 'handle_get_delivery_note',
    'handle_get_statement', 'handle_get_recent_logs',
    'handle_get_statistics',
    'handle_create_delivery_note', 'handle_advance_note_status',
    'summarize_create_delivery_note', 'summarize_advance_note_status',
]
