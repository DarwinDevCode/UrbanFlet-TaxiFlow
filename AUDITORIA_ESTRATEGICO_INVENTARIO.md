# Auditoría del Nivel Estratégico — Inventario (Fase 1)

Auditoría solicitada por el usuario vía `prompt_auditoria_nivel_estrategico.md`. Este documento
es el inventario **sin juicios de valor** — la crítica va en
[AUDITORIA_ESTRATEGICO_HALLAZGOS.md](AUDITORIA_ESTRATEGICO_HALLAZGOS.md). Todo lo que sigue se
verificó leyendo el código real (backend `src/*/service.py`, frontend
`apps/web-interno/src/sections/estrategico/*.tsx`, DAGs/`analytics/plugins/indicadores.py`), no
se infirió de los nombres de campo ni de la documentación de sesiones previas.

Alcance: los 9 paneles (Tablero Ejecutivo + 8 dashboards de detalle) de
`apps/web-interno/src/sections/estrategico/`, sus 9 endpoints backend, y el modelo de datos
completo (MongoDB + ClickHouse Gold) del que podrían alimentarse.

## 0. Mapa de archivos

| Panel | Frontend | Endpoint | Service (backend) |
|---|---|---|---|
| Tablero Ejecutivo (CU-E01) | `TableroEjecutivo.tsx` | `GET /estrategico/tablero-ejecutivo` | `estrategico/service.py::obtener_tablero_ejecutivo` |
| Crecimiento (OE1) | `PanelCrecimiento.tsx` | `GET /captacion/panel-estrategico/crecimiento` | `captacion/service.py:530` |
| Confiabilidad (OE2a) | `PanelConfiabilidad.tsx` | `GET /viajes/panel-estrategico/confiabilidad` | `viajes/service.py:565` |
| Estado y Costo de Flota (OE2b) | `PanelEstadoCostoFlota.tsx` | `GET /mantenimiento/panel-estrategico/estado-costo-flota` | `mantenimiento/service.py:519` |
| Capacidades y Plataforma (OE3) | `PanelCapacidades.tsx` | `GET /plataforma/panel-estrategico/capacidades` | `plataforma/service.py:136` |
| Rentabilidad y Demanda (OE4) | `PanelRentabilidad.tsx` | `GET /estrategico/rentabilidad-demanda` | `estrategico/service.py:92` |
| Integridad Financiera (OE5) | `PanelIntegridadFinanciera.tsx` | `GET /liquidaciones/panel-estrategico/integridad-financiera` | `recaudacion/service.py:934` |
| Cumplimiento Normativo (OE6a) | `PanelCumplimientoNormativo.tsx` | `GET /cumplimiento/panel-estrategico/cumplimiento-normativo` | `cumplimiento/service.py:335` |
| Gobernanza de Datos y Seguridad (OE6b) | `PanelGobernanza.tsx` | `GET /auditoria/panel-estrategico/gobernanza` | `auditoria/service.py:79` |

RBAC (todos vía `require_roles`, confirmado en cada router): `rentabilidad-demanda` y
`tablero-ejecutivo` son exclusivos de `gerencia`. Los 7 restantes son `gerencia` + un segundo rol
dueño del dominio, salvo Gobernanza que es **exclusivo de `gerencia`** (ni siquiera
`admin_sistema`, confirmado en `auditoria/router.py:98`).

## 1. Inventario de KPIs por panel

Convención de unidades confirmada en `apps/web-interno/src/sections/estrategico/formato.ts`:
todo `pct_*`/`margen_pct`/`share_*` viaja como fracción 0-1; todo `variacion_*_pct` ya viaja en
puntos porcentuales.

### Tablero Ejecutivo Consolidado (CU-E01)

8 tarjetas, una por dashboard de detalle. Cada una llama al **mismo** service que su panel de
detalle (`estrategico/service.py:339-397`), nunca reimplementa el cálculo.

