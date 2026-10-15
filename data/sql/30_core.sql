-- core: modelo en estrella (hechos y dimensiones) como vistas materializadas.
-- Solo user_pseudo_id; nunca correo, nombre, user_id ni person_hash.
CREATE MATERIALIZED VIEW core.dim_market AS
SELECT market_id, name, lat, lng, opens_at, closes_at, offers_from, tz FROM staging.stg_markets;

CREATE MATERIALIZED VIEW core.dim_stall AS
SELECT s.stall_id, s.market_id, s.name, s.category, s.verified FROM staging.stg_stalls s;

CREATE MATERIALIZED VIEW core.dim_product AS
SELECT p.product_id, p.stall_id, s.category, p.name, p.unit, p.unit_weight_g, p.vat_rate, p.allergens,
       p.food_class, p.usual_price_cents
FROM staging.stg_products p JOIN staging.stg_stalls s USING (stall_id);

CREATE MATERIALIZED VIEW core.dim_date AS
SELECT d::date AS date_key,
       to_char(d, 'IYYY-"W"IW') AS week_key,
       extract(isodow FROM d)::int AS isodow,
       extract(isodow FROM d) >= 6 AS is_weekend,
       extract(isodow FROM d) < 7 AS is_market_day
FROM generate_series(
       (SELECT min(occurred_at AT TIME ZONE 'Europe/Madrid')::date FROM raw.events),
       (core.clock_now() AT TIME ZONE 'Europe/Madrid')::date,
       interval '1 day') AS g(d);

CREATE MATERIALIZED VIEW core.fct_offers AS
WITH sales AS (
  SELECT oi.offer_id,
         sum(oi.qty) FILTER (WHERE o.status IN ('HELD','PAID','PREPARING','IN_LOCKER','PICKED_UP','NO_SHOW')) AS units_sold,
         sum(oi.qty) FILTER (WHERE o.status = 'PICKED_UP') AS units_picked_up,
         max(o.created_at) FILTER (WHERE o.status IN ('HELD','PAID','PREPARING','IN_LOCKER','PICKED_UP','NO_SHOW')) AS last_sale_at
  FROM staging.stg_order_items oi JOIN staging.stg_orders o USING (order_id)
  GROUP BY oi.offer_id
)
SELECT f.offer_id, f.stall_id, s.market_id, s.category, f.product_id, f.qty_total, f.qty_available,
       coalesce(sa.units_sold, 0)::int AS units_sold,
       coalesce(sa.units_picked_up, 0)::int AS units_picked_up,
       f.price_cents, f.reference_price_cents, f.status, f.consume_by,
       f.created_at, f.pickup_from, f.pickup_until,
       (pub.offer_id IS NOT NULL) AS is_published,
       (f.pickup_until <= core.clock_now()) AS is_closed,
       (f.status = 'SOLD_OUT') AS is_sold_out,
       pub.occurred_at AS published_at,
       CASE WHEN f.status = 'SOLD_OUT'
            THEN extract(epoch FROM (sa.last_sale_at - pub.occurred_at)) / 60.0 END AS minutes_to_sell_out,
       (f.created_at AT TIME ZONE 'Europe/Madrid')::date AS day_local
FROM staging.stg_offers f
JOIN staging.stg_stalls s USING (stall_id)
LEFT JOIN sales sa USING (offer_id)
LEFT JOIN staging.stg_offer_published pub USING (offer_id);

