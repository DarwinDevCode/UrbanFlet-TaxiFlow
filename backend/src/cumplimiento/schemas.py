from datetime import date

from pydantic import BaseModel


class RenovacionSubirRequest(BaseModel):
    url_objeto: str
    hash_archivo: str
    fecha_vencimiento: date


class RenovacionVerificarRequest(BaseModel):
    aprobar: bool
    motivo: str | None = None


class ControlVigenciaResultado(BaseModel):
    revisados: int
    por_vencer_notificados: int
    vencidos_nuevos: int


class RenovacionPendienteOut(BaseModel):
    documento_id: str
    tipo: str
    propietario_tipo: str
    propietario_id: str
    propietario_nombre: str | None = None
    fecha_vencimiento_actual: str | None
    fecha_vencimiento_propuesta: str


class DocumentoVencimientoOut(BaseModel):
    """Panel táctico de Vigencia Documental -- CU-T10/OT6.1, informe simple (MongoDB)."""

    documento_id: str
    tipo: str
    propietario_tipo: str
    propietario_id: str
    propietario_nombre: str | None = None
    fecha_vencimiento: date | None
    estado_verificacion: str
    dias_restantes: int | None = None


class DocumentacionVigenteOut(BaseModel):
    """Fila del informe compuesto (ClickHouse) `rpt_documentacion_vigente` -- CU-T10/OT6.1."""

    tipo: str
    pct_vigente: float
    total_registros: int
    fecha_datos: str | None = None
