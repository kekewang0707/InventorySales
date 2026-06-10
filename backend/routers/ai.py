"""AI 快捷操作路由

- POST /api/ai/command — 接收用户文本，返回 AI 回复
- POST /api/ai/confirm — 用户确认写入操作后执行
"""
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.services.ai_service import handle_command, execute_pending

router = APIRouter(prefix="/api/ai", tags=["ai"])


class CommandRequest(BaseModel):
    text: str


class ConfirmRequest(BaseModel):
    confirm_id: str


class CommandResponse(BaseModel):
    action: str  # "queried" | "needs_confirm" | "error" | "executed"
    reply: str
    confirm_id: Optional[str] = None
    tool_calls: Optional[list] = None


@router.post("/command", response_model=CommandResponse)
async def ai_command(
    req: CommandRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await handle_command(req.text, db)
    return CommandResponse(**result)


@router.post("/confirm", response_model=CommandResponse)
async def ai_confirm(
    req: ConfirmRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await execute_pending(req.confirm_id, db)
    return CommandResponse(**result)
