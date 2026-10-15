"""Compra atómica (sección 10.6). Reglas y precio se recalculan SIEMPRE en el servidor."""
import uuid
from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Market, Offer, Order, OrderItem, PointsLedger, Product, Stall, User
from app.errors import ApiError
from app.eventos.outbox import emit
from app.identidad.security import pseudo_id
from app.identidad.service import is_age_verified
from app.notificaciones import service as notif
from app.reglas import service as reglas
from app.reloj import week_key
from app.sqlutil import select_orm, select_orm_stmt
from app.taquillas.capacity import locker_free_slots

DENIAL_EVENT = {"no_points": "sin_puntos", "exceeds_max": "supera_maximo", "insufficient_reputation": "reputacion_insuficiente",
                "account_not_verified": "cuenta_no_verificada", "age_not_verified": "cuenta_no_verificada",
                "out_of_stock": "sin_stock", "no_locker_capacity": "sin_capacidad_taquilla"}


def _record_denial(db: Session, now: datetime, user: User, offer_id: uuid.UUID, code: str) -> None:
    reason = DENIAL_EVENT.get(code)
    if reason is None:
        return
    emit(db, now, "order.denied", None,
         {"user_pseudo_id": pseudo_id(user.id), "offer_id": str(offer_id), "reason": reason})
    db.commit()


def _same_items(db: Session, order: Order, items: dict[uuid.UUID, int]) -> bool:
    have = {r.offer_id: r.qty for r in select_orm(db, OrderItem, OrderItem.order_id == order.id)}
    return have == items


