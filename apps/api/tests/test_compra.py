import threading
import uuid

from sqlalchemy import text

from app.db.session import SessionLocal
from app.errors import ApiError
from app.pedidos import service
from app.reloj import get_clock


def buy(user_id, offer_id, qty=1, key=None, results=None):
    db = SessionLocal()
    try:
        from app.db.models import User
        u = db.get(User, user_id)
        order, created = service.create_order(db, get_clock().now(), u, [(offer_id, qty)], key or uuid.uuid4().hex)
        r = ("ok", created)
    except ApiError as e:
        r = ("err", e.code)
    finally:
        db.close()
    if results is not None:
        results.append(r)
    return r


def test_compra_basica_y_idempotencia(db, world):
    u = world.make_user("marta")
    o = world.make_offer(qty=5)
    key = "k-12345678"
    assert buy(u.id, o.id, 2, key) == ("ok", True)
    assert buy(u.id, o.id, 2, key) == ("ok", False)          # reintento: mismo pedido
    assert buy(u.id, o.id, 1, key) == ("err", "idempotency_key_reused")
    db.expire_all()
    assert db.execute(text("select qty_available from offers")).scalar() == 3
    assert db.execute(text("select spent from points_week")).scalar() == 4
    assert db.execute(text("select count(*) from orders")).scalar() == 1


def test_sin_puntos_y_stock_no_cambian_nada(db, world):
    u = world.make_user("luis")
    o = world.make_offer(qty=5)
    db.execute(text("insert into points_week (user_id, week_key, allowance, spent) "
                    "values (:u, '2026-W42', 20, 20)"), {"u": u.id})
    db.commit()
    assert buy(u.id, o.id) == ("err", "no_points")
    db.expire_all()
    assert db.execute(text("select qty_available from offers")).scalar() == 5
    assert db.execute(text("select count(*) from orders")).scalar() == 0
    assert db.execute(text("select count(*) from domain_events where event_type='order.denied'")).scalar() == 1


def test_no_verificado(db, world):
    u = world.make_user("nuevo", verified=False, status="PENDING")
    o = world.make_offer()
    assert buy(u.id, o.id) == ("err", "account_not_verified")


def test_concurrencia_200_compradores_10_unidades(db, world):
    o = world.make_offer(qty=10, profile="LIBRE")
    users = [world.make_user(f"c{i}") for i in range(60)]
    # capacidad de taquilla no limita esta prueba: 60 compradores, 4 compartimentos -> sube a 60
    from app.db.models import Compartment
    for i in range(5, 70):
        db.add(Compartment(id=uuid.uuid4(), locker_id=world.comps[0].locker_id, slot=i, size="M",
                           zone="REFRIGERATED"))
    db.commit()
    results: list = []
    threads = [threading.Thread(target=buy, args=(u.id, o.id, 1, None, results)) for u in users]
    [t.start() for t in threads]
    [t.join() for t in threads]
    oks = [r for r in results if r[0] == "ok"]
    assert len(oks) == 10, results
    assert all(r == ("err", "out_of_stock") for r in results if r[0] == "err")
    db.expire_all()
    assert db.execute(text("select qty_available from offers")).scalar() == 0
    assert db.execute(text("select status from offers")).scalar() == "SOLD_OUT"
    assert db.execute(text("select count(*) from orders")).scalar() == 10


def test_mismo_usuario_concurrente_no_supera_saldo(db, world):
    u = world.make_user("acaparador")
    offers = [world.make_offer(qty=20, profile="LIBRE", policy={"base": {"points_per_unit": 3,
              "max_units_per_user": 10}}) for _ in range(8)]
    results: list = []
    threads = [threading.Thread(target=buy, args=(u.id, o.id, 1, None, results)) for o in offers]
    [t.start() for t in threads]
    [t.join() for t in threads]
    db.expire_all()
    spent = db.execute(text("select spent from points_week")).scalar()
    assert spent <= 20 and spent == 3 * len([r for r in results if r[0] == "ok"])
