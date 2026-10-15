"""Máquina de estados del pedido (sección 9.2) y sus efectos. Toda transición es un
UPDATE condicional atómico: un pedido no puede cambiar dos veces de estado a la vez."""
import uuid
from datetime import datetime, timedelta

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.hooks import after_commit
from app.db.models import Order, OrderItem, Payment, PointsLedger
from app.errors import ApiError
from app.eventos.outbox import emit
from app.identidad.security import pseudo_id
from app.notificaciones import service as notif
from app.taquillas import capacity
from app.taquillas.transport import get_transport

TRANSITIONS: dict[str, set[str]] = {
    "HELD": {"PAID", "EXPIRED_HOLD"},
    "PAID": {"PREPARING", "CANCELLED_BY_PRODUCER"},
    "PREPARING": {"IN_LOCKER", "CANCELLED_BY_PRODUCER"},
    "IN_LOCKER": {"PICKED_UP", "NO_SHOW", "TEMP_ALARM"},
    "CANCELLED_BY_PRODUCER": {"REFUNDED"},
    "TEMP_ALARM": {"REFUNDED"},
}


def move(db: Session, order: Order, to: str, now: datetime) -> None:
    """Transición atómica; ApiError(invalid_transition) si el estado actual no la permite."""
    frm = order.status
    if to not in TRANSITIONS.get(frm, set()):
        raise ApiError("invalid_transition", **{"from": frm, "to": to})
    res = db.execute(text("UPDATE orders SET status=:to WHERE id=:id AND status=:frm"),
                     {"to": to, "id": order.id, "frm": frm})
    if res.rowcount == 0:
        db.refresh(order)
        raise ApiError("invalid_transition", **{"from": order.status, "to": to})
    order.status = to
    if to in ("PICKED_UP", "NO_SHOW", "REFUNDED", "TEMP_ALARM"):
        # el código de retirada solo vive en la bandeja mientras el pedido está IN_LOCKER
        db.execute(text("UPDATE notifications SET payload = payload - 'pickup_code' "
                        "WHERE kind='ORDER_READY' AND payload->>'order_id' = :o"), {"o": str(order.id)})
    notif.publish_order(db, order)


def _cancel_event(db, now, order, cause):
    emit(db, now, "order.cancelled", order.id, {"order_id": str(order.id), "cause": cause})


def release_stock(db: Session, order_id: uuid.UUID) -> list[uuid.UUID]:
    ids = []
    for it in db.scalars(select(OrderItem).where(OrderItem.order_id == order_id).order_by(OrderItem.offer_id)):
        db.execute(text(
            "UPDATE offers SET qty_available = LEAST(qty_total, qty_available + :q), "
            "status = CASE WHEN status='SOLD_OUT' THEN 'ACTIVE' ELSE status END WHERE id=:o"),
            {"q": it.qty, "o": it.offer_id})
        notif.publish_offer(db, it.offer_id)
        ids.append(it.offer_id)
    return ids


def refund_points(db: Session, now: datetime, order: Order, reason: str) -> None:
    row = db.execute(select(PointsLedger).where(
        PointsLedger.order_id == order.id, PointsLedger.reason == "PURCHASE")).scalars().first()
    if row is None or order.points_cost <= 0:
        return
    db.execute(text("UPDATE points_week SET spent = GREATEST(spent - :c, 0) WHERE user_id=:u AND week_key=:w"),
               {"c": order.points_cost, "u": order.user_id, "w": row.week_key})
    db.add(PointsLedger(user_id=order.user_id, week_key=row.week_key, delta=order.points_cost,
                        reason=reason, order_id=order.id, created_at=now))
    emit(db, now, "points.refunded", order.id,
         {"user_pseudo_id": pseudo_id(order.user_id), "week_key": row.week_key, "delta": order.points_cost})


def _free_compartment(db: Session, now: datetime, order: Order) -> None:
    cid = capacity.release_compartment(db, order.id, now)
    if cid:
        after_commit(db, lambda: get_transport().remove_codes(cid))


def expire_hold(db: Session, now: datetime, order: Order) -> None:
    move(db, order, "EXPIRED_HOLD", now)
    release_stock(db, order.id)
    refund_points(db, now, order, "REFUND_CANCEL")
    _cancel_event(db, now, order, "hold_expired")
    notif.notify(db, now, order.user_id, "ORDER_CANCELLED",
                 {"order_id": str(order.id), "cause": "hold_expired"})


