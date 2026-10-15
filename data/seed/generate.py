"""Generador determinista de datos de demo (seccion 17.4). Sin acceso a base de datos.

Todo sale de `random.Random(seed)` y de `clock_start` (DEMO_CLOCK_START): nunca se lee la hora
del sistema. Mismo seed + mismo reloj + misma clave => exactamente las mismas filas.
Los nombres de mercados son reales; puestos, productos, personas y ventas son ficticios.
"""
from __future__ import annotations

import hashlib
import hmac
import math
import random
import uuid
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Madrid")
UTC = timezone.utc
NS = uuid.UUID("6d657263-6174-2d63-6f6e-656374000000")
ALLOWANCE = 20
HISTORY_DAYS = 28
DEMO_PASSWORD = "demo1234"

# Columnas exactas de apps/api/app/db/models.py (las que se rellenan; los id autonumericos los pone la BD).
COLUMNS: dict[str, list[str]] = {
    "markets": ["id", "name", "lat", "lng", "opens_at", "closes_at", "offers_from", "tz"],
    "stalls": ["id", "market_id", "name", "category", "owner_user_id", "verified_at", "payout_account_ref"],
    "users": ["id", "email", "password_hash", "display_name", "role", "lang", "reputation", "status",
              "telegram_chat_id", "created_at"],
    "user_identities": ["user_id", "person_hash", "age_verified_at", "age_method", "provider_ref"],
    "products": ["id", "stall_id", "name", "unit", "unit_weight_g", "vat_rate", "allergens", "food_class",
                 "usual_price_cents", "photo_path"],
    "offers": ["id", "stall_id", "product_id", "qty_total", "qty_available", "price_cents",
               "reference_price_cents", "pickup_from", "pickup_until", "status", "consume_by", "created_at"],
    "offer_policies": ["offer_id", "profile", "policy", "version"],
    "points_week": ["user_id", "week_key", "allowance", "spent"],
    "points_ledger": ["user_id", "week_key", "delta", "reason", "order_id", "created_at"],
    "orders": ["id", "user_id", "stall_id", "status", "total_cents", "points_cost", "rules_applied",
               "idempotency_key", "hold_expires_at", "pickup_until", "created_at"],
    "order_items": ["order_id", "offer_id", "qty", "unit_cents"],
    "payments": ["id", "order_id", "provider", "provider_ref", "amount_cents", "status", "created_at"],
    "lockers": ["id", "market_id", "device_id", "last_seen", "firmware"],
    "compartments": ["id", "locker_id", "slot", "size", "zone", "status"],
    "deposits": ["id", "order_id", "compartment_id", "code_hash", "valid_from", "valid_until",
                 "deposited_at", "picked_up_at"],
    "subscriptions": ["user_id", "market_id", "categories", "quiet_from", "quiet_to"],
    "notifications": ["user_id", "kind", "payload", "read_at", "created_at"],
    "payouts": ["id", "stall_id", "period_from", "period_to", "gross_cents", "commission_cents",
                "amount_cents", "status", "paid_at"],
    "charities": ["id", "name", "contact_email", "active"],
    "donations": ["id", "offer_id", "charity_id", "qty", "status", "created_at", "completed_at"],
    "domain_events": ["occurred_at", "event_type", "aggregate_id", "payload", "published_at"],
}
# Orden de carga que respeta las claves foraneas.
LOAD_ORDER = ["markets", "users", "stalls", "user_identities", "products", "offers", "offer_policies",
              "charities", "lockers", "compartments", "orders", "order_items", "payments", "deposits",
              "points_week", "points_ledger", "donations", "payouts", "subscriptions", "notifications",
              "domain_events"]
JSONB_COLUMNS = {("offer_policies", "policy"), ("orders", "rules_applied"), ("notifications", "payload"),
                 ("domain_events", "payload")}

