# Auditoría del Nivel Estratégico — Propuesta de KPIs y Drill-down (Fases 3-4)

Depende de [AUDITORIA_ESTRATEGICO_INVENTARIO.md](AUDITORIA_ESTRATEGICO_INVENTARIO.md) y
[AUDITORIA_ESTRATEGICO_HALLAZGOS.md](AUDITORIA_ESTRATEGICO_HALLAZGOS.md). Ningún cambio de código
se ejecutó en esta ronda — este documento es la propuesta a aprobar antes de la siguiente etapa.

## 1. KPIs a eliminar

**Ninguno.** No se encontró ningún KPI activo cuyo valor sea ruido puro o cuya pregunta de negocio
no se pueda formular. Los 4 candidatos más débiles (`crecimiento_demanda_pct`,
`avance_capacitacion_pct`, `franja_menor_cobertura`, `margen_comision_promedio`) ya están
correctamente declarados como no disponibles o son de bajo-pero-no-nulo valor (`franja_menor_
cobertura` duplica una fila de tabla visible, pero orientar al lector sin que busque no es dañino
— se recomienda **fusionar visualmente, no eliminar**, ver §3).

## 2. KPIs a corregir

### C1 — Tablero Ejecutivo: variación mostrada debe pertenecer al mismo KPI que el valor (H-T1, H-T2)

**Corrección de fondo, no cosmética.** Para las 3 tarjetas afectadas (Crecimiento, Rentabilidad,
Gobernanza), dos caminos posibles — decisión de negocio, no técnica:

- **Opción A (recomendada)**: cada tarjeta muestra la variación de SU PROPIO valor. Requiere que
  el backend calcule una variación propia donde hoy no existe:
  - Crecimiento: variación de `pct_conversion_onboarding` entre los últimos 2 cortes de
    `rpt_conversion_onboarding` (el dato ya está en `tendencia_onboarding`, el cálculo es trivial
    con `variacion_pct` ya existente).
  - Rentabilidad: variación de `margen_promedio_pct` — requiere calcular el margen del periodo
    anterior con la misma fórmula (factible, mismos `rpt_*` de origen, un mes más atrás).
  - Gobernanza: variación de `eventos_administrativos` — mismo mecanismo ya usado para
    `accesos_denegados` (`_inicio_ventana(meses*2)`), solo aplicado a la otra cuenta.
- **Opción B**: si no se calcula la variación propia, quitar la línea de variación de esas 3
  tarjetas y mostrar únicamente "Sin variación comparable" (ya es el comportamiento cuando
  `variacion_pct` es `None`) — más honesto que mostrar la variación de otro KPI, aunque pierde
  información real que sí existe (la variación de accesos denegados, de altas, de recaudación son
  datos reales y útiles, solo que no pertenecen a ESA tarjeta).

En ambos casos, corregir `subirEsBueno` de Gobernanza a `false` (H-T2) es obligatorio
independientemente de cuál opción se elija — hoy es un error de signo real, no una decisión de
diseño.

### C2 — "Corridas OK" / "Corridas fallidas": acotar por ventana o renombrar (H-T3)

Dos caminos, cualquiera resuelve el hallazgo:

- **Opción A (recomendada, bajo esfuerzo)**: acotar la query a la ventana de `cortes` ya presente
  en el selector del panel — traducir `cortes` a un rango de fechas sobre `corridas.iniciado_en`
  (columna que ya existe, confirmada en el modal de drill-down de `PanelCapacidades.tsx:284`).
  Mantiene la etiqueta "en el periodo" veraz.
- **Opción B (esfuerzo mínimo)**: si se prefiere mantener el conteo histórico completo (puede ser
  intencional — "salud acumulada del pipeline"), renombrar a "Corridas OK (histórico)" / "Corridas
  fallidas (histórico)" y quitar la palabra "periodo" de la descripción.

### C3 — Panel de Confiabilidad: extender la advertencia de `rpt_tasa_cancelacion` al conteo, no solo a la tasa (H-T4)

Bajo esfuerzo, solo frontend: ampliar la `NotaLimitacion` ya existente
(`PanelConfiabilidad.tsx:151-158`) para declarar explícitamente que el **conteo absoluto**
(`cancelaciones_periodo`) también hereda el sobre-conteo conocido de `rpt_tasa_cancelacion`, no
solo la tasa. Alternativa más fuerte (mayor esfuerzo, toca ETL): corregir el `GROUP BY` de
`indicadores.py::refrescar_tasa_cancelacion` para que deje de sobre-contar — pero eso es
exactamente el trabajo ya señalado como pendiente en `CLAUDE.md` §17.11 y está fuera del alcance
de "solo corregir la presentación" de esta ronda.

### C4 — Rentabilidad: recalcular `zona_disponible` en vez de dejarlo fijo en `false`

