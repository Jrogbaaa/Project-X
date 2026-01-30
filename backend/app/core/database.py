import ssl
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from typing import AsyncGenerator, Optional


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


# Lazy-loaded engine and session maker for serverless compatibility
_engine = None
_async_session_maker = None


def get_engine():
    """Get or create the async engine (lazy initialization)."""
    global _engine
    if _engine is None:
        from app.config import get_settings, needs_ssl
        settings = get_settings()
        
        # Configure SSL for Neon and other cloud databases
        connect_args = {}
        if needs_ssl(settings.database_url_raw):
            # Create SSL context for asyncpg
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            connect_args["ssl"] = ssl_context
        
        _engine = create_async_engine(
            settings.database_url,
            echo=settings.debug,
            pool_pre_ping=True,
            connect_args=connect_args,
        )
    return _engine


def get_session_maker():
    """Get or create the session maker (lazy initialization)."""
    global _async_session_maker
    if _async_session_maker is None:
        _async_session_maker = async_sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _async_session_maker


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting database sessions."""
    session_maker = get_session_maker()
    async with session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Initialize database tables."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
