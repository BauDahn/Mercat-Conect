"""SOLO DEMO (DEMO_MODE=true): taquillas virtuales."""
import uuid
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Compartment, Deposit, Locker, Order
from app.db.session import get_db
from app.errors import ApiError
from app.reloj import get_clock
from app.taquillas import service
from app.taquillas.transport import get_transport

router = APIRouter(tags=["demo"])


def _comp_out(db: Session, c: Compartment) -> dict[str, Any]:
    st = get_transport().state(c.id)
    order_id = db.scalar(select(Deposit.order_id).join(Order, Order.id == Deposit.order_id).where(
        Deposit.compartment_id == c.id, Order.status.in_(("PREPARING", "IN_LOCKER"))))
    return {"slot": c.slot, "size": c.size, "zone": c.zone, "status": c.status,
            "door": st.door if st else "CLOSED", "celsius": st.celsius if st else None,
            "order_id": str(order_id) if order_id else None}


@router.get("/sim/lockers")
def list_lockers(db: Session = Depends(get_db)):
    service.sync_from_db(db)
    out = []
    for lk in db.scalars(select(Locker).order_by(Locker.device_id)):
        comps = db.scalars(select(Compartment).where(Compartment.locker_id == lk.id).order_by(Compartment.slot))
        out.append({"id": str(lk.id), "device_id": lk.device_id, "market_id": str(lk.market_id),
                    "online": not get_transport().is_offline(lk.id),
                    "compartments": [_comp_out(db, c) for c in comps]})
    return {"items": out}


class NetBody(BaseModel):
    online: bool


@router.post("/sim/lockers/{locker_id}/network")
def network(locker_id: uuid.UUID, body: NetBody, db: Session = Depends(get_db)):
    lk = db.get(Locker, locker_id)
    if lk is None:
        raise ApiError("not_found")
    service.sync_from_db(db)
    get_transport().set_online(lk.id, body.online)   # al volver la red se sincronizan los eventos en cola
    db.expire_all()
    comps = db.scalars(select(Compartment).where(Compartment.locker_id == lk.id).order_by(Compartment.slot))
    return {"id": str(lk.id), "device_id": lk.device_id, "market_id": str(lk.market_id),
            "online": body.online, "compartments": [_comp_out(db, c) for c in comps]}


@router.post("/sim/lockers/{locker_id}/compartments/{slot}/{action}")
def action(locker_id: uuid.UUID, slot: int, action: str, body: dict | None = None, db: Session = Depends(get_db)):
    body = body or {}
    comp = db.scalar(select(Compartment).where(Compartment.locker_id == locker_id, Compartment.slot == slot))
    if comp is None or action not in ("close_door", "open_door", "enter_code", "set_temperature", "fail"):
        raise ApiError("not_found")
    t = get_transport()
    service._register(db, comp)  # noqa: SLF001
    now = get_clock().now()
    st = t.state(comp.id)
    if action == "close_door":
        if st.door != "OPEN":
            raise ApiError("conflict", reason="door_already_closed")
        t.close_door(comp.id, now)
    elif action == "open_door":
        if comp.status == "OCCUPIED":
            raise ApiError("forbidden", reason="needs_code")
        if comp.status == "OUT_OF_SERVICE":
            raise ApiError("conflict", reason="out_of_service")
        t.open_compartment(comp.id)
    elif action == "enter_code":
        if comp.status != "OCCUPIED":
            raise ApiError("conflict", reason="nothing_to_pick_up")
        if not t.enter_code(comp.id, str(body.get("code", "")), now):
            raise ApiError("forbidden", reason="invalid_code")
    elif action == "set_temperature":
        if not isinstance(body.get("celsius"), (int, float)):
            raise ApiError("validation_failed", field="celsius")
        t.set_temperature(comp.id, float(body["celsius"]), now)
    elif action == "fail":
        if comp.status == "OCCUPIED":
            raise ApiError("conflict", reason="occupied")
        comp.status = "OUT_OF_SERVICE"
        db.commit()
    db.expire_all()
    return _comp_out(db, db.get(Compartment, comp.id))
