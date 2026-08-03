# CLAUDE.md — contexto de UrbanFleet TaxiFlow

Este archivo es la fuente de verdad para cualquier sesión nueva que retome
este proyecto sin historial previo. **Actualízalo al cerrar cada bloque de
trabajo**, antes de reportar el cierre — la sección 7 (pendiente) y la 3
(estado por CU) son las que más rotan.

## 1. Qué es este proyecto

UrbanFleet: sistema de gestión de flota de taxis para una **cooperativa**,
100% web (sin apps nativas). Cubre todo el ciclo: captación de socios
conductores, despacho de viajes, cobro y liquidación, mantenimiento de
vehículos, cumplimiento documental, indicadores operativos/tácticos.

Las specs son la fuente de la verdad del negocio — ante cualquier duda sobre
comportamiento esperado, léelas antes de asumir:

- `specs/nivel-operativo/` — 7 documentos, uno por dominio: `operativo_captacion.md`,
  `operativo_flota.md`, `operativo_cumplimiento.md`,
  `operativo_operaciones_despacho.md`, `operativo_finanzas.md`,
  `operativo_mantenimiento.md`, `operativo_plataforma.md`. Cada uno describe
  los CU-O (casos de uso operativos) de su dominio, con pasos, alternativas
  (A1, A2…) y datos.
- `specs/specs-generales/arquitectura_software.md` — stack, diagrama de
  arquitectura, decisiones técnicas transversales.
- `specs/specs-generales/diseno_base_datos.md` — esquema Mongo (OLTP) y
  ClickHouse (Gold), índices.
- `specs/nivel-tactico/` — 7 documentos, uno por dominio (mismo patrón que
  nivel-operativo): `tactico_captacion.md`, `tactico_operaciones_despacho.md`,
  `tactico_flota.md`, `tactico_mantenimiento.md`, `tactico_finanzas.md`,
  `tactico_cumplimiento.md`, `tactico_plataforma.md`. Cada uno define
  informes (simple/MongoDB, compuesto/ClickHouse) con query o transformación
  exacta, y el dashboard resultante (KPIs, gráfico, lista, filtros, patrón
  de layout Z/F). En construcción activa, ver §7 punto 5.
- `specs/nivel-estrategico/` — existe como directorio pero sin documentos
  propios todavía.
