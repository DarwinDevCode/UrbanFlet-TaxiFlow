from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Panel de Rentabilidad y Demanda (OE4 / CU-E02 + CU-E03, patrón F)
# ---------------------------------------------------------------------------


class RentabilidadKpisOut(BaseModel):
    margen_promedio_pct: float | None
    # Cierre Tier 1-2, punto 2.1: variación PROPIA de `margen_promedio_pct`
    # (antes el Tablero mostraba `variacion_recaudacion_trimestral_pct`, un
    # KPI distinto). Compara el margen mensual (no el promedio de toda la
    # ventana) de los últimos 2 meses.
    variacion_margen_promedio_pct: float | None = None
    franja_menos_rentable: str | None
    margen_menos_rentable_pct: float | None
    recaudacion_ultimo_trimestre: float | None
    variacion_recaudacion_trimestral_pct: float | None


class CeldaRentabilidadOut(BaseModel):
    """Celda de la matriz dominante del patrón F: mes  *  franja.

    La spec pide zona  *  franja; la dimensión zona no existe todavía en los
    datos (ver `metadata.zona_disponible`)."""

    periodo: str
    franja: str
    recaudacion: float
    comision: float
    costo_mantenimiento: float
    margen: float
    margen_pct: float | None = None
    share_demanda: float
    share_capacidad: float


class ResumenFranjaOut(BaseModel):
    franja: str
    recaudacion: float
    comision: float
    costo_mantenimiento: float
    margen: float
    margen_pct: float | None = None


class PuntoDemandaOut(BaseModel):
    periodo: str
    recaudacion: float
    meses: int


class RentabilidadMetadataOut(BaseModel):
    meses: int
    zona_disponible: bool
    demanda_viajes_disponible: bool
    # Resumen en una línea de la fórmula aplicada; la justificación completa
    # vive en el docstring del servicio.
    formula: str
    fuentes: list[str]
    registros_previos: dict[str, int | None] | None = None
    registros_previos_disponible: bool = True


class PanelRentabilidadOut(BaseModel):
    kpis: RentabilidadKpisOut
    matriz: list[CeldaRentabilidadOut]
    resumen_franja: list[ResumenFranjaOut]
    tendencia_demanda: list[PuntoDemandaOut]
    metadata: RentabilidadMetadataOut


# ---------------------------------------------------------------------------
# Tablero Ejecutivo Consolidado (CU-E01)
# ---------------------------------------------------------------------------


class PuntoMiniTendenciaOut(BaseModel):
    periodo: str
    valor: float | None = None


class TarjetaEjecutivaOut(BaseModel):
    # Identificador del dashboard estratégico de detalle al que navega el
    # enlace "Ver detalle" de esta tarjeta (spec §4). El frontend lo mapea a
    # su sección; el backend es la única fuente de esa lista.
    seccion: str
    titulo: str
    kpi: str
    objetivo: str
    valor: float | None = None
    unidad: str
    variacion_pct: float | None = None
    tendencia: list[PuntoMiniTendenciaOut] = []
    # `false` cuando la fuente de ese headline está vacía o caída: la tarjeta
    # se muestra igual, en estado "sin dato", en vez de tumbar el tablero.
    disponible: bool


class TableroEjecutivoMetadataOut(BaseModel):
    total: int
    disponibles: int


class TableroEjecutivoOut(BaseModel):
    tarjetas: list[TarjetaEjecutivaOut]
    metadata: TableroEjecutivoMetadataOut
