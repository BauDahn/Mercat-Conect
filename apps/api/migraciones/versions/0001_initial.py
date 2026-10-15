"""esquema inicial (ARQUITECTURA.md sección 8.2 + sessions, payouts, charities, donations, deliveries)

Revision ID: 0001
Revises:
"""
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

DDL = r"""
-- ============ Mercados y puestos ============
CREATE TABLE markets (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name          text NOT NULL,
  lat           double precision,
  lng           double precision,
  opens_at      time NOT NULL,
  closes_at     time NOT NULL,
  offers_from   time NOT NULL,              -- no se publica antes (evita canibalizar la venta normal)
  tz            text NOT NULL DEFAULT 'Europe/Madrid'
);

CREATE TABLE stalls (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  market_id     uuid NOT NULL REFERENCES markets,
  name          text NOT NULL,
  category      text NOT NULL,
  owner_user_id uuid,
  verified_at   timestamptz,                -- alta validada por la gestión del mercado
  payout_account_ref text                   -- referencia en el proveedor de pagos, nunca el IBAN
);

-- ============ Usuarios ============
CREATE TABLE users (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email          citext UNIQUE NOT NULL,
  password_hash  text,                      -- NULL si solo usa enlace mágico
  display_name   text NOT NULL,
  role           text NOT NULL CHECK (role IN ('NEIGHBOR','PRODUCER','MANAGER','ADMIN')),
  lang           text NOT NULL DEFAULT 'es',
  reputation     numeric(3,2) NOT NULL DEFAULT 1.00,
  status         text NOT NULL DEFAULT 'PENDING'  -- PENDING hasta verificar edad
                 CHECK (status IN ('PENDING','ACTIVE','SUSPENDED','DELETED')),
  telegram_chat_id bigint,                  -- opcional y futuro: solo para avisos
  created_at     timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE user_identities (
  user_id         uuid PRIMARY KEY REFERENCES users,
  person_hash     bytea UNIQUE NOT NULL,           -- una persona = una cuenta
  age_verified_at timestamptz NOT NULL,
  age_method      text NOT NULL,                   -- 'clave','eudi','kyc','demo'
  provider_ref    text
);

-- ============ Catálogo y ofertas ============
CREATE TABLE products (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  stall_id       uuid NOT NULL REFERENCES stalls,
  name           text NOT NULL,
  unit           text NOT NULL,                    -- 'kg','ud','bandeja'
  unit_weight_g  integer,                          -- para convertir a kg rescatados
  vat_rate       numeric(4,2) NOT NULL,            -- IVA según producto (verificar tipos)
  allergens      text[] NOT NULL DEFAULT '{}',
  food_class     text NOT NULL CHECK (food_class IN ('REFRIGERATED','AMBIENT')),
  usual_price_cents integer,
  photo_path     text
);

CREATE TABLE offers (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  stall_id       uuid NOT NULL REFERENCES stalls,
  product_id     uuid NOT NULL REFERENCES products,
  qty_total      integer NOT NULL CHECK (qty_total > 0),
  qty_available  integer NOT NULL CHECK (qty_available >= 0),
  price_cents    integer NOT NULL CHECK (price_cents >= 0),   -- lo fija el productor
  reference_price_cents integer,                              -- para mostrar el ahorro real
  pickup_from    timestamptz NOT NULL,
  pickup_until   timestamptz NOT NULL,
  status         text NOT NULL DEFAULT 'DRAFT'
                 CHECK (status IN ('DRAFT','ACTIVE','SOLD_OUT','EXPIRED','WITHDRAWN','DONATED','DISCARDED')),
  consume_by     text NOT NULL CHECK (consume_by IN ('TODAY','BEST_BEFORE')),
  created_at     timestamptz NOT NULL DEFAULT now(),
  CHECK (qty_available <= qty_total)
);

CREATE TABLE offer_policies (               -- reglas del productor para esa oferta (sección 10)
  offer_id    uuid PRIMARY KEY REFERENCES offers,
  profile     text NOT NULL,                -- 'LIBRE' | 'EQUILIBRADO' | 'ESTRICTO' | 'PERSONALIZADO'
  policy      jsonb NOT NULL,
  version     integer NOT NULL DEFAULT 1
);

-- ============ Puntos ============
CREATE TABLE points_week (                  -- saldo por usuario y semana
  user_id    uuid NOT NULL REFERENCES users,
  week_key   text NOT NULL,                 -- ej. '2026-W42' en hora de Madrid
  allowance  integer NOT NULL,
  spent      integer NOT NULL DEFAULT 0,
  PRIMARY KEY (user_id, week_key),
  CHECK (spent >= 0 AND spent <= allowance)
);

CREATE TABLE points_ledger (                -- libro inmutable: auditoría y reembolsos
  id         bigserial PRIMARY KEY,
  user_id    uuid NOT NULL REFERENCES users,
  week_key   text NOT NULL,
  delta      integer NOT NULL,              -- negativo = gasto, positivo = devolución
  reason     text NOT NULL,                 -- 'PURCHASE','REFUND_PRODUCER_FAULT','REFUND_CANCEL','ADMIN'
  order_id   uuid,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- ============ Pedidos ============
CREATE TABLE orders (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id          uuid NOT NULL REFERENCES users,
  stall_id         uuid NOT NULL REFERENCES stalls,
  status           text NOT NULL,           -- ver máquina de estados (sección 9)
  total_cents      integer NOT NULL,
  points_cost      integer NOT NULL,
  rules_applied    jsonb NOT NULL DEFAULT '[]',  -- explicabilidad: qué reglas pesaron
  idempotency_key  text UNIQUE NOT NULL,    -- evita duplicados por doble clic o reintento
  hold_expires_at  timestamptz,
  pickup_until     timestamptz NOT NULL,
  created_at       timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE order_items (
  order_id    uuid NOT NULL REFERENCES orders,
  offer_id    uuid NOT NULL REFERENCES offers,
  qty         integer NOT NULL CHECK (qty > 0),
  unit_cents  integer NOT NULL,
  PRIMARY KEY (order_id, offer_id)
);

CREATE TABLE payments (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  order_id      uuid UNIQUE NOT NULL REFERENCES orders,
  provider      text NOT NULL,              -- 'fake','redsys','stripe',...
  provider_ref  text UNIQUE,
  amount_cents  integer NOT NULL,
  status        text NOT NULL,              -- 'PENDING','PAID','FAILED','REFUNDED'
  created_at    timestamptz NOT NULL DEFAULT now()
);

-- ============ Taquillas ============
CREATE TABLE lockers (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  market_id   uuid NOT NULL REFERENCES markets,
  device_id   text UNIQUE NOT NULL,         -- en la demo, un identificador virtual
  last_seen   timestamptz,
  firmware    text
);

CREATE TABLE compartments (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  locker_id   uuid NOT NULL REFERENCES lockers,
  slot        integer NOT NULL,
  size        text NOT NULL CHECK (size IN ('S','M','L')),
  zone        text NOT NULL CHECK (zone IN ('REFRIGERATED','AMBIENT')),
  status      text NOT NULL DEFAULT 'FREE'
              CHECK (status IN ('FREE','RESERVED','OCCUPIED','OUT_OF_SERVICE')),
  UNIQUE (locker_id, slot)
);

CREATE TABLE deposits (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  order_id        uuid UNIQUE NOT NULL REFERENCES orders,
  compartment_id  uuid NOT NULL REFERENCES compartments,
  code_hash       bytea NOT NULL,           -- el código de retirada nunca se guarda en claro
  valid_from      timestamptz NOT NULL,
  valid_until     timestamptz NOT NULL,
  deposited_at    timestamptz,
  picked_up_at    timestamptz
);

-- ============ Avisos y suscripciones ============
CREATE TABLE subscriptions (
  user_id     uuid NOT NULL REFERENCES users,
  market_id   uuid NOT NULL REFERENCES markets,
  categories  text[] NOT NULL DEFAULT '{}',
  quiet_from  time,
  quiet_to    time,
  PRIMARY KEY (user_id, market_id)
);

CREATE TABLE notifications (                -- bandeja dentro de la app
  id          bigserial PRIMARY KEY,
  user_id     uuid NOT NULL REFERENCES users,
  kind        text NOT NULL,                -- 'OFFER_MATCH','ORDER_READY','ORDER_CANCELLED',...
  payload     jsonb NOT NULL,
  read_at     timestamptz,
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE push_subscriptions (           -- Web Push (opcional)
  id          bigserial PRIMARY KEY,
  user_id     uuid NOT NULL REFERENCES users,
  endpoint    text UNIQUE NOT NULL,
  keys        jsonb NOT NULL
);

-- ============ Eventos (auditoría y pipeline) ============
CREATE TABLE domain_events (                -- outbox
  id            bigserial PRIMARY KEY,
  occurred_at   timestamptz NOT NULL,       -- hora del Clock, no de la base de datos
  event_type    text NOT NULL,
  aggregate_id  uuid,
  payload       jsonb NOT NULL,
  published_at  timestamptz                 -- NULL hasta que el worker lo publica
);

-- ============ Extensiones a la sección 8.2 (mínimas) ============
CREATE TABLE sessions (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     uuid NOT NULL REFERENCES users,
  token_hash  bytea UNIQUE NOT NULL,
  created_at  timestamptz NOT NULL,          -- hora del Clock
  expires_at  timestamptz NOT NULL
);

CREATE TABLE payouts (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  stall_id         uuid NOT NULL REFERENCES stalls,
  period_from      timestamptz NOT NULL,
  period_to        timestamptz NOT NULL,
  gross_cents      integer NOT NULL,
  commission_cents integer NOT NULL DEFAULT 0,
  amount_cents     integer NOT NULL,
  status           text NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','PAID')),
  paid_at          timestamptz
);

CREATE TABLE charities (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name          text NOT NULL,
  contact_email text,
  active        boolean NOT NULL DEFAULT true
);

CREATE TABLE donations (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  offer_id     uuid NOT NULL REFERENCES offers,
  charity_id   uuid NOT NULL REFERENCES charities,
  qty          integer NOT NULL CHECK (qty > 0),
  status       text NOT NULL DEFAULT 'OFFERED',
  created_at   timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz
);

CREATE TABLE deliveries (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  order_id     uuid UNIQUE NOT NULL REFERENCES orders,
  provider     text NOT NULL,
  provider_ref text,
  status       text NOT NULL DEFAULT 'REQUESTED',
  created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX ix_offers_status_pickup ON offers (status, pickup_until);
CREATE INDEX ix_orders_user ON orders (user_id, created_at DESC);
CREATE INDEX ix_orders_hold ON orders (hold_expires_at) WHERE status = 'HELD';
CREATE INDEX ix_domain_events_unpublished ON domain_events (id) WHERE published_at IS NULL;

"""

