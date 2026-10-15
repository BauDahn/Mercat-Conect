-- Ingesta idempotente outbox -> raw (clave event_id) y refresco de core/marts en orden de dependencias.
INSERT INTO raw.events (event_id, occurred_at, event_type, aggregate_id, payload)
SELECT id, occurred_at, event_type, aggregate_id, payload FROM public.domain_events
ON CONFLICT (event_id) DO NOTHING;

REFRESH MATERIALIZED VIEW core.dim_market;
REFRESH MATERIALIZED VIEW core.dim_stall;
REFRESH MATERIALIZED VIEW core.dim_product;
REFRESH MATERIALIZED VIEW core.dim_date;
REFRESH MATERIALIZED VIEW core.fct_offers;
REFRESH MATERIALIZED VIEW core.fct_orders;
REFRESH MATERIALIZED VIEW core.fct_order_items;
REFRESH MATERIALIZED VIEW core.fct_locker_readings;
REFRESH MATERIALIZED VIEW core.fct_app_events;
REFRESH MATERIALIZED VIEW core.fct_donations;
REFRESH MATERIALIZED VIEW marts.offer_performance;
REFRESH MATERIALIZED VIEW marts.sellout_by_category;
REFRESH MATERIALIZED VIEW marts.demand_heatmap;
REFRESH MATERIALIZED VIEW marts.funnel_daily;
REFRESH MATERIALIZED VIEW marts.locker_daily;
REFRESH MATERIALIZED VIEW marts.impact_daily;
REFRESH MATERIALIZED VIEW marts.producer_income_weekly;
REFRESH MATERIALIZED VIEW marts.impact_totals;