Menor. `viajes/service.py` (Confiabilidad) ya calcula `zona_disponible` real a partir de las
filas de `rpt_tiempo_asignacion` (línea 677-678); `estrategico/service.py` (Rentabilidad) usa la
MISMA tabla como fuente de `share_demanda` pero deja `zona_disponible=False` fijo. Aplicar el
mismo cálculo por consistencia — hoy, si el dato de zona llegara a resolverse, Confiabilidad lo
reflejaría automáticamente y Rentabilidad seguiría diciendo "no disponible" hasta un despliegue
nuevo de código.

### C5 — Integridad Financiera: ponderar `margen_comision_promedio` entre periodos, no promediar plano

Menor. Cambiar `sum(p["margen"] for p in tendencia_margen) / len(tendencia_margen)` (media simple)
por `promedio_ponderado(tendencia_margen, "margen", "bruto_total")` (ya importado en el módulo,
usado en otras partes del mismo archivo) para que un mes con más recaudación pese más que uno con
poca.

## 3. KPIs nuevos a agregar

Ordenados por dominio, solo con fuente verificada — ningún KPI de esta lista requiere una tabla
`rpt_*` nueva salvo donde se indica explícitamente.

### N1 — Crecimiento: conversión por canal EN EL TIEMPO (no solo consolidada)

**Pregunta de negocio**: "¿qué canal de captación está mejorando o empeorando su conversión mes a
mes?" **Fuente**: `rpt_conversion_captacion` ya trae `canal` + `periodo` juntos — hoy se usa solo
para el consolidado de la ventana (`canales`), nunca como serie temporal. **Esfuerzo**: bajo,
mismo dato ya cargado, solo una transformación nueva de agregación (pivotar por canal × periodo,
mismo patrón ya usado en el nivel táctico para "conversión por canal" — `CLAUDE.md` §13.3).

### N2 — Estado y Costo de Flota: costo vs. antigüedad del vehículo (condicional)

**Pregunta de negocio**: "¿los vehículos más viejos son también los más caros de mantener?"
**Fuente**: requiere confirmar si `vehiculos` (Mongo) tiene un campo de año/fecha de alta
utilizable — **no verificado en esta pasada** (ver Hallazgos, panel OE2b, punto 3). Si existe, es
un dato descriptivo (mismo patrón ya aceptado para la placa), no rompe la regla de "solo
`rpt_*`" para las métricas. **Esfuerzo**: bajo si el campo existe y solo falta resolverlo igual que
la placa; **medio** si no existe y hay que agregarlo al modelo.

### N3 — Capacidades: acotar "Corridas OK/fallidas" a la ventana (ver C2, es corrección y adición a la vez)

### N4 — Integridad Financiera: no se identificó un KPI nuevo con soporte de datos real

Se evaluó "concentración de recaudación por conductor/socio" — pero eso requiere
`rpt_ingreso_conductor`, que hoy es una tabla táctica sin dimensión de tiempo agregada a nivel
estratégico. Ver N6.

### N5 — Cumplimiento Normativo: no se identificó un KPI nuevo con soporte real adicional

El panel ya cubre el 100% de lo que `rpt_documentacion_vigente` puede ofrecer.

### N6 — Nuevo panel/sección candidata (fuera del alcance de "agregar un KPI a un panel existente"): Desempeño y Concentración de la Flota de Conductores

**Pregunta de negocio**: "¿la operación depende de forma riesgosa de un puñado de conductores?
¿la calidad de servicio (calificación, % de viajes completados) es homogénea o hay una cola larga
de bajo desempeño?" **Fuente real y ya construida**: `rpt_desempeno_conductor` +
`rpt_ingreso_conductor` (ambas con datos reales, construidas en la sesión de "Rendimiento de
Conductores" táctico — `CLAUDE.md` §17.4). Hoy ninguna llega al nivel estratégico. **Esfuerzo**:
bajo en cuanto a dato (las tablas ya existen y tienen datos reales) pero el diseño de un KPI de
"concentración" (ej. % de viajes o ingresos que caen sobre los 3 conductores con más volumen) es
una decisión de negocio nueva — no hay un umbral de concentración documentado en ninguna spec.
**Nota de honestidad de dato requerida**: el entorno de desarrollo tiene una concentración
artificial conocida (5 conductores con ~270K viajes cada uno por el patrón de siembra NYC, ver
`CLAUDE.md` §8.5/§17.4) — cualquier KPI de concentración construido sobre este entorno mostrará un
número alarmante que es un artefacto del dataset de desarrollo, no una señal real de negocio. Se
recomienda explícitamente advertirlo en la UI si se construye, o esperar a datos de producción
reales.

### N7 — Rotación de conductores (bajas), NO recomendado construir todavía

**Pregunta de negocio**: "¿cuántos socios dejan la cooperativa por periodo, y por qué motivo?"
**Fuente**: el evento existe (`usuarios.estado="BAJA"`, acción de auditoría `USUARIO_BAJA`) pero
**no hay ninguna tabla Gold que lo agregue por periodo** — construirlo violaría la regla de "no
Mongo directo" a menos que se agregue una tabla `rpt_*` nueva alimentada por un DAG nuevo (o se
extienda `dag_captacion_gold`, que ya extrae `usuarios`, para capturar también las bajas). Es el
único KPI nuevo de esta lista que requiere trabajo de ETL antes de poder implementarse — no se
propone su fórmula aquí porque no hay una tabla real sobre la cual definirla todavía.

