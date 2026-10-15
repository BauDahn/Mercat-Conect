import json
import re
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import create_app


def login(c: TestClient, email):
    r = c.post("/auth/login", json={"email": email, "password": "secret123"})
    assert r.status_code == 200, r.text
    return c


def new_client():
    return TestClient(create_app())


def order(c, offer_id, qty=1, key="key-00000001"):
    return c.post("/orders", json={"items": [{"offer_id": str(offer_id), "qty": qty}]}, headers={"Idempotency-Key": key})


def test_alta_edad_y_persona_unica(client):
    r = client.post("/auth/register", json={"email": "Nuevo@Demo.test", "password": "secret123", "display_name": "N"})
    assert r.status_code == 201 and r.json()["status"] == "PENDING" and not r.json()["age_verified"]
    assert "mc_session" in r.cookies and "httponly" in r.headers["set-cookie"].lower()
    assert client.post("/auth/register", json={"email": "nuevo@demo.test", "password": "secret123",
                                               "display_name": "N"}).json()["error"]["code"] == "email_taken"
    st = client.get("/identity/age/start").json()
    # menor: bloqueo
    r = client.get("/identity/age/callback", params={"state": st["state"], "token": "12345678Z", "kind": "minor"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "age_not_verified"
    r = client.get("/identity/age/callback", params={"state": st["state"], "token": "12345678Z", "kind": "adult"})
    assert r.status_code == 200 and r.json()["status"] == "ACTIVE" and r.json()["age_verified"]
    # segunda cuenta con el mismo DNI
    c2 = new_client()
    c2.post("/auth/register", json={"email": "otro@demo.test", "password": "secret123", "display_name": "O"})
    st2 = c2.get("/identity/age/start").json()
    r = c2.get("/identity/age/callback", params={"state": st2["state"], "token": "12345678z", "kind": "adult"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "person_already_registered"
    # estado de otro usuario no vale
    r = c2.get("/identity/age/callback", params={"state": st["state"], "token": "99"})
    assert r.status_code == 401


def test_errores_con_formato_y_login(client):
    r = client.post("/auth/login", json={"email": "x@demo.test", "password": "mal-mal-mal"})
    assert r.status_code == 401 and set(r.json()["error"]) == {"code", "message_key", "params"}
    assert client.post("/orders", json={"items": []}).status_code == 401
    assert client.get("/nope").json()["error"]["code"] == "not_found"
    assert client.post("/auth/register", json={"email": "bad", "password": "1", "display_name": "x"}).status_code == 422


def test_recorrido_completo(client, db, world):
    marta = world.make_user("marta")
    o = world.make_offer(qty=5)
    c = login(new_client(), "marta@demo.test")
    d = c.get(f"/offers/{o.id}").json()
    assert d["decision"]["allowed"] and d["decision"]["points_cost"] == 2
    assert client.get(f"/offers/{o.id}").json()["decision"] is None
    assert len(client.get("/offers").json()["items"]) == 1
    assert order(c, o.id, 1, "key-k1-0001").status_code == 201
    r = order(c, o.id, 1, "key-k1-0001")
    assert r.status_code == 200
    ordr = r.json()
    assert ordr["status"] == "HELD" and ordr["pickup_code"] is None
    assert c.get("/me/points").json()["left"] == 18
    r = c.post("/orders", json={"items": [{"offer_id": str(o.id), "qty": 1}]})
    assert r.status_code == 400 and r.json()["error"]["code"] == "idempotency_key_required"
    # pago con fallo y reintento
    r = c.post(f"/orders/{ordr['id']}/pay", json={"simulate": "failure"})
    assert r.json()["status"] == "FAILED"
    r = c.post(f"/orders/{ordr['id']}/pay", json={"simulate": "success"})
    assert r.json()["status"] == "PAID"
    assert c.get(f"/orders/{ordr['id']}").json()["status"] == "PAID"
    # productor
    p = login(new_client(), "pepa@demo.test")
    assert [x["id"] for x in p.get("/producer/orders").json()["items"]] == [ordr["id"]]
    assert c.post(f"/producer/orders/{ordr['id']}/accept").status_code == 403  # vecino
    acc = p.post(f"/producer/orders/{ordr['id']}/accept").json()
    assert acc["status"] == "PREPARING" and acc["locker"]["slot"] >= 1
    assert p.post(f"/producer/orders/{ordr['id']}/accept").status_code == 409
    dep = p.post(f"/producer/orders/{ordr['id']}/deposit")
    assert dep.status_code == 200 and dep.json()["status"] == "IN_LOCKER"
    assert dep.json()["pickup_code"] is None                       # el productor no ve el código
    mine = c.get(f"/orders/{ordr['id']}").json()
    code = mine["pickup_code"]
    assert re.fullmatch(r"\d{6}", code)
    assert db.execute(text("select code_hash from deposits")).scalar().hex() != code
    # taquilla virtual
    lk = client.get("/sim/lockers").json()["items"][0]
    slot = mine["locker"]["slot"]
    base = f"/sim/lockers/{lk['id']}/compartments/{slot}"
    assert client.post(f"{base}/enter_code", json={"code": "000000" if code != "000000" else "111111"}).status_code == 403
    r = client.post(f"{base}/enter_code", json={"code": code})
    assert r.status_code == 200 and r.json()["door"] == "OPEN"
    assert c.get(f"/orders/{ordr['id']}").json()["status"] == "PICKED_UP"
    assert client.post(f"{base}/enter_code", json={"code": code}).status_code == 409   # ya retirado
    assert p.get("/producer/payouts").json()["items"][0]["amount_cents"] == 150
    types = [r[0] for r in db.execute(text("select event_type from domain_events order by id"))]
    for t in ("order.held", "points.spent", "order.paid", "order.deposited", "order.picked_up", "notification.sent"):
        assert t in types
    assert len(c.get("/notifications").json()["items"]) >= 1


def test_deposito_via_simulador_y_no_show(client, db, world):
    from app.reloj import get_clock
    world.make_user("marta")
    o = world.make_offer()
    c = login(new_client(), "marta@demo.test")
    oid = order(c, o.id).json()["id"]
    c.post(f"/orders/{oid}/pay", json={})
    p = login(new_client(), "pepa@demo.test")
    slot = p.post(f"/producer/orders/{oid}/accept").json()["locker"]["slot"]
    lk = client.get("/sim/lockers").json()["items"][0]
    base = f"/sim/lockers/{lk['id']}/compartments/{slot}"
    assert client.post(f"{base}/close_door").status_code == 409
    assert client.post(f"{base}/open_door").status_code == 200
    r = client.post(f"{base}/close_door")
    assert r.json()["status"] == "OCCUPIED"
    assert c.get(f"/orders/{oid}").json()["status"] == "IN_LOCKER"
    r = client.post("/demo/clock", json={"advance_seconds": 3 * 3600})
    assert r.status_code == 200
    got = c.get(f"/orders/{oid}").json()
    assert got["status"] == "NO_SHOW" and c.get("/me/points").json()["left"] == 18   # sin devolución
    assert float(db.execute(text("select reputation from users where email='marta@demo.test'")).scalar()) == 0.9
    assert db.execute(text("select count(*) from donations")).scalar() >= 0
    assert db.execute(text("select status from compartments where slot=:s"), {"s": slot}).scalar() == "FREE"


def test_caducidad_reserva_y_pago_tardio(client, db, world, monkeypatch):
    from app.config import get_settings
    monkeypatch.setenv("FAKE_PAYMENT_DELAY_SECONDS", "900")
    get_settings.cache_clear()
    world.make_user("marta")
    o = world.make_offer(qty=3)
    c = login(new_client(), "marta@demo.test")
    oid = order(c, o.id, 2).json()["id"]
    r = c.post(f"/orders/{oid}/pay", json={"simulate": "delay"})
    assert r.json()["status"] == "PENDING"
    client.post("/demo/clock", json={"advance_seconds": 11 * 60})   # caduca antes de pagar
    client.post("/demo/clock", json={"advance_seconds": 5 * 60})    # llega el webhook tardío
    got = c.get(f"/orders/{oid}").json()
    assert got["status"] == "EXPIRED_HOLD"
    assert c.get("/me/points").json()["left"] == 20
    assert db.execute(text("select qty_available from offers")).scalar() == 3
    assert db.execute(text("select status from payments")).scalar() == "REFUNDED"   # webhook tardío reembolsado


def test_alarma_temperatura(client, db, world):
    world.make_user("marta")
    o = world.make_offer()
    c = login(new_client(), "marta@demo.test")
    oid = order(c, o.id).json()["id"]
    c.post(f"/orders/{oid}/pay", json={})
    p = login(new_client(), "pepa@demo.test")
    slot = p.post(f"/producer/orders/{oid}/accept").json()["locker"]["slot"]
    p.post(f"/producer/orders/{oid}/deposit")
    lk = client.get("/sim/lockers").json()["items"][0]
    base = f"/sim/lockers/{lk['id']}/compartments/{slot}"
    assert client.post(f"{base}/set_temperature", json={"celsius": 9}).status_code == 200
    assert c.get(f"/orders/{oid}").json()["status"] == "IN_LOCKER"        # aún no pasaron 15 min
    client.post("/demo/clock", json={"advance_seconds": 16 * 60})
    assert c.get(f"/orders/{oid}").json()["status"] == "REFUNDED"
    assert c.get("/me/points").json()["left"] == 20
    assert db.execute(text("select status from compartments where slot=:s"), {"s": slot}).scalar() == "OUT_OF_SERVICE"
    assert db.execute(text("select count(*) from domain_events where event_type='locker.alarm'")).scalar() == 1
    assert db.execute(text("select status from payments")).scalar() == "REFUNDED"


def test_webhook_firma_y_cierre_con_donacion(client, db, world):
    from app.db.models import Charity
    db.add(Charity(name="Banco de alimentos"))
    db.commit()
    assert client.post("/payments/webhook/fake", json={"provider_ref": "x", "status": "PAID"},
                       headers={"X-Signature": "bad"}).status_code == 401
    world.make_user("marta")
    o = world.make_offer(qty=4, until_min=30)
    c = login(new_client(), "marta@demo.test")
    order(c, o.id)
    client.post("/demo/clock", json={"advance_seconds": 11 * 60})     # caduca la reserva y vuelve el stock
    client.post("/demo/clock", json={"advance_seconds": 30 * 60})     # cierra la oferta
    row = db.execute(text("select status from offers")).scalar()
    assert row == "DONATED"
    assert db.execute(text("select qty from donations")).scalar() == 4
    assert db.execute(text("select count(*) from domain_events where event_type='donation.completed'")).scalar() == 1


def test_publicar_ofertas_y_guardrails(client, db, world):
    p = login(new_client(), "pepa@demo.test")
    body = {"stall_id": str(world.stall.id), "product_id": str(world.product.id), "qty_total": 5,
            "price_cents": 100, "pickup_from": "2026-10-16T12:00:00+02:00", "pickup_until": "2026-10-16T14:00:00+02:00",
            "consume_by": "TODAY"}
    r = p.post("/producer/offers", json=body)
    assert r.status_code == 201 and r.json()["status"] == "ACTIVE" and r.json()["policy_profile"] == "EQUILIBRADO"
    oid = r.json()["id"]
    assert p.patch(f"/producer/offers/{oid}", json={"price_cents": 120}).json()["price_cents"] == 120
    m = login(new_client(), "gestion@demo.test")
    assert m.put("/admin/guardrails", json={"max_price_ratio": 1.0}).json()["max_price_ratio"] == 1.0
    assert p.post("/producer/offers", json={**body, "price_cents": 999}).status_code == 422
    assert p.post(f"/producer/offers/{oid}/withdraw").json()["status"] == "WITHDRAWN"
    assert p.post(f"/producer/offers/{oid}/withdraw").status_code == 409
    assert client.post("/admin/stalls", json={}).status_code == 401
    assert m.get("/admin/metrics").status_code == 200
    assert p.get("/admin/metrics").status_code == 403
    assert client.get("/open-data/impact.csv").status_code == 503


def test_demo_gating_y_simulacion(client, db, world, monkeypatch):
    for i in range(3):
        world.make_offer(qty=20)
    r = client.post("/demo/simulate", json={"buyers": 15, "scenario": "peak"})
    assert r.status_code == 200 and r.json()["attempted"] == 15 and r.json()["held"] > 0
    from app.config import get_settings
    monkeypatch.setenv("DEMO_MODE", "false")
    get_settings.cache_clear()
    try:
        prod = TestClient(create_app())
        assert prod.post("/demo/clock", json={"advance_seconds": 1}).status_code == 404
        assert prod.get("/sim/lockers").status_code == 404
        monkeypatch.setenv("DEMO_MODE", "true")
        monkeypatch.setenv("ALLOWED_HOSTS", "midominio.es")
        get_settings.cache_clear()
        try:
            create_app()
            raise AssertionError("debía negarse a arrancar")
        except RuntimeError:
            pass
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()


def test_email_sin_smtp_escribe_log(tmp_path, monkeypatch):
    from app.config import get_settings
    from app.notificaciones.notifiers import deliver_email
    monkeypatch.setenv("MAIL_LOG_PATH", str(tmp_path / "mail.log"))
    monkeypatch.setenv("SMTP_PORT", "1")
    get_settings.cache_clear()
    assert deliver_email("a@demo.test", "Hola", "cuerpo", "/pedidos/1") is False
    assert "a@demo.test" in (tmp_path / "mail.log").read_text()
    get_settings.cache_clear()


def test_sse_hub():
    import asyncio
    import uuid
    from app.notificaciones.bus import hub

    async def go():
        uid = uuid.uuid4()
        sub = hub.subscribe(uid)
        hub.publish("offer.updated", {"x": 1})
        hub.publish("order.updated", {"y": 2}, [uuid.uuid4()])   # otro usuario: no llega
        ev = await asyncio.wait_for(sub.queue.get(), 1)
        assert ev[0] == "offer.updated" and json.loads(ev[1]) == {"x": 1}
        assert sub.queue.empty()
        hub.unsubscribe(sub)
    asyncio.run(go())


def test_ninguna_logica_lee_la_hora_del_sistema():
    """Falla si hay llamadas directas a la hora del sistema fuera de reloj/__init__.py."""
    root = Path(__file__).resolve().parents[1] / "app"
    pat = re.compile(r"datetime\.(now|utcnow|today)\(|time\.(time|monotonic)\(|date\.today\(|func\.now|"
                     r"CURRENT_(TIMESTAMP|DATE)|(?<![.\w])now\(\)", re.I)
    bad = []
    for f in root.rglob("*.py"):
        if f.relative_to(root).as_posix() == "reloj/__init__.py":
            continue
        for n, line in enumerate(f.read_text().splitlines(), 1):
            if pat.search(line) and "clock-ok" not in line:
                bad.append(f"{f.relative_to(root)}:{n}: {line.strip()}")
    assert not bad, bad