CREATE MATERIALIZED VIEW core.fct_orders AS
SELECT o.order_id, h.user_pseudo_id, o.stall_id, s.market_id, s.category, o.status,
       o.total_cents, o.points_cost,
       coalesce(it.units, 0)::int AS units, coalesce(it.kg, 0) AS kg,
       o.created_at, p.paid_at, d.deposited_at, d.picked_up_at,
       (o.created_at AT TIME ZONE 'Europe/Madrid')::date AS day_local,
       extract(hour FROM o.created_at AT TIME ZONE 'Europe/Madrid')::int AS hour_local,
       extract(isodow FROM o.created_at AT TIME ZONE 'Europe/Madrid')::int AS isodow,
       to_char(o.created_at AT TIME ZONE 'Europe/Madrid', 'IYYY-"W"IW') AS week_key,
       (p.paid_at IS NOT NULL) AS is_paid,
       (o.status IN ('HELD','PAID','PREPARING','IN_LOCKER','PICKED_UP','NO_SHOW')) AS is_sale,
       (o.status IN ('PAID','PREPARING','IN_LOCKER','PICKED_UP','NO_SHOW')) AS is_revenue
FROM staging.stg_orders o
JOIN staging.stg_stalls s USING (stall_id)
LEFT JOIN staging.stg_order_held h ON h.order_id = o.order_id
LEFT JOIN staging.stg_payments p ON p.order_id = o.order_id
LEFT JOIN staging.stg_deposits d ON d.order_id = o.order_id
LEFT JOIN (
  SELECT oi.order_id, sum(oi.qty) AS units, sum(oi.qty * coalesce(pr.unit_weight_g, 0)) / 1000.0 AS kg
  FROM staging.stg_order_items oi
  JOIN staging.stg_offers f ON f.offer_id = oi.offer_id
  JOIN staging.stg_products pr ON pr.product_id = f.product_id
  GROUP BY oi.order_id
) it ON it.order_id = o.order_id;

CREATE MATERIALIZED VIEW core.fct_order_items AS
SELECT oi.order_id, oi.offer_id, f.product_id, o.stall_id, s.market_id, s.category, o.status,
       oi.qty, oi.unit_cents, oi.qty * oi.unit_cents AS amount_cents,
       oi.qty * coalesce(pr.unit_weight_g, 0) / 1000.0 AS kg,
       o.created_at, (o.created_at AT TIME ZONE 'Europe/Madrid')::date AS day_local
FROM staging.stg_order_items oi
JOIN staging.stg_orders o USING (order_id)
JOIN staging.stg_offers f ON f.offer_id = oi.offer_id
JOIN staging.stg_products pr ON pr.product_id = f.product_id
JOIN staging.stg_stalls s ON s.stall_id = o.stall_id;

CREATE MATERIALIZED VIEW core.fct_locker_readings AS
SELECT r.event_id, r.occurred_at, r.locker_id, r.compartment_id, r.celsius, l.market_id,
       EXISTS (SELECT 1 FROM staging.stg_locker_alarm a
               WHERE a.locker_id = r.locker_id AND a.occurred_at = r.occurred_at) AS is_alarm
FROM staging.stg_locker_temp_reading r
JOIN staging.stg_lockers l ON l.locker_id = r.locker_id;

CREATE MATERIALIZED VIEW core.fct_app_events AS
SELECT event_id, occurred_at, 'app.offer_viewed'::text AS event_type, user_pseudo_id, offer_id, NULL::text AS reason
FROM staging.stg_app_offer_viewed
UNION ALL
SELECT event_id, occurred_at, 'app.checkout_started', user_pseudo_id, offer_id, NULL
FROM staging.stg_app_checkout_started
UNION ALL
SELECT event_id, occurred_at, 'order.denied', user_pseudo_id, offer_id, reason
FROM staging.stg_order_denied;

CREATE MATERIALIZED VIEW core.fct_donations AS
SELECT d.event_id, d.occurred_at AS completed_at,
       (d.occurred_at AT TIME ZONE 'Europe/Madrid')::date AS day_local,
       d.offer_id, d.charity_id, f.stall_id, s.market_id, s.category, d.qty,
       d.qty * coalesce(pr.unit_weight_g, 0) / 1000.0 AS kg
FROM staging.stg_donation_completed d
JOIN staging.stg_offers f ON f.offer_id = d.offer_id
JOIN staging.stg_products pr ON pr.product_id = f.product_id
JOIN staging.stg_stalls s ON s.stall_id = f.stall_id;
