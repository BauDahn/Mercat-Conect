import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.models import Market, Stall, User
from app.db.session import get_db
from app.deps import require_roles
from app.errors import ApiError
from app.eventos import analytics
from app.pedidos.serialize import stall_out
from app.reglas import service as reglas
from app.reloj import get_clock

router = APIRouter()
mgr = require_roles("MANAGER", "ADMIN")


class Guardrails(BaseModel):
    max_points_per_unit: int | None = Field(default=None, ge=0)
    max_units_per_user: int | None = Field(default=None, ge=1)
    max_price_ratio: float | None = Field(default=None, gt=0)
    weekly_allowance: int | None = Field(default=None, ge=0)
    min_open_data_cell: int | None = Field(default=None, ge=1)


class StallInput(BaseModel):
    market_id: uuid.UUID
    name: str = Field(min_length=1)
    category: str = Field(min_length=1)
    owner_user_id: uuid.UUID | None = None


@router.put("/admin/guardrails")
def put_guardrails(body: Guardrails, user: User = Depends(mgr), db: Session = Depends(get_db)):
    patch = body.model_dump(exclude_unset=True)
    return reglas.put_guardrails(db, get_clock().now(), patch)


@router.post("/admin/stalls", status_code=201)
def create_stall(body: StallInput, user: User = Depends(mgr), db: Session = Depends(get_db)):
    market = db.get(Market, body.market_id)
    if market is None:
        raise ApiError("validation_failed", field="market_id")
    if body.owner_user_id and db.get(User, body.owner_user_id) is None:
        raise ApiError("validation_failed", field="owner_user_id")
    s = Stall(id=uuid.uuid4(), market_id=market.id, name=body.name, category=body.category,
              owner_user_id=body.owner_user_id, verified_at=get_clock().now())
    db.add(s)
    db.commit()
    return stall_out(s, market.name)


def _one(db, sql, **p):
    return db.execute(text(sql), p).scalar()


@router.get("/admin/calidad")
def calidad(user: User = Depends(mgr), db: Session = Depends(get_db)):
    now = get_clock().now()
    failures = analytics.quality(db, now)
    if failures is None:
        raise ApiError("conflict", "errors.analytics_unavailable", status=503)
    return {"ok": not failures, "checked_at": now.isoformat(),
            "failures": [{"test": t, "detail": d} for t, d in failures]}


@router.get("/admin/donations")
def donations(user: User = Depends(mgr), db: Session = Depends(get_db)):
    rows = db.execute(text(
        "SELECT d.id, d.offer_id, p.name, d.charity_id, c.name, d.qty, d.status, d.created_at, d.completed_at "
        "FROM donations d JOIN offers f ON f.id=d.offer_id JOIN products p ON p.id=f.product_id "
        "JOIN charities c ON c.id=d.charity_id ORDER BY d.created_at DESC, d.id LIMIT 500")).all()
    return {"items": [{"id": str(r[0]), "offer_id": str(r[1]), "product_name": r[2], "charity_id": str(r[3]),
                       "charity_name": r[4], "qty": r[5], "status": r[6], "created_at": r[7].isoformat(),
                       "completed_at": r[8].isoformat() if r[8] else None} for r in rows]}


@router.get("/admin/metrics")
def metrics(user: User = Depends(mgr), db: Session = Depends(get_db)):
    kg = _one(db, "SELECT coalesce(sum(oi.qty*p.unit_weight_g),0)/1000.0 FROM order_items oi "
                  "JOIN orders o ON o.id=oi.order_id JOIN offers f ON f.id=oi.offer_id "
                  "JOIN products p ON p.id=f.product_id WHERE o.status='PICKED_UP'")
    kgd = _one(db, "SELECT coalesce(sum(d.qty*p.unit_weight_g),0)/1000.0 FROM donations d "
                   "JOIN offers f ON f.id=d.offer_id JOIN products p ON p.id=f.product_id "
                   "WHERE d.status='COMPLETED'")
    published = _one(db, "SELECT coalesce(sum(qty_total),0) FROM offers WHERE status<>'DRAFT'")
    picked = _one(db, "SELECT coalesce(sum(oi.qty),0) FROM order_items oi JOIN orders o ON o.id=oi.order_id "
                      "WHERE o.status='PICKED_UP'")
    offers_n = _one(db, "SELECT count(*) FROM offers WHERE status<>'DRAFT'")
    sold_out = _one(db, "SELECT count(*) FROM offers WHERE status='SOLD_OUT'")
    paid_n = _one(db, "SELECT count(*) FROM orders WHERE status NOT IN ('HELD','EXPIRED_HOLD')")
    noshow = _one(db, "SELECT count(*) FROM orders WHERE status='NO_SHOW'")
    denied = _one(db, "SELECT count(*) FROM domain_events WHERE event_type='order.denied' "
                      "AND payload->>'reason'='sin_puntos'")
    attempts = _one(db, "SELECT count(*) FROM domain_events WHERE event_type IN ('order.held','order.denied')")
    comps = _one(db, "SELECT count(*) FROM compartments")
    busy = _one(db, "SELECT count(*) FROM compartments WHERE status IN ('RESERVED','OCCUPIED')")
    revenue = _one(db, "SELECT coalesce(sum(total_cents),0) FROM orders WHERE status IN "
                       "('PAID','PREPARING','IN_LOCKER','PICKED_UP','NO_SHOW')")
    heat = db.execute(text(
        "SELECT extract(dow FROM created_at AT TIME ZONE 'Europe/Madrid')::int, "
        "extract(hour FROM created_at AT TIME ZONE 'Europe/Madrid')::int, count(*) FROM orders "
        "GROUP BY 1,2 ORDER BY 1,2")).all()
    r = lambda a, b: round(a / b, 4) if b else 0.0  # noqa: E731
    return {"kg_rescued": float(kg), "kg_donated": float(kgd), "sell_through": r(picked, published),
            "sold_out_rate": r(sold_out, offers_n), "no_show_rate": r(noshow, paid_n),
            "points_denial_rate": r(denied, attempts), "locker_utilization": r(busy, comps),
            "co2_avoided_kg": None, "producer_revenue_cents": int(revenue),
            "heatmap": [{"weekday": h[0], "hour": h[1], "orders": h[2]} for h in heat]}
