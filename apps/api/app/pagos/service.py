import json
import uuid
from datetime import datetime, timedelta

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Order, Payment, Payout
from app.errors import ApiError
from app.notificaciones import service as notif
from app.pagos.provider import FakePaymentProvider, get_provider
from app.pedidos import lifecycle
from app.reloj import day_start, get_clock


def intent(p: Payment) -> dict:
    return {"order_id": str(p.order_id), "payment_id": str(p.id), "provider": p.provider, "status": p.status,
            "checkout_url": f"/demo/pago?ref={p.provider_ref}" if p.status == "PENDING" else None}


def pay_order(db: Session, now: datetime, order: Order, simulate: str | None) -> dict:
    if order.status == "HELD" and order.hold_expires_at and order.hold_expires_at <= now:
        lifecycle.expire_hold(db, now, order)   # venció la reserva: se libera stock y puntos
        db.commit()
        raise ApiError("invalid_transition", **{"from": "EXPIRED_HOLD", "to": "PAID"})
    if order.status != "HELD":
        raise ApiError("invalid_transition", **{"from": order.status, "to": "PAID"})
    prov = get_provider()
    pay = db.scalar(select(Payment).where(Payment.order_id == order.id))
    if pay is not None and pay.status == "PAID":
        return intent(pay)
    if pay is not None and pay.status == "PENDING":
        return intent(pay)
    sess = prov.create_charge(order.id, order.total_cents)
    if pay is None:
        pay = Payment(order_id=order.id, provider=prov.name, provider_ref=sess.provider_ref,
                      amount_cents=order.total_cents, status="PENDING", created_at=now)
        db.add(pay)
    else:  # reintento tras fallo
        pay.provider_ref, pay.status = sess.provider_ref, "PENDING"
    db.commit()
    sim = simulate if get_settings().DEMO_MODE and isinstance(prov, FakePaymentProvider) else None
    if isinstance(prov, FakePaymentProvider) and sim:
        if sim == "delay":
            prov.schedule(now + timedelta(seconds=get_settings().FAKE_PAYMENT_DELAY_SECONDS), sess.provider_ref)
        else:
            raw, sig = prov.make_webhook(sess.provider_ref, "PAID" if sim == "success" else "FAILED",
                                         order.total_cents)
            process_webhook(db, now, "fake", raw, sig)
    elif isinstance(prov, FakePaymentProvider) and get_settings().DEMO_MODE:
        raw, sig = prov.make_webhook(sess.provider_ref, "PAID", order.total_cents)
        process_webhook(db, now, "fake", raw, sig)
    db.refresh(pay)
    return intent(pay)


def process_webhook(db: Session, now: datetime, provider: str, raw: bytes, signature: str) -> None:
    try:
        prov = get_provider(provider)
    except RuntimeError:
        raise ApiError("bad_request", reason="unknown_provider") from None
    if not prov.verify_webhook(raw, signature):
        raise ApiError("invalid_signature")
    try:
        body = json.loads(raw)
        ref, status = body["provider_ref"], body["status"]
        if status not in ("PAID", "FAILED"):
            raise ValueError
    except (ValueError, KeyError, TypeError):
        raise ApiError("bad_request") from None
    pay = db.scalar(select(Payment).where(Payment.provider_ref == ref).with_for_update())
    if pay is None:
        raise ApiError("bad_request", reason="unknown_payment")
    if body.get("amount_cents") is not None and body["amount_cents"] != pay.amount_cents:
        raise ApiError("bad_request", reason="amount_mismatch")
    order = db.scalar(select(Order).where(Order.id == pay.order_id).with_for_update())
    if status == "FAILED":
        if pay.status == "PENDING":
            pay.status = "FAILED"
        db.commit()
        return
    if pay.status in ("PAID", "REFUNDED"):  # duplicado: idempotente
        db.commit()
        return
    if order.status == "HELD" and order.hold_expires_at and order.hold_expires_at <= now:
        lifecycle.expire_hold(db, now, order)       # pago tras vencer la reserva (aunque el planificador no corriera aún)
    if order.status == "HELD":
        pay.status = "PAID"
        lifecycle.mark_paid(db, now, order)
    else:  # llegó tarde (reserva caducada o cancelada): reembolso automático
        prov.refund(ref, pay.amount_cents)
        pay.status = "REFUNDED"
        notif.notify(db, now, order.user_id, "ORDER_REFUNDED",
                     {"order_id": str(order.id), "message": "Pago recibido tras caducar la reserva: reembolsado"})
    db.commit()


def refund_payment(db: Session, now: datetime, order: Order) -> None:
    pay = db.scalar(select(Payment).where(Payment.order_id == order.id))
    if pay is not None and pay.status == "PAID":
        get_provider(pay.provider).refund(pay.provider_ref, pay.amount_cents)
        pay.status = "REFUNDED"


def deliver_due(db: Session, now: datetime) -> int:
    prov = get_provider()
    if not isinstance(prov, FakePaymentProvider):
        return 0
    n = 0
    for ref in prov.pop_due(now):
        raw, sig = prov.make_webhook(ref, "PAID")
        try:
            process_webhook(db, now, "fake", raw, sig)
            n += 1
        except ApiError:
            db.rollback()
    return n


def accrue_payout(db: Session, now: datetime, order: Order) -> None:
    """Liquidación al productor: un acumulado PENDING por puesto y día (comisión 0 %)."""
    start = day_start(now)
    row = db.scalar(select(Payout).where(Payout.stall_id == order.stall_id, Payout.status == "PENDING",
                                         Payout.period_from == start).with_for_update())
    if row is None:
        db.add(Payout(stall_id=order.stall_id, period_from=start, period_to=start + timedelta(days=1),
                      gross_cents=order.total_cents, commission_cents=0, amount_cents=order.total_cents,
                      status="PENDING"))
    else:
        row.gross_cents += order.total_cents
        row.amount_cents = row.gross_cents - row.commission_cents


_ = (text, uuid, get_clock)
