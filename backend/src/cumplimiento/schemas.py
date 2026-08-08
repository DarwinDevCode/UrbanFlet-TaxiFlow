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


# ---------------------------------------------------------------------------
# Nivel estratégico — Panel de Cumplimiento Normativo (OE6a)
# ---------------------------------------------------------------------------


class CumplimientoNormativoKpisOut(BaseModel):
    pct_vigente: float | None
    variacion_vigencia_pct: float | None
    documentos_vencidos: int
    tipo_mas_expuesto: str | None


class PuntoVigenciaOut(BaseModel):
    periodo: str
    pct_vigente: float
    total_registros: int
    documentos_vencidos: int


class TipoDocumentoVigenciaOut(BaseModel):
    tipo: str
    pct_vigente: float
    total_registros: int
    documentos_vencidos: int


class CumplimientoNormativoMetadataOut(BaseModel):
    cortes: int
    fuentes: list[str]


class PanelCumplimientoNormativoOut(BaseModel):
    kpis: CumplimientoNormativoKpisOut
    tendencia_vigencia: list[PuntoVigenciaOut]
    tipos: list[TipoDocumentoVigenciaOut]
    metadata: CumplimientoNormativoMetadataOut
