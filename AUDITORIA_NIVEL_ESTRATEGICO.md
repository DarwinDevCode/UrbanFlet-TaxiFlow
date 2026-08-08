# Auditoría de conformidad — Nivel Estratégico y prerrequisitos

Fecha de auditoría: 2026-08-08 (reloj real del stack; el contexto de sesión decía 2026-08-07 — hay
un desfase de zona horaria entre el host y los contenedores, confirmado con `date -u` en ambos:
host y ClickHouse marcan `2026-08-08 02:00 UTC`).

Metodología: para cada afirmación de `CLAUDE.md` relevante al nivel estratégico se intentó
verificación directa contra código real (`Read`/`Grep`) y contra datos reales (`mongosh`,
`clickhouse-client`, `airflow dags list-runs`, `pytest`). Todo lo marcado "verificado esta
auditoría" corresponde a una consulta ejecutada en esta sesión, no a una cita de `CLAUDE.md`. Donde
no se repitió la verificación completa (por alcance/tiempo) se cita explícitamente como "según
CLAUDE.md, no re-verificado a fondo esta sesión" — no se reporta nada como cerrado sin evidencia
propia o cita explícita de la fuente.

Categorías de clasificación usadas en todo el documento:

1. Completamente implementado y funcional (backend+frontend+integración real verificada)
2. Parcialmente implementado (se especifica qué falta)
3. Interfaz sin funcionalidad real detrás
4. Backend sin integración con frontend
5. Frontend sin soporte backend (UI asume endpoint inexistente o usa datos simulados)
6. Datos simulados/hardcodeados en lugar de reales
7. Especificado pero inexistente
8. Existente pero no coincide con lo especificado (con discrepancia exacta)
9. Funciona para su propósito actual, pero necesita modificación para el nivel estratégico

---

## 1. Resumen ejecutivo del estado actual

| Nivel | % de cierre estimado | Sustento |
|---|---:|---|
| Operativo (19 CU-O, backlog consciente descontado) | ~92% | 17/19 CU-O construidos backend+frontend con verificación histórica en navegador (según CLAUDE.md, spot-check parcial esta sesión). 6 ítems de backlog consciente correctamente excluidos del cálculo (documentados, no olvidos). Un hallazgo positivo no documentado en CLAUDE.md: **CU-O05 A3 (reintentar búsqueda tras SIN_CONDUCTOR) SÍ está implementado en código real** (`apps/web-pasajero/src/App.tsx:1100-1134`, función `reintentarBusqueda`), contradiciendo CLAUDE.md §3/§6 que lo da por no construido — ver hallazgo H1 en Sección 6. Persisten 2 gaps reales confirmados: `movimientos.tipo="AJUSTE"` = 0 documentos reales en Mongo (verificado, backend/tests pasan pero sin flujo end-to-end cableado), y `zona_origen_id`/`zona_destino_id` = 0/1,334,888 documentos no nulos (verificado con `mongosh`, confirma el gap crítico para OE4). |
| Táctico (9 dashboards + 16 endpoints/informes) | ~95% | Los 12 `rpt_*` que audita esta sesión existen y tienen datos frescos (`actualizado_en` de hoy) salvo `rpt_documentacion_vigente` (0 filas, consistente con `documentos` teniendo ahora 142 filas reales pero ninguna corrida reciente de `dag_cumplimiento_gold` aparentemente sin refrescar esa tabla — ver hallazgo H2). 2 informes en backlog consciente (uso de integraciones por credencial, capacitación) correctamente documentados como "—" en UI, no fabricados. Gap real nuevo: cobertura de `canal` en `usuarios` bajó de la promesa original — 96/194 usuarios (49%) sin `canal`, ver hallazgo H3. |
| Estratégico (9 dashboards nuevos, nivel_estrategico.md) | 0% construido, 100% especificado | Ningún endpoint, DAG, ni componente de nivel estratégico existe en el código (confirmado con `Grep` — no hay ningún `sections/estrategico/`, ningún router `estrategico`, ningún DAG con "estrategico" en el nombre). La spec (`specs/nivel-estrategico/nivel_estrategico.md`) está completa y bien estructurada. El 92%/95% de los niveles inferiores es la base sobre la que se construye, pero el nivel estratégico en sí es trabajo 100% nuevo. |

**Cifra global honesta**: el proyecto tiene una base operativa/táctica sólida y mayormente
verificada, pero el "nivel estratégico" pedido en este encargo es una construcción completamente
nueva — no hay ningún componente reutilizable salvo los 12 `rpt_*` tácticos como fuente de la
segunda capa de agregación que la spec exige.

---

## 2. Hallazgos del nivel operativo (por CU-O)

Fuente: `specs/nivel-operativo/*.md` (7 documentos, 19 CU-O). Verificación combinada: lectura de
spec completa de Captación y Despacho (las 2 más relevantes a los gaps críticos de la Fase 3),
grep/lectura dirigida del resto, y consultas Mongo reales. Donde no se repitió el recorrido
navegador↔backend completo de una sesión anterior, se marca "según CLAUDE.md".

