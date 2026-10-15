-- marts: metricas por uso (definiciones exactas de la seccion 16.5).
CREATE MATERIALIZED VIEW marts.offer_performance AS
SELECT offer_id, day_local AS day, market_id, stall_id, category, product_id, status,
       qty_total, units_sold, units_picked_up,
       CASE WHEN qty_total > 0 THEN round(units_picked_up::numeric / qty_total, 4) END AS sell_through,
       is_sold_out, is_closed, round(minutes_to_sell_out::numeric, 1) AS minutes_to_sell_out,
       price_cents, reference_price_cents,
       CASE WHEN reference_price_cents > 0
            THEN round(100.0 * (reference_price_cents - price_cents) / reference_price_cents, 1) END AS discount_pct
FROM core.fct_offers
WHERE is_published;

CREATE MATERIALIZED VIEW marts.sellout_by_category AS
SELECT category,
       count(*) AS offers_closed,
       count(*) FILTER (WHERE is_sold_out) AS offers_sold_out,
       round(count(*) FILTER (WHERE is_sold_out)::numeric / nullif(count(*), 0), 4) AS sellout_rate,
       round(avg(minutes_to_sell_out)::numeric, 1) AS avg_minutes_to_sell_out,
       round(sum(units_picked_up)::numeric / nullif(sum(qty_total), 0), 4) AS sell_through
FROM core.fct_offers
WHERE is_published AND is_closed
GROUP BY category;

CREATE MATERIALIZED VIEW marts.demand_heatmap AS
SELECT market_id, isodow, hour_local,
       count(*) AS orders, sum(units)::int AS units
FROM core.fct_orders
WHERE is_paid
GROUP BY market_id, isodow, hour_local;

CREATE MATERIALIZED VIEW marts.funnel_daily AS
WITH v AS (
  SELECT (occurred_at AT TIME ZONE 'Europe/Madrid')::date AS day,
         count(DISTINCT (offer_id, user_pseudo_id)) FILTER (WHERE event_type = 'app.offer_viewed') AS unique_views,
         count(*) FILTER (WHERE event_type = 'app.checkout_started') AS checkouts,
         count(*) FILTER (WHERE event_type = 'order.denied') AS denied,
         count(*) FILTER (WHERE event_type = 'order.denied' AND reason = 'sin_puntos') AS denied_no_points
  FROM core.fct_app_events GROUP BY 1
), o AS (
  SELECT day_local AS day, count(*) FILTER (WHERE is_paid) AS orders_paid, count(*) AS orders_held
  FROM core.fct_orders GROUP BY 1
)
SELECT coalesce(v.day, o.day) AS day,
       coalesce(v.unique_views, 0) AS unique_views, coalesce(v.checkouts, 0) AS checkouts,
       coalesce(o.orders_held, 0) AS orders_held, coalesce(o.orders_paid, 0) AS orders_paid,
       coalesce(v.denied, 0) AS denied, coalesce(v.denied_no_points, 0) AS denied_no_points,
       round(coalesce(o.orders_paid, 0)::numeric / nullif(v.unique_views, 0), 4) AS conversion
FROM v FULL JOIN o ON o.day = v.day;

