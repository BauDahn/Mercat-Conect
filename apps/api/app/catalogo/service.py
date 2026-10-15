import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Market, Offer, OfferPolicy, Product, Stall
from app.identidad.service import is_age_verified
from app.pedidos.serialize import stall_out
from app.reglas import service as reglas
from app.taquillas.capacity import free_slots_map


def product_out(p: Product) -> dict:
    return {"id": str(p.id), "name": p.name, "unit": p.unit, "unit_weight_g": p.unit_weight_g,
            "vat_rate": float(p.vat_rate), "allergens": list(p.allergens or []), "food_class": p.food_class,
            "usual_price_cents": p.usual_price_cents, "photo_url": p.photo_path}


def offer_out(o: Offer, s: Stall, p: Product, m: Market, free: dict) -> dict:
    slots = free.get((m.id, p.food_class), 0)
    return {"id": str(o.id), "stall": stall_out(s, m.name), "product": product_out(p), "qty_total": o.qty_total,
            "qty_available": o.qty_available, "effective_stock": min(o.qty_available, slots),
            "price_cents": o.price_cents, "reference_price_cents": o.reference_price_cents,
            "pickup_from": o.pickup_from.isoformat(), "pickup_until": o.pickup_until.isoformat(),
            "status": o.status, "consume_by": o.consume_by}


def load_offer(db: Session, offer_id: uuid.UUID):
    return db.execute(select(Offer, Stall, Product, Market).join(Stall, Stall.id == Offer.stall_id)
                      .join(Product, Product.id == Offer.product_id).join(Market, Market.id == Stall.market_id)
                      .where(Offer.id == offer_id)).first()


def list_offers(db: Session, now: datetime, market: uuid.UUID | None, category: str | None, sort: str,
                q: str | None, user=None) -> list[dict]:
    stmt = (select(Offer, Stall, Product, Market).join(Stall, Stall.id == Offer.stall_id)
            .join(Product, Product.id == Offer.product_id).join(Market, Market.id == Stall.market_id)
            .where(Offer.status == "ACTIVE", Offer.pickup_until > now))
    if market:
        stmt = stmt.where(Stall.market_id == market)
    if category:
        stmt = stmt.where(Stall.category == category)
    if q:
        stmt = stmt.where(Product.name.ilike(f"%{q}%"))
    stmt = stmt.order_by({"price_asc": Offer.price_cents.asc(), "price_desc": Offer.price_cents.desc(),
                          "newest": Offer.created_at.desc()}.get(sort, Offer.pickup_until.asc()), Offer.id)
    free = free_slots_map(db)
    verified = is_age_verified(db, user.id) if user is not None else False
    out = []
    for o, s, p, m in db.execute(stmt).all():
        d = offer_out(o, s, p, m, free)
        d["decision"] = reglas.decide(db, user, verified, o, s, p, m, 1, now).to_api() if user is not None else None
        d["policy_profile"] = policy_profile(db, o.id)
        out.append(d)
    return out


def policy_profile(db: Session, offer_id: uuid.UUID) -> str | None:
    row = db.get(OfferPolicy, offer_id)
    return row.profile if row else None
