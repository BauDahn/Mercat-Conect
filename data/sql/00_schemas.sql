-- Capas del almacen analitico (seccion 16.4). Idempotente: staging/core/marts/open_data
-- se recrean enteras; raw se conserva (es la ingesta inmutable de eventos).
DROP SCHEMA IF EXISTS open_data CASCADE;
DROP SCHEMA IF EXISTS marts CASCADE;
DROP SCHEMA IF EXISTS core CASCADE;
DROP SCHEMA IF EXISTS staging CASCADE;

CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA staging;
CREATE SCHEMA core;
CREATE SCHEMA marts;
CREATE SCHEMA open_data;

-- Parametros del almacen. Nada lee now(): la hora es la del Clock (clock_now).
CREATE TABLE core.meta (
  key   text PRIMARY KEY,
  value text NOT NULL
);

CREATE FUNCTION core.clock_now() RETURNS timestamptz
  LANGUAGE sql STABLE AS $$ SELECT value::timestamptz FROM core.meta WHERE key = 'clock_now' $$;

CREATE FUNCTION core.meta_num(k text) RETURNS numeric
  LANGUAGE sql STABLE AS $$ SELECT value::numeric FROM core.meta WHERE key = k $$;

-- Factores de emision (16.5: "por definir"). Valores de DEMO, no citables como dato real.
CREATE TABLE core.emission_factor (
  category          text PRIMARY KEY,
  kg_co2e_per_kg    numeric NOT NULL,
  source            text NOT NULL
);
INSERT INTO core.emission_factor (category, kg_co2e_per_kg, source) VALUES
  ('fruta',        0.9, 'SUPUESTO DEMO (por definir: citar fuente oficial antes de publicar)'),
  ('verdura',      0.6, 'SUPUESTO DEMO (por definir: citar fuente oficial antes de publicar)'),
  ('pescado',      5.0, 'SUPUESTO DEMO (por definir: citar fuente oficial antes de publicar)'),
  ('carne',       12.0, 'SUPUESTO DEMO (por definir: citar fuente oficial antes de publicar)'),
  ('panaderia',    1.3, 'SUPUESTO DEMO (por definir: citar fuente oficial antes de publicar)'),
  ('charcuteria',  8.0, 'SUPUESTO DEMO (por definir: citar fuente oficial antes de publicar)'),
  ('lacteos',      3.0, 'SUPUESTO DEMO (por definir: citar fuente oficial antes de publicar)'),
  ('despensa',     1.5, 'SUPUESTO DEMO (por definir: citar fuente oficial antes de publicar)');
