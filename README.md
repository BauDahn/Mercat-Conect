# Mercat-Conect

Plataforma pública para reducir el desperdicio alimentario en los mercados municipales de València (Ruzafa, Colón, etc.).

Los puestos publican lo que les sobra cada día a precio reducido, los vecinos reciben un aviso y lo reservan para recogerlo antes del cierre. Lo que no se vende se ofrece a entidades sociales.

> **DEMO · datos inventados.** Los nombres de mercados son reales; puestos, productos, personas y ventas son ficticios.

## Arranque

```bash
cp .env.example .env && make demo    # con Docker: levanta todo, migra y carga datos
make demo-local                      # sin Docker: PostgreSQL embebido (uv + npm)
# Abre http://localhost:5173
```

Sin Docker, `make demo-local` usa PostgreSQL en `127.0.0.1:5433` (datos en `.demo/pgdata`) y deja los logs en `.demo/`. Para parar: `make down-local`. Con Docker: `make down`.

Otros comandos: `make help`. Destacados: `make reset` (vuelve al estado inicial), `make seed SEED=43` (otro conjunto de datos), `make test`, `make e2e`.

Analítica opcional con Metabase: `docker compose --profile analytics up -d metabase` (puerto 3000).

## Documentación

- Arquitectura y decisiones: [ARQUITECTURA.md](ARQUITECTURA.md) (fuente de verdad; mapa de secciones en `docs/ARQ-MAPA.md`).
- Demo y guion: sección 17 de `ARQUITECTURA.md`.

## Estado

En fase de diseño y construcción de la demo.
