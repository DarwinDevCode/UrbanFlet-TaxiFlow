from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, model_validator

TipoPropietarioDocumento = Literal["CONDUCTOR", "VEHICULO"]
EstadoSolicitud = Literal[
    "BORRADOR", "ENVIADA", "EN_VERIFICACION", "OBSERVADA", "APROBADA", "RECHAZADA", "EXPIRADA"
]
# CU-T01/T02 (specs/nivel-tactico/tactico_captacion.md) -- canal de
# adquisición del socio/pasajero, usado por los informes tácticos de
# conversión y altas por canal. Default "web" para altas que no declaran
# canal explícito (ninguno de los 2 frontends lo pedía hasta ahora).
Canal = Literal["app", "web", "referido", "campana"]


class PasajeroRegistroRequest(BaseModel):
    nombre: str = Field(min_length=1, max_length=200)
    telefono: str | None = Field(default=None, min_length=7, max_length=20)
    email: EmailStr | None = None
    password: str = Field(min_length=8, max_length=128)
    version_consentimiento: str = Field(min_length=1)
    canal: Canal = "web"

    @model_validator(mode="after")
    def _requiere_telefono_o_email(self) -> "PasajeroRegistroRequest":
        if not self.telefono and not self.email:
            raise ValueError("Debes registrarte con al menos un teléfono o un correo")
        return self


class PasajeroRegistroResponse(BaseModel):
    usuario_id: str
    estado: str


class DocumentoInput(BaseModel):
    tipo: str
    propietario_tipo: TipoPropietarioDocumento
    # Antes `url_objeto`/`hash_archivo` de texto libre, confiados tal cual
    # del cliente -- mismo patrón ya corregido en `documento_renovacion`
    # (ver cumplimiento/schemas.py::RenovacionSubirRequest): ahora el
    # cliente sube el archivo real primero (`POST /archivos`, contexto
    # "documento_postulacion") y solo manda el id devuelto -- el hash real
    # se resuelve del lado del servidor, nunca se confía en el del cliente.
    archivo_id: str
    fecha_emision: date | None = None
    fecha_vencimiento: date | None = None


class DocumentoSolicitudOut(BaseModel):
    tipo: str
    propietario_tipo: TipoPropietarioDocumento
    archivo_id: str
    fecha_emision: date | None
    fecha_vencimiento: date | None


class VehiculoInput(BaseModel):
    # Bitácora de revisión (2026-08-26, hallazgo #2): sin cota alguna hasta
    # ahora -- mismos límites ya usados por el endpoint de edición
    # (`mantenimiento/schemas.py::VehiculoEditarRequest`), para no divergir.
    placa: str
    marca: str
    modelo: str
    anio: int = Field(ge=1950, le=2100)
    color: str
    capacidad: int = Field(ge=1, le=20)


class SolicitudCrearRequest(BaseModel):
    nombre: str = Field(min_length=1, max_length=200)
    telefono: str | None = Field(default=None, min_length=7, max_length=20)
    email: EmailStr | None = None
    password: str = Field(min_length=8, max_length=128)
    cedula: str = Field(min_length=5, max_length=20)
    licencia_numero: str
    vehiculo: VehiculoInput
    documentos: list[DocumentoInput] = Field(default_factory=list)
    enviar: bool = True
    canal: Canal = "web"

    @model_validator(mode="after")
    def _requiere_telefono_o_email(self) -> "SolicitudCrearRequest":
        if not self.telefono and not self.email:
            raise ValueError("Debes postular con al menos un teléfono o un correo")
        return self


class SolicitudOut(BaseModel):
    id: str
    usuario_id: str
    usuario_nombre: str | None = None
    cedula: str
    # Nunca se habían expuesto por API pese a que se piden al crear la
    # solicitud (`SolicitudCrearRequest`) -- sin esto, ni la pantalla de
    # verificación podía mostrarlos, ni esta misma ronda podía construir una
    # corrección sobre un dato que la UI no mostraba en ningún lado.
    licencia_numero: str
    vehiculo: VehiculoInput
    estado: EstadoSolicitud
    fecha_envio: datetime | None
    fecha_decision: datetime | None
    revision_reforzada: bool
    motivo_rechazo: str | None
    canal: str | None = None
    # Gestión documental en la postulación (Fase 2): visible en la pantalla
    # de revisión de Captación para que quien decide vea qué se subió, no
    # solo que "hay documentos". Vacío para solicitudes viejas que nunca
    # cargaron nada -- no es un error, es el estado real previo a esta ronda.
    documentos: list[DocumentoSolicitudOut] = Field(default_factory=list)


