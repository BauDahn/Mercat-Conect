"""Outbox: los eventos se insertan en la misma transacción que el cambio."""
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import DomainEvent


def emit(db: Session, now: datetime, event_type: str, aggregate_id: uuid.UUID | None, payload: dict[str, Any]) -> None:
    db.add(DomainEvent(occurred_at=now, event_type=event_type, aggregate_id=aggregate_id, payload=payload))
