from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

EstadoViaje = Literal[
    "PROGRAMADO",
    "SOLICITADO",
    "OFERTADO",
    "ASIGNADO",
    "EN_CAMINO",
    "EN_CURSO",
    "FINALIZADO",
    "PAGADO",
    "CANCELADO",
    "SIN_CONDUCTOR",
]
Franja = Literal["DIURNA", "NOCTURNA"]


class SolicitarViajeRequest(BaseModel):
    origen_lat: float = Field(ge=-90, le=90)
    origen_lon: float = Field(ge=-180, le=180)
    origen_direccion: str
    destino_lat: float | None = Field(default=None, ge=-90, le=90)
    destino_lon: float | None = Field(default=None, ge=-180, le=180)
    destino_direccion: str | None = None
    # Sección 1.5 de ux_complementaria.md: "Ahora" (None, comportamiento de
    # siempre) vs. "Programar" (hora futura -- el viaje se crea en
    # PROGRAMADO y el auto-despacho se dispara después, cerca de esa hora).
    ts_programado: datetime | None = None


class CalificacionOut(BaseModel):
    puntaje: int
    comentario: str | None
    ts: datetime


class DesgloseTarifaOut(BaseModel):
    """CU-O08 paso 3: "el sistema muestra la tarifa final a ambos actores con
    el desglose de los tres rubros" -- los 3 montos ya se calculaban en
    `service_finalizacion.py` para llegar a `tarifa_final`, pero se
    descartaban después de la suma. `subtotal` es la suma de los 3 ANTES de
    aplicar el piso de `carrera_minima` -- el frontend determina si el piso
    se aplicó comparando `subtotal` contra `ViajeOut.tarifa_final` (son
    iguales si no se aplicó, `tarifa_final` > `subtotal` si sí)."""

    arrancada: float
    distancia: float
    espera: float
    subtotal: float


class ViajeOut(BaseModel):
    id: str
    pasajero_id: str
    conductor_id: str | None
    vehiculo_id: str | None
    estado: EstadoViaje
    origen_lat: float
    origen_lon: float
    origen_direccion: str
    destino_lat: float | None
    destino_lon: float | None
    destino_direccion: str | None
    franja: Franja
    ts_programado: datetime | None = None
    ts_solicitud: datetime
    ts_asignacion: datetime | None
    ts_llegada_origen: datetime | None = None
    ts_inicio: datetime | None
    ts_fin: datetime | None
    km_recorridos: float | None
    min_espera: float | None
    tarifa_estimada: float | None
    tarifa_final: float | None
    desglose_tarifa: DesgloseTarifaOut | None = None
    motivo_cancelacion: str | None
    conductor_nombre: str | None = None
    conductor_calificacion: float | None = None
    # Sección 2.2 de la spec ux_complementaria.md: foto que el pasajero ve
    # al ser asignado (CU-O05 P5). Snapshot tomado en el momento de la
    # asignación desde `usuarios.foto_url` (campo general de foto de
    # perfil, ver perfil/service.py -- ya no exclusivo de `conductor`), el
    # id de un archivo servido por `GET /archivos/{id}` (contexto de
    # lectura pública `foto_perfil`, sin necesidad de sesión).
    conductor_foto_url: str | None = None
    vehiculo_placa: str | None = None
    vehiculo_marca: str | None = None
    vehiculo_color: str | None = None
    calificacion_pasajero_a_conductor: CalificacionOut | None = None
    calificacion_conductor_a_pasajero: CalificacionOut | None = None
    # CU-O14 paso 3 / A2: "datos de la contraparte (limitados: nombre y
    # calificación)" — para cuando el CONDUCTOR consulta el historial, ya que
    # conductor_nombre/conductor_calificacion (arriba) cubren el caso inverso
    # (pasajero viendo al conductor) desde que se asigna el viaje. Nunca
    # incluye teléfono ni historial de ubicaciones del pasajero.
    pasajero_nombre: str | None = None
    pasajero_calificacion: float | None = None
    # Ronda de fotos en historial/usuarios: mismo criterio que
    # `conductor_foto_url` -- id de un archivo de contexto `foto_perfil`
    # (lectura pública). A diferencia de `conductor_foto_url` (snapshoteado
    # en el viaje al asignar), este se resuelve en tiempo de consulta junto
    # al resto de la "contraparte limitada" de CU-O14 A2 (ver
    # `service_historial.py::enriquecer_con_pasajero`) -- nunca abre acceso
    # a un dato nuevo, es el mismo tipo de identidad visual que ya expone
    # `pasajero_nombre`.
    pasajero_foto_url: str | None = None
    # Mapa del historial (CU-O14 paso 3, "mapa con la ruta recorrida"). Es la
    # traza GPS REAL acumulada durante el viaje por
    # `service_ejecucion.registrar_punto_traza` (un punto por cada reporte de
    # posición del conductor) -- nunca una ruta recalculada ni una línea
    # inventada entre origen y destino. `None` en la LISTA (nunca se serializa
    # ahí: un historial de 20 filas con hasta 20 000 puntos cada una sería un
    # payload absurdo) y en cualquier viaje que no llegó a acumularla
    # (SIN_CONDUCTOR, cancelado antes de arrancar, o los viajes históricos
    # sembrados desde el dataset NYC, que nacen con `traza: []`). Solo los
    # endpoints de DETALLE la piden -- ver `to_out(..., incluir_traza=True)`.
    traza: list[tuple[float, float]] | None = None


