from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    AsyncSession,
    create_async_engine
)

from sqlalchemy.orm import DeclarativeBase

# 数据库地址
ASYNC_DATABASE_URL = "postgresql+asyncpg://postgres:xiaoyi@localhost:5432/xiaoyi_ai"

# 创建数据库引擎
async_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=True,
    pool_size=10,
    max_overflow=20
)

# 异步会话工厂
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# 所有模型共用的 Base
class Base(DeclarativeBase):
    pass

# 获取数据库 session
async def get_db():

    async with AsyncSessionLocal() as session:

        try:

            yield session

            await session.commit()

        except Exception:

            await session.rollback()

            raise

        finally:

            await session.close()