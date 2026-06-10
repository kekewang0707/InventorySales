"""工具处理函数 — 每个工具一个 handler，按功能模块组织"""
from datetime import datetime, date
from decimal import Decimal

from backend.services import (
    product_service,
    customer_service,
    audit_service,
)
from backend.services.delivery_service import (
    list_notes as _list_notes,
    get_note as _get_note,
    create_note as _create_note,
    advance_status as _advance_status,
)


# ==================== 查询类 ====================

async def handle_search_product(params: dict, db) -> str:
    query = params.get("query", "")
    page = params.get("page", 1)
    total, items = await product_service.list_products(db, search=query, page=page)
    if not items:
        return f"未找到与「{query}」相关的产品"
    lines = [f"  - {p.name} | 型号: {p.model or '-'} | 单价: {p.default_price or '-'}元" for p in items]
    return f"找到 {total} 个产品：\n" + "\n".join(lines)


async def handle_search_customer(params: dict, db) -> str:
    query = params.get("query", "")
    page = params.get("page", 1)
    total, items = await customer_service.list_customers(db, search=query, page=page)
    if not items:
        return f"未找到与「{query}」相关的客户"
    lines = [f"  - {c.name} | 联系人: {c.contact_person or '-'} | 电话: {c.phone or '-'}" for c in items]
    return f"找到 {total} 个客户：\n" + "\n".join(lines)


async def handle_get_customer(params: dict, db) -> str:
    cid = int(params["customer_id"])
    c = await customer_service.get_customer(db, cid)
    if not c:
        return f"客户（ID={cid}）不存在"
    return (f"客户信息：{c.name}\n"
            f"联系人：{c.contact_person or '-'}\n"
            f"电话：{c.phone or '-'}\n"
            f"地址：{c.address or '-'}\n"
            f"备注：{c.remark or '-'}")


async def handle_get_product(params: dict, db) -> str:
    pid = int(params["product_id"])
    p = await product_service.get_product(db, pid)
    if not p:
        return f"产品（ID={pid}）不存在"
    return (f"产品信息：{p.name}\n"
            f"型号：{p.model or '-'}\n"
            f"默认单价：{p.default_price or '-'}元\n"
            f"备注：{p.remark or '-'}")


async def handle_list_delivery_notes(params: dict, db) -> str:
    cid = params.get("customer_id")
    sd = params.get("start_date")
    ed = params.get("end_date")
    page = params.get("page", 1)
    if sd:
        sd = date.fromisoformat(sd)
    if ed:
        ed = date.fromisoformat(ed)
    total, items = await _list_notes(db, customer_id=cid, start_date=sd, end_date=ed, page=page)
    if not items:
        return "未找到符合条件的送货单"
    lines = []
    for n in items:
        lines.append(f"  - #{n.id} {n.doc_number} | 客户: {n.customer_name} | 日期: {n.delivery_date} | 金额: {n.total_amount or 0}元 | 状态: {n.status}")
    return f"找到 {total} 张送货单：\n" + "\n".join(lines)


async def handle_get_delivery_note(params: dict, db) -> str:
    nid = int(params["note_id"])
    n = await _get_note(db, nid)
    if not n:
        return f"送货单（ID={nid}）不存在"
    item_lines = [f"    {item.product_name} × {item.quantity} @ {item.unit_price}元 = {item.subtotal}元" for item in n.items]
    items_str = "\n".join(item_lines) if item_lines else "    (无明细)"
    return (f"送货单 #{n.id}\n"
            f"编号：{n.doc_number}\n"
            f"客户：{n.customer_name}\n"
            f"日期：{n.delivery_date}\n"
            f"金额：{n.total_amount or 0}元\n"
            f"状态：{n.status}\n"
            f"备注：{n.remark or '-'}\n"
            f"明细：\n{items_str}")


