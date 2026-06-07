from typing import Optional, Tuple, List

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.product import Product
from backend.schemas.product import ProductCreate, ProductUpdate, ProductResponse


async def list_products(
    db: AsyncSession,
    search: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> Tuple[int, List[ProductResponse]]:
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
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if product:
        return ProductResponse.model_validate(product)
    return None


async def create_product(db: AsyncSession, data: ProductCreate) -> ProductResponse:
    product = Product(**data.model_dump())
    db.add(product)
    await db.flush()
    await db.refresh(product)
    return ProductResponse.model_validate(product)


async def update_product(
    db: AsyncSession, product_id: int, data: ProductUpdate
) -> Optional[ProductResponse]:
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        return None

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(product, key, value)

    await db.flush()
    await db.refresh(product)
    return ProductResponse.model_validate(product)


async def delete_product(db: AsyncSession, product_id: int) -> bool:
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        return False
    await db.delete(product)
    await db.flush()
    return True
