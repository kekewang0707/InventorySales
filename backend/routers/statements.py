from datetime import date
from typing import Optional, List
from urllib.parse import quote

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.database import get_db
from backend.models.delivery_note import DeliveryNote, DeliveryNoteItem
from backend.schemas.statement import StatementQuery, StatementResponse, StatementItem, StatementNoteItem, StatementItemDetail
from backend.services.excel_service import generate_statement_xlsx

router = APIRouter(prefix="/api/statements", tags=["statements"])


async def _query_notes(db: AsyncSession, query: StatementQuery) -> list:
    """Shared query logic for both statement and export endpoints."""
    base_query = (
        select(DeliveryNote)
        .options(
            selectinload(DeliveryNote.items).selectinload(DeliveryNoteItem.product),
            selectinload(DeliveryNote.customer),
        )
        .where(DeliveryNote.delivery_date >= query.start_date)
        .where(DeliveryNote.delivery_date <= query.end_date)
    )
    if query.customer_id:
        base_query = base_query.where(DeliveryNote.customer_id == query.customer_id)

    base_query = base_query.order_by(DeliveryNote.customer_id, DeliveryNote.delivery_date)
    result = await db.execute(base_query)
    return list(result.scalars().all())


def _build_statements(notes: list) -> List[StatementItem]:
    """Group notes by customer and build response."""
    from decimal import Decimal
    customer_groups: dict = {}
    for note in notes:
        cid = note.customer_id
        if cid not in customer_groups:
            customer_groups[cid] = {
                "customer_name": note.customer.name,
                "notes": [],
            }

        detail_parts = []
        item_details = []
        for item in note.items:
            if item.product:
                detail_parts.append(f"{item.product.name} * {item.quantity}")
                item_details.append(
                    StatementItemDetail(
                        product_name=item.product.name,
                        unit_price=item.unit_price,
                        quantity=item.quantity,
                        subtotal=item.subtotal,
                    )
                )
        customer_groups[cid]["notes"].append(
            StatementNoteItem(
                doc_number=note.doc_number,
                delivery_date=note.delivery_date,
                detail=", ".join(detail_parts),
                total_amount=note.total_amount or Decimal("0"),
                remark=note.remark,
                items=item_details,
            )
        )

    result = []
    for cid, data in customer_groups.items():
        total = sum(n.total_amount for n in data["notes"])
        result.append(
            StatementItem(
                customer_id=cid,
                customer_name=data["customer_name"],
                delivery_notes=data["notes"],
                total_amount=total,
            )
        )
    return result


@router.post("", response_model=StatementResponse)
async def query_statements(
    query: StatementQuery,
    db: AsyncSession = Depends(get_db),
):
    notes = await _query_notes(db, query)
    statements = _build_statements(notes)
    return StatementResponse(statements=statements)


@router.post("/export")
async def export_statements(
    query: StatementQuery,
    db: AsyncSession = Depends(get_db),
):
    notes = await _query_notes(db, query)
    xlsx_bytes = generate_statement_xlsx(notes, query.start_date, query.end_date)

    # Build filename
    if query.customer_id and notes:
        customer_name = notes[0].customer.name
    else:
        customer_name = "全部客户"
    filename = f"{customer_name}_{query.start_date.isoformat()}-{query.end_date.isoformat()}.xlsx"

    # RFC 5987 encoding for Chinese filenames
    encoded_filename = quote(filename)

    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
        },
    )
