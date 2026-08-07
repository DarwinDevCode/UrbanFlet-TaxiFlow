from datetime import datetime

from pydantic import BaseModel, Field


class PoliticaAuthCreate(BaseModel):
    longitud_minima_password: int = Field(ge=6, le=64)
    umbral_intentos_fallidos: int = Field(ge=3, le=20)
    ventana_minutos: int = Field(ge=1, le=180)
    bloqueo_minutos: int = Field(ge=1, le=1440)
    # None = sin vencimiento periódico exigido. Aplica solo a roles de alto
    # privilegio (ver seguridad/service.py::ROLES_ALTO_PRIVILEGIO).
    vencimiento_dias_alto_privilegio: int | None = Field(default=None, ge=1, le=3650)
    vigente_desde: datetime


class PoliticaAuthOut(BaseModel):
    id: str | None
    longitud_minima_password: int
    umbral_intentos_fallidos: int
    ventana_minutos: int
    bloqueo_minutos: int
    vencimiento_dias_alto_privilegio: int | None
    vigente_desde: datetime | None
    vigente_hasta: datetime | None


class PoliticaSeguridadCreate(BaseModel):
    access_token_minutos: int = Field(ge=1, le=1440)
    refresh_token_dias: int = Field(ge=1, le=365)
    refresh_umbral_fallos: int = Field(ge=3, le=20)
    refresh_ventana_minutos: int = Field(ge=1, le=180)
    rbac_umbral_denegaciones: int = Field(ge=3, le=20)
    rbac_ventana_minutos: int = Field(ge=1, le=180)
    rbac_suspension_minutos: int = Field(ge=1, le=1440)
    vigente_desde: datetime


class PoliticaSeguridadOut(BaseModel):
    id: str | None
    access_token_minutos: int
    refresh_token_dias: int
    refresh_umbral_fallos: int
    refresh_ventana_minutos: int
    rbac_umbral_denegaciones: int
    rbac_ventana_minutos: int
    rbac_suspension_minutos: int
    vigente_desde: datetime | None
    vigente_hasta: datetime | None
