# Diversificación funcional de visualizaciones — propuesta para revisión

Documento de revisión, **sin cambios de código**. Cubre los 9 paneles estratégicos + Tablero
Ejecutivo (`apps/web-interno/src/sections/estrategico/`) y los 10 paneles tácticos
(`apps/web-interno/src/sections/tactico/`), leídos directamente del código real. Cada fila
responde primero la pregunta funcional (§1 del prompt) antes de proponer un cambio — donde la
visualización actual ya es la correcta, se deja "se mantiene" con la razón.

Componentes de gráfico disponibles hoy: `CategoryBarChart` y `TrendLineChart`
(`apps/shared-ui/src/components/charts/`), ambos wrappers de **recharts** (ya instalado). Ninguna
propuesta de abajo requiere una librería nueva — recharts ya soporta barras horizontales
(`layout="vertical"`), barras flotantes (para cascada) y `PieChart`/donut. Un mapa de calor sí
requeriría un componente nuevo simple (grid de celdas, no hay soporte nativo en recharts), sin
librería adicional.

## Nivel estratégico

| Panel / elemento | Visualización actual | Visualización propuesta | Justificación funcional |
|---|---|---|---|
| **Crecimiento** — Tendencia de altas y captación | Línea (2 series: altas, solicitudes) | Se mantiene | Tendencia temporal — línea es correcta. |
| **Crecimiento** — Conversión de altas en el tiempo | Línea (1 serie) | Se mantiene | Tendencia temporal. |
| **Crecimiento** — Conversión por canal en el tiempo | Línea (multi-serie, 1 por canal) | Se mantiene | Tendencia temporal por categoría, pocas series (≤4 canales) — línea multi-serie es la lectura correcta de evolución. |
| **Crecimiento** — Tabla "Conversión por canal (consolidada)" | Tabla (canal, conversión, solicitudes, altas, días) | **Agregar barras** de % conversión por canal, encima de la tabla ya existente | Comparación entre categorías (4 canales) — hoy solo se puede comparar leyendo números en fila; un vistazo a barras muestra de inmediato qué canal convierte mejor. La tabla se conserva íntegra debajo para las columnas que las barras no pueden mostrar (solicitudes, altas, días de aprobación). |
| **Confiabilidad** — 3 líneas de tendencia (asignación, cancelaciones, flota activa) | Línea | Se mantiene | Tendencia temporal en los 3 casos. |
| **Confiabilidad** — Tabla "Franjas con menor disponibilidad" | Tabla (4 franjas, ya ordenada ascendente) | **Barras horizontales** ordenadas por disponibilidad | Ranking de N elementos (4 franjas) — ya viene pre-ordenado en el código (`franjasOrdenadas`), señal de que el propio desarrollo ya pensaba en un ranking. Barras horizontales comunican "cuál franja está peor" de un vistazo; se conserva la tabla debajo solo para la columna "Registros" que las barras no muestran. |
| **Confiabilidad** — Tabla "Tiempo de asignación por franja tarifaria" | Tabla (2 filas: diurna/nocturna) | Se mantiene | Solo 2 categorías — no hay ganancia real de convertir una tabla de 2 filas en gráfico. |
| **Estado y Costo de Flota** — Costo total por mes | Barras (categoría = mes) | Se mantiene | Aunque es una serie temporal, son totales discretos por mes (no una magnitud continua) — barras mensuales es un patrón estándar y legible para "costo del mes", no confunde. |
| **Estado y Costo de Flota** — Cumplimiento preventivo (%) | Línea | Se mantiene | Tendencia temporal. |
| **Estado y Costo de Flota** — Tabla "Vehículos candidatos a reemplazo" | Tabla | **Agregar barras horizontales de ranking** (por costo acumulado), encima de la tabla | Ranking de N vehículos por costo — mismo criterio que "Franjas con menor disponibilidad". La tabla se conserva para meses con costo, órdenes y km (este último en "—", dato no disponible). |
| **Capacidades y Plataforma** — Tendencia y barras por dominio | Línea + barras (ya existen) | Se mantiene | Tendencia temporal correcta; comparación entre 7 dominios ya usa barras — correcto. |
| **Capacidades y Plataforma** — Tabla "Calidad de datos por dominio" | Tabla | Se mantiene | Mismos datos que el gráfico de barras de arriba (dominio × %) — convertirla también sería redundancia, no variedad funcional. Se queda como el detalle con columnas Extraídos/Rechazados que el gráfico no muestra. Un mapa de calor dominio × periodo sería la mejora natural, pero el endpoint actual solo trae el último corte por dominio (sin serie de periodos por dominio) — no hay dato para construirlo sin tocar el backend, fuera de alcance de esta ronda. |
| **Rentabilidad y Demanda** — Demanda de largo plazo | Línea | Se mantiene | Tendencia temporal. |
| **Rentabilidad y Demanda** — Tabla "Resumen por franja" | Tabla (2 filas) | Se mantiene | Solo 2 categorías, tarjeta de contexto en patrón F — no justifica gráfico propio. |
| **Rentabilidad y Demanda** — "Matriz de rentabilidad: mes × franja" | Tabla (elemento dominante del panel) | **Mapa de calor** (margen % por celda, mes × franja), con la tabla de detalle conservada debajo | Candidato explícito del prompt. Intensidad por 2 dimensiones cruzadas (mes × franja) es exactamente el caso de uso de un mapa de calor — con solo 2 franjas × N meses, escanear visualmente qué meses/franjas son menos rentables es mucho más rápido que leer una tabla fila por fila. La tabla se conserva íntegra debajo (recaudación, comisión, costo, participación en demanda/capacidad — columnas que el mapa de calor no puede mostrar). Requiere un componente nuevo (grid de celdas con escala secuencial de un solo tono, paleta de la skill `dataviz`), sin librería nueva. |
| **Integridad Financiera** — Conciliación y discrepancias en el tiempo | Línea (2 series) | Se mantiene | Tendencia temporal — es la pregunta correcta aquí (evolución), no composición. |
| **Integridad Financiera** — KPIs "Conciliado" / "Tasa de discrepancias" | 2 tarjetas de texto separadas | **Considerado y descartado**: un donut o barra apilada de 2 segmentos | Evaluado explícitamente por ser candidato del prompt. Decisión: las 2 tarjetas KPI ya están una junto a la otra y sus valores son complementarios de forma obvia (suman ~100%); agregar una composición visual sería reforzar algo que el texto ya comunica sin ambigüedad, no resolver un problema de lectura real. Se prioriza la propuesta de cascada de abajo, que sí responde una pregunta que hoy no tiene visualización. |
| **Integridad Financiera** — Margen de comisión (%) | Línea | **Agregar cascada** (Bruto → −Comisión → Neto) del último periodo, junto al KPI "Margen de comisión prom." | Contribución de un factor (comisión) a un total (bruto → neto) — hoy solo existe como línea de tendencia del %, que no muestra "a dónde va la plata". Los campos `bruto_total`/`comisiones_total` ya vienen en `tendencia_margen`, sin cálculo de negocio nuevo (solo la resta bruto−comisión=neto, ya usada en otros paneles). La línea de tendencia se conserva — responde una pregunta distinta (evolución del %, no composición de un periodo). Requiere componente nuevo (barra flotante sobre recharts), sin librería nueva. |
| **Integridad Financiera** — "Periodos con discrepancia relevante" / "Comparación interanual" | Tabla / Barras + tabla | Se mantiene | Detalle fila a fila (tabla) y comparación entre años (barras) ya son las elecciones correctas. |
| **Cumplimiento Normativo** — Tendencia de vigencia | Línea | Se mantiene | Tendencia temporal. |
| **Cumplimiento Normativo** — "Vigencia por tipo de documento" (gráfico) y "Exposición por tipo" (tabla) | Barras verticales + tabla | **Barras horizontales con banda de umbral** (estilo bullet: 90% bueno / 70% advertencia / debajo peligro) | Candidato explícito del prompt: "hay un umbral implícito de vigente/no vigente". Ese umbral YA existe en el código (`Badge tono`: `>=0.9` éxito, `>=0.7` advertencia, si no peligro) — hoy se ve solo como color de una tabla, nunca como posición contra una banda. Con solo 2 tipos de documento, un bullet-style deja ver de un vistazo cuánto le falta a cada tipo para salir de la zona de riesgo, no solo cuál es mayor. No es una barra genérica nueva — es la misma comparación de categorías (2 tipos) enriquecida con la banda que ya existe en la lógica de color. Requiere extender `CategoryBarChart` (o un componente pequeño nuevo) con soporte de `ReferenceArea`/`ReferenceLine` de recharts — ya instalado. |
| **Gobernanza** — Tendencia (3 series) | Línea | Se mantiene | Tendencia temporal. |
| **Gobernanza** — Bitácora de eventos | Tabla (elemento dominante, patrón F) | Se mantiene | Detalle fila a fila que se necesita comparar — exactamente el caso que el prompt marca como "no reemplazar solo por variedad". |
| **Desempeño de Conductores** — "Top 10 por viajes completados" | Barras verticales | **Barras horizontales** ordenadas descendente | Candidato explícito del prompt (mismo caso que su gemelo táctico). Ranking de N elementos con nombres de socios que pueden ser largos — barras horizontales evitan la rotación de etiquetas que hoy usa `CategoryBarChart` cuando hay más de 6 categorías. |
| **Desempeño de Conductores** — "Detalle por socio y trimestre" | Tabla | Se mantiene | Detalle multi-columna que se compara fila a fila. |
| **Tablero Ejecutivo** — 8 tarjetas con KPI + mini-tendencia | Sparkline sin ejes | Se mantiene | Candidato explícito del prompt para bullet chart "si existe un umbral/meta definido". Verificado contra el schema real (`TableroEjecutivoOut`): **ningún headline trae un campo de meta/umbral** — el backend no publica ninguno. Agregar un bullet chart exigiría inventar una meta institucional que no existe en ningún lado del sistema, violando la regla de no fabricar datos. Queda documentado como pendiente de una definición de negocio (qué meta tiene cada indicador), no como algo descartado por falta de mérito. |

