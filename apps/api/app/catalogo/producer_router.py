import uuid
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.catalogo import service
from app.db.models import Market, Offer, OfferPolicy, Product, Stall, User
from app.db.session import get_db
from app.deps import require_roles
from app.errors import ApiError
from app.eventos.outbox import emit
from app.notificaciones import service as notif
from app.pedidos.serialize import stall_out
from app.reglas import engine, service as reglas
from app.reglas.profiles import policy_for
from app.reloj import get_clock, local
from app.taquillas.capacity import free_slots_map

router = APIRouter()
Profile = Literal["LIBRE", "EQUILIBRADO", "ESTRICTO", "PERSONALIZADO"]


class OfferInput(BaseModel):
    stall_id: uuid.UUID
    product_id: uuid.UUID
    qty_total: int = Field(ge=1)
    price_cents: int = Field(ge=0)
    reference_price_cents: int | None = Field(default=None, ge=0)
    pickup_from: datetime
    pickup_until: datetime
    consume_by: Literal["TODAY", "BEST_BEFORE"]
    profile: Profile = "EQUILIBRADO"
    policy: dict[str, Any] | None = None
    publish: bool = True


class OfferPatch(BaseModel):
    qty_total: int | None = Field(default=None, ge=1)
    price_cents: int | None = Field(default=None, ge=0)
    reference_price_cents: int | None = Field(default=None, ge=0)
    pickup_from: datetime | None = None
    pickup_until: datetime | None = None
    profile: Profile | None = None
    policy: dict[str, Any] | None = None


def _policy(profile: str, custom: dict | None) -> dict:
    try:
        pol = policy_for(profile, custom)
    except ValueError:
        raise ApiError("validation_failed", field="policy") from None
    errs = engine.validate_policy(pol)
    if errs:
        raise ApiError("validation_failed", field="policy", errors=errs)
    return pol


def _check_price(db: Session, price: int, product: Product) -> None:
    ratio = reglas.get_guardrails(db).get("max_price_ratio")
    if ratio and product.usual_price_cents and price > product.usual_price_cents * ratio:
        raise ApiError("validation_failed", field="price_cents", reason="above_max_price_ratio")


def _check_offers_from(market: Market, now: datetime) -> None:
    lt = local(now)
    if (lt.hour, lt.minute) < (market.offers_from.hour, market.offers_from.minute):
        raise ApiError("validation_failed", reason="too_early_to_publish", offers_from=market.offers_from.isoformat())


def _published(db: Session, now: datetime, offer: Offer, stall: Stall, product: Product, market: Market) -> None:
    emit(db, now, "offer.published", offer.id, {
        "offer_id": str(offer.id), "stall_id": str(stall.id), "product_id": str(product.id),
        "qty": offer.qty_total, "price_cents": offer.price_cents,
        "pickup_window": {"from": offer.pickup_from.isoformat(), "until": offer.pickup_until.isoformat()}})
    notif.publish_offer(db, offer.id)
    db.flush()
    notif.match_offer(db, now, offer, stall, product, market)


def _own_offer(db: Session, user: User, id: uuid.UUID) -> Offer:
    o = db.scalar(select(Offer).where(Offer.id == id).with_for_update())
    if o is None:
        raise ApiError("not_found")
    if db.scalar(select(Stall.owner_user_id).where(Stall.id == o.stall_id)) != user.id:
        raise ApiError("forbidden")
    return o


def _detail(db: Session, offer_id: uuid.UUID) -> dict:
    db.expire_all()
    o, s, p, m = service.load_offer(db, offer_id)
    out = service.offer_out(o, s, p, m, free_slots_map(db))
    out["decision"] = None
    out["policy_profile"] = service.policy_profile(db, o.id)
    return out


@router.get("/producer/stalls")
def my_stalls(user: User = Depends(require_roles("PRODUCER")), db: Session = Depends(get_db)):
    rows = db.execute(select(Stall, Market.name).join(Market, Market.id == Stall.market_id)
                      .where(Stall.owner_user_id == user.id).order_by(Stall.name)).all()
    return {"items": [stall_out(s, mn) for s, mn in rows]}


@router.get("/products")
def products(stall_id: uuid.UUID, user: User = Depends(require_roles("PRODUCER")), db: Session = Depends(get_db)):
    st = db.get(Stall, stall_id)
    if st is None or st.owner_user_id != user.id:
        raise ApiError("forbidden")
    return {"items": [service.product_out(p) for p in db.scalars(
        select(Product).where(Product.stall_id == stall_id).order_by(Product.name))]}


OFFER_STATUSES = {"DRAFT", "ACTIVE", "SOLD_OUT", "EXPIRED", "WITHDRAWN", "DONATED", "DISCARDED"}


@router.get("/producer/offers")
def my_offers(status: str | None = None, user: User = Depends(require_roles("PRODUCER")),
              db: Session = Depends(get_db)):
    if status is not None and status not in OFFER_STATUSES:
        raise ApiError("validation_failed", field="status")
    stmt = (select(Offer, Stall, Product, Market).join(Stall, Stall.id == Offer.stall_id)
            .join(Product, Product.id == Offer.product_id).join(Market, Market.id == Stall.market_id)
            .where(Stall.owner_user_id == user.id))
    if status:
        stmt = stmt.where(Offer.status == status)
    free = free_slots_map(db)
    items = []
    for o, s_, p, m in db.execute(stmt.order_by(Offer.created_at.desc(), Offer.id)).all():
        d = service.offer_out(o, s_, p, m, free)
        d["decision"] = None
        d["policy_profile"] = service.policy_profile(db, o.id)
        items.append(d)
    return {"items": items}


