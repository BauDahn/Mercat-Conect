import time
import uuid

from sqlalchemy import text

from tests.test_flujo import login, new_client, order


def test_me_stalls_products(client, db, world):
    world.make_user("marta")
    c = login(new_client(), "marta@demo.test")
    me = c.get("/me").json()
    assert me["role"] == "NEIGHBOR" and me["age_verified"] and me["lang"] == "es"
    assert client.get("/me").status_code == 401
    p = login(new_client(), "pepa@demo.test")
    st = p.get("/producer/stalls").json()["items"]
    assert [s["id"] for s in st] == [str(world.stall.id)] and st[0]["market_name"] == "Ruzafa"
    assert [x["name"] for x in p.get("/products", params={"stall_id": st[0]["id"]}).json()["items"]] == ["Tomates"]
    assert p.get("/products", params={"stall_id": str(uuid.uuid4())}).status_code == 403
    assert c.get("/producer/stalls").status_code == 403


def test_listado_con_decision(client, db, world):
    world.make_user("marta")
    world.make_offer()
    assert client.get("/offers").json()["items"][0]["decision"] is None
    c = login(new_client(), "marta@demo.test")
    d = c.get("/offers").json()["items"][0]["decision"]
    assert d["allowed"] and d["points_cost"] == 2


def test_rechazo_del_productor(client, db, world):
    world.make_user("marta")
    o = world.make_offer()
    c = login(new_client(), "marta@demo.test")
    oid = order(c, o.id, 2).json()["id"]
    p = login(new_client(), "pepa@demo.test")
    assert p.post(f"/producer/orders/{oid}/reject").status_code == 409     # aún HELD
    c.post(f"/orders/{oid}/pay", json={})
    r = p.post(f"/producer/orders/{oid}/reject")
    assert r.status_code == 200 and r.json()["status"] == "REFUNDED"
    assert c.get("/me/points").json()["left"] == 20
    assert db.execute(text("select status from payments")).scalar() == "REFUNDED"
    assert db.execute(text("select count(*) from domain_events where event_type='order.cancelled' "
                           "and payload->>'cause'='producer_rejected'")).scalar() == 1


def test_red_de_taquilla_offline(client, db, world):
    world.make_user("marta")
    o = world.make_offer()
    c = login(new_client(), "marta@demo.test")
    oid = order(c, o.id).json()["id"]
    c.post(f"/orders/{oid}/pay", json={})
    p = login(new_client(), "pepa@demo.test")
    p.post(f"/producer/orders/{oid}/accept")
    p.post(f"/producer/orders/{oid}/deposit")
    code = c.get(f"/orders/{oid}").json()["pickup_code"]
    slot = c.get(f"/orders/{oid}").json()["locker"]["slot"]
    lk = client.get("/sim/lockers").json()["items"][0]
    assert lk["online"] is True
    assert client.post(f"/sim/lockers/{lk['id']}/network", json={"online": False}).json()["online"] is False
    r = client.post(f"/sim/lockers/{lk['id']}/compartments/{slot}/enter_code", json={"code": code})
    assert r.status_code == 200                                             # abre sin red
    assert c.get(f"/orders/{oid}").json()["status"] == "IN_LOCKER"          # el servidor aún no lo sabe
    assert client.get("/sim/lockers").json()["items"][0]["online"] is False
    client.post(f"/sim/lockers/{lk['id']}/network", json={"online": True})
    assert c.get(f"/orders/{oid}").json()["status"] == "PICKED_UP"
    assert client.post(f"/sim/lockers/{uuid.uuid4()}/network", json={"online": True}).status_code == 404


