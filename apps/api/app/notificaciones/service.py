import uuid
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.hooks import after_commit
from app.db.models import Notification, Offer, Order, Product, Stall, Subscription, User
from app.eventos.outbox import emit
from app.identidad.security import pseudo_id
from app.notificaciones.bus import hub
from app.notificaciones.notifiers import get_notifiers
from app.reloj import day_start, local

EMAIL_KINDS = {"ORDER_READY", "ORDER_CANCELLED", "ORDER_REFUNDED", "TEMP_ALARM", "ORDER_NEW"}


def notify(db: Session, now: datetime, user_id: uuid.UUID, kind: str, payload: dict,
           offer_id: uuid.UUID | None = None) -> None:
    user = db.get(User, user_id)
    if user is None:
        return
    for n in get_notifiers():
        if n.channel == "email" and kind not in EMAIL_KINDS:
            continue
        n.send(db, now, user, kind, payload)
        emit(db, now, "notification.sent", user_id, {
            "channel": n.channel, "audience": pseudo_id(user_id),
            "offer_id": str(offer_id) if offer_id else None, "latency_ms": 0})


def notify_managers(db: Session, now: datetime, kind: str, payload: dict) -> None:
    for uid in db.scalars(select(User.id).where(User.role.in_(("MANAGER", "ADMIN")), User.status == "ACTIVE")):
        notify(db, now, uid, kind, payload)


def publish_order(db: Session, order: Order) -> None:
    """SSE order.updated al comprador y al dueño del puesto (tras commit)."""
    owner = db.scalar(select(Stall.owner_user_id).where(Stall.id == order.stall_id))
    ids = [order.user_id] + ([owner] if owner else [])
    data = {"order_id": str(order.id), "status": order.status}
    after_commit(db, lambda: hub.publish("order.updated", data, ids))


def publish_offer(db: Session, offer_id: uuid.UUID) -> None:
    """SSE offer.updated a todos los suscritos (lee el estado final tras el commit)."""
    row = db.execute(select(Offer.status, Offer.qty_available, Offer.price_cents).where(Offer.id == offer_id)).first()
    if row:
        data = {"offer_id": str(offer_id), "status": row[0], "qty_available": row[1], "price_cents": row[2]}
        after_commit(db, lambda: hub.publish("offer.updated", data))


def _in_quiet(sub: Subscription, now: datetime) -> bool:
    if not sub.quiet_from or not sub.quiet_to:
        return False
    t = local(now).time()
    a, b = sub.quiet_from, sub.quiet_to
    return a <= t < b if a <= b else (t >= a or t < b)


def match_offer(db: Session, now: datetime, offer: Offer, stall: Stall, product: Product, market) -> int:
    """Avisa a suscriptores del mercado/categoría con puntos y reputación (sección 14.2)."""
    from app.config import get_settings
    from app.reglas import service as reglas

    cap = get_settings().DAILY_NOTIFICATION_CAP
    subs = db.scalars(select(Subscription).where(Subscription.market_id == market.id)).all()
    cands = []
    for sub in subs:
        if sub.categories and stall.category not in sub.categories:
            continue
        if _in_quiet(sub, now):
            continue
        u = db.get(User, sub.user_id)
        if not u or u.status != "ACTIVE":
            continue
        if reglas.points_state(db, u.id, now)["left"] <= 0:
            continue
        cands.append(u)
    cands.sort(key=lambda u: -float(u.reputation))
    n = 0
    for u in cands:
        dec = reglas.decide(db, u, True, offer, stall, product, market, 1, now)
        item = {"offer_id": str(offer.id), "product": product.name, "stall": stall.name,
                "price_cents": offer.price_cents, "qty_available": offer.qty_available,
                "until": offer.pickup_until.isoformat(), "points_cost": dec.points_cost,
                "link": f"/oferta/{offer.id}"}
        # Agrupación: varias ofertas en 5 min se unen en un único aviso (sección 14.2)
        grp = db.scalar(select(Notification).where(
            Notification.user_id == u.id, Notification.kind == "OFFER_MATCH",
            Notification.created_at > now - timedelta(minutes=5)).order_by(Notification.id.desc()).limit(1))
        if grp is not None:
            offers = list(grp.payload.get("offers") or [grp.payload])
            offers.append(item)
            grp.payload = {**item, "offers": offers, "count": len(offers)}
            db.flush()
            data = {"id": grp.id, "kind": grp.kind, "payload": grp.payload, "created_at": grp.created_at.isoformat()}
            after_commit(db, lambda d=data, uid=u.id: hub.publish("notification.created", d, [uid]))
            n += 1
            continue
        sent = db.scalar(select(func.count()).select_from(Notification).where(
            Notification.user_id == u.id, Notification.kind == "OFFER_MATCH",
            Notification.created_at >= day_start(now)))
        if sent >= cap:
            continue
        notify(db, now, u.id, "OFFER_MATCH", {**item, "offers": [item], "count": 1}, offer.id)
        n += 1
    return n