class HistorialOut(BaseModel):
    viajes: list[ViajeOut]
    total: int
    pagina: int
    limite: int


# Sección 1.2 de ux_complementaria.md: compartir viaje en tiempo real.
class CompartirViajeOut(BaseModel):
    token: str


class PosicionCompartidaOut(BaseModel):
    lat: float
    lon: float


class ViajeCompartidoOut(BaseModel):
    """Salida del endpoint público `GET /publico/viajes-compartidos/{token}`
    -- deliberadamente mínima: nunca teléfono/correo, nunca datos del
    pasajero (quien lo generó ya sabe quién es), solo lo que un contacto de
    confianza necesita para verificar que el viaje va bien."""

    conductor_nombre: str | None
    conductor_calificacion: float | None
    conductor_foto_url: str | None
    vehiculo_placa: str | None
    estado: EstadoViaje
    posicion: PosicionCompartidaOut | None


class CalificarViajeRequest(BaseModel):
    puntaje: int = Field(ge=1, le=5)
    comentario: str | None = None


class OfertaActualOut(BaseModel):
    viaje_id: str
    pasajero_nombre: str
    pasajero_calificacion: float | None
    origen_lat: float
    origen_lon: float
    distancia_km: float | None
    tiene_destino: bool
    segundos_restantes: int


class ResponderOfertaRequest(BaseModel):
    aceptar: bool


class CancelarViajePasajeroRequest(BaseModel):
    # Catálogos Ronda 1 (Ola 1.4): antes `motivo_cancelacion` se hardcodeaba
    # server-side a "Cancelado por el pasajero" -- ahora lo elige el
    # pasajero desde el selector (categoría `cancelacion` de
    # motivos_cancelacion), obligatorio.
    motivo: str = Field(min_length=1, max_length=200)


class EstimacionRutaOut(BaseModel):
    # Directions API de Google no envía cabeceras CORS — la ruta se pide
    # siempre a través del backend, nunca directo desde el navegador (ver
    # rutas.ts en web-pasajero). `origen_directions=False` indica que se usó
    # el respaldo de línea recta (cuota agotada, sin ruta, red caída, etc.).
    ruta: list[tuple[float, float]]
    distancia_km: float
    duracion_min: float
    origen_directions: bool


class RecalculoRutaRequest(BaseModel):
    """CU-O07 A6: el conductor (cliente) ya detectó el desvío >2km y ya
    recalculó la ruta contra GET /viajes/estimacion-ruta — este cuerpo es
    solo lo que hace falta para dejar el evento en bitácora (posición del
    desvío + ruta anterior vs. recalculada), no un segundo cálculo de ruta."""

    lat: float
    lon: float
    distancia_desvio_km: float = Field(ge=0)
    ruta_anterior: list[tuple[float, float]]
    ruta_nueva: list[tuple[float, float]]


class ViajeActivoOut(BaseModel):
    """Panel táctico de Despacho -- CU-T07, informe simple (MongoDB)."""

    id: str
    pasajero_id: str
    conductor_id: str | None
    estado: EstadoViaje
    zona_origen_id: str | None = None
    ts_solicitud: datetime


class ViajeSinConductorCanceladoOut(BaseModel):
    """Panel táctico de Despacho -- CU-T08, informe simple (MongoDB)."""

    id: str
    estado: EstadoViaje
    motivo_cancelacion: str | None
    actor_cancelacion: str | None = None
    ts_solicitud: datetime


class TiempoAsignacionOut(BaseModel):
    """Fila del informe compuesto (ClickHouse) `rpt_tiempo_asignacion` -- CU-T07/OT4.1."""

    zona_origen_id: str
    franja: str
    segundos_promedio: float
    segundos_p95: float
    total_registros: int


class TasaCancelacionOut(BaseModel):
    """Fila del informe compuesto (ClickHouse) `rpt_tasa_cancelacion` -- CU-T08/OT4.2."""

    periodo: str
    zona_origen_id: str
    motivo: str
    actor: str
    cancelados: int
    solicitados: int
    tasa_cancelacion: float


