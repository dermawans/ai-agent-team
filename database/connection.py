"""
Database Connection & Session Management.
Uses WAL mode and write locking for safe concurrent access from multiple agents.
"""

import asyncio
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import event, text
from database.models import Base
from config import config

# SQLite connection args for concurrency
connect_args = {"timeout": 30}  # Wait up to 30s for locked DB

engine = create_async_engine(
    config.DATABASE.URL,
    echo=False,
    connect_args=connect_args,
    pool_size=1,          # Single connection pool for SQLite
    max_overflow=0,
    pool_pre_ping=True,
)

async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# Enable WAL mode for better concurrent read/write
@event.listens_for(engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=30000")  # 30 second timeout
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


async def init_db():
    """Create all tables if they don't exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# Global write lock for serializing DB writes
_db_write_lock = asyncio.Lock()


class DatabaseManager:
    """Manages database lifecycle with write serialization for SQLite."""

    def __init__(self):
        self.engine = engine
        self.session_factory = async_session_factory

    async def initialize(self):
        """Initialize the database (create tables)."""
        await init_db()

    @asynccontextmanager
    async def get_session(self):
        """Create a new session with write lock for SQLite safety."""
        async with _db_write_lock:
            session = self.session_factory()
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    async def close(self):
        """Close the database engine."""
        await self.engine.dispose()


db_manager = DatabaseManager()
