# ESTADO · Mercat-Conect

> Para el próximo Claude (y para el equipo). **Léelo después de `CLAUDE.md`.**
> Última actualización: 15 de octubre de 2026. Versión de `ARQUITECTURA.md`: 0.3.
> Marcas: ✅ hecho y verificado · 🟡 hecho pero sin verificar del todo · 🔧 en curso al escribir esto · ❌ pendiente.
> Si cambias algo relevante, **actualiza este archivo** antes de terminar.

## 1. Resumen

Hackathon: plataforma pública donde los puestos de los mercados de València publican el excedente del día con precio libre; vecinos **mayores de 18** compran desde una **app web (PWA)** gastando **puntos semanales** y recogen en **taquillas refrigeradas**. Las reglas (coste en puntos, máximo por persona) se ajustan solas según demanda y hora. Telegram es solo una idea futura para avisos. Todo lo externo (edad, pago, taquillas, avisos, reloj) está **simulado detrás de interfaces**; la demo corre en localhost con datos inventados.

El repo se construyó con un equipo de agentes siguiendo `ARQUITECTURA.md`. **No hay nada commiteado** salvo el commit inicial: todo el trabajo está sin commitear (el usuario decide cuándo).

## 2. Cómo arrancarlo (comprobado el 15-oct)

```
export PATH=$HOME/.nvm/versions/node/v24.14.1/bin:$PATH   # node no está en el PATH de bash
cp -n .env.example .env
make demo-local        # Postgres embebido (pgserver) + migra + siembra + API :8000 + web :5173
```

- Web http://localhost:5173 · API http://localhost:8000 (`/docs`) · logs en `.demo/`.
- Usuarios (contraseña `demo1234`, dominio `@demo.test`): `marta` (20 puntos), `luis` (0 puntos), `ana` (baja reputación), `nuevo` (sin verificar), `pepa` (productora), `gestion`.
- Apagar: `make down-local`. Reiniciar datos: `POST /demo/reset` o `make seed`.
- ✅ Comprobado a mano: `healthz`, login con cookie, `GET /me`, `GET /offers` (24 ofertas con `decision`), `GET /me/points`, web sirve 200.

## 3. Qué hay y en qué estado

| Área | Estado | Notas |
|---|---|---|
| `ARQUITECTURA.md` v0.3 + `docs/ARQ-MAPA.md` | ✅ | 24 secciones, 17 diagramas Mermaid (sin renderizar en local; revisar en GitHub) |
| Contratos `packages/contracts/` | ✅ | `openapi.yaml` (3.1) y `events.schema.json`; el contrato se cambia antes que el código |
| Backend `apps/api` | ✅ | **46 pruebas en verde** (reglas, Hypothesis, compra atómica con 60 hilos, mismo usuario en paralelo, idempotencia, flujo completo, caducidades, alarma de frío, reloj estricto) |
| Frontend `apps/web` | ✅/🟡 | `build` y `lint` pasan. **Visto con Chromium headless** (dashboard anónimo y detalle de oferta con sesión): renderiza bien, sin errores de página, proxy `/api` y login funcionan. **No recorrido el guion completo**; falta el mapa. A vigilar: en móvil la barra inferior fija puede tapar el botón "Reservar y pagar" en la página de oferta, y el título "Cerca de ti" se aprieta junto al selector "Ordenar" |
| Datos `data/` | ✅ | Seed determinista (hash idéntico), 4 semanas de historial, capas SQL, calidad OK, claves de eventos alineadas con el backend |
| Arranque (Makefile, compose, CI) | ✅/🟡 | `make demo-local` ✅ (reiniciado con el código final); **Docker Compose sin ejecutar** (no hay Docker aquí) |
| Pruebas e2e (`e2e/`, Playwright) | 🟡 | Escritas (`e2e/tests/guion.spec.ts`) pero **nunca ejecutadas con éxito**: el agente QA fue detenido por el usuario antes de terminar |
| Configuración multiagente (`.claude/`) | ✅ | 6 agentes `arq-*`, `settings.json`, `NOTICE` |
| Telegram | ❌ | Fuera del alcance del hackathon; queda como `Notifier` futuro (sección 14.4) |
| Mapa en el dashboard, Web Push real, Metabase | ❌ | "Podría" de §2.1 |
| `LICENSE` (EUPL-1.2) | ❌ | Falta el texto de la licencia |

**Verificado a mano el 15-oct con la demo reiniciada:** `healthz`, login, `GET /me`, `GET /offers` con `decision`, `POST /demo/reset` (204), y el recorrido de compra: pedido (puntos 20→16, stock 8→6), misma `Idempotency-Key` devuelve el mismo pedido, pago simulado → `PAID`.

