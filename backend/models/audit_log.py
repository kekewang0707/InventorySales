from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, Integer, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="操作对象类型: product/customer"
    )
    entity_id: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="操作对象 ID"
    )
    action: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="操作: create/update/delete/import"
    )
    old_values: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="变更前数据(JSON)"
    )
    new_values: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="变更后数据(JSON)"
    )
    operator: Mapped[str] = mapped_column(
        String(100), default="system", comment="操作人"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="操作时间"
    )