async def handle_get_statement(params: dict, db) -> str:
    from backend.routers.statements import _query_notes, _build_statements
    from backend.schemas.statement import StatementQuery
    cid = params.get("customer_id")
    sd = date.fromisoformat(params["start_date"])
    ed = date.fromisoformat(params["end_date"])
    query = StatementQuery(customer_id=cid, start_date=sd, end_date=ed)
    notes = await _query_notes(db, query)
    statements = _build_statements(notes)
    if not statements:
        return "该时间段内无送货记录"
    parts = [f"{stmt.customer_name}：{len(stmt.delivery_notes)} 张送货单，合计 {stmt.total_amount}元" for stmt in statements]
    return "对账单汇总：\n" + "\n".join(parts)


async def handle_get_recent_logs(params: dict, db) -> str:
    entity_type = params.get("entity_type")
    action = params.get("action")
    limit = params.get("limit", 10)
    total, items = await audit_service.list_logs(db, entity_type=entity_type, action=action, page_size=limit)
    if not items:
        return "暂无操作日志"
    lines = [f"  - [{log.action}] {log.entity_type}(ID={log.entity_id}) at {log.created_at}" for log in items[:limit]]
    return f"最近 {len(lines)} 条操作日志：\n" + "\n".join(lines)


async def handle_get_statistics(params: dict, db) -> str:
    from sqlalchemy import select, func
    from backend.models.product import Product
    from backend.models.customer import Customer
    from backend.models.delivery_note import DeliveryNote
    pr = await db.execute(select(func.count(Product.id)))
    product_count = pr.scalar_one()
    cr = await db.execute(select(func.count(Customer.id)))
    customer_count = cr.scalar_one()
    dr = await db.execute(select(func.count(DeliveryNote.id)))
    note_count = dr.scalar_one()
    first_of_month = date(datetime.now().year, datetime.now().month, 1)
    sr = await db.execute(
        select(func.coalesce(func.sum(DeliveryNote.total_amount), 0))
        .where(DeliveryNote.delivery_date >= first_of_month)
    )
    month_total = sr.scalar_one()
    return (f"系统概览\n"
            f"产品总数：{product_count}\n"
            f"客户总数：{customer_count}\n"
            f"送货单总数：{note_count}\n"
            f"本月送货总额：{month_total}元")


# ==================== 写入类 ====================

def summarize_create_delivery_note(params: dict) -> str:
    cid = params.get("customer_id", "?")
    items = params.get("items", [])
    total = sum(
        Decimal(str(i.get("quantity", 0))) * Decimal(str(i.get("unit_price", 0)))
        for i in items
    )
    return (f"创建送货单：客户ID={cid}，日期={params.get('delivery_date', '?')}，"
            f"{len(items)} 项产品，合计 {total}元")


def summarize_advance_note_status(params: dict) -> str:
    return f"推进送货单状态：ID={params.get('note_id', '?')}"


async def handle_create_delivery_note(params: dict, db) -> str:
    from backend.schemas.delivery_note import DeliveryNoteCreate, DeliveryNoteItemCreate
    items_data = [
        DeliveryNoteItemCreate(
            product_id=int(i["product_id"]),
            quantity=Decimal(str(i["quantity"])),
            unit_price=Decimal(str(i["unit_price"])),
        )
        for i in params.get("items", [])
    ]
    data = DeliveryNoteCreate(
        customer_id=int(params["customer_id"]),
        delivery_date=date.fromisoformat(params["delivery_date"]),
        items=items_data,
        remark=params.get("remark"),
    )
    note = await _create_note(db, data)
    return f"创建成功：送货单编号 {note.doc_number}，金额 {note.total_amount or 0}元，共 {len(data.items)} 项产品"


async def handle_advance_note_status(params: dict, db) -> str:
    nid = int(params["note_id"])
    note = await _advance_status(db, nid)
    if not note:
        return f"送货单（ID={nid}）不存在"
    return f"操作成功：送货单 #{note.doc_number} 状态已推进至「{note.status}」"
