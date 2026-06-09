from typing import Optional, Tuple, List

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.customer import Customer
from backend.schemas.customer import CustomerCreate, CustomerUpdate, CustomerResponse
from backend.services import audit_service


async def list_customers(
    db: AsyncSession,
    search: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> Tuple[int, List[CustomerResponse]]:
    query = select(Customer)
    count_query = select(func.count(Customer.id))

    if search:
        pattern = f"%{search}%"
        query = query.where(
            Customer.name.ilike(pattern) | Customer.phone.ilike(pattern)
        )
        count_query = count_query.where(
            Customer.name.ilike(pattern) | Customer.phone.ilike(pattern)
        )

    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    query = query.order_by(Customer.id.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    customers = result.scalars().all()

    return total, [CustomerResponse.model_validate(c) for c in customers]


async def get_customer(db: AsyncSession, customer_id: int) -> Optional[CustomerResponse]:
    result = await db.execute(select(Customer).where(Customer.id == customer_id))
    customer = result.scalar_one_or_none()
    if customer:
        return CustomerResponse.model_validate(customer)
    return None


async def create_customer(db: AsyncSession, data: CustomerCreate) -> CustomerResponse:
    customer = Customer(**data.model_dump())
    db.add(customer)
    await db.flush()
    await db.refresh(customer)

    await audit_service.log_create(
        db, "customer", customer.id,
        data.model_dump(),
    )

    return CustomerResponse.model_validate(customer)


async def update_customer(
    db: AsyncSession, customer_id: int, data: CustomerUpdate
) -> Optional[CustomerResponse]:
    result = await db.execute(select(Customer).where(Customer.id == customer_id))
    customer = result.scalar_one_or_none()
    if not customer:
        return None

    old_values = {
        "name": customer.name,
        "contact_person": customer.contact_person,
        "phone": customer.phone,
        "address": customer.address,
        "remark": customer.remark,
    }

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(customer, key, value)

    await db.flush()
    await db.refresh(customer)

    await audit_service.log_update(
        db, "customer", customer_id,
        old_values, update_data,
    )

    return CustomerResponse.model_validate(customer)


async def delete_customer(db: AsyncSession, customer_id: int) -> bool:
    result = await db.execute(select(Customer).where(Customer.id == customer_id))
    customer = result.scalar_one_or_none()
    if not customer:
        return False

    # 检查是否被送货单引用
    from backend.services.delivery_service import check_customer_referenced
    if await check_customer_referenced(db, customer_id):
        raise ValueError("该客户已被送货单引用，无法删除")

    await audit_service.log_delete(
        db, "customer", customer_id,
        {
            "name": customer.name,
            "contact_person": customer.contact_person,
            "phone": customer.phone,
            "address": customer.address,
            "remark": customer.remark,
        },
    )

    await db.delete(customer)
    await db.flush()
    return True
