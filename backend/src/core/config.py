from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"

    jwt_secret: str = "change-me-in-every-environment-min-32-bytes"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 30

    # replicaSet=rs0: las transacciones multi-documento (core/db_transaction.py)
    # exigen replica set incluso de un solo nodo (ver docker-compose.yml).
    mongo_uri: str = "mongodb://localhost:27017/?replicaSet=rs0"
    mongo_db_name: str = "urbanflet"

    redis_url: str = "redis://localhost:6379/0"

    pocketbase_url: str = "http://localhost:8090"

    clickhouse_host: str = "localhost"
    clickhouse_port: int = 8123
    clickhouse_db: str = "urbanflet_gold"
    clickhouse_user: str = "default"
    clickhouse_password: str = ""

    vapid_public_key: str = ""
    vapid_private_key: str = ""
    vapid_subject: str = "mailto:soporte@urbanflet.local"

    # Directions API de Google no envía cabeceras CORS (a diferencia de
    # Geocoding, que sí) — está pensada para llamarse solo desde servidor.
    # La key vive aquí, nunca en el bundle del cliente; el frontend pide la
    # ruta a nuestra propia API (ver viajes/router_trips.py).
    google_maps_api_key: str = ""

    idempotency_key_ttl_seconds: int = 86400

    # La franja tarifaria se resuelve en hora LOCAL (línea 122 arquitectura:
    # "todos los timestamps se persisten en UTC; la franja tarifaria se
    # resuelve en hora local de la ciudad de operación"). El corte horario SÍ
    # está especificado — CU-O08 (operativo_operaciones_despacho.md, tabla de
    # parámetros de tarifa): "Diurna (05:00-22:00) / Nocturna (22:00-05:00)".
    # Corregido de un default 06:00-19:00 asumido erróneamente en el slice
    # anterior sin haber releído este documento — la ciudad/zona horaria
    # exacta sigue sin estar dada, esa parte del default queda a confirmar.
    zona_horaria_operacion: str = "America/Guayaquil"
    franja_diurna_desde_hora: int = 5
    franja_diurna_hasta_hora: int = 22

    # Orígenes permitidos para los 3 clientes web (línea 5 arquitectura: "tres
    # clientes web"). Puertos de Vite en dev (5173/74/75, ver .claude/launch.json);
    # en despliegue real se sobreescribe por variable de entorno con los
    # dominios reales de web-pasajero/web-conductor/web-interno.
    cors_origins: str = "http://localhost:5173,http://localhost:5174,http://localhost:5175"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    # CU-O11: "cierre del periodo de liquidación (semanal, parámetro de la
    # junta)". El catálogo de `parametros` (tarifa/comisión) es para valores
    # de negocio versionados con vigencia — la duración del periodo es más
    # una configuración de calendario, así que se trata como el resto de los
    # defaults de este archivo (zona_horaria_operacion, franja_diurna_*).
    # Corte CONFIRMADO con el cliente: semana viernes(4)-a-viernes — el
    # periodo arranca un viernes y cierra el viernes siguiente (exclusivo),
    # cubriendo vie-sáb-dom-lun-mar-mié-jue. Índices de weekday() de Python:
    # lunes=0 ... viernes=4 ... domingo=6.
    periodo_liquidacion_dias: int = 7
    periodo_liquidacion_inicio_semana: int = 4

    # CU-O11 A3: "a los 2 periodos con saldo negativo impago... puede
    # suspender el inicio de turno" — la suspensión en sí queda en backlog
    # (decisión ya confirmada, ítem 6 del plan); esto solo gobierna cuántos
    # periodos consecutivos con saldo negativo disparan la alerta.
    liquidacion_periodos_saldo_negativo_alerta: int = 2


@lru_cache
def get_settings() -> Settings:
    return Settings()
