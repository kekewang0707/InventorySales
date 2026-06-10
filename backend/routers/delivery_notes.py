from datetime import date
import subprocess
from typing import Dict, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Form
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.schemas.delivery_note import (
    DeliveryNoteCreate,
    DeliveryNoteUpdate,
    DeliveryNoteResponse,
    DeliveryNoteListResponse,
)
from backend.services import delivery_service

router = APIRouter(prefix="/api/delivery-notes", tags=["delivery-notes"])


@router.get("", response_model=DeliveryNoteListResponse)
async def list_notes(
    customer_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """查询送货单列表，支持按客户、日期范围筛选和分页。"""
    total, items = await delivery_service.list_notes(
        db, customer_id, start_date, end_date, page, page_size
    )
    return DeliveryNoteListResponse(total=total, items=items)


@router.post("", response_model=DeliveryNoteResponse, status_code=201)
async def create_note(
    data: DeliveryNoteCreate,
    db: AsyncSession = Depends(get_db),
):
    """创建送货单（含明细行）。"""
    return await delivery_service.create_note(db, data)


@router.get("/printers")
async def get_printers_cross_platform() -> Dict[str, Any]:
    """跨平台获取打印机列表，支持 Windows、macOS、Linux。"""
    import platform
    system = platform.system()

    try:
        if system == "Windows":
            # Windows：使用 PowerShell Get-Printer
            printers, default = _get_printers_windows()
        elif system in ("Darwin", "Linux"):
            # macOS / Linux：使用 lpstat (CUPS)
            printers, default = _get_printers_unix()
        else:
            return {"printers": [], "default": "", "error": f"不支持的系统: {system}"}

        return {"printers": printers, "default": default}
    except Exception as e:
        return {"printers": [], "default": "", "error": str(e)}


def _get_printers_windows():
    """Windows 获取打印机列表（PowerShell）"""
    printers = []
    default_printer = ""

    # PowerShell 命令：获取所有打印机名称，并标记默认打印机
    ps_command = """
    $printers = Get-Printer | Select-Object Name, Default
    $default = ($printers | Where-Object { $_.Default }).Name
    $printers | ForEach-Object {
        [PSCustomObject]@{
            Name = $_.Name
            IsDefault = $_.Default
        }
    } | ConvertTo-Json
    """
    try:
        result = subprocess.run(
            ["powershell", "-Command", ps_command],
            capture_output=True,
            text=True,
            timeout=10,
            encoding="utf-8"
        )
        if result.returncode == 0 and result.stdout.strip():
            import json
            data = json.loads(result.stdout)
            # 确保 data 是列表
            if not isinstance(data, list):
                data = [data]
            for item in data:
                printers.append({
                    "name": item["Name"],
                    "description": "",
                    "is_default": item.get("IsDefault", False)
                })
                if item.get("IsDefault"):
                    default_printer = item["Name"]
    except Exception:
        # 回退方案：使用 wmic
        printers, default_printer = _get_printers_windows_fallback()

    return printers, default_printer


def _get_printers_windows_fallback():
    """备用方案：使用 wmic 获取打印机"""
    printers = []
    default_printer = ""
    try:
        # 获取所有打印机及其默认状态
        result = subprocess.run(
            ["wmic", "printer", "get", "name,default", "/format:csv"],
            capture_output=True,
            text=True,
            timeout=10,
            encoding="utf-8"
        )
        if result.returncode == 0:
            lines = result.stdout.strip().splitlines()
            for line in lines[1:]:  # 跳过标题行
                if not line.strip():
                    continue
                parts = line.split(',')
                if len(parts) >= 2:
                    name = parts[1].strip()
                    if name:
                        is_default = (len(parts) > 2 and parts[2].strip().lower() == 'true')
                        printers.append({
                            "name": name,
                            "description": "",
                            "is_default": is_default
                        })
                        if is_default:
                            default_printer = name
    except Exception:
        pass
    return printers, default_printer


def _get_printers_unix():
    """macOS / Linux 获取打印机列表（lpstat）"""
    printers = []
    default_printer = ""

    # 1. 获取所有打印机
    result = subprocess.run(
        ["lpstat", "-p"],
        capture_output=True,
        text=True,
        timeout=5
    )
    if result.returncode != 0:
        # 无打印机或命令错误
        return [], ""

    for line in result.stdout.strip().split("\n"):
        if line.startswith("printer "):
            parts = line.split()
            if len(parts) >= 2:
                printer_name = parts[1]
                printers.append({
                    "name": printer_name,
                    "description": "",
                    "is_default": False
                })

    # 2. 获取默认打印机
    try:
        dr = subprocess.run(
            ["lpstat", "-d"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if dr.returncode == 0 and dr.stdout.strip():
            # 格式：system default destination: printer_name
            if ":" in dr.stdout:
                default_printer = dr.stdout.split(":", 1)[-1].strip()
            else:
                default_printer = dr.stdout.strip()
    except Exception:
        pass

    # 3. 标记默认打印机
    for p in printers:
        p["is_default"] = (p["name"] == default_printer)

    return printers, default_printer

@router.get("/{note_id}", response_model=DeliveryNoteResponse)
async def get_note(
    note_id: int,
    db: AsyncSession = Depends(get_db),
):
    """根据 ID 获取送货单详情（含明细行和产品信息）。"""
    note = await delivery_service.get_note(db, note_id)
    if not note:
        raise HTTPException(status_code=404, detail="送货单不存在")
    return note


@router.put("/{note_id}", response_model=DeliveryNoteResponse)
async def update_note(
    note_id: int,
    data: DeliveryNoteUpdate,
    db: AsyncSession = Depends(get_db),
):
    """更新送货单基本信息及明细行。已审核/已保存的送货单不可编辑。"""
    existing = await delivery_service.get_note(db, note_id)
    if not existing:
        raise HTTPException(status_code=404, detail="送货单不存在")
    if existing.status != "draft":
        raise HTTPException(status_code=400, detail="已审核或已保存的送货单不可编辑")
    note = await delivery_service.update_note(db, note_id, data)
    return note


@router.delete("/{note_id}", status_code=204)
async def delete_note(
    note_id: int,
    db: AsyncSession = Depends(get_db),
):
    """删除送货单（级联删除明细行）。"""
    deleted = await delivery_service.delete_note(db, note_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="送货单不存在")


@router.put("/{note_id}/status", response_model=DeliveryNoteResponse)
async def advance_status(
    note_id: int,
    db: AsyncSession = Depends(get_db),
):
    """推进送货单状态：draft → saved → reviewed。"""
    try:
        note = await delivery_service.advance_status(db, note_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not note:
        raise HTTPException(status_code=404, detail="送货单不存在")
    return note


@router.put("/{note_id}/status-revert", response_model=DeliveryNoteResponse)
async def revert_status(
    note_id: int,
    db: AsyncSession = Depends(get_db),
):
    """回退送货单状态：reviewed → saved → draft。"""
    try:
        note = await delivery_service.revert_status(db, note_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not note:
        raise HTTPException(status_code=404, detail="送货单不存在")
    return note


@router.post("/{note_id}/print")
async def print_note(
    note_id: int,
    printer_name: str = Form(""),
    db: AsyncSession = Depends(get_db),
):
    """打印送货单，生成 Excel 并通过系统打印命令发送到打印机。"""
    import subprocess, platform
    from datetime import datetime
    from backend.services.excel_service import export_delivery_note_xlsx
    from backend.config import get_data_dir

    note = await delivery_service.get_note(db, note_id)
    if not note:
        raise HTTPException(status_code=404, detail="送货单不存在")

    xlsx_bytes = export_delivery_note_xlsx(note)

    exports_dir = get_data_dir() / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    safe_doc = note.doc_number.replace("/", "_").replace(" ", "_")
    name = safe_doc.rsplit("-", 1)[0]
    ts = datetime.now().strftime("%H%M%S")
    xlsx_path = str(exports_dir / f"{name}_{ts}.xlsx")

    with open(xlsx_path, "wb") as f:
        f.write(xlsx_bytes)

    # 打印
    try:
        cmd = ["lp"]
        if printer_name:
            cmd.extend(["-d", printer_name])
        cmd.append(xlsx_path)
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"打印失败: {result.stderr.strip()}")
        return {"message": "已发送到打印机", "xlsx_path": xlsx_path, "printer": printer_name or "(默认)"}
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="打印超时")
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="系统未安装打印命令")


@router.get("/{note_id}/export")
async def export_note(
    note_id: int,
    db: AsyncSession = Depends(get_db),
):
    """导出送货单为 Excel 文件下载。"""
    from fastapi.responses import Response
    note = await delivery_service.get_note(db, note_id)
    if not note:
        raise HTTPException(status_code=404, detail="送货单不存在")

    from backend.services.excel_service import export_delivery_note_xlsx
    xlsx_bytes = export_delivery_note_xlsx(note)

    filename = f"{note.doc_number.replace('/', '_')}.xlsx"
    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---- 打印机 ----