CREATE MATERIALIZED VIEW marts.locker_daily AS
WITH lk AS (
  SELECT l.locker_id, l.market_id, m.tz, m.opens_at, m.closes_at, c.n_comp, c.n_cold
  FROM staging.stg_lockers l
  JOIN core.dim_market m USING (market_id)
  JOIN (SELECT locker_id, count(*) AS n_comp, count(*) FILTER (WHERE zone = 'REFRIGERATED') AS n_cold
        FROM staging.stg_compartments GROUP BY locker_id) c USING (locker_id)
), grid AS (
  SELECT lk.*, d.date_key AS day,
         (d.date_key + lk.opens_at) AT TIME ZONE lk.tz AS open_ts,
         (d.date_key + lk.closes_at) AT TIME ZONE lk.tz AS close_ts
  FROM lk CROSS JOIN core.dim_date d WHERE d.is_market_day
), hrs AS (
  SELECT g.*, greatest(0, extract(epoch FROM (least(g.close_ts, core.clock_now()) - g.open_ts)) / 3600.0) AS open_hours
  FROM grid g
), occ AS (
  SELECT g.locker_id, g.day,
         sum(greatest(0, extract(epoch FROM (
               least(coalesce(dp.picked_up_at, dp.valid_until), g.close_ts, core.clock_now())
               - greatest(dp.deposited_at, g.open_ts))) / 3600.0)) AS occupied_hours
  FROM grid g
  JOIN staging.stg_compartments c ON c.locker_id = g.locker_id
  JOIN staging.stg_deposits dp ON dp.compartment_id = c.compartment_id
   AND dp.deposited_at >= g.open_ts AND dp.deposited_at < g.close_ts
  GROUP BY g.locker_id, g.day
), alarms AS (
  SELECT locker_id, (occurred_at AT TIME ZONE 'Europe/Madrid')::date AS day, count(*) AS alarms
  FROM staging.stg_locker_alarm GROUP BY 1, 2
)
SELECT h.locker_id, h.market_id, h.day, h.n_comp, h.n_cold,
       round(h.open_hours::numeric, 2) AS open_hours,
       round((h.n_comp * h.open_hours)::numeric, 2) AS available_hours,
       round(coalesce(o.occupied_hours, 0)::numeric, 2) AS occupied_hours,
       round((h.n_cold * h.open_hours)::numeric, 2) AS cold_hours,
       coalesce(a.alarms, 0)::int AS alarms
FROM hrs h
LEFT JOIN occ o ON o.locker_id = h.locker_id AND o.day = h.day
LEFT JOIN alarms a ON a.locker_id = h.locker_id AND a.day = h.day;

CREATE MATERIALIZED VIEW marts.impact_daily AS
WITH f AS (
  SELECT market_id, day_local AS day,
         sum(qty_total) FILTER (WHERE is_published) AS units_published,
         sum(units_picked_up) AS units_picked_up
  FROM core.fct_offers GROUP BY 1, 2
), o AS (
  SELECT market_id, day_local AS day,
         count(*) FILTER (WHERE is_paid) AS orders_paid,
         sum(kg) FILTER (WHERE status = 'PICKED_UP') AS kg_rescued,
         sum(total_cents) FILTER (WHERE is_revenue) AS revenue_cents
  FROM core.fct_orders GROUP BY 1, 2
), co AS (
  SELECT i.market_id, i.day_local AS day, sum(i.kg * ef.kg_co2e_per_kg) AS co2_avoided_kg
  FROM core.fct_order_items i JOIN core.emission_factor ef USING (category)
  WHERE i.status = 'PICKED_UP' GROUP BY 1, 2
), dn AS (
  SELECT market_id, day_local AS day, sum(kg) AS kg_donated, sum(qty) AS units_donated
  FROM core.fct_donations GROUP BY 1, 2
)
SELECT market_id, day,
       coalesce(f.units_published, 0)::int AS units_published,
       coalesce(f.units_picked_up, 0)::int AS units_picked_up,
       round(coalesce(f.units_picked_up, 0)::numeric / nullif(f.units_published, 0), 4) AS sell_through,
       coalesce(o.orders_paid, 0)::int AS orders_paid,
       round(coalesce(o.kg_rescued, 0)::numeric, 2) AS kg_rescued,
       round(coalesce(dn.kg_donated, 0)::numeric, 2) AS kg_donated,
       coalesce(o.revenue_cents, 0)::int AS revenue_cents,
       round(coalesce(o.revenue_cents, 0) * (1 - core.meta_num('commission_rate')))::int AS producer_income_cents,
       round(coalesce(co.co2_avoided_kg, 0)::numeric, 2) AS co2_avoided_kg
FROM f
FULL JOIN o USING (market_id, day)
FULL JOIN co USING (market_id, day)
FULL JOIN dn USING (market_id, day);