| Tarjeta (`seccion`) | Valor mostrado | Variación mostrada | Mini-tendencia (campo) |
|---|---|---|---|
| `crecimiento` | `pct_conversion_onboarding` | `variacion_altas_pct` | `tendencia_onboarding.pct_activo` |
| `confiabilidad` | `pct_flota_activa` | `None` (fijo) | `tendencia_flota.pct_disponible` |
| `estado-costo-flota` | `pct_cumplimiento_preventivo` | `variacion_cumplimiento_pct` | `tendencia_preventivo.pct_cumplimiento` |
| `capacidades` | `pct_cuarentena_global` | `variacion_cuarentena_pct` | `tendencia_cuarentena.pct_cuarentena` |
| `rentabilidad` | `margen_promedio_pct` | `variacion_recaudacion_trimestral_pct` | `tendencia_demanda.recaudacion` |
| `integridad-financiera` | `pct_conciliado` | `variacion_conciliado_pct` | `tendencia_conciliacion.pct_conciliado` |
| `cumplimiento-normativo` | `pct_vigente` | `variacion_vigencia_pct` | `tendencia_vigencia.pct_vigente` |
| `gobernanza` | `eventos_administrativos` | `variacion_accesos_denegados_pct` | `tendencia.eventos_administrativos` |

Fórmula del tono de color (`TableroEjecutivo.tsx:134`): `tonoVariacion(variacion_pct, {subirEsBueno:
seccion !== "capacidades"})` — es decir, **toda** tarjeta salvo Capacidades asume "subir es
bueno".

### Panel de Crecimiento Estratégico (OE1)

Fuente: `rpt_conversion_captacion`, `rpt_altas_retencion_canal`, `rpt_conversion_onboarding`.

| KPI | Fórmula real (código) | Comparación temporal |
|---|---|---|
| Conversión de altas (`pct_conversion_onboarding`) | `promedio_ponderado(onboarding, "pct_activo", "total_registros")` sobre el último corte de `rpt_conversion_onboarding` | No (foto del último corte) |
| Retención a 90 días (`pct_retencion_90d`) | `promedio_ponderado(altas, "pct_retencion", "altas")` sobre `rpt_altas_retencion_canal` | No |
| Altas de socios del periodo (`altas_periodo`) | Suma de `altas` del último periodo de `tendencia_altas` | Sí, `variacion_altas_pct` vs. el periodo anterior de la misma tendencia |
| Crecimiento de demanda (`crecimiento_demanda_pct`) | **Siempre `None`** — declarado en `metadata.demanda_disponible=false` | N/A |

Tabla: "Conversión por canal" (`canales`), filtrable por canal. Gráficos: altas+solicitudes por
periodo, % onboarding activo en el tiempo. Metadata declara `canal_cobertura_parcial=true` (49%
de usuarios sin `canal`, hallazgo H3 heredado).

### Panel de Confiabilidad y Disponibilidad del Servicio (OE2a)

Fuente: `rpt_tiempo_asignacion`, `rpt_tasa_cancelacion`, `rpt_flota_activa_franja`.

| KPI | Fórmula real | Comparación temporal |
|---|---|---|
| Tiempo de asignación prom. (`segundos_asignacion_promedio`) | `promedio_ponderado(asignacion, "segundos_promedio", "total_registros")`, último corte | No |
| Tasa de cancelación (`tasa_cancelacion`) | **Siempre `None`** — `metadata.tasa_cancelacion_disponible=false` | N/A |
| Cancelaciones del periodo (`cancelaciones_periodo`) | Suma de `cancelados` (`countIf(estado IN (CANCELADO,SIN_CONDUCTOR))`) del último periodo de `rpt_tasa_cancelacion`, agrupado por `periodo,zona_origen_id,motivo,actor` con `HAVING cancelados > 0` (`indicadores.py:722-761`) | Sí, `variacion_cancelaciones_pct` vs. periodo anterior |
| Flota activa promedio (`pct_flota_activa`) | `promedio_ponderado(flota, "pct_disponible", "total_registros")`, último corte | No |
| Franja con menor cobertura (`franja_menor_cobertura`) | Label del mínimo de `franjas` ordenado por `pct_disponible` | No |

