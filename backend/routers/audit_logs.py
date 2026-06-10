from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.schemas.audit_log import AuditLogListResponse
from backend.services import audit_service

router = APIRouter(prefix="/api/audit-logs", tags=["audit-logs"])


@router.get("", response_model=AuditLogListResponse)
async def list_audit_logs(
    entity_type: Optional[str] = None,
    action: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """查询审计日志列表，支持按实体类型和操作类型筛选。"""
    total, items = await audit_service.list_logs(db, entity_type, action, page, page_size)
    return AuditLogListResponse(total=total, items=items)
