-- raw: eventos tal cual llegan del outbox (domain_events). Clave event_id: ingesta idempotente.
CREATE TABLE IF NOT EXISTS raw.events (
  event_id     bigint PRIMARY KEY,
  occurred_at  timestamptz NOT NULL,
  event_type   text NOT NULL,
  aggregate_id uuid,
  payload      jsonb NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_raw_events_type ON raw.events (event_type, occurred_at);
