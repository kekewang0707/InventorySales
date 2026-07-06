"""AI 快捷操作路由

- POST /api/ai/command — 接收用户文本，返回 AI 回复
- POST /api/ai/confirm — 用户确认写入操作后执行
"""
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.services.ai_service import handle_command, execute_pending, get_all_sessions_info, get_session_messages, rename_session

router = APIRouter(prefix="/api/ai", tags=["ai"])


class CommandRequest(BaseModel):
    text: str
    session_id: str = ""  # v1.1.0: 可选，不传时服务端自动生成


class ConfirmRequest(BaseModel):
    confirm_id: str






class RenameRequest(BaseModel):
    title: str


@router.patch("/sessions/{session_id}/title")
async def rename_session_endpoint(session_id: str, req: RenameRequest, db: AsyncSession = Depends(get_db)):
    """修改会话标题。"""
    from backend.services.ai_service import rename_session as _rename
    ok = await _rename(session_id, req.title, db)
    return {"renamed": ok}


class SessionInfoResponse(BaseModel):
    session_id: str
    message_count: int
    first_message: str = ""
    title: str = ""
    last_active: str = ""
    created_at: str = ""


@router.get("/sessions", response_model=list[SessionInfoResponse])
async def list_sessions():
    """列出当前所有活跃会话的元信息（用于前端 tab 切换）。"""
    from backend.services.ai_service import get_all_sessions_info
    return get_all_sessions_info()



@router.get("/sessions/{session_id}/messages")
async def get_session_messages_endpoint(session_id: str, db: AsyncSession = Depends(get_db)):
    """获取指定会话的消息列表。"""
    msgs = await get_session_messages(session_id, db)
    return {"session_id": session_id, "messages": msgs}


@router.delete("/sessions/{session_id}")
async def delete_session_route(session_id: str, db: AsyncSession = Depends(get_db)):
    """删除指定会话及其消息（内存 + DB）。"""
    from backend.services.ai_service import delete_session as _delete_session
    ok = await _delete_session(session_id, db)
    return {"deleted": ok}


class CommandResponse(BaseModel):
    action: str  # "queried" | "needs_confirm" | "error" | "executed"
    reply: str
    confirm_id: Optional[str] = None
    tool_calls: Optional[list] = None
    session_id: str = ""  # v1.1.0: 新增，用于多轮对话


@router.post("/command", response_model=CommandResponse)
async def ai_command(
    req: CommandRequest,
    db: AsyncSession = Depends(get_db),
):
    """接收用户文本指令，由 AI 服务处理后返回回复（查询/确认/执行）。"""
    result = await handle_command(req.text, db, session_id=req.session_id)
    return CommandResponse(**result)


@router.post("/confirm", response_model=CommandResponse)
async def ai_confirm(
    req: ConfirmRequest,
    db: AsyncSession = Depends(get_db),
):
    """用户确认写入操作后执行对应的 AI 工具函数。"""
    result = await execute_pending(req.confirm_id, db)
    return CommandResponse(**result)
