"""
Database engine configuration.

WHY ASYNC?
----------
ARIES handles multiple concurrent interviews. A synchronous database
driver would block the entire server while waiting for a query to complete.
Async SQLAlchemy with aiosqlite lets FastAPI serve other requests while
a database operation is in progress.

WHY SQLAlchemy (not raw SQL)?
-----------------------------
1. The repository pattern: Business logic doesn't know about SQL syntax
2. Migration path: Change `sqlite+aiosqlite:///` to `postgresql+asyncpg://` 
   and the code still works
3. Type safety: SQLAlchemy's ORM maps Python classes to tables
4. Connection pooling: Managed automatically

For Phase 1, we just set up the engine. Tables are defined in Phase 3.
"""

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings
from app.observability.logging import get_logger

logger = get_logger(__name__)

# Module-level variables — initialized by init_database()
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


async def init_database() -> None:
    """
    Initialize the async database engine and session factory.

    Called once during application startup (in FastAPI's lifespan).

    The engine manages the connection pool. The session_factory creates
    individual sessions for each request/operation.
    """
    global _engine, _session_factory

    settings = get_settings()

    logger.info(
        "Initializing database",
        extra={"database_url": settings.database_url.split("///")[0] + "///***"},
    )

    _engine = create_async_engine(
        settings.database_url,
        echo=settings.is_development,  # Log SQL in dev mode
        # SQLite doesn't support connection pooling the same way,
        # but these settings prepare us for PostgreSQL
        pool_pre_ping=True,
    )

    _session_factory = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,  # Don't expire objects after commit
    )

    # Create tables if they don't exist (safe for SQLite; for Postgres use Alembic migrations)
    from app.database.models import Base
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        def _ensure_schema(connection):
            from sqlalchemy import inspect, text
            inspector = inspect(connection)
            if "interview_sessions" in inspector.get_table_names():
                cols = [c["name"] for c in inspector.get_columns("interview_sessions")]
                if "proctoring_events" not in cols:
                    connection.execute(text("ALTER TABLE interview_sessions ADD COLUMN proctoring_events JSON DEFAULT '[]'"))

        await conn.run_sync(_ensure_schema)

    logger.info("Database engine initialized successfully")


async def close_database() -> None:
    """Close the database engine. Called during shutdown."""
    global _engine, _session_factory

    if _engine is not None:
        await _engine.dispose()
        logger.info("Database engine closed")

    _engine = None
    _session_factory = None


async def get_db_session() -> AsyncSession:
    """
    Get an async database session.

    Used as a FastAPI dependency:
        @router.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db_session)):
            ...

    The session is automatically closed when the request completes.
    """
    if _session_factory is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")

    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def get_engine() -> AsyncEngine:
    """Get the database engine (for creating tables, migrations, etc.)."""
    if _engine is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    return _engine