MARKETS = [  # nombre real, lat, lng, abre, cierra, ofertas desde
    ("Mercado de Ruzafa", 39.4627, -0.3724, time(7, 0), time(15, 0), time(11, 30)),
    ("Mercado de Colón", 39.4672, -0.3523, time(7, 30), time(15, 0), time(11, 30)),
    ("Mercado Central", 39.4739, -0.3787, time(7, 0), time(15, 0), time(11, 30)),
]
LOCKERS = [(0, "LOCKER-RUZ-01"), (0, "LOCKER-RUZ-02"), (1, "LOCKER-COL-01"), (2, "LOCKER-CEN-01")]
STALLS = [  # (mercado, nombre ficticio, categoria, mitad del catalogo)
    (0, "Frutería La Huerta de Pepa", "fruta", 0), (0, "Pescados Mar de Ruzafa", "pescado", 0),
    (0, "Forn del Barri", "panaderia", 0), (0, "Carnes Ca Tonet", "carne", 0),
    (1, "Verduras Hermanos Soler", "verdura", None), (1, "Selectos Mestre", "charcuteria", None),
    (1, "Pescadería Las Gaviotas", "pescado", 1), (1, "Horno San Vicente", "panaderia", 1),
    (2, "Fruta Els Tarongers", "fruta", 1), (2, "Carnicería Casa Paco", "carne", 1),
    (2, "Despensa El Cabanyal", "despensa", None), (2, "Lácteos La Alquería", "lacteos", None),
]
R, A = "REFRIGERATED", "AMBIENT"
CATALOG = {  # nombre, unidad, peso unitario (g), IVA %, alergenos, clase de frio, precio habitual (cent)
    "fruta": [("Tomates de la huerta", "bolsa 1 kg", 1000, 4, [], A, 280), ("Naranjas de Valencia", "bolsa 2 kg", 2000, 4, [], A, 320),
              ("Fresas", "bandeja 500 g", 500, 4, [], R, 350), ("Plátanos", "manojo", 900, 4, [], A, 230),
              ("Uvas", "bandeja 500 g", 500, 4, [], A, 290), ("Kakis", "bandeja 1 kg", 1000, 4, [], A, 310),
              ("Mandarinas", "bolsa 1 kg", 1000, 4, [], A, 260), ("Granadas", "bolsa 1 kg", 1000, 4, [], A, 330)],
    "verdura": [("Lechuga", "unidad", 350, 4, [], A, 130), ("Pimientos rojos", "bandeja 500 g", 500, 4, [], A, 380),
                ("Calabacines", "bolsa 1 kg", 1000, 4, [], A, 240), ("Espinacas", "bolsa 300 g", 300, 4, [], R, 210),
                ("Cebollas", "malla 1 kg", 1000, 4, [], A, 150), ("Alcachofas", "bolsa 500 g", 500, 4, [], A, 360)],
    "pescado": [("Merluza", "bandeja 400 g", 400, 10, ["pescado"], R, 780), ("Gambas", "bandeja 300 g", 300, 10, ["crustaceos"], R, 1250),
                ("Sardinas", "bandeja 500 g", 500, 10, ["pescado"], R, 520), ("Mejillones", "malla 1 kg", 1000, 10, ["moluscos"], R, 410),
                ("Dorada", "unidad 450 g", 450, 10, ["pescado"], R, 690)],
    "carne": [("Pollo troceado", "bandeja 800 g", 800, 10, [], R, 640), ("Longaniza", "bandeja 400 g", 400, 10, ["sulfitos"], R, 560),
              ("Ternera picada", "bandeja 500 g", 500, 10, [], R, 720), ("Costillas de cerdo", "bandeja 700 g", 700, 10, [], R, 590)],
    "panaderia": [("Barra de pan", "unidad 250 g", 250, 4, ["gluten"], A, 120), ("Hogaza de espelta", "unidad 600 g", 600, 4, ["gluten"], A, 340),
                  ("Bollería surtida", "bolsa 6 uds", 360, 10, ["gluten", "huevo", "lacteos"], A, 450),
                  ("Coca de llanda", "unidad 400 g", 400, 10, ["gluten", "huevo"], A, 380)],
    "charcuteria": [("Jamón serrano loncheado", "sobre 150 g", 150, 10, [], R, 520), ("Queso curado", "cuña 250 g", 250, 10, ["lacteos"], R, 690),
                    ("Sobrasada", "unidad 300 g", 300, 10, [], R, 430), ("Fuet", "unidad 150 g", 150, 10, [], R, 310)],
    "lacteos": [("Leche fresca", "botella 1 L", 1000, 4, ["lacteos"], R, 140), ("Yogur artesano", "pack 4", 500, 10, ["lacteos"], R, 280),
                ("Requesón", "tarrina 250 g", 250, 4, ["lacteos"], R, 240), ("Mató", "unidad 300 g", 300, 4, ["lacteos"], R, 330)],
    "despensa": [("Garbanzos cocidos", "bote 400 g", 400, 4, [], A, 160), ("Arroz bomba", "paquete 1 kg", 1000, 4, [], A, 390),
                 ("Almendras", "bolsa 250 g", 250, 10, ["frutos_secos"], A, 420), ("Pasas", "bolsa 300 g", 300, 10, [], A, 270),
                 ("Lentejas", "paquete 500 g", 500, 4, [], A, 210)],
}
CHARITIES = [("Cocina Solidaria Ruzafa", "contacto@cocina-solidaria.demo.test"),
             ("Despensa Vecinal Colón", "contacto@despensa-vecinal.demo.test")]
DEMO_USERS = [  # clave, rol, estado, reputacion, idioma, nombre
    ("marta", "NEIGHBOR", "ACTIVE", 1.00, "es", "Marta Demo"), ("luis", "NEIGHBOR", "ACTIVE", 1.00, "va", "Luis Demo"),
    ("ana", "NEIGHBOR", "ACTIVE", 0.45, "es", "Ana Demo"), ("nuevo", "NEIGHBOR", "PENDING", 1.00, "es", "Nuevo Demo"),
    ("pepa", "PRODUCER", "ACTIVE", 1.00, "es", "Pepa Demo"), ("gestion", "MANAGER", "ACTIVE", 1.00, "es", "Gestión Demo"),
]
FIRST = ["Carmen", "Josep", "Lucía", "Vicent", "Elena", "Pau", "Marina", "Àlex", "Rosa", "Toni", "Inés", "Joan",
         "Paula", "Enric", "Nuria", "Hugo", "Amparo", "Rafa", "Clara", "Biel"]
LAST = ["Ferrer", "Soler", "Mora", "Gil", "Pons", "Navarro", "Císcar", "Climent", "Bosch", "Furió", "Roca", "Sanchis"]
DOW_DEMAND = {0: 0.75, 1: 0.85, 2: 0.9, 3: 1.0, 4: 1.3, 5: 1.15, 6: 0.5}
OPEN_STATUSES = ("HELD", "PAID", "PREPARING", "IN_LOCKER", "PICKED_UP", "NO_SHOW")


def utc(dt: datetime) -> datetime:
    return dt.astimezone(UTC)


def iso(dt: datetime | None) -> str | None:
    return None if dt is None else utc(dt).isoformat()


def week_key(dt: datetime) -> str:
    iy, iw, _ = dt.astimezone(TZ).date().isocalendar()
    return f"{iy}-W{iw:02d}"


