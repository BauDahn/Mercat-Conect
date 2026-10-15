-- staging: tipos corregidos, duplicados eliminados, zona horaria normalizada.
-- Una vista por tipo de evento y una por tabla transaccional (sin datos personales).
CREATE VIEW staging.stg_events AS
SELECT DISTINCT ON (event_id)
       event_id, occurred_at,
       occurred_at AT TIME ZONE 'Europe/Madrid' AS occurred_local,
       event_type, aggregate_id, payload
FROM raw.events
ORDER BY event_id;

CREATE VIEW staging.stg_offer_published AS
SELECT event_id, occurred_at, (payload->>'offer_id')::uuid AS offer_id, (payload->>'stall_id')::uuid AS stall_id,
       (payload->>'product_id')::uuid AS product_id, (payload->>'qty')::int AS qty, (payload->>'price_cents')::int AS price_cents,
       (payload#>>'{pickup_window,from}')::timestamptz AS pickup_from, (payload#>>'{pickup_window,until}')::timestamptz AS pickup_until
FROM staging.stg_events WHERE event_type = 'offer.published';

CREATE VIEW staging.stg_offer_expired AS
SELECT event_id, occurred_at, (payload->>'offer_id')::uuid AS offer_id, (payload->>'qty_remaining')::int AS qty_remaining
FROM staging.stg_events WHERE event_type = 'offer.expired';

CREATE VIEW staging.stg_offer_withdrawn AS
SELECT event_id, occurred_at, (payload->>'offer_id')::uuid AS offer_id, (payload->>'qty_remaining')::int AS qty_remaining
FROM staging.stg_events WHERE event_type = 'offer.withdrawn';

CREATE VIEW staging.stg_app_offer_viewed AS
SELECT event_id, occurred_at, payload->>'user_pseudo_id' AS user_pseudo_id, (payload->>'offer_id')::uuid AS offer_id
FROM staging.stg_events WHERE event_type = 'app.offer_viewed';

CREATE VIEW staging.stg_app_checkout_started AS
SELECT event_id, occurred_at, payload->>'user_pseudo_id' AS user_pseudo_id, (payload->>'offer_id')::uuid AS offer_id
FROM staging.stg_events WHERE event_type = 'app.checkout_started';

CREATE VIEW staging.stg_notification_sent AS
SELECT event_id, occurred_at, payload->>'channel' AS channel, payload->>'audience' AS audience,
       (payload->>'offer_id')::uuid AS offer_id, (payload->>'latency_ms')::int AS latency_ms
FROM staging.stg_events WHERE event_type = 'notification.sent';

CREATE VIEW staging.stg_order_held AS
SELECT event_id, occurred_at, (payload->>'order_id')::uuid AS order_id, payload->>'user_pseudo_id' AS user_pseudo_id,
       (payload->>'offer_id')::uuid AS offer_id, (payload->>'qty')::int AS qty, (payload->>'points_cost')::int AS points_cost,
       payload->'rules_applied' AS rules_applied
FROM staging.stg_events WHERE event_type = 'order.held';

CREATE VIEW staging.stg_order_denied AS
SELECT event_id, occurred_at, payload->>'user_pseudo_id' AS user_pseudo_id, (payload->>'offer_id')::uuid AS offer_id,
       payload->>'reason' AS reason
FROM staging.stg_events WHERE event_type = 'order.denied';

CREATE VIEW staging.stg_order_paid AS
SELECT event_id, occurred_at, (payload->>'order_id')::uuid AS order_id, (payload->>'amount_cents')::int AS amount_cents
FROM staging.stg_events WHERE event_type = 'order.paid';

CREATE VIEW staging.stg_order_deposited AS
SELECT event_id, occurred_at, (payload->>'order_id')::uuid AS order_id, (payload->>'compartment_id')::uuid AS compartment_id,
       (payload->>'seconds_since_paid')::numeric AS seconds_since_paid
FROM staging.stg_events WHERE event_type = 'order.deposited';

CREATE VIEW staging.stg_order_picked_up AS
SELECT event_id, occurred_at, (payload->>'order_id')::uuid AS order_id, (payload->>'seconds_to_pickup')::numeric AS seconds_to_pickup
FROM staging.stg_events WHERE event_type = 'order.picked_up';

CREATE VIEW staging.stg_order_no_show AS
SELECT event_id, occurred_at, (payload->>'order_id')::uuid AS order_id, payload->>'cause' AS cause
FROM staging.stg_events WHERE event_type = 'order.no_show';

CREATE VIEW staging.stg_order_cancelled AS
SELECT event_id, occurred_at, (payload->>'order_id')::uuid AS order_id, payload->>'cause' AS cause
FROM staging.stg_events WHERE event_type = 'order.cancelled';

CREATE VIEW staging.stg_points_spent AS
SELECT event_id, occurred_at, payload->>'user_pseudo_id' AS user_pseudo_id, payload->>'week_key' AS week_key,
       (payload->>'delta')::int AS delta, aggregate_id AS order_id
FROM staging.stg_events WHERE event_type = 'points.spent';

CREATE VIEW staging.stg_points_refunded AS
SELECT event_id, occurred_at, payload->>'user_pseudo_id' AS user_pseudo_id, payload->>'week_key' AS week_key,
       (payload->>'delta')::int AS delta, aggregate_id AS order_id
FROM staging.stg_events WHERE event_type = 'points.refunded';

CREATE VIEW staging.stg_locker_temp_reading AS
SELECT event_id, occurred_at, (payload->>'locker_id')::uuid AS locker_id, (payload->>'compartment_id')::uuid AS compartment_id,
       (payload->>'celsius')::numeric AS celsius
FROM staging.stg_events WHERE event_type = 'locker.temp_reading';

CREATE VIEW staging.stg_locker_alarm AS
SELECT event_id, occurred_at, (payload->>'locker_id')::uuid AS locker_id, payload->>'type' AS alarm_type
FROM staging.stg_events WHERE event_type = 'locker.alarm';

CREATE VIEW staging.stg_donation_completed AS
SELECT event_id, occurred_at, (payload->>'offer_id')::uuid AS offer_id, (payload->>'charity_id')::uuid AS charity_id,
       (payload->>'qty')::int AS qty
FROM staging.stg_events WHERE event_type = 'donation.completed';

CREATE VIEW staging.stg_user_verified AS
SELECT event_id, occurred_at, payload->>'user_pseudo_id' AS user_pseudo_id, payload->>'method' AS method
FROM staging.stg_events WHERE event_type = 'user.verified';

-- Tablas transaccionales: solo columnas no personales (ni user_id, ni correo, ni person_hash).
CREATE VIEW staging.stg_markets AS
SELECT id AS market_id, name, lat, lng, opens_at, closes_at, offers_from, tz FROM public.markets;

CREATE VIEW staging.stg_stalls AS
SELECT id AS stall_id, market_id, name, category, (verified_at IS NOT NULL) AS verified FROM public.stalls;

CREATE VIEW staging.stg_products AS
SELECT id AS product_id, stall_id, name, unit, unit_weight_g, vat_rate, allergens, food_class, usual_price_cents FROM public.products;

CREATE VIEW staging.stg_offers AS
SELECT id AS offer_id, stall_id, product_id, qty_total, qty_available, price_cents, reference_price_cents,
       pickup_from, pickup_until, status, consume_by, created_at,
       created_at AT TIME ZONE 'Europe/Madrid' AS created_local
FROM public.offers;

CREATE VIEW staging.stg_orders AS
SELECT id AS order_id, stall_id, status, total_cents, points_cost, created_at, pickup_until FROM public.orders;

CREATE VIEW staging.stg_order_items AS
SELECT order_id, offer_id, qty, unit_cents FROM public.order_items;

CREATE VIEW staging.stg_payments AS
SELECT id AS payment_id, order_id, provider, amount_cents, status, created_at AS paid_at FROM public.payments;

CREATE VIEW staging.stg_lockers AS SELECT id AS locker_id, market_id, device_id FROM public.lockers;

CREATE VIEW staging.stg_compartments AS
SELECT id AS compartment_id, locker_id, slot, size, zone, status FROM public.compartments;

CREATE VIEW staging.stg_deposits AS
SELECT id AS deposit_id, order_id, compartment_id, valid_from, valid_until, deposited_at, picked_up_at FROM public.deposits;

CREATE VIEW staging.stg_donations AS
SELECT id AS donation_id, offer_id, charity_id, qty, status, created_at, completed_at FROM public.donations;
