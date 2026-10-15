import os
import shutil
import tempfile
import uuid
from datetime import datetime, time, timedelta

import pytest

# Entorno de pruebas ANTES de importar la app
os.environ.setdefault("DEMO_MODE", "true")
os.environ["SCHEDULER_ENABLED"] = "false"
os.environ["NOTIFIERS"] = "inapp"
os.environ["MAIL_LOG_PATH"] = os.path.join(tempfile.gettempdir(), "mercat-test-mail.log")


@pytest.fixture(scope="session", autouse=True)
def _database():
    server, tmp = None, None
    try:
        if not os.environ.get("DATABASE_URL"):
            import pgserver
            tmp = tempfile.mkdtemp(prefix="mercat-pg-")
            server = pgserver.get_server(tmp, cleanup_mode="stop")
            uri = server.get_uri()
            os.environ["DATABASE_URL"] = uri.replace("postgresql://", "postgresql+psycopg://", 1)
        from app.config import get_settings
        get_settings.cache_clear()
        from alembic import command
        from alembic.config import Config
        cfg = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
        cfg.set_main_option("script_location", os.path.join(os.path.dirname(__file__), "..", "migraciones"))
        command.upgrade(cfg, "head")  # la 0001 emula citext si el servidor no lo trae
        yield
    finally:  # también si fallan las pruebas o se interrumpen: parar el servidor y borrar el directorio
        try:
            from app.db.session import reset_engine
            reset_engine()
        finally:
            if server is not None:
                try:
                    server.cleanup()
                finally:
                    shutil.rmtree(tmp, ignore_errors=True)
            elif tmp:
                shutil.rmtree(tmp, ignore_errors=True)


TABLES = ("deliveries, donations, charities, payouts, sessions, domain_events, push_subscriptions, notifications, "
          "subscriptions, deposits, compartments, lockers, payments, order_items, orders, points_ledger, "
          "points_week, offer_policies, offers, products, user_identities, users, stalls, markets, app_settings")


@pytest.fixture()
def db():
    from sqlalchemy import text
    from app import ratelimit
    from app.db.session import SessionLocal
    from app.reloj import DemoClock, parse_dt, set_clock
    from app.taquillas.transport import get_transport
    s = SessionLocal()
    s.execute(text(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE"))
    s.commit()
    set_clock(DemoClock(parse_dt("2026-10-16T12:00:00+02:00"), paused=True))
    ratelimit.clear()
    get_transport().reset()
    yield s
    s.close()


@pytest.fixture()
def world(db):
    """Mercado, puesto de pepa, producto, taquilla (4 compartimentos) y usuarios activos."""
    from app.db.models import (Compartment, Locker, Market, Offer, OfferPolicy, Product, Stall, User,
                               UserIdentity)
    from app.identidad.security import hash_password, person_hash
    from app.reglas.profiles import policy_for
    from app.reloj import get_clock
    now = get_clock().now()
    m = Market(id=uuid.uuid4(), name="Ruzafa", opens_at=time(8), closes_at=time(15), offers_from=time(11, 30))
    pepa = User(id=uuid.uuid4(), email="pepa@demo.test", password_hash=hash_password("secret123"),
                display_name="Pepa", role="PRODUCER", status="ACTIVE", created_at=now)
    mgr = User(id=uuid.uuid4(), email="gestion@demo.test", password_hash=hash_password("secret123"),
               display_name="Gestion", role="MANAGER", status="ACTIVE", created_at=now)
    db.add_all([m, pepa, mgr])
    db.flush()
    st = Stall(id=uuid.uuid4(), market_id=m.id, name="Fruteria Pepa", category="fruta", owner_user_id=pepa.id)
    db.add(st)
    db.flush()
    pr = Product(id=uuid.uuid4(), stall_id=st.id, name="Tomates", unit="kg", unit_weight_g=1000, vat_rate=4,
                 food_class="REFRIGERATED", usual_price_cents=300)
    db.add(pr)
    db.flush()
    lk = Locker(id=uuid.uuid4(), market_id=m.id, device_id="LK-1")
    db.add(lk)
    db.flush()
    comps = [Compartment(id=uuid.uuid4(), locker_id=lk.id, slot=i, size="M", zone="REFRIGERATED") for i in range(1, 5)]
    db.add_all(comps)
    db.commit()

    def make_user(name, rep=1.0, verified=True, status="ACTIVE"):
        u = User(id=uuid.uuid4(), email=f"{name}@demo.test", password_hash=hash_password("secret123"),
                 display_name=name, role="NEIGHBOR", status=status, reputation=rep, created_at=now)
        db.add(u)
        db.flush()
        if verified:
            db.add(UserIdentity(user_id=u.id, person_hash=person_hash(name), age_verified_at=now, age_method="demo"))
        db.commit()
        return u

    def make_offer(qty=10, price=150, until_min=120, profile="EQUILIBRADO", policy=None):
        o = Offer(id=uuid.uuid4(), stall_id=st.id, product_id=pr.id, qty_total=qty, qty_available=qty,
                  price_cents=price, pickup_from=now, pickup_until=now + timedelta(minutes=until_min),
                  status="ACTIVE", consume_by="TODAY", created_at=now)
        db.add(o)
        db.flush()
        db.add(OfferPolicy(offer_id=o.id, profile=profile, policy=policy or policy_for(profile)))
        db.commit()
        return o

    class W:
        pass
    w = W()
    w.market, w.stall, w.product, w.pepa, w.mgr, w.comps = m, st, pr, pepa, mgr, comps
    w.make_user, w.make_offer, w.now = make_user, make_offer, now
    return w


@pytest.fixture()
def client(db):
    from fastapi.testclient import TestClient
    from app.main import create_app
    app = create_app()
    with TestClient(app) as c:
        yield c


_ = datetime


@pytest.fixture(autouse=True)
def _fresh_settings():
    yield
    from app.config import get_settings
    get_settings.cache_clear()
