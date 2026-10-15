import threading
import uuid
from datetime import timedelta

import psycopg
import pytest
from sqlalchemy import text

from tests.test_compra import buy
from tests.test_flujo import login, new_client, order

BODY = lambda w: {"stall_id": str(w.stall.id), "product_id": str(w.product.id), "qty_total": 5,  # noqa: E731
                  "price_cents": 100, "pickup_from": "2026-10-16T12:00:00+02:00",
                  "pickup_until": "2026-10-16T14:00:00+02:00", "consume_by": "TODAY"}


def test_salvaguarda_demo_y_bind(monkeypatch):
    from app.__main__ import bind_host
    from app.config import get_settings
    from app.main import create_app
    monkeypatch.setenv("ALLOWED_HOSTS", "")
    get_settings.cache_clear()
    with pytest.raises(RuntimeError):
        create_app()
    monkeypatch.setenv("ALLOWED_HOSTS", "localhost,evil.example")
    get_settings.cache_clear()
    with pytest.raises(RuntimeError):
        create_app()
    monkeypatch.setenv("ALLOWED_HOSTS", "localhost")
    get_settings.cache_clear()
    assert bind_host() == "127.0.0.1"
    monkeypatch.setenv("BIND_HOST", "0.0.0.0")
    get_settings.cache_clear()
    assert bind_host() == "0.0.0.0"


def test_codigo_fuera_del_correo_y_borrado_al_cerrar(client, db, world, tmp_path, monkeypatch):
    from app.config import get_settings
    monkeypatch.setenv("NOTIFIERS", "inapp,email")
    monkeypatch.setenv("SMTP_PORT", "1")
    monkeypatch.setenv("MAIL_LOG_PATH", str(tmp_path / "mail.log"))
    get_settings.cache_clear()
    world.make_user("marta")
    o = world.make_offer()
    c = login(new_client(), "marta@demo.test")
    oid = order(c, o.id).json()["id"]
    c.post(f"/orders/{oid}/pay", json={})
    p = login(new_client(), "pepa@demo.test")
    p.post(f"/producer/orders/{oid}/accept")
    p.post(f"/producer/orders/{oid}/deposit")
    code = c.get(f"/orders/{oid}").json()["pickup_code"]
    ready = [n for n in c.get("/notifications").json()["items"] if n["kind"] == "ORDER_READY"][0]
    assert ready["payload"]["pickup_code"] == code           # solo en la bandeja y mientras IN_LOCKER
    import time
    time.sleep(0.5)
    log = (tmp_path / "mail.log").read_text() if (tmp_path / "mail.log").exists() else ""
    assert code not in log and f"/pedidos/{oid}" in log
    lk = client.get("/sim/lockers").json()["items"][0]
    slot = c.get(f"/orders/{oid}").json()["locker"]["slot"]
    client.post(f"/sim/lockers/{lk['id']}/compartments/{slot}/enter_code", json={"code": code})
    ready = [n for n in c.get("/notifications").json()["items"] if n["kind"] == "ORDER_READY"][0]
    assert "pickup_code" not in ready["payload"]


def test_transporte_cumple_la_interfaz():
    from app.taquillas.transport import InProcessSimulator, LockerTransport
    for m in ("close_door", "enter_code", "set_temperature", "set_online", "is_offline", "state", "states", "reset"):
        assert m in LockerTransport.__abstractmethods__
    assert not InProcessSimulator.__abstractmethods__