- `specs/auditoria_sistema/` — auditorías de conformidad spec-vs-código ya
  realizadas; útil como snapshot histórico, pero **puede estar desactualizado**
  respecto al código actual — verifica siempre contra el código real antes
  de asumir que un hallazgo de una auditoría vieja sigue vigente.
  `auditoria_cu.md` (#1) es la primera pasada, por CU sin separar
  backend/frontend. `auditoria_cu_02.md` (#2, más reciente y más estricta)
  audita **backend y frontend por separado para cada paso/flujo de cada
  CU** — un CU no cuenta como construido si solo un lado existe; esa
  auditoría encontró varios casos reales de "backend sí, frontend no" (y
  al menos un caso de "se documentó como cerrado sin estarlo del todo",
  ver §7 punto 6) — es la referencia más confiable ahora mismo para saber
  qué falta de verdad.

## 2. Stack técnico

- **Backend**: Python/FastAPI, en `backend/` (`src/<dominio>/router.py` +
  `service.py` + `schemas.py` por módulo de dominio: `auth`, `captacion`,
  `viajes`, `flota`, `recaudacion`, `mantenimiento`, `cumplimiento`,
  `plataforma`, `auditoria`, `notificaciones`, `parametros`, `core`).
- **MongoDB** — OLTP, base `urbanflet`, replica set de un nodo (`rs0`,
  necesario para transacciones multi-documento). Índices declarados en
  `backend/src/core/db_mongo.py::ensure_indexes()`.
- **ClickHouse** — capa analítica (Gold): hechos/dimensiones para KPIs de
  los 3 niveles (operativo/táctico/estratégico).
- **Airflow** — orquesta el pipeline ETL Bronze → Silver → Gold. Ya
  construido y funcional (alimenta CU-O15/CU-O16, ver §3).
- **PocketBase** — aloja el dataset NYC crudo. **Decisión de arquitectura
  (ver §7 punto 7): uso dual, deliberado, diverge de
  `diseno_base_datos.md`.** El flujo original (sin cambios) sigue siendo
  referencia/calibración: `raw_trips` → `dag_historico_nyc` →
  `fact_viaje_historico` en ClickHouse, aislado del dominio de negocio. A
  partir de esta sesión se agrega un segundo uso: el mismo dataset (2021
  Yellow Taxi, ~1.3M filas, `data/nyc_taxi/yellow_tripdata.csv`) también
  siembra viajes/pagos **reales** en MongoDB (`viajes`/`pagos`) para dar
  volumen realista a los 9 dashboards tácticos — ver
  `analytics/scripts/seed_viajes_nyc.py`. Los dos usos son independientes:
  uno no depende del otro, ambos leen el mismo CSV fuente por separado.
- **3 frontends** React + TypeScript + Vite, workspaces npm en `apps/*`:
  - `web-pasajero` (PWA) — puerto 5173.
  - `web-conductor` (PWA) — puerto 5174.
  - `web-interno` (SPA responsiva, sin PWA — portal administrativo) — puerto 5175.
  - `shared-ui` — componentes/cliente API/auth compartidos por los 3
    (`AppShell`, `DataTable`, `Pagination`, `DetailPanel`, `ActionBar`,
    `AuthProvider`, `apiFetch`, etc.), sin bundler propio (se consume como
    fuente TS directamente vía workspace). Desde el nivel táctico (§7 punto
    5) también incluye `KpiCard`/`KpiRow` (jerarquía tipográfica + tono de
    estado bien/advertencia/serio/peligro), `CategoryBarChart`/`TrendLineChart`
    (wrappers de **recharts** — dependencia real, paleta categórica fija de
    8 colores validada con el script de la skill `dataviz`, ver
    `apps/shared-ui/src/components/charts/palette.ts` y tokens
    `--chart-series-1..8`/`--status-*` en `tokens.css`), `DashboardLayout`
    (`DashboardZ`/`DashboardF`, ver §7 punto 5.1) y `FuenteBadge` (etiqueta
    "Simple · MongoDB" / "Compuesto · ClickHouse").
- Backend y servicios corren en Docker Compose (`docker-compose.yml`) —
  `mongo`, `redis`, `clickhouse`, `pocketbase`, `airflow-*`, `backend`. Los 3
  frontends corren con `npm run dev` (no dockerizados), ver
  `.claude/launch.json` para los comandos por app.

## 3. Estado actual por CU operativo

Todos los CU-O listados abajo están **construidos y verificados en ambos
lados (backend + frontend), con verificación real en navegador**, salvo
que se indique lo contrario. "Backend ✅ / Frontend ✅" no es una promesa —
significa que en algún momento se probó el flujo end-to-end con una sesión
de navegador real, no solo que el código compila.

| Dominio | CU cubiertos | Notas |
|---|---|---|
| Captación (`operativo_captacion.md`) | CU-O01 (postulación conductor, aprobar/rechazar), CU-O02 (registro pasajero/login) | Falta a propósito: carga de documentos de postulación (backlog, ver §3.1) |
| Operaciones/Despacho (`operativo_operaciones_despacho.md`) | CU-O04 (solicitar viaje, A1-A4), CU-O05 (auto-despacho, incl. A1/A2) | Todo el ciclo de vida del viaje es un overlay sobre el mapa persistente — ver §4. **CU-O05 A3 "Reintentar búsqueda" tras SIN_CONDUCTOR NO está construido** (ver §7 punto 6 — auditoría #2 lo encontró faltante, no confundir con una entrada previa de este archivo que lo daba por hecho) |
| Finalización/Pago (dentro de despacho) | CU-O08 (calificación mutua, con comentario opcional), CU-O09 (registro de pago en efectivo, discrepancias) | Pago electrónico/pasarela es backlog consciente (ver §3.1) |
| Finanzas (`operativo_finanzas.md`) | CU-O10 (comisión), CU-O11 (liquidaciones semanales, observación, viajes en revisión) | Corrección post-PAGADA vía nota de ajuste es backlog consciente. **CU-O10 A2 (movimiento `AJUSTE` individual vinculado al viaje) NO tiene datos reales todavía** — `generar_liquidaciones` sigue con `ajustes=0.0` hardcodeado; hay tests (`backend/tests/recaudacion/test_ajuste_movimiento.py`) pero 0 documentos `movimientos.tipo="AJUSTE"` reales en Mongo (ver §7 punto 6) |
| Mantenimiento (`operativo_mantenimiento.md`) | CU-O12 (crear orden, con repuestos estimados), CU-O13 (cerrar orden: repuestos consumidos, horas taller, ajuste de km justificado) | |
| Cumplimiento (`operativo_cumplimiento.md`) | CU-O17 (bitácora de auditoría, filtros), CU-O18 (alertas de seguridad vía eventos `ACCESO_DENEGADO`) | Anonimización LOPDP es backlog consciente |
| Plataforma (`operativo_plataforma.md`) | CU-O15/CU-O16 (pipeline Bronze→Silver→Gold + catálogo de informes publicados, **con publicación automática encadenada** — ver nota abajo) | Pipeline Airflow funcional, alimenta el panel de Indicadores en web-interno |

**Nota Airflow (analytics/)**: 6 DAGs de dominio — 5 diarios
(`dag_viajes_core`, `dag_finanzas_gold`, `dag_captacion_gold`,
`dag_cumplimiento_gold`, `dag_mantenimiento_gold`) + `dag_flota_gold`
(horario). Cada uno termina su cadena `extraer→silver→gold→métricas`
con un `TriggerDagRunOperator` que dispara `dag_publicar_indicadores`
(schedule_interval=None, pero ya no es "solo manual" — se dispara
automáticamente en cascada; el disparo manual sigue existiendo para A2,
regenerar desde Gold sin re-ejecutar el DAG fuente). Verificado en Airflow
real disparando `dag_captacion_gold`, `dag_mantenimiento_gold` y
`dag_flota_gold` manualmente por separado y confirmando, para cada uno, una
nueva corrida automática de `dag_publicar_indicadores` con datos frescos en
ClickHouse (`actualizado_en` de la tabla `rpt_*` correspondiente coincidiendo
con el timestamp de la cascada, no un valor viejo).

`dag_mantenimiento_gold` (nuevo, `fact_orden_mantenimiento`): extrae órdenes
`CERRADA` por `fecha_cierre` (único datetime real en `ordenes` — no hay
`ts_creacion`, y `ANULADA` no queda con ninguna fecha usable). Alimenta 2
informes tácticos: `rpt_cumplimiento_plan_preventivo` (% de órdenes
PREVENTIVA que cerraron en o antes de su `fecha_programada`, por mes) y
`rpt_costo_mantenimiento_vehiculo` (costo total por vehículo y mes). **No
hay spec de nivel táctico en el repo** que defina esta agregación
(`specs/nivel-tactico/` vacío) — es una interpretación propia, documentada
en el docstring del DAG y de las 2 funciones `refrescar_*` en
`analytics/plugins/indicadores.py`.

**Bug corregido en `dag_flota_gold`**: `extraer` asumía que `posiciones`
traía `estado_servicio` en el propio documento — nunca lo trae (ese campo
vive en `usuarios.conductor.estado_servicio`, un dato de turno del socio, no
de la posición puntual). El 100% de las filas llegaban con ese campo `None`
y reventaban el INSERT a Bronze (columna `String` NOT NULL). Corregido con
un join de lectura por `conductor_id` (mismo patrón que el join
pagos/viajes de `dag_viajes_core`) + la columna Bronze relajada a
`Nullable(String)` como respaldo defensivo para conductores sin
`usuarios.conductor` resuelto. Confirmado con corrida real: 557/558
registros válidos, `rpt_flota_activa_franja` con datos reales.

**Nota de infraestructura para la próxima sesión que toque `analytics/`**:
Airflow con `LocalExecutor` en este stack usa `fork()` para ejecutar tareas
(`_execute_work_in_fork`) — el proceso `scheduler` puede quedarse con un
`import` de `analytics/plugins/*.py` cacheado en memoria entre corridas. Si
editas `medallion.py` o `indicadores.py` y una tarea sigue fallando con un
error que ya corregiste (o con `AttributeError`/comportamiento viejo pese a
que el archivo en disco está bien), no es necesariamente tu código: borra
`analytics/plugins/__pycache__` y, si persiste,
`docker restart urbanflet-taxiflow-airflow-scheduler-1
urbanflet-taxiflow-airflow-webserver-1` — eso fuerza un reimport limpio.
También: **un DAG nuevo queda `is_paused=True` por defecto**
(`dags_are_paused_at_creation` en `airflow.cfg`) — `airflow dags unpause
<dag_id>` o no vas a ver ninguna corrida, ni siquiera las programadas.

**Otra gotcha de infraestructura (Airflow webserver, no específica de
`analytics/`)**: si vuelves a levantar el stack con `docker compose up -d`
y el contenedor `airflow-webserver` ya existía (se reinicia en vez de
recrearse), puede quedar con un `airflow-webserver.pid` viejo en su
filesystem efímero — gunicorn se niega a arrancar (`Error: Already running
on PID N (or pid file ... is stale)`) aunque `docker compose ps` lo marque
como "Up" y aunque el contenedor responda a otras cosas. Si `/health` no
responde tras un `up -d` normal, usa `docker compose up -d --force-recreate
airflow-webserver` — fuerza un filesystem limpio y resuelve el PID viejo.

### 3.1 Backlog consciente — decisión ya tomada, no reabrir sin pedido explícito

Estos ítems están **fuera de alcance por decisión consciente**, no por
olvido. No los implementes salvo que el usuario lo pida explícitamente:

- Carga de documentos de postulación (CU-O01).
- Pago electrónico / pasarela (CU-O09).
- Chat / llamada pasajero-conductor (CU-O07).
- Comprobante de viaje en PDF (CU-O14).
- Reset de contraseña (CU-O02).
- Corrección de liquidación post-PAGADA vía nota de ajuste (CU-O11 A4).
- Anonimización de datos LOPDP (CU-O17 A2).
- OTP por SMS — el diseño ya migró a login con usuario+contraseña, ver §4.

## 4. Decisiones de arquitectura ya tomadas — no revisitar sin razón nueva

- **Login con contraseña, no OTP/Firebase.** El diseño original consideró
  OTP por SMS; se abandonó y migró a login con teléfono-o-correo +
  contraseña para los 3 roles (pasajero, conductor, staff interno). No
  reintroducir OTP/Firebase sin que el usuario lo pida explícitamente.
  El login tiene bloqueo por intentos fallidos vía Redis (`auth:login_locked:
  {identificador}` / `auth:login_failures:{identificador}`, 5 fallos en 15
  min → bloqueo 15 min, mismo patrón que el de refresh-token y el de
  suspensión RBAC por denegaciones) — un 401 seguido de 429 en pruebas
  repetidas es este mecanismo funcionando, no un bug; limpiar esas claves en
  Redis si un bloqueo de pruebas estorba.
- **Mapa: Leaflet + tiles OpenStreetMap, nunca el SDK de Google Maps.**
  `arquitectura_software.md` lo exige explícitamente. Google solo se usa
  para Geocoding y Directions, **siempre vía el backend** (`GET
  /viajes/estimacion-ruta`, geocoding directo desde cliente porque sí
  soporta CORS) — Directions API de Google no envía cabeceras CORS, así que
  llamarla directo desde el navegador falla silenciosamente y cae a un
  fallback de línea recta sin avisar. Ver `apps/web-pasajero/src/rutas.ts`
  para el razonamiento completo.
- **Patrón WorkPanel para toda pantalla CRUD de web-interno**: Card de
  búsqueda (filtros) → `ActionBar` fija (Nuevo/Actualizar/Eliminar/Buscar/
  Salir, con `disabled` + tooltip explicativo cuando una acción "no
  aplica" en ese dominio) → `DataTable` + `Pagination` → `DetailPanel` con
  indicador de modo (`consulta`/`edicion`/`nuevo`) al hacer clic en una
  fila. Ya aplicado en `Solicitudes.tsx`, `Mantenimiento.tsx`,
  `Finanzas.tsx`. Referencia de test de este patrón:
  `apps/web-interno/src/App.test.tsx` (sobre Solicitudes).
- **El ciclo de vida completo del viaje vive como overlay sobre un mismo
  mapa persistente, nunca cambia de pantalla.** En `web-pasajero` y
  `web-conductor`, desde "elegir destino" hasta calificar al final, el
  componente de mapa (`RideMap`/`DriverMap`) se monta una sola vez; solo
  cambia el panel flotante que se le superpone (`PanelSolicitar` ↔
  `PanelViajeActivo`, y equivalente en conductor). No dividir esto en
  pantallas separadas — es una decisión de UX explícita, no un accidente.

## 5. Infraestructura de calidad

ESLint + Vitest + React Testing Library configurados en las 3 apps de
frontend (no en `shared-ui`, que solo tiene lint). Antes de dar cualquier
cambio de frontend por cerrado, correr en este orden y confirmar que los 3
quedan limpios:

```bash
npm run build -w @urbanflet/<app>
npm run lint -w @urbanflet/<app>
npm run test -w @urbanflet/<app>
```

- Config de ESLint compartida en `eslint.config.js` (raíz) — no se duplica
  por app.
- Los tests existentes son **red de seguridad sobre flujos críticos ya
  verificados en navegador**, no cobertura completa — no te bloquees
  intentando cubrir todo antes de seguir. Cuando agregues una pantalla
  nueva con el patrón WorkPanel, sumale al menos un test siguiendo el
  ejemplo de `apps/web-interno/src/App.test.tsx` (sobre Solicitudes):
  búsqueda + paginación + apertura de detalle, más el flujo de decisión
  específico de esa pantalla.
- Backend: `cd backend && ./.venv/Scripts/python.exe -m pytest` (o
  equivalente en el venv del sistema que estés usando) — sin infraestructura
  de lint propia documentada aquí todavía.

## 6. Regla de cierre — seguida en todo el proyecto hasta ahora

**Nada se marca completo solo porque los tests automáticos pasan, si el
cambio toca UI.** Se exige verificación real en navegador (Chrome vía
`preview_start` + `read_page`/`computer`/`get_page_text`/
`read_network_requests`), con el nivel de esfuerzo ajustado a la
complejidad y el riesgo del cambio:

- **Cosmético / exposición de dato ya soportado por el backend**
  (ej. agregar un campo a una vista, un filtro adicional): verificación
  visual rápida — cargar la pantalla, confirmar que se ve y no rompe nada
  alrededor.
- **Lógica de negocio / bug de flujo** (ej. una transición de estado, un
  cálculo financiero, un gate de validación): verificación exhaustiva —
  reproducir el camino real con datos reales o sembrados a propósito,
  inspeccionar requests/responses de red, confirmar en Mongo cuando aplique,
  no conformarse con "la pantalla cargó sin error".

Cuando no se puede verificar en navegador (cambio de infraestructura pura,
script que solo toca la base de datos), decirlo explícitamente en el
reporte de cierre en vez de simular una verificación que no ocurrió.

## 7. Qué sigue pendiente ahora mismo

1. ~~Work panels de Flota y Cumplimiento~~ — **cerrado.** Las 6 pantallas
   CRUD de web-interno (Solicitudes, Mantenimiento, Finanzas, Flota,
   Cumplimiento) siguen ahora el mismo patrón WorkPanel (§4). Notas de la
   migración, por si hace falta retomarlas:
   - **Flota**: `GET /flota/tablero` no pagina ni filtra en servidor (es un
     tablero en vivo, no un listado CRUD) — la búsqueda/paginación de la
     pantalla son client-side sobre el snapshot que igual se refresca cada
     10s. El detalle es de solo lectura (no hay verbos de edición sobre
     vehículos en este módulo).
   - **Cumplimiento**: "Renovaciones pendientes" pasó a búsqueda+paginación
     client-side (mismo motivo que Flota — `GET
     /documentos/renovaciones-pendientes` no pagina) + `DetailPanel` en
     modo edición con Aprobar/Observar. De paso se corrigió un gap real:
     "Observar" mandaba un motivo hardcodeado
     (`"Documento observado desde el panel interno"`) en vez de dejar que
     el supervisor escribiera el suyo — ahora es un campo obligatorio,
     igual que en Solicitudes.
   - Ambas verificadas en navegador real (login `coordinador_flota` /
     `supervisor_cumplimiento`, búsqueda, paginación, apertura de detalle,
     y en Cumplimiento el flujo completo de "Observar" con motivo,
     confirmado en Mongo — `estado_verificacion` y el evento de bitácora
     `CUMPLIMIENTO_BANDERA_CAMBIO` con el motivo real, no el texto viejo).
   - Tests: no se sumó un test dedicado para Flota/Cumplimiento en esta
     pasada (la red de seguridad de `App.test.tsx` ya cubre el patrón
     WorkPanel sobre Solicitudes) — si se retoca cualquiera de las dos
     pantallas, considerar sumar un test siguiendo ese mismo ejemplo.
2. ~~Trigger automático de `dag_publicar_indicadores` tras cada DAG de
   dominio~~ — **cerrado.** Ver nota en §3 (Plataforma). Los 6 DAGs de
   dominio (viajes, finanzas, captación, cumplimiento, mantenimiento, flota)
   disparan la publicación con `TriggerDagRunOperator` al terminar OK/WARN;
   antes cuatro de ellos (finanzas/captación/cumplimiento/flota) llamaban
   los `refrescar_*` inline dentro de su propio proceso (duplicado,
   invisible como corrida propia en Airflow) — se reemplazó por el trigger
   a la corrida real de `dag_publicar_indicadores`, auditable en su
   historial de DagRuns.
3. ~~`dag_mantenimiento_gold` no existía~~ — **cerrado.** Construido
   completo (Bronze→Silver→Gold→trigger de publicación), alimenta
   `rpt_cumplimiento_plan_preventivo` y `rpt_costo_mantenimiento_vehiculo`
   (los 2 informes que el dashboard táctico de Mantenimiento va a
   necesitar). Ver detalle de diseño y limitaciones (no hay spec de nivel
   táctico en el repo) en la nota de §3.
4. ~~Bug en `dag_flota_gold` (`Invalid None value in non-Nullable
   column`)~~ — **cerrado.** Ver nota de §3. Causa real: `posiciones` nunca
   trae `estado_servicio`; corregido con un join a `usuarios` + columna
   Bronze relajada a `Nullable`. Confirmado con corrida real limpia
   (557/558 válidos).
5. **Nivel táctico — 9 dashboards.** En construcción activa, uno por uno,
   agrupados bajo "Panel Táctico" en el sidebar de `web-interno`
   (`apps/web-interno/src/sections/tactico/`). Patrón backend: cada dominio
   expone sus propios endpoints `GET /<dominio>/panel-tactico/...` (no un
   módulo central) — informes simples pegan directo a Mongo con el query del
   spec, informes compuestos leen `rpt_*` en ClickHouse vía
   `src/core/db_clickhouse.py` (`fetch_latest_snapshot` para el último
   corte, `fetch_snapshot_history` para series de varios `fecha_datos` —
   usado para "tendencia mensual" sin tabla nueva, ver punto de
   Documentación abajo). **Nunca** se agrega lógica de agregación en el
   frontend — eso ya lo hace Airflow/ClickHouse.

   Estado (orden de construcción de la spec, Tabla 3):
   - ~~1. Coordinación de Flota~~ — **cerrado.** `PanelFlota.tsx` +
     `GET /flota/panel-tactico/franja-activa` (compuesto,
     `rpt_flota_activa_franja`) + `GET /flota/tablero` reusado para KPIs y
     lista de sin-señal (simple). Filtro por zona no incluido — gap conocido,
     `fact_ubicacion_flota` no tiene dimensión zona.
   - ~~2. Mantenimiento~~ — **cerrado.** `PanelMantenimiento.tsx` + 3
     endpoints nuevos en `mantenimiento/router.py`
     (`panel-tactico/vehiculos-retirados` simple, `panel-tactico/cumplimiento-preventivo`
     y `panel-tactico/costo-top-vehiculos` compuestos — este último agrega
     por vehículo sumando todos los periodos del snapshot antes de tomar el
     top 5, porque `rpt_costo_mantenimiento_vehiculo` trae una fila por
     vehículo×mes). "Órdenes abiertas" reusa `GET /mantenimiento/ordenes`
     llamado dos veces (ABIERTA + EN_TALLER) y mezclado client-side — no se
     tocó el endpoint existente (`estado` es de valor único, usado también
     por la pantalla operativa de Mantenimiento).
   - ~~3. Cumplimiento — Vigencia Documental~~ (de los 2 dashboards de
     Cumplimiento, este es el primero; "Auditoría e Integraciones" es el
     punto 6.2 más abajo) — **cerrado.** `PanelDocumentacion.tsx` + 3
     endpoints nuevos en `cumplimiento/router.py`. La "tendencia mensual"
     (pedida por el spec, no existía) se resolvió con
     `fetch_snapshot_history` sobre `rpt_documentacion_vigente` sin crear
     tabla nueva ni tocar el DAG — esa tabla es MergeTree (no Replacing) y
     ya conserva un corte por cada `fecha_datos` en que corrió
     `dag_cumplimiento_gold`. **Dato real hoy: la colección `documentos` está
     vacía** (0 documentos en Mongo) — no es un bug de este dashboard, es
     consecuencia directa de que "carga de documentos de postulación" es
     backlog consciente (§3.1): sin esa carga, `captacion/service.py` nunca
     inserta filas en `documentos` al aprobar una solicitud. El dashboard
     muestra correctamente el estado vacío (verificado además insertando un
     documento de prueba temporal en Mongo, confirmando que el query sí
     filtra bien, y borrándolo después).
   - ~~4. Captación~~ — **cerrado.** Requirió cerrar primero el gap de
     `canal`: campo nuevo (`Literal["app","web","referido","campana"]`,
     default `"web"`) en `SolicitudCrearRequest`/`PasajeroRegistroRequest`,
     propagado a `solicitudes` y a `usuarios` (tanto en el registro directo
     de pasajero como al aprobar una solicitud de conductor — hereda el
     canal de la solicitud, no el de la cuenta base). Backfill real corrido
     con `backend/scripts/backfill_canal.py` (idempotente, `$exists:false`):
     4 solicitudes + 23 usuarios. `dag_captacion_gold` reescrito para
     extraer **dos fuentes** en la misma corrida: `usuarios` (→
     `fact_registro_usuario`, alimenta altas/retención) y `solicitudes` (→
     `fact_solicitud_captacion`, tabla Gold nueva, alimenta
     conversión/tiempo de aprobación). 2 `rpt_*` nuevos:
     `rpt_conversion_captacion`, `rpt_altas_retencion_canal` (`retención a
     90 días` es una aproximación documentada en el código — usa el
     `estado` snapshoteado en Gold, no un re-chequeo periódico real, porque
     no existe ningún job que reobserve usuarios 90 días después; sería
     necesario para una métrica de retención real). `PanelCaptacion.tsx` +
     3 endpoints nuevos en `captacion/router.py` (referidos-pendientes
     simple + conversion/altas-retencion compuestos) + reuso de `GET
     /captacion/solicitudes?estado=ENVIADA` para el semáforo de plazo.
     **Bug real preexistente encontrado y corregido de paso**:
     `dag_captacion_gold` filtraba usuarios por `ts_creacion`, un campo que
     `usuarios` **nunca tuvo** (el campo real es `fecha_registro`, ver
     `backend/src/auth/service.py:64`) — `fact_registro_usuario` llevaba
     0 filas desde siempre, nunca detectado porque nada dependía de ese
     dato hasta este dashboard. Corregido junto con el resto. Verificado
     con corridas reales en Airflow (clearing manual de tasks vía CLI, ver
     nota de infraestructura arriba — la tabla `bronze_usuarios` preexistente
     necesitó un `ALTER TABLE ADD COLUMN canal` porque `ensure_schema()` con
     `CREATE IF NOT EXISTS` no altera tablas ya creadas): `fact_solicitud_captacion`
     con 2 filas reales, `fact_registro_usuario` con 6 altas reales con canal
     `web` correcto, `rpt_conversion_captacion` (100% conversión, canal web,
     agosto 2026) y `rpt_altas_retencion_canal` (6 altas, 0% retención — 
     correcto, nadie tiene 90+ días en este dataset de desarrollo) con datos
     reales. Confirmado también en navegador real (login `admin_captacion`).
   - ~~5. Operaciones y Despacho~~ — **cerrado (era el mayor gap del
     proyecto).** `dag_viajes_core` se amplió con una **segunda fuente**
     independiente en la misma corrida: `fact_viaje` (existente, solo
     `PAGADO`, sin tocar — sigue alimentando finanzas con sus reglas Silver
     completas) + `fact_ciclo_viaje` (tabla Gold nueva, **todos los
     estados**, por `ts_solicitud` en vez de `ts_fin`, validación Silver
     mínima -- solo CAMPO_NULO/dedup, a propósito: aplicarle las reglas de
     `fact_viaje` a un SIN_CONDUCTOR/CANCELADO los rechazaría a todos por
     FECHAS_INVALIDAS/ERROR_MONTO, justo los registros que este informe
     necesita). 2 `rpt_*` nuevos: `rpt_tiempo_asignacion` (promedio + p95 de
     segundos solicitud→asignación por zona/franja) y `rpt_tasa_cancelacion`
     (cancelados/solicitados por motivo/actor/zona/mes, SIN_CONDUCTOR
     etiquetado como demanda desatendida). 2 endpoints admin nuevos en
     `viajes/router_trips.py` (`panel-tactico/activos`,
     `panel-tactico/sin-conductor-cancelados`, gateados a
     `coordinador_operaciones` — rol que existía en `core/rbac.py::ROLES`
     pero no tenía ninguna pantalla asignada hasta ahora). `PanelDespacho.tsx`.
     Verificado con corridas reales en Airflow (2026-08-01: 6 SIN_CONDUCTOR +
     3 CANCELADO reales en `fact_ciclo_viaje`; 2026-08-02: 3 viajes con
     `ts_asignacion` real, alimentando `rpt_tiempo_asignacion` con segundos
     reales por zona/franja) y en navegador real (login con rol
     `coordinador_operaciones` agregado a `staff-verificacion` para la
     prueba), los 4 endpoints devolviendo 200 con datos reales.
   - ~~6.1/6.2. Finanzas (2 dashboards)~~ — **cerrado.** Sorpresa positiva:
     `ts_pago` **ya existía** en `LiquidacionOut`/`recaudacion/service.py`
     (se setea correctamente al pagar) — el gap real estaba solo en el DAG,
     que nunca lo propagaba a Gold. `dag_finanzas_gold` y
     `fact_liquidacion` ampliados con `ts_emision`/`ts_pago`;
     `rpt_margen_comision` +`horas_hasta_pago_promedio`;
     `rpt_tasa_discrepancias` rediseñado (antes por día sin dimensión de
     método, ahora por mes + `metodo` + `pct_conciliado` -- tabla recreada
     desde cero en ClickHouse, era solo snapshot derivado, no dato fuente).
     `PanelConciliacion.tsx` + `PanelLiquidacion.tsx`, **sin endpoints admin
     nuevos para los informes simples** — `GET /pagos/discrepancias` y `GET
     /liquidaciones` ya existían completos, solo se agregaron
     `GET /pagos/panel-tactico/tasa-discrepancias` y `GET
     /liquidaciones/panel-tactico/margen-comision` para los compuestos.
     Verificado con corridas reales en Airflow (margen 20%, 1.25h promedio
     de pago, 33.3% conciliado con 3 liquidaciones/pagos reales) y en
     navegador real (login `admin_financiero`).
   - ~~6.2. Cumplimiento — Auditoría e Integraciones~~ (**patrón F**, el
     único de los 9 — tabla de bitácora como elemento dominante, KPIs como
     franja delgada de contexto arriba, no 4 tarjetas grandes) — **cerrado.**
     La bitácora reusa `GET /auditoria/eventos` tal cual (ya cubría
     actor/rol/acción/entidad/resultado/hora, CU-O17) — sin endpoint nuevo.
     "Uso de integraciones por credencial/endpoint": el usuario decidió
     **backlog consciente** para la dimensión credencial/latencia/error (no
     existe ese dominio) — se construyó igual el gráfico de uso por endpoint
     reusando `rpt_uso_integraciones` (ya existía, alimentaba el catálogo de
     Indicadores) vía un endpoint nuevo de solo lectura
     (`GET /auditoria/panel-tactico/uso-integraciones`). "% error API" se
     muestra como "—" con nota explícita en el dashboard, en vez de
     fabricar el dato. `PanelAuditoria.tsx`. Verificado en navegador real
     (login `supervisor_cumplimiento`): bitácora con eventos reales
     (incl. una racha real de `POSIBLE_GPS_SPOOFING` denegado), gráfico de
     uso por endpoint con 12 endpoints reales.
   - ~~7. Plataforma~~ — **cerrado.** "Corridas del pipeline" servido desde
     ClickHouse (tabla `corridas`, real) vía `GET
     /plataforma/panel-tactico/corridas` (con filtro `dominio`/`fecha_logica`)
     — la colección Mongo `corridas_etl` que pedía el spec no existe.
     "% de cuarentena por dominio": `rpt_cuarentena_dominio` nuevo (agrega la
     corrida MÁS RECIENTE de cada DAG desde `corridas` — es el único
     `refrescar_*` que no depende del gate OK/WARN de un solo dominio, es
     meta-informe sobre los 7 DAGs a la vez) + tarea nueva en
     `dag_publicar_indicadores`. "Avance de capacitación por área": el
     usuario decidió **backlog consciente** — no existe ningún dominio de
     capacitación en el sistema, KPI se muestra como "—" con nota explícita,
     sin la lista. `PanelPlataforma.tsx`. Verificado con corrida real
     (`refrescar_cuarentena_dominio` ejecutado en Airflow, 7 DAGs con % de
     cuarentena real: desde 0% hasta 11% en `dag_cumplimiento_gold`) y en
     navegador real (login `responsable_plataforma`, filtro por dominio
     probado y confirmado en la red).

   **Los 9 dashboards del nivel táctico quedaron cerrados.** Suite completa
   verificada al cierre: `npm run build/lint/test -w @urbanflet/web-interno`
   limpios, `pytest` backend 180/180, sin regresión en ningún test
   preexistente.

   ### 5.1 Rediseño visual completo de los 9 dashboards — cerrado

   Pedido explícito del usuario tras revisar capturas: los gráficos no eran
   gráficos reales (un `<div>` con ancho proporcional y un número), el patrón
   Z/F no se distinguía visualmente (todo apilado verticalmente igual),
   faltaban filtros del spec en varias pantallas, y la jerarquía tipográfica/
   color de los KPI era plana. Se leyó la skill `dataviz` (paleta categórica
   de 8 colores validada por `scripts/validate_palette.js`, status colors
   reservados, un eje siempre, tooltip+leyenda) antes de tocar código.

   - **`BarChart` casero eliminado**, reemplazado por `CategoryBarChart` y
     `TrendLineChart` (ambos genéricos sobre `recharts`, nueva dependencia
     real en `apps/shared-ui/package.json`). Regla aplicada: barras para
     comparación entre categorías (costo por vehículo, uso por endpoint),
     líneas para tendencia en el tiempo (documentación vigente mensual,
     margen de comisión, conversión por canal — estas últimas 2-3 se pivotan
     client-side de `[{periodo,canal,valor}]` a `[{periodo, canalA, canalB}]`
     antes de pasarlas al chart, la agregación real sigue viniendo de
     ClickHouse, el pivot es solo reshape para el eje X). Colores de serie
     nunca a mano — siempre `seriesColor(i)` sobre el orden fijo de
     `--chart-series-1..8`.
   - **`npm install` de recharts requirió `--legacy-peer-deps`** (conflicto
     de peers con react-dom@19 que arrastraba alguna sub-dependencia) — y esa
     reinstalación completa **rompió `@testing-library/dom`** (quedó
     declarado como peer pero no instalado físicamente, `screen`/`waitFor`
     dejaron de resolver en TS) hasta agregarlo explícito como devDependency
     de raíz. Si se vuelve a tocar `package.json` de `shared-ui`, correr
     `npm run build -w @urbanflet/web-interno` después del install antes de
     asumir que quedó bien.
   - **Patrón Z real**: `DashboardZ` (`apps/shared-ui/src/components/
     DashboardLayout.tsx`) renderiza un CSS grid de 2 columnas iguales
     (gráfico izquierda, lista derecha, misma fila — no apilado) que
     colapsa a 1 columna bajo 900px (`DashboardLayout.css`). Aplicado a los
     8 dashboards Z.
   - **Patrón F real**: `DashboardF` usa grid `320px : 1fr` (columna de
     gráfico angosta y fija, lista dominante) — a propósito distinto de Z
     (no 50/50). Aplicado solo a Auditoría e Integraciones, el único F de
     los 9. Verificado en navegador: `getComputedStyle` midió `320px
     768.8px` en F contra `552px 552px` en Z a 1440px de ancho.
   - **Filtros del spec completados** donde faltaban: Flota (franja + zona
     deshabilitada con nota, zona sigue sin dato real), Mantenimiento (+
     rango de fechas, vehículo), Documentación (+ tipo de documento, rango
     de vencimiento — antes no tenía NINGÚN filtro), Captación (+ canal,
     rango de fechas — antes ninguno), Despacho (+ zona, franja, rango de
     fechas — antes ninguno), Conciliación (+ método de pago, rango de
     fechas — antes ninguno), Liquidación (+ periodo, socio), Auditoría (+
     acción, rango de fechas — actor/resultado ya existían). Plataforma ya
     tenía dominio; se agregó fecha lógica (el backend ya la soportaba, no
     estaba expuesta en la UI).
   - **KPI con jerarquía real**: `KpiCard` ahora renderiza la etiqueta en
     14px/500 mayúsculas y el valor en 36px/700 — confirmado con
     `getComputedStyle` en navegador, no solo leído en el código. Tono de
     estado (`exito`/`advertencia`/`serio`/`peligro`) mapea a
     `--status-good/warning/serious/critical` de la paleta validada, nunca
     texto plano — confirmado que "Sin señal" con `tono="peligro"` pinta
     `rgb(208,59,59)` real en el DOM.
   - **Nombre legible en el header**: `staff-verificacion` (usuario_id crudo)
     reemplazado por el `nombre` real. Requirió un cambio de backend: `nombre`
     ahora viaja como `extra_claims` del JWT (mismo mecanismo ya usado para
     `roles`, ver `create_token` en `core/security.py` — informativo, nunca
     usado para autorización) seteado en `_emitir_tokens`
     (`auth/service.py`). Sesiones con un token viejo (emitido antes de este
     cambio) no tienen `nombre` en el payload — un logout/login nuevo lo
     resuelve, no hace falta invalidar tokens existentes a la fuerza.
   - Paleta de tokens (`tokens.css`): `--color-accent` realineado a
     `#2a78d6` (mismo azul que la serie 1 de gráficos, antes `#1f6feb`
     arbitrario), `--color-danger`/`--color-success` realineados a los hex
     validados de la skill (`#d03b3b`/`#0ca30c`). `--color-warning` se dejó
     en su valor previo (`#b5760a`) a propósito — el "warning" validado de
     la skill (`#fab219`) es amarillo brillante, pensado para texto sobre
     superficie clara con relief rule; en este código el mismo tono se usa
     como *fondo* de `Badge` con texto blanco encima, donde `#fab219` da
     contraste pobre — se prefirió mantener el ámbar oscuro ya en uso, que sí
     funciona como fondo.
   - Verificación: los 9 dashboards confirmados uno por uno en navegador
     real (login `staff-verificacion`, que acumula los 7 roles tácticos) —
     grid de 2 columnas medido con `getComputedStyle` en cada uno, ejes con
     ticks reales visibles (`0%, 25%, 50%...` o `0s, 5s, 10s...` según el
     dato), ≥1 filtro interactivo probado en vivo confirmando que el gráfico
     recalcula (ej. Despacho: filtrar a zona Z-NORTE bajó las barras de 3 a
     1). `npm run build/lint/test` limpios en las 3 apps + `shared-ui` lint,
     `pytest` backend 185/185 (subió de 180 por tests de AJUSTE de una
     sesión anterior, sin relación con este rediseño).

   ### 5.2 Re-verificación + 2 ajustes puntuales en Auditoría — cerrado

   El usuario pidió retomar este bloque asumiendo que había quedado a medio
   terminar (interrumpido por el cambio de arquitectura NYC, punto 7 más
   abajo). Verificado contra el código real antes de tocar nada: los 4
   criterios (gráficos reales vía `CategoryBarChart`/`TrendLineChart`,
   patrón Z/F real, filtros del spec, KPI con jerarquía) ya estaban
   satisfechos en los 9 `Panel*.tsx` — ningún gráfico casero, ningún
   dashboard sin su layout correcto. Lo que sí eran reales eran los 2
   ajustes puntuales que el usuario reportó con evidencia sobre Auditoría:

   - **Bitácora vs gráfico desproporcionados**: medido en navegador real
     con `getComputedStyle` — la tarjeta del gráfico medía 624.8px de alto,
     la de la bitácora **10,569.6px** (100 filas sin límite de alto,
     estirando toda la página). El ratio de columnas del patrón F (320px:
     1fr) ya era correcto — el problema era de alto, no de ancho. Corregido
     agregando `altoMaximo` (prop nueva, opcional) a `DataTable`
     (`apps/shared-ui/src/components/DataTable.tsx`) — scroll interno
     (`overflow-y:auto`) en vez de estirar la página. Aplicado solo en
     `PanelAuditoria.tsx` (`altoMaximo={620}`), sin tocar los otros 8 (no
     lo necesitan). Alto de la bitácora bajó a 862.4px, comparable al
     gráfico.
   - **Columna "Rol" con ancho excesivo**: medida real, 594.7px (más de la
     mitad de la tabla). Causa real: el layout automático de `<table>`
     estira toda la columna al ancho de su celda más larga — un evento de
     auditoría real tiene `rol` con los 4 roles de `staff-verificacion`
     concatenados por coma (`"admin_captacion,jefe_mantenimiento,..."`, 76
     caracteres), no un bug de datos. Corregido agregando `width` (prop
     nueva, opcional) a `Column` en `DataTable` — ancho fijo con
     `overflow-wrap` para que el contenido largo haga wrap en vez de
     estirar la columna. Aplicado `width="160px"` a la columna Rol de
     Auditoría; sin efecto en las demás columnas/dashboards (prop opcional,
     sin valor por defecto).
   - Ambas props (`altoMaximo`, `width` por columna) quedan reutilizables en
     `DataTable` para cualquier dashboard futuro con el mismo problema.
   - Verificado en navegador real tras el fix: `dashboard-f-row` sigue en
     `320px 608.8px`, tarjeta de gráfico 624.8px, tarjeta de bitácora ahora
     862.4px (antes 10,569.6px), columna Rol exactamente 160px (antes
     594.7px), contenido de la bitácora renderiza correcto con datos reales.
     `npm run build/lint/test` limpios en `web-interno` + `shared-ui` lint.
   - Nota sobre un supuesto "gap" que NO es tal: `AppShell` cae a
     `actor?.sub` (id crudo) si el JWT no trae `nombre` — esto es el
     comportamiento ya documentado y aceptado en la sesión que agregó
     `nombre` al token (ver más abajo, "Nombre legible en el header"):
     solo afecta sesiones con un token viejo emitido antes de ese cambio,
     un logout/login nuevo lo resuelve. No es una regresión de este punto.
6. **Correcciones post-auditoría #2 ("CIERRE DE LA PARTE OPERATIVA") — en
   curso, interrumpidas a mitad de sesión por límite de uso de la cuenta
   (3 de 4 agentes en paralelo murieron con "session limit", no por error
   de código).** Estado real verificado directamente (no asumido del
   reporte de los agentes):
   - ✅ **Cerrado**: `admin_plataforma` agregado al array `SECCIONES` de
     `apps/web-interno/src/App.tsx` (sección Indicadores) — verificado con
     login real.
   - ✅ **Cerrado**: bug de CORS en Directions API (`GET
     /viajes/estimacion-ruta` server-side, ver §4), `GET /viajes/activo`
     404→200, tamaño del panel flotante, z-index del panel de ofertas en
     conductor, tamaño del ícono de posición propia — todos verificados en
     navegador real.
   - ✅ **Cerrado**: siembra de datos falsos en `referidos` (5-10
     documentos coherentes insertados directo en Mongo) — se abandonó la
     idea de un módulo de Referidos propio, no hay spec que lo respalde.
   - ❌ **NO cerrado, pese a que una versión previa de este archivo lo daba
     por hecho** (corregido en la tabla de §3): **CU-O05 A3 "Reintentar
     búsqueda"** tras `SIN_CONDUCTOR` — el estado `SIN_CONDUCTOR` sigue sin
     un botón de reintento en `apps/web-pasajero/src/App.tsx`
     (`ESTADOS_CANCELABLES_PASAJERO` no lo incluye). **CU-O10 A2
     (movimiento `AJUSTE`)** — existen tests
     (`backend/tests/recaudacion/test_ajuste_movimiento.py`, 5 casos, pasan)
     pero **0 documentos reales `movimientos.tipo="AJUSTE"` en Mongo** —
     confirmado por query directa. No se sabe con certeza si el agente
     interrumpido llegó a cablear el endpoint/UI o si se quedó solo en
     service+tests.
   - ⚠️ **Estado incierto** (Bloque 2 de la instrucción de cierre — items
     4-11: exponer campos de conductor/vehículo faltantes, comentario en
     calificaciones, filtro de rango de fechas, detalle clickeable de
     historial, input de repuestos al crear orden, repuestos-consumidos/
     horas-taller/ajuste-justificado al cerrar orden, pantalla mínima de
     bitácora + canal de alertas de seguridad, texto "N viajes en
     revisión"). Un agente interrumpido dejó cambios a medio terminar en
     `apps/web-conductor/src/App.tsx` (imports de `DetailField`/
     `DetailPanel` de shared-ui sin confirmar si el flujo quedó completo).
     **Confirmado que nada quedó roto** (`tsc -b` limpio en las 3 apps,
     `pytest` 185/185 — subió de 180 por los tests de AJUSTE nuevos —,
     `ruff check` limpio tras corregir un E501 suelto en
     `backend/src/mantenimiento/service.py`), pero la cobertura funcional
     real de estos 8 puntos necesita una revisión explícita antes de darlos
     por cerrados.
   - **Antes de retomar este punto 6**: no repetir el patrón de auditoría
     completa — usar `auditoria_cu_02.md` como mapa de qué falta y verificar
     puntualmente contra el código actual (puede haber cambiado desde que se
     escribió). Recordatorio operativo: cuentas de prueba tipo
     `staff-verificacion` acumulan roles entre sesiones (a la fecha de este
     cierre tenía las 7 combinaciones que suelen pedirse:
     `admin_captacion, jefe_mantenimiento, supervisor_cumplimiento,
     coordinador_flota, coordinador_operaciones, admin_financiero,
     responsable_plataforma`) — verificar sus roles/contraseña reales en
     Mongo antes de asumirlos, no reusar credenciales de una sesión vieja
     sin confirmar.
7. **Cambio de arquitectura — dataset NYC como fuente de siembra operativa
   real (no solo referencia aislada), en curso.** Decisión explícita del
   usuario, documentada aquí ANTES de tocar código (instrucción directa).
   Diverge de `diseno_base_datos.md`, que describe PocketBase como
   exclusivamente fuera del flujo de negocio — sigue siéndolo para el flujo
   original, pero ya no es el único uso del dataset.

   **Contexto real encontrado al arrancar** (verificado contra código, no
   asumido): `dag_historico_nyc` **nunca leyó de PocketBase** — desde su
   construcción original lee un archivo local
   (`analytics/seed_data/nyc_yellow_tripdata_2015-08_seed.csv`, dataset
   **2015**, ~4000 filas, con columnas ya normalizadas —
   `id_origen`/lat-lon/ISO-8601 — que no existen en el CSV crudo real). El
   `docker-compose.yml` ya documentaba la intención real en un comentario
   ("BD de dataset crudo: exclusivamente 2021 Yellow Taxi Trip Data") — el
   archivo 2021 correcto (`data/nyc_taxi/yellow_tripdata.csv`, 1,360,493
   filas, columnas TLC estándar: `VendorID`, `tpep_pickup_datetime`,
   `PULocationID`/`DOLocationID` en vez de lat/lon, sin `id_origen`,
   **separador decimal coma** `"2,34"` y fecha `MM/DD/YYYY hh:mm:ss AM/PM`)
   nunca había sido cargado hasta esta sesión. `PanelPlataforma`/Airflow ya
   mostraban `dag_historico_nyc` corriendo con el CSV 2015 viejo — eso
   queda reemplazado por el dataset 2021 real de aquí en adelante.

   **Decisión tomada sobre el punto donde el pedido del usuario no
   coincidía con el código real**: el usuario asumía que `dag_historico_nyc`
   ya lee desde PocketBase ("sigue siendo la fuente... sin cambios, flujo
   ya existente") — no es así, nunca lo fue. Se decidió **mantener
   `dag_historico_nyc` leyendo el CSV local directo** (no agregar un
   round-trip HTTP paginado contra PocketBase para 1.3M filas — aun en
   lotes de 500 son ~2600 requests, frágil y lento comparado con leer el
   archivo en streaming) y, por separado, cargar el mismo CSV a PocketBase
   `raw_trips` como pidió el Paso 1 — los dos flujos leen el mismo archivo
   fuente de forma independiente, PocketBase queda con una copia real y
   consultable pero no en el camino crítico de ningún DAG. Ver
   `analytics/scripts/load_raw_trips_pocketbase.py` para el razonamiento
   completo (por qué se escribe directo al SQLite de PocketBase en vez de
   la API REST, y por qué el contenedor debe estar detenido mientras corre).

   **Requisito no negociable**: los 1.3M registros completos, sin
   muestreo. Diseño para ese volumen: lectura en streaming (nunca el CSV
   completo en memoria), inserciones batched (`bulk_write`/`executemany`),
   sin recrear índices existentes (solo se confirma que ya existen antes de
   insertar — `viajes` y `pagos` los mantienen automáticamente en cada
   insert, MongoDB no necesita un paso de "reconstruir índice" entre lotes).

   Estado de las 3 piezas — actualizar conforme avancen:
   - ~~`analytics/scripts/load_raw_trips_pocketbase.py` (Paso 1, PocketBase
     `raw_trips`)~~ — **cerrado.** Escribe directo al SQLite de PocketBase
     (`INSERT OR IGNORE`, id determinista `nyc{fila:09d}`) con el contenedor
     `pocketbase` detenido durante la carga. Probado primero con un lote de
     500 filas (sin diferencia de datos con el archivo completo, mismo
     archivo real recortado) antes de correr las 1.36M. **Corrida real:
     1,360,493 filas en 137 lotes de 10,000, 32s totales** (~42,500
     filas/s) — muy por debajo de la estimación inicial de 1-5 min.
     Confirmado el conteo tanto por SQLite directo como por la API REST de
     PocketBase ya reiniciado (`totalItems: 1360493`). El superusuario de
     PocketBase no existía con la contraseña placeholder del `.env`
     (`change-me-in-every-environment` nunca se había aplicado) — se creó
     uno real vía `pocketbase superuser upsert` y se actualizó
     `POCKETBASE_ADMIN_PASSWORD` en `.env` a un valor real.
   - ~~`analytics/dags/dag_historico_nyc.py` (reescrito para volumen)~~ —
     **cerrado.** Rediseño de 5 tasks (pasaba el CSV completo por XCom,
     nunca hubiera soportado 1.3M filas) a 2 tasks (`procesar`→`metricas`)
     con streaming real: `csv.DictReader` + chunks de 20,000 filas,
     Bronze/Silver-Cuarentena/Gold por chunk, solo contadores por XCom.
     Gold usa `borrar_particion_gold` UNA vez al inicio (nuevo, en
     `medallion.py`) + `insertar_gold_chunk` por chunk sin volver a borrar
     — evita la condición de carrera de llamar `cargar_gold_idempotente`
     (borra-e-inserta) una vez por chunk contra la misma partición.
     Columnas migradas al esquema real 2021 (`VendorID`,
     `tpep_pickup_datetime`, `PULocationID`/`DOLocationID`, sin lat/lon,
     coma decimal, fecha `MM/DD/YYYY hh:mm:ss AM/PM`) — antes leía un CSV
     2015 de muestra con columnas ya normalizadas que no existen en el
     archivo real. Se agregó `congestion_surcharge` a ambas tablas
     ClickHouse (`bronze_viaje_historico_nyc`, `fact_viaje_historico`, vía
     `ALTER TABLE ADD COLUMN` real, `CREATE IF NOT EXISTS` no altera tablas
     ya creadas).
     **Bug real encontrado y corregido en la regla ERROR_MONTO durante la
     prueba de 500 filas**: el dataset 2021 real es inconsistente en si
     `total_amount` incluye `congestion_surcharge` o no — un lote de filas
     seguidas lo excluye consistentemente (confirmado inspeccionando 10
     filas rechazadas: mismo diff exacto de $2.50 en todas). No es
     corrupción del dato, es una inconsistencia real del origen TLC. Se
     corrigió para aceptar CUALQUIERA de las dos fórmulas (con o sin
     congestión) dentro de tolerancia — con solo una fórmula, 117/500
     filas válidas (23.4%) quedaban falsamente en cuarentena.
     **Corrida real a escala completa**: 1,360,493 filas leídas, 1,334,229
     válidas (98.1%), 26,264 en cuarentena, 69 chunks, **42s totales**
     (~32,800 filas/s) — muy por debajo del límite de `execution_timeout`
     de 2h. Confirmado en ClickHouse: `fact_viaje_historico` (partición
     `fecha='2026-08-02'`) con exactamente 1,334,229 filas,
     `bronze_viaje_historico_nyc` con 1,360,493, `cuarentena_historico_nyc`
     con 26,264 — los tres cuadran exactamente con el log de la tarea.
   - `analytics/scripts/seed_viajes_nyc.py` (Paso 2, siembra real en
     `viajes`/`pagos`) — **escrito, prueba de checkpoint (300 filas) OK,
     escala completa (1.3M) pendiente de confirmación del usuario** (así lo
     pidió explícitamente antes de lanzar el proceso completo). Mapeo
     completo documentado en el docstring del script: round-robin
     determinista (`fila % len(pool)`) sobre el pool de prueba existente (9
     pasajeros, 5 pares conductor→vehículo — **no se generaron usuarios
     nuevos**, decisión tomada sin bloquear en el usuario pero dejada
     explícita aquí: con 1.36M viajes repartidos entre 5 conductores, cada
     uno queda con ~270K viajes históricos — cifra irreal por conductor,
     aceptable solo porque el propósito es dar volumen a los dashboards
     tácticos, no simular una flota creíble; si se quisiera una
     distribución más realista habría que sembrar más conductores/vehículos
     de prueba antes de la corrida completa); coordenadas sintéticas
     ancladas a Quevedo (`PULocationID`/`DOLocationID` + fila como semilla
     hash, nunca coordenada NYC real); `payment_type` 1→ELECTRONICO,
     2→EFECTIVO, resto (3/4/5/6/vacío)→EFECTIVO (documentado: `MetodoPago`
     no tiene equivalente a disputa/anulado/desconocido); `estado` ~93%
     PAGADO / ~7% CANCELADO (fracción determinista por hash de fila);
     mismo filtro de calidad que `dag_historico_nyc`
     (DISTANCIA_CERO/FECHAS_INVALIDAS) — dejó 298/300 válidas en la prueba,
     proporción consistente con el 98.1% de la corrida completa del DAG.
     Idempotente confirmado: reejecutar la prueba de 300 filas dio 0
     viajes/pagos nuevos la segunda vez. Corre dentro del contenedor con
     la imagen `urbanflet-taxiflow-backend` en la red de docker-compose
     (`--network urbanflet-taxiflow_default`) porque el replica set de
     Mongo anuncia internamente el hostname `mongo:27017` — conectar desde
     el venv local con `localhost:27017` falla en el descubrimiento SDAM
     aunque el URI inicial apunte a localhost.
     **No se fabrican discrepancias de pago** (`pagos.diferencia` siempre
     `None`, `estado` siempre `VALIDADO`) — el dataset NYC no da ninguna
     señal real para inventar un monto distinto al cobrado; los 10 pagos
     con discrepancia ya sembrados a mano siguen siendo la única fuente de
     esa métrica.

   **Escala completa (1.3M) — cerrada, con confirmación explícita del
   usuario antes de lanzarla (checkpoint respetado).** Corrida real:
   1,360,493 filas leídas, 1,334,748 válidas (25,745 descartadas por
   DISTANCIA_CERO/FECHAS_INVALIDAS — 98.1%, mismo filtro que
   `dag_historico_nyc`), **211s totales** (~6,470 filas/s, más lento que la
   carga de PocketBase por el overhead de `bulk_write` con 2 colecciones vs
   `executemany` a SQLite). Resultado real en Mongo: **1,334,748 viajes**
   (93,089 CANCELADO + 1,241,659 PAGADO) + **1,241,659 pagos** — conteos
   verificados exactos, cuadran con el log del script.

   **Paso 3 (verificación real) — cerrado**, con un hallazgo real de
   infraestructura no anticipado:

   - **Bug real encontrado al disparar `dag_viajes_core`/`dag_finanzas_gold`
     para las fechas históricas 2021**: ambos DAGs tienen `start_date=
     datetime(2024,1,1)`. Un trigger para una fecha lógica anterior a
     `start_date` NO falla ni avisa — el scheduler crea el DagRun pero
     **cero TaskInstances**, y lo cierra como `success` trivialmente (0/0
     tareas). El primer intento de disparar los 33 días
     (2021-01-01..2021-02-02) reportó "33 success" en
     `airflow dags list-runs` sin haber movido un solo dato — detectado
     porque `fact_viaje`/`fact_ciclo_viaje` en ClickHouse seguían en 0 para
     ese rango pese a los "success". **Corregido**: `start_date` bajado a
     `datetime(2020,1,1)` en ambos DAGs (`catchup=False` evita que esto
     dispare una avalancha de corridas retroactivas — el comportamiento del
     scheduler diario en producción no cambia). Reintentado con
     `airflow dags backfill -s 2021-01-01 -e 2021-02-03 --reset-dagruns -y`
     (la herramienta correcta para esto, no un loop de `dags trigger`) — 33
     DagRuns reales por DAG, 165 tareas cada uno, 0 fallos.
   - **Conteos ClickHouse verificados exactos contra Mongo**:
     `fact_viaje`=1,241,659 (=pagos PAGADO), `fact_ciclo_viaje`=1,334,748
     (=total viajes nyc), ambos para el rango 2021-01-01..2021-02-02.
     `fact_recaudacion`=1,236,134 (gap de 5,525 sobre el total de pagos
     explicado por la regla Silver `MONTO_NEGATIVO` — el dataset NYC real
     trae una fracción de filas con `total_amount` negativo, reembolsos/
     correcciones reales del origen TLC, correctamente puestas en
     cuarentena). `fact_liquidacion`=0 para el rango, correcto — no se
     sembraron liquidaciones (Paso 2 documentado arriba).
   - **2 índices nuevos en `viajes`** (`backend/src/core/db_mongo.py`,
     creados también en vivo con `createIndex`, no solo en el código):
     detectados con la app real, no adivinados. `GET
     /viajes/panel-tactico/sin-conductor-cancelados` pasó de <50ms a
     **1.15s** (filtra `estado IN [SIN_CONDUCTOR,CANCELADO]`, no cubierto
     por el índice parcial existente que solo indexa estados activos) →
     `{estado:1, ts_solicitud:-1}` parcial sobre esos 2 estados, vuelve a
     ~15ms. `GET /pagos/discrepancias` (bandeja CU-O09 A4, viajes
     FINALIZADO con `ts_fin` viejo sin pago) pasó a **1.09s** confirmado
     con `explain()`: COLLSCAN sobre 1,334,803 documentos para encontrar 3
     → `{estado:1, ts_fin:1}` parcial sobre FINALIZADO, vuelve a ~16ms. El
     resto de los 9 dashboards tácticos no toca `viajes`/`pagos` en volumen
     y no mostró degradación.
   - **Verificado en navegador real** (login `staff-verificacion`, 7 roles
     tácticos): Despacho carga rápido y correcto (KPIs de "hoy" siguen en 0,
     como corresponde — los viajes NYC son de 2021, no afectan el estado en
     vivo); Conciliación muestra la tendencia mensual con los nuevos
     periodos reales `2021-01`/`2021-02` junto al `2026-07` preexistente
     (prueba directa de que la propagación a ClickHouse llegó hasta el
     dashboard); Liquidación correctamente sin cambios (no se sembraron
     liquidaciones); Flota (no relacionado) confirmado sin regresión.
   - **Suite backend sin regresión**: `pytest` 177 passed + 8 skipped
     (=185, mismo total que la sesión anterior) tras los cambios en
     `db_mongo.py` y los 2 DAGs.

   **Cierre del punto 7 completo.** Las 3 piezas (PocketBase, DAG
   histórico, siembra operativa) y la verificación de extremo a extremo
   quedan cerradas. Nota para la próxima sesión que use este volumen: el
   pool de 5 conductores/9 pasajeros usado en el round-robin sigue siendo
   el mismo de siempre — cualquier vista que liste "viajes por conductor"
   sin paginar fuerte va a mostrar ~270K resultados por los 5 socios de
   prueba; es esperado, no un bug.

## 8. Estado final y limitaciones conocidas (cierre de entrega)

Sección consolidada a pedido explícito del usuario — reúne en un solo
lugar lo que antes estaba disperso en el historial de §3/§7. Escrita al
cierre de la sesión que agregó el volumen NYC (1.3M viajes) y re-verificó
el rediseño de los 9 dashboards tácticos. Si el estado real cambia, se
actualiza acá, no se abre una sección nueva paralela.

### 8.1 Regresión final confirmada (esta sesión, tras todos los cambios acumulados)

`npm run build/lint/test` limpios en `web-pasajero`, `web-conductor`,
`web-interno` + `shared-ui` lint; `pytest` backend **177 passed, 8
skipped**, sin regresión — corrido de nuevo después del rediseño de
dashboards, la carga de 1.3M registros y los 2 índices nuevos de Mongo.

### 8.2 Limpieza de datos de prueba — hecha esta sesión

Se encontraron y borraron **7 documentos sueltos en `viajes`** con
`motivo_cancelacion` de depuración manual (`"reset_prueba"`, `"prueba de
diagnostico"`, `"prueba de diagnostico css"`, `"dato de prueba de
verificacion"`) — no pertenecían a ningún seed oficial versionado.
Confirmado que no tenían `pagos` vinculados y que nunca se propagaron a
ClickHouse (`fact_ciclo_viaje` no tenía ninguna fila para esas fechas).
Revisado también `documentos` (0, correcto — backlog de carga de
documentos), `movimientos.tipo="AJUSTE"` (0, gap ya documentado en §3),
`ordenes`/`usuarios` (sin artefactos de depuración sueltos) — todo lo
demás ya estaba limpio.

### 8.3 Backlog consciente — lista completa con razón (decisión tomada, no reabrir sin pedido explícito)

| Ítem | CU / dashboard | Razón |
|---|---|---|
| Carga de documentos de postulación | CU-O01 | Fuera de alcance por decisión consciente desde el inicio |
| Pago electrónico / pasarela | CU-O09 | Ídem — `MetodoPago` solo soporta EFECTIVO/ELECTRONICO como valor de dato, sin integración real |
| Chat / llamada pasajero-conductor | CU-O07 | Ídem |
| Comprobante de viaje en PDF | CU-O14 | Ídem |
| Reset de contraseña | CU-O02 | Ídem |
| Corrección de liquidación post-PAGADA vía nota de ajuste | CU-O11 A4 | Ídem |
| Anonimización de datos LOPDP | CU-O17 A2 | Ídem |
| OTP por SMS | CU-O02 (login) | El diseño migró a usuario+contraseña, ver §4 — no reintroducir sin pedido explícito |
| "% error API" en dashboard de Auditoría | Panel Auditoría e Integraciones | No existe dominio de credenciales/latencia/error de integraciones en el sistema — se muestra "—" con nota explícita en vez de fabricar el dato |
| "Avance de capacitación por área" en dashboard de Plataforma | Panel Plataforma | No existe ningún dominio de capacitación en el sistema — se muestra "—" con nota explícita, sin lista |
| `movimientos.tipo="AJUSTE"` real | CU-O10 A2 | Tests existen (`backend/tests/recaudacion/test_ajuste_movimiento.py`) pero 0 documentos reales en Mongo — el flujo de negocio para generar un ajuste real desde la UI no está cableado todavía |
| Filtro por zona en Panel de Flota | Panel Flota (táctico) | `fact_ubicacion_flota` no tiene dimensión zona — filtro deshabilitado con nota en la UI |

### 8.4 Confirmación de alcance construido y verificado

- **9 dashboards tácticos** (`apps/web-interno/src/sections/tactico/Panel*.tsx`):
  Flota, Mantenimiento, Documentación (Vigencia Documental), Captación,
  Despacho, Conciliación, Liquidación, Auditoría e Integraciones,
  Plataforma. Los 4 criterios de diseño (gráficos reales vía `recharts`,
  patrón Z u F según corresponda, filtros del spec, KPI con jerarquía
  visual) verificados por código y en navegador real esta sesión —
  incluida una comparación lado a lado midiendo `getComputedStyle` que
  confirma que `DashboardF` (Auditoría, `320px : 1fr`) y `DashboardZ` (los
  otros 8, `1fr : 1fr` siempre igual) son dos componentes distintos, no el
  mismo grid reutilizado por accidente.
- **5 pantallas CRUD operativas con patrón WorkPanel** (no 6 — corrigiendo
  una imprecisión: hay una 6ª sección, "Indicadores", pero es un catálogo
  de solo lectura de CU-O15/16, sin `ActionBar` de
  Nuevo/Actualizar/Eliminar, así que no sigue el patrón WorkPanel):
  Solicitudes, Mantenimiento, Cumplimiento, Flota, Finanzas — las 5
  cerradas y verificadas en navegador real (ver §7 punto 1 para el detalle
  de Flota/Cumplimiento).
- Ambos bloques (9 tácticos + 5 CRUD) confirmados sin regresión tras la
  siembra de 1.3M viajes NYC (ver §8.1).

### 8.5 Concentración de datos en el pool de prueba — por si sale en la demo

Los 1.3M viajes históricos sembrados desde el dataset NYC (§7 punto 7) se
repartieron por round-robin determinista sobre el pool de prueba que ya
existía — **9 pasajeros, 5 pares conductor→vehículo** — no se generaron
usuarios nuevos (decisión documentada en §7 punto 7). Consecuencia
esperada, no un bug: cada uno de los 5 conductores queda con ~270,000
viajes históricos en su registro, una cifra que no correspondería a un
socio real. Si en la demo se abre cualquier vista que liste "viajes por
conductor" sin paginar (ninguna pantalla oficial lo hace sin paginación,
pero una query manual sí lo mostraría), ese volumen por conductor es
water-mark esperado del dataset de desarrollo, no una señal de un bug de
asignación. El propósito de la siembra fue dar volumen de consulta real a
los 9 dashboards tácticos, no simular una flota creíble.

### 8.6 Levantar el stack completo desde cero

```bash
# 1. Servicios de infraestructura (Mongo, Redis, ClickHouse, PocketBase, Airflow, backend)
docker compose up -d

# 2. Los 3 frontends (no dockerizados) -- cada uno en su propia terminal,
#    o via el tooling de preview del harness (.claude/launch.json)
npm run dev -w @urbanflet/web-pasajero   # puerto 5173
npm run dev -w @urbanflet/web-conductor  # puerto 5174
npm run dev -w @urbanflet/web-interno    # puerto 5175
```

**URLs**:
- `web-pasajero` (PWA): http://localhost:5173
- `web-conductor` (PWA): http://localhost:5174
- `web-interno` (portal administrativo, todos los CRUD + 9 dashboards
  tácticos): http://localhost:5175
- Backend (FastAPI): http://localhost:8000 (docs en `/docs`)
- Airflow: http://localhost:8080 (usuario `admin` / password `admin`,
  seteado en `airflow-init` de `docker-compose.yml`)
- ClickHouse HTTP: http://localhost:8123
- PocketBase: http://localhost:8090 (superusuario
  `admin@urbanflet.local`, password en `.env` →
  `POCKETBASE_ADMIN_PASSWORD`)
- MongoDB: `localhost:27017` (replica set `rs0`, un solo nodo)

**Gotchas de arranque ya documentadas** (ver también notas de
infraestructura en §3): si `airflow-webserver` no responde tras un `up
-d` normal por un PID file viejo, usar `docker compose up -d
--force-recreate airflow-webserver`; los DAGs nuevos quedan pausados por
defecto (`airflow dags unpause <dag_id>`); si se edita
`analytics/plugins/*.py` y una tarea sigue fallando con comportamiento
viejo, borrar `analytics/plugins/__pycache__` y reiniciar
`airflow-scheduler`/`airflow-webserver`.

### 8.7 Credenciales de demo — un solo lugar, verificadas por login real esta sesión

No existía antes un lugar único con credenciales reales funcionando — la
información estaba dispersa (o de hecho, para varias cuentas nombradas
como `staff-verificacion`, ninguna contraseña en texto plano existía en
ningún archivo del repo, solo el hash en Mongo de sesiones previas). Las 3
cuentas de abajo se confirmaron con una llamada real a `POST
/auth/login` esta sesión (no asumidas):

| Rol(es) | Identificador | Password | Cubre |
|---|---|---|---|
| `pasajero` | `+593987001122` (Pasajera Prueba) | `DemoPasajero123!` | Apps `web-pasajero` — CU-O02/04/08 |
| `conductor` | `+593911223344` (Juan Pérez, con vehículo `PBA-1234` habilitado) | `DemoConductor123!` | App `web-conductor` — CU-O04/05/08/09 |
| `admin_captacion, jefe_mantenimiento, supervisor_cumplimiento, coordinador_flota, coordinador_operaciones, admin_financiero, responsable_plataforma` (los 7 roles tácticos acumulados) | `+593900000001` (`staff-verificacion`) | `VerifDash123!` | `web-interno` completo — las 5 pantallas CRUD WorkPanel (Solicitudes/Mantenimiento/Cumplimiento/Flota/Finanzas, cada una gateada a uno de estos 7 roles) + los 9 dashboards tácticos + el catálogo de Indicadores |

**Nota sobre el pedido original de "4 roles operativos + 7 tácticos"**:
no existen 4 cuentas operativas separadas de las 7 tácticas — la RBAC del
sistema (`backend/src/core/rbac.py::ROLES`, 12 roles en total) hace que
las 5 pantallas CRUD operativas de `web-interno` estén gateadas
exactamente por 5 de los mismos 7 roles "tácticos" (`admin_captacion`,
`jefe_mantenimiento`, `supervisor_cumplimiento`, `coordinador_flota`,
`admin_financiero`) — no hay una separación real de "roles operativos" vs
"roles tácticos" a nivel de cuenta, es la misma cuenta `staff-verificacion`
la que cubre ambos bloques. Los verdaderos 2 roles operativos adicionales,
distintos de los 7 de staff, son `pasajero` y `conductor` (para las apps
externas) — de ahí las 3 filas de la tabla de arriba, no 2 (pasajero +
conductor) + 7 (staff) = 9 cuentas separadas. `gerencia` e
`integracion_externa` son roles válidos en `ROLES` sin cuenta de demo
dedicada — no tienen ninguna pantalla propia en `web-interno` que los
requiera en exclusiva (siempre aparecen en un `$or` con otro rol ya
cubierto).

Estas 3 credenciales quedan como la referencia única y vigente — si una
sesión futura cambia cualquier password, actualizar esta tabla en el mismo
commit, no dejarla desincronizada.

### 8.8 Datos ricos para demo — sembrados esta sesión, todo vía servicios reales

Pedido explícito del usuario: más volumen en todos los dominios (no solo
viajes NYC) para poder evaluar tablas/filtros/paginación/gráficos con
realismo, sin insertar documentos a mano. Los 6 scripts/mecanismos de
abajo pasan por los servicios reales del backend (auditoría write-ahead,
transacciones, efectos secundarios reales) — ninguno hace
`insert_one`/`insert_many` directo salvo donde el propio dominio no tiene
CU operativo que lo respalde (referidos, igual que ya estaba).

- **Solicitudes de conductor**: `backend/scripts/seed_solicitudes_demo.py`
  (nuevo) — 160 vía `captacion.service.crear_solicitud`/`tomar_solicitud`/
  `decidir_solicitud` reales (25 ENVIADA, 20 EN_VERIFICACION, 25 OBSERVADA,
  20 RECHAZADA, 70 APROBADA). Las 70 aprobadas generaron, como efecto
  legítimo de la transacción real de aprobación (no a mano): **70
  vehículos nuevos** en `vehiculos` (Flota) y **140 documentos reales** en
  `documentos` (49 vigente / 43 por vencer / 48 vencido — mezcla real,
  confirmada consultando `fecha_vencimiento`, que se guarda como string
  ISO por `model_dump(mode="json")`, no como BSON Date -- comportamiento
  preexistente del schema, no algo que este script introdujo).
- **Referidos**: `backend/scripts/seed_referidos.py` (ampliado in-place,
  no reemplazado) — los 10 originales se mantienen literales; se agregó
  generación programática de 100 pares adicionales sobre el pool real de
  usuarios (incluye los conductores nuevos de arriba), mismo patrón de
  idempotencia (`_id` determinista + `$setOnInsert`). Total: 110.
- **Órdenes de mantenimiento**:
  `backend/scripts/seed_ordenes_mantenimiento_demo.py` (nuevo) — 130 vía
  `mantenimiento.service.crear_orden`/`marcar_en_taller`/`cerrar_orden`/
  `anular_orden` reales (25 ABIERTA, 20 EN_TALLER, 65 CERRADA, 20
  ANULADA), tipos PREVENTIVA/CORRECTIVA mezclados, sobre el pool de
  vehículos ampliado (75 en total).
- **Bitácora de auditoría**: sin script dedicado — subió de forma natural
  a **1,648 eventos** (23 tipos de acción distintos) como efecto colateral
  real de los 3 scripts de arriba (cada `write_audit_event` real que
  disparan). Superó ampliamente el ≥100 pedido sin necesidad de sembrar
  nada aparte.
- **Liquidaciones**: `backend/scripts/seed_liquidaciones_demo.py`
  (nuevo) — el más complejo de los 6. Hallazgo real que cambió el enfoque:
  `recaudacion.service.generar_liquidaciones()` **no acepta un periodo
  como parámetro** (siempre calcula "la semana ya cerrada respecto a AHORA
  MISMO", no hay scheduler en el stack) y **lee de `movimientos`, no de
  `pagos`** — los 1.24M pagos del dataset NYC nunca generaron movimientos
  (nunca pasaron por `registrar_pago_efectivo`), así que **no hay forma de
  generar liquidaciones reales sobre el dataset NYC**, ni para el periodo
  actual ni para ninguna fecha de 2021. Resuelto generando un lote
  **separado y pequeño** de viajes/pagos NUEVOS (no toca los 1.3M NYC) que
  sí pasan por el flujo real completo — `viajes.service.solicitar_viaje`
  → `service_dispatch.responder_oferta` → `service_ejecucion.
  marcar_en_camino/marcar_llegada/iniciar_viaje` →
  `service_finalizacion.finalizar_viaje` →
  `recaudacion.service.registrar_pago_efectivo` — con el reloj interno de
  esos 6 módulos (`viajes.service`, `service_dispatch`, `service_ejecucion`,
  `service_finalizacion`, `recaudacion.service`, `core.audit`, los únicos
  que llaman `datetime.now(UTC)`) congelado a un instante dentro de cada
  una de 5 semanas pasadas distintas (clase `_RelojCongelado` que
  reemplaza temporalmente `modulo.datetime`, restaurado después — no
  requirió instalar `freezegun`, ni modifica ninguna regla de negocio, solo
  qué instante ve el código real). Resultado real: **80/80 viajes pagados
  reales, 66 liquidaciones nuevas sobre 5 periodos distintos, 40 socios
  distintos**, con los 4 estados reales aplicados vía las funciones reales
  (`aprobar_liquidacion`/`pagar_liquidacion`/`observar_liquidacion`) —
  17 APROBADA, 16 PAGADA, 16 OBSERVADA, resto EMITIDA. Verificado en
  navegador real (`web-interno`, sección Finanzas): tabla de liquidaciones
  con periodos `10/7–17/7`, `17/7–24/7`, `24/7–31/7` mezclados, socios
  reales (`Postulante Demo NNN` + los originales), y la sección "Alertas
  de saldo negativo" mostrando conductores reales con 2+ periodos
  consecutivos en rojo — prueba downstream de que los múltiples periodos
  quedaron correctamente encadenados.
- **Corridas de pipeline / cuarentena**: evaluado, **no hizo falta más**
  — ya había 124 corridas reales repartidas en 7 dominios (38-50 de
  `dag_viajes_core`/`dag_finanzas_gold` de los backfills NYC de esta
  misma sesión). No se disparó ningún backfill adicional para esto.

**Intento fallido, documentado, no reintentar sin razón nueva**: se
intentó enriquecer el gráfico de tendencia compuesto (ClickHouse) de
Captación/Mantenimiento con `airflow dags backfill --reset-dagruns` sobre
~150 días (mismo patrón que funcionó para NYC) para que reflejara el
rango completo de fechas retro-fechadas de `seed_solicitudes_demo.py`/
`seed_ordenes_mantenimiento_demo.py`. **Se topó con un deadlock real**
(`BackfillJob is deadlocked` — choque conocido entre `BackfillJob` y la
tarea `disparar_publicacion_indicadores`, que dispara `dag_publicar_
indicadores` por dentro) tras solo 1/148 días procesados, y
`--reset-dagruns` de paso dejó 6 corridas previas no relacionadas
atascadas en `queued`/`running`. Limpiado sin pérdida de datos (las 6
corridas se resolvieron vía el ORM de Airflow directamente —
`DagRun.state = FAILED/SUCCESS` según correspondía —, sin tocar Mongo ni
ClickHouse; `rpt_conversion_captacion` sigue con datos frescos y
correctos del trigger normal, no corrupto). **Decisión: no reintentar**
— es una mejora cosmética (el gráfico de tendencia solo refleja "hoy",
las tablas simples de Mongo ya muestran el 100% del volumen nuevo
correctamente) que no justifica el riesgo de volver a desestabilizar el
scheduler de estos 2 DAGs de producción.

Suite backend sin regresión tras los 3 scripts nuevos: no se corrió
`pytest` de nuevo después de este bloque específico (los scripts no
tocan código de producción, solo lo invocan) — la última corrida limpia
registrada es la de §8.1 (177 passed, 8 skipped), antes de este bloque.
