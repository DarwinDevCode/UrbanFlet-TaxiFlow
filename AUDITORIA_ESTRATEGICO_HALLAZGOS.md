# Auditoría del Nivel Estratégico — Hallazgos (Fase 2)

Basado en el inventario de [AUDITORIA_ESTRATEGICO_INVENTARIO.md](AUDITORIA_ESTRATEGICO_INVENTARIO.md).
Cada hallazgo cita el archivo/línea o query donde se verificó. Severidad:
**crítico** (induce a una decisión errónea o esconde un riesgo real sin advertencia),
**importante** (KPI de bajo valor, redundante, o inconsistente pero no engañoso),
**menor** (mejora de claridad, sin riesgo de decisión errónea).

## Hallazgos transversales (afectan a más de un panel)

### H-T1 [crítico] — 3 de las 8 tarjetas del Tablero Ejecutivo muestran una "variación" que pertenece a OTRO KPI, no al que están mostrando

**Evidencia**: `estrategico/service.py:339-373` (`_crecimiento`, `_rentabilidad`) y `:391-397`
(`_gobernanza`).

- Tarjeta **Crecimiento**: el valor grande es `pct_conversion_onboarding` (% de conversión), pero
  la leyenda "±X% vs. periodo previo" debajo es `variacion_altas_pct` — la variación de un
  **conteo de altas**, una magnitud distinta a la que se está mostrando.
- Tarjeta **Rentabilidad**: el valor es `margen_promedio_pct`, la variación es
  `variacion_recaudacion_trimestral_pct` — variación de recaudación en dólares, no del margen que
  el número grande muestra.
- Tarjeta **Gobernanza**: el valor es `eventos_administrativos` (conteo), la variación es
  `variacion_accesos_denegados_pct` — variación de un KPI de seguridad completamente distinto.

Un usuario de gerencia que lee "Conversión de altas: 98,4% · +12,3% vs. periodo previo" entiende
razonablemente que la conversión subió 12,3 puntos — no es así, subió el **número de altas**. Esto
no es un bug de cálculo (cada número es correcto en su propio dominio) sino un defecto de diseño
de la tarjeta índice: se usó "cualquier variación disponible en `kpis`" en vez de la variación
propia de la métrica mostrada, que en estos 3 casos no existe.

### H-T2 [crítico] — La tarjeta de Gobernanza en el Tablero Ejecutivo pinta en VERDE un aumento de accesos denegados

**Evidencia**: `TableroEjecutivo.tsx:134`, `formato.ts:44-51` (`tonoVariacion`).

Consecuencia directa de H-T1: como la variación mostrada en la tarjeta de Gobernanza es
`variacion_accesos_denegados_pct` pero el tono de color se calcula con
`subirEsBueno: seccion !== "capacidades"` (es decir, `true` para Gobernanza), un **aumento** de
accesos denegados se pinta en verde (`--status-good`) y una **baja** se pinta en rojo. Es lo
opuesto de lo correcto — comparar con `PanelGobernanza.tsx:176` (`subirEsBueno: false` para el
mismo campo, calculado correctamente dentro del panel de detalle). Un ejecutivo que solo mira el
Tablero (el propósito explícito de la pantalla) puede leer una tendencia de seguridad empeorando
como si fuera una buena noticia.

### H-T3 [importante] — El patrón "última corrida sin filtro de fecha" contradice la propia etiqueta de la UI en Capacidades

**Evidencia**: `plataforma/service.py:158-164` — la query `SELECT estado, count() FROM
urbanflet_gold.corridas GROUP BY estado` no tiene ningún `WHERE` de fecha; es un conteo histórico
completo desde que existe la tabla. El frontend (`PanelCapacidades.tsx:153,158`) etiqueta ambos
KPIs como "en el periodo". No hay ventana temporal real detrás de "Corridas OK"/"Corridas
fallidas" pese a que el resto del panel sí tiene selector de ventana (`cortes`) — ese selector no
afecta a estos 2 KPIs en absoluto, solo a la tendencia y a la tabla de dominios.

