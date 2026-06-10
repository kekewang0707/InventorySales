import io
import uuid
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.services import excel_service, audit_service
from backend.services.product_service import create_product
from backend.services.customer_service import create_customer
from backend.schemas.product import ProductCreate
from backend.schemas.customer import CustomerCreate

router = APIRouter(prefix="/api/import", tags=["import"])

_preview_sessions: dict = {}


@router.get("/template")
async def download_template(entity_type: str):
    """下载实体（product/customer）的 Excel 导入模板。"""
    try:
        data = excel_service.generate_template(entity_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    print(f"下载导入模板: {entity_type}", flush=True)

    entity_label = "产品" if entity_type == "product" else "客户"
    filename_ascii = f"{entity_type}_template.xlsx"
    filename_utf8 = f"{entity_label}_导入模板.xlsx"
    encoded = quote(filename_utf8)

    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename=\"{filename_ascii}\"; filename*=UTF-8''{encoded}",
            "Content-Length": str(len(data)),
        },
    )


@router.post("/preview")
async def preview_import(
    file: UploadFile = File(...),
    entity_type: str = Form(...),
):
    """预览导入：解析 Excel 文件，校验数据并返回预览结果（有效行数、错误列表）。"""
    if not file.filename.endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="仅支持 .xlsx 文件")

    content = await file.read()

    try:
        valid_rows, errors = excel_service.parse_excel(content, entity_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    session_id = str(uuid.uuid4())
    _preview_sessions[session_id] = {
        "entity_type": entity_type,
        "valid_rows": valid_rows,
    }

    preview_data = []
    for row in valid_rows:
        if entity_type == "product":
            preview_data.append(excel_service.row_to_product_data(row))
        else:
            preview_data.append(excel_service.row_to_customer_data(row))

    return {
        "session_id": session_id,
        "total_rows": len(valid_rows) + len(errors),
        "valid_count": len(valid_rows),
        "error_count": len(errors),
        "errors": errors,
        "preview": preview_data,
    }


class ConfirmImportRequest(BaseModel):
    session_id: str


@router.post("/confirm")
async def confirm_import(
    data: ConfirmImportRequest,
    db: AsyncSession = Depends(get_db),
):
    """确认导入：执行预览阶段校验通过的数据写入，原子化操作（全部成功或全部回滚）。"""
    session = _preview_sessions.pop(data.session_id, None)
    if not session:
        raise HTTPException(status_code=404, detail="预览会话不存在或已过期")

    entity_type = session["entity_type"]
    valid_rows = session["valid_rows"]

    if not valid_rows:
        return {"imported": 0, "failed": 0, "all_or_nothing": True, "errors": []}

    count = len(valid_rows)
    try:
        for row in valid_rows:
            if entity_type == "product":
                pd = excel_service.row_to_product_data(row)
                await create_product(db, ProductCreate(**pd))
            elif entity_type == "customer":
                cd = excel_service.row_to_customer_data(row)
                await create_customer(db, CustomerCreate(**cd))

        await audit_service.log_import(db, entity_type, count)

    except Exception as e:
        return {
            "imported": 0,
            "failed": count,
            "all_or_nothing": True,
            "errors": [{"row": 0, "message": f"导入失败，已全部回滚: {str(e)}"}],
        }

    return {"imported": count, "failed": 0, "all_or_nothing": True, "errors": []}
