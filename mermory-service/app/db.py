import uuid

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(get_settings().database_url, echo=False)
async_session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncSession:
    async with async_session_maker() as session:
        yield session


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    await engine.dispose()


def generate_fact_id() -> str:
    return f"fact-{uuid.uuid4().hex[:12]}"


def generate_conflict_id() -> str:
    return f"conflict-{uuid.uuid4().hex[:12]}"


def generate_snapshot_id() -> str:
    return f"snapshot-{uuid.uuid4().hex[:12]}"
