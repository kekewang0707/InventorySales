from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="客户名称/公司全称")
    contact_person: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="联系人")
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment="联系电话")
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="地址")
    remark: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="备注")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )
