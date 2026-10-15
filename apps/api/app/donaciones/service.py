"""Cierre de ofertas y donación del sobrante (secciones 9.1 y 11.1)."""
import uuid
from datetime import datetime

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db.models import Charity, Donation, Offer
from app.eventos.outbox import emit
from app.notificaciones import service as notif


def first_active_charity(db: Session) -> uuid.UUID | None:
    return db.scalar(select(Charity.id).where(Charity.active.is_(True)).order_by(Charity.name, Charity.id).limit(1))


def close_offers(db: Session, now: datetime) -> int:
    """ACTIVE vencidas -> EXPIRED -> DONATED / DISCARDED (si no quedan reservas pendientes)."""
    ids = db.scalars(select(Offer.id).where(
        Offer.status == "ACTIVE", Offer.pickup_until <= now,
        text("NOT EXISTS (SELECT 1 FROM order_items oi JOIN orders o ON o.id=oi.order_id "
              "WHERE oi.offer_id = offers.id AND o.status = 'HELD')"))).all()
    n = 0
    for oid in ids:
        res = db.execute(text("UPDATE offers SET status='EXPIRED' WHERE id=:o AND status='ACTIVE' "
                              "RETURNING qty_available"), {"o": oid}).first()
        if res is None:
            continue
        left = res[0]
        emit(db, now, "offer.expired", oid, {"offer_id": str(oid), "qty_remaining": left})
        charity = first_active_charity(db) if left > 0 else None
        if charity:
            db.add(Donation(offer_id=oid, charity_id=charity, qty=left, status="COMPLETED",
                            created_at=now, completed_at=now))
            db.execute(text("UPDATE offers SET status='DONATED' WHERE id=:o"), {"o": oid})
            emit(db, now, "donation.completed", oid,
                 {"offer_id": str(oid), "charity_id": str(charity), "qty": left})
        else:
            db.execute(text("UPDATE offers SET status='DISCARDED' WHERE id=:o"), {"o": oid})
        notif.publish_offer(db, oid)
        db.commit()
        n += 1
    return n