Dos tablas de franja con taxonomías distintas (`franjas` = buckets 6h de flota; `franjas_asignacion`
= DIURNA/NOCTURNA de despacho), declaradas explícitamente como no cruzables. Filtro de zona
deshabilitado (`zona_disponible` calculado real, hoy `true` porque las filas Gold sí traen
Z-NORTE/Z-SUR — distinto del caso fijo de Rentabilidad).

### Panel de Estado y Costo de Flota (OE2b)

Fuente: `rpt_cumplimiento_plan_preventivo`, `rpt_costo_mantenimiento_vehiculo`.

| KPI | Fórmula real | Comparación temporal |
|---|---|---|
| Cumplimiento preventivo (`pct_cumplimiento_preventivo`) | `promedio_ponderado(..., "pct_cumplimiento", "total_ordenes")` del último periodo de `tendencia_preventivo` | Sí, `variacion_cumplimiento_pct` |
| Costo del último periodo (`costo_mantenimiento_periodo`) | Suma de `costo_total` del último periodo de `tendencia_costo` | Sí, `variacion_costo_pct` |
| Costo acumulado (`costo_acumulado`) | Suma de `costo_total` de TODOS los vehículos en la ventana completa | No |

Tabla "Vehículos candidatos a reemplazo" (top 10 por costo acumulado, con `km_recorridos` siempre
`None` — declarado `km_disponible=false`). Único acceso a Mongo de todo el nivel estratégico
fuera de Gobernanza: resolver la **placa** (dato descriptivo) de cada vehículo del ranking
(`obtener_placas_vehiculos`, `mantenimiento/service.py:594`).

### Panel de Capacidades y Plataforma (OE3)

Fuente: `rpt_cuarentena_dominio` + tabla `corridas` de ClickHouse (consulta directa, no `rpt_*`,
pero sigue siendo ClickHouse).

| KPI | Fórmula real | Comparación temporal |
|---|---|---|
| Registros rechazados global (`pct_cuarentena_global`) | `sum(registros_cuarentena)/sum(registros_extraidos)` del último corte de `tendencia_cuarentena` (vía `fetch_snapshot_history`) | Sí, `variacion_cuarentena_pct` |
| Dominio más afectado (`dominio_mas_afectado`) | Label del máximo `pct_cuarentena` en `dominios` (último corte) | No |
| Corridas OK (`corridas_ok`) | `SELECT estado, count() FROM corridas GROUP BY estado` — suma de `OK`+`WARN`, **sin filtro de fecha, histórico completo de la tabla** (`plataforma/service.py:158-170`) | No |
| Corridas fallidas (`corridas_fallidas`) | Igual query, suma de todo estado que no sea `OK`/`WARN` — **también histórico completo, sin filtro de periodo** | No |
| Avance de capacitación (`avance_capacitacion_pct`) | **Siempre `None`** — `metadata.capacitacion_disponible=false` | N/A |

Nota: la etiqueta en frontend (`PanelCapacidades.tsx:153,158`) dice "en el periodo" para ambos
KPIs de corridas, pese a que la query no filtra por fecha en absoluto — ver hallazgo en Fase 2.
Tiene drill-down real ya construido ("Corridas fallidas" → modal con filtro de estado, fuente
`GET /plataforma/panel-tactico/corridas`).

### Panel de Rentabilidad y Demanda (OE4) — patrón F

Fuente: `rpt_margen_comision`, `rpt_costo_mantenimiento_vehiculo`, `rpt_tiempo_asignacion`,
`rpt_flota_activa_franja`. Fórmula completa documentada en el docstring de
`estrategico/service.py::obtener_panel_rentabilidad` (líneas 92-146), reproducida en el hallazgo
correspondiente.

