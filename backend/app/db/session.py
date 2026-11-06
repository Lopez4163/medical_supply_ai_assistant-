from collections.abc import AsyncIterator
from functools import lru_cache

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.settings import Settings, get_settings


def create_database_engine(settings: Settings) -> AsyncEngine:
    return create_async_engine(
        settings.database_url,
        connect_args={"connect_timeout": 3},
        pool_pre_ping=True,
    )


@lru_cache
def get_database_engine() -> AsyncEngine:
    return create_database_engine(get_settings())


@lru_cache
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_database_engine(), expire_on_commit=False)


async def get_db_session(
    session_factory: async_sessionmaker[AsyncSession] = Depends(get_session_factory),
) -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session


async def is_database_ready(engine: AsyncEngine) -> bool:
    """Check connectivity and the baseline pgvector extension without writing state."""
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
            vector_enabled = await connection.scalar(
                text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')")
            )
    except OSError, SQLAlchemyError, TimeoutError:
        return False

    return bool(vector_enabled)


async def dispose_database_engine() -> None:
    if get_database_engine.cache_info().currsize:
        await get_database_engine().dispose()
    get_database_engine.cache_clear()
    get_session_factory.cache_clear()