## 4. Candidatos a drill-down (Fase 3)

4 KPIs estratégicos ya tienen drill-down real construido (confirmado en código, no en teoría):
"Corridas fallidas" (Capacidades), "Documentos vencidos" (Cumplimiento Normativo), "Eventos
administrativos" y "Accesos denegados" (Gobernanza) — mismo patrón `KpiCard.onClick` +
`KpiDetalleModal` del rollout operativo/táctico de 24 KPIs.

### Candidatos nuevos, con filtro/consulta y columnas propuestas

| KPI | Panel | Filtro/consulta del listado | Columnas del modal | Esfuerzo |
|---|---|---|---|---|
| Corridas OK | Capacidades | Mismo modal ya construido para "Corridas fallidas" (`GET /plataforma/panel-tactico/corridas`), cambiar el filtro inicial de estado a `OK`/`WARN` en vez de `FAILED` | Igual a las ya definidas (`columnasEventoGobernanza`-equivalente ya existe en el modal actual) | Muy bajo — el modal y la fuente ya existen, solo falta el segundo `onClick` |
| Tasa de discrepancias | Integridad Financiera | Reusar `GET /pagos/discrepancias` (ya construido y ya drill-downed a nivel táctico en Conciliación, `CLAUDE.md` §17.8) | Viaje, monto esperado, monto cobrado, diferencia, método de pago, fecha | Bajo — mismo endpoint, 1 fetch nueva al abrir |
| Cumplimiento preventivo | Estado y Costo de Flota | Reusar `GET /mantenimiento/panel-tactico/cumplimiento-preventivo` (fuente simple ya usada a nivel táctico) filtrando a órdenes que incumplieron plazo | Vehículo (placa), fecha programada, fecha cierre, días de atraso | Bajo — endpoint táctico ya existe |
| Costo del último periodo / Costo acumulado | Estado y Costo de Flota | La tabla "Vehículos candidatos a reemplazo" YA es un listado (top 10) — no se propone un modal adicional, se considera cubierto | N/A | N/A — ya resuelto por diseño de panel |
| Alertas de seguridad | Gobernanza | Mismo patrón que "Accesos denegados": `GET /auditoria/eventos?accion=LOGIN_FALLIDO_CONSECUTIVO,POSIBLE_GPS_SPOOFING&desde=<metadata.desde>` (requiere confirmar si el endpoint soporta múltiples valores de `accion` separados por coma o si hace falta 2 llamadas) | Fecha, actor, acción, entidad, resultado (mismas columnas ya definidas para el resto de Gobernanza) | Bajo — mismo patrón ya construido 2 veces en el mismo panel |

### KPIs NO candidatos a drill-down, con razón (mismo criterio que "Altas de socios"/"Cancelaciones del periodo" del rollout anterior)

| KPI | Panel | Razón |
|---|---|---|
| Conversión de altas / Retención a 90 días / Documentación vigente / Conciliado / Tasa de discrepancias (como %) / Cumplimiento preventivo (como %) / Registros rechazados global | Todos | Son porcentajes/promedios ponderados sobre un snapshot agregado — no existe "la fila que es ese porcentaje", mismo criterio que descartó los ~40 KPIs de este tipo en el rollout operativo/táctico |
| Altas de socios (periodo) | Crecimiento | **Ya evaluado y descartado en la ronda anterior** (`CLAUDE.md` §17.11) — ningún endpoint Mongo mapea de forma confiable al mismo corte que usa `rpt_altas_retencion_canal`. Se reafirma la decisión, no hay información nueva que la cambie. |
| Cancelaciones del periodo | Confiabilidad | **Ya evaluado y descartado en la ronda anterior**, y con razón reforzada por esta auditoría: el número en sí está bajo sospecha de sobre-conteo (H-T4) — construir un drill-down sobre un número ya cuestionado sería peor que no construirlo, mostraría filas que no explican el conteo real. |
| Recaudación último trimestre | Rentabilidad | Sale de `rpt_margen_comision` (agregado mensual), no de transacciones individuales — bajar al detalle de "qué liquidaciones componen este trimestre" requeriría consultar `fact_liquidacion`/Mongo directo, prohibido en este nivel (regla §2 de la spec estratégica) |
| Margen promedio / Franja menos rentable / Margen de esa franja | Rentabilidad | La matriz mes×franja YA es el detalle — un modal adicional sería redundante con una tabla que ya está siempre visible en el panel (patrón F) |
| Franja con menor cobertura / Franja de tiempo de asignación | Confiabilidad | Mismo caso — las tablas "Franjas con menor disponibilidad"/"Tiempo de asignación por franja" ya están siempre visibles, no ocultas detrás de un clic |
| Dominio más afectado / Tipo más expuesto | Capacidades / Cumplimiento Normativo | Labels que apuntan a una fila ya visible en la tabla del propio panel |
| 8 tarjetas del Tablero Ejecutivo | Tablero | Son navegación a otro panel (`Ver detalle`/`Ver táctico`), no drill-down a registros — patrón ya correcto y distinto por diseño (`CLAUDE.md` §13.4) |

