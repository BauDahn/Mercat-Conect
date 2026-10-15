from sqlalchemy import text

from .test_flujo import login, new_client


def test_clear_offers_deja_lista_vacia_y_publica_despues(client, db, world):
    p = login(new_client(), "pepa@demo.test")
    body = {"stall_id": str(world.stall.id), "product_id": str(world.product.id), "qty_total": 5,
            "price_cents": 100, "pickup_from": "2026-10-16T12:00:00+02:00",
            "pickup_until": "2026-10-16T14:00:00+02:00", "consume_by": "TODAY"}
    assert p.post("/producer/offers", json=body).status_code == 201
    assert len(client.get("/offers").json()["items"]) >= 1
    assert client.post("/demo/clear-offers").status_code == 204
    assert client.get("/offers").json()["items"] == []
    assert db.execute(text("select count(*) from domain_events where event_type='offer.withdrawn'")).scalar() >= 1
    assert db.execute(text("select count(*) from stalls")).scalar() >= 1  # puestos intactos
    assert p.post("/producer/offers", json=body).status_code == 201
    assert len(client.get("/offers").json()["items"]) == 1