def test_mismo_usuario_20_hilos_no_supera_max_units(db, world):
    u = world.make_user("acaparador")
    o = world.make_offer(qty=30)                     # EQUILIBRADO: máx. 3 por persona
    res: list = []
    ts = [threading.Thread(target=buy, args=(u.id, o.id, 1, None, res)) for _ in range(20)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    oks = [r for r in res if r[0] == "ok"]
    assert len(oks) == 3, res
    assert all(r == ("err", "exceeds_max") for r in res if r[0] == "err")
    db.expire_all()
    assert db.execute(text("select coalesce(sum(qty),0) from order_items")).scalar() == 3


def test_capacidad_de_taquilla_bajo_concurrencia(db, world):
    o = world.make_offer(qty=30, profile="LIBRE")
    users = [world.make_user(f"c{i}") for i in range(12)]
    res: list = []
    ts = [threading.Thread(target=buy, args=(u.id, o.id, 1, None, res)) for u in users]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert len([r for r in res if r[0] == "ok"]) == 4          # 4 compartimentos
    assert all(r == ("err", "no_locker_capacity") for r in res if r[0] == "err")


def test_ciclo_de_oferta_borrador_publicar(client, db, world):
    p = login(new_client(), "pepa@demo.test")
    r = p.post("/producer/offers", json={**BODY(world), "publish": False})
    assert r.status_code == 201 and r.json()["status"] == "DRAFT"
    oid = r.json()["id"]
    assert p.post(f"/producer/offers/{oid}/withdraw").status_code == 409        # DRAFT no se retira
    assert p.patch(f"/producer/offers/{oid}", json={"qty_total": 8}).json()["status"] == "DRAFT"
    assert p.post(f"/producer/offers/{oid}/publish").json()["status"] == "ACTIVE"
    assert p.post(f"/producer/offers/{oid}/publish").status_code == 409
    assert p.delete(f"/producer/offers/{oid}").status_code == 409               # solo borradores
    d = p.post("/producer/offers", json={**BODY(world), "publish": False}).json()["id"]
    assert p.delete(f"/producer/offers/{d}").status_code == 204
    assert client.get(f"/offers/{d}").status_code == 404
    # offers_from 11:30: a las 11:00 no se puede publicar
    from app.reloj import get_clock
    get_clock().set(get_clock().now().replace(hour=11, minute=0))
    e = p.post("/producer/offers", json={**BODY(world), "publish": False}).json()["id"]
    r = p.post(f"/producer/offers/{e}/publish")
    assert r.status_code == 422 and r.json()["error"]["params"]["reason"] == "too_early_to_publish"


def test_patch_no_reabre_agotada(client, db, world):
    o = world.make_offer(qty=2)
    db.execute(text("update offers set qty_available=0, status='SOLD_OUT'"))
    db.commit()
    p = login(new_client(), "pepa@demo.test")
    assert p.patch(f"/producer/offers/{o.id}", json={"qty_total": 9}).status_code == 409


def test_pago_con_reserva_vencida(client, db, world):
    from app.reloj import get_clock
    world.make_user("marta")
    o = world.make_offer(qty=3)
    c = login(new_client(), "marta@demo.test")
    oid = order(c, o.id, 2).json()["id"]
    r = c.post(f"/orders/{oid}/pay", json={"simulate": "delay"})
    assert r.json()["status"] == "PENDING"
    get_clock().advance(11 * 60)                      # vence sin pasar el planificador
    from app.pagos.provider import get_provider
    ref = db.execute(text("select provider_ref from payments")).scalar()
    raw, sig = get_provider().make_webhook(ref, "PAID", 300)
    assert client.post("/payments/webhook/fake", content=raw, headers={"X-Signature": sig}).status_code == 200
    assert c.get(f"/orders/{oid}").json()["status"] == "EXPIRED_HOLD"
    assert db.execute(text("select status from payments")).scalar() == "REFUNDED"
    assert c.get("/me/points").json()["left"] == 20
    # pay_order con reserva vencida: 409 y se libera
    oid2 = order(c, o.id, 1, key="key-otra-0002").json()["id"]
    get_clock().advance(11 * 60)
    assert c.post(f"/orders/{oid2}/pay", json={}).status_code == 409
    assert c.get(f"/orders/{oid2}").json()["status"] == "EXPIRED_HOLD"


def test_decision_con_cantidad(client, db, world):
    world.make_user("marta")
    o = world.make_offer()
    c = login(new_client(), "marta@demo.test")
    d = c.get(f"/offers/{o.id}", params={"qty": 3}).json()["decision"]
    assert d["allowed"] and d["points_cost"] == 6
    d = c.get(f"/offers/{o.id}", params={"qty": 4}).json()["decision"]
    assert not d["allowed"] and d["reasons"] == ["errors.exceeds_max"]
    assert c.get(f"/offers/{o.id}", params={"qty": 0}).status_code == 422


def test_penalizacion_al_productor(client, db, world):
    world.make_user("marta")
    o = world.make_offer()
    c = login(new_client(), "marta@demo.test")
    oid = order(c, o.id).json()["id"]
    c.post(f"/orders/{oid}/pay", json={})
    p = login(new_client(), "pepa@demo.test")
    p.post(f"/producer/orders/{oid}/reject")
    assert float(db.execute(text("select reputation from users where email='pepa@demo.test'")).scalar()) == 0.95
    ev = db.execute(text("select payload from domain_events where event_type='producer.penalized'")).scalar()
    assert ev["cause"] == "producer_rejected" and ev["delta"] == -0.05
    # no deposita a tiempo
    oid = order(c, o.id, key="key-otra-0003").json()["id"]
    c.post(f"/orders/{oid}/pay", json={})
    p.post(f"/producer/orders/{oid}/accept")
    from app.reloj import get_clock
    get_clock().advance(21 * 60)
    from app.planificador import run_due
    run_due(db, get_clock().now())
    assert c.get(f"/orders/{oid}").json()["status"] == "REFUNDED"
    assert float(db.execute(text("select reputation from users where email='pepa@demo.test'")).scalar()) == 0.90


def test_cabeceras_sse_y_borrado_de_cuenta(client, db, world):
    r = client.get("/healthz")
    h = r.headers
    assert "default-src 'self'" in h["content-security-policy"] and h["x-content-type-options"] == "nosniff"
    assert h["referrer-policy"]
    from app.notificaciones.bus import hub
    import asyncio

    async def go():
        u = uuid.uuid4()
        subs = [hub.subscribe(u) for _ in range(5)]
        assert hub.count(u) == 5
        [hub.unsubscribe(s) for s in subs]
    asyncio.run(go())
    m = world.make_user("marta")
    c = login(new_client(), "marta@demo.test")
    o = world.make_offer()
    oid = order(c, o.id).json()["id"]
    assert c.delete("/me").status_code == 409                    # pedido en curso
    c.post(f"/orders/{oid}/pay", json={"simulate": "failure"})
    from app.reloj import get_clock
    get_clock().advance(11 * 60)
    from app.planificador import run_due
    run_due(db, get_clock().now())
    assert c.delete("/me").status_code == 204
    row = db.execute(text("select email, display_name, status, password_hash from users where id=:i"),
                     {"i": m.id}).one()
    assert row[0].endswith("@anon.invalid") and row[2] == "DELETED" and row[3] is None
    assert db.execute(text("select count(*) from user_identities where user_id=:i"), {"i": m.id}).scalar() == 0
    assert c.get("/me").status_code == 401


def test_proveedor_de_envios_simulado():
    from datetime import datetime
    from app.envios.provider import DeliveryProvider, FakeDeliveryProvider
    d: DeliveryProvider = FakeDeliveryProvider()
    q = d.quote(uuid.uuid4(), "calle", datetime(2026, 10, 16, 13, 0), True)
    assert q.cold_chain_ok
    ref = d.create(uuid.uuid4(), uuid.uuid4(), "calle")
    d.cancel(ref)
    assert d.status(ref) == "CANCELLED"


def test_analitica_refresco_y_calidad(client, db, world):
    from app.config import get_settings
    from app.reloj import get_clock
    m = login(new_client(), "gestion@demo.test")
    assert m.get("/admin/calidad").status_code == 503             # capas no instaladas
    url = get_settings().DATABASE_URL.replace("postgresql+psycopg://", "postgresql://")
    import importlib.util
    from pathlib import Path
    path = Path(__file__).resolve().parents[3] / "data" / "sql" / "apply.py"
    spec = importlib.util.spec_from_file_location("apply_t", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    try:
        with psycopg.connect(url) as conn:
            mod.apply_layers(conn, get_clock().now())
        world.make_user("marta")
        c = login(new_client(), "marta@demo.test")
        order(c, world.make_offer().id)
        client.post("/demo/clock", json={"advance_seconds": 120})
        now = get_clock().now()
        with psycopg.connect(url) as conn:
            clock_now = conn.execute("SELECT value FROM core.meta WHERE key='clock_now'").fetchone()[0]
            held = conn.execute("SELECT count(*) FROM raw.events WHERE event_type='order.held'").fetchone()[0]
        assert clock_now.startswith(now.isoformat()[:16]) and held == 1
        r = m.get("/admin/calidad")
        assert r.status_code == 200 and set(r.json()) == {"ok", "failures", "checked_at"}
    finally:
        with psycopg.connect(url, autocommit=True) as conn:
            for sch in ("open_data", "marts", "core", "staging", "raw"):
                conn.execute(f"DROP SCHEMA IF EXISTS {sch} CASCADE")
        from app.eventos import analytics
        analytics.reset_state()


def test_listado_de_ofertas_del_productor(client, db, world):
    from app.db.models import Stall, User
    from app.identidad.security import hash_password
    p = login(new_client(), "pepa@demo.test")
    draft = p.post("/producer/offers", json={**BODY(world), "publish": False}).json()["id"]
    act = p.post("/producer/offers", json=BODY(world)).json()["id"]
    items = p.get("/producer/offers").json()["items"]
    assert {i["id"] for i in items} == {draft, act} and all("status" in i for i in items)
    assert [i["id"] for i in p.get("/producer/offers", params={"status": "DRAFT"}).json()["items"]] == [draft]
    assert p.get("/producer/offers", params={"status": "X"}).status_code == 422
    otro = User(id=uuid.uuid4(), email="otro@demo.test", password_hash=hash_password("secret123"),
                display_name="Otro", role="PRODUCER", status="ACTIVE", created_at=world.now)
    db.add(otro)
    db.flush()
    db.add(Stall(id=uuid.uuid4(), market_id=world.market.id, name="Otro puesto", category="fruta",
                 owner_user_id=otro.id))
    db.commit()
    assert login(new_client(), "otro@demo.test").get("/producer/offers").json()["items"] == []
    world.make_user("marta")
    assert login(new_client(), "marta@demo.test").get("/producer/offers").status_code == 403
    assert client.get("/producer/offers").status_code == 401
