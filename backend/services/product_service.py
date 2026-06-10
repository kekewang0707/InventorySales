from typing import Optional, Tuple, List

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.product import Product
from backend.schemas.product import ProductCreate, ProductUpdate, ProductResponse
from backend.services import audit_service


async def list_products(
    db: AsyncSession,
    search: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> Tuple[int, List[ProductResponse]]:
    """分页查询产品列表，支持按名称/型号模糊搜索。"""
    query = select(Product)
    count_query = select(func.count(Product.id))

    if search:
        pattern = f"%{search}%"
        query = query.where(
            Product.name.ilike(pattern) | Product.model.ilike(pattern)
        )
        count_query = count_query.where(
            Product.name.ilike(pattern) | Product.model.ilike(pattern)
        )

    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    query = query.order_by(Product.id.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    products = result.scalars().all()

    return total, [ProductResponse.model_validate(p) for p in products]


async def get_product(db: AsyncSession, product_id: int) -> Optional[ProductResponse]:
    """根据 ID 获取产品详情。"""
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if product:
        return ProductResponse.model_validate(product)
    return None


async def create_product(db: AsyncSession, data: ProductCreate) -> ProductResponse:
    """创建新产品并记录审计日志。"""
    product = Product(**data.model_dump())
    db.add(product)
    await db.flush()
    await db.refresh(product)

    # 审计日志
    await audit_service.log_create(
        db, "product", product.id,
        data.model_dump(),
    )

    return ProductResponse.model_validate(product)


async def update_product(
    db: AsyncSession, product_id: int, data: ProductUpdate
) -> Optional[ProductResponse]:
    """更新产品信息，记录变更前后的审计日志。"""
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        return None

    old_values = {
        "name": product.name,
        "model": product.model,
        "default_price": float(product.default_price) if product.default_price else None,
        "remark": product.remark,
    }

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(product, key, value)

    await db.flush()
    await db.refresh(product)

    # 审计日志
    await audit_service.log_update(
        db, "product", product_id,
        old_values, update_data,
    )

    return ProductResponse.model_validate(product)


async def delete_product(db: AsyncSession, product_id: int) -> bool:
    """删除产品，检查是否被送货单引用，记录审计日志。"""
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        return False

    # 检查是否被送货单引用
    from backend.services.delivery_service import check_product_referenced
    if await check_product_referenced(db, product_id):
        raise ValueError("该产品已被送货单引用，无法删除")

    # 审计日志（先记录再删除）
    await audit_service.log_delete(
        db, "product", product_id,
        {
            "name": product.name,
            "model": product.model,
            "default_price": float(product.default_price) if product.default_price else None,
            "remark": product.remark,
        },
    )

    await db.delete(product)
    await db.flush()
    return True
