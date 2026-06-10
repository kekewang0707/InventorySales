from datetime import date, datetime
from decimal import Decimal
from typing import Optional, Tuple, List

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.delivery_note import DeliveryNote, DeliveryNoteItem
from backend.schemas.delivery_note import (
    DeliveryNoteCreate, DeliveryNoteUpdate,
    DeliveryNoteResponse, DeliveryNoteItemResponse,
)
from backend.services import audit_service


def _build_doc_number() -> str:
    """生成送货单编号（毫秒级时间戳）。"""
    return f"{int(datetime.now().timestamp() * 1000)}"


def _compute_total(items: List[DeliveryNoteItemResponse]) -> Decimal:
    """计算送货单明细行的合计金额。"""
    return sum((item.subtotal for item in items), Decimal("0"))


def _item_to_response(item: DeliveryNoteItem) -> DeliveryNoteItemResponse:
    """将 DeliveryNoteItem ORM 对象转换为响应模型，嵌入产品名称/型号。"""
    data = DeliveryNoteItemResponse.model_validate(item)
    if item.product:
        data.product_name = item.product.name
        data.product_model = item.product.model
    return data


def _note_to_response(note: DeliveryNote) -> DeliveryNoteResponse:
    """将 DeliveryNote ORM 对象转换为响应模型，嵌入客户名称和明细行。"""
    data = DeliveryNoteResponse.model_validate(note)
    if note.customer:
        data.customer_name = note.customer.name
    data.items = [_item_to_response(item) for item in note.items]
    return data


# ---- CRUD ----