class SolicitudDecisionRequest(BaseModel):
    decision: Literal["APROBADA", "RECHAZADA", "OBSERVADA"]
    motivo: str | None = None


# Gestión documental en la postulación, Fase 1: separado de
# `SolicitudCrearRequest` porque el archivo real solo puede subirse DESPUÉS
# de que la cuenta exista (POST /archivos exige un actor autenticado, y la
# cuenta se crea recién al enviar la solicitud) -- el flujo real es
# crear_solicitud(enviar=False) -> login -> subir cada archivo -> este
# endpoint, que adjunta los documentos ya subidos y recién ahí pasa la
# solicitud a ENVIADA (mismo efecto que `enviar=True` de siempre, solo que
# en dos pasos en vez de uno).
class EnviarSolicitudConDocumentosRequest(BaseModel):
    documentos: list[DocumentoInput] = Field(min_length=1)


class SolicitudListOut(BaseModel):
    items: list[SolicitudOut]
    total: int


class ReferidoPendienteOut(BaseModel):
    """Panel táctico de Captación -- CU-T02/OT1.2, informe simple (MongoDB)."""

    id: str
    referente_id: str
    referido_id: str
    canal: str
    estado_incentivo: str
    fecha_referido: datetime


class ConversionCaptacionOut(BaseModel):
    """Fila del informe compuesto (ClickHouse) `rpt_conversion_captacion` -- CU-T01/OT1.1."""

    periodo: str
    canal: str
    pct_conversion: float
    dias_aprobacion_promedio: float | None
    total_solicitudes: int


class AltasRetencionCanalOut(BaseModel):
    """Fila del informe compuesto (ClickHouse) `rpt_altas_retencion_canal` -- CU-T02/OT1.2."""

    periodo: str
    canal: str
    altas: int
    pct_retencion: float


# ---------------------------------------------------------------------------
# Nivel estratégico — Panel de Crecimiento Estratégico (OE1)
# ---------------------------------------------------------------------------


class CrecimientoKpisOut(BaseModel):
    pct_conversion_onboarding: float | None
    # Cierre Tier 1-2, punto 2.1: variación PROPIA de `pct_conversion_onboarding`
    # (antes el Tablero Ejecutivo mostraba `variacion_altas_pct`, un KPI distinto).
    variacion_onboarding_pct: float | None = None
    pct_retencion_90d: float | None
    altas_periodo: int | None
    variacion_altas_pct: float | None
    # Siempre `None`: ninguna vista `rpt_*` publica viajes solicitados por
    # mes. Ver `metadata.demanda_disponible` y el docstring del servicio.
    crecimiento_demanda_pct: float | None = None


class PuntoAltasOut(BaseModel):
    periodo: str
    altas: int
    pct_retencion: float


class PuntoConversionOut(BaseModel):
    periodo: str
    pct_conversion: float
    total_solicitudes: int


class PuntoConversionCanalOut(BaseModel):
    """Cierre Tier 1-2, punto 2.6 (N1): mismo dato que `PuntoConversionOut`
    pero desglosado por canal -- serie temporal, no solo el consolidado de
    `canales` (más abajo)."""

    periodo: str
    canal: str
    pct_conversion: float
    total_solicitudes: int


class PuntoOnboardingOut(BaseModel):
    periodo: str
    pct_activo: float
    total_registros: int


class CanalCrecimientoOut(BaseModel):
    canal: str
    pct_conversion: float
    total_solicitudes: int
    dias_aprobacion_promedio: float | None = None
    altas: int = 0


class CrecimientoMetadataOut(BaseModel):
    meses: int
    # `true`: 96 de 194 usuarios (49%) no tienen `canal` -- el desglose por
    # canal subrepresenta a esa mitad. El frontend debe advertirlo.
    canal_cobertura_parcial: bool
    demanda_disponible: bool
    fuentes: list[str]
    registros_previos: dict[str, int | None] | None = None


class PanelCrecimientoOut(BaseModel):
    kpis: CrecimientoKpisOut
    tendencia_altas: list[PuntoAltasOut]
    tendencia_conversion: list[PuntoConversionOut]
    tendencia_conversion_por_canal: list[PuntoConversionCanalOut] = Field(default_factory=list)
    tendencia_onboarding: list[PuntoOnboardingOut]
    canales: list[CanalCrecimientoOut]
    metadata: CrecimientoMetadataOut
