import io
import re
from decimal import Decimal, InvalidOperation
from typing import List, Dict, Any, Tuple

from openpyxl import Workbook, load_workbook

TEMPLATES = {
    "product": {
        "headers": ["产品名称", "规格型号", "默认单价", "备注"],
        "required": ["产品名称"],
    },
    "customer": {
        "headers": ["客户名称", "联系人", "联系电话", "地址", "备注"],
        "required": ["客户名称", "联系电话"],
    },
}


def generate_template(entity_type: str) -> bytes:
    tpl = TEMPLATES.get(entity_type)
    if not tpl:
        raise ValueError(f"不支持的实体类型: {entity_type}")

    wb = Workbook()
    ws = wb.active
    ws.title = f"{entity_type}_导入模板"
    ws.append(tpl["headers"])

    if entity_type == "product":
        ws.append(["示例产品A", "X-100", "99.50", "备注示例"])
    elif entity_type == "customer":
        ws.append(["示例客户公司", "联系人姓名", "13800138000", "地址示例", "备注示例"])

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()


def _validate_product_row(row: Dict[str, str], row_num: int) -> List[str]:
    """校验单行产品数据，返回错误列表"""
    errors = []

    name = row.get("产品名称", "").strip()
    if not name:
        errors.append(f"第{row_num}行: 产品名称不能为空")
    elif len(name) > 200:
        errors.append(f"第{row_num}行: 产品名称不能超过200个字符")

    model = row.get("规格型号", "").strip()
    if len(model) > 200:
        errors.append(f"第{row_num}行: 规格型号不能超过200个字符")

    price_str = row.get("默认单价", "").strip()
    if price_str:
        try:
            price = Decimal(price_str)
            if price < 0:
                errors.append(f"第{row_num}行: 默认单价不能为负数")
        except InvalidOperation:
            errors.append(f"第{row_num}行: 默认单价格式无效，请输入数字（如 99.50）")

    return errors


def _validate_customer_row(row: Dict[str, str], row_num: int) -> List[str]:
    """校验单行客户数据，返回错误列表"""
    errors = []

    name = row.get("客户名称", "").strip()
    if not name:
        errors.append(f"第{row_num}行: 客户名称不能为空")
    elif len(name) > 200:
        errors.append(f"第{row_num}行: 客户名称不能超过200个字符")

    phone = row.get("联系电话", "").strip()
    if not phone:
        errors.append(f"第{row_num}行: 联系电话不能为空")
    elif not re.match(r'^[\d\-+\s()]{6,20}$', phone):
        errors.append(f"第{row_num}行: 联系电话格式不正确（请输入6-20位数字）")

    contact = row.get("联系人", "").strip()
    if len(contact) > 100:
        errors.append(f"第{row_num}行: 联系人不能超过100个字符")

    return errors


def parse_excel(
    file_bytes: bytes, entity_type: str
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """解析 Excel 文件，返回 (valid_rows, errors)"""
    tpl = TEMPLATES.get(entity_type)
    if not tpl:
        raise ValueError(f"不支持的实体类型: {entity_type}")

    wb = load_workbook(io.BytesIO(file_bytes), read_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    wb.close()

    if not rows:
        return [], [{"row": 0, "message": "文件为空"}]

    headers = [str(h).strip() if h else "" for h in rows[0]]

    # 校验表头
    expected = tpl["headers"]
    if headers != expected:
        return [], [{
            "row": 0,
            "message": f"表头不匹配。预期: {' → '.join(expected)}，实际: {' → '.join(headers)}"
        }]

    valid_rows = []
    errors = []

    for i, row in enumerate(rows[1:], start=2):
        if all(cell is None or str(cell).strip() == "" for cell in row):
            continue

        row_dict = {}
        for col_idx, header in enumerate(headers):
            cell_val = row[col_idx] if col_idx < len(row) else None
            row_dict[header] = str(cell_val).strip() if cell_val is not None else ""

        # 执行校验
        if entity_type == "product":
            row_errors = _validate_product_row(row_dict, i)
        else:
            row_errors = _validate_customer_row(row_dict, i)

        if row_errors:
            errors.extend([{"row": i, "message": msg} for msg in row_errors])
        else:
            valid_rows.append(row_dict)

    return valid_rows, errors


def row_to_product_data(row: Dict[str, str]) -> Dict[str, Any]:
    price = None
    if row.get("默认单价", "").strip():
        try:
            price = Decimal(str(row["默认单价"]).strip())
        except InvalidOperation:
            price = None
    return {
        "name": row.get("产品名称", "").strip(),
        "model": row.get("规格型号", "").strip(),
        "default_price": price,
        "remark": row.get("备注", "").strip(),
    }


def row_to_customer_data(row: Dict[str, str]) -> Dict[str, Any]:
    return {
        "name": row.get("客户名称", "").strip(),
        "contact_person": row.get("联系人", "").strip(),
        "phone": row.get("联系电话", "").strip(),
        "address": row.get("地址", "").strip(),
        "remark": row.get("备注", "").strip(),
    }
