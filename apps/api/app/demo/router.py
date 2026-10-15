"""SOLO DEMO (DEMO_MODE=true): reloj, demanda sintética y reinicio."""
import hashlib
import random
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import ratelimit
from app.config import get_settings
from app.db.models import Offer, User, UserIdentity
from app.db.session import SessionLocal, get_db, reset_engine
from app.errors import ApiError
from app.eventos import analytics
from app.identidad.security import person_hash
from app.pedidos import service as pedidos
from app.planificador import run_due
from app.reloj import DemoClock, get_clock, parse_dt
from app.taquillas import service as taq
from app.taquillas.transport import get_transport

router = APIRouter(tags=["demo"])
REPO_ROOT = Path(__file__).resolve().parents[4]


class ClockBody(BaseModel):
    set: datetime | None = None
    advance_seconds: int | None = Field(default=None, ge=0)
    paused: bool | None = None


class SimBody(BaseModel):
    offer_id: uuid.UUID | None = None
    buyers: int = Field(default=20, ge=1, le=500)
    scenario: str = Field(default="steady", pattern="^(peak|steady|closing)$")


@router.post("/demo/clock")
def clock(body: ClockBody, db: Session = Depends(get_db)):
    c = get_clock()
    if not isinstance(c, DemoClock):
        raise ApiError("demo_only")
    if body.set is None and body.advance_seconds is None and body.paused is None:
        raise ApiError("validation_failed", reason="set_advance_or_paused_required")
    if body.set is not None:
        c.set(body.set)
    if body.advance_seconds:
        c.advance(body.advance_seconds)
    if body.paused is not None:
        c.pause() if body.paused else c.resume()
    run_due(db, c.now(), force_analytics=True)
    return {"now": c.now().isoformat(), "paused": c.paused}


def _synthetic_user(db: Session, now: datetime, i: int) -> User:
    email = f"sim{i:03d}@demo.test"
    u = db.scalar(select(User).where(User.email == email))
    if u is None:
        u = User(id=uuid.uuid4(), email=email, password_hash=None, display_name=f"Comprador sim {i}",
                 role="NEIGHBOR", status="ACTIVE", created_at=now)
        db.add(u)
        db.flush()
        db.add(UserIdentity(user_id=u.id, person_hash=person_hash(f"SYNTH-{i}"), age_verified_at=now,
                            age_method="demo"))
        db.commit()
    return u


@router.post("/demo/simulate")
def simulate(body: SimBody, db: Session = Depends(get_db)):
    now = get_clock().now()
    if body.offer_id is not None:
        if db.get(Offer, body.offer_id) is None:
            raise ApiError("not_found")
        pool = [body.offer_id]
    else:
        pool = list(db.scalars(select(Offer.id).where(Offer.status == "ACTIVE", Offer.pickup_until > now)
                               .order_by(Offer.pickup_until, Offer.id)))
        if not pool:
            return {"attempted": 0, "held": 0, "denied": 0}
    seed = int(hashlib.sha256(f"{get_settings().DEMO_SEED}|{now.isoformat()}|{body.buyers}|{body.scenario}"
                              .encode()).hexdigest()[:12], 16)
    rnd = random.Random(seed)
    held = denied = 0
    for i in range(body.buyers):
        user = _synthetic_user(db, now, i)
        offer_id = pool[0] if body.scenario == "closing" and len(pool) > 1 and rnd.random() < 0.6 else rnd.choice(pool)
        qty = rnd.choice([1, 1, 2]) if body.scenario == "peak" else rnd.choice([1, 2, 3]) if body.scenario == "closing" else 1
        try:
            pedidos.create_order(db, now, user, [(offer_id, qty)], f"sim-{uuid.uuid4().hex}")
            held += 1
        except ApiError:
            db.rollback()
            denied += 1
    return {"attempted": body.buyers, "held": held, "denied": denied}


@router.post("/demo/reset", status_code=204)
def reset(db: Session = Depends(get_db)):
    script = REPO_ROOT / "data" / "seed" / "run.py"
    if not script.exists():
        raise ApiError("conflict", "errors.seed_unavailable", status=503, path="data/seed/run.py")
    db.close()
    reset_engine()
    s = get_settings()
    import os
    env = {**os.environ, "DATABASE_URL": s.DATABASE_URL, "DEMO_SEED": str(s.DEMO_SEED)}
    r = subprocess.run([sys.executable, str(script)], cwd=REPO_ROOT, env=env, capture_output=True, text=True,
                       timeout=180)
    if r.returncode != 0:
        raise ApiError("conflict", "errors.seed_failed", status=500, detail=r.stderr[-500:])
    c = get_clock()
    if isinstance(c, DemoClock):
        c.set(parse_dt(s.DEMO_CLOCK_START))
    ratelimit.clear()
    analytics.reset_state()
    t = get_transport()
    t.reset()
    with SessionLocal() as d:
        taq.sync_from_db(d)