| KPI | Fórmula real | Comparación temporal |
|---|---|---|
| Margen promedio (`margen_promedio_pct`) | `promedio_ponderado(resumen_franja, "margen_pct", "recaudacion")` sobre las 2 franjas | No |
| Franja menos rentable / Margen de esa franja | Mínimo de `resumen_franja` ordenado por `margen_pct` | No |
| Recaudación último trimestre (`recaudacion_ultimo_trimestre`) | Suma de `bruto_total` del último trimestre de `tendencia_demanda` (agrupado de meses a trimestres en Python) | Sí, `variacion_recaudacion_trimestral_pct` vs. trimestre anterior |

Tabla dominante: matriz mes×franja con recaudación/comisión/costo/margen/participaciones. Zona
siempre `false` (`zona_disponible` **fijo**, a diferencia de Confiabilidad donde se calcula).
`share_demanda`/`share_capacidad` se toman del ÚLTIMO corte y se aplican a TODOS los meses de la
ventana (declarado en el docstring, línea 141-145).

### Panel de Integridad Financiera (OE5 / CU-E04)

Fuente: `rpt_tasa_discrepancias`, `rpt_margen_comision`.

| KPI | Fórmula real | Comparación temporal |
|---|---|---|
| Conciliado (`pct_conciliado`) | `promedio_ponderado(..., "pct_conciliado", "total_registros")` del último periodo | Sí, `variacion_conciliado_pct` |
| Tasa de discrepancias (`tasa_discrepancias`) | `promedio_ponderado(..., "pct_discrepancia", "total_registros")` del último periodo | Sí, `variacion_discrepancias_pct` |
| Margen de comisión prom. (`margen_comision_promedio`) | Media aritmética simple de `tendencia_margen[].margen` (cada `margen` de fila ya es un promedio ponderado por `bruto_total` a nivel de periodo — el promedio ENTRE periodos no vuelve a ponderar) | No |

Tabla "Periodos con discrepancia relevante" (>0), comparación interanual (solo si ≥2 años),
metadata `dataset_mixto` cuando el rango cruza NYC-2021/operación-2026.

### Panel de Cumplimiento Normativo (OE6a)

Fuente: `rpt_documentacion_vigente`.

| KPI | Fórmula real | Comparación temporal |
|---|---|---|
| Documentación vigente (`pct_vigente`) | `promedio_ponderado(actual, "pct_vigente", "total_registros")` sobre el ÚLTIMO SNAPSHOT COMPLETO (no el último punto de `tendencia`) | Sí, `variacion_vigencia_pct` vs. penúltimo punto de tendencia |
| Documentos vencidos (`documentos_vencidos`) | `round(sum(total_registros * (1 - pct_vigente)))` — aritmética exacta sobre el snapshot, no consulta nueva | No |
| Tipo más expuesto (`tipo_mas_expuesto`) | Mínimo `pct_vigente` de `tipos` | No |

Ya tiene drill-down real ("Documentos vencidos" → modal, reusa
`GET /cumplimiento/panel-tactico/documentos-por-vencer` filtrado a `dias_restantes<0`).

### Panel de Gobernanza de Datos y Seguridad (OE6b / CU-E05) — patrón F

Fuente: colección `bitacora` de MongoDB **directo** (única excepción documentada a la regla de
"solo `rpt_*`", justificada en el docstring de `auditoria/service.py:6-13`).

| KPI | Fórmula real | Comparación temporal |
|---|---|---|
| Eventos administrativos (`eventos_administrativos`) | `count_documents({accion: {$in: ACCIONES_ADMINISTRATIVAS}, ts: {$gte: desde}})` | No (no tiene variación propia) |
| Accesos denegados (`accesos_denegados`) | `count_documents({accion: "ACCESO_DENEGADO", ts: {$gte: desde}})` | Sí, `variacion_accesos_denegados_pct` — único KPI de los 9 paneles que compara ventana completa vs. ventana completa anterior (no últimos-2-puntos-de-tendencia como el resto) |
| Alertas de seguridad (`alertas_seguridad`) | `count_documents({accion: {$in: [LOGIN_FALLIDO_CONSECUTIVO, POSIBLE_GPS_SPOOFING]}, ts: {$gte: desde}})` | No |

