from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

_engine: Engine | None = None
_factory: sessionmaker | None = None


def get_engine() -> Engine:
    global _engine, _factory
    if _engine is None:
        _engine = create_engine(
            get_settings().DATABASE_URL, pool_size=20, max_overflow=40, pool_pre_ping=True,
            connect_args={"options": "-c idle_in_transaction_session_timeout=15000 -c lock_timeout=10000"},
        )
        _factory = sessionmaker(_engine, expire_on_commit=False)
    return _engine


def SessionLocal() -> Session:
    get_engine()
    assert _factory is not None
    return _factory()


def reset_engine() -> None:
    global _engine, _factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _factory = None


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
