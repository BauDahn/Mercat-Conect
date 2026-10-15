-- Pruebas de calidad (16.6). Devuelve filas SOLO si algo falla: (test, detail).
-- Una sola sentencia SELECT; apply.py la instala como vista marts.quality_failures.
SELECT test, detail FROM (
  -- Unicidad y no nulos
  SELECT 'unique_order_id'::text AS test, ('order_id=' || coalesce(order_id::text, 'NULL'))::text AS detail
    FROM core.fct_orders GROUP BY order_id HAVING count(*) > 1 OR order_id IS NULL
  UNION ALL
  SELECT 'unique_event_id', ('event_id=' || coalesce(event_id::text, 'NULL'))
    FROM raw.events GROUP BY event_id HAVING count(*) > 1 OR event_id IS NULL
  UNION ALL
  SELECT 'event_not_null_fields', 'event_id=' || event_id::text
    FROM raw.events WHERE occurred_at IS NULL OR event_type IS NULL OR payload IS NULL
  -- Integridad referencial
  UNION ALL
  SELECT 'order_without_items', o.id::text
    FROM public.orders o WHERE NOT EXISTS (SELECT 1 FROM public.order_items i WHERE i.order_id = o.id)
  UNION ALL
  SELECT 'order_item_without_offer', i.order_id::text
    FROM public.order_items i LEFT JOIN public.offers f ON f.id = i.offer_id WHERE f.id IS NULL
  UNION ALL
  SELECT 'order_without_stall_or_user', o.id::text
    FROM public.orders o
    LEFT JOIN public.stalls s ON s.id = o.stall_id
    LEFT JOIN public.users u ON u.id = o.user_id
    WHERE s.id IS NULL OR u.id IS NULL
  -- Reglas de negocio
  UNION ALL
  SELECT 'negative_or_excess_stock', id::text
    FROM public.offers WHERE qty_available < 0 OR qty_available > qty_total
  UNION ALL
  SELECT 'oversold_offer', f.id::text
    FROM public.offers f
    JOIN (SELECT i.offer_id, sum(i.qty) AS q FROM public.order_items i JOIN public.orders o ON o.id = i.order_id
          WHERE o.status IN ('HELD','PAID','PREPARING','IN_LOCKER','PICKED_UP','NO_SHOW') GROUP BY i.offer_id) s
      ON s.offer_id = f.id
    WHERE s.q > f.qty_total
  UNION ALL
  SELECT 'points_overspent', user_id::text || ' ' || week_key
    FROM public.points_week WHERE spent > allowance OR spent < 0
  UNION ALL
  SELECT 'points_ledger_mismatch', pw.user_id::text || ' ' || pw.week_key
    FROM public.points_week pw
    WHERE pw.spent <> -coalesce((SELECT sum(l.delta) FROM public.points_ledger l
                                 WHERE l.user_id = pw.user_id AND l.week_key = pw.week_key), 0)
  UNION ALL
  SELECT 'ledger_without_points_week', l.user_id::text || ' ' || l.week_key
    FROM public.points_ledger l
    WHERE NOT EXISTS (SELECT 1 FROM public.points_week pw WHERE pw.user_id = l.user_id AND pw.week_key = l.week_key)
    GROUP BY l.user_id, l.week_key
  UNION ALL
  SELECT 'deposit_before_payment', d.order_id::text
    FROM public.deposits d JOIN public.payments p ON p.order_id = d.order_id
    WHERE d.deposited_at < p.created_at
  UNION ALL
  SELECT 'pickup_before_deposit', d.order_id::text
    FROM public.deposits d WHERE d.picked_up_at IS NOT NULL AND (d.deposited_at IS NULL OR d.picked_up_at < d.deposited_at)
  UNION ALL
  SELECT 'picked_up_without_deposit', o.id::text
    FROM public.orders o LEFT JOIN public.deposits d ON d.order_id = o.id
    WHERE o.status = 'PICKED_UP' AND (d.deposited_at IS NULL OR d.picked_up_at IS NULL)
  UNION ALL
  SELECT 'picked_up_event_without_deposited_event', p.order_id::text
    FROM staging.stg_order_picked_up p
    WHERE NOT EXISTS (SELECT 1 FROM staging.stg_order_deposited d WHERE d.order_id = p.order_id)
  UNION ALL
  SELECT 'picked_up_order_without_event', o.id::text
    FROM public.orders o
    WHERE o.status = 'PICKED_UP' AND NOT EXISTS (SELECT 1 FROM staging.stg_order_picked_up p WHERE p.order_id = o.id)
  -- Reconciliacion de pagos (en la demo, contra el pago simulado)
  UNION ALL
  SELECT 'payment_reconciliation', o.id::text
    FROM public.orders o LEFT JOIN public.payments p ON p.order_id = o.id
    WHERE (o.status NOT IN ('HELD','EXPIRED_HOLD') AND (p.id IS NULL OR p.amount_cents <> o.total_cents))
       OR (o.status IN ('HELD','EXPIRED_HOLD') AND p.id IS NOT NULL)
  UNION ALL
  SELECT 'paid_events_vs_payments', 'events=' || e.n || ' payments=' || p.n
    FROM (SELECT count(*) AS n FROM staging.stg_order_paid) e, (SELECT count(*) AS n FROM public.payments) p
    WHERE e.n <> p.n
  -- Sincronia de capas
  UNION ALL
  SELECT 'outbox_not_in_raw', 'missing=' || count(*)
    FROM public.domain_events d WHERE NOT EXISTS (SELECT 1 FROM raw.events r WHERE r.event_id = d.id)
    HAVING count(*) > 0
  UNION ALL
  SELECT 'core_stale', 'orders=' || a.n || ' fct_orders=' || b.n
    FROM (SELECT count(*) AS n FROM public.orders) a, (SELECT count(*) AS n FROM core.fct_orders) b WHERE a.n <> b.n
  UNION ALL
  SELECT 'core_stale', 'offers=' || a.n || ' fct_offers=' || b.n
    FROM (SELECT count(*) AS n FROM public.offers) a, (SELECT count(*) AS n FROM core.fct_offers) b WHERE a.n <> b.n
  -- Frescura: en horario de mercado, ultimo evento a menos de N minutos del Clock
  UNION ALL
  SELECT 'event_freshness', 'last_event=' || coalesce(e.mx::text, 'NULL') || ' clock=' || core.clock_now()::text
    FROM (SELECT max(occurred_at) AS mx FROM raw.events) e
    WHERE EXISTS (SELECT 1 FROM staging.stg_markets m
                  WHERE (core.clock_now() AT TIME ZONE 'Europe/Madrid')::time BETWEEN m.opens_at AND m.closes_at)
      AND (e.mx IS NULL OR e.mx < core.clock_now() - make_interval(mins => core.meta_num('freshness_minutes')::int))
  -- Volumen: pico o caida anomala frente a la semana anterior
  UNION ALL
  SELECT 'volume_anomaly', 'last7=' || v.a || ' prev7=' || v.b
    FROM (SELECT count(*) FILTER (WHERE occurred_at >= core.clock_now() - interval '7 days' AND occurred_at < core.clock_now()) AS a,
                 count(*) FILTER (WHERE occurred_at >= core.clock_now() - interval '14 days'
                                    AND occurred_at < core.clock_now() - interval '7 days') AS b
          FROM staging.stg_order_held) v
    WHERE v.b >= 20 AND (v.a::numeric / v.b > 3 OR v.a::numeric / v.b < 0.33)
  -- Privacidad: ningun evento lleva id de cuenta, correo ni person_hash
  UNION ALL
  SELECT 'pii_in_events', 'event_id=' || e.event_id
    FROM raw.events e
    WHERE EXISTS (SELECT 1 FROM public.users u WHERE position(u.id::text in e.payload::text) > 0
                                                   OR position(lower(u.email::text) in lower(e.payload::text)) > 0)
       OR EXISTS (SELECT 1 FROM public.user_identities i WHERE position(encode(i.person_hash, 'hex') in e.payload::text) > 0)
       OR e.payload ?| ARRAY['email','user_id','person_hash','display_name']
  -- Datos abiertos: ninguna celda bajo el umbral minimo
  UNION ALL
  SELECT 'open_data_small_cell', 'rescued_by_market_day ' || market || ' ' || day FROM open_data.rescued_by_market_day
    WHERE orders < core.meta_num('open_data_min_cell')
  UNION ALL
  SELECT 'open_data_small_cell', 'rescued_by_category_week ' || market || ' ' || category || ' ' || week FROM open_data.rescued_by_category_week
    WHERE orders < core.meta_num('open_data_min_cell')
  UNION ALL
  SELECT 'open_data_small_cell', 'demand_by_slot ' || market || ' ' || weekday || ' ' || hour FROM open_data.demand_by_slot
    WHERE orders < core.meta_num('open_data_min_cell')
  UNION ALL
  SELECT 'open_data_small_cell', 'donations_by_market_week ' || market || ' ' || week FROM open_data.donations_by_market_week
    WHERE donations < core.meta_num('open_data_min_cell')
  UNION ALL
  SELECT 'open_data_small_cell', 'locker_utilization_week ' || market || ' ' || week FROM open_data.locker_utilization_week
    WHERE deposits < core.meta_num('open_data_min_cell')
) failures
