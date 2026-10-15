from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql+psycopg://mercat:mercat@localhost:5432/mercat"
    DEMO_MODE: bool = True
    ALLOWED_HOSTS: str = "localhost,127.0.0.1"
    DEMO_SEED: int = 42
    DEMO_CLOCK_START: str = "2026-10-16T12:00:00+02:00"
    AGE_VERIFIER: str = "fake"
    PAYMENT_PROVIDER: str = "fake"
    LOCKER_TRANSPORT: str = "inprocess"
    NOTIFIERS: str = "inapp,email"
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 1025
    MAIL_LOG_PATH: str = ""  # vacío = <raíz del repo>/.demo/mail.log
    SMTP_FROM: str = "avisos@mercat-conect.test"
    SECRET_KEY: str = "dev-only-change-me"
    PERSON_HASH_KEY: str = "dev-only-change-me-too"

    # Planificador interno y reglas de negocio (supuestos de ARQUITECTURA.md)
    SCHEDULER_ENABLED: bool = True
    SCHEDULER_INTERVAL_SECONDS: float = 1.0
    HOLD_MINUTES: int = 10            # sección 9.2 / 11.1
    PREP_MINUTES: int = 20            # sección 11.1 (supuesto)
    PICKUP_GRACE_MINUTES: int = 15    # ventana mínima de retirada tras depositar (supuesto)
    SESSION_TTL_HOURS: int = 168
    COOKIE_SECURE: bool = False
    DEFAULT_ALLOWANCE: int = 100      # sección 10.6 (supuesto)
    TEMP_ALARM_CELSIUS: float = 5.0   # sección 13.5 (supuesto)
    TEMP_ALARM_MINUTES: int = 15
    DAILY_NOTIFICATION_CAP: int = 5   # sección 14.2
    FAKE_PAYMENT_DELAY_SECONDS: int = 30
    UPLOAD_DIR: str = ""              # vacío = <raíz del repo>/.demo/uploads
    MAX_UPLOAD_BYTES: int = 2 * 1024 * 1024
    BIND_HOST: str = ""               # solo Docker; vacío = 127.0.0.1 en demo
    SSE_MAX_PER_USER: int = 5
    PRODUCER_PENALTY: float = 0.05
    ANALYTICS_REFRESH_SECONDS: int = 60
    DEMO_LOCATION: str = "39.4893,-0.3585"  # Plaça de Benimaclet (ubicación simulada del vecino)

    @property
    def demo_location(self) -> tuple[float, float]:
        a, b = self.DEMO_LOCATION.split(",")
        return float(a), float(b)

    @property
    def allowed_hosts_list(self) -> list[str]:
        return [h.strip() for h in self.ALLOWED_HOSTS.split(",") if h.strip()]

    @property
    def notifiers_list(self) -> list[str]:
        return [n.strip() for n in self.NOTIFIERS.split(",") if n.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