TABLES = [
    "deliveries", "donations", "charities", "payouts", "sessions", "domain_events",
    "push_subscriptions", "notifications", "subscriptions", "deposits", "compartments",
    "lockers", "payments", "order_items", "orders", "points_ledger", "points_week",
    "offer_policies", "offers", "products", "user_identities", "users", "stalls", "markets",
]


def _extension(name: str, fallback: str | None = None) -> None:
    """Crea la extensión; si el servidor no la trae (p. ej. PostgreSQL embebido de
    `make demo-local`), usa la alternativa. La app ya guarda el correo en minúsculas."""
    conn = op.get_bind()
    try:
        with conn.begin_nested():
            conn.exec_driver_sql(f"CREATE EXTENSION IF NOT EXISTS {name}")
    except Exception:
        if fallback:
            conn.exec_driver_sql(fallback)


def upgrade() -> None:
    # gen_random_uuid() es nativa desde PostgreSQL 13: pgcrypto no es imprescindible.
    _extension("pgcrypto")
    _extension("citext", "CREATE DOMAIN citext AS text")
    for stmt in DDL.split(";"):
        if stmt.strip():
            op.execute(stmt)


def downgrade() -> None:
    for t in TABLES:
        op.execute(f"DROP TABLE IF EXISTS {t} CASCADE")