## 4. Decisiones y desviaciones respecto a ARQUITECTURA.md

Aceptadas durante la construcción; si las cambias, actualiza el documento aparte (no lo edites sin que el usuario lo pida).

- **PostgreSQL embebido en `demo-local`** (`pgserver`, sin `citext`/`pgcrypto`): la migración 0001 crea un dominio `citext AS text` si la extensión no existe; el correo se normaliza a minúsculas en la app. `apps/api/.python-version` = 3.12 por las ruedas de `pgserver`.
- **Migración 0002** `app_settings` (barandillas municipales) y tablas extra en 0001: `sessions`, `payouts`, `charities`, `donations`, `deliveries`.
- **Rutas añadidas al contrato** (§5.4 era orientativo): `/open-data/{name}.csv`, `/sim/lockers/{id}/compartments/{slot}/{action}`, `GET /me`, `GET /producer/stalls`, `GET /products`, `POST /producer/orders/{id}/reject`, `POST /sim/lockers/{id}/network`, `GET /admin/donations`.
- **Rutas añadidas tras la revisión**: `DELETE /me` (anonimiza; 409 si hay pedidos en curso), `POST /producer/offers/{id}/publish`, `DELETE /producer/offers/{id}` (solo borradores), `GET /producer/offers`, `GET /admin/calidad`, `GET /offers/{id}?qty=N`; `/stream` responde 429 con más de 5 conexiones por usuario; evento `producer.penalized`.
- **`GET /offers` incluye `decision` por oferta** si hay sesión (evita N llamadas).
- **Verificación de edad simulada**: el callback recibe `token` = DNI inventado y `kind` = `adult|minor`. Un mismo DNI en dos cuentas se rechaza.
- **`DemoClock` es un reloj *offset* que corre en tiempo real** desde `DEMO_CLOCK_START`; `/demo/clock` admite `set`, `advance_seconds` y `paused`. Las pruebas usan reloj pausado.
- **Vistas abiertas**: `marts.open_data_*`; el backend solo lee esas (503 si no existe el esquema, 404 si falta la vista).
- **Perfiles de oferta**: `LIBRE`, `EQUILIBRADO`, `ESTRICTO`, `PERSONALIZADO` (mayúsculas).
- **`LOCKER_TRANSPORT`** acepta `sim` e `inprocess` (por defecto `inprocess`).
- **Avisos**: `OFFER_MATCH` agrupados en ventana de 5 min con tope de 5 al día.
- **Alembic anclado** con `%(here)s` para ejecutarlo desde la raíz.
- **Seed**: contraseña `demo1234` con Argon2 y sal fija (solo demo); `person_hash` con HMAC y `PERSON_HASH_KEY`.

## 5. Revisión de conformidad: resuelta

El revisor (`arq-reviewer`) encontró 13 incumplimientos; **los 13 están corregidos** y verificados por el backend (46 pruebas) y por una ejecución propia de `make test`. Resumen de lo corregido, por si hace falta volver a mirar:

- Claves de eventos del seed/staging alineadas con las que emite el backend; los eventos reales llegan a `core.fct_orders` y `marts.funnel_daily`.
- Salvaguarda demo: `python -m app` escucha en `127.0.0.1` salvo `BIND_HOST`; `ALLOWED_HOSTS` vacío o no local impide arrancar. Compose publica todos los puertos en `127.0.0.1`.
- `pickup_code` fuera del correo y del log; solo en la bandeja mientras el pedido está `IN_LOCKER`.
- `LockerTransport` completo; capacidad y `max_units` dentro de la transacción (advisory locks + `FOR UPDATE`); pagos con comprobación de `hold_expires_at`.
- Ofertas §9.1: `POST /producer/offers/{id}/publish`, `DELETE` de borradores y `GET /producer/offers`.
- Refresco de marts al mover el reloj y cada minuto; `GET /admin/calidad`.
- Penalización al productor (`users.reputation` −0,05 y evento `producer.penalized`), cabeceras de seguridad, límite de 5 SSE por usuario, `DELETE /me`, `DeliveryProvider` con `FakeDeliveryProvider`, test estricto del reloj, y `conftest.py` con *teardown* (ya no deja Postgres huérfanos).
- `OfferPage` pide el coste al servidor con `GET /offers/{id}?qty=N`.

Si se vuelve a lanzar `arq-reviewer`, pídele solo lo **nuevo** desde esta fecha.

## 6. Pendiente (por prioridad)

