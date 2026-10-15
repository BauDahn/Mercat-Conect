-- Datos abiertos (16.9): solo agregados por mercado/dia/categoria; cada celda debe tener al menos
-- `open_data_min_cell` pedidos (parametro en core.meta, por defecto 5). Sin pseudonimos ni ids de cuenta.
CREATE VIEW open_data.rescued_by_market_day AS
SELECT m.name AS market, o.day_local AS day,
       count(*)::int AS orders, sum(o.units)::int AS units, round(sum(o.kg)::numeric, 1) AS kg_rescued
FROM core.fct_orders o JOIN core.dim_market m USING (market_id)
WHERE o.status = 'PICKED_UP'
GROUP BY m.name, o.day_local
HAVING count(*) >= core.meta_num('open_data_min_cell');

CREATE VIEW open_data.rescued_by_category_week AS
SELECT m.name AS market, o.category, o.week_key AS week,
       count(*)::int AS orders, sum(o.units)::int AS units, round(sum(o.kg)::numeric, 1) AS kg_rescued
FROM core.fct_orders o JOIN core.dim_market m USING (market_id)
WHERE o.status = 'PICKED_UP'
GROUP BY m.name, o.category, o.week_key
HAVING count(*) >= core.meta_num('open_data_min_cell');

CREATE VIEW open_data.demand_by_slot AS
SELECT m.name AS market, o.isodow AS weekday, o.hour_local AS hour, count(*)::int AS orders
FROM core.fct_orders o JOIN core.dim_market m USING (market_id)
WHERE o.is_paid
GROUP BY m.name, o.isodow, o.hour_local
HAVING count(*) >= core.meta_num('open_data_min_cell');

CREATE VIEW open_data.donations_by_market_week AS
SELECT m.name AS market, to_char(d.day_local, 'IYYY-"W"IW') AS week,
       count(*)::int AS donations, sum(d.qty)::int AS units, round(sum(d.kg)::numeric, 1) AS kg_donated
FROM core.fct_donations d JOIN core.dim_market m USING (market_id)
GROUP BY m.name, to_char(d.day_local, 'IYYY-"W"IW')
HAVING count(*) >= core.meta_num('open_data_min_cell');

CREATE VIEW open_data.locker_utilization_week AS
WITH u AS (
  SELECT market_id, to_char(day, 'IYYY-"W"IW') AS week,
         round(sum(occupied_hours) / nullif(sum(available_hours), 0), 4) AS utilization
  FROM marts.locker_daily GROUP BY 1, 2
), d AS (
  SELECT market_id, week_key AS week, count(*)::int AS deposits
  FROM core.fct_orders WHERE deposited_at IS NOT NULL GROUP BY 1, 2
)
SELECT m.name AS market, u.week, u.utilization, d.deposits
FROM u JOIN d USING (market_id, week) JOIN core.dim_market m USING (market_id)
WHERE d.deposits >= core.meta_num('open_data_min_cell');

-- Catalogo de conjuntos (para GET /open-data/*.csv).
CREATE VIEW open_data.datasets AS
SELECT * FROM (VALUES
  ('rescued_by_market_day',      'Kg rescatados, unidades y pedidos por mercado y dia', 'mercado, dia'),
  ('rescued_by_category_week',   'Kg rescatados por mercado, categoria y semana ISO',   'mercado, categoria, semana'),
  ('demand_by_slot',             'Pedidos por mercado, dia de la semana y hora',        'mercado, dia semana, hora'),
  ('donations_by_market_week',   'Donaciones a entidades sociales por mercado y semana','mercado, semana'),
  ('locker_utilization_week',    'Utilizacion de taquillas por mercado y semana',       'mercado, semana')
) AS t(dataset, description, grain);
