import json
from typing import Optional, Dict, Any, Tuple, List

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.audit_log import AuditLog
from backend.schemas.audit_log import AuditLogResponse


async def _log(
    db: AsyncSession,
    entity_type: str,
    entity_id: int,
    action: str,
    old_values: Optional[Dict] = None,
    new_values: Optional[Dict] = None,
    operator: str = "system",
):
    """审计日志底层写入方法，记录操作类型、实体、变更前后数据。"""
    log = AuditLog(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        old_values=json.dumps(old_values, ensure_ascii=False, default=str) if old_values else None,
        new_values=json.dumps(new_values, ensure_ascii=False, default=str) if new_values else None,
        operator=operator,
    )
    db.add(log)


async def log_create(
    db: AsyncSession,
    entity_type: str,
    entity_id: int,
    new_values: Dict,
    operator: str = "system",
):
    """记录创建操作的审计日志。"""
    await _log(db, entity_type, entity_id, "create", new_values=new_values, operator=operator)


async def log_update(
    db: AsyncSession,
    entity_type: str,
    entity_id: int,
    old_values: Dict,
    new_values: Dict,
    operator: str = "system",
):
    """记录更新操作的审计日志，包含变更前后的数据快照。"""
    await _log(db, entity_type, entity_id, "update", old_values=old_values, new_values=new_values, operator=operator)


async def log_delete(
    db: AsyncSession,
    entity_type: str,
    entity_id: int,
    old_values: Dict,
    operator: str = "system",
):
    """记录删除操作的审计日志，保存被删除实体的数据快照。"""
    await _log(db, entity_type, entity_id, "delete", old_values=old_values, operator=operator)


async def log_import(
    db: AsyncSession,
    entity_type: str,
    count: int,
    operator: str = "system",
):
    """记录批量导入操作的审计日志。"""
    await _log(db, entity_type, 0, "import", new_values={"imported_count": count}, operator=operator)


async def list_logs(
    db: AsyncSession,
    entity_type: Optional[str] = None,
    action: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> Tuple[int, List[AuditLogResponse]]:
    """分页查询审计日志，支持按实体类型和操作类型筛选。"""
    query = select(AuditLog)
    count_query = select(func.count(AuditLog.id))

    if entity_type:
        query = query.where(AuditLog.entity_type == entity_type)
        count_query = count_query.where(AuditLog.entity_type == entity_type)
    if action:
        query = query.where(AuditLog.action == action)
        count_query = count_query.where(AuditLog.action == action)

    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    query = query.order_by(desc(AuditLog.created_at))
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    logs = result.scalars().all()

    items = []
    for log in logs:
        d = AuditLogResponse.model_validate(log)
        # Parse JSON strings back to dict
        if isinstance(d.old_values, str):
            try:
                d.old_values = json.loads(d.old_values)
            except (json.JSONDecodeError, TypeError):
                pass
        if isinstance(d.new_values, str):
            try:
                d.new_values = json.loads(d.new_values)
            except (json.JSONDecodeError, TypeError):
                pass
        items.append(d)

    return total, items