@router.post("/producer/offers", status_code=201)
def create(body: OfferInput, user: User = Depends(require_roles("PRODUCER")), db: Session = Depends(get_db)):
    now = get_clock().now()
    stall = db.get(Stall, body.stall_id)
    if stall is None or stall.owner_user_id != user.id:
        raise ApiError("forbidden")
    product = db.get(Product, body.product_id)
    if product is None or product.stall_id != stall.id:
        raise ApiError("validation_failed", field="product_id")
    if body.pickup_until <= body.pickup_from or body.pickup_until <= now:
        raise ApiError("validation_failed", field="pickup_until")
    _check_price(db, body.price_cents, product)
    market = db.get(Market, stall.market_id)
    lt = local(now)
    if body.publish:
        _check_offers_from(market, now)
    pol = _policy(body.profile, body.policy)
    oid = uuid.uuid4()
    offer = Offer(id=oid, stall_id=stall.id, product_id=product.id, qty_total=body.qty_total,
                  qty_available=body.qty_total, price_cents=body.price_cents,
                  reference_price_cents=body.reference_price_cents, pickup_from=body.pickup_from,
                  pickup_until=body.pickup_until, status="ACTIVE" if body.publish else "DRAFT",
                  consume_by=body.consume_by, created_at=now)
    db.add(offer)
    db.flush()
    db.add(OfferPolicy(offer_id=oid, profile=body.profile, policy=pol, version=int(pol.get("version", 1))))
    if body.publish:
        _published(db, now, offer, stall, product, market)
    db.commit()
    return _detail(db, oid)


@router.patch("/producer/offers/{id}")
def patch(id: uuid.UUID, body: OfferPatch, user: User = Depends(require_roles("PRODUCER")),
          db: Session = Depends(get_db)):
    now = get_clock().now()
    o = _own_offer(db, user, id)
    if o.status not in ("DRAFT", "ACTIVE"):   # SOLD_OUT solo vuelve a ACTIVE por liberación de stock
        raise ApiError("invalid_transition", **{"from": o.status})
    product = db.get(Product, o.product_id)
    data = body.model_dump(exclude_unset=True)
    old_price = o.price_cents
    if "price_cents" in data:
        _check_price(db, data["price_cents"], product)
        o.price_cents = data["price_cents"]
    if "reference_price_cents" in data:
        o.reference_price_cents = data["reference_price_cents"]
    if "pickup_from" in data and data["pickup_from"]:
        o.pickup_from = data["pickup_from"]
    if "pickup_until" in data and data["pickup_until"]:
        o.pickup_until = data["pickup_until"]
    if o.pickup_until <= o.pickup_from:
        raise ApiError("validation_failed", field="pickup_until")
    if data.get("qty_total"):
        delta = data["qty_total"] - o.qty_total
        if o.qty_available + delta < 0 or (o.status == "ACTIVE" and o.qty_available + delta == 0):
            raise ApiError("conflict", reason="below_sold_units")   # el estado nunca cambia por PATCH
        o.qty_total, o.qty_available = data["qty_total"], o.qty_available + delta
    if data.get("profile") or data.get("policy"):
        prof = data.get("profile") or (service.policy_profile(db, o.id) or "EQUILIBRADO")
        pol = _policy(prof, data.get("policy"))
        row = db.get(OfferPolicy, o.id)
        if row:
            row.profile, row.policy, row.version = prof, pol, row.version + 1
        else:
            db.add(OfferPolicy(offer_id=o.id, profile=prof, policy=pol))
    if o.price_cents != old_price:
        emit(db, now, "offer.price_changed", o.id,
             {"offer_id": str(o.id), "old_cents": old_price, "new_cents": o.price_cents})
    notif.publish_offer(db, o.id)
    db.commit()
    return _detail(db, id)


@router.post("/producer/offers/{id}/publish")
def publish(id: uuid.UUID, user: User = Depends(require_roles("PRODUCER")), db: Session = Depends(get_db)):
    now = get_clock().now()
    o = _own_offer(db, user, id)
    if o.status != "DRAFT":
        raise ApiError("invalid_transition", **{"from": o.status, "to": "ACTIVE"})
    if o.pickup_until <= now:
        raise ApiError("validation_failed", field="pickup_until")
    stall = db.get(Stall, o.stall_id)
    market = db.get(Market, stall.market_id)
    _check_offers_from(market, now)
    db.execute(text("UPDATE offers SET status='ACTIVE' WHERE id=:o AND status='DRAFT'"), {"o": id})
    db.refresh(o)
    _published(db, now, o, stall, db.get(Product, o.product_id), market)
    db.commit()
    return _detail(db, id)


@router.delete("/producer/offers/{id}", status_code=204)
def delete_draft(id: uuid.UUID, user: User = Depends(require_roles("PRODUCER")), db: Session = Depends(get_db)):
    o = _own_offer(db, user, id)
    if o.status != "DRAFT":
        raise ApiError("invalid_transition", **{"from": o.status, "to": "deleted"})
    db.execute(text("DELETE FROM offer_policies WHERE offer_id=:o"), {"o": id})
    db.delete(o)
    db.commit()
    return Response(status_code=204)


@router.post("/producer/offers/{id}/withdraw")
def withdraw(id: uuid.UUID, user: User = Depends(require_roles("PRODUCER")), db: Session = Depends(get_db)):
    now = get_clock().now()
    o = _own_offer(db, user, id)
    if o.status != "ACTIVE":
        raise ApiError("invalid_transition", **{"from": o.status, "to": "WITHDRAWN"})
    db.execute(text("UPDATE offers SET status='WITHDRAWN' WHERE id=:o"), {"o": id})
    emit(db, now, "offer.withdrawn", id, {"offer_id": str(id), "qty_remaining": o.qty_available})
    notif.publish_offer(db, id)
    db.commit()
    return _detail(db, id)
