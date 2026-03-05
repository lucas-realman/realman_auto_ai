from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from crm.config import settings


engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db():
    async with async_session_maker() as session:
        yield session


# Alias used by API routers
get_session = get_db
