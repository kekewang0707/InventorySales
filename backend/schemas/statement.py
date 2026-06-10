from datetime import date
from decimal import Decimal
from typing import Optional, List

from pydantic import BaseModel


class StatementQuery(BaseModel):
    customer_id: Optional[int] = None  # None = 全部客户
    start_date: date
    end_date: date


class StatementItemDetail(BaseModel):
    product_name: str
    unit_price: Decimal
    quantity: Decimal
    subtotal: Decimal


class StatementNoteItem(BaseModel):
    doc_number: str
    delivery_date: date
    detail: str
    total_amount: Decimal
    remark: Optional[str] = None
    items: List[StatementItemDetail] = []


class StatementItem(BaseModel):
    customer_id: Optional[int] = None  # None = 全部客户
    customer_name: str
    delivery_notes: List[StatementNoteItem]
    total_amount: Decimal


class StatementResponse(BaseModel):
    statements: List[StatementItem]
