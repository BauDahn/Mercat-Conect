import uuid
from datetime import datetime, timedelta

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import AppSetting, Market, Offer, OfferPolicy, PointsWeek, Product, Stall
from app.reglas import engine
from app.reglas.profiles import policy_for
from app.reloj import local, next_week_start, week_key
from app.taquillas.capacity import locker_free_slots

NON_COUNTING = ("EXPIRED_HOLD", "CANCELLED_BY_PRODUCER", "REFUNDED", "TEMP_ALARM")


def get_guardrails(db: Session) -> dict:
    row = db.get(AppSetting, "guardrails")
    g = {**engine.DEFAULT_GUARDRAILS, "weekly_allowance": get_settings().DEFAULT_ALLOWANCE}
    if row:
        g.update(row.value)
    return g


def put_guardrails(db: Session, now: datetime, patch: dict) -> dict:
    g = get_guardrails(db)
    g.update(patch)
    row = db.get(AppSetting, "guardrails")
    if row:
        row.value, row.updated_at = g, now
    else:
        db.add(AppSetting(key="guardrails", value=g, updated_at=now))
    db.commit()
    return g


def points_state(db: Session, user_id: uuid.UUID, now: datetime) -> dict:
    wk = week_key(now)
    row = db.get(PointsWeek, (user_id, wk))
    allowance = row.allowance if row else get_guardrails(db)["weekly_allowance"]
    spent = row.spent if row else 0
    return {"week_key": wk, "allowance": allowance, "spent": spent, "left": allowance - spent,
            "renews_at": next_week_start(now).isoformat()}


def time_band(minutes: int) -> str:
    return "apertura" if minutes < 600 else "media_manana" if minutes < 750 else "comida" if minutes < 870 else "cierre"


def demand_attempts(db: Session, offer_id: uuid.UUID, now: datetime) -> int:
    return db.execute(text(
        "SELECT count(*) FROM domain_events WHERE event_type IN ('order.held','order.denied') "
        "AND payload->>'offer_id' = :o AND occurred_at > :since AND occurred_at <= :now"),
        {"o": str(offer_id), "since": now - timedelta(minutes=10), "now": now}).scalar() or 0


def compute_signals(db: Session, offer: Offer, product: Product, market: Market, now: datetime) -> engine.Signals:
    loc = local(now)
    minutes = loc.hour * 60 + loc.minute
    to_close = (offer.pickup_until - now).total_seconds() / 60
    mclose = loc.replace(hour=market.closes_at.hour, minute=market.closes_at.minute, second=0, microsecond=0)
    if mclose > loc:
        to_close = min(to_close, (mclose - loc).total_seconds() / 60)
    attempts = demand_attempts(db, offer.id, now)
    return engine.Signals(
        stock_ratio=offer.qty_available / offer.qty_total,
        demand_velocity=attempts / max(offer.qty_available, 1),
        minutes_to_close=max(0.0, to_close), time_band=time_band(minutes),
        locker_free_slots=locker_free_slots(db, market.id, product.food_class), local_minutes=minutes)


def user_facts(db: Session, user, verified: bool, offer_id: uuid.UUID, now: datetime) -> engine.UserFacts:
    left = points_state(db, user.id, now)["left"]
    already = db.execute(text(
        "SELECT coalesce(sum(oi.qty),0) FROM order_items oi JOIN orders o ON o.id=oi.order_id "
        "WHERE o.user_id=:u AND oi.offer_id=:f AND o.status NOT IN :ex").bindparams(
        bindparam("ex", expanding=True)),
        {"u": user.id, "f": offer_id, "ex": list(NON_COUNTING)}).scalar() or 0
    return engine.UserFacts(status=user.status, age_verified=verified, reputation=float(user.reputation),
                            points_left=left, units_already=int(already))


def offer_policy(db: Session, offer_id: uuid.UUID) -> tuple[str, dict]:
    row = db.get(OfferPolicy, offer_id)
    if row is None:
        return "EQUILIBRADO", policy_for("EQUILIBRADO")
    return row.profile, row.policy


def decide(db: Session, user, verified: bool, offer: Offer, stall: Stall, product: Product, market: Market,
           qty: int, now: datetime) -> engine.Decision:
    sig = compute_signals(db, offer, product, market, now)
    facts = user_facts(db, user, verified, offer.id, now)
    _, policy = offer_policy(db, offer.id)
    return engine.evaluate(facts, qty, sig, policy, get_guardrails(db))

