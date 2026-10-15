import uuid

from app.catalogo.service import haversine_m
from app.db.models import Market, Offer, OfferPolicy, Product, Stall


def test_haversine_conocida():
    # Plaça de Benimaclet -> Mercado Central de València: ~2,4 km
    d = haversine_m(39.4893, -0.3585, 39.4739, -0.3787)
    assert 2300 < d < 2600
    assert haversine_m(39.4893, -0.3585, 39.4893, -0.3585) == 0


def _far_offer(db, w):
    m = Market(id=uuid.uuid4(), name="Lejos", lat=39.4739, lng=-0.3787, opens_at=w.market.opens_at,
               closes_at=w.market.closes_at, offers_from=w.market.offers_from)
    db.add(m)
    db.flush()
    st = Stall(id=uuid.uuid4(), market_id=m.id, name="Puesto lejano", category="fruta")
    db.add(st)
    db.flush()
    pr = Product(id=uuid.uuid4(), stall_id=st.id, name="Naranjas", unit="kg", vat_rate=4, food_class="AMBIENT")
    db.add(pr)
    db.flush()
    o = Offer(id=uuid.uuid4(), stall_id=st.id, product_id=pr.id, qty_total=5, qty_available=5, price_cents=100,
              pickup_from=w.now, pickup_until=w.now.replace(hour=w.now.hour + 1), status="ACTIVE",
              consume_by="TODAY", created_at=w.now)
    db.add(o)
    db.flush()
    db.add(OfferPolicy(offer_id=o.id, profile="LIBRE", policy={"version": 1, "base": {"points_per_unit": 1, "max_units_per_user": 6},
                                                              "rules": [], "bounds": {"points_per_unit": [0, 6], "max_units_per_user": [1, 10]}}))
    db.commit()
    return o


def test_orden_por_cercania_y_distance_m(client, db, world):
    w = world
    w.market.lat, w.market.lng = 39.4627, -0.3724  # Ruzafa
    w.stall.lat, w.stall.lng = 39.4895, -0.3589    # puesto propio, cerca de Benimaclet
    db.commit()
    near = w.make_offer()
    far = _far_offer(db, w)
    items = client.get("/offers").json()["items"]  # sin lat/lng: DEMO_LOCATION
    assert [i["id"] for i in items] == [str(near.id), str(far.id)]
    assert all(isinstance(i["distance_m"], int) for i in items)
    assert items[0]["distance_m"] < 100 < items[1]["distance_m"]
    assert items[0]["stall"]["lat"] == 39.4895


def test_origen_del_cliente_cambia_el_orden(client, db, world):
    w = world
    w.market.lat, w.market.lng = 39.4627, -0.3724
    db.commit()
    near_ruz = w.make_offer()
    far = _far_offer(db, w)
    items = client.get("/offers", params={"lat": 39.4739, "lng": -0.3787}).json()["items"]
    assert items[0]["id"] == str(far.id) and items[0]["distance_m"] == 0
    assert items[1]["id"] == str(near_ruz.id)
