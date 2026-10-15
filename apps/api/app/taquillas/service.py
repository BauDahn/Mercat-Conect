"""Logística de taquillas: reserva, depósito, retirada y alarma de temperatura."""
import logging
import uuid
from datetime import datetime, timedelta

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.hooks import after_commit
from app.db.models import Compartment, Deposit, Locker, Market, Offer, Order, OrderItem, Product, Stall
from app.db.session import SessionLocal
from app.errors import ApiError
from app.eventos.outbox import emit
from app.notificaciones import service as notif
from app.pedidos import lifecycle
from app.reloj import get_clock
from app.taquillas import capacity
from app.taquillas.codes import code_hash, pickup_code
from app.taquillas.transport import CodeEntry, DeviceEvent, get_transport

log = logging.getLogger("mercat.taquillas")


def _register(db: Session, comp: Compartment) -> None:
    get_transport().register(comp.id, comp.locker_id, comp.slot, comp.zone)


def sync_from_db(db: Session) -> None:
    """Registra todos los compartimentos y reenvía los códigos vigentes (arranque / reset)."""
    t = get_transport()
    for c in db.scalars(select(Compartment)):
        _register(db, c)
    rows = db.execute(select(Deposit, Order.status).join(Order, Order.id == Deposit.order_id)
                      .where(Order.status == "IN_LOCKER", Deposit.deposited_at.is_not(None))).all()
    for d, _ in rows:
        st = t.state(d.compartment_id)
        if st is not None and not st.entries:
            t.push_codes(d.compartment_id, [CodeEntry(d.code_hash, d.valid_from, d.valid_until)])


def _order_weight_zone(db: Session, order: Order) -> tuple[int | None, str]:
    rows = db.execute(select(OrderItem.qty, Product.unit_weight_g, Product.food_class)
                      .join(Offer, Offer.id == OrderItem.offer_id).join(Product, Product.id == Offer.product_id)
                      .where(OrderItem.order_id == order.id)).all()
    zone = "REFRIGERATED" if any(r[2] == "REFRIGERATED" for r in rows) else "AMBIENT"
    if any(r[1] is None for r in rows):
        return None, zone
    return sum(r[0] * r[1] for r in rows), zone


def accept_order(db: Session, now: datetime, order: Order) -> None:
    """PAID -> PREPARING y reserva compartimento (sección 13.3)."""
    weight, zone = _order_weight_zone(db, order)
    market_id = db.scalar(select(Stall.market_id).where(Stall.id == order.stall_id))
    cid = capacity.reserve_compartment(db, market_id, zone, capacity.required_size(weight))
    if cid is None:
        raise ApiError("no_locker_capacity")
    lifecycle.accept(db, now, order)
    db.add(Deposit(order_id=order.id, compartment_id=cid, code_hash=b"", valid_from=now,
                   valid_until=order.pickup_until))
    db.flush()
    _register(db, db.get(Compartment, cid))


def producer_deposit(db: Session, now: datetime, order: Order) -> None:
    if order.status != "PREPARING":
        raise ApiError("invalid_transition", **{"from": order.status, "to": "IN_LOCKER"})
    dep = db.scalar(select(Deposit).where(Deposit.order_id == order.id))
    comp = db.get(Compartment, dep.compartment_id)
    if comp.status != "RESERVED":  # averiado entre medias: reasignar
        weight, zone = _order_weight_zone(db, order)
        market_id = db.scalar(select(Stall.market_id).where(Stall.id == order.stall_id))
        cid = capacity.reserve_compartment(db, market_id, zone, capacity.required_size(weight))
        if cid is None:
            raise ApiError("no_locker_capacity")
        dep.compartment_id = cid
        comp = db.get(Compartment, cid)
        db.flush()
    _register(db, comp)
    get_transport().open_compartment(comp.id)
    complete_deposit(db, now, order, dep, comp)
    after_commit(db, lambda: get_transport().close_door(comp.id, now, emit=False))


def _paid_at(db: Session, order: Order, fallback: datetime) -> datetime:
    r = db.execute(text("SELECT occurred_at FROM domain_events WHERE event_type='order.paid' AND aggregate_id=:o "
                        "ORDER BY id DESC LIMIT 1"), {"o": order.id}).first()
    return r[0] if r else fallback


