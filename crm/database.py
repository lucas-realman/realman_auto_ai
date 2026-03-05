"""数据库引擎与会话管理。

提供 AsyncEngine、async_session_maker 以及健康检查辅助函数。
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)

from crm.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DB_ECHO,
    future=True,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_recycle=settings.DB_POOL_RECYCLE,
    pool_pre_ping=True,
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db():
    """FastAPI 依赖：获取一个异步数据库 session。

    Yields:
        AsyncSession: SQLAlchemy 异步 session，请求结束后自动关闭。
    """
    async with async_session_maker() as session:
        yield session


# Alias used by API routers
get_session = get_db


async def check_db_connection() -> bool:
    """检测数据库是否可连通。

    Returns:
        bool: 连通返回 True，否则 False。
    """
    try:
        async with async_session_maker() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
