from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import String, Text, Numeric, Date, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class DeliveryNote(Base):
    __tablename__ = "delivery_notes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    doc_number: Mapped[str] = mapped_column(String(50), nullable=False, comment="送货单编号")
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, comment="客户"
    )
    delivery_date: Mapped[date] = mapped_column(Date, nullable=False, comment="送货日期")
    total_amount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2), nullable=True, comment="总金额"
    )
    remark: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="备注")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", comment="状态")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )

    customer: Mapped["Customer"] = relationship("Customer", lazy="joined")
    items: Mapped[List["DeliveryNoteItem"]] = relationship(
        "DeliveryNoteItem", back_populates="delivery_note",
        cascade="all, delete-orphan", lazy="selectin"
    )


class DeliveryNoteItem(Base):
    __tablename__ = "delivery_note_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    delivery_note_id: Mapped[int] = mapped_column(
        ForeignKey("delivery_notes.id", ondelete="CASCADE"), nullable=False, comment="所属送货单"
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, comment="产品"
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, comment="数量")
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, comment="单价")
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, comment="小计")
    remark: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="行备注")

    delivery_note: Mapped["DeliveryNote"] = relationship("DeliveryNote", back_populates="items")
    product: Mapped["Product"] = relationship("Product", lazy="joined")