def complete_deposit(db: Session, now: datetime, order: Order, dep: Deposit, comp: Compartment) -> None:
    lifecycle.move(db, order, "IN_LOCKER", now)
    code = pickup_code(order.id)
    until = max(order.pickup_until, now + timedelta(minutes=get_settings().PICKUP_GRACE_MINUTES))
    dep.code_hash, dep.deposited_at, dep.valid_from, dep.valid_until = code_hash(comp.id, code), now, now, until
    db.execute(text("UPDATE orders SET pickup_until=:u WHERE id=:o"), {"u": until, "o": order.id})
    order.pickup_until = until
    db.execute(text("UPDATE compartments SET status='OCCUPIED' WHERE id=:c AND status='RESERVED'"), {"c": comp.id})
    secs = int((now - _paid_at(db, order, order.created_at)).total_seconds())
    emit(db, now, "order.deposited", order.id,
         {"order_id": str(order.id), "compartment_id": str(comp.id), "seconds_since_paid": max(secs, 0)})
    locker = db.get(Locker, comp.locker_id)
    mname = db.scalar(select(Market.name).where(Market.id == locker.market_id))
    notif.notify(db, now, order.user_id, "ORDER_READY", {
        "order_id": str(order.id), "locker_id": str(locker.id), "market_name": mname, "slot": comp.slot,
        "pickup_code": code, "pickup_until": until.isoformat(), "link": f"/pedidos/{order.id}",
        "message": f"Tu pedido está en la taquilla {comp.slot} de {mname}. Consulta el código en tu pedido."})
    entry = CodeEntry(dep.code_hash, now, until)
    cid = comp.id
    after_commit(db, lambda: get_transport().push_codes(cid, [entry]))


def _trigger_alarm(db: Session, now: datetime, comp: Compartment, kind: str = "temperature") -> None:
    db.execute(text("UPDATE compartments SET status='OUT_OF_SERVICE' WHERE id=:c"), {"c": comp.id})
    emit(db, now, "locker.alarm", comp.locker_id, {"locker_id": str(comp.locker_id), "type": kind})
    order = db.scalar(select(Order).join(Deposit, Deposit.order_id == Order.id)
                      .where(Deposit.compartment_id == comp.id, Order.status == "IN_LOCKER").with_for_update())
    if order is not None:
        lifecycle.temp_alarm(db, now, order)
        notif.notify(db, now, order.user_id, "TEMP_ALARM", {"order_id": str(order.id),
                     "message": "Alarma de temperatura: producto retirado, reembolso y puntos devueltos"})
    notif.notify_managers(db, now, "LOCKER_ALARM", {"locker_id": str(comp.locker_id), "slot": comp.slot,
                                                    "type": kind})


def _eval_temp(db: Session, now: datetime, comp: Compartment) -> None:
    st = get_transport().state(comp.id)
    if st is None or comp.zone != "REFRIGERATED" or comp.status == "OUT_OF_SERVICE":
        return
    s = get_settings()
    if st.celsius > s.TEMP_ALARM_CELSIUS:
        if st.above_since is None:
            st.above_since = now
        if now - st.above_since >= timedelta(minutes=s.TEMP_ALARM_MINUTES):
            _trigger_alarm(db, now, comp)
            st.above_since = None
    else:
        st.above_since = None


def check_temperatures(db: Session, now: datetime) -> int:
    t = get_transport()
    n = 0
    for cid, st in t.states():
        if st.above_since is not None:
            comp = db.get(Compartment, cid)
            before = comp.status
            _eval_temp(db, now, comp)
            db.commit()
            db.refresh(comp)
            n += comp.status != before
    return n


def handle_device_event(ev: DeviceEvent) -> None:
    """Eventos de la taquilla hacia el dominio (sesión y transacción propias)."""
    db = SessionLocal()
    now = get_clock().now()
    try:
        comp = db.get(Compartment, ev.compartment_id)
        if comp is None:
            return
        if ev.kind == "door_closed":
            dep = db.scalar(select(Deposit).join(Order, Order.id == Deposit.order_id).where(
                Deposit.compartment_id == comp.id, Order.status == "PREPARING", Deposit.deposited_at.is_(None)))
            if dep is not None:
                order = db.scalar(select(Order).where(Order.id == dep.order_id).with_for_update())
                complete_deposit(db, now, order, dep, comp)
        elif ev.kind == "pickup":
            dep = db.scalar(select(Deposit).join(Order, Order.id == Deposit.order_id).where(
                Deposit.compartment_id == comp.id, Order.status == "IN_LOCKER"))
            if dep is not None:
                order = db.scalar(select(Order).where(Order.id == dep.order_id).with_for_update())
                dep.picked_up_at = ev.at
                secs = int((ev.at - dep.deposited_at).total_seconds()) if dep.deposited_at else 0
                lifecycle.picked_up(db, now, order, max(secs, 0))
                owner = db.scalar(select(Stall.owner_user_id).where(Stall.id == order.stall_id))
                if owner:
                    notif.notify(db, now, owner, "ORDER_PICKED_UP", {"order_id": str(order.id)})
        elif ev.kind == "temp":
            emit(db, now, "locker.temp_reading", comp.locker_id, {
                "locker_id": str(comp.locker_id), "compartment_id": str(comp.id), "celsius": ev.data["celsius"]})
            _eval_temp(db, now, comp)
        db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()
        log.exception("evento de taquilla no procesado")
    finally:
        db.close()


def init_transport() -> None:
    get_transport().set_handler(handle_device_event)


_ = uuid