def test_agrupacion_avisos_y_tope(client, db, world):
    from app.db.models import Subscription
    m = world.make_user("marta")
    db.add(Subscription(user_id=m.id, market_id=world.market.id, categories=[]))
    db.commit()
    p = login(new_client(), "pepa@demo.test")
    body = {"stall_id": str(world.stall.id), "product_id": str(world.product.id), "qty_total": 5,
            "price_cents": 100, "pickup_from": "2026-10-16T12:00:00+02:00",
            "pickup_until": "2026-10-16T14:00:00+02:00", "consume_by": "TODAY"}
    for _ in range(3):
        assert p.post("/producer/offers", json=body).status_code == 201
    c = login(new_client(), "marta@demo.test")
    items = c.get("/notifications").json()["items"]
    assert len(items) == 1 and items[0]["payload"]["count"] == 3 and len(items[0]["payload"]["offers"]) == 3
    # tope diario: cada aviso fuera de ventana cuenta; el 6.º del día se descarta
    for _ in range(7):
        client.post("/demo/clock", json={"advance_seconds": 6 * 60})
        p.post("/producer/offers", json=body)
    n = len(c.get("/notifications").json()["items"])
    assert n == 5


def test_donaciones_y_opendata(client, db, world):
    from app.db.models import Charity
    db.add(Charity(name="Banco"))
    db.commit()
    world.make_offer(qty=3, until_min=10)
    client.post("/demo/clock", json={"advance_seconds": 11 * 60})
    m = login(new_client(), "gestion@demo.test")
    it = m.get("/admin/donations").json()["items"]
    assert len(it) == 1 and it[0]["qty"] == 3 and it[0]["charity_name"] == "Banco" and it[0]["product_name"] == "Tomates"
    assert login(new_client(), "pepa@demo.test").get("/admin/donations").status_code == 403
    assert client.get("/open-data/daily.csv").status_code == 503
    db.execute(text("CREATE SCHEMA marts"))
    db.execute(text("CREATE VIEW marts.open_data_daily AS SELECT 1 AS day, 7 AS n_orders UNION ALL SELECT 2, 1"))
    db.execute(text("CREATE VIEW marts.secret AS SELECT 1 AS x"))
    db.commit()
    try:
        r = client.get("/open-data/daily.csv")
        assert r.status_code == 200 and r.text.splitlines() == ["day,n_orders", "1,7"]   # celda <5 suprimida
        assert client.get("/open-data/secret.csv").status_code == 404
    finally:
        db.execute(text("DROP SCHEMA marts CASCADE"))
        db.commit()


def test_reloj_offset_en_tiempo_real_y_pausa(client):
    from app.reloj import DemoClock, parse_dt, set_clock
    set_clock(DemoClock(parse_dt("2026-10-16T12:00:00+02:00")))
    a = client.post("/demo/clock", json={"advance_seconds": 0}).json()
    assert a["paused"] is False
    time.sleep(1.1)
    b = client.post("/demo/clock", json={"advance_seconds": 0}).json()
    from datetime import datetime
    assert (datetime.fromisoformat(b["now"]) - datetime.fromisoformat(a["now"])).total_seconds() >= 1.0
    p = client.post("/demo/clock", json={"paused": True}).json()
    time.sleep(0.3)
    assert client.post("/demo/clock", json={"paused": True}).json()["now"] == p["now"]
    j = client.post("/demo/clock", json={"set": "2026-10-16T13:45:00+02:00", "paused": False}).json()
    assert j["now"].startswith("2026-10-16T13:45") and j["paused"] is False
    assert client.post("/demo/clock", json={}).status_code == 422


def test_tarda_solo_con_el_paso_del_tiempo(client, db, world):
    from app.reloj import DemoClock, get_clock, parse_dt, set_clock
    from app.planificador import run_due
    set_clock(DemoClock(parse_dt("2026-10-16T12:00:00+02:00")))   # corre solo
    world.make_user("marta")
    o = world.make_offer()
    c = login(new_client(), "marta@demo.test")
    oid = order(c, o.id).json()["id"]
    from app.config import get_settings
    get_settings().FAKE_PAYMENT_DELAY_SECONDS = 1
    assert c.post(f"/orders/{oid}/pay", json={"simulate": "delay"}).json()["status"] == "PENDING"
    time.sleep(1.3)
    run_due(db, get_clock().now())                                 # lo que haría el planificador
    assert c.get(f"/orders/{oid}").json()["status"] == "PAID"