def policy_for(profile: str) -> dict:
    pico = {"id": "pico-de-demanda", "when": {"demand_velocity_gte": 0.5},
            "then": {"points_per_unit_mult": 2.0, "max_units_per_user": 2}}
    cierre = {"id": "cierre-con-sobrante", "when": {"minutes_to_close_lte": 30, "stock_ratio_gte": 0.4},
              "then": {"points_per_unit_mult": 0.5, "max_units_per_user": 6}}
    fiables = {"id": "primera-hora-solo-fiables", "when": {"time_between": ["12:30", "13:00"]},
               "then": {"min_reputation": 0.6}}
    if profile == "LIBRE":
        return {"version": 1, "base": {"points_per_unit": 1, "max_units_per_user": 6},
                "rules": [{"id": "agotamiento-rapido", "when": {"demand_velocity_gte": 0.8},
                           "then": {"points_per_unit_mult": 2.0}}],
                "bounds": {"points_per_unit": [0, 6], "max_units_per_user": [1, 10]}}
    if profile == "ESTRICTO":
        return {"version": 1, "base": {"points_per_unit": 3, "max_units_per_user": 2},
                "rules": [fiables, cierre],
                "bounds": {"points_per_unit": [1, 6], "max_units_per_user": [1, 4]}}
    return {"version": 1, "base": {"points_per_unit": 2, "max_units_per_user": 3},
            "rules": [pico, cierre, fiables],
            "bounds": {"points_per_unit": [0, 6], "max_units_per_user": [1, 10]}}


class Dataset:
    def __init__(self) -> None:
        self.tables: dict[str, list[tuple]] = {t: [] for t in COLUMNS}
        self.demo_users: dict[str, uuid.UUID] = {}
        self.stats: dict[str, int] = {}


