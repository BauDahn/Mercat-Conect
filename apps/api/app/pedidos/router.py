import uuid

from fastapi import APIRouter, Depends, Header, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import ratelimit
from app.db.models import Order, Stall, User
from app.db.session import get_db
from app.deps import current_user, require_roles
from app.errors import ApiError
from app.pedidos import lifecycle, service
from app.pedidos.schemas import CreateOrderRequest
from app.pedidos.serialize import serialize_orders
from app.reloj import get_clock
from app.taquillas import service as taq

router = APIRouter()
STATUSES = {"HELD", "PAID", "EXPIRED_HOLD", "PREPARING", "CANCELLED_BY_PRODUCER", "IN_LOCKER", "PICKED_UP",
            "NO_SHOW", "TEMP_ALARM", "REFUNDED"}


def _status(status: str | None) -> str | None:
    if status is not None and status not in STATUSES:
        raise ApiError("validation_failed", field="status")
    return status


@router.post("/orders", status_code=201)
def create_order(body: CreateOrderRequest, response: Response, idempotency_key: str | None = Header(default=None),
                 user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not idempotency_key:
        raise ApiError("idempotency_key_required")
    if not 8 <= len(idempotency_key) <= 128:
        raise ApiError("bad_request", reason="idempotency_key_length")
    if not ratelimit.hit(f"orders:{user.id}", 60, 60):
        raise ApiError("rate_limited")
    order, created = service.create_order(db, get_clock().now(), user,
                                          [(i.offer_id, i.qty) for i in body.items], idempotency_key)
    if not created:
        response.status_code = 200
    return serialize_orders(db, [order], user.id)[0]


@router.get("/orders")
def list_orders(status: str | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    q = select(Order).where(Order.user_id == user.id)
    if _status(status):
        q = q.where(Order.status == status)
    orders = list(db.scalars(q.order_by(Order.created_at.desc())))
    return {"items": serialize_orders(db, orders, user.id)}


@router.get("/orders/{id}")
def get_order(id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    o = db.get(Order, id)
    if o is None:
        raise ApiError("not_found")
    owner = db.scalar(select(Stall.owner_user_id).where(Stall.id == o.stall_id))
    if o.user_id != user.id and owner != user.id and user.role not in ("MANAGER", "ADMIN"):
        raise ApiError("not_found")
    return serialize_orders(db, [o], user.id)[0]


# ---- productor ----
def _own_order(db: Session, user: User, id: uuid.UUID) -> Order:
    o = db.scalar(select(Order).where(Order.id == id).with_for_update())
    if o is None:
        raise ApiError("not_found")
    if db.scalar(select(Stall.owner_user_id).where(Stall.id == o.stall_id)) != user.id:
        raise ApiError("forbidden")
    return o


@router.get("/producer/orders")
def producer_orders(status: str | None = None, user: User = Depends(require_roles("PRODUCER")),
                    db: Session = Depends(get_db)):
    q = select(Order).join(Stall, Stall.id == Order.stall_id).where(Stall.owner_user_id == user.id)
    if _status(status):
        q = q.where(Order.status == status)
    return {"items": serialize_orders(db, list(db.scalars(q.order_by(Order.created_at.desc()))), user.id)}


def _act(db: Session, user: User, id: uuid.UUID, fn):
    o = _own_order(db, user, id)
    try:
        fn(db, get_clock().now(), o)
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(o)
    return serialize_orders(db, [o], user.id)[0]


@router.post("/producer/orders/{id}/accept")
def accept(id: uuid.UUID, user: User = Depends(require_roles("PRODUCER")), db: Session = Depends(get_db)):
    return _act(db, user, id, lambda d, n, o: _accept(d, n, o))


def _accept(db, now, order):
    if order.status != "PAID":
        raise ApiError("invalid_transition", **{"from": order.status, "to": "PREPARING"})
    taq.accept_order(db, now, order)


def _reject(db, now, order):
    if order.status != "PAID":
        raise ApiError("invalid_transition", **{"from": order.status, "to": "CANCELLED_BY_PRODUCER"})
    lifecycle.cancel_by_producer(db, now, order, "producer_rejected")


@router.post("/producer/orders/{id}/reject")
def reject(id: uuid.UUID, user: User = Depends(require_roles("PRODUCER")), db: Session = Depends(get_db)):
    return _act(db, user, id, _reject)


@router.post("/producer/orders/{id}/deposit")
def deposit(id: uuid.UUID, user: User = Depends(require_roles("PRODUCER")), db: Session = Depends(get_db)):
    return _act(db, user, id, taq.producer_deposit)


_ = lifecycle