## Nivel táctico

| Panel / elemento | Visualización actual | Visualización propuesta | Justificación funcional |
|---|---|---|---|
| **Despacho** — Tiempo de asignación por zona y franja | Barras verticales | Se mantiene | Comparación entre categorías (combinaciones zona×franja), pocas categorías visibles a la vez tras filtrar — barras verticales siguen siendo legibles. |
| **Despacho** — 2 tablas de detalle (activos / sin conductor) | Tabla | Se mantiene | Detalle operativo fila a fila, uso explícito de "actuar sobre lo que se ve" (spec de nivel táctico). |
| **Rendimiento de Conductores** — "Viajes completados por socio" | Barras verticales | **Barras horizontales** ordenadas descendente | Mismo criterio que su gemelo estratégico — ranking con nombres de socios, mejor legibilidad en horizontal. |
| **Rendimiento de Conductores** — Tabla de detalle | Tabla | Se mantiene | Comparación fila a fila por socio y periodo. |
| **Auditoría e Integraciones** — "Uso de API por endpoint" | Barras verticales (~12 endpoints) | **Barras horizontales** ordenadas por conteo | Ranking de N elementos (endpoints) — las rutas de API son cadenas largas (ej. `/mantenimiento/panel-tactico/costo-top-vehiculos`), justo el caso que el prompt señala como el que más se beneficia de barras horizontales. |
| **Auditoría e Integraciones** — Bitácora | Tabla (dominante, patrón F) | Se mantiene | Mismo caso que su gemelo estratégico — detalle que se compara fila a fila. |
| **Vigencia Documental** — "Documentación vigente por tipo" | Barras verticales (2 tipos) | **Barras horizontales con banda de umbral** (mismo criterio que Cumplimiento Normativo estratégico) | Mismo par tipo/% vigente con el mismo umbral 90%/70% ya usado en el `Badge` — se propone el mismo tratamiento en ambos niveles para mantener consistencia entre el panel táctico y su versión consolidada estratégica. |
| **Vigencia Documental** — Tendencia mensual por tipo | Línea (multi-serie) | Se mantiene | Tendencia temporal por categoría — correcto. |
| **Vigencia Documental** — Tabla de documentos | Tabla | Se mantiene | Detalle operativo, acción directa (aprobar/observar). |
| **Mantenimiento** — "Costo por vehículo (top 5)" | Barras verticales | **Barras horizontales** ordenadas descendente | Mismo criterio que su gemelo estratégico ("Vehículos candidatos a reemplazo") — ranking de 5 vehículos, placas como etiqueta. |
| **Mantenimiento** — Cumplimiento preventivo por mes | Línea | Se mantiene | Tendencia temporal. |
| **Mantenimiento** — 2 tablas (órdenes abiertas / retirados) | Tabla | Se mantiene | Detalle operativo accionable. |
| **Conciliación** — Tasa de discrepancias mensual | Línea (multi-serie por método) | Se mantiene | Tendencia temporal por categoría (método de pago). |
| **Conciliación** — 2 tablas (discrepancias / sin pago) | Tabla | Se mantiene | Detalle operativo accionable — mismo criterio que su gemelo estratégico, sin agregar composición aquí: el nivel táctico ya desglosa por método (no es un binario conciliado/discrepancia como en el resumen estratégico), y el usuario actúa sobre discrepancias individuales, no sobre el agregado. |
| **Liquidación** — Margen de comisión por mes | Línea | **Agregar cascada** (Bruto → −Comisiones → Neto) del último mes, junto a los KPIs | Mismo criterio que su gemelo estratégico — los campos `bruto_total`/`comisiones_total` ya vienen en `margen[]` (`/liquidaciones/panel-tactico/margen-comision`). Responde "a dónde va la comisión" en el mes vigente, algo que hoy solo se puede inferir restando 2 números. |
| **Liquidación** — Tabla de liquidaciones | Tabla | Se mantiene | Detalle accionable (aprobar/pagar/observar por fila). |
| **Captación** — Conversión de altas por canal | Línea (multi-serie) | Se mantiene | Tendencia temporal por categoría — no tiene una tabla-resumen-por-canal equivalente a la de su gemelo estratégico (el táctico muestra solicitudes pendientes + referidos, no un resumen por canal), así que el candidato de "agregar barras" no aplica aquí de forma directa. |
| **Captación** — 2 tablas (pendientes / referidos) | Tabla | Se mantiene | Detalle operativo accionable (plazo, incentivo). |
| **Flota** — % de flota activa por franja horaria | Barras verticales (4 franjas) | Se mantiene | Comparación entre categorías, ya con la elección correcta — pocas categorías, sin necesidad de horizontal. |
| **Flota** — Tabla de vehículos sin señal | Tabla | Se mantiene | Detalle operativo accionable. |
| **Plataforma** — % de registros rechazados por dominio | Barras verticales (7 dominios) | Se mantiene | Comparación entre categorías — mismo criterio que su gemelo estratégico (Capacidades), consistencia entre ambos niveles. |
| **Plataforma** — Tabla de corridas | Tabla | Se mantiene | Detalle operativo (estado por corrida). |