def mark_paid(db: Session, now: datetime, order: Order) -> None:
    move(db, order, "PAID", now)
    deadline = now + timedelta(minutes=get_settings().PREP_MINUTES)
    db.execute(text("UPDATE orders SET hold_expires_at=:d WHERE id=:id"), {"d": deadline, "id": order.id})
    order.hold_expires_at = deadline
    emit(db, now, "order.paid", order.id, {"order_id": str(order.id), "amount_cents": order.total_cents})
    from app.db.models import Stall
    owner = db.scalar(select(Stall.owner_user_id).where(Stall.id == order.stall_id))
    if owner:
        notif.notify(db, now, owner, "ORDER_NEW", {
            "order_id": str(order.id), "minutes": get_settings().PREP_MINUTES,
            "message": f"Prepara 1 pedido, tienes {get_settings().PREP_MINUTES} min", "link": "/productor/pedidos"})


def accept(db: Session, now: datetime, order: Order) -> None:
    move(db, order, "PREPARING", now)


def cancel_by_producer(db: Session, now: datetime, order: Order, cause: str = "producer_no_deposit") -> None:
    """PAID/PREPARING -> CANCELLED_BY_PRODUCER -> REFUNDED (reembolso, puntos y penalización)."""
    move(db, order, "CANCELLED_BY_PRODUCER", now)
    _cancel_event(db, now, order, cause)
    _refund(db, now, order, "REFUND_PRODUCER_FAULT")
    from app.db.models import Stall
    owner = db.scalar(select(Stall.owner_user_id).where(Stall.id == order.stall_id))
    if owner:
        rep = db.execute(text("UPDATE users SET reputation = GREATEST(reputation - :p, 0) WHERE id=:u "
                              "RETURNING reputation"), {"p": get_settings().PRODUCER_PENALTY, "u": owner}).scalar()
        emit(db, now, "producer.penalized", order.id, {
            "stall_id": str(order.stall_id), "order_id": str(order.id), "delta": -get_settings().PRODUCER_PENALTY,
            "cause": cause, "reputation": float(rep)})
        notif.notify(db, now, owner, "PRODUCER_PENALTY", {"order_id": str(order.id), "cause": cause})


def temp_alarm(db: Session, now: datetime, order: Order) -> None:
    move(db, order, "TEMP_ALARM", now)
    _cancel_event(db, now, order, "temp_alarm")
    _refund(db, now, order, "REFUND_PRODUCER_FAULT")


def _refund(db: Session, now: datetime, order: Order, ledger_reason: str) -> None:
    from app.pagos import service as pagos
    move(db, order, "REFUNDED", now)
    pagos.refund_payment(db, now, order)
    refund_points(db, now, order, ledger_reason)
    _free_compartment(db, now, order)
    notif.notify(db, now, order.user_id, "ORDER_REFUNDED",
                 {"order_id": str(order.id), "amount_cents": order.total_cents,
                  "message": "Pedido reembolsado y puntos devueltos"})


def no_show(db: Session, now: datetime, order: Order) -> None:
    from app.db.models import Donation
    from app.db.models import User
    move(db, order, "NO_SHOW", now)
    emit(db, now, "order.no_show", order.id, {"order_id": str(order.id), "cause": "pickup_window_expired"})
    _free_compartment(db, now, order)
    db.execute(text("UPDATE users SET reputation = GREATEST(reputation - 0.10, 0) WHERE id=:u"), {"u": order.user_id})
    from app.donaciones.service import first_active_charity
    charity = first_active_charity(db)
    if charity:
        for it in db.scalars(select(OrderItem).where(OrderItem.order_id == order.id)):
            db.add(Donation(offer_id=it.offer_id, charity_id=charity, qty=it.qty, status="OFFERED", created_at=now))
    notif.notify(db, now, order.user_id, "ORDER_NO_SHOW", {"order_id": str(order.id)})
    _ = User


def picked_up(db: Session, now: datetime, order: Order, seconds: int) -> None:
    from app.pagos.service import accrue_payout
    move(db, order, "PICKED_UP", now)
    emit(db, now, "order.picked_up", order.id, {"order_id": str(order.id), "seconds_to_pickup": seconds})
    accrue_payout(db, now, order)
    _free_compartment(db, now, order)


def sweep(db: Session, now: datetime) -> int:
    """Caducidades (reservas 10 min, preparación 20 min, ventana de retirada). Devuelve nº cambios."""
    n = 0
    for oid in db.scalars(select(Order.id).where(Order.status == "HELD", Order.hold_expires_at <= now)).all():
        o = db.get(Order, oid)
        try:
            expire_hold(db, now, o)
            db.commit()
            n += 1
        except ApiError:
            db.rollback()
    for oid in db.scalars(select(Order.id).where(
            Order.status.in_(("PAID", "PREPARING")), Order.hold_expires_at <= now)).all():
        o = db.get(Order, oid)
        try:
            cancel_by_producer(db, now, o)
            db.commit()
            n += 1
        except ApiError:
            db.rollback()
    for oid in db.scalars(select(Order.id).where(Order.status == "IN_LOCKER", Order.pickup_until <= now)).all():
        o = db.get(Order, oid)
        try:
            no_show(db, now, o)
            db.commit()
            n += 1
        except ApiError:
            db.rollback()
    return n


_ = Payment
