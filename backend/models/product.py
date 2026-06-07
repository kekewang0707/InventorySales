from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import String, Text, Numeric, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="产品名称")
    model: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, comment="规格型号")
    default_price: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2), nullable=True, comment="默认单价"
    )
    remark: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="备注")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )
