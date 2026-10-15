import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Compartment, Deposit, Locker, Market, Offer, Order, OrderItem, Product, Stall
from app.taquillas.codes import pickup_code


def stall_out(s: Stall, market_name: str | None) -> dict:
    return {"id": str(s.id), "market_id": str(s.market_id), "market_name": market_name,
            "name": s.name, "category": s.category}


def serialize_orders(db: Session, orders: list[Order], viewer_id: uuid.UUID | None) -> list[dict]:
    if not orders:
        return []
    ids = [o.id for o in orders]
    items: dict[uuid.UUID, list] = {}
    for it, name in db.execute(select(OrderItem, Product.name).join(Offer, Offer.id == OrderItem.offer_id)
                               .join(Product, Product.id == Offer.product_id).where(OrderItem.order_id.in_(ids))):
        items.setdefault(it.order_id, []).append({"offer_id": str(it.offer_id), "product_name": name,
                                                  "qty": it.qty, "unit_cents": it.unit_cents})
    stalls = {s.id: (s, m) for s, m in db.execute(
        select(Stall, Market.name).join(Market, Market.id == Stall.market_id)
        .where(Stall.id.in_({o.stall_id for o in orders})))}
    lockers = {d.order_id: (c, l, mn) for d, c, l, mn in db.execute(
        select(Deposit, Compartment, Locker, Market.name).join(Compartment, Compartment.id == Deposit.compartment_id)
        .join(Locker, Locker.id == Compartment.locker_id).join(Market, Market.id == Locker.market_id)
        .where(Deposit.order_id.in_(ids)))}
    out = []
    for o in orders:
        s, mname = stalls[o.stall_id]
        lk = lockers.get(o.id)
        locker = {"locker_id": str(lk[1].id), "market_name": lk[2], "slot": lk[0].slot} if lk else None
        code = pickup_code(o.id) if (o.status == "IN_LOCKER" and viewer_id == o.user_id) else None
        out.append({
            "id": str(o.id), "stall": stall_out(s, mname), "status": o.status, "total_cents": o.total_cents,
            "points_cost": o.points_cost, "rules_applied": o.rules_applied,
            "hold_expires_at": o.hold_expires_at.isoformat() if o.hold_expires_at else None,
            "pickup_until": o.pickup_until.isoformat(), "created_at": o.created_at.isoformat(),
            "items": items.get(o.id, []), "locker": locker, "pickup_code": code})
    return out
