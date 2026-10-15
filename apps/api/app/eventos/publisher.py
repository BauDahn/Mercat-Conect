"""Publica domain_events no publicados en raw.events (si el esquema existe)."""
import json
import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

log = logging.getLogger("mercat.eventos")
WANTED = ("event_id", "event_type", "aggregate_id", "occurred_at", "payload")


def publish_pending(db: Session, now, batch: int = 500) -> int:
    reg = db.execute(text("SELECT to_regclass('raw.events')")).scalar()
    if reg is None:
        db.rollback()
        return 0
    cols = {r[0] for r in db.execute(text(
        "SELECT column_name FROM information_schema.columns WHERE table_schema='raw' AND table_name='events'"))}
    if "event_id" not in cols:
        db.rollback()
        return 0
    use = [c for c in WANTED if c in cols]
    rows = db.execute(text(
        "SELECT id, occurred_at, event_type, aggregate_id, payload FROM domain_events "
        "WHERE published_at IS NULL ORDER BY id LIMIT :n"), {"n": batch}).all()
    if not rows:
        db.rollback()
        return 0
    try:
        for r in rows:
            vals = {"event_id": r.id, "event_type": r.event_type, "aggregate_id": r.aggregate_id,
                    "occurred_at": r.occurred_at, "payload": json.dumps(r.payload)}
            sql = (f"INSERT INTO raw.events ({', '.join(use)}) SELECT "
                   + ", ".join(f"CAST(:{c} AS jsonb)" if c == "payload" and False else f":{c}" for c in use)
                   + " WHERE NOT EXISTS (SELECT 1 FROM raw.events WHERE event_id = :event_id)")
            db.execute(text(sql), {k: vals[k] for k in use})
        db.execute(text("UPDATE domain_events SET published_at=:t WHERE id = ANY(:ids)"),
                   {"t": now, "ids": [r.id for r in rows]})
        db.commit()
    except Exception:  # noqa: BLE001 - tolerante: esquema distinto al esperado
        log.warning("raw.events no admite el formato esperado; no se publica", exc_info=True)
        db.rollback()
        return 0
    return len(rows)