async def list_notes(
    db: AsyncSession,
    customer_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    page: int = 1,
    page_size: int = 20,
) -> Tuple[int, List[DeliveryNoteResponse]]:
    """分页查询送货单列表，支持按客户、日期范围筛选。"""
    query = select(DeliveryNote)
    count_query = select(func.count(DeliveryNote.id))

    if customer_id:
        query = query.where(DeliveryNote.customer_id == customer_id)
        count_query = count_query.where(DeliveryNote.customer_id == customer_id)
    if start_date:
        query = query.where(DeliveryNote.delivery_date >= start_date)
        count_query = count_query.where(DeliveryNote.delivery_date >= start_date)
    if end_date:
        query = query.where(DeliveryNote.delivery_date <= end_date)
        count_query = count_query.where(DeliveryNote.delivery_date <= end_date)

    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    query = query.order_by(DeliveryNote.id.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    notes = result.scalars().all()

    return total, [_note_to_response(n) for n in notes]


async def get_note(db: AsyncSession, note_id: int) -> Optional[DeliveryNoteResponse]:
    """根据 ID 获取送货单详情（含明细行和产品信息）。"""
    result = await db.execute(select(DeliveryNote).where(DeliveryNote.id == note_id))
    note = result.scalar_one_or_none()
    if note:
        return _note_to_response(note)
    return None


async def create_note(db: AsyncSession, data: DeliveryNoteCreate) -> DeliveryNoteResponse:
    """创建送货单，自动生成编号、计算合计金额，记录审计日志。"""
    doc_number = _build_doc_number()

    total = sum(
        (item.quantity * item.unit_price for item in data.items),
        Decimal("0"),
    )

    note = DeliveryNote(
        doc_number=doc_number,
        customer_id=data.customer_id,
        delivery_date=data.delivery_date,
        total_amount=total,
        remark=data.remark,
        status="draft",
    )
    db.add(note)
    await db.flush()

    for item_data in data.items:
        item = DeliveryNoteItem(
            delivery_note_id=note.id,
            product_id=item_data.product_id,
            quantity=item_data.quantity,
            unit_price=item_data.unit_price,
            subtotal=item_data.quantity * item_data.unit_price,
            remark=item_data.remark,
        )
        db.add(item)

    await db.flush()
    await db.refresh(note)

    await audit_service.log_create(
        db, "delivery_note", note.id,
        {"doc_number": doc_number, "customer_id": data.customer_id, "item_count": len(data.items)},
    )

    return _note_to_response(note)


async def update_note(
    db: AsyncSession, note_id: int, data: DeliveryNoteUpdate
) -> Optional[DeliveryNoteResponse]:
    """更新送货单基本信息及明细行（替换全部旧明细），记录审计日志。"""
    result = await db.execute(select(DeliveryNote).where(DeliveryNote.id == note_id))
    note = result.scalar_one_or_none()
    if not note:
        return None

    old_values = {
        "customer_id": note.customer_id,
        "delivery_date": str(note.delivery_date),
        "remark": note.remark,
    }

    if data.customer_id is not None:
        note.customer_id = data.customer_id
    if data.delivery_date is not None:
        note.delivery_date = data.delivery_date
    if data.remark is not None:
        note.remark = data.remark

    # 替换明细行
    if data.items is not None:
        # 删除旧行
        await db.execute(
            select(DeliveryNoteItem).where(DeliveryNoteItem.delivery_note_id == note_id)
        )
        old_items = (await db.execute(
            select(DeliveryNoteItem).where(DeliveryNoteItem.delivery_note_id == note_id)
        )).scalars().all()
        for oi in old_items:
            await db.delete(oi)
        await db.flush()

        total = Decimal("0")
        for item_data in data.items:
            subtotal = item_data.quantity * item_data.unit_price
            total += subtotal
            item = DeliveryNoteItem(
                delivery_note_id=note.id,
                product_id=item_data.product_id,
                quantity=item_data.quantity,
                unit_price=item_data.unit_price,
                subtotal=subtotal,
                remark=item_data.remark,
            )
            db.add(item)
        note.total_amount = total

    await db.flush()
    await db.refresh(note)

    new_values = {
        "customer_id": note.customer_id,
        "delivery_date": str(note.delivery_date),
        "remark": note.remark,
    }
    await audit_service.log_update(db, "delivery_note", note_id, old_values, new_values)

    return _note_to_response(note)


async def delete_note(db: AsyncSession, note_id: int) -> bool:
    """删除送货单（级联删除明细行），记录审计日志。"""
    result = await db.execute(select(DeliveryNote).where(DeliveryNote.id == note_id))
    note = result.scalar_one_or_none()
    if not note:
        return False

    await audit_service.log_delete(
        db, "delivery_note", note_id,
        {"doc_number": note.doc_number, "customer_id": note.customer_id},
    )

    await db.delete(note)
    await db.flush()
    return True


# ---- 状态流转 ----

STATUS_FLOW = {"draft": "saved", "saved": "reviewed"}
STATUS_REVERT_FLOW = {"reviewed": "saved", "saved": "draft"}


async def advance_status(db: AsyncSession, note_id: int) -> Optional[DeliveryNoteResponse]:
    """推进送货单状态：draft → saved → reviewed。"""
    result = await db.execute(select(DeliveryNote).where(DeliveryNote.id == note_id))
    note = result.scalar_one_or_none()
    if not note:
        return None
    next_status = STATUS_FLOW.get(note.status)
    if not next_status:
        raise ValueError(f"当前状态 {note.status} 无法再推进")

    note.status = next_status
    await db.flush()
    await db.refresh(note)
    return _note_to_response(note)


async def revert_status(db: AsyncSession, note_id: int) -> Optional[DeliveryNoteResponse]:
    """回退送货单状态：reviewed → saved → draft。"""
    result = await db.execute(select(DeliveryNote).where(DeliveryNote.id == note_id))
    note = result.scalar_one_or_none()
    if not note:
        return None
    prev_status = STATUS_REVERT_FLOW.get(note.status)
    if not prev_status:
        raise ValueError(f"当前状态 {note.status} 无法再回退")

    note.status = prev_status
    await db.flush()
    await db.refresh(note)
    return _note_to_response(note)


# ---- 删除约束检查 ----


async def check_product_referenced(db: AsyncSession, product_id: int) -> bool:
    """检查产品是否被送货单明细行引用（删除约束校验用）。"""
    result = await db.execute(
        select(func.count(DeliveryNoteItem.id)).where(
            DeliveryNoteItem.product_id == product_id
        )
    )
    return result.scalar_one() > 0


async def check_customer_referenced(db: AsyncSession, customer_id: int) -> bool:
    """检查客户是否被送货单引用（删除约束校验用）。"""
    result = await db.execute(
        select(func.count(DeliveryNote.id)).where(
            DeliveryNote.customer_id == customer_id
        )
    )
    return result.scalar_one() > 0
