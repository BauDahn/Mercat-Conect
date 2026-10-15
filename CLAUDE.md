# Mercat-Conect · instrucciones para Claude

Plataforma pública contra el desperdicio alimentario en los mercados municipales de València. **Proyecto de hackathon** con **demo reproducible en localhost** y datos inventados. Los productores publican el excedente del día con el precio que quieran, los vecinos mayores de edad lo compran desde una app web (PWA) gastando **puntos semanales** y lo recogen en **taquillas refrigeradas**. Telegram queda solo como idea futura para avisos.

> **Empieza por `ESTADO.md`**: qué está hecho, qué está en curso, qué falla y por dónde seguir. El presupuesto de tokens del usuario está **casi agotado**: sé breve, no releas documentos largos y usa modelos baratos (haiku) para lo mecánico y lo visual.

## Fuente de verdad (obligatorio)

- **`ARQUITECTURA.md` manda.** Es larga (~27 000 tokens): **no la leas entera**. Lee `docs/ARQ-MAPA.md` (tabla de secciones con sus líneas) y después solo las secciones de tu tarea con `Read` y `offset`/`limit`.
- Si el código y el documento se contradicen, gana el documento. Si crees que el documento está mal, **no lo edites**: dilo en tu informe y apúntalo en `ESTADO.md`.
- Nombres de tablas, campos y endpoints: **los de las secciones 5.4 y 8.2** y los de `packages/contracts/openapi.yaml`. El contrato de la API se cambia **primero** y la implementación después.
- Las desviaciones ya aceptadas respecto al documento están listadas en `ESTADO.md` (sección "Decisiones y desviaciones").

## Reglas inquebrantables (resumen de la sección 1)

1. **Todo lo externo, detrás de una interfaz** con implementación simulada (demo) y real (producción): `AgeVerifier`, `PaymentProvider`, `LockerTransport`, `Notifier`, `DeliveryProvider`, `Clock`. El dominio no conoce la implementación concreta.
2. **Nada lee la hora del sistema.** Toda la lógica usa `Clock` (`DemoClock` en la demo). Prohibido `datetime.now()`, `time.time()`, `date.today()` y `now()` de SQL en lógica de negocio. Solo `reloj/__init__.py` (`SystemClock`) puede leerla.
3. **Stock y puntos: `UPDATE` condicional atómico** en una sola transacción (sección 10.6). Los pedidos llevan `Idempotency-Key`.
4. **Eventos por *outbox***: se insertan en `domain_events` en la misma transacción que el cambio, con `occurred_at` del `Clock`.
5. **El servidor recalcula siempre** precio, puntos y reglas. Nunca confía en el cliente.
6. **Perfil `demo` solo en `localhost`** y con datos sintéticos (banner "DEMO · datos inventados", correos `.test`). `/demo/*` y `/sim/*` no existen fuera de `DEMO_MODE`.
7. **Datos personales mínimos**: nunca guardar documento ni fecha de nacimiento; solo `person_hash` y "edad verificada". La analítica usa `user_pseudo_id`.
8. **Sin internet en la demo**: fuentes, iconos e imágenes dentro del repo; sin CDN.

## Arrancar y comprobar

```
cp -n .env.example .env
make demo-local        # sin Docker: Postgres embebido + migra + siembra + API :8000 + web :5173
make demo              # con Docker Compose (NO verificado en esta máquina)
make test              # pytest del backend
make reset | seed SEED=43 | e2e | down-local | help
```

- Demo: http://localhost:5173 (web) · http://localhost:8000 (API, `/docs`) · logs en `.demo/*.log`.
- Usuarios de demo (contraseña `demo1234`): `marta@` (con puntos), `luis@` (0 puntos), `ana@` (baja reputación), `nuevo@` (sin verificar), `pepa@` (productora), `gestion@`; todos `@demo.test`.
- Salud rápida: `curl localhost:8000/healthz` → `{"status":"ok","demo_mode":true}`.

## Trampas del entorno (esta máquina)

- **No hay Docker ni servidor PostgreSQL.** `demo-local` usa PostgreSQL embebido con el paquete PyPI `pgserver` (sin `citext` ni `pgcrypto`: la migración 0001 tiene *fallback*). Por eso `apps/api/.python-version` fija **Python 3.12** (las ruedas de `pgserver` son cp312).
- **`node`/`npm` no están en el `PATH` de bash** (nvm perezoso). Antes de usar npm: `export PATH=$HOME/.nvm/versions/node/v24.14.1/bin:$PATH`.
- Alembic se ejecuta desde la raíz: `alembic -c apps/api/alembic.ini upgrade head` (rutas ancladas con `%(here)s`).
- El correo en `demo-local` no tiene buzón: se escribe en `.demo/mail.log` (con Docker sería Mailpit).

