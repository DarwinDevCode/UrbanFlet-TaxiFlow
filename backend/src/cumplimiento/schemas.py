from datetime import date

from pydantic import BaseModel


class RenovacionSubirRequest(BaseModel):
    # Cierre del gap de renovación documental: antes de esto el endpoint
    # aceptaba `url_objeto`/`hash_archivo` como texto libre del cliente, sin
    # ningún archivo real detrás (mismo patrón viejo ya documentado para
    # `documentos` de postulación). Ahora reusa la infraestructura real de
    # `archivos/` -- el cliente sube primero con `POST /archivos`
    # (contexto "documento_renovacion") y manda acá el id resultante; el
    # backend resuelve `url_objeto`/`hash_archivo` del propio archivo real
    # (ver `service.py::subir_renovacion`), nunca confía en lo que el
    # cliente diga que subió.
    archivo_id: str
    fecha_vencimiento: date


# Autoservicio del conductor: sus propios documentos con vigencia, para que
# sepa qué está vencido/por vencer y pueda decidir si subir una renovación.
class MiDocumentoOut(BaseModel):
    id: str
    tipo: str
    fecha_vencimiento: date | None
    estado_verificacion: str
    dias_restantes: int | None = None
    tiene_renovacion_pendiente: bool
    # Bitácora de revisión (2026-08-26, hallazgo #4): antes no viajaba --
    # ni el propio conductor ni el personal interno podían ver la foto real
    # del documento, solo su tipo/fecha. `documentos.url_objeto` YA guarda el
    # id de archivo real (nombre de campo heredado, ver captacion/service.py),
    # se expone acá con el nombre correcto.
    archivo_id: str | None = None


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
    # Bitácora de revisión (2026-08-26, hallazgo #4): el supervisor decidía
    # aprobar/observar una renovación sin poder ver ni el documento vigente
    # ni la foto de la renovación propuesta -- los dos importan para revisar
    # (comparar contra el anterior), así que se exponen los dos ids.
    archivo_id: str | None = None
    archivo_id_propuesto: str | None = None


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
    # Bitácora de revisión (2026-08-26, hallazgo #4): mismo criterio que
    # `MiDocumentoOut`.
    archivo_id: str | None = None


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
    # Tier 1, punto 6 (H-T5): n real que respalda el periodo anterior de cada
    # variación mostrada -- ver `formato.ts::baseEsInsuficiente` en el frontend.
    registros_previos: dict[str, int | None] | None = None


class PanelCumplimientoNormativoOut(BaseModel):
    kpis: CumplimientoNormativoKpisOut
    tendencia_vigencia: list[PuntoVigenciaOut]
    tipos: list[TipoDocumentoVigenciaOut]
    metadata: CumplimientoNormativoMetadataOut