class Builder:
    def __init__(self, seed: int, clock_start: datetime, person_hash_key: str, hash_password) -> None:
        if clock_start.tzinfo is None:
            clock_start = clock_start.replace(tzinfo=TZ)
        self.seed = seed
        self.T = utc(clock_start)
        self.today = self.T.astimezone(TZ).date()
        self.cur_week = week_key(self.T)
        self.key = person_hash_key.encode()
        self.hash_password = hash_password
        self.rng = random.Random(seed)
        self.ds = Dataset()
        self._n: dict[str, int] = {}
        self.events: list[tuple] = []
        self.spent: dict[tuple, int] = {}
        self.offers: list[dict] = []
        self.busy: dict[uuid.UUID, str] = {}
        self.completed: list[tuple] = []  # (stall_id, paid_at, total_cents) para liquidaciones
        self.pseudo_cache: dict[str, str] = {}

    # ---------- utilidades ----------
    def uid(self, kind: str) -> uuid.UUID:
        self._n[kind] = self._n.get(kind, 0) + 1
        return uuid.uuid5(NS, f"{self.seed}/{kind}/{self._n[kind]}")

    def add(self, table: str, **kw) -> None:
        cols = COLUMNS[table]
        assert set(kw) <= set(cols), (table, set(kw) - set(cols))
        self.ds.tables[table].append(tuple(kw.get(c) for c in cols))

    def ev(self, at: datetime, etype: str, agg, payload: dict) -> None:
        assert at <= self.T, (etype, at, self.T)
        self.events.append((at, len(self.events), etype, agg, payload))

    def pseudo(self, ident: str) -> str:
        if ident not in self.pseudo_cache:
            self.pseudo_cache[ident] = hmac.new(self.key, b"pseudo:" + ident.encode(), hashlib.sha256).hexdigest()[:16]
        return self.pseudo_cache[ident]

    def at(self, d: date, h: int, m: int = 0, s: int = 0) -> datetime:
        return utc(datetime(d.year, d.month, d.day, h, m, s, tzinfo=TZ))

    def mins(self, a: float, b: float) -> timedelta:
        return timedelta(seconds=int(self.rng.uniform(a, b) * 60))

    # ---------- datos de referencia ----------
    def reference(self) -> None:
        rng = self.rng
        base = self.T - timedelta(days=60)
        self.markets = []
        for name, lat, lng, op, cl, off in MARKETS:
            mid = self.uid("market")
            self.markets.append({"id": mid, "name": name})
            self.add("markets", id=mid, name=name, lat=lat, lng=lng, opens_at=op, closes_at=cl, offers_from=off, tz="Europe/Madrid")

        # usuarios (los demo primero, despues vecinos sinteticos)
        self.users: dict[str, dict] = {}
        for i, (k, role, status, rep, lang, name) in enumerate(DEMO_USERS):
            self._user(k, f"{k}@demo.test", name, role, status, rep, lang, base + timedelta(minutes=i))
        self.neighbors = []
        for i in range(54):
            nm = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
            rep = rng.choice([1.0] * 6 + [0.9, 0.85, 0.8, 0.7, 0.5])
            u = self._user(f"vecino{i + 1:02d}", f"vecino{i + 1:02d}@demo.test", nm, "NEIGHBOR", "ACTIVE", rep,
                           rng.choice(["es", "es", "va"]), base + timedelta(minutes=10 + i))
            self.neighbors.append(u)
        pool = list(self.neighbors)
        rng.shuffle(pool)
        for pos, k in ((1, "marta"), (3, "luis"), (6, "ana")):
            pool.insert(pos, self.users[k])
        w = [1 / (i + 1) ** 0.7 for i in range(len(pool))]
        self.pool_all = (pool, w)
        cur = [(u, wi) for u, wi in zip(pool, w) if u["key"] not in ("marta", "luis")]
        self.pool_cur = ([u for u, _ in cur], [wi for _, wi in cur])

        # puestos y productos
        self.stalls, self.products = [], {}
        for i, (mi, name, cat, half) in enumerate(STALLS):
            sid = self.uid("stall")
            owner = self.users["pepa"]["id"] if i == 0 else None
            st = {"id": sid, "market": mi, "name": name, "category": cat, "products": []}
            self.stalls.append(st)
            self.add("stalls", id=sid, market_id=self.markets[mi]["id"], name=name, category=cat, owner_user_id=owner,
                     verified_at=base, payout_account_ref=f"acct_demo_{i + 1:02d}")
            pool_p = CATALOG[cat] if half is None else CATALOG[cat][half::2]
            for (pn, unit, wg, vat, al, fc, price) in pool_p:
                pid = self.uid("product")
                p = {"id": pid, "stall": st, "name": pn, "usual": price, "food_class": fc, "weight": wg}
                st["products"].append(p)
                self.products[pid] = p
                self.add("products", id=pid, stall_id=sid, name=pn, unit=unit, unit_weight_g=wg, vat_rate=vat,
                         allergens=al, food_class=fc, usual_price_cents=price)

        # taquillas: 4 x 12 compartimentos (tamanos y zonas mezclados)
        self.lockers = []
        for li, (mi, dev) in enumerate(LOCKERS):
            lid = self.uid("locker")
            lk = {"id": lid, "market": mi, "comps": []}
            self.lockers.append(lk)
            self.add("lockers", id=lid, market_id=self.markets[mi]["id"], device_id=dev,
                     last_seen=self.T - timedelta(seconds=30 + li * 7), firmware="1.4.2")
            for slot in range(1, 13):
                cid = self.uid("compartment")
                lk["comps"].append({"id": cid, "slot": slot, "zone": R if slot <= 6 else A, "locker": lk,
                                    "size": "SML"[(slot + li) % 3]})
        self.oos = self.lockers[3]["comps"][11]["id"]  # una averiada fija

        self.charities = []
        for nm, mail in CHARITIES:
            cid = self.uid("charity")
            self.charities.append(cid)
            self.add("charities", id=cid, name=nm, contact_email=mail, active=True)

        for k, mi, cats in (("marta", 0, ["fruta", "pescado"]), ("luis", 1, ["verdura", "panaderia"]), ("ana", 0, [])):
            self.add("subscriptions", user_id=self.users[k]["id"], market_id=self.markets[mi]["id"], categories=cats,
                     quiet_from=time(22, 0), quiet_to=time(7, 0))
        for u in rng.sample(self.neighbors, 20):
            self.add("subscriptions", user_id=u["id"], market_id=rng.choice(self.markets)["id"],
                     categories=rng.sample(list(CATALOG), 2), quiet_from=time(22, 0), quiet_to=time(7, 0))

    def _user(self, key, email, name, role, status, rep, lang, created) -> dict:
        uid_ = self.uid("user")
        salt = hashlib.sha256(f"{self.seed}/salt/{email}".encode()).digest()[:16]
        self.add("users", id=uid_, email=email, password_hash=self.hash_password(DEMO_PASSWORD, salt), display_name=name,
                 role=role, lang=lang, reputation=rep, status=status, created_at=created)
        u = {"key": key, "id": uid_, "rep": rep, "status": status, "name": name}
        self.users[key] = u
        if status == "ACTIVE":
            verified = created + timedelta(hours=1)
            ph = hmac.new(self.key, f"demo-person:{email}".encode(), hashlib.sha256).digest()
            self.add("user_identities", user_id=uid_, person_hash=ph, age_verified_at=verified, age_method="fake",
                     provider_ref=f"fake-{key}")
            self.ev(verified, "user.verified", None, {"user_pseudo_id": self.pseudo(str(uid_)), "method": "demo"})
        return u

    # ---------- ofertas ----------
    def make_offer(self, d: date, stall: dict, product: dict, *, today: bool, profile=None, qty=None,
                   until: datetime | None = None) -> dict:
        rng = self.rng
        mk = MARKETS[stall["market"]]
        created = self.at(d, mk[5].hour, mk[5].minute) + self.mins(0, 25)
        if created >= self.T and today:
            created = self.T - timedelta(minutes=1)
        profile = profile or rng.choices(["LIBRE", "EQUILIBRADO", "ESTRICTO"], [2, 6, 2])[0]
        q = qty or rng.randint(3, 9)
        price = max(30, int(product["usual"] * rng.uniform(0.45, 0.7)) // 5 * 5)
        off = {"id": self.uid("offer"), "stall": stall, "product": product, "qty_total": q, "avail": q, "price": price,
               "ref": product["usual"], "created": created, "pfrom": self.at(d, 12, 0),
               "puntil": until or self.at(d, *rng.choice([(13, 30), (14, 0), (14, 30)])), "status": "ACTIVE",
               "consume_by": "TODAY" if product["food_class"] == R else rng.choice(["TODAY", "BEST_BEFORE"]),
               "profile": profile, "policy": policy_for(profile), "att": [], "n_orders": 0, "last_order": None}
        self.offers.append(off)
        return off

    def publish(self, off: dict) -> None:
        s, p = off["stall"], off["product"]
        self.ev(off["created"], "offer.published", off["id"], {
            "offer_id": str(off["id"]), "stall_id": str(s["id"]), "product_id": str(p["id"]), "qty": off["qty_total"],
            "price_cents": off["price"], "pickup_window": {"from": iso(off["pfrom"]), "until": iso(off["puntil"])}})
        self.ev(off["created"] + timedelta(seconds=self.rng.randint(2, 20)), "notification.sent", off["id"], {
            "channel": "in_app", "audience": self.pseudo(f"audience:{off['id']}"), "offer_id": str(off["id"]),
            "latency_ms": self.rng.randint(150, 2500)})

    # ---------- politica ----------
    def eval_policy(self, off: dict, now: datetime) -> tuple[float, int, float, list]:
        pol = off["policy"]
        ppu, maxu, minrep, applied = float(pol["base"]["points_per_unit"]), pol["base"]["max_units_per_user"], 0.0, []
        local = now.astimezone(TZ).strftime("%H:%M")
        for rule in pol["rules"]:
            ok = True
            for k, v in rule["when"].items():
                if k == "demand_velocity_gte":
                    recent = sum(1 for t in off["att"] if now - timedelta(minutes=10) <= t <= now)
                    ok &= recent / max(off["avail"], 1) >= v
                elif k == "minutes_to_close_lte":
                    ok &= (off["puntil"] - now).total_seconds() / 60 <= v
                elif k == "stock_ratio_gte":
                    ok &= off["avail"] / off["qty_total"] >= v
                elif k == "time_between":
                    ok &= v[0] <= local < v[1]
            if ok:
                th = rule["then"]
                ppu *= th.get("points_per_unit_mult", 1.0)
                maxu = th.get("max_units_per_user", maxu)
                minrep = max(minrep, th.get("min_reputation", 0.0))
                applied.append({"id": rule["id"], "then": th})
        lo, hi = pol["bounds"]["points_per_unit"]
        ppu = min(max(ppu, lo), hi)
        lo, hi = pol["bounds"]["max_units_per_user"]
        return ppu, min(max(maxu, lo), hi), minrep, applied

    # ---------- simulacion de un dia ----------
    def sim_day(self, d: date, is_today: bool, scenarios: list | None = None) -> list[dict]:
        rng = self.rng
        offers: list[dict] = []
        if is_today:
            for st in self.stalls:
                prods = rng.sample(st["products"], 2)
                if st is self.stalls[0] and all(p["name"] != "Tomates de la huerta" for p in prods):
                    prods[0] = st["products"][0]
                for p in prods:
                    offers.append(self.make_offer(d, st, p, today=True))
            for off, sc in zip(offers, scenarios):
                off["scenario"] = sc
                if sc == "closing":
                    off["puntil"] = self.at(d, 12, 30 + rng.randint(0, 15))
            tom = next(o for o in offers if o["product"]["name"] == "Tomates de la huerta")
            tom.update(scenario="some", qty_total=12, avail=12, profile="EQUILIBRADO", policy=policy_for("EQUILIBRADO"),
                       price=180, ref=280, puntil=self.at(d, 14, 30), consume_by="TODAY")
            tom["f"] = 0.25
        else:
            for st in self.stalls:
                if rng.random() < 0.85:
                    for p in rng.sample(st["products"], min(rng.choice([1, 1, 1, 2]), len(st["products"]))):
                        offers.append(self.make_offer(d, st, p, today=False))
            if not offers:
                offers.append(self.make_offer(d, self.stalls[0], self.stalls[0]["products"][0], today=False))
            if all(o["profile"] != "LIBRE" for o in offers):
                o = offers[0]
                o["profile"], o["policy"] = "LIBRE", policy_for("LIBRE")
        for off in offers:
            self.publish(off)
        self.day_offers = offers

        attempts: list[tuple] = []
        idx = 0
        for off in offers:
            if is_today:
                f = off.get("f") or {"fresh": 0.0, "some": rng.uniform(0.2, 0.55), "almost": rng.uniform(0.8, 0.95),
                                     "sold": 1.4, "closing": rng.uniform(0.1, 0.5)}[off["scenario"]]
                n = math.ceil(off["qty_total"] * f / 1.6 * 1.2) if f > 0 else 0
                lo, hi = off["created"] + timedelta(minutes=1), self.T - timedelta(minutes=1)
                times = [lo + (hi - lo) * rng.random() for _ in range(n)] if hi > lo else []
            else:
                dem = off["qty_total"] * rng.uniform(0.35, 1.5) * DOW_DEMAND[d.weekday()]
                n = max(0, round(dem / 1.6 * 1.2))
                lo, hi = off["created"] + timedelta(minutes=2), off["puntil"] - timedelta(minutes=45)
                plo, phi = max(lo, self.at(d, 12, 0)), min(hi, self.at(d, 13, 15))
                times = []
                for _ in range(n):
                    a, b = (plo, phi) if (phi > plo and rng.random() < 0.6) else (lo, hi)
                    times.append(a + (b - a) * rng.random())
            for t in times:
                attempts.append((t, idx, off, None))
                idx += 1
            # ruido de vistas (usuarios y anonimos)
            nv = rng.randint(3, 18) if not is_today else rng.randint(0, 8)
            vhi = min(off["puntil"] - timedelta(minutes=30), self.T)
            for _ in range(nv):
                if vhi <= off["created"]:
                    break
                t = off["created"] + (vhi - off["created"]) * rng.random()
                who = self.pseudo(str(rng.choice(self.pool_all[0])["id"])) if rng.random() < 0.55 else None
                self.ev(t, "app.offer_viewed", off["id"], {"user_pseudo_id": who, "offer_id": str(off["id"])})
                if rng.random() < 0.25:
                    self.ev(min(t + timedelta(seconds=rng.randint(10, 90)), self.T), "app.checkout_started", off["id"],
                            {"user_pseudo_id": who, "offer_id": str(off["id"])})

        # Luis: compras forzadas hasta agotar sus puntos de la semana actual (demuestra el bloqueo).
        if week_key(self.at(d, 12)) == self.cur_week:
            rem = ALLOWANCE - self.spent.get((self.users["luis"]["id"], self.cur_week), 0)
            cand = [o for o in offers if o["policy"]["base"]["points_per_unit"] <= rem and o["created"] + timedelta(minutes=1) < self.T]
            if rem > 0 and cand:
                off = max(cand, key=lambda o: (o["policy"]["base"]["points_per_unit"], o["qty_total"]))
                ppu = off["policy"]["base"]["points_per_unit"]
                units = min(off["policy"]["base"]["max_units_per_user"], rem // ppu, off["qty_total"])
                attempts.append((off["created"] + timedelta(minutes=1), idx, off, {"user": self.users["luis"], "units": units}))

        attempts.sort(key=lambda a: (a[0], a[1]))
        for t, _, off, forced in attempts:
            self.attempt(t, off, forced, d)
        return offers

    def attempt(self, t: datetime, off: dict, forced: dict | None, d: date) -> None:
        rng = self.rng
        if off["avail"] <= 0:
            return
        if forced:
            user = forced["user"]
        else:
            pool, w = self.pool_cur if week_key(t) == self.cur_week else self.pool_all
            user = rng.choices(pool, w)[0]
        pid = self.pseudo(str(user["id"]))
        oid_s = str(off["id"])
        self.ev(max(off["created"], t - timedelta(seconds=rng.randint(30, 600))), "app.offer_viewed", off["id"],
                {"user_pseudo_id": pid, "offer_id": oid_s})
        self.ev(t - timedelta(seconds=rng.randint(1, 20)), "app.checkout_started", off["id"],
                {"user_pseudo_id": pid, "offer_id": oid_s})
        if forced:
            ppu, maxu, minrep, applied = float(off["policy"]["base"]["points_per_unit"]), 99, 0.0, []
            units, cost = forced["units"], forced["units"] * off["policy"]["base"]["points_per_unit"]
        else:
            ppu, maxu, minrep, applied = self.eval_policy(off, t)
            units = rng.choices([1, 2, 3, 4], [5, 3, 1.5, 0.5])[0]
            off["att"].append(t)
            if user["rep"] < minrep:
                return self.deny(t, off, pid, "reputacion_insuficiente")
            if units > maxu:
                if rng.random() < 0.4:
                    return self.deny(t, off, pid, "supera_maximo")
                units = maxu
            units = min(units, off["avail"])
            cost = math.ceil(units * ppu - 1e-9)
        wk = week_key(t)
        if self.spent.get((user["id"], wk), 0) + cost > ALLOWANCE:
            return self.deny(t, off, pid, "sin_puntos")
        self.place_order(user, pid, off, units, cost, applied, t, forced is not None)

    def deny(self, t, off, pid, reason) -> None:
        self.ev(t, "order.denied", off["id"], {"user_pseudo_id": pid, "offer_id": str(off["id"]), "motivo": reason})

    def place_order(self, user, pid, off, units, cost, applied, held, forced) -> None:
        rng, T = self.rng, self.T
        ok = lambda x: x is not None and x <= T  # noqa: E731
        oid = self.uid("order")
        os_ = str(oid)
        wk = week_key(held)
        total = units * off["price"]
        prod = off["product"]
        off["avail"] -= units
        off["n_orders"] += 1
        off["last_order"] = held
        r = rng.random()
        if forced:
            kind = "PICKED_UP"
        elif r < 0.04:
            kind = "EXPIRED_HOLD"
        elif r < 0.07:
            kind = "CANCELLED"
        elif r < 0.13:
            kind = "NO_SHOW"
        elif r < 0.138 and prod["food_class"] == R:
            kind = "TEMP_ALARM"
        else:
            kind = "PICKED_UP"
        tl = [(held, "HELD")]
        paid = prep = dep = pick = alarm = exp = refunded = None
        until, pfrom = off["puntil"], off["pfrom"]
        if kind == "EXPIRED_HOLD":
            exp = held + timedelta(minutes=10)
            tl.append((exp, "EXPIRED_HOLD"))
            refunded = exp
        else:
            paid = held + timedelta(seconds=rng.randint(30, 120))
            tl.append((paid, "PAID"))
            if kind == "CANCELLED":
                c = paid + self.mins(3, 15)
                refunded = c + timedelta(minutes=1)
                tl += [(c, "CANCELLED_BY_PRODUCER"), (refunded, "REFUNDED")]
            else:
                prep = paid + self.mins(2, 10)
                dep = max(min(prep + self.mins(10, 40), until - timedelta(minutes=10)), prep + timedelta(minutes=1))
                tl += [(prep, "PREPARING"), (dep, "IN_LOCKER")]
                if kind == "PICKED_UP":
                    pick = max(dep + self.mins(3, 60), pfrom + self.mins(1, 10))
                    pick = max(min(pick, until - timedelta(minutes=1)), dep + timedelta(minutes=1))
                    tl.append((pick, "PICKED_UP"))
                elif kind == "NO_SHOW":
                    tl.append((until, "NO_SHOW"))
                else:
                    alarm = max(min(dep + self.mins(10, 40), until - timedelta(minutes=1)), dep + timedelta(minutes=1))
                    refunded = alarm + timedelta(minutes=1)
                    tl += [(alarm, "TEMP_ALARM"), (refunded, "REFUNDED")]
        status = [s for t, s in tl if ok(t)][-1]
        h = ok(exp) and kind == "EXPIRED_HOLD"
        self.add("orders", id=oid, user_id=user["id"], stall_id=off["stall"]["id"], status=status, total_cents=total,
                 points_cost=cost, rules_applied=[a["id"] for a in applied], idempotency_key=f"demo-{oid}",
                 hold_expires_at=(held + timedelta(minutes=10)) if (h or status == "HELD") else None,
                 pickup_until=until, created_at=held)
        self.add("order_items", order_id=oid, offer_id=off["id"], qty=units, unit_cents=off["price"])
        # puntos y stock
        self.spent[(user["id"], wk)] = self.spent.get((user["id"], wk), 0) + cost
        self.add("points_ledger", user_id=user["id"], week_key=wk, delta=-cost, reason="PURCHASE", order_id=oid, created_at=held)
        self.ev(held, "order.held", oid, {"order_id": os_, "user_pseudo_id": pid, "offer_id": str(off["id"]),
                                          "qty": units, "points_cost": cost, "rules_applied": [a["id"] for a in applied]})
        self.ev(held, "points.spent", oid, {"user_pseudo_id": pid, "week_key": wk, "delta": -cost})
        refund_now = ok(refunded) and kind in ("EXPIRED_HOLD", "CANCELLED", "TEMP_ALARM")
        if refund_now:
            rw = week_key(refunded)
            self.spent[(user["id"], rw)] -= cost
            self.add("points_ledger", user_id=user["id"], week_key=rw, delta=cost, reason="REFUND", order_id=oid, created_at=refunded)
            self.ev(refunded, "points.refunded", oid, {"user_pseudo_id": pid, "week_key": rw, "delta": cost})
        if h:
            off["avail"] += units
            self.ev(exp, "order.cancelled", oid, {"order_id": os_, "cause": "hold_expired"})
        # pago
        if ok(paid):
            self.add("payments", id=self.uid("payment"), order_id=oid, provider="fake",
                     provider_ref=f"fake_{self._n['payment']:06d}", amount_cents=total,
                     status="REFUNDED" if refund_now else "SUCCEEDED", created_at=paid)
            self.ev(paid, "order.paid", oid, {"order_id": os_, "amount_cents": total})
            if kind == "CANCELLED" and ok(tl[2][0]):
                self.ev(tl[2][0], "order.cancelled", oid, {"order_id": os_, "cause": "producer_rejected"})
        # taquilla
        if ok(prep):
            zone = prod["food_class"]
            lks = [lk for lk in self.lockers if lk["market"] == off["stall"]["market"]]
            comps = [c for lk in lks for c in lk["comps"] if c["zone"] == zone and c["id"] not in self.busy and c["id"] != self.oos]
            comp = rng.choice(comps or [c for lk in lks for c in lk["comps"] if c["zone"] == zone])
            self.add("deposits", id=self.uid("deposit"), order_id=oid,
                     compartment_id=comp["id"], code_hash=hashlib.sha256(f"{self.seed}/code/{oid}".encode()).digest(),
                     valid_from=prep, valid_until=until, deposited_at=dep if ok(dep) else None,
                     picked_up_at=pick if ok(pick) else None)
            if status == "PREPARING":
                self.busy[comp["id"]] = "RESERVED"
            elif status == "IN_LOCKER":
                self.busy[comp["id"]] = "OCCUPIED"
            if ok(dep):
                self.ev(dep, "order.deposited", oid, {"order_id": os_, "compartment_id": str(comp["id"]),
                                                      "seconds_since_paid": int((dep - paid).total_seconds())})
            if ok(pick):
                self.ev(pick, "order.picked_up", oid, {"order_id": os_,
                                                      "seconds_to_pickup": int((pick - dep).total_seconds())})
            if ok(alarm):
                lid = str(comp["locker"]["id"])
                celsius = round(rng.uniform(9.1, 11.5), 1)
                self.ev(alarm, "locker.temp_reading", comp["locker"]["id"], {"locker_id": lid, "compartment_id": str(comp["id"]), "celsius": celsius})
                self.ev(alarm, "locker.alarm", comp["locker"]["id"], {"locker_id": lid, "type": "temperature"})
                self.ev(refunded, "order.cancelled", oid, {"order_id": os_, "cause": "temp_alarm"}) if ok(refunded) else None
        if kind == "NO_SHOW" and ok(until):
            self.ev(until, "order.no_show", oid, {"order_id": os_, "cause": "pickup_window_expired"})
            if rng.random() < 0.7:  # el producto no retirado se ofrece a donacion
                self.donate(off, units, until + self.mins(10, 25))
        if ok(paid) and status in ("PICKED_UP", "NO_SHOW"):
            self.completed.append((off["stall"]["id"], paid, total))
        if user["key"] in ("marta", "luis", "ana"):
            when = pick if ok(pick) else held
            self.add("notifications", user_id=user["id"], kind="order.status",
                     payload={"order_id": os_, "status": status}, read_at=(when + timedelta(minutes=5)) if when < T - timedelta(days=1) else None,
                     created_at=when)

    def donate(self, off: dict, qty: int, created: datetime) -> None:
        rng = self.rng
        done = created + self.mins(20, 60)
        if done > self.T:
            return
        did = self.uid("donation")
        ch = rng.choice(self.charities)
        self.add("donations", id=did, offer_id=off["id"], charity_id=ch, qty=qty, status="COMPLETED",
                 created_at=created, completed_at=done)
        self.ev(done, "donation.completed", did, {"offer_id": str(off["id"]),
                                                  "charity_id": str(ch), "qty": qty})

    def close_day(self, offers: list[dict]) -> None:
        rng = self.rng
        for off in offers:
            if off["avail"] == 0:
                off["status"] = "SOLD_OUT"
            elif off["n_orders"] == 0 and rng.random() < 0.05:
                off["status"] = "WITHDRAWN"
                self.ev(off["created"] + self.mins(10, 60), "offer.withdrawn", off["id"],
                        {"offer_id": str(off["id"]), "qty_remaining": off["avail"]})
            else:
                self.ev(off["puntil"], "offer.expired", off["id"], {"offer_id": str(off["id"]), "qty_remaining": off["avail"]})
                if rng.random() < 0.65:
                    off["status"] = "DONATED"
                    self.donate(off, off["avail"], off["puntil"] + self.mins(10, 25))
                else:
                    off["status"] = "DISCARDED"

    # ---------- telemetria ----------
    def telemetry(self, days: list[date]) -> None:
        rng = self.rng
        for d in days:
            for lk in self.lockers:
                cold = [c for c in lk["comps"] if c["zone"] == R and c["id"] != self.oos]
                for h in range(7, 16):
                    t = self.at(d, h)
                    if t > self.T:
                        continue
                    c = rng.choice(cold)
                    v = rng.uniform(7.1, 7.9) if rng.random() < 0.01 else min(max(rng.gauss(3.2, 0.6), 1.0), 6.5)
                    self.ev(t, "locker.temp_reading", lk["id"], {"locker_id": str(lk["id"]), "compartment_id": str(c["id"]),
                                                                  "celsius": round(v, 1)})

    # ---------- liquidaciones ----------
    def payouts(self) -> None:
        by: dict[tuple, int] = {}
        for sid, paid, total in self.completed:
            local = paid.astimezone(TZ).date()
            monday = local - timedelta(days=local.weekday())
            by[(sid, monday)] = by.get((sid, monday), 0) + total
        cur_monday = self.today - timedelta(days=self.today.weekday())
        for (sid, monday), gross in sorted(by.items(), key=lambda kv: (str(kv[0][0]), kv[0][1])):
            comm = round(gross * 0.05)
            done = monday < cur_monday
            self.add("payouts", id=self.uid("payout"), stall_id=sid, period_from=self.at(monday, 0),
                     period_to=self.at(monday + timedelta(days=7), 0), gross_cents=gross, commission_cents=comm,
                     amount_cents=gross - comm, status="PAID" if done else "PENDING",
                     paid_at=self.at(monday + timedelta(days=8), 10) if done else None)

    # ---------- orquestacion ----------
    def build(self) -> Dataset:
        rng = self.rng
        self.reference()
        hist = [self.today - timedelta(days=i) for i in range(HISTORY_DAYS, 0, -1)]
        hist = [d for d in hist if d.weekday() != 6]
        for d in hist:
            offers = self.sim_day(d, False)
            self.close_day(offers)
        scen = ["fresh"] * 6 + ["some"] * 9 + ["almost"] * 5 + ["sold"] * 2 + ["closing"] * 2
        rng.shuffle(scen)
        today_offers = self.sim_day(self.today, True, scen)
        for off in today_offers:
            if off["avail"] == 0:
                off["status"] = "SOLD_OUT"
        # borrador de Pepa (escena del productor)
        st = self.stalls[0]
        draft = self.make_offer(self.today, st, next(p for p in st["products"] if p["name"] == "Fresas"),
                                today=True, profile="EQUILIBRADO", qty=6)
        draft["status"] = "DRAFT"
        self.telemetry(hist + [self.today])
        self.payouts()
        self.finalize()
        return self.ds

    def finalize(self) -> None:
        rng = self.rng
        for off in self.offers:
            self.add("offers", id=off["id"], stall_id=off["stall"]["id"], product_id=off["product"]["id"],
                     qty_total=off["qty_total"], qty_available=off["avail"], price_cents=off["price"],
                     reference_price_cents=off["ref"], pickup_from=off["pfrom"], pickup_until=off["puntil"],
                     status=off["status"], consume_by=off["consume_by"], created_at=off["created"])
            self.add("offer_policies", offer_id=off["id"], profile=off["profile"], policy=off["policy"], version=1)
        for lk in self.lockers:
            for c in lk["comps"]:
                st = "OUT_OF_SERVICE" if c["id"] == self.oos else self.busy.get(c["id"], "FREE")
                self.add("compartments", id=c["id"], locker_id=lk["id"], slot=c["slot"], size=c["size"], zone=c["zone"], status=st)
        # saldo semanal: semanas con actividad + semana actual para todo usuario verificado
        weeks = dict(self.spent)
        for u in list(self.users.values()):
            if u["status"] == "ACTIVE" and u["key"] not in ("pepa", "gestion"):
                weeks.setdefault((u["id"], self.cur_week), 0)
        for (uid_, wk), sp in sorted(weeks.items(), key=lambda kv: (str(kv[0][0]), kv[0][1])):
            assert 0 <= sp <= ALLOWANCE, (uid_, wk, sp)
            self.add("points_week", user_id=uid_, week_key=wk, allowance=ALLOWANCE, spent=sp)
        # notificacion sin leer para Marta: tomates publicados hoy
        tom = next(o for o in self.offers if o["product"]["name"] == "Tomates de la huerta" and o["created"].astimezone(TZ).date() == self.today)
        self.add("notifications", user_id=self.users["marta"]["id"], kind="offer.new",
                 payload={"offer_id": str(tom["id"])}, read_at=None, created_at=tom["created"] + timedelta(seconds=5))
        # orden estable para identidades autonumericas
        self.ds.tables["points_ledger"].sort(key=lambda r: (r[5], str(r[0]), r[4] and str(r[4]), r[3]))
        self.ds.tables["notifications"].sort(key=lambda r: (r[4], str(r[0]), r[1]))
        for at_, seq, etype, agg, payload in sorted(self.events, key=lambda e: (e[0], e[1])):
            self.add("domain_events", occurred_at=at_, event_type=etype, aggregate_id=agg, payload=payload, published_at=at_)
        self.ds.demo_users = {k: u["id"] for k, u in self.users.items() if k in dict((x[0], 1) for x in DEMO_USERS)}
        self.ds.stats = {t: len(r) for t, r in self.ds.tables.items()}


def generate(seed: int, clock_start: datetime, person_hash_key: str, hash_password) -> Dataset:
    """hash_password(password: str, salt: bytes) -> str  (Argon2 con sal fija derivada de la semilla)."""
    return Builder(seed, clock_start, person_hash_key, hash_password).build()
