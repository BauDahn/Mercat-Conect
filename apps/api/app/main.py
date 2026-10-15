from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.errors import register_handlers
from app.seguridad import SecurityHeadersMiddleware

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def create_app() -> FastAPI:
    s = get_settings()
    hosts = {h.rsplit(":", 1)[0] if h.count(":") == 1 else h for h in s.allowed_hosts_list}
    if s.DEMO_MODE and (not hosts or not hosts <= LOCAL_HOSTS):
        raise RuntimeError("DEMO_MODE exige ALLOWED_HOSTS no vacío y solo localhost")

    from app.admin.router import router as admin
    from app.catalogo.producer_router import router as producer_offers
    from app.catalogo.router import router as offers
    from app.demo.router import router as demo
    from app.identidad.router import router as identidad
    from app.notificaciones.router import router as notificaciones
    from app.opendata.router import router as opendata
    from app.pagos.router import router as pagos
    from app.pedidos.router import router as pedidos
    from app.planificador import Scheduler
    from app.taquillas import service as taq
    from app.taquillas.sim_router import router as sim

    scheduler = Scheduler()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        taq.init_transport()
        try:
            from app.db.session import SessionLocal
            with SessionLocal() as db:
                taq.sync_from_db(db)
        except Exception:  # noqa: BLE001 - la base puede no estar lista aún
            pass
        if s.SCHEDULER_ENABLED:
            scheduler.start()
        yield
        scheduler.stop()

    app = FastAPI(title="Mercat-Conect API", version="0.1.0", lifespan=lifespan)
    register_handlers(app)
    app.add_middleware(SecurityHeadersMiddleware, hsts=s.COOKIE_SECURE)
    if s.DEMO_MODE:
        app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                           allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

    @app.get("/healthz")
    def healthz() -> dict:
        return {"status": "ok", "demo_mode": s.DEMO_MODE}

    for r in (identidad, offers, producer_offers, pedidos, pagos, notificaciones, admin, opendata):
        app.include_router(r)
    if s.DEMO_MODE:  # /demo/* y /sim/* no existen en producción (404)
        app.include_router(demo)
        app.include_router(sim)
    return app


app = create_app()