Ya tiene drill-down real en 2 de los 3 KPIs ("Eventos administrativos" reusa el array `eventos` ya
cargado; "Accesos denegados" dispara 1 fetch nueva a `GET /auditoria/eventos?accion=ACCESO_DENEGADO`).
"Alertas de seguridad" no tiene drill-down todavía.

## 2. Patrón "dato no disponible" — inventario de banderas `metadata`

Confirmado en cada `service.py` y consumido en el frontend vía `NotaLimitacion` (nunca se fabrica
un valor):

| Bandera | Panel | Estado real verificado |
|---|---|---|
| `demanda_disponible=false` | Crecimiento | Fijo, sin fuente `rpt_*` |
| `canal_cobertura_parcial=true` | Crecimiento | Calculado — 96/194 usuarios sin `canal` (49%) |
| `tasa_cancelacion_disponible=false` | Confiabilidad | Fijo |
| `zona_disponible` | Confiabilidad | **Calculado real** — hoy `true` |
| `km_disponible=false` | Estado y Costo de Flota | Fijo |
| `capacitacion_disponible=false` | Capacidades | Fijo |
| `zona_disponible=false` | Rentabilidad | **Fijo** (no calculado, a diferencia de Confiabilidad) |
| `demanda_viajes_disponible=false` | Rentabilidad | Fijo |
| `dataset_mixto` | Integridad Financiera | Calculado real |
| `interanual_disponible` | Integridad Financiera | Calculado real |

## 3. Entidades del modelo de datos — inventario completo

### 3.1 Tablas `rpt_*` en ClickHouse (15 totales, `analytics/plugins/indicadores.py`)

| Tabla | Dominio dueño | ¿Consumida por el nivel estratégico? |
|---|---|---|
| `rpt_flota_activa_franja` | Flota | Sí (Confiabilidad, Rentabilidad) |
| `rpt_tasa_discrepancias` | Finanzas | Sí (Integridad Financiera) |
| `rpt_margen_comision` | Finanzas | Sí (Integridad Financiera, Rentabilidad) |
| `rpt_conversion_onboarding` | Captación | Sí (Crecimiento) |
| `rpt_documentacion_vigente` | Cumplimiento | Sí (Cumplimiento Normativo) |
| `rpt_uso_integraciones` | Plataforma | **No** |
| `rpt_cumplimiento_plan_preventivo` | Mantenimiento | Sí (Estado y Costo de Flota) |
| `rpt_costo_mantenimiento_vehiculo` | Mantenimiento | Sí (Estado y Costo de Flota, Rentabilidad) |
| `rpt_conversion_captacion` | Captación | Sí (Crecimiento) |
| `rpt_altas_retencion_canal` | Captación | Sí (Crecimiento) |
| `rpt_tiempo_asignacion` | Despacho | Sí (Confiabilidad, Rentabilidad) |
| `rpt_tasa_cancelacion` | Despacho | Sí (Confiabilidad) — con el defecto documentado en §1 |
| `rpt_cuarentena_dominio` | Plataforma (meta) | Sí (Capacidades) |
| `rpt_desempeno_conductor` | Despacho (conductor) | **No** |
| `rpt_ingreso_conductor` | Finanzas (conductor) | **No** |

Confirmado por grep: ninguna referencia a `rpt_desempeno_conductor`, `rpt_ingreso_conductor` ni
`rpt_uso_integraciones` en `backend/src/estrategico/`, ni en los 7 `service.py` de dominio que
exponen `panel-estrategico`.

### 3.2 Tablas `fact_*` (Gold, ClickHouse) — no consultadas directo por el nivel estratégico