def create_order(db: Session, now: datetime, user: User, raw_items: list[tuple[uuid.UUID, int]],
                 idem_key: str) -> tuple[Order, bool]:
    """Devuelve (pedido, creado). creado=False si es un reintento idempotente."""
    items: dict[uuid.UUID, int] = {}
    for oid, q in raw_items:
        if oid in items:
            raise ApiError("validation_failed", reason="duplicate_offer")
        items[oid] = q

    existing = db.scalar(select_orm_stmt(Order, Order.idempotency_key == idem_key))
    if existing is not None:
        if existing.user_id != user.id or not _same_items(db, existing, items):
            raise ApiError("idempotency_key_reused")
        return existing, False

    verified = is_age_verified(db, user.id)
    first_offer = next(iter(items))
    if user.status != "ACTIVE" or not verified:
        _record_denial(db, now, user, first_offer, "account_not_verified")
        raise ApiError("account_not_verified")

    offers = list(db.scalars(select_orm_stmt(Offer, Offer.id.in_(list(items))).order_by(Offer.id)))
    if len(offers) != len(items):
        raise ApiError("offer_not_active")
    stalls = {o.stall_id for o in offers}
    if len(stalls) != 1:
        raise ApiError("validation_failed", reason="single_stall_per_order")
    stall = db.get(Stall, offers[0].stall_id)
    market = db.get(Market, stall.market_id)
    products = {o.id: db.get(Product, o.product_id) for o in offers}
    zone = "REFRIGERATED" if any(p.food_class == "REFRIGERATED" for p in products.values()) else "AMBIENT"
    db.rollback()  # termina la lectura previa: la decisión se toma DENTRO de la transacción atómica

    wk = week_key(now)
    order_id = uuid.uuid4()
    s = get_settings()
    try:
        # 0) bloqueos en orden global fijo (sin interbloqueos): capacidad del mercado/zona, usuario+oferta, filas de oferta
        db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))"), {"k": f"cap:{market.id}:{zone}"})
        for o in offers:
            db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))"),
                       {"k": f"uo:{user.id}:{o.id}"})
        offers = list(db.scalars(select_orm_stmt(Offer, Offer.id.in_(list(items))).order_by(Offer.id)
                                 .with_for_update().execution_options(populate_existing=True)))
        for o in offers:
            if o.status == "SOLD_OUT":
                raise ApiError("out_of_stock", offer_id=str(o.id))
            if o.status != "ACTIVE" or o.pickup_until <= now:
                raise ApiError("offer_not_active", offer_id=str(o.id))
        if locker_free_slots(db, market.id, zone) < 1:
            raise ApiError("no_locker_capacity")

        # Motor de reglas (función pura) con datos ya bloqueados: unidades previas, saldo y capacidad exactos.
        total_cost, applied, total_cents = 0, [], 0
        points_left = reglas.points_state(db, user.id, now)["left"]
        for o in offers:
            sig = reglas.compute_signals(db, o, products[o.id], market, now)
            facts = reglas.user_facts(db, user, verified, o.id, now)
            facts = type(facts)(facts.status, facts.age_verified, facts.reputation, points_left - total_cost,
                                facts.units_already)
            _, policy = reglas.offer_policy(db, o.id)
            dec = reglas_engine().evaluate(facts, items[o.id], sig, policy, reglas.get_guardrails(db))
            if not dec.allowed:
                raise ApiError(dec.denial, offer_id=str(o.id), **dec.params)
            total_cost += dec.points_cost
            applied += [r for r in dec.rules_applied if r not in applied]
            total_cents += items[o.id] * o.price_cents
        allowance = reglas.get_guardrails(db)["weekly_allowance"]

        # 1) saldo de la semana (si no existe)
        db.execute(text("INSERT INTO points_week (user_id, week_key, allowance) VALUES (:u,:w,:a) "
                        "ON CONFLICT DO NOTHING"), {"u": user.id, "w": wk, "a": allowance})
        # 2) descuento condicional de puntos
        if total_cost > 0:
            r = db.execute(text("UPDATE points_week SET spent = spent + :c WHERE user_id=:u AND week_key=:w "
                                "AND spent + :c <= allowance RETURNING allowance - spent"),
                           {"c": total_cost, "u": user.id, "w": wk}).first()
            if r is None:
                raise ApiError("no_points")
        # 3) reserva condicional de stock
        for o in offers:
            r = db.execute(text(
                "UPDATE offers SET qty_available = qty_available - :q, "
                "status = CASE WHEN qty_available - :q = 0 THEN 'SOLD_OUT' ELSE status END "
                "WHERE id=:o AND status='ACTIVE' AND qty_available >= :q RETURNING qty_available"),
                {"q": items[o.id], "o": o.id}).first()
            if r is None:
                raise ApiError("out_of_stock", offer_id=str(o.id))
        # 4) pedido, líneas, libro y eventos: todo o nada
        order = Order(id=order_id, user_id=user.id, stall_id=stall.id, status="HELD", total_cents=total_cents,
                      points_cost=total_cost, rules_applied=applied, idempotency_key=idem_key,
                      hold_expires_at=now + timedelta(minutes=s.HOLD_MINUTES),
                      pickup_until=min(o.pickup_until for o in offers), created_at=now)
        db.add(order)
        db.flush()
        for o in offers:
            db.add(OrderItem(order_id=order_id, offer_id=o.id, qty=items[o.id], unit_cents=o.price_cents))
        if total_cost > 0:
            db.add(PointsLedger(user_id=user.id, week_key=wk, delta=-total_cost, reason="PURCHASE",
                                order_id=order_id, created_at=now))
            emit(db, now, "points.spent", order_id,
                 {"user_pseudo_id": pseudo_id(user.id), "week_key": wk, "delta": -total_cost})
        for o in offers:
            emit(db, now, "order.held", order_id, {
                "order_id": str(order_id), "user_pseudo_id": pseudo_id(user.id), "offer_id": str(o.id),
                "qty": items[o.id], "points_cost": total_cost, "rules_applied": applied})
            notif.publish_offer(db, o.id)
        notif.publish_order(db, order)
        db.commit()
        return order, True
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select_orm_stmt(Order, Order.idempotency_key == idem_key))
        if existing is not None and existing.user_id == user.id and _same_items(db, existing, items):
            return existing, False
        raise ApiError("idempotency_key_reused") from None
    except ApiError as e:
        db.rollback()
        _record_denial(db, now, user, first_offer, e.code)
        raise


def reglas_engine():
    from app.reglas import engine
    return engine