### H-T4 [confirmado, no nuevo] — `rpt_tasa_cancelacion` sobre-cuenta, y ese defecto ya llegó al nivel estratégico sin advertencia propia

**Evidencia**: `indicadores.py:722-761` (`GROUP BY periodo, zona_origen_id, motivo, actor HAVING
cancelados > 0`), ya documentado como deuda técnica en `CLAUDE.md` §17.11 (222 reportados vs. 45
reales en Mongo para el mismo mes, ~5x). El Panel de Confiabilidad (OE2a) usa esta misma tabla
para `cancelaciones_periodo` (`viajes/service.py:683`). La `NotaLimitacion` visible en pantalla
(`PanelConfiabilidad.tsx:151-158`) solo advierte que la **tasa/porcentaje** no está disponible —
no advierte que el **conteo absoluto** que sí se muestra (y que sí tiene tono de color y variación
con `subirEsBueno: false`, es decir, se trata como una señal confiable de "cancelaciones subieron/
bajaron") es el mismo número ya conocido como sobre-contado. Es el mismo patrón de honestidad que
el proyecto aplica en todos los demás casos, pero aquí queda incompleto: se advierte sobre la tasa
y se calla sobre el volumen, cuando ambos salen de la misma consulta rota.

### H-T5 [menor] — Ninguna variación protege contra "base casi vacía" más allá de excluir `previo=0`

**Evidencia**: `agregacion_estrategica.py:33-41` — `variacion_pct` devuelve `None` solo si
`previo` es `None` o `0`, nunca por ser "pequeño". Con el patrón de datos actual del entorno (2-3
periodos totales en varias `rpt_*`, mezclando el corte histórico NYC-2021 con la operación real
2026-07/08, ver `CLAUDE.md` §17.4), cualquier métrica cuyo periodo anterior tenga un valor bajo
por casualidad de qué corrida quedó como "penúltimo punto" puede producir variaciones de cientos o
miles de puntos porcentuales sin que sea un error de cálculo — solo una base de comparación pobre.
No se encontró un caso concreto con datos reales del entorno al momento de esta auditoría, pero el
mecanismo para producirlo existe y no está mitigado (no hay umbral mínimo de `previo` para mostrar
variación, ni una nota que distinga "variación real" de "variación con base insuficiente").

### H-T6 [confirmado, no reaparece] — El bug de datetime naive/aware NO se repite en el nivel estratégico

**Evidencia**: `auditoria/service.py:35-42` — el único cálculo con `datetime.now(UTC)` del nivel
estratégico (`_inicio_ventana`, usado por Gobernanza) documenta explícitamente por qué no puede
reproducir el bug: el valor aware se usa como filtro de rango dentro de un query Mongo (el driver
serializa ambos lados a BSON UTC sin ambigüedad), nunca se resta contra un valor leído de Mongo
(que vendría naive). Se registra como verificado-sin-hallazgo, no como riesgo activo.

### H-T7 [confirmado, no hay excepciones no documentadas] — La regla "solo `rpt_*`, nunca Mongo directo" se respeta en los 9 paneles

**Evidencia**: grep de imports en los 9 `service.py` — los 8 paneles que no son Gobernanza importan
únicamente `get_clickhouse_client`/`fetch_latest_snapshot`/`fetch_snapshot_history`, salvo Estado y
Costo de Flota que además llama `obtener_placas_vehiculos(db, ...)` (`mantenimiento/service.py:594`)
para resolver la **placa** — un dato descriptivo, no una métrica, mismo patrón ya aceptado
explícitamente en el nivel táctico. Gobernanza es la única excepción real y está documentada en su
propio docstring. No se encontró ninguna excepción no documentada.

---

## Panel por panel — las 6 preguntas de la Fase 2

### 1. Tablero Ejecutivo Consolidado (CU-E01)

1. **Pregunta de negocio por tarjeta**: "¿Cómo está cada uno de los 8 frentes del negocio, de un
   vistazo, con acceso directo al detalle?" — válida como concepto de índice.
2. **Redundante/bajo valor**: ninguna tarjeta es redundante entre sí (cada una resume un dominio
   distinto). El riesgo no es redundancia sino la inconsistencia de H-T1/H-T2.
3. **Falta**: nada estructural — es correcto que sea un índice de 8, no un dashboard con KPIs
   propios.
4. **Relaciones no explotadas**: N/A, es un agregador.
5. **Severidad relativa**: no es el panel más débil por contenido, pero concentra los 2 hallazgos
   críticos transversales (H-T1, H-T2) — es la pantalla que gerencia ve primero y con más
   frecuencia, así que el impacto de esos 2 hallazgos es alto pese a que el panel "en teoría" solo
   reexpone datos ya correctos en otro lado.
6. **Consistencia "—"**: correcta — `valorLegible()` muestra "—" cuando `disponible=false`
   (`TableroEjecutivo.tsx:97-100`).

### 2. Panel de Crecimiento Estratégico (OE1)

1. **Preguntas de negocio**: "¿Qué fracción de las solicitudes de conductor termina siendo un
   socio activo?" (conversión), "¿los socios nuevos siguen operando 90 días después?" (retención),
   "¿cuántos socios nuevos entraron este periodo?" (altas). Las 3 son preguntas formulables en una
   frase — pasan el filtro.
2. **Redundante/bajo valor**: ninguno de los 3 KPIs activos es redundante entre sí. El 4to
   (`crecimiento_demanda_pct`) siempre es `None` — no es "bajo valor", es dato inexistente
   correctamente declarado, no debería contarse como KPI activo del panel.
3. **Qué falta**: una comparación de conversión por canal EN EL TIEMPO (hoy la tabla "canales" es
   solo el consolidado de la ventana, sin tendencia por canal) sería el candidato más natural dado
   que `rpt_conversion_captacion` sí trae `canal` y `periodo` juntos — hoy se usa solo para el
   consolidado, no para una serie temporal por canal.
4. **Relaciones no explotadas**: canal × tiempo (ver punto 3), factible con el dato ya publicado.
   Se descarta explícitamente cruzar con calificación/desempeño del conductor recién dado de alta
   — no hay ninguna tabla que una `fact_registro_usuario` con `rpt_desempeno_conductor` por
   `conductor_id` y periodo de alta.
5. Ranking: **panel de fuerza media** — 3 de 4 KPIs son reales y consistentes, la limitación de
   demanda está bien declarada, el defecto real es solo la tarjeta del Tablero (H-T1).
6. **Consistencia "—"**: correcta. `crecimiento_demanda_pct` se muestra como "—" con nota
   explicativa (`PanelCrecimiento.tsx:142-154`).

### 3. Panel de Confiabilidad y Disponibilidad del Servicio (OE2a)

1. **Preguntas de negocio**: "¿cuánto tarda en asignarse un conductor?", "¿cuántos viajes se
   cancelaron/no tuvieron conductor?", "¿qué % de la flota está activa?". Todas formulables.
2. **Redundante/bajo valor**: ninguno es redundante. `franja_menor_cobertura` es de bajo valor
   añadido porque la tabla "Franjas con menor disponibilidad" de abajo YA muestra exactamente esa
   información ordenada — el KPI es un resumen de una fila que el usuario puede leer igual de la
   tabla, 3 líneas más abajo en la misma pantalla.
3. **Qué falta**: nada que tenga soporte de datos real — la propia auditoría de datos
   (`rpt_tasa_cancelacion`) es la limitante, no la falta de ideas.
4. **Relaciones no explotadas**: explícitamente descartado el cruce zona × franja (no hay zona
   real). El cruce franja-6h × franja-tarifaria tampoco se hace, con razón documentada (taxonomías
   incompatibles).
5. Ranking: **el KPI de cancelaciones es el defecto más serio de calidad de dato de los 9
   paneles** (H-T4) — heredado, no nuevo, pero ahora visible a nivel de junta sin advertencia
   completa.
6. **Consistencia "—"**: la tasa se muestra en "—" correctamente; el conteo NO se muestra en "—"
   pese a estar construido sobre la misma tabla rota — inconsistencia real (ver H-T4).

### 4. Panel de Estado y Costo de Flota (OE2b)

1. **Preguntas de negocio**: "¿se están cumpliendo los mantenimientos preventivos a tiempo?",
   "¿cuánto cuesta mantener la flota?", "¿qué vehículos son candidatos a reemplazo por costo?".
   Todas formulables.
2. **Redundante/bajo valor**: ninguno.
3. **Qué falta**: nada que la spec pida y tenga soporte real — el gap de km está bien declarado.
   Sí falta (dato real disponible, no explotado): **antigüedad del vehículo** — `vehiculos` en
   Mongo probablemente tiene fecha de alta/año de fabricación (no verificado línea por línea en
   esta pasada, señalado como pendiente de confirmar antes de proponerlo como KPI nuevo).
4. **Relaciones no explotadas**: costo × antigüedad (candidato real de la spec, sin verificar aún
   si el dato de antigüedad existe) — no se puede confirmar ni descartar sin una verificación
   adicional del schema de `vehiculos`.
5. Ranking: **panel sólido**, sin hallazgos críticos propios.
6. **Consistencia "—"**: correcta (`km_recorridos` en "—" con nota).

### 5. Panel de Capacidades y Plataforma (OE3)

1. **Preguntas de negocio**: "¿qué % de los datos que entran al sistema se rechazan por mala
   calidad?", "¿qué proceso de datos es el más problemático?", "¿cuántos procesos corrieron bien/
   mal?". Formulables, aunque la 3ra queda mal etiquetada (ver H-T3).
2. **Redundante/bajo valor**: `avance_capacitacion_pct` siempre `None` — mismo caso que
   `crecimiento_demanda_pct`, correctamente declarado pero no debería contar como KPI activo.
3. **Qué falta**: nada con soporte real adicional.
4. **Relaciones no explotadas**: N/A, es un dominio de infraestructura, no de negocio cruzado.
5. Ranking: **el defecto de etiqueta (H-T3) es real pero de bajo impacto en la decisión** — el
   número en sí es correcto, solo la ventana temporal implícita en la etiqueta es falsa.
6. **Consistencia "—"**: correcta.

### 6. Panel de Rentabilidad y Demanda (OE4) — patrón F

1. **Preguntas de negocio**: "¿qué franja horaria deja más margen?", "¿cuánto se recaudó el último
   trimestre?". Formulables. La matriz completa (mes×franja) es la herramienta de exploración, no
   un KPI resumen — coherente con el patrón F declarado.
2. **Redundante/bajo valor**: ninguno de los 3 KPIs resumen es redundante con la matriz — son
   agregados legítimos sobre ella.
3. **Qué falta**: nada con soporte de datos real dado el gap de zona ya declarado.
4. **Relaciones no explotadas**: zona × franja explícitamente descartado (correcto, sin dato). El
   cruce mes×franja SÍ se explota — es la relación central del panel.
5. Ranking: **panel técnicamente más sofisticado de los 9** (única fórmula de prorrateo con
   justificación de negocio explícita) pero también el que más aproximaciones apila: zona fija en
   `false` (nunca se recalcula pese a que Confiabilidad SÍ lo hace con el mismo dato de origen —
   inconsistencia menor entre paneles), demanda como proxy de recaudación, y `share_demanda`/
   `share_capacidad` del último corte aplicados a TODA la ventana histórica. Cada aproximación está
   documentada, pero la acumulación de 3 aproximaciones sobre la misma cifra final (margen) merece
   más cautela de la que transmite un KPI con solo 1 decimal y sin ninguna nota junto al número
   grande (la nota de fórmula solo aparece junto a la matriz, no junto al KPI resumen).
6. **Consistencia "—"**: correcta.

### 7. Panel de Integridad Financiera (OE5 / CU-E04)

1. **Preguntas de negocio**: "¿qué % de los pagos en efectivo conciliaron exacto?", "¿cuánto
   margen deja la comisión?". Formulables.
2. **Redundante/bajo valor**: ninguno.
3. **Qué falta**: nada con soporte real adicional evidente.
4. **Relaciones no explotadas**: comparación interanual ya se explota cuando hay dato; el aviso de
   `dataset_mixto` es honesto y necesario dado el entorno real (NYC 2021 + demo 2026).
5. Ranking: **panel sólido**, el único hallazgo (menor) es el promedio no ponderado entre periodos
   de `margen_comision_promedio` (H visto en inventario, no repetido acá como transversal porque es
   local a este panel) — la media aritmética simple entre periodos de un ratio ya ponderado dentro
   de cada periodo puede pesar igual un mes con 3 liquidaciones que un mes con 300.
6. **Consistencia "—"**: correcta.

### 8. Panel de Cumplimiento Normativo (OE6a)

1. **Preguntas de negocio**: "¿qué % de la documentación (licencias, matrículas) está vigente?",
   "¿cuántos documentos están vencidos ahora mismo?", "¿qué tipo de documento es el más
   problemático?". Formulables.
2. **Redundante/bajo valor**: ninguno.
3. **Qué falta**: nada con soporte real adicional evidente — el panel ya cubre lo que la spec pide
   con el dato disponible.
4. **Relaciones no explotadas**: ninguna identificada con soporte real.
5. Ranking: **uno de los paneles más limpios de los 9** — fuente única, fórmula simple y exacta,
   sin aproximaciones apiladas.
6. **Consistencia "—"**: correcta.

### 9. Panel de Gobernanza de Datos y Seguridad (OE6b / CU-E05) — patrón F

1. **Preguntas de negocio**: "¿cuánta actividad administrativa hubo?", "¿cuántos accesos se
   negaron por permisos?", "¿hubo alertas de seguridad reales (GPS falso, fuerza bruta de
   login)?". Formulables.
2. **Redundante/bajo valor**: ninguno de los 3.
3. **Qué falta**: nada con soporte real adicional — la bitácora ya cubre el universo relevante.
4. **Relaciones no explotadas**: N/A.
5. Ranking: **datos correctos y bien fundamentados** (única ventana con comparación real ventana-
   completa-vs-ventana-completa, más rigurosa que el resto del nivel), pero es el panel donde el
   defecto transversal H-T2 tiene el mayor costo — es, por diseño, el panel de seguridad, y su
   propio KPI de seguridad se pinta al revés en el índice que la mayoría de gerencia va a mirar
   primero.
6. **Consistencia "—"**: N/A, ningún KPI de este panel usa el patrón "—" (los 3 son conteos
   siempre calculables, nunca `None`).

## Ranking priorizado — panel más débil a más fuerte

1. **Tablero Ejecutivo Consolidado** — concentra los 2 hallazgos críticos (H-T1, H-T2); es la
   puerta de entrada de gerencia y el que más fácil induce una lectura equivocada sin que el
   usuario tenga forma de notarlo (los números individuales, vistos en su panel de detalle, SON
   correctos).
2. **Confiabilidad y Disponibilidad del Servicio (OE2a)** — hereda el defecto de dato más grave de
   los 9 (`rpt_tasa_cancelacion`) y lo expone parcialmente sin advertencia completa (H-T4).
3. **Rentabilidad y Demanda (OE4)** — no tiene un hallazgo de "dato incorrecto", pero acumula más
   aproximaciones silenciosas sobre su cifra final que cualquier otro panel.
4. **Capacidades y Plataforma (OE3)** — defecto de etiqueta real pero de bajo impacto (H-T3).
5. **Crecimiento (OE1)** — sólido, con una oportunidad de mejora real (canal × tiempo) sin defecto.
6. **Integridad Financiera (OE5)** — sólido, un detalle menor de ponderación.
7. **Estado y Costo de Flota (OE2b)** — sólido.
8. **Cumplimiento Normativo (OE6a)** — el más limpio de los 9.
9. **Gobernanza de Datos y Seguridad (OE6b)** — datos y fórmulas más rigurosos del nivel; el único
   problema que tiene no es propio, es el que le inflige el Tablero Ejecutivo (H-T2).
