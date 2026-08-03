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
    url_objeto: str
    hash_archivo: str
    fecha_emision: date | None = None
    fecha_vencimiento: date | None = None


class VehiculoInput(BaseModel):
    placa: str
    marca: str
    modelo: str
    anio: int
    color: str
    capacidad: int


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
    estado: EstadoSolicitud
    fecha_envio: datetime | None
    fecha_decision: datetime | None
    revision_reforzada: bool
    motivo_rechazo: str | None
    canal: str | None = None


class SolicitudDecisionRequest(BaseModel):
    decision: Literal["APROBADA", "RECHAZADA", "OBSERVADA"]
    motivo: str | None = None


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