CREATE MATERIALIZED VIEW marts.producer_income_weekly AS
SELECT stall_id, week_key,
       sum(total_cents) FILTER (WHERE is_revenue)::int AS gross_cents,
       round(sum(total_cents) FILTER (WHERE is_revenue) * core.meta_num('commission_rate'))::int AS commission_cents,
       round(sum(total_cents) FILTER (WHERE is_revenue) * (1 - core.meta_num('commission_rate')))::int AS income_cents
FROM core.fct_orders
GROUP BY stall_id, week_key;

-- Una fila con las metricas de 16.5 para el panel de impacto.
CREATE MATERIALIZED VIEW marts.impact_totals AS
SELECT
  core.clock_now() AS as_of,
  (SELECT round(coalesce(sum(kg), 0)::numeric, 1) FROM core.fct_order_items WHERE status = 'PICKED_UP') AS kg_rescued,
  (SELECT round(coalesce(sum(kg), 0)::numeric, 1) FROM core.fct_donations) AS kg_donated,
  (SELECT sum(qty_total)::int FROM core.fct_offers WHERE is_published) AS units_published,
  (SELECT sum(units_picked_up)::int FROM core.fct_offers WHERE is_published) AS units_picked_up,
  (SELECT round(sum(units_picked_up)::numeric / nullif(sum(qty_total), 0), 4)
     FROM core.fct_offers WHERE is_published AND is_closed) AS sell_through,
  (SELECT round(count(*) FILTER (WHERE is_sold_out)::numeric / nullif(count(*), 0), 4)
     FROM core.fct_offers WHERE is_published AND is_closed) AS sellout_rate,
  (SELECT round(avg(minutes_to_sell_out)::numeric, 1) FROM core.fct_offers WHERE is_sold_out) AS avg_minutes_to_sell_out,
  (SELECT round(count(*) FILTER (WHERE is_paid)::numeric
          / nullif((SELECT count(DISTINCT (offer_id, user_pseudo_id)) FROM core.fct_app_events
                    WHERE event_type = 'app.offer_viewed'), 0), 4)
     FROM core.fct_orders) AS conversion,
  (SELECT round(count(*) FILTER (WHERE status = 'NO_SHOW')::numeric / nullif(count(*) FILTER (WHERE is_paid), 0), 4)
     FROM core.fct_orders) AS no_show_rate,
  (SELECT round(count(*) FILTER (WHERE event_type = 'order.denied' AND reason = 'sin_puntos')::numeric
          / nullif(count(*) FILTER (WHERE event_type = 'order.denied')
                   + (SELECT count(*) FROM staging.stg_order_held), 0), 4)
     FROM core.fct_app_events) AS points_denial_rate,
  (SELECT round(sum(units) FILTER (WHERE rn <= ceil(n * 0.1))::numeric / nullif(sum(units), 0), 4)
     FROM (SELECT units, row_number() OVER (ORDER BY units DESC, user_pseudo_id) AS rn, count(*) OVER () AS n
           FROM (SELECT user_pseudo_id, sum(units) AS units FROM core.fct_orders WHERE is_sale GROUP BY 1) u) r
  ) AS top10_purchase_concentration,
  (SELECT round(sum(occupied_hours) / nullif(sum(available_hours), 0), 4) FROM marts.locker_daily) AS locker_utilization,
  (SELECT round(sum(alarms) / nullif(sum(cold_hours), 0) * 1000, 3) FROM marts.locker_daily) AS cold_incidents_per_1000h,
  (SELECT round(coalesce(sum(total_cents), 0) * (1 - core.meta_num('commission_rate')))::int
     FROM core.fct_orders WHERE is_revenue) AS producer_income_cents,
  (SELECT round(coalesce(sum(i.kg * ef.kg_co2e_per_kg), 0)::numeric, 1)
     FROM core.fct_order_items i JOIN core.emission_factor ef USING (category)
     WHERE i.status = 'PICKED_UP') AS co2_avoided_kg;