## Candidatos evaluados y descartados explícitamente

- **Embudo (funnel) para el proceso de captación** (solicitud enviada → verificación → aprobada →
  primer viaje): sería el ajuste natural para "etapas consecutivas de un proceso", pero ningún
  endpoint actual devuelve el conteo por etapa como serie — solo trae el % de conversión ya
  agregado. Construirlo exigiría una agregación de negocio nueva en el backend, fuera del alcance
  de esta ronda (solo capa de presentación).
- **Dispersión (scatter) costo vs. km recorridos** en "Estado y Costo de Flota": es la lectura
  natural para "relación entre 2 variables cuantitativas", pero `km_recorridos` ya viene marcado
  como no disponible (`km_disponible: false`, columna en "—") — no hay dato real que graficar.
  Documentado como mejora futura si el dato de kilometraje se resuelve algún día.
- **Gauges individuales por KPI con umbral implícito** (ej. "Cumplimiento preventivo" con el 80%
  usado en el `tono` de la tarjeta): evaluado y descartado de forma sistemática en toda la app —
  el `KpiCard` ya comunica el estado bueno/advertencia/peligro por color: agregar un gauge junto a
  cada tarjeta individual sería redundante con esa señal ya existente, y sobrecargaría los
  paneles sin una pregunta nueva que responder. Los 2 casos donde SÍ se propone un tratamiento de
  banda (Cumplimiento Normativo, Vigencia Documental) son distintos: ahí se está reemplazando un
  gráfico de comparación entre categorías ya existente, no añadiendo un elemento nuevo por cada
  tarjeta.