## Stack y convenciones

- Backend: Python, FastAPI, SQLAlchemy 2.0, Alembic, psycopg 3, PostgreSQL. Tests: pytest + Hypothesis (el `conftest.py` levanta un Postgres efímero si no hay `DATABASE_URL`).
- Frontend: React, Vite, TypeScript, Tailwind 4, `vite-plugin-pwa`, SSE. Tipos generados del contrato con `npm run gen:api`. Textos en **castellano y valenciano** (`es.json` y `va.json` con las mismas claves; nada incrustado).
- Datos: `data/seed/run.py` (seed determinista, `reset()` reutilizable) y `data/sql/` (capas `raw → staging → core → marts`, vistas abiertas `marts.open_data_*`, pruebas de calidad).
- Código, tablas y campos en **inglés**; textos de interfaz y documentación en **español**.
- Estructura de carpetas: sección 21.1 de `ARQUITECTURA.md`.

## Trabajo multiagente (ahorro de tokens)

La sesión principal **orquesta**; los agentes **implementan** en su carpeta. Definiciones en `.claude/agents/` (inspiradas en [wshobson/agents](https://github.com/wshobson/agents), ver `NOTICE`):

| Agente | Carpeta | Modelo | Para qué |
|---|---|---|---|
| `arq-backend` | `apps/api/` | sonnet | Dominio, reglas, pedidos, pagos, taquillas |
| `arq-frontend` | `apps/web/` | sonnet | PWA, dashboard, productor, gestión, demo |
| `arq-data` | `data/` | sonnet | Seed, capas SQL, calidad, datos abiertos |
| `arq-ops` | raíz, `infra/`, CI | **haiku** | Compose, Makefile, Dockerfiles, CI |
| `arq-qa` | `apps/api/tests/`, `e2e/` | sonnet | Pruebas; no arregla producción |
| `arq-reviewer` | solo lectura | sonnet | Conformidad con `ARQUITECTURA.md` |

**Cómo invocarlos.** Claude Code descubre los agentes al **iniciar la sesión dentro del repo**: abre `claude` en `proyectos/Mercat-Conect` y úsalos por nombre. Si la sesión ya estaba abierta, no aparecen: lanza un agente `general-purpose` con el `model` indicado y el prompt *"Lee `.claude/agents/arq-X.md` y `CLAUDE.md`: son tu rol y tus reglas"*.

**Cómo ahorrar tokens** (por qué existe esta configuración):

- Equipo pequeño y descripciones cortas (el catálogo de agentes pesa contexto en cada sesión; la documentación avisa a partir de ~15 000 tokens).
- Modelo según el coste de la tarea: `haiku` para lo mecánico, `sonnet` para implementar y revisar.
- Cada agente lee solo sus secciones del documento (4–8 k tokens en vez de ~27 k).
- **Contratos primero** (`packages/contracts/`), luego backend, frontend y datos **en paralelo** sin leerse entre sí. Máximo 4 agentes a la vez (`CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS` en `.claude/settings.json`).
- **Informe final ≤ 150 palabras**: qué hizo, qué verificó, qué queda. Sin pegar código ni listados largos.
- Para pedir cambios a un agente que ya conoce el código, **reanúdalo con `SendMessage`** en vez de lanzar otro desde cero.
- No releas lo que acabas de escribir; no hagas búsquedas amplias (rutas conocidas); muestra solo el final de las salidas con errores.

## Límites

- **No hagas commit ni push** salvo que el usuario lo pida expresamente. Último commit subido: `bc823ba` (antes del rediseño del frontend); puede haber trabajo posterior sin commitear.
- No instales nada global ni uses `sudo` (si hace falta, el usuario lo ejecuta con `! comando`).
- No toques `ARQUITECTURA.md` ni los secretos de `.env` (los de `.env.example` son solo de demo).
- Habla con el usuario en **español**.
- En la presentación, **no uses el "4 %" de desperdicio en los mercados** (no hay fuente). Cifras con fuente: ver `docs/fuentes/`.