1. **Recorrer el guion de la sección 17.6 (12 escenas) en un navegador** y comprobar el aspecto contra los wireframes de §6.2/6.3. Ya se vieron el dashboard y el detalle de oferta (capturas headless OK); faltan compra, productor, taquilla virtual, demo y gestión. Atención al solape de la barra inferior con el botón de reservar en móvil.
2. **Pruebas e2e** (`make e2e`, escenas 1, 4, 5, 6, 7 y 9): están escritas pero nunca se ejecutaron con éxito. Necesitan la demo en marcha. En esta máquina `cd e2e && npm ci && npx playwright install chromium` **funciona** (descarga un build de ubuntu24.04). Con sesión iniciada la página mantiene el SSE abierto: usa `waitUntil: 'load'`, no `'networkidle'`. El agente QA fue detenido a medias; su único hallazgo (`/demo/reset` daba 500) **no se reproduce** con el código final (devuelve 204): era un servidor desactualizado.
3. **Docker Compose**: nunca ejecutado. Versiones de imagen (`postgres:16.4`, `mailpit v1.20.2`, `metabase v0.50.30`) y de `uv`, Python y Node en los Dockerfiles **sin verificar**. Probar `make demo` en una máquina con Docker. Con Docker, el Python del contenedor debe ser 3.12 (igual que `.python-version`).
4. **`LICENSE`** EUPL-1.2 y revisar `NOTICE`.
5. **Vídeo de respaldo y ensayo del guion** (riesgo R12).
6. **Valenciano**: `va.json` tiene las mismas claves que `es.json`; **pasar revisión humana** de la calidad de la traducción.
7. **Probar `open_data` con una venta real hasta `PICKED_UP`** (hasta ahora solo se probó el lado de pedidos retenidos).
8. Extras: mapa del dashboard, canal de Telegram (~15 líneas), Web Push real, pasar `path_separator=os` en `alembic.ini` (aviso de deprecación inocuo).
9. **Renderizar los diagramas Mermaid** de `ARQUITECTURA.md` en GitHub y corregir si alguno falla.
10. **Limpieza de Postgres de prueba antiguos** (de antes del *teardown*): `pkill -f 'postgres -D /tmp/mc_pg_'`. No toca el de la demo (`.demo/pgdata`).

## 7. Cómo seguir con agentes

- Usa los agentes `arq-*` (ver tabla en `CLAUDE.md`): **abre `claude` dentro del repo** para que se carguen por nombre; en una sesión ya abierta, usa `general-purpose` con el `model` correspondiente y pídele que lea su archivo de `.claude/agents/`.
- Orden recomendado: contrato → (backend ∥ frontend ∥ datos) → QA → revisor. Para cambios pequeños en código que un agente ya conoce, reanúdalo con `SendMessage`.
- Antes de lanzar `arq-reviewer` de nuevo, pásale la lista de la sección 5 para que compruebe qué sigue abierto.

## 8. Qué NO hacer

- No commitear ni hacer push sin que el usuario lo pida. No usar `sudo` (que lo ejecute el usuario con `! comando`).
- No editar `ARQUITECTURA.md` por cuenta propia. No cambiar nombres de tablas/campos/endpoints sin tocar antes el contrato.
- No presentar el "4 %" de desperdicio en mercados como dato (no hay fuente). Cifras con fuente en `docs/fuentes/Sobra_al_Mercat_fuentes.pdf`: estudio CSIC-UPV de 2025 (>140 000 t/año en València y su área), Eurostat 2024, Ley 1/2025.
- No usar los resultados del panel de impacto como evidencia real: son de datos inventados.

## 9. Archivos clave

| Qué | Dónde |
|---|---|
| Arquitectura y mapa de secciones | `ARQUITECTURA.md`, `docs/ARQ-MAPA.md` |
| Instrucciones para Claude | `CLAUDE.md`, `.claude/agents/`, `.claude/settings.json` |
| Contratos | `packages/contracts/openapi.yaml`, `packages/contracts/events.schema.json` |
| Backend | `apps/api/app/{identidad,catalogo,reglas,pedidos,pagos,taquillas,notificaciones,donaciones,reloj,demo,eventos,opendata,admin}/` |
| Motor de reglas | `apps/api/app/reglas/engine.py` |
| Compra atómica | `apps/api/app/pedidos/service.py` |
| Ciclo de vida de pedidos | `apps/api/app/pedidos/lifecycle.py` |
| Frontend | `apps/web/src/` (páginas en `pages/`, textos en `i18n/`) |
| Seed y capas SQL | `data/seed/run.py`, `data/seed/generate.py`, `data/sql/` |
| Arranque | `Makefile`, `scripts/localdb.py`, `docker-compose.yml`, `.env.example` |
| Propuesta y fuentes (PDF) | `docs/Sobra_al_Mercat_propuesta.pdf`, `docs/fuentes/Sobra_al_Mercat_fuentes.pdf` |
