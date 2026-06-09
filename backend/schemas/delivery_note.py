from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List

from pydantic import BaseModel, ConfigDict, field_validator


# ---- Item ----

class DeliveryNoteItemBase(BaseModel):
    product_id: int
    quantity: Decimal
    unit_price: Decimal
    remark: Optional[str] = None

    @field_validator("quantity")
    @classmethod
    def quantity_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("数量必须大于0")
        return v

    @field_validator("unit_price")
    @classmethod
    def price_non_negative(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("单价不能为负数")
        return v


class DeliveryNoteItemCreate(DeliveryNoteItemBase):
    pass


class DeliveryNoteItemUpdate(DeliveryNoteItemBase):
    product_id: Optional[int] = None
    quantity: Optional[Decimal] = None
    unit_price: Optional[Decimal] = None


class DeliveryNoteItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    delivery_note_id: int
    product_id: int
    quantity: Decimal
    unit_price: Decimal
    subtotal: Decimal
    remark: Optional[str] = None

    # 嵌套产品信息
    product_name: Optional[str] = None
    product_model: Optional[str] = None


# ---- DeliveryNote ----

class DeliveryNoteBase(BaseModel):
    customer_id: int
    delivery_date: date
    remark: Optional[str] = None


class DeliveryNoteCreate(DeliveryNoteBase):
    items: List[DeliveryNoteItemCreate]


class DeliveryNoteUpdate(DeliveryNoteBase):
    customer_id: Optional[int] = None
    delivery_date: Optional[date] = None
    items: Optional[List[DeliveryNoteItemCreate]] = None


class DeliveryNoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    doc_number: str
    customer_id: int
    delivery_date: date
    total_amount: Optional[Decimal] = None
    remark: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime
    items: List[DeliveryNoteItemResponse] = []

    # 嵌套客户名称
    customer_name: Optional[str] = None


class DeliveryNoteListResponse(BaseModel):
    total: int
    items: List[DeliveryNoteResponse]


class StatusUpdateRequest(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def valid_status(cls, v: str) -> str:
        if v not in ("draft", "saved", "reviewed"):
            raise ValueError("状态值无效")
        return v
