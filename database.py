import os
import shutil
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import event

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LEGACY_DB_PATH = PROJECT_ROOT / "aura.db"
DEFAULT_DB_PATH = Path(os.getenv("LOCALAPPDATA", str(PROJECT_ROOT))) / "AuraProject" / "aura.db"
DB_PATH = Path(os.getenv("AURA_DB_PATH", str(DEFAULT_DB_PATH))).expanduser().resolve()
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite+aiosqlite:///{DB_PATH.as_posix()}")

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"timeout": 30}
)
AsyncSessionLocal = sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)

Base = declarative_base()


@event.listens_for(engine.sync_engine, "connect")
def configure_sqlite(connection, _record):
    cursor = connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def bootstrap_database_file():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists() or not LEGACY_DB_PATH.exists() or LEGACY_DB_PATH.resolve() == DB_PATH:
        return
    shutil.copy2(LEGACY_DB_PATH, DB_PATH)


async def init_database():
    bootstrap_database_file()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