## 5. Priorización

### Alto impacto / bajo esfuerzo — hacer primero

1. **C1, opción B únicamente para Gobernanza** (quitar la variación mal etiquetada y corregir el
   signo de color) — el hallazgo más crítico (H-T2, seguridad mostrada en verde) con el fix más
   barato disponible de inmediato.
2. **C2 / N3** — acotar "Corridas OK/fallidas" a la ventana ya seleccionada, o renombrar. Cambio
   de una query.
3. **C3** — ampliar la nota de limitación de Confiabilidad. Cambio de texto únicamente.
4. **Drill-down de "Corridas OK"** — el modal y la fuente ya existen, falta un segundo botón.
5. **Drill-down de "Alertas de seguridad"** — mismo patrón ya construido 2 veces en el mismo
   panel, tercera repetición de bajo riesgo.

### Impacto medio / esfuerzo medio

6. **C1, opción A completa** (calcular variación propia para Crecimiento y Rentabilidad en el
   Tablero) — requiere tocar 2 `service.py` de dominio, pero reutiliza `variacion_pct` ya existente.
7. **C4** (recalcular `zona_disponible` en Rentabilidad) y **C5** (ponderar
   `margen_comision_promedio`) — cambios pequeños y aislados, sin urgencia de negocio.
8. **Drill-down de Tasa de discrepancias y Cumplimiento preventivo** — reusan endpoints tácticos
   ya construidos, el trabajo es de integración en el panel estratégico, no de backend nuevo.
9. **N1** (conversión por canal en el tiempo) — dato ya disponible, solo falta la transformación y
   el componente de gráfico (ya existe `TrendLineChart`, patrón ya usado en otros paneles).

### Requiere decisión de negocio antes de poder ejecutarse (no es una decisión técnica)

- **N6** (panel de desempeño/concentración de conductores): antes de construirlo, alguien con
  autoridad de negocio debe definir qué umbral de concentración es "aceptable" vs. "riesgo" — hoy
  no existe esa meta en ninguna spec, y construir el KPI sin ella deja al lector sin forma de
  interpretar el número (mismo criterio que el prompt pidió aplicar: "señalar dónde establecerla
  tendría sentido" sin inventarla).
- **H-T5** (variaciones con base casi vacía): la mitigación real (ej. "no mostrar variación si el
  periodo anterior tiene menos de N registros") requiere que alguien defina ese `N` — es un umbral
  de negocio, no una regla técnica objetiva.
- **N2** (costo vs. antigüedad): depende de si el dato de antigüedad existe en `vehiculos` — pura
  verificación técnica pendiente, no bloqueada por una decisión de negocio, pero bloqueada por
  investigación no completada en esta ronda.

### Requiere cambio de modelo de datos / ETL (mayor esfuerzo, no para esta ronda)

- **N7** (rotación/bajas de conductores): necesita una tabla `rpt_*` nueva y extender un DAG
  existente (o crear uno) — es el único KPI nuevo de todo este documento que no puede construirse
  solo con lo que ya existe en ClickHouse.
- **Corrección de raíz de `rpt_tasa_cancelacion`** (alternativa fuerte a C3): reescribir el
  `GROUP BY`/`HAVING` de `indicadores.py::refrescar_tasa_cancelacion` para que deje de sobre-
  contar. Ya estaba señalado como pendiente antes de esta auditoría (`CLAUDE.md` §17.11); esta
  auditoría solo confirma que el impacto ahora alcanza también al nivel estratégico (Confiabilidad,
  H-T4), lo que sube su prioridad relativa frente a otros pendientes de ETL, pero sigue siendo
  trabajo de mayor esfuerzo que cualquier ítem de las 2 primeras categorías.