class DesempenoConductorOut(BaseModel):
    """Fila del panel táctico "Rendimiento de Conductores" -- Punto 3 de la
    ronda de mejoras de claridad y profundidad analítica (agosto 2026).
    Combina `rpt_desempeno_conductor` (viajes/calificación) + `rpt_ingreso_conductor`
    (ingreso), unidos por (conductor_id, periodo) -- ver CLAUDE.md §17.4."""

    conductor_id: str
    conductor_nombre: str | None = None
    periodo: str
    viajes_completados: int
    viajes_cancelados: int
    pct_exito: float
    calificacion_promedio: float | None
    bruto: float | None
    comisiones: float | None
    neto: float | None
    # Fila sintética (Parte 3, ronda de diagnóstico de agosto 2026): un socio
    # activo sin ningún viaje completado/cancelado en la ventana consultada,
    # incluido solo cuando `incluir_inactivos=true` -- nunca aparece en
    # `rpt_desempeno_conductor` por construcción, así que esta fila no viene
    # de esa vista, se agrega aparte cruzando contra el roster de conductores.
    sin_actividad: bool = False


class KmPorSocioOut(BaseModel):
    """Kilómetros recorridos por socio en la ventana consultada -- leído
    directo de `fact_viaje.km_recorridos` (Parte 3, ronda de diagnóstico y
    nuevos indicadores, agosto 2026), no de una `rpt_*`."""

    conductor_id: str
    conductor_nombre: str | None = None
    km_total: float


class HistogramaCalificacionOut(BaseModel):
    """Distribución de calificaciones (1-5 estrellas) de todos los viajes en
    la ventana consultada -- leído directo de `fact_viaje.calificacion_puntaje`."""

    estrellas: int
    viajes: int


class PanelDesempenoConductoresOut(BaseModel):
    filas: list[DesempenoConductorOut]
    km_por_socio: list[KmPorSocioOut] = []
    histograma_calificaciones: list[HistogramaCalificacionOut] = []
    metadata: dict


class FilaDesempenoTrimestralOut(BaseModel):
    """Fila del panel ESTRATÉGICO de Desempeño de Conductores -- a diferencia
    de `DesempenoConductorOut` (panel táctico, grano mensual), esta es una
    segunda capa de agregación real por conductorxTRIMESTRE (ver
    `viajes/service.py::obtener_panel_estrategico_desempeno_conductores`)."""

    conductor_id: str
    conductor_nombre: str | None = None
    trimestre: str
    viajes_completados: int
    viajes_cancelados: int
    pct_exito: float | None
    calificacion_promedio: float | None
    bruto: float | None
    comisiones: float | None
    neto: float | None


class PanelDesempenoTrimestralOut(BaseModel):
    filas: list[FilaDesempenoTrimestralOut]
    metadata: dict


# ---------------------------------------------------------------------------
# Nivel estratégico — Panel de Confiabilidad y Disponibilidad (OE2a)
# ---------------------------------------------------------------------------


class ConfiabilidadKpisOut(BaseModel):
    segundos_asignacion_promedio: float | None
    cancelaciones_periodo: int | None
    variacion_cancelaciones_pct: float | None
    tasa_cancelacion: float | None = None
    pct_flota_activa: float | None
    franja_menor_cobertura: str | None


class PuntoAsignacionOut(BaseModel):
    periodo: str
    segundos_promedio: float
    total_registros: int


class PuntoCancelacionOut(BaseModel):
    periodo: str
    cancelados: int
    sin_conductor: int
    solicitados: int


class PuntoFlotaOut(BaseModel):
    periodo: str
    pct_disponible: float
    total_registros: int


class FranjaCoberturaOut(BaseModel):
    franja: str
    pct_disponible: float
    total_registros: int


class FranjaAsignacionOut(BaseModel):
    """Franja según la taxonomía de `rpt_tiempo_asignacion` (DIURNA/NOCTURNA),
    distinta de la de `rpt_flota_activa_franja` (00-06/06-12/...) — por eso
    va en su propia lista y no cruzada con `FranjaCoberturaOut`."""

    franja: str
    segundos_promedio: float
    total_registros: int


class ConfiabilidadMetadataOut(BaseModel):
    meses: int
    # `false` mientras `viajes.zona_origen_id` siga sin resolverse: el futuro
    # frontend usa esta bandera para mostrar la limitación en vez de un filtro
    # de zona que no filtraría nada.
    zona_disponible: bool
    tasa_cancelacion_disponible: bool
    fuentes: list[str]
    registros_previos: dict[str, int | None] | None = None


class PanelConfiabilidadOut(BaseModel):
    kpis: ConfiabilidadKpisOut
    tendencia_asignacion: list[PuntoAsignacionOut]
    tendencia_cancelacion: list[PuntoCancelacionOut]
    tendencia_flota: list[PuntoFlotaOut]
    franjas: list[FranjaCoberturaOut]
    franjas_asignacion: list[FranjaAsignacionOut]
    metadata: ConfiabilidadMetadataOut
