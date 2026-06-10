import os
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import List

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from backend.config import get_fonts_dir, get_data_dir
from backend.schemas.delivery_note import DeliveryNoteResponse


def _register_fonts():
    """注册中文字体"""
    fonts_dir = get_fonts_dir()
    # 思源黑体 — 尝试几个常见文件名
    candidates = [
        "NotoSansSC-Regular.ttf",
        "SourceHanSansSC-Regular.ttf",
        "NotoSansCJKsc-Regular.ttf",
        "SimHei.ttf",
    ]
    regular = None
    for name in candidates:
        path = fonts_dir / name
        if path.exists():
            regular = str(path)
            break

    bold_candidates = [
        "NotoSansSC-Bold.ttf",
        "SourceHanSansSC-Bold.ttf",
        "NotoSansCJKsc-Bold.ttf",
    ]
    bold = None
    for name in bold_candidates:
        path = fonts_dir / name
        if path.exists():
            bold = str(path)
            break

    if regular:
        pdfmetrics.registerFont(TTFont("CNFont", regular))
        if bold:
            pdfmetrics.registerFont(TTFont("CNFontBold", bold))
        else:
            pdfmetrics.registerFont(TTFont("CNFontBold", regular))
    else:
        # 回退：尝试系统字体
        import platform
        if platform.system() == "Darwin":
            system_font = "/System/Library/Fonts/STHeiti Light.ttc"
            if os.path.exists(system_font):
                pdfmetrics.registerFont(TTFont("CNFont", system_font))
                pdfmetrics.registerFont(TTFont("CNFontBold", system_font))


def _cn_style(font_size=10, bold=False, align=TA_LEFT, name=None):
    """创建中文字体样式"""
    font = "CNFontBold" if bold else "CNFont"
    return ParagraphStyle(
        name or f"CN_{font_size}_{'b' if bold else 'r'}",
        fontName=font,
        fontSize=font_size,
        leading=font_size + 4,
        alignment=align,
    )


def _amount_cn(n: Decimal) -> str:
    """金额小写转大写（支持角/分）"""
    digits = ["零", "壹", "贰", "叁", "肆", "伍", "陆", "柒", "捌", "玖"]
    units = ["", "拾", "佰", "仟", "万", "拾", "佰", "仟", "亿"]
    if n == 0:
        return "零元整"
    # 整数部分
    int_part = int(n)
    s = str(int_part)
    l = len(s)
    result = ""
    for i, ch in enumerate(s):
        d = int(ch)
        u = l - i - 1
        if d == 0:
            if u % 4 != 0 and i < l - 1 and s[i + 1] != "0":
                result += "零"
        else:
            result += digits[d] + units[u]
    if not result:
        result = "零"
    result += "元"
    # 小数部分（角/分）
    frac = int(round((n - int_part) * 100))
    if frac == 0:
        result += "整"
    else:
        jiao = frac // 10
        fen = frac % 10
        if jiao > 0:
            result += digits[jiao] + "角"
        if fen > 0:
            result += digits[fen] + "分"
    return result


def generate_delivery_note_pdf(note: DeliveryNoteResponse, company_name: str = "XX公司") -> str:
    """生成送货单 PDF，返回临时文件路径"""
    _register_fonts()

    exports_dir = get_data_dir() / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    safe_doc = note.doc_number.replace("/", "_").replace(" ", "_")
    path = str(exports_dir / f"{safe_doc}.pdf")

    doc = SimpleDocTemplate(
        path, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=15 * mm, bottomMargin=15 * mm,
    )

    elements = []
    title_style = _cn_style(18, bold=True, align=TA_CENTER)
    normal_style = _cn_style(10)

    # 抬头
    elements.append(Paragraph(f"{company_name} 送货单", title_style))
    elements.append(Spacer(1, 6 * mm))

    # 基本信息行
    info_data = [
        [
            Paragraph(f"单据编号：{note.doc_number}", normal_style),
            Paragraph(f"送货日期：{note.delivery_date}", normal_style),
        ],
        [
            Paragraph(f"客户：{note.customer_name or ''}", normal_style),
            Paragraph(f"状态：{note.status}", normal_style),
        ],
    ]
    info_table = Table(info_data, colWidths=[90 * mm, 80 * mm])
    info_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 6 * mm))

    # 明细表格
    header = ["序号", "产品名称", "规格", "数量", "单价", "小计", "备注"]
    col_widths = [10*mm, 28*mm, 28*mm, 20*mm, 22*mm, 28*mm, 28*mm]
    header_cells = [Paragraph(h, _cn_style(9, bold=True, align=TA_CENTER)) for h in header]
    table_data = [header_cells]

    for idx, item in enumerate(note.items, 1):
        row = [
            Paragraph(str(idx), _cn_style(9, align=TA_CENTER)),
            Paragraph(item.product_name or "", _cn_style(9)),
            Paragraph(item.product_model or "", _cn_style(9)),
            Paragraph(str(item.quantity), _cn_style(9, align=TA_RIGHT)),
            Paragraph(f"{item.unit_price:.2f}", _cn_style(9, align=TA_RIGHT)),
            Paragraph(f"{item.subtotal:.2f}", _cn_style(9, align=TA_RIGHT)),
            Paragraph(item.remark or "", _cn_style(9)),
        ]
        table_data.append(row)

    note_table = Table(table_data, colWidths=col_widths, repeatRows=1)

    table_style = [
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e0e0e0")),
    ]
    note_table.setStyle(TableStyle(table_style))
    elements.append(note_table)
    elements.append(Spacer(1, 10 * mm))

    # 合计
    total = note.total_amount or Decimal("0")
    total_text = f"合计金额（小写）：¥ {total:,.2f}　　大写：{_amount_cn(total)}"
    elements.append(Paragraph(total_text, _cn_style(11, bold=True, align=TA_RIGHT)))
    elements.append(Spacer(1, 8 * mm))

    # 底部签字区
    sign_data = [
        [
            Paragraph("制单人：_______________", _cn_style(10)),
            Paragraph("客户签收：_______________", _cn_style(10)),
        ]
    ]
    sign_table = Table(sign_data, colWidths=[85 * mm, 85 * mm])
    sign_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
    ]))
    elements.append(sign_table)

    doc.build(elements)
    return path
