import os
import sqlite3

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

os.makedirs("data", exist_ok=True)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/clanstvo.db")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@event.listens_for(Engine, "connect")
def _vklopi_tuje_kljuce(dbapi_conn, _record) -> None:
    """SQLite privzeto NE uveljavlja tujih ključev – vklopimo jih za vsako povezavo."""
    if isinstance(dbapi_conn, sqlite3.Connection):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()


def sqlite_pot(url: str | None = None) -> str | None:
    """Vrne pot do SQLite datoteke iz DATABASE_URL ali None, če URL ni sqlite."""
    url = (url or DATABASE_URL).strip()
    if url.startswith("sqlite:///") and not url.endswith(":memory:"):
        return url[len("sqlite:///"):]
    return None


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
