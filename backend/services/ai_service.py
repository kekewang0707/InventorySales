# """AI 服务 — 兼容层（重导出 ai_service_v2）。
#
# 自 v2.0.0 起，核心 AI 逻辑已迁移至 ai_service_v2.py（LangGraph ReAct Agent）。
# 本文件保留为轻量兼容层，所有公开 API 重导出至 v2 实现。
# """
#
# from backend.services.ai_service_v2 import (
#     # 核心入口
#     handle_command,
#     execute_pending,
#     # 会话管理
#     load_sessions_from_db,
#     cleanup_stale_sessions,
#     get_all_sessions_info,
#     get_session_messages,
#     rename_session,
#     delete_session,
#     # 离线降级（仍在使用）
#     _try_offline,
# )
#
# # 保留旧的 dataclass 定义 — 以防其他模块引用
# from dataclasses import dataclass, field
# from datetime import datetime, timedelta
# from typing import Dict, List
# import uuid
#
# @dataclass
# class SessionMessage:
#     role: str
#     content: str
#
#
# @dataclass
# class ConversationSession:
#     session_id: str
#     messages: List[SessionMessage]
#     created_at: datetime
#     last_active: datetime
#     title: str = ""
#
#
# @dataclass
# class PendingAction:
#     tool_name: str
#     params: dict
#     text_summary: str
#     prompt: str = ""
#     history: str = ""
#     llm_response: str = ""
#     session_id: str = ""
#     confirm_message: str = ""
#     created_at: datetime = field(default_factory=datetime.now)