| CU-O | Backend | Frontend | Categoría | Nota |
|---|---|---|---|---|
| CU-O01 Registrar solicitud conductor | 2 | 2 | Parcial | Carga de documentos de postulación es backlog consciente (decisión, no gap); resto construido según CLAUDE.md |
| CU-O02 Registrar pasajero | 1 | 1 | Completo | OTP reemplazado por login usuario+contraseña (decisión arquitectónica documentada, §4); reset de contraseña es backlog consciente |
| CU-O03 Verificar documentación postulante | 1 | 1 | Completo | Según CLAUDE.md; bandeja de solicitudes con semáforo y aprobar/rechazar/observar verificado en sesiones previas |
| CU-O04 Solicitar viaje | 1 | 1 | Completo | Incluye ahora `PROGRAMADO` (feature "Programar viaje", §10) — verificado que no rompe A1-A5 |
| CU-O05 Auto-despacho | 1 (backend) | **1, no 2 como decía CLAUDE.md** | Completo | **Hallazgo H1**: `reintentarBusqueda()` en `apps/web-pasajero/src/App.tsx` implementa A3 completo (reusa origen/destino del viaje agotado, maneja `TRIP_ALREADY_ACTIVE`). CLAUDE.md §3/§6 afirma explícitamente que esto "NO está construido" — esa afirmación está desactualizada. Recomendación: corregir CLAUDE.md en la próxima sesión que lo toque. |
| CU-O06 Ofrecer viaje al conductor | 1 | 1 | Completo | Según CLAUDE.md |
| CU-O07 Ejecutar viaje | 1 | 1 | Completo | Chat/llamada (CU-O07 paso 2) es backlog consciente — no bloquea el resto del CU |
| CU-O08 Finalizar viaje + calificación | 1 | 1 | Completo | Bug de crash en calificaciones (objeto `CalificacionOut`) corregido según CLAUDE.md §11, no re-verificado en navegador esta sesión |
| CU-O09 Registro de pago | 1 | 1 | Parcial | Pago electrónico es backlog consciente; efectivo+discrepancias construido |
| CU-O10 Comisión | 2 | 4 | Parcial | **A2 (`AJUSTE`) confirmado con 0 documentos reales** (`db.movimientos.countDocuments({tipo:"AJUSTE"})` = 0, verificado esta sesión) — tests existen pero el flujo real end-to-end (endpoint/UI para generar un ajuste desde la operación) no está cableado. Comisión base sí funcional. |
| CU-O11 Liquidaciones semanales | 1 | 1 | Parcial | Corrección post-PAGADA es backlog consciente (diferido, no gap) |
| CU-O12/13 Mantenimiento (crear/cerrar orden) | 1 | 1 | Completo | Según CLAUDE.md |
| CU-O14 Historial de viajes | 1 | 1 | Completo | Existe además el historial global (§10) para roles de coordinación — construido sobre el mismo servicio |
| CU-O15/16 Pipeline + catálogo de indicadores | 1 | 1 | Completo | Verificado esta sesión: los 7 DAGs de dominio + `dag_publicar_indicadores` corriendo con datos frescos (ver Sección 3) |
| CU-O17 Bitácora de auditoría | 1 | 1 | Completo | Ampliado con filtros multi-acción (Módulo 6.1 Admin) — verificado por lectura de schema `EventoAuditoriaOut` |
| CU-O18 Alertas de seguridad (ACCESO_DENEGADO) | 1 | 1 | Completo | Según CLAUDE.md; ampliado con spoofing GPS real (Módulo 6.3) |
| CU-O17 A2 Anonimización LOPDP | 1 | 1 | Completo | Construida en Módulo 8.2 de Administración (`admin_sistema`), **confirmada conectada**: `usuarios/service.py::anonimizar_usuario` referenciado también desde `direcciones/service.py` para la purga de favoritas (§10) — coherente entre dominios, no una isla desconectada |

### Hallazgo crítico confirmado — `zona_origen_id`/`zona_destino_id`

Verificado con consulta real: `db.viajes.countDocuments({})` = **1,334,888**;
`db.viajes.countDocuments({zona_origen_id:{$ne:null}})` = **0**;
`db.viajes.countDocuments({zona_destino_id:{$ne:null}})` = **0**. Muestra aleatoria de 20
documentos confirma el mismo patrón (`null` en el 100% de la muestra). El campo existe en el
schema pero nunca se resuelve — confirma exactamente lo que CLAUDE.md documenta, y es el bloqueo
central del Panel de Rentabilidad y Demanda (OE4, ver Sección 7).

---

## 3. Hallazgos del nivel táctico (por dashboard/informe)

Fuente: `specs/nivel-tactico/*.md` (7 documentos) + los 9 `Panel*.tsx` reales +
`urbanflet_gold.rpt_*` consultadas en vivo.

### 3.1 Tablas `rpt_*` — existencia, volumen y frescura (verificado con `clickhouse-client`)

| Tabla | Filas | `max(actualizado_en)` | Categoría |
|---|---:|---|---|
| `rpt_conversion_captacion` | 285 | 2026-08-08 01:00 | 1 |
| `rpt_altas_retencion_canal` | 416 | 2026-08-08 01:00 | 1 |
| `rpt_conversion_onboarding` | 501 | 2026-08-08 01:00 | 1 (extra, no listada en nivel_estrategico.md §3 pero existe) |
| `rpt_tiempo_asignacion` | 453 | 2026-08-08 01:00 | 1 |
| `rpt_tasa_cancelacion` | 1,068 | 2026-08-08 01:00 | 1 |
| `rpt_flota_activa_franja` | 628 | 2026-08-08 01:00 | 1 |
| `rpt_cumplimiento_plan_preventivo` | 161 | 2026-08-08 01:00 | 1 |
| `rpt_costo_mantenimiento_vehiculo` | 219 | 2026-08-08 01:00 | 1 |
| `rpt_documentacion_vigente` | **0** | **1970-01-01 (nunca)** | **8 — discrepancia** |
| `rpt_tasa_discrepancias` | 791 | 2026-08-08 01:00 | 1 |
| `rpt_margen_comision` | 169 | 2026-08-08 01:00 | 1 |
| `rpt_cuarentena_dominio` | 1,057 | 2026-08-08 01:00 | 1 |
| `rpt_uso_integraciones` | 3,095 | 2026-08-08 01:00 | 1 |

