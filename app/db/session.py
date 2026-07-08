from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

_engine = None
_SessionLocal = None


def _init() -> None:
    global _engine, _SessionLocal
    if _engine is not None or _SessionLocal is not None:
        return
    settings = get_settings()
    if not settings.database_url:
        return
    _engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
    _SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False, future=True)


def get_engine():
    _init()
    return _engine


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    _init()
    if _SessionLocal is None:
        raise RuntimeError("DATABASE_URL not configured")
    s = _SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def db_available() -> bool:
    """Return True if a live PostgreSQL+PostGIS connection is usable."""
    settings = get_settings()
    if not settings.database_url:
        return False
    _init()
    if _engine is None:
        return False
    try:
        with _engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            conn.execute(text("SELECT PostGIS_Version()"))
        return True
    except Exception:
        return False
