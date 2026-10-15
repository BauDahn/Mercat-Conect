"""Refresco de core/marts y pruebas de calidad usando data/sql/apply.py (si las capas existen)."""
import importlib.util
import logging
from datetime import datetime
from pathlib import Path

import psycopg
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings

log = logging.getLogger("mercat.analytics")
APPLY = Path(__file__).resolve().parents[4] / "data" / "sql" / "apply.py"
_mod = None
_last: datetime | None = None


def _apply():
    global _mod
    if _mod is None and APPLY.exists():
        spec = importlib.util.spec_from_file_location("mc_data_sql_apply", APPLY)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        _mod = m
    return _mod


def available(db: Session) -> bool:
    ok = db.execute(text("SELECT to_regclass('core.meta') IS NOT NULL AND to_regclass('marts.quality_failures') "
                         "IS NOT NULL")).scalar()
    db.rollback()
    return bool(ok) and _apply() is not None


def _connect():
    return psycopg.connect(get_settings().DATABASE_URL.replace("postgresql+psycopg://", "postgresql://"))


def refresh(db: Session, now: datetime) -> bool:
    """Ingesta outbox -> raw, refresca vistas y fija core.meta.clock_now (hora del Clock)."""
    global _last
    if not available(db):
        return False
    with _connect() as conn:
        _apply().refresh(conn, now)
    _last = now
    return True


def maybe_refresh(db: Session, now: datetime, force: bool = False) -> bool:
    if not force and _last is not None and abs((now - _last).total_seconds()) < get_settings().ANALYTICS_REFRESH_SECONDS:
        return False
    try:
        return refresh(db, now)
    except Exception:  # noqa: BLE001
        log.exception("refresco analítico fallido")
        return False


def quality(db: Session, now: datetime) -> list[tuple[str, str]] | None:
    if not refresh(db, now):
        return None
    with _connect() as conn:
        return _apply().run_quality(conn)


def reset_state() -> None:
    global _last
    _last = None