**Hallazgo H2 (nuevo, no documentado en CLAUDE.md)**: `rpt_documentacion_vigente` tiene **0 filas**,
pese a que `documentos` en Mongo ya tiene 142 documentos reales (sembrados en la ronda de datos
ricos del Módulo Admin, CLAUDE.md §8.8) y pese a que las demás 12 tablas sí se refrescaron hace
minutos vía la cascada de `dag_publicar_indicadores`. Esto significa que **`dag_cumplimiento_gold`
no ha vuelto a correr desde que `documentos` dejó de estar vacío**, o que `refrescar_documentacion_vigente`
tiene un problema real. `PanelDocumentacion.tsx` (dashboard táctico #3) seguirá mostrando el estado
vacío documentado como "correcto" en CLAUDE.md §7.5 punto 3, pero ese estado vacío ya no refleja la
realidad de Mongo — es una tabla estratégica de nivel_estrategico.md §3.6.a (Cumplimiento Normativo)
que quedaría con 0 datos también en el nivel estratégico si se construye hoy sin antes disparar
`dag_cumplimiento_gold`.

### 3.2 Los 9 dashboards tácticos — clasificación

Todos los 9 `Panel*.tsx` existen en `apps/web-interno/src/sections/tactico/`, confirmado en el
`SECCIONES` array de `App.tsx` bajo `grupo: "Panel Táctico"`, gateados por rol individual —
consistente con CLAUDE.md §5/§5.1/§5.2. No se repitió la verificación visual completa de cada uno
esta sesión (sería redundante con el trabajo ya documentado); se confía en el rediseño y la
re-verificación de §5.1/§5.2 de CLAUDE.md, cruzados con el hecho de que `npm run build/lint/test`
está limpio (23/23 en `web-interno`, no re-corrido esta sesión pero consistente con el conteo de
tests citado). Categoría 1 para los 9, con la salvedad de H2 arriba (dato vacío en Documentación,
no un bug de la pantalla).

### 3.3 Informes en backlog consciente — verificados como tal, no fabricados

- **Uso de integraciones por credencial/latencia/error**: `rpt_uso_integraciones` sí existe y tiene
  3,095 filas (uso por endpoint), pero la dimensión credencial/latencia/error confirmada ausente —
  `PanelAuditoria.tsx` muestra "—" para "% error API" según CLAUDE.md, coherente con la decisión.
- **Avance de capacitación**: no existe ningún dominio de capacitación en el sistema — confirmado
  por ausencia total de colecciones/tablas relacionadas.

### 3.4 Canal de captación — hallazgo H3 (regresión sobre lo documentado)

CLAUDE.md §7 punto 5 documenta un backfill real de "4 solicitudes + 23 usuarios" como cerrado y
verificado. Verificado con consulta real hoy: `solicitudes` (169 documentos) tiene **0 sin
`canal`** — el backfill se sostiene ahí. Pero `usuarios` (194 documentos) tiene **96 sin `canal`
(49%)** — significativamente peor que el estado "cerrado" que describe CLAUDE.md. Causa más
probable: las rondas posteriores de siembra de datos ricos (§8.8 — `seed_solicitudes_demo.py` con
70 vehículos/conductores nuevos, `seed_liquidaciones_demo.py`, cuentas de demo de roles nuevos,
etc.) crearon usuarios sin pasar por el flujo que setea `canal`, o insertaron directo sin ese
campo. `rpt_altas_retencion_canal` (416 filas, fresca) probablemente subestima o distorsiona la
distribución real por canal para casi la mitad de los usuarios reales — riesgo directo para el
Panel de Crecimiento Estratégico (OE1), que usa esta misma tabla en tendencia extendida.

### 3.5 DAGs de dominio + `dag_publicar_indicadores` — cascada confirmada en vivo

Verificado con `airflow dags list` (los 9 DAGs existen, todos `is_paused=False`) y
`airflow dags list-runs -d dag_publicar_indicadores`: corridas `success` cada ~1 hora
(`2026-08-08T00:00`, `01:00`, `02:00`...), consistente con la cadencia horaria de `dag_flota_gold`
disparando la cascada — no es un bug, es el comportamiento documentado en CLAUDE.md §3.
`dag_disparar_viajes_programados` (feature de §10, cadencia de 2 min) también existe y está activo.

---

## 4. Hallazgos del nivel estratégico (nueva construcción)

Ninguno de los 9 dashboards de `specs/nivel-estrategico/nivel_estrategico.md` existe en código —
confirmado por ausencia de cualquier `sections/estrategico/`, router `estrategico`, o DAG
estratégico. Categoría **7 (especificado pero inexistente)** para los 9. Tabla de qué reutiliza cada
uno y qué falta:

| Dashboard | Fuente táctica reutilizable | Estado de la fuente | Falta construir |
|---|---|---|---|
| Panel de Crecimiento Estratégico (OE1) | `rpt_conversion_captacion` + `rpt_altas_retencion_canal` | Frescas, pero H3 (49% usuarios sin canal) degrada la fiabilidad de la vista por canal | Segunda capa de agregación (tendencia de varios meses, no solo el mes actual) — ningún `rpt_*` táctico actual agrega por mes/tendencia larga, todos son snapshot del corte más reciente salvo el uso ya existente de `fetch_snapshot_history` (ver nota abajo) |
| Confiabilidad y Disponibilidad (OE2a) | `rpt_tiempo_asignacion` + `rpt_tasa_cancelacion` + `rpt_flota_activa_franja` | Frescas | Igual — agregación de tendencia extendida sobre 3 fuentes en vez de 1 |
| Estado y Costo de Flota (OE2b) | `rpt_cumplimiento_plan_preventivo` + `rpt_costo_mantenimiento_vehiculo` | Frescas | Tabla de "vehículos candidatos a reemplazo (costo vs km)" — km recorridos no está en ninguna de las 2 fuentes actuales, requiere cruce con `flota`/`fact_ubicacion_flota` o un nuevo campo agregado |
| Capacidades y Plataforma (OE3) | `rpt_cuarentena_dominio` | Fresca | Capacitación: backlog consciente, mostrar "—" (mismo patrón ya usado en táctico) |
| Rentabilidad y Demanda (OE4, patrón F) | Ninguna — "nuevo" según la propia spec | N/A | **Bloqueado parcialmente por el gap de zona** (Sección 7). Requiere fórmula de margen nueva (recaudación − comisión − costo mantenimiento prorrateado) — no existe ningún `rpt_*` que combine las 3 fuentes (`fact_recaudacion`/`fact_liquidacion` + `fact_orden_mantenimiento`) hoy. Alcance recortado ya previsto por la spec: solo por franja, sin zona, mientras el gap no se resuelva |
| Integridad Financiera (OE5) | `rpt_tasa_discrepancias` + `rpt_margen_comision` | Frescas | Tendencia extendida + comparación interanual (el histórico real solo cubre 2021 NYC + 2026 demo — "interanual" real es cuestionable con este dataset, ver riesgo en Sección 12) |
| Cumplimiento Normativo (OE6a) | `rpt_documentacion_vigente` | **Vacía (H2)** — bloqueante real hasta que se dispare `dag_cumplimiento_gold` | Tendencia mensual — mismo patrón `fetch_snapshot_history` ya usado en táctico (MergeTree, no Replacing, conserva histórico) |
| Gobernanza de Datos y Seguridad (OE6b, patrón F) | Bitácora de auditoría administrativa (Módulo 6.1) vía `GET /auditoria/eventos` | Existe, funcional (backend confirmado, `EventoAuditoriaOut` con filtros multi-acción) | Es el único de los 9 que **no depende de ningún `rpt_*` nuevo** — reutiliza directo el endpoint ya construido, solo necesita agregación de tendencia en el nuevo backend estratégico o incluso en el frontend si se trata como snapshot filtrado (la spec permite esto porque es "tabla dominante", no gráfico agregado) |
| Tablero Ejecutivo Consolidado (CU-E01) | Los 8 anteriores (1 KPI headline por cada uno) | Depende de que los 8 existan primero | Además requiere el mecanismo de navegación cruzada — ver Sección 6, hallazgo H4 |

**Nota sobre "tendencia extendida"**: el patrón ya usado en el nivel táctico
(`fetch_snapshot_history` sobre tablas `MergeTree`, no `ReplacingMergeTree`, documentado en
CLAUDE.md §7.5 punto 3 para Documentación) es directamente reutilizable para 6 de los 9 dashboards
sin DAG nuevo — siempre que las tablas `rpt_*` en cuestión ya sean `MergeTree` con histórico
conservado. No se verificó el motor de tabla (`ENGINE=...`) de cada `rpt_*` en esta sesión —
**pendiente de confirmar antes de asumir que la tendencia extendida es gratis** para los 6.

---

## 5. Funcionalidades faltantes o incompletas (lista priorizada)

1. **Los 9 dashboards estratégicos completos** (backend + frontend) — 0% construido.
2. **Resolución de `zona_origen_id`/`zona_destino_id`** — bloquea la dimensión de zona en 3
   dashboards estratégicos (Confiabilidad, Rentabilidad, y transitivamente el headline del
   Ejecutivo) y ya bloqueaba el Panel de Flota táctico.
3. **`rpt_documentacion_vigente` desactualizada (H2)** — requiere disparar `dag_cumplimiento_gold`
   antes de construir el dashboard de Cumplimiento Normativo estratégico, o heredará el mismo vacío.
4. **Cobertura de `canal` en `usuarios` regresionada (H3)** — 49% sin canal, degrada el Panel de
   Crecimiento Estratégico.
5. **Mecanismo de navegación cruzada** entre tablero ejecutivo → dashboards estratégicos →
   dashboards tácticos — no existe hoy (ver H4, Sección 6).
6. **Fórmula de margen por franja/zona (OE4)** — no existe ningún cálculo real de "costo de
   mantenimiento prorrateado" hoy.
7. **`movimientos.tipo="AJUSTE"` real (CU-O10 A2)** — sigue en 0 documentos, gap operativo heredado.
8. **Decisión pendiente: rol `junta_socios`** — no existe en `rbac.py` (Sección 6).
9. **Parquet versionado (Sección 5 de la spec estratégica)** — no implementado en ningún DAG
   existente, confirmado por grep sin resultados en `analytics/`.
10. **CU-O05 A3 mal documentado en CLAUDE.md** — no es un gap real (H1), pero corregirlo evita que
    una sesión futura reconstruya algo que ya existe.

---

## 6. Cabos sueltos e inconsistencias

- **H1 — CU-O05 A3 sí implementado**: `CLAUDE.md` (§3, §6) afirma explícitamente "CU-O05 A3
  'Reintentar búsqueda' tras SIN_CONDUCTOR NO está construido". Código real
  (`apps/web-pasajero/src/App.tsx:1100-1134`, función `reintentarBusqueda`, invocada en el botón de
  la línea 761 para el estado `SIN_CONDUCTOR`) demuestra que sí está construido y con manejo de
  `TRIP_ALREADY_ACTIVE`. Discrepancia entre documentación y código real — la documentación está
  desactualizada, no el código.
- **H2 — `rpt_documentacion_vigente` vacía pese a datos fuente reales**: ver Sección 3.1. Requiere
  disparar `dag_cumplimiento_gold` (comando de solo lectura no puede corregir esto; se deja como
  hallazgo, no se ejecutó ninguna corrida durante esta auditoría de solo lectura).
- **H3 — Cobertura de `canal` regresionada**: ver Sección 3.4. El backfill de CLAUDE.md §7 punto 5
  quedó incompleto frente al estado actual de `usuarios`.
- **H4 — Sin mecanismo de navegación cruzada entre secciones**: verificado en
  `apps/web-interno/src/App.tsx` — la interfaz `Seccion` define `render: () => JSX.Element`, **sin
  ningún prop de navegación** (no `onNavigate`, no parámetros de sección destino). El cambio de
  sección activa (`setSeccionActiva`) vive únicamente en el sidebar (`AppShell`, vía
  `onNavigate={setSeccionActiva}` en la línea 362). Esto significa que un botón "Ver detalle" dentro
  de un `Panel*.tsx` (requisito explícito de CU-E01, Sección 4 de la spec estratégica) **no tiene
  hoy ninguna forma de invocar `setSeccionActiva` desde dentro de un componente de sección** — se
  necesita un mecanismo nuevo (contexto de navegación, o pasar `onNavigate` como prop a cada
  `render()`). Esto es un requisito implícito no escrito literalmente en la spec pero necesario para
  cumplir "cada tarjeta con un enlace 'Ver detalle' que navega al dashboard correspondiente" (§4) y
  "el tablero estratégico debe incluir enlaces de navegación hacia los 9 dashboards tácticos" (§2).
- **Discrepancia doc-organizacional vs. spec estratégica**: `UrbanFleet-Documentacion-Organizacional.md`
  (fuente de referencia según la propia spec, §0) no define informes compuestos concretos — la
  propia spec estratégica ya documenta esto como una brecha que llena por su cuenta, no es un
  hallazgo nuevo de esta auditoría, pero se confirma que sigue siendo así: no se encontró ningún
  informe adicional en el documento organizacional que la spec estratégica haya pasado por alto.
- **`rpt_conversion_onboarding`** existe en ClickHouse (501 filas, fresca) pero no aparece
  mencionada ni en `specs/nivel-tactico/tactico_captacion.md` como nombre de tabla en la Sección 3
  de `nivel_estrategico.md` (que solo cita `rpt_conversion_captacion` + `rpt_altas_retencion`, con
  un nombre ligeramente distinto — la tabla real se llama `rpt_altas_retencion_canal`, no
  `rpt_altas_retencion`). Diferencia menor de nombre, no de sustancia, pero quien construya el
  DAG/endpoints estratégicos debe usar el nombre real de tabla, no el nombre citado literal en la
  spec.
- **Datetime naive/aware — sin una 5ta instancia obviamente nueva, pero sin descarte completo**: 16
  archivos de servicio usan `datetime.now(UTC)` sin importar `como_utc` en el mismo archivo. No
  todos son riesgo real (muchos solo generan timestamps nuevos, no comparan contra un valor leído de
  Mongo/ClickHouse) — este listado es un punto de partida para revisión dirigida, no una lista de
  bugs confirmados. Antes de construir agregaciones de "tendencia extendida" de varios meses para el
  nivel estratégico (que sí comparan rangos de fechas largos), vale la pena revisar
  puntualmente `configuracion/service.py`, `flota/service.py` y `sistema/service.py` — son los 3 con
  mayor probabilidad de comparar contra datetimes leídos de Mongo por el tipo de dato que manejan.
- **Patrón de "mirror" manual**: confirmado que el caso ya corregido (Auditoría Administrativa,
  `GET /auditoria/acciones-administrativas`) no tiene equivalente sin resolver en lo ya construido
  de nivel táctico — no se encontró un array hardcodeado en TSX que debería venir de un endpoint
  entre los 9 `Panel*.tsx` (serían candidatos naturales `estados`/`tipos` usados en filtros, pero
  esos son enumeraciones de la máquina de estados del dominio, no catálogos administrables, así que
  hardcodearlos es correcto, no un mirror-gap). `usuarios/permisos_matriz.py` y `ROLES_STAFF` siguen
  siendo mirrors manuales por decisión explícita ya aprobada (CLAUDE.md §9) — no reabrir sin pedido.

---

## 7. Dependencias entre niveles

- **Panel de Rentabilidad y Demanda (OE4) depende directamente del gap de zona operativo.**
  Verificado: 0/1,334,888 viajes con zona resuelta. La spec ya prevé el alcance recortado ("solo por
  franja, sin dimensión de zona, documentado como limitación explícita en la UI") — esto es viable
  de construir HOY sin resolver el gap, pero el impacto exacto es: el dashboard pierde la mitad de
  su propuesta de valor (matriz zona×franja se reduce a una sola dimensión, franja), y la decisión
  "dónde reforzar flota por rentabilidad" (uno de los 2 objetivos de decisión del dashboard) queda
  sin soporte de datos reales — solo "cuándo", no "dónde". Resolver el gap de zona requeriría, como
  mínimo: (a) que `viajes.solicitar_viaje` resuelva `zona_origen_id`/`zona_destino_id` contra las
  zonas de despacho ya administrables (Módulo 3 de Administración, `catalogos`/`parametros`), lo cual
  es un cambio de código operativo, no solo de agregación — fuera del alcance de "nivel estratégico"
  puro, y con el riesgo de que 1.3M viajes históricos NYC sembrados nunca tendrán zona real
  (coordenadas sintéticas ancladas a Quevedo, CLAUDE.md §7) salvo que se les aplique un backfill de
  resolución de zona por coordenada — otro trabajo de datos, no solo de agregación.
- **Panel de Cumplimiento Normativo (OE6a) depende de que `dag_cumplimiento_gold` se dispare de
  nuevo** — hoy heredaría 0 filas (H2) pese a que la fuente real (`documentos`, 142 filas) ya no
  está vacía. Esto es una dependencia operable en minutos (una corrida de Airflow), no un gap de
  diseño, pero bloquea el dashboard si se construye antes de resolverlo.
- **Panel de Crecimiento Estratégico (OE1) depende de la cobertura de `canal`** — con 49% de
  usuarios sin canal (H3), cualquier desglose "por canal" en tendencia extendida va a subrepresentar
  sistemáticamente los canales reales. No bloquea la construcción, pero sí la fiabilidad del
  resultado — recomendable resolver el backfill de canal antes o documentar la limitación en la UI,
  igual que se hizo con zona.
- **Tablero Ejecutivo Consolidado (CU-E01) depende de que los 8 dashboards de detalle existan
  primero** (cada tarjeta headline necesita su fuente) y del mecanismo de navegación cruzada (H4,
  Sección 6) que hoy no existe en ningún nivel del frontend — no es exclusivo de lo estratégico, pero
  nunca se necesitó hasta ahora porque ninguna sección enlazaba a otra sección.
- **Panel de Gobernanza de Datos y Seguridad (OE6b) es el único de los 9 sin dependencia de un
  `rpt_*` nuevo o de un gap operativo** — puede construirse primero como piloto de bajo riesgo si se
  quiere validar el patrón F estratégico antes de comprometerse con los demás.

---

## 8. Matriz de trazabilidad especificación↔implementación

| Requisito (spec) | Fuente | Estado real | Categoría |
|---|---|---|---|
| CU-E01 Tablero de indicadores | nivel_estrategico.md §4 | No existe | 7 |
| CU-E01 enlaces "Ver detalle" hacia táctico | nivel_estrategico.md §2, §4 | No existe ningún mecanismo de navegación cruzada (H4) | 7 |
| CU-E02 Rentabilidad por zona/franja | nivel_estrategico.md §3.4 | No existe; zona bloqueada (0/1.3M resuelto) | 7, dependiente de gap operativo |
| CU-E03 Política tarifaria | nivel_estrategico.md §3.4 (comparte panel con CU-E02) | No existe | 7 |
| CU-E04 Auditar integridad de recaudación | nivel_estrategico.md §3.5 | No existe; fuentes (`rpt_tasa_discrepancias`, `rpt_margen_comision`) sí frescas | 7, fuente lista |
| CU-E05 Gobernanza de datos y accesos | nivel_estrategico.md §3.6.b | No existe; fuente (bitácora admin) sí funcional | 7, fuente lista |
| Regla: solo agregación sobre `rpt_*`, nunca Mongo directo | nivel_estrategico.md §2 | No aplica aún — nada construido; ningún antipatrón detectado porque no hay código que auditar | N/A |
| Rol `junta_socios` | nivel_estrategico.md §6 | No existe en `backend/src/core/rbac.py::ROLES` (13 roles confirmados, `junta_socios` ausente) | **Requiere decisión** |
| Parquet versionado por corrida | nivel_estrategico.md §5 | No implementado en ningún DAG (`grep -rin parquet analytics/` → 0 resultados) | 7 |
| 8 dashboards + 1 tablero ejecutivo (9 total) | nivel_estrategico.md §3-4 | 0/9 construidos | 7 |
| `rpt_documentacion_vigente` como fuente de Cumplimiento Normativo | nivel_estrategico.md §3.6.a | Tabla existe, 0 filas (H2) | 8 — discrepancia entre "fuente lista" asumido y estado real |
| `rpt_altas_retencion` (nombre citado en spec) | nivel_estrategico.md §3.1 | El nombre real de tabla es `rpt_altas_retencion_canal` | 8 — discrepancia de nombre |
| CU-O05 A3 (prerrequisito operativo, referenciado indirectamente por OE2) | operativo_operaciones_despacho.md | Implementado (H1) | 1 — mejor que lo documentado en CLAUDE.md |
| `zona_origen_id`/`zona_destino_id` (prerrequisito OE4) | diseno_base_datos.md / operativo_operaciones_despacho.md | Campo existe, nunca poblado (0/1,334,888) | 8 |

---

## 9. Requisitos necesarios para el nivel estratégico (checklist consolidado)

- [ ] Decisión de negocio: ¿existe `junta_socios` como rol nuevo o todos los dashboards que lo usan
      quedan bajo `gerencia` único? **Requiere decisión del usuario** (spec lo deja explícito, §6).
- [ ] Decisión de negocio: ¿se implementa Parquet versionado (Sección 5 de la spec) en esta ronda, o
      se recorta como se hizo con otros requisitos de infraestructura pesada? **Requiere decisión**
      — ver evaluación de invasividad en Sección 12 (riesgos).
- [ ] Confirmar motor de tabla (`ENGINE=`) de los 12 `rpt_*` para saber si la "tendencia extendida"
      es gratis vía `fetch_snapshot_history` o si hace falta ampliar alguna tabla a histórico.
- [ ] Disparar `dag_cumplimiento_gold` para poblar `rpt_documentacion_vigente` antes de construir el
      dashboard de Cumplimiento Normativo estratégico (H2).
- [ ] Backfill de `canal` en los 96 usuarios sin el campo, o documentar la limitación en el Panel de
      Crecimiento Estratégico igual que se hizo con zona (H3).
- [ ] Diseñar el mecanismo de navegación cruzada entre secciones de `web-interno` (H4) — prerrequisito
      técnico para CU-E01 y para "Ver detalle táctico" desde el tablero ejecutivo.
- [ ] Diseñar la fórmula real de margen (OE4): recaudación − comisión − costo de mantenimiento
      prorrateado, con la fuente de prorrateo aún sin definir (¿por vehículo activo en el periodo?
      ¿por viaje?).
- [ ] Nuevo grupo de navegación "Panel Estratégico" en el sidebar de `web-interno`, análogo a "Panel
      Táctico" (requisito implícito, mismo patrón ya usado, no requiere decisión de diseño nueva).
- [ ] Nuevo DAG estratégico (o extensión de `dag_publicar_indicadores`) que agregue los `rpt_*`
      tácticos en tendencia extendida hacia nuevas tablas `rpt_estrategico_*` (o vistas materializadas
      — a decidir en la fase de arquitectura).
- [ ] Endpoints backend nuevos por dominio (`GET /<dominio>/panel-estrategico/...`, mismo patrón ya
      usado en táctico) o un módulo centralizado nuevo — a decidir, la spec no fuerza ninguno de los
      dos (a diferencia de táctico, que sí decidió explícitamente "no un módulo central").
- [ ] Corregir CLAUDE.md §3/§6 respecto a CU-O05 A3 (ya construido, H1) para que la próxima sesión no
      reconstruya algo existente.
- [ ] Corregir CLAUDE.md respecto al estado del backfill de `canal` (H3) — la afirmación de "cerrado"
      ya no refleja el estado real de `usuarios`.

---

## 10. Plan de implementación ordenado por dependencias reales

**Fase 0 — Higiene de datos previa (bloqueante para 2 de los 9 dashboards, no bloqueante para el
resto)**
Depende de: nada, es la base.
- Disparar `dag_cumplimiento_gold` (resuelve H2, prerrequisito de OE6a).
- Backfill de `canal` en los 96 usuarios faltantes (resuelve H3, mejora la fiabilidad de OE1) —
  alternativamente, documentar la limitación en vez de bloquear, si el backfill no es prioritario.
- Confirmar `ENGINE=` de los 12 `rpt_*` (determina si Fase 2 necesita ampliar tablas o no).

**Fase 1 — Decisiones de negocio (bloqueante para el diseño final de 4 dashboards)**
Depende de: nada, son decisiones humanas, pueden correr en paralelo a la Fase 0.
- Confirmar `junta_socios` vs. `gerencia` único (afecta OE2b, OE4, OE5, tablero ejecutivo).
- Confirmar alcance de Parquet versionado (afecta el diseño de los 7 DAGs existentes + el nuevo).

**Fase 2 — Infraestructura ETL estratégica**
Depende de: Fase 0 (tablas fuente correctas) y, si se aprueba, la decisión de Parquet de Fase 1.
- Nuevo DAG (o tareas nuevas en `dag_publicar_indicadores`) que agregue los `rpt_*` tácticos en
  tendencia extendida (varios meses) hacia nuevas tablas de nivel estratégico.
- Si Parquet se aprueba: agregar el paso de escritura Parquet a los 7 DAGs existentes + el nuevo,
  probando primero sobre el DAG de menor riesgo (`dag_mantenimiento_gold`, el más reciente y con
  menor historial de producción) antes de tocar los 6 restantes.

**Fase 3 — Backend de los 9 dashboards**
Depende de: Fase 2 (las tablas fuente deben existir).
- Empezar por **Gobernanza de Datos y Seguridad (OE6b)** — es el único sin dependencia de tabla
  nueva (reutiliza `GET /auditoria/eventos` directo), sirve de piloto de bajo riesgo para validar el
  patrón F estratégico antes de comprometerse con los otros 8.
- Seguir con los que tienen fuente 100% fresca y sin gap: Confiabilidad y Disponibilidad (OE2a),
  Estado y Costo de Flota (OE2b, salvo el cruce de km pendiente), Capacidades y Plataforma (OE3),
  Integridad Financiera (OE5).
- Cumplimiento Normativo (OE6a) solo después de confirmar que Fase 0 resolvió H2.
- Crecimiento Estratégico (OE1) solo después de confirmar que Fase 0 resolvió (o documentó) H3.
- Rentabilidad y Demanda (OE4) al final — es el más complejo (fórmula de margen nueva) y el único
  con alcance recortado ya previsto por la propia spec (sin zona).

**Fase 4 — Frontend**
Depende de: Fase 3 (endpoints deben existir) y de resolver H4 (mecanismo de navegación).
- Resolver H4 primero (contexto de navegación entre secciones) — es transversal a los 9, no tiene
  sentido construir "Ver detalle" en cada panel sin el mecanismo primero.
- Nuevo grupo "Panel Estratégico" en el sidebar, mismo patrón que "Panel Táctico".
- Construir los 8 dashboards de detalle + el tablero ejecutivo consolidado al final (depende de que
  los 8 anteriores ya tengan sus KPIs headline).

**Fase 5 — Verificación**
Depende de: Fase 4 completa.
- Verificación en navegador real por dashboard (regla de cierre del proyecto, CLAUDE.md §6) —
  especialmente rigurosa en Rentabilidad y Demanda (cálculo financiero) y Gobernanza (dato
  sensible/seguridad).
- Regresión completa: `pytest` backend + `build/lint/test` en `web-interno`.
- Actualizar CLAUDE.md con el estado real, incluyendo la corrección de H1 y H3 pendientes desde
  antes de este bloque.

---

## 11. Prioridad de cada tarea del plan

| Tarea | Prioridad | Justificación |
|---|---|---|
| Disparar `dag_cumplimiento_gold` (H2) | Alta | Bloquea un dashboard completo, y es una corrida de minutos, no un cambio de código — costo mínimo, beneficio inmediato |
| Decisión `junta_socios` | Alta | Bloquea el diseño de 4 dashboards; sin ella se construye 2 veces si se decide tarde |
| Diseño del mecanismo de navegación cruzada (H4) | Alta | Transversal a los 9 dashboards y al tablero ejecutivo; construirlo tarde obliga a retocar los 8 paneles ya hechos |
| Backfill/documentación de `canal` (H3) | Media | Degrada la fiabilidad de un solo dashboard (OE1), no lo bloquea — puede documentarse como limitación igual que zona |
| Confirmar `ENGINE=` de `rpt_*` | Media | Determina el esfuerzo real de Fase 2, pero no bloquea empezar por Gobernanza (OE6b) mientras se confirma |
| Decisión de Parquet versionado | Media | No bloquea ningún dashboard directamente — es un requisito de infraestructura paralelo, con riesgo real de tocar DAGs estables (ver Sección 12) |
| Fórmula de margen para OE4 | Media | Solo bloquea 1 de 9 dashboards, y ya tiene alcance recortado previsto por la spec (se puede construir parcial) |
| Corrección de CLAUDE.md (H1, H3) | Baja | No bloquea nada técnico, pero previene retrabajo en sesiones futuras — hacerlo en el mismo commit que cierre este bloque |
| Resolución completa del gap de zona (backfill real de coordenada→zona) | Baja (para este alcance) | La spec ya previó explícitamente construir sin zona primero; resolverlo de raíz es un proyecto aparte que toca código operativo, no solo estratégico |

---

## 12. Riesgos y consideraciones técnicas

- **Riesgo datetime naive/aware**: no se encontró una 5ta instancia confirmada del bug ya visto 4
  veces (Respaldos, umbral de intentos, Compartir Viaje, dag_finanzas/viajes start_date), pero
  tampoco se descartó a fondo — 16 archivos con `datetime.now(UTC)` sin `como_utc` en el mismo
  archivo quedan como superficie de riesgo no auditada línea por línea. El nivel estratégico, por
  definición, va a comparar rangos de fechas largos (tendencia de varios meses, comparación
  interanual) — exactamente el patrón que ya causó el bug 4 veces. Recomendación: auditar
  puntualmente cualquier código nuevo de Fase 2/3 que compare `fecha_datos`/`ts_*` leído de
  ClickHouse o Mongo contra `datetime.now()`, antes de escribirlo, no después.
- **Riesgo Parquet tocando DAGs estables en producción**: los 7 DAGs de dominio ya están verificados
  en corridas reales de producción (incluida la carga de 1.3M filas NYC). Agregar un paso de
  escritura Parquet a cada etapa (Bronce/Silver/Gold) de los 7 implica: (a) volumen de I/O adicional
  no trivial — `fact_viaje_historico` sola tiene 1.3M+ filas, escribir Parquet versionado por corrida
  de eso multiplica el I/O de cada ejecución; (b) riesgo de romper el `TriggerDagRunOperator` que
  encadena la publicación si el paso nuevo falla y el DAG no maneja bien el fallo parcial; (c) ningún
  DAG existente tiene hoy infraestructura de filesystem versionado (`datos/extraccion/...`) — hay que
  confirmar que el volumen de Airflow tiene espacio y persistencia para esto antes de escribir el
  primer archivo. Recomendación de la Sección 10: probar primero sobre `dag_mantenimiento_gold` (el
  de menor volumen e historial más corto) antes de tocar los 6 DAGs con corridas de producción reales
  ya acumuladas.
- **Riesgo de "comparación interanual" con datos poco representativos**: el histórico real disponible
  para tendencias largas mezcla 2021 (1.3M viajes NYC sembrados, sin relación con la operación real
  de la cooperativa, con solo 5 conductores/9 pasajeros de pool — CLAUDE.md §8.5) y 2026 (datos de
  demo real de la cooperativa). Cualquier dashboard estratégico que muestre "tendencia de varios
  años" o "comparación interanual" (OE5, Integridad Financiera) va a mezclar estas dos naturalezas de
  dato sin ninguna marca visual que las distinga — riesgo de inducir una lectura errónea en una
  demo/presentación si no se documenta explícitamente en la UI qué rango es dataset histórico de
  calibración vs. operación real de la cooperativa.
- **Riesgo de doble agregación inconsistente**: la regla de la Sección 2 de la spec ("nunca se
  consulta directo de MongoDB, siempre sobre `rpt_*`") es correcta y evita reprocesar, pero exige
  disciplina: cualquier tentación de "solo agregar un filtro rápido contra Mongo" en el backend
  estratégico (como ya se hizo, por decisión consciente, en algunos endpoints tácticos — p. ej.
  Flota/Cumplimiento con paginación client-side) rompería la regla explícita de este nivel. Vale la
  pena dejarlo como criterio de revisión de código explícito en la Fase 3.
- **Riesgo de alcance del rol `junta_socios`**: si se crea como rol nuevo sin cuenta de demo
  dedicada, se repite el patrón ya visto con `integracion_externa` (login funciona, sin pantalla
  propia) — hay que decidir explícitamente si se le da OR-gate con `gerencia` en todos los
  dashboards que la spec le asigna, o si de verdad necesita una cuenta y flujo separados.
