from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from backend.config import DATABASE_URL

engine = create_async_engine(DATABASE_URL, echo=False)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    """获取数据库会话的依赖注入函数，每次请求自动提交，异常时回滚。"""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db():
    """初始化数据库，创建所有未创建的表。在应用启动时调用。"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # 迁移：添加 title 列（如果不存在）
        try:
            await conn.execute(__import__("sqlalchemy").text("ALTER TABLE ai_sessions ADD COLUMN title VARCHAR(255) DEFAULT ''"))
        except Exception:
            pass  # 列已存在


async def close_db():
    """关闭数据库连接池。在应用关闭时调用。"""
    await engine.dispose()