`fact_viaje`, `fact_ubicacion_flota`, `fact_recaudacion`, `fact_liquidacion`,
`fact_registro_usuario`, `fact_ciclo_viaje` (con `conductor_id` desde la sesión de Rendimiento de
Conductores — no usado por ningún panel estratégico), `fact_solicitud_captacion`,
`fact_cumplimiento_documental`, `fact_integracion_api`, `fact_orden_mantenimiento`,
`fact_viaje_historico`. La spec estratégica (§2) prohíbe consultarlas directo desde este nivel —
confirmado que ningún `service.py` estratégico lo hace (todos pasan por `fetch_latest_snapshot`/
`fetch_snapshot_history` sobre `rpt_*`, salvo la excepción declarada de Gobernanza sobre Mongo).

### 3.3 Colecciones MongoDB relevantes no explotadas por el nivel estratégico

- **`usuarios`** (conductores/pasajeros/staff): campo `estado` con valores `ACTIVO`/`SUSPENDIDO`/
  `BAJA` (confirmado en `usuarios/service.py:36,99,239,251,254,275,278,287,299` — `USUARIO_BAJA`
  es una acción de auditoría real). No existe ninguna tabla Gold que agregue bajas/rotación de
  conductores por periodo — solo se agregan **altas** (`fact_registro_usuario` →
  `rpt_altas_retencion_canal`).
- **`viajes.calificacion_pasajero_a_conductor` / `calificacion_conductor_a_pasajero`**: existen
  desde CU-O08, y `fact_viaje.calificacion_puntaje` ya se extrae a Gold (agregado en la sesión de
  Rendimiento de Conductores táctico) — pero solo alimenta `rpt_desempeno_conductor`, que ningún
  panel estratégico consume.
- **`documentos`**, **`ordenes`**, **`bitacora`**: cubiertas indirectamente vía sus `rpt_*`
  respectivos, salvo `bitacora` que Gobernanza sí lee directo (única excepción documentada).
- No existe ningún dominio de **siniestralidad/incidentes** en el sistema (confirmado por grep de
  "siniestr", "accidente" en `backend/src` — sin resultados relacionados a un dominio propio;
  "incidencia" solo aparece en el catálogo de motivos de cancelación/incidencia y en mantenimiento,
  no como entidad de siniestros).

## 4. Información de niveles operativo/táctico que NO llega al nivel estratégico

Confirmado con evidencia real (no solo "tendría sentido que faltara"):

1. **Calificaciones de servicio / desempeño por conductor** (`rpt_desempeno_conductor`,
   `rpt_ingreso_conductor`) — existen y tienen datos reales (construidos en la sesión de
   "Rendimiento de Conductores" táctico, `analytics/plugins/indicadores.py:826-919`), pero ningún
   panel estratégico las referencia. Relevante para gerencia: concentración de viajes/ingresos en
   pocos conductores (dato real y ya documentado como problema conocido del dataset de
   desarrollo, CLAUDE.md §8.5 — 5 conductores con ~270K viajes cada uno), calidad de servicio
   agregada.
2. **Rotación/bajas de conductores** — el evento existe (`USUARIO_BAJA` en `usuarios`/`bitacora`)
   pero no hay ninguna tabla Gold ni KPI que la agregue por periodo. Solo se mide "altas", nunca
   "bajas" ni retención neta de la flota de conductores (distinto de "retención a 90 días", que
   mide actividad post-alta, no permanencia como socio).
3. **Uso de integraciones externas** (`rpt_uso_integraciones`) — existe con datos reales (ya
   consumida por el panel táctico de Auditoría e Integraciones), pero el nivel estratégico no la
   toca en absoluto, ni siquiera en Gobernanza (que solo mira `bitacora`).
4. **Estacionalidad / estructura de demanda por franja horaria más allá de DIURNA/NOCTURNA** —
   `rpt_flota_activa_franja` sí trae buckets de 6h, pero ningún panel estratégico expone
   estacionalidad semanal/mensual de la demanda (el único "trimestral" de Rentabilidad es un proxy
   de recaudación, no de volumen de viajes).

Este inventario es la base de la Fase 2. Los hallazgos, severidad y evidencia puntual viven en
[AUDITORIA_ESTRATEGICO_HALLAZGOS.md](AUDITORIA_ESTRATEGICO_HALLAZGOS.md).
