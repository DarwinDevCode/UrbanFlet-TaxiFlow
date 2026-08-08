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
| Operaciones/Despacho (`operativo_operaciones_despacho.md`) | CU-O04 (solicitar viaje, A1-A4), CU-O05 (auto-despacho, incl. A1/A2/A3) | Todo el ciclo de vida del viaje es un overlay sobre el mapa persistente — ver §4. **CU-O05 A3 "Reintentar búsqueda" tras SIN_CONDUCTOR SÍ está construido** — `reintentarBusqueda()` en `apps/web-pasajero/src/App.tsx` (reusa origen/destino del viaje agotado, maneja `TRIP_ALREADY_ACTIVE`), confirmado con lectura de código real en la auditoría de nivel estratégico (2026-08-08, `AUDITORIA_NIVEL_ESTRATEGICO.md`, hallazgo H1). Las 2 entradas previas de este archivo (§6 y la nota de auditoría #2 que citaban) estaban desactualizadas — no reabrir este punto sin evidencia nueva |
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

**Piloto de Parquet versionado por corrida (2026-08-08, Fase 2 de
`AUDITORIA_NIVEL_ESTRATEGICO.md` §10, requisito de
`specs/nivel-estrategico/nivel_estrategico.md` §5) — cerrado, solo en
`dag_mantenimiento_gold`, no extendido a los otros 6 DAGs de dominio.**
Nueva tarea `exportar_parquet` (entre `gold` y `metricas`) que escribe 3
archivos Parquet por corrida — uno por etapa Medallion (Bronze crudo,
Silver validado, Gold agregado) — en
`datos/<extraccion|transformacion|carga>/mantenimiento/<fecha_logica>/<lote_id>.parquet`,
tal cual la estructura de carpetas que pide la spec. Implementado como
`medallion.exportar_parquet()` nuevo (reutilizable por cualquier DAG futuro
que quiera el mismo patrón, sin acoplarse a mantenimiento). `lote_id`
(`registrar_inicio_corrida`, ya único por corrida: `dag_id+fecha_logica+uuid
corto`) se reusa tal cual como nombre de archivo — nunca sobrescribe una
corrida anterior, sin necesidad de un segundo identificador de versión.
**Sin dependencias nuevas**: `pandas` (2.1.4) y `pyarrow` (16.1.0) ya venían
instalados en la imagen base `apache/airflow:2.9.3-python3.11` (arrastrados
por `apache-airflow-providers-google`/`snowflake`), confirmado con `pip show`
antes de tocar el Dockerfile — no hizo falta modificar
`_PIP_ADDITIONAL_REQUIREMENTS` ni ninguna imagen. **Nuevo bind-mount**
`./analytics/exports:/opt/airflow/exports` agregado solo a
`airflow-scheduler` en `docker-compose.yml` (LocalExecutor ejecuta las
tareas por `fork()` ahí mismo, `airflow-webserver`/`airflow-init` nunca
corren tareas) — los archivos quedan también en el host en
`analytics/exports/datos/...`, verificables sin entrar al contenedor.
Verificado con una corrida real completa (`airflow dags trigger`, fecha
lógica 2026-08-08): las 6 tareas (las 5 ya existentes + `exportar_parquet`)
terminaron en `success`; los 3 Parquet de esa corrida quedaron escritos (0
filas cada uno, correcto — no hubo órdenes `CERRADA` ese día lógico, pero el
archivo con schema real se escribió igual, no se omitió). Verificado también
contra una fecha con datos reales (2026-08-01, 3 órdenes): Parquet de
`carga` con 8,567 bytes reales, leído de vuelta con `pandas.read_parquet`
dentro del contenedor confirmando 3 filas con columnas y tipos correctos
(`orden_id`, `costo_total`, `cumple_plazo`, etc.). Idempotencia/no-colisión
confirmada re-disparando la misma fecha lógica (`airflow tasks clear` +
recorrida) — quedaron 4 archivos Parquet distintos en la misma carpeta
`2026-08-01/` (uno de la prueba con `tasks test` + 3 de reintentos
automáticos de la segunda corrida real), cada uno con su propio `lote_id`
en el nombre, ninguno sobrescrito. Sin ningún import error nuevo en los
otros 8 DAGs tras el cambio (`airflow dags list-import-errors` limpio,
`airflow dags list` con los 9 DAGs intactos) — el piloto no tocó
`dag_viajes_core`/`dag_finanzas_gold`/`dag_captacion_gold`/
`dag_cumplimiento_gold`/`dag_flota_gold`/`dag_historico_nyc` ni
`dag_publicar_indicadores`. **Recomendación explícita, no extender el piloto
a los 6 DAGs restantes todavía**: el riesgo de I/O que preveía la Sección 12
de la auditoría no se materializó a esta escala (mantenimiento es un dominio
pequeño, milisegundos de escritura por archivo), pero **no se probó a la
escala real de `dag_viajes_core`/`dag_historico_nyc`** (fact_viaje_historico
sola tiene 1.3M+ filas) — escribir un Parquet de ese tamaño por corrida,
encima de un chunk de 20,000 filas por vez, es un escenario de I/O
cualitativamente distinto que este piloto no midió; extender el patrón a
esos 2 DAGs sin medir antes el costo real de esa escala sería repetir el
riesgo que la Sección 12 ya advertía, no algo ya descartado.

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

**Bug corregido en `dag_cumplimiento_gold` (2026-08-08, hallazgo H2 de la
auditoría de nivel estratégico)**: `rpt_documentacion_vigente` llevaba **0
filas desde siempre**, pese a que `documentos` ya tenía 142 registros reales
(§8.8) — no por falta de corridas recientes, sino por 3 bugs encadenados
descubiertos al re-disparar el DAG: (1) `_extraer` filtraba
`documentos.fecha_emision` (guardado como string ISO, no BSON Date, mismo
patrón ya conocido de `fecha_vencimiento`) contra un `datetime` de Python —
Mongo nunca hace match entre tipos BSON distintos, el filtro devolvía 0 filas
en toda corrida histórica; (2) aunque el tipo se arreglara, `documentos` es
un registro de estado (vigencia), no un evento con timestamp de creación —
filtrar por "emitido en las últimas 24h" nunca habría reflejado el universo
completo, corregido extrayendo el snapshot completo en cada corrida (igual
que el tablero de Flota); (3) al llegar por fin datos reales a `_gold`, la
inserción a `fact_cumplimiento_documental` fallaba porque `filas_doc`
incluía la clave `fecha_emision`, columna que esa tabla Gold nunca tuvo
(`fecha_vencimiento` sí) — nunca se había detectado porque `doc_validos`
siempre llegaba vacío por el bug (1). Corregidos los 3 en
`analytics/dags/dag_cumplimiento_gold.py`. Confirmado con corrida real:
`fact_cumplimiento_documental` con 142 filas, `rpt_documentacion_vigente`
con 2 tipos (`LICENCIA_CONDUCIR` 71 registros/57.7% vigente,
`MATRICULA_VEHICULAR` 71 registros/69.0% vigente), `actualizado_en` fresco.

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
   - ~~4. Captación~~ — **cerrado originalmente, con regresión posterior —
     ver nota 2026-08-08 abajo.** Requirió cerrar primero el gap de
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
   - ⚠️ **Regresión detectada 2026-08-08 (hallazgo H3, auditoría de nivel
     estratégico)**: el backfill de arriba dejó `solicitudes` en 0/169 sin
     `canal` (sigue así, verificado). Pero `usuarios` — que tenía 0/23 sin
     `canal` al cerrar este punto — hoy tiene **96/194 (49%) sin `canal`**.
     Causa más probable: las rondas posteriores de siembra de datos ricos
     (§8.8, `seed_solicitudes_demo.py` con 70 conductores/vehículos nuevos,
     `seed_liquidaciones_demo.py`, cuentas de demo de roles nuevos) crearon
     usuarios sin pasar por el flujo que setea `canal`. **Decisión tomada
     (2026-08-08): no reintentar el backfill ahora** — degrada la
     fiabilidad de `rpt_altas_retencion_canal` para casi la mitad de los
     usuarios reales, pero no bloquea nada; se documenta como limitación
     conocida en el futuro Panel de Crecimiento Estratégico (OE1, nivel
     estratégico) en vez de bloquear ese trabajo por esto — mismo criterio
     ya usado con el gap de zona en `viajes`. Ver
     `AUDITORIA_NIVEL_ESTRATEGICO.md` para el detalle completo.
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
   - ✅ **Corrección de documentación (2026-08-08)**: la entrada anterior de
     este punto afirmaba que **CU-O05 A3 "Reintentar búsqueda"** tras
     `SIN_CONDUCTOR` NO estaba construido. Es falso — la auditoría de nivel
     estratégico (`AUDITORIA_NIVEL_ESTRATEGICO.md`, hallazgo H1) confirmó con
     lectura de código real que `reintentarBusqueda()` en
     `apps/web-pasajero/src/App.tsx` sí lo implementa completo (reusa
     origen/destino del viaje agotado, maneja `TRIP_ALREADY_ACTIVE`). Esta
     afirmación llevaba al menos 2 sesiones repitiéndose sin re-verificar
     contra el código — corregido también en la tabla de §3. **CU-O10 A2
     (movimiento `AJUSTE`)** — sigue sin resolver, existen tests
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

**Cobertura completa de los 12 roles de `rbac.py::ROLES`** — ampliada en
una sesión posterior a pedido explícito ("credenciales de cada
usuario/rol que existe en el sistema"). Los 3 roles que quedaban sin
cuenta de demo dedicada (`admin_plataforma`, `gerencia`,
`integracion_externa`) ahora también tienen una, verificada con login
real:

| Rol | Identificador | Password | Nota |
|---|---|---|---|
| `admin_plataforma` | `+593911998822` (cuenta ya existente de sesión previa, "Admin Plataforma QA") | `AdminPlataforma123!` | Ve Flota + Indicadores + 3 dashboards tácticos (Flota/Auditoría/Plataforma) vía los OR-gates de RBAC — confirmado en navegador real |
| `gerencia` | `+593900000010` (`gerencia-demo-01`, cuenta nueva) | `Gerencia123!` | Mismas 3 pantallas tácticas que `admin_plataforma` vía OR-gate (`gerencia` aparece en el `$or` de Auditoría/Plataforma), sin pantalla propia exclusiva |
| `integracion_externa` | `+593900000011` (`integracion-externa-demo-01`, cuenta nueva) | `Integracion123!` | Login funciona, pero no tiene ninguna pantalla de `web-interno` gateada a este rol — es un rol pensado para acceso de API/máquina-a-máquina, no para el portal |

Con esto, los 12 roles del sistema tienen credenciales reales verificadas
— 3 cuentas cubren los 9 roles "principales" (§8.7 arriba) + 3 cuentas
individuales para estos 3 roles residuales.

**Rol 13 agregado en sesión posterior**: `admin_sistema` (ver §9, módulo de
Administración del Sistema) — separado de `admin_plataforma` por principio
de mínimo privilegio, no reutiliza ninguna de las cuentas de arriba.

| Rol | Identificador | Password | Nota |
|---|---|---|---|
| `admin_sistema` | `+593900000099` (`Admin Sistema QA`) | `AdminSistema123!` | `web-interno` → "Administración → Usuarios" y "→ Políticas de autenticación" (Módulo 1, IAM) — único rol con acceso, sin OR-gate con ningún otro |

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

## 9. Módulo de Administración del Sistema — en construcción activa

Nuevo paquete transversal (`specs/specs-administrativas/admin_sistema.md`,
8 módulos: IAM, Configuración General, Catálogos, Integraciones Externas,
Monitoreo, Auditoría y Seguridad, Respaldos y Continuidad, Mantenimiento y
Gobernanza de Datos) — infraestructura de gobierno del sistema mismo, no
un caso de uso de negocio de la cooperativa. Plan de trabajo completo,
estimaciones de esfuerzo y los 6 recortes de alcance ya aprobados por el
usuario viven en [PLAN_ADMIN_SISTEMA.md](PLAN_ADMIN_SISTEMA.md) — ese
archivo es la fuente de verdad de qué falta, no lo dupliques aquí. Esta
sección solo resume decisiones de arquitectura y estado por si una sesión
sin el plan a mano necesita contexto rápido.

**Decisión de arquitectura (confirmada explícitamente por el usuario antes
de tocar código)**: se creó el rol nuevo `admin_sistema`
(`backend/src/core/rbac.py::ROLES`), **separado** de `admin_plataforma`
(que administra pipeline/indicadores de negocio, CU-T14/OT8.1) — principio
de mínimo privilegio ya declarado en `operativo_cumplimiento.md`. Todos los
endpoints de los 8 módulos se gatean exclusivamente a `admin_sistema`
(nunca combinado con otro rol vía OR-gate, a diferencia de la mayoría de
los demás routers del proyecto) salvo donde la spec pide explícitamente
que `gerencia` también vea algo — en la práctica, terminó siendo un único
caso real: Módulo 7.2 (plan de continuidad), el único OR-gate
`admin_sistema`/`gerencia` de todo el bloque. Módulo 8.2 (gobernanza de
datos) NO lo necesitó pese a una nota de planificación temprana que lo
sugería — su texto de spec real nunca menciona `gerencia`, confirmado al
construirlo (ver §17).

**Módulo 1 (IAM) — cerrado y verificado.** Gestión de cuentas de personal
interno, roles, políticas de contraseña/bloqueo configurables y sesiones
activas revocables. Detalle completo (qué se construyó, hallazgos reales,
verificación en navegador) en
[PLAN_ADMIN_SISTEMA.md §7](PLAN_ADMIN_SISTEMA.md). Piezas nuevas más
relevantes para el resto del proyecto: `backend/src/core/sessions.py`
(primer registro de sesiones activas en Redis del proyecto — JWT era
puramente stateless hasta ahora), `POST /auth/cambiar-password` nuevo, y
`AuthProvider` (shared-ui) ganó `debeCambiarPassword`/`cambiarPassword`
genéricos (sin wirear en `web-pasajero`/`web-conductor` todavía). Cuenta de
demo: ver tabla de credenciales en §8.7.

**Módulo 2 (Configuración General) — cerrado y verificado.** Parámetros
globales del sistema (radios de despacho, expiración de oferta, idioma,
zona horaria — versionados, mismo patrón que tarifa/comisión) y feature
flags (activar/desactivar por % o rol). Detalle completo en
[PLAN_ADMIN_SISTEMA.md §8](PLAN_ADMIN_SISTEMA.md). Pieza más relevante
para el resto del proyecto: `viajes/service_dispatch.py` ya no tiene
`RADIOS_M`/`OFERTA_EXPIRA_SEGUNDOS` como constantes fijas — se leen en
caliente de `configuracion.service`, con los mismos valores como fallback
(`configuracion/service.py::DEFAULTS`) si nunca se publicó una versión.
`core/feature_flags.py::is_enabled()` es un helper genérico nuevo, todavía
sin ningún consumidor real (por diseño — ver alcance de 2.2 en el plan).

**Módulo 6.1 (Auditoría de cambios administrativos) — cerrado y
verificado.** Vista filtrada de la misma bitácora de CU-O17, sin segundo
almacén — reutiliza `GET /auditoria/eventos`, ampliado para aceptar varias
`accion` a la vez. Detalle completo en
[PLAN_ADMIN_SISTEMA.md §9](PLAN_ADMIN_SISTEMA.md). Pieza más relevante
para el resto del proyecto: `EventoAuditoriaOut` ahora expone
`datos_previos`/`datos_posteriores` (ya existían en Mongo desde CU-O17,
nunca se habían leído por API) — cualquier pantalla futura puede
mostrarlos sin cambios de backend. Se corrigió de paso un cruce real:
Módulo 2.1 reutilizaba la acción de auditoría de tarifa/comisión
(`PARAMETRO_CAMBIO`) para los parámetros de sistema — ahora tiene su
propia acción (`PARAMETRO_SISTEMA_CAMBIO`) para no mezclarse en el filtro
administrativo.

**Módulo 3 (Catálogos y Parámetros de Negocio) — cerrado y verificado.**
Zonas de despacho (CRUD completo, extendiendo el router `parametros/`
ya existente en vez de duplicarlo — nueva dependencia
`_puede_gestionar_zonas` que suma `admin_sistema` sin darle acceso a
tarifa/comisión) + tipos de documento y motivos de cancelación/incidencia
(módulo nuevo `catalogos/`, solo activar/desactivar, sin DELETE — ambos
alimentan campos hoy de texto libre sin FK real, confirmado con
investigación de código antes de construir). Detalle completo en
[PLAN_ADMIN_SISTEMA.md §10](PLAN_ADMIN_SISTEMA.md). Hallazgo real de
paso: `viajes.zona_origen_id`/`zona_destino_id` existen en el schema pero
nunca se resuelven (siempre `None`) — el guard "no eliminar zona en uso"
es código real y correcto, pero no bloquea nada todavía en la práctica.

**Módulo 8.1 (Versión/Despliegue) — cerrado y verificado.** `GET
/sistema/version` (backend + 3 frontends, valores mantenidos a mano en
sync con `pyproject.toml`/`package.json`, sin introspección automática) +
`GET`/`POST /sistema/despliegues` (registro manual, alcance recortado
aprobado — no hay CI/CD real en el proyecto). Detalle completo en
[PLAN_ADMIN_SISTEMA.md §11](PLAN_ADMIN_SISTEMA.md).

**Corrección estructural post-8.1 (§12 del plan)**: el mirror de
`ACCIONES_ADMINISTRATIVAS` en `AuditoriaAdmin.tsx` se había desincronizado
del backend (Módulo 3 agregó 3 acciones nuevas que quedaron invisibles en
el filtro, sin que ningún test lo detectara). A pedido del usuario, se
eliminó la causa raíz en vez de solo agregar un test que la detecte:
`GET /auditoria/acciones-administrativas` (nuevo) expone
`core/audit.py::ACCIONES_ADMINISTRATIVAS` directamente — `AuditoriaAdmin.tsx`
ya no declara ningún array hardcodeado, lo consume de ahí. **No queda
ningún archivo en `apps/web-interno` que deba tocarse a mano cuando un
módulo futuro (4/5/6.2/6.3/7/8.2) agregue una acción administrativa
nueva** — a diferencia de `usuarios/permisos_matriz.py` y `ROLES_STAFF`
(Módulo 1.2), que siguen siendo mirrors manuales reales por decisión
explícita ya aprobada (alcance recortado, no un descuido).

**Módulo 6.2 (Políticas de seguridad) — cerrado y verificado.** TTL de
access/refresh token y umbrales de los 3 mecanismos de rate limiting que
ya existían (login, ya cubierto por Módulo 1.3; refresh y denegaciones
RBAC, cubiertos aquí) dejaron de ser constantes fijas. Detalle completo en
[PLAN_ADMIN_SISTEMA.md §13](PLAN_ADMIN_SISTEMA.md). Piezas más relevantes
para el resto del proyecto: `core/security.py::create_token` acepta TTL
opcionales; `auth/service.py::_emitir_tokens` cambió de firma (ahora
requiere `db`); `core/rbac.py` importa `seguridad.service` de forma
perezosa (dentro de la función, no a nivel de módulo) para no acoplar el
archivo más foundational del proyecto a un dominio de negocio. Hallazgo
real corregido de paso: `core/sessions.py` (registro de sesiones activas,
Módulo 1.4) seguía leyendo el TTL fijo de `Settings` en vez de la política
vigente — ahora sigue al mismo TTL configurado que el token real.
Verificado con un login real decodificando el JWT emitido (TTL de 420s
para una política de 7 minutos, no los 900s por defecto).

**Módulo 6.3 (Alertas y notificaciones del sistema) — cerrado y
verificado.** Detalle completo en
[PLAN_ADMIN_SISTEMA.md §14](PLAN_ADMIN_SISTEMA.md). Hallazgo real más
relevante: de las 3 alertas que la spec asume que "el sistema ya genera",
solo las denegaciones RBAC (5 en 10 min) estaban realmente conectadas a
una notificación — el spoofing GPS solo se auditaba, nunca notificaba a
nadie, y se corrigió (`flota/service.py::reportar_posicion` ahora dispara
una alerta real vía `notificaciones.service.disparar_alerta`). "Corrida de
pipeline fallida" es enteramente del lado de Airflow (sin webhook al
backend) y queda solo configurable, sin disparo real, documentado como tal
en vez de simulado. `canal` quedó limitado a `web_push` en el schema
(único canal con entrega real en el codebase — no hay envío de correo en
ningún lado) en vez de aceptar "correo"/"ambos" como sugiere la spec.

**Módulo 4 (Integraciones Externas) — cerrado y verificado.** CRUD real de
credenciales de integración (secreto mostrado una sola vez, hash bcrypt
irreversible, revocación idempotente-protegida con 409 en el segundo
intento) + estado/rotación de servicios externos. Detalle completo en
[PLAN_ADMIN_SISTEMA.md §15](PLAN_ADMIN_SISTEMA.md). Confirmado antes de
construir, a pedido explícito del usuario: `GET /ext/v1/...` que la spec
asumía existente **no existe en el código** — el CRUD se construyó sin el
middleware de validación contra ese endpoint, `usos_registrados` queda en
0 con ese motivo explícito. Pieza más relevante para el resto del
proyecto: `viajes/service.py::estimar_ruta` ya no lee la key de Google
Maps solo de `Settings` — ahora la resuelve vía
`integraciones/service.py::obtener_google_maps_api_key(db)`, que consulta
un override en `servicios_externos_config` (Mongo) antes que la variable
de entorno. Esto permite rotar la key desde la UI con efecto inmediato sin
reiniciar el backend — verificado en navegador real inspeccionando la
petición saliente real a `maps.googleapis.com` en el log del contenedor,
confirmando que llevaba la key recién rotada, no la del `.env`.

**Módulo 5 (Monitoreo y Observabilidad) — cerrado y verificado.** Panel de
estado de infraestructura (backend, Mongo, Redis, ClickHouse, Airflow) con
ping real y latencia medida, más umbrales configurables que colorean cada
tarjeta al abrir o actualizar el panel. Detalle completo en
[PLAN_ADMIN_SISTEMA.md §16](PLAN_ADMIN_SISTEMA.md). Alcance confirmado
(re-aprobado explícitamente): **evaluación bajo demanda, no vigilancia
continua** — no hay proceso de background que sondee umbrales ni dispare
alertas push automáticas (no hay worker/cron apto en este stack sin
agregar infraestructura nueva tipo Celery beat). Pieza más relevante para
el resto del proyecto: `sistema/service.py` extiende el módulo de Módulo
8.1 (no crea uno nuevo) con `obtener_salud`/`obtener_umbrales`/
`actualizar_umbral`; `Settings.airflow_url` nuevo apunta al hostname
interno `airflow-webserver:8080` de docker-compose. Verificado en
navegador real bajando el umbral de Mongo y confirmando con
`getComputedStyle` que la tarjeta pasó de verde a rojo (`--status-critical`
real) mientras las otras 4 se mantuvieron en verde — el color reacciona al
umbral real, no a un estado fijo.

**Módulo 8.2 (Gobernanza de datos) — cerrado y verificado.** Anonimización
irreversible de una cuenta (derechos ARCO/LOPDP, CU-O17 A2) con doble
confirmación real (`Literal["ANONIMIZAR"]` en el schema, no solo del lado
del cliente) + política de retención de solo lectura por tipo de dato.
Detalle completo en [PLAN_ADMIN_SISTEMA.md §17](PLAN_ADMIN_SISTEMA.md).
Decisión de diseño clave: `bitacora.actor_id` ya era un UUID opaco desde
siempre (nunca el dato personal en sí), así que "seudonimizar el
identificador en la bitácora" (CU-O17 A2) se cumple sin tocar ningún
evento ya escrito — lo que sí se diseñó con cuidado fue que el propio
evento `USUARIO_ANONIMIZACION` **nunca** lleva el nombre/teléfono/correo
real que se está purgando (`bitacora` es insert-only y permanente; grabar
ahí el dato purgado derrotaría el propósito de la anonimización). El TTL
de `posiciones` en la política de retención se lee real de
`db.posiciones.index_information()`, nunca hardcodeado como texto. Bug
real encontrado y corregido de paso en `shared-ui/TextField.tsx`: el `id`
autogenerado a partir del label no sanitizaba comillas/puntuación,
generando un `id` HTML inválido para labels como `Escribe "ANONIMIZAR"
para confirmar` — corregido de forma general (`.replace(/[^a-z0-9-]/g,
"")`), verificado sin romper build/lint/test en ninguna de las 3 apps.

**Módulo 7 (Respaldos y Continuidad) — cerrado y verificado. Con este
cierre, los 8 módulos del paquete de administración del sistema quedan
completos.** Detalle completo en
[PLAN_ADMIN_SISTEMA.md §18](PLAN_ADMIN_SISTEMA.md). El recorte de alcance
más grande del documento, repasado en detalle con el usuario antes de
construir, con un ajuste real: verificado que la imagen del backend no
tiene `mongodump`/`mongorestore`/`clickhouse-client` instalados —
**aprobada explícitamente la Opción B**: exportación vía los drivers que
el backend ya usa en producción (`motor`/`bson.json_util` para Mongo,
`clickhouse_connect`/pickle para ClickHouse) en vez de instalar binarios
nuevos y reconstruir la imagen. Alcance de qué se respalda decidido con
datos reales del entorno: Mongo respalda **todas** las colecciones de
negocio (incluida `bitacora`); ClickHouse respalda solo las tablas
`rpt_*` + referencia — excluye deliberadamente `bronze_*`/`fact_*`/
`cuarentena_*` (en este entorno ya suman más de 6M de filas, 100%
re-derivables re-ejecutando los DAGs de Airflow, no son la fuente de
verdad). La restauración de prueba tiene la base de destino
**hardcodeada en el código** (`urbanflet_restore_test`/
`urbanflet_gold_restore_test`) — nunca acepta un nombre de base del
cliente, así que "nunca toca producción" es una garantía de código, no
solo de la UI. Cifrado en reposo: no implementado, documentado
explícitamente. Bug real encontrado y corregido (afecta producción, no
solo tests): Mongo devuelve `datetime` naive en UTC al leer, restar
contra un `datetime.now(UTC)` aware reventaba con `TypeError` — cada
respaldo real fallaba silenciosamente a `estado="error"` hasta el fix.
Verificado con un respaldo real completo contra los ~2.6M documentos
reales del entorno (Mongo 78.5s/2.4GB, ClickHouse 0.09s/529KB), hash
verificado dos veces (API + navegador), y una restauración real completa
a las bases de prueba aisladas con conteos exactos confirmados por
consulta directa — y confirmando que las bases reales no se movieron ni
un documento.

**Ronda de usabilidad post-cierre (2026-08-07) — en curso.** Tras probar
personalmente los 8 módulos, el usuario pidió 7 mejoras transversales de
usabilidad/automatización ("reducir el trabajo manual del administrador y
evitar errores humanos, no solo exponer campos editables"), aplicadas al
módulo completo de administración (algunas también auditadas contra el
resto del sistema). Detalle completo por punto en
[PLAN_ADMIN_SISTEMA.md §19+](PLAN_ADMIN_SISTEMA.md). Estado:

- ✅ **P1 — Manejo de errores transversal**: handler global nuevo
  (`backend/src/core/validation.py`) traduce los 422 de Pydantic a mensajes
  en español, uno por campo — antes esos errores eran completamente
  silenciosos en el frontend (solo aparecían en la consola del navegador).
  `ApiError` (shared-ui) ahora expone `fieldErrors`; nuevo helper
  `fieldError(error, campo)` + `hint`/`rangeHint` en `TextField` para
  mostrar el límite válido junto al campo antes de enviar. Aplicado a los
  formularios de Administración con campos numéricos/validados
  (`PoliticasAuth`, `PoliticasSeguridad`, `ParametrosGlobales`,
  `Monitoreo`).
- ✅ **P2 — Selects para valores finitos**: `idioma`/`zona_horaria` en
  Parámetros Globales pasaron de texto libre a `Select` con opciones
  curadas (`América/Guayaquil` por defecto). Backend se dejó permisivo
  (`str`, sin `Literal`) porque no existe ningún consumidor real de
  `idioma` en el código — confirmado con grep antes de decidir no forzarlo
  a nivel de esquema.
- ✅ **P3 — Catálogo `talleres` + validación de `tipos_documento` en
  Captación** — cerrado, ver detalle en PLAN_ADMIN_SISTEMA.md §19. Nuevo
  catálogo (mismo patrón que `tipos_documento`/`motivos_cancelacion`, solo
  activar/desactivar) + `captacion/service.py::crear_solicitud` ahora
  rechaza con 422 `TIPO_DOCUMENTO_INVALIDO` cualquier `documentos[].tipo`
  que no exista o esté inactivo en el catálogo — antes era texto 100%
  libre sin ninguna validación. **No se tocó ninguna máquina de estado**
  (confirmado explícitamente con el usuario antes de construir). `canal`
  (dimensión de captación) quedó fuera de este punto a propósito, para una
  sesión aparte.
- ✅ **P4 — Modo solo-lectura por defecto**: patrón nuevo reutilizable
  (`apps/shared-ui/src/components/ReadOnlyGate.tsx` — hook
  `useReadOnlyGate()` + componente `<ReadOnlyActions>`) aplicado a las 3
  pantallas de configuración sensible (`PoliticasAuth`, `PoliticasSeguridad`,
  `ParametrosGlobales`): campos bloqueados al entrar, botón "Editar"
  explícito para desbloquear, se re-bloquean al guardar/cancelar.
  `VersionSistema.tsx` quedó fuera a propósito — es un log de registro
  append-only, no configuración editable en vivo.
- ✅ **P5 — Selector real de usuarios**: `UserPicker` nuevo
  (`apps/shared-ui/src/components/UserPicker.tsx`) — busca por nombre/rol/
  correo, multi-select, guarda solo IDs pero siempre muestra nombres
  legibles. Reemplazó el campo de texto libre de IDs crudos en
  `ConfiguracionAlertas.tsx` (destinatarios adicionales de alertas).
- ✅ **P6 — Monitoreo: indicadores + histórico + auto-refresco** — cerrado,
  ver detalle en PLAN_ADMIN_SISTEMA.md §20. Nuevos `GET /sistema/indicadores`
  (Mongo vía `serverStatus`/`dbStats`, Redis vía `INFO`, ClickHouse vía
  `system.metrics`/`system.asynchronous_metrics` — sin Airflow por ahora,
  degradan a "no disponible" sin propagar el error real, mismo patrón que
  el panel de salud original) y `GET /sistema/historial-latencia`
  (`historial_monitoreo`, TTL de 7 días, un snapshot por componente en cada
  consulta real del panel — sin worker/cron nuevo). Frontend:
  auto-refresco de 20s con pausa manual, tarjetas de indicadores
  adicionales por motor, y gráfico de tendencia de latencia (`TrendLineChart`
  ya existente). **Bug real encontrado y corregido en navegador**: el
  metric name inicial de ClickHouse (`MemoryTracking`) no existe en la
  versión real del stack (24.x) — corregido a `MemoryResident`, confirmado
  con `clickhouse-client` directo.
- ✅ **P7 — Gestión de conductores/pasajeros en Usuarios**: confirmado que
  el formulario de creación NO debe ofrecer estos 2 roles (correcto tal
  cual, por CU-O01/CU-O02 de autorregistro) — pero ahora son visibles y
  gestionables en el listado de `Usuarios.tsx` (filtro por rol, detalle,
  suspender/reactivar/dar de baja, sesiones), con sus roles mostrados en
  modo solo-lectura (`title` explicando por qué, mismo patrón de tooltip
  ya usado en el resto de pantallas WorkPanel) en vez de editables.

**Con esto, los 7 puntos de la ronda de usabilidad post-cierre
(2026-08-07) quedan completos.**

## 10. Funcionalidades complementarias de UX — cerrado (los 7 puntos completos)

Nuevo paquete transversal (`specs/specs-administrativas/ux_complementaria.md`,
4 secciones: Pasajero, Conductor, Personal interno, Transversal) — cierra
brechas frente a una app de transporte comercial real (perfil propio,
ajustes, notificaciones in-app, historial global, direcciones favoritas,
compartir viaje, programar viaje). Plan de trabajo completo, las 3
decisiones aprobadas (D1/D2/D3) y el desglose de tareas por funcionalidad
viven en [PLAN_UX_COMPLEMENTARIA.md](PLAN_UX_COMPLEMENTARIA.md) — esa es la
fuente de verdad de qué falta, no lo dupliques aquí. Esta sección solo
resume decisiones de arquitectura y estado.

**Hallazgo real de la Fase 0 (verificación de la spec contra el código)**:
la spec asumía que el registro de pasajero/conductor usa OTP para
reverificar un teléfono nuevo — **ya no existe** ningún mecanismo de OTP en
el sistema (el login migró a usuario+contraseña, ver §4 arriba) ni
infraestructura de envío de SMS/correo. Decisión D1 (aprobada): editar el
propio contacto exige la contraseña actual en vez de OTP, mismo nivel de
exigencia que ya tenía `POST /auth/cambiar-password`.

**Perfil propio editable (1.3/2.2/3.1) — cerrado y verificado.** Nuevo
dominio backend `perfil/` (autoservicio: `GET`/`PATCH /perfil`, `GET`/
`DELETE /perfil/sesiones/{jti}`), separado de `usuarios/` (exclusivamente
administrativo, Módulo 1 de admin_sistema) y de `auth/` (tokens/
credenciales). Reutiliza `usuarios/service.py::editar_usuario` (ahora con
un parámetro `accion` opcional, default `USUARIO_EDICION`, para que
`perfil/service.py` pueda pasar la acción de auditoría nueva
`PERFIL_EDICION` sin duplicar la lógica de unicidad de teléfono/correo) y
`core/sessions.py` tal cual. Frontend: componente único `PerfilPropio`
(nuevo en `shared-ui`) reutilizado por las 3 apps — "Mi perfil" en
pasajero/conductor, "Mi cuenta" en `web-interno` (visible para los 13
roles vía un sentinel `ROL_CUALQUIERA = "*"`, agregado al final de
`SECCIONES` a propósito para no convertirse en la sección por defecto de
ningún rol ya existente). Foto de perfil del conductor (2.2): campo de URL
en `usuarios.conductor.foto_url` (mismo patrón `url_objeto` ya usado por
documentos de captación, sin upload propio — no existe esa infraestructura
en el backend), propagada a `ViajeOut.conductor_foto_url` para que el
pasajero la vea al ser asignado (CU-O05 P5). Nunca expone `roles` en el
schema de edición — un usuario no puede cambiar su propio rol desde aquí.
Verificado en navegador real en las 3 apps con cuentas reales (login real,
edición real con contraseña correcta/incorrecta, evento `PERFIL_EDICION`
confirmado en Mongo, sesiones activas reales con IP/user-agent reales).
Backend 282/282 tests + ruff limpio (subió de 274); frontend build/lint/
test limpios en las 3 apps + `shared-ui` lint (21 tests en `web-interno`,
6 en `web-pasajero`, 4 en `web-conductor`).

**Ajustes básicos + Centro de ayuda (1.4/2.3/3.2/4.1) — cerrado y
verificado.** Nuevo dominio backend `preferencias/` (documento único por
cuenta en `preferencias_usuario`, sin auditoría — son ajustes de interfaz,
no acciones de seguridad). Frontend: 2 componentes nuevos en `shared-ui`
reutilizados por las 3 apps — `AjustesPropios` (tema, densidad de tablas
solo en `web-interno`, preferencias de turno solo en `web-conductor`) y
`CentroAyuda` (FAQ + contacto, distinto por app). **Tema oscuro real**:
paleta completa nueva en `tokens.css` (`:root[data-theme="dark"]`,
recalibrando color/estado/gráficos para contraste sobre fondo oscuro) +
`theme.ts` (aplicación síncrona en `main.tsx` antes del primer render, para
no parpadear en claro). **Densidad de tablas**: implementada vía variables
CSS (`--table-cell-padding-y/x`, mecanismo `densidad.ts` idéntico a
`theme.ts`) en vez de una prop nueva en `DataTable` — una variable global
aplica a las ~15 pantallas con tabla sin tocar ninguna, ajuste real sobre
el diseño original del plan. **Centro de ayuda**: implementado como nav
item más (no como ícono flotante en el header, que hubiera exigido un
popover nuevo desde cero) — mismo patrón que "Mi perfil"/"Ajustes", sigue
siendo un clic desde cualquier pantalla. Contacto con **placeholder
documentado** (`soporte@urbanfleet.example` / `+593900000000`) — decisión
final confirmada por el usuario al cierre de todo el bloque de UX
complementaria (§10 abajo): UrbanFleet es un proyecto académico, no una
cooperativa real operando, así que no existe ningún dato de contacto real
que reemplazar — el placeholder se queda tal cual, permanentemente, no es
un TODO pendiente.
Verificado en navegador real: tema oscuro confirmado con `getComputedStyle`
(`rgb(15, 17, 21)`), densidad confirmada sobre una celda real de la tabla
de Usuarios (8px→3px), preferencias de turno guardadas de verdad en Mongo
en `web-conductor`. Backend 288/288 tests + ruff limpio (subió de 282);
frontend build/lint/test limpios en las 3 apps + `shared-ui` lint.

**Centro de notificaciones in-app + cierre de push por categoría (4.2/1.4)
— cerrado y verificado.** `NotificationService.notify_user()`
(`notificaciones/service.py`) ahora persiste SIEMPRE en la nueva colección
`notificaciones_usuario` (TTL 30 días) antes de intentar la entrega en
vivo — un solo punto de cambio, ningún call site existente tocado.
Taxonomía de categorías (`captacion`, `cumplimiento`, `mantenimiento`,
`viaje`, `seguridad` — esta última nunca configurable por el usuario) +
eventos nuevos de ciclo de vida del viaje agregados junto al
`broadcast_channel` ya existente (`VIAJE_ASIGNADO`, `CONDUCTOR_EN_CAMINO`,
`CONDUCTOR_LLEGO`, `VIAJE_INICIADO`, `VIAJE_CANCELADO_CONDUCTOR`,
`VIAJE_FINALIZADO`) en `router_dispatch.py`/`router_ejecucion.py`/
`router_finalizacion.py`. Frontend: `NotificacionesBell` (nuevo en
`shared-ui`, primer consumidor real del slot `AppShell.headerActions`) con
contador de no leídas y panel desplegable, en las 3 apps; toggles de push
por categoría agregados a `AjustesPropios`. **Bug real encontrado y
corregido**: el `aria-label` de la campana colisionaba con el nombre
accesible del nav item "Notificaciones" ya existente en `web-interno`
(Módulo 6.3) — corregido a "Bandeja de notificaciones". Verificado en
navegador real: una orden de mantenimiento real creada contra el vehículo
del conductor demo generó una notificación real, visible como "🔔1" al
loguearse como ese conductor, marcada como leída con un `PATCH` real (200)
y el contador volviendo a 0; toggle de categoría "Estado del viaje"
confirmado en Mongo. Backend 296/296 tests + ruff limpio (subió de 288);
frontend build/lint/test limpios en las 3 apps + `shared-ui` lint.

**Historial global de viajes (3.3) — cerrado y verificado.** Nuevo
`listar_historial_global` en `viajes/service_historial.py` (mismo shape
que `listar_historial` de CU-O14, sin fijar `pasajero_id`/`conductor_id`
al actor) + `GET /viajes/historial-global` (`router_trips.py`, gateado a
`coordinador_operaciones`/`supervisor_cumplimiento`/`gerencia`/
`admin_sistema`). Reutiliza `to_out()`/`HistorialOut`/
`enriquecer_con_pasajero` ya existentes — sin schema ni enriquecimiento
nuevo. Sin filtro de zona (gap ya conocido, `zona_origen_id`/
`zona_destino_id` nunca se resuelven). Frontend: nuevo work panel
"Historial de viajes" en `web-interno`, patrón WorkPanel estándar,
agregado a `SECCIONES` en un grupo propio ("Historial") **al final de la
lista** — mismo motivo que "Mi cuenta" (no debe volverse la sección por
defecto de ningún rol). **Bug real encontrado y corregido durante los
tests**: la primera versión lo insertó antes del grupo "Administración",
lo que desplazó la sección por defecto de `admin_sistema` de "Usuarios" a
"Historial de viajes" y rompió 4 tests preexistentes sin relación
aparente — mismo patrón de bug ya visto (y corregido) al agregar "Mi
cuenta". Verificado en navegador real contra el stack completo (tras un
reinicio real de Docker Desktop a mitad de sesión): 1,334,885 viajes
históricos reales cargados con paginación real, búsqueda por texto
("Conductor Prueba" → 267,014 resultados reales), detalle completo de un
viaje real. Backend 302/302 tests + ruff limpio (subió de 296); frontend
build/lint/test limpios en las 3 apps + `shared-ui` lint.

**Direcciones favoritas (1.1) — cerrado y verificado.** Nuevo dominio
backend `direcciones/` (exclusivo `pasajero`), colección
`direcciones_favoritas` con límite de 10 por cuenta (409 real al superarlo)
y purga automática al anonimizar una cuenta (`usuarios/service.py::
anonimizar_usuario` ahora también la limpia). Frontend en `web-pasajero`:
chips de acceso rápido (Casa/Trabajo/Otro) sobre el campo de destino en el
flujo de solicitud — un toque fija el destino sin geocodificar, ya viene
con lat/lon guardados. **Ajuste real sobre el diseño del plan**: en vez de
un formulario de alta con lat/lon a mano, se agregó un botón "☆ Guardar
como favorita" junto al destino ya elegido en el mapa — reutiliza las
coordenadas que el flujo de solicitud ya resolvió, evita pedirle al
pasajero un dato que no puede dar fácilmente sin un mapa. Gestión (ver/
eliminar) integrada en "Mi perfil" vía el slot `extra` de `PerfilPropio`.
Verificado en navegador real con la cuenta demo de pasajero: crear/listar/
eliminar direcciones reales confirmado contra Mongo, y el flujo completo
de seleccionar un chip + guardar una nueva favorita desde la pantalla de
viaje, ambos con llamadas reales (200/201/204). Backend 309/309 tests +
ruff limpio (subió de 302); frontend build/lint/test limpios en las 3
apps + `shared-ui` lint.

**Compartir viaje en tiempo real (1.2) — cerrado y verificado.** Enlace de
solo lectura, sin cuenta, mientras el viaje está `EN_CAMINO`/`EN_CURSO`.
Diseño anti-enumeración de tokens aprobado explícitamente antes de
construir: `secrets.token_urlsafe(32)` (256 bits, mismo generador que
`integraciones/service.py`), un único 404 genérico sin distinguir la causa
(mismo criterio que el login), rate limiting de 20 fallos/15min por IP
reutilizando el patrón de `_registrar_fallo_login`. Nuevo
`POST /viajes/activo/compartir` (autenticado, pasajero, idempotente
mientras el token siga vigente) + primer endpoint público del proyecto sin
`Depends(get_current_actor)` fuera de auth (`GET
/publico/viajes-compartidos/{token}`, `viajes/router_publico.py`),
documentado como patrón nuevo. El token se invalida explícitamente (no
solo por el techo de 4h, `TECHO_EXPIRACION_HORAS`) al finalizar el viaje y
al cancelarlo por conductor — en este segundo caso porque el viaje puede
terminar reasignado a OTRO conductor y un token viejo no debe seguir
mostrando esa posición nueva sin que el pasajero lo vuelva a compartir.
Acción de auditoría nueva `VIAJE_COMPARTIR_ACTIVADO` (write-ahead),
deliberadamente fuera de `ACCIONES_ADMINISTRATIVAS` (autoservicio de
pasajero, no acción de `admin_sistema`). Frontend: `RideMap` ganó el prop
`soloLectura` (suprime el botón de ubicación y los clics de "elegir
destino"); página pública nueva `VistaCompartida` sin usar ningún router
(el proyecto no tiene uno) — un chequeo de `window.location.pathname`
contra `/^\/compartido\/(.+)$/` al inicio de `App()` en `web-pasajero`,
primera ruta pública real de las 3 apps, con polling cada 8s. Bug real
encontrado y corregido en la prueba: comparar el `expira_en` naive leído
de Mongo contra un `datetime.now(UTC)` aware reventaba con `TypeError` en
el chequeo de idempotencia — corregido con `como_utc()` (mismo helper ya
usado en el resto del proyecto para este problema conocido de PyMongo).
Verificado en navegador real: viaje real llevado hasta `EN_CAMINO`
(cuentas demo pasajero/conductor), botón "Compartir viaje" generó el
enlace real, abierto en una pestaña nueva sin sesión — 200 real sin ningún
header de autorización, datos del conductor/vehículo correctos, mapa sin
botón "Ir a mi ubicación". Un token inventado mostró el mensaje genérico;
el mismo enlace real devolvió ese mismo 404 genérico tras finalizar el
viaje por el flujo completo del conductor — confirmado en Mongo que
ambos campos de token quedan ausentes del documento y que el evento de
bitácora real existe con actor/rol/expiración correctos. Backend 317/317
tests + ruff limpio (subió de 309); frontend build/lint/test limpios en
`web-pasajero` (9/9) + `shared-ui` lint. Detalle completo en
[PLAN_UX_COMPLEMENTARIA.md §8](PLAN_UX_COMPLEMENTARIA.md).

**Programar un viaje (1.5) — cerrado y verificado. Con este cierre, los 7
puntos del bloque de UX complementaria quedan completos.** Enfoque D2 ya
aprobado: nuevo estado `PROGRAMADO` en `EstadoViaje` + disparo diferido vía
Airflow + HTTP interno. `solicitar_viaje` con `ts_programado` (ventana
15min-7días, `TS_PROGRAMADO_INVALIDO` fuera de rango) crea el viaje en
`PROGRAMADO` sin disparar despacho; `disparar_viaje_programado` (nuevo)
transiciona a `SOLICITADO` actualizando `ts_solicitud` a AHORA (no a la
hora de creación — evita que `rpt_tiempo_asignacion`/`rpt_tasa_cancelacion`
mezclen "cuándo se programó" con "cuándo entró a la cola real") y reusa
`avanzar_despacho` tal cual, sin duplicar lógica de CU-O05. Sin conductor a
la hora programada → `SIN_CONDUCTOR`, mismo comportamiento de siempre, sin
reintento especial (CU-O05 A3 sigue en backlog). Nuevo
`POST /viajes/{id}/disparar-programado`, primer endpoint del proyecto para
ser llamado por otro servicio del stack (no un usuario) — protegido por
`X-Internal-Token` (`core/config.py::internal_api_token`,
`secrets.compare_digest`). **Bug real encontrado y corregido, necesario
para que la feature funcionara**: `viajes/service.py` tenía dos
definiciones a nivel de módulo del nombre `ESTADOS_ACTIVOS` (una para
`obtener_viaje_activo`/cancelación, otra para el panel táctico de
Despacho) — la segunda sombreaba la primera en tiempo de ejecución (mismo
nombre reasignado a nivel de módulo), así que agregar `PROGRAMADO` solo a
la primera no habría tenido ningún efecto real; corregido renombrando la
segunda a `ESTADOS_ACTIVOS_PANEL` (deliberadamente sin `PROGRAMADO`, un
viaje no disparado no es "en curso" para ese panel). `analytics/dags/
dag_disparar_viajes_programados.py` (nuevo) — a diferencia de los otros 7
DAGs, no es un pipeline Bronze→Silver→Gold, es un disparador operativo
puro (`schedule_interval="*/2 * * * *"`, consulta Mongo directo con
`pymongo`, POST al backend con el token interno por cada `PROGRAMADO`
vencido, nunca reimplementa despacho). Frontend (`web-pasajero`): toggle
"Ahora"/"Programar" en `PanelSolicitar` con `<input type="datetime-local">`,
`PanelViajeActivo` muestra "Programado para: <hora>", cancelación reusa el
botón existente. Verificado en navegador real: 422 real al programar a 30
días ("La hora programada no puede ser más de 7 días en el futuro"), viaje
real creado en `PROGRAMADO` confirmado en Mongo sin despacho disparado.
**Cadena Airflow→backend verificada con una corrida real del DAG** (no un
curl manual simulando el disparo): `ts_programado` de un viaje real
adelantado en Mongo para simular vencimiento, `airflow dags trigger`
disparó la tarea real, que encontró el candidato vía pymongo y llamó al
endpoint interno real — log de la tarea "1 disparados, 0 fallidos, 1
candidatos", viaje confirmado pasando a `OFERTADO` en Mongo con
`ts_solicitud` actualizado al instante del disparo y `ts_programado`
preservado; corridas automáticas de la cadencia de 2 minutos confirmadas
corriendo solas en verde de fondo. Backend 327/327 tests + ruff limpio
(subió de 317); frontend build/lint/test limpios en `web-pasajero` (10/10,
subió de 9) + `shared-ui` lint. Detalle completo en
[PLAN_UX_COMPLEMENTARIA.md §9](PLAN_UX_COMPLEMENTARIA.md).

**Con el cierre de "Programar un viaje", los 7 puntos del paquete de UX
complementaria (`specs/specs-administrativas/ux_complementaria.md`) quedan
completos** — plan detallado completo en
[PLAN_UX_COMPLEMENTARIA.md](PLAN_UX_COMPLEMENTARIA.md). **Decisión final
sobre el contacto del Centro de ayuda** (preguntada explícitamente al
cierre de todo el bloque, como quedó acordado): el placeholder
(`soporte@urbanfleet.example` / `+593900000000`) se queda tal cual, de
forma permanente — UrbanFleet es un proyecto académico, no una cooperativa
real en operación, así que no existe ningún dato de contacto real que
reemplazar. No es un TODO pendiente; no reabrir este punto salvo pedido
explícito de un dato de contacto real.

## 11. Ronda de correcciones y mejoras (2026-08-07, post-UX complementaria)

Detectadas en pruebas manuales reales tras el cierre del bloque de UX
complementaria (§10). 4 de 5 puntos cerrados y verificados en navegador; el
5to (arquitectura de caché) quedó en propuesta, pendiente de aprobación
explícita del usuario antes de construirse — **no implementar sin esa
aprobación**.

- ✅ **Bug real — crash en "Historial de viajes" (web-interno)**: cerrado.
  `HistorialGlobal.tsx` tipaba `calificacion_pasajero_a_conductor`/
  `calificacion_conductor_a_pasajero` como `number | null`, pero
  `ViajeOut` (`backend/src/viajes/schemas.py:72-73`) los devuelve como
  `CalificacionOut | null` (`{puntaje, comentario, ts}`) — el objeto
  completo se pasaba a `DetailField`, reventando con "Objects are not
  valid as a React child". Corregido el tipo y el render (`{puntaje}★`,
  mismo patrón ya usado en `web-pasajero`/`web-conductor`, que nunca
  tuvieron este bug). Causa de que el test existente no lo detectara: el
  mock de `App.test.tsx` (`crearViajeHistorial`) usaba números planos en
  vez del shape real del backend — corregido también, más una aserción
  nueva (`"5★"` ×2) que ahora sí ejercita el render real. Revisado el
  resto de usos de `DetailField` en `web-interno` (grep de
  `DetailField label=.*value=`) — ningún otro caso pasa un objeto crudo.
- ✅ **Rediseño — overlay del mapa (web-pasajero/web-conductor)**: cerrado.
  El mapa (`RideMap`/`DriverMap`) tenía altura fija de 480px
  (`ALTO_MAPA`) sin importar el viewport, y el panel flotante encima
  tenía un tope duro de `min(45%, 260px)` con `overflowY: auto` que
  forzaba scroll interno. Ambos problemas venían de la misma causa: el
  mapa nunca llenaba el espacio real disponible de la pantalla. Fix:
  nuevo prop `llenarAltura` en `RideMap`/`DriverMap` (usa `height:"100%"`
  del contenedor en vez de `ALTO_MAPA` fijo — los usos de historial/vista
  pública compartida siguen con altura fija, sin cambios) + cadena de
  `flex:1`/`minHeight:0` desde `AppShell.css` (`.shell-content` pasó a
  `display:flex; flex-direction:column`) hasta el contenedor del mapa en
  cada app, condicionada solo a la vista de mapa activo (no afecta el
  resto de pantallas de `web-pasajero`/`web-conductor`, que siguen con
  alto de contenido normal). El panel flotante pasó su `maxHeight` de
  `min(45%, 260px)` a `calc(100% - 2 * var(--space-3))` — ya no necesita
  el tope duro porque el mapa (su contenedor) ahora es mucho más alto.
  Verificado en navegador real (cuentas demo pasajero/conductor): mapa
  llena 608px de un viewport de 720px de alto (antes serían 480px fijos,
  ~130px de espacio sobrante); overlay sin scroll en ningún estado
  probado (`scrollHeight === clientHeight` medido con `getComputedStyle`/
  DOM real, tanto en "¿A dónde vamos?" sin origen como en "Mi turno"
  DISPONIBLE). `npm run build/lint/test` limpios en las 3 apps +
  `shared-ui` lint.
- ✅ **Verificación — Densidad de tablas (Ajustes, web-interno)**: no era
  un bug, confirmado exhaustivamente. `aplicarDensidadInicial()` se llama
  en `main.tsx` antes del primer render (mismo patrón que `theme.ts`), la
  preferencia es una variable CSS global en `<html>`
  (`--table-cell-padding-y/x`), así que persiste en navegación entre
  secciones y en recarga completa de página — confirmado con
  `getComputedStyle` real tras un `navigate` de página completa, no solo
  cambio de estado en memoria. Confirmado en 3 tablas distintas
  (Solicitudes, Mantenimiento, Flota): alto de fila real 61px→51px
  (~16%) al pasar de "Cómoda" (no seteada = usa el mismo fallback de
  8px/12px, por diseño — por eso elegir "Cómoda" explícitamente no se ve
  distinto de no tocar el ajuste) a "Compacta" (3px/8px). Pasos de
  reproducción para confirmarlo a simple vista: **Ajustes → Densidad de
  tablas → Compacta**, comparar cualquier tabla del sistema — el cambio
  es inmediato, sin recargar.
- ✅ **Logo oficial**: cerrado. `logo_urbanflet.png` (1408×768, sin
  transparencia real pese a ser RGBA) ya estaba en la raíz del repo, sin
  que el usuario tuviera que agregarlo. Recortado en 2 variantes vía PIL
  (bbox por distancia de color contra blanco, ver histórico de comandos
  de esta sesión si hace falta reproducir el recorte) a
  `apps/shared-ui/src/assets/`: `logo-urbanflet-icon.png` (485×485,
  cuadrado, solo el emblema circular, con relleno blanco simétrico para
  no cortar contenido) para sidebar/header, y `logo-urbanflet-full.png`
  (607×567, emblema + wordmark "URBANFLEET / COOPERATIVA DE TRANSPORTE")
  para las 3 pantallas de login. Nuevo módulo `shared-ui/src/logo.ts`
  (reexportado desde `index.ts`) para que las 3 apps importen
  `logoUrbanFleetIcon`/`logoUrbanFleetFull` desde `@urbanflet/shared-ui`
  en vez de rutas relativas cruzadas entre paquetes. Reemplazó el
  cuadrado de color placeholder en `AppShell.tsx` (sidebar, 32×32, las 3
  apps) y se agregó sobre el título de cada `LoginCard`
  (`web-pasajero`/`web-conductor`/`web-interno`, 160px de ancho,
  `height:auto` para no distorsionar). Verificado en navegador real en
  las 3 apps: `naturalWidth`/`naturalHeight` correctos, aspect ratio
  preservado (`160×149.45` = mismo ratio que `607×567`), sin distorsión.
  Los PNG no se optimizaron a fondo (267KB + 374KB, un intento de
  cuantización con Pillow falló por modo RGBA y no valía la pena
  reintentar para este alcance) — aceptable para un asset cacheado que se
  carga una vez, no bloqueante.
- 🔶 **Estrategia de carga de datos entre secciones — enfoque aprobado,
  piloto construido y verificado, rollout al resto pendiente.** Investigado
  con evidencia real antes de proponer nada (no asumido): las 19 secciones
  de `sections/*.tsx` + los 9 `Panel*.tsx` de `sections/tactico/` en
  `web-interno` seguían el patrón `cargar()` + `useEffect` sin ningún
  caché compartido — el estado vivía con `useState` dentro de cada
  componente de sección, y `Panel()` en `App.tsx` desmonta/monta la
  sección activa (no hay `display:none`), así que volver a una sección ya
  visitada siempre repetía el fetch completo. No hay ninguna librería de
  fetching/caché instalada (ni react-query, ni SWR). El usuario aprobó el
  enfoque propuesto (caché casera, sin librería nueva) con la condición de
  migrar primero 2-3 secciones representativas y verificar en navegador
  antes de aplicarlo al resto.

  **Construido**: `apps/shared-ui/src/api/swrCache.ts` — hook
  `useSwr<T>(key, fetcher)` (stale-while-revalidate real: si `key` ya está
  en el `Map` en memoria del módulo, la muestra de inmediato en el primer
  render Y dispara igual un fetch en segundo plano que actualiza la vista
  si el servidor devolvió algo distinto; dedupe de requests en vuelo vía
  un segundo `Map` de promesas) + `invalidateSwr(key)`/
  `invalidateSwrPrefix(prefix)` para limpiar caché tras una mutación (por
  prefijo, no por key exacta — una mutación en una fila puede volver
  obsoleta CUALQUIER combinación de filtros cacheada de ese recurso, no
  solo la que estaba visible). Vive en memoria del tab (no
  `localStorage`): se pierde al recargar la página a propósito, no es
  persistencia de datos de negocio, solo evitar refetch entre
  navegaciones dentro de la misma sesión.

  **Piloto migrado** (2 secciones, un caso simple y uno complejo con
  filtros, como pidió el usuario): `Solicitudes.tsx` (`RECURSO_SOLICITUDES`)
  y `HistorialGlobal.tsx` (`RECURSO_HISTORIAL_GLOBAL`, el candidato más
  exigente por el volumen de 1.3M viajes NYC sembrados, ver §7). En ambos:
  la key de caché es la URL completa con querystring (así que cada
  combinación de filtros/página cachea por separado, no se mezclan);
  `ActionBar.actualizar` pasó de llamar `cargar()` a `refetch()`; en
  Solicitudes, `tomar()`/`decidir()` (las 2 mutaciones) ahora llaman
  `invalidateSwrPrefix(RECURSO_SOLICITUDES)` antes de `refetch()`.
  HistorialGlobal es de solo lectura (sin mutaciones, ver su propio
  docstring), así que no necesitó ese paso.

  **Verificado en navegador real** (cuenta `staff-verificacion`): (1)
  revisitar Solicitudes tras navegar a Mantenimiento y volver disparó una
  nueva request de red de fondo (revalidación) confirmada en
  `read_network_requests`, sin mostrar una pantalla en blanco ni de carga
  — el patrón SWR real, no solo teórico; (2) filtrar Solicitudes por
  "En verificación" (20 filas), aprobar una desde su panel de detalle, y
  confirmar que desapareció de esa lista filtrada de inmediato (19 filas)
  Y que al cambiar el filtro a "Todas" (una key de caché *distinta*, que
  ya tenía un valor viejo cacheado de antes de la mutación) mostraba el
  estado `APROBADA` correcto, no el `EN_VERIFICACION` obsoleto — prueba
  directa de que `invalidateSwrPrefix` limpia todas las combinaciones de
  filtro cacheadas, no solo la visible; (3) Historial de viajes cargó
  1,334,887 resultados reales con paginación, y el detalle de un viaje
  `PAGADO` mostró `Calificación pasajero → conductor: 5★` /
  `conductor → pasajero: 5★` sin errores de consola — confirma de paso,
  con datos reales de producción, el fix del punto 1 de esta misma
  ronda. Sin errores nuevos en consola (los 401 que aparecen son el
  ciclo normal de refresh de token, ya documentado en §4).
  `npm run build/lint/test` limpios en `web-interno` (23/23) + `shared-ui`
  lint.

  **Rollout aprobado por el usuario tras el piloto** — en curso, por
  lotes. Lote 1 cerrado: **Mantenimiento.tsx, Cumplimiento.tsx (2
  sub-secciones: bitácora + renovaciones), Finanzas.tsx (3 recursos:
  discrepancias, alertas de saldo negativo, liquidaciones)**. Notas de
  diseño nuevas encontradas en este lote (no estaban en el piloto):
  - **Bug real evitado en Cumplimiento** (detectado antes de llegar a
    producción, no en el piloto): el badge de "alertas de seguridad
    (24h)" calculaba `desde = Date.now() - 24h` directo como parte de la
    key de caché — recalculado en cada render, la key habría cambiado en
    cada repintado y el hook nunca habría podido servir desde caché (peor
    aún, cada render dispara un fetch nuevo). Corregido redondeando
    `desde` a baldes de 5 minutos antes de construir la key — mismo
    propósito (ventana de "últimas 24h") sin precisión de milisegundo,
    key estable entre renders. **Cualquier key de `useSwr` construida con
    `Date.now()`/`new Date()` sin redondear es sospechosa** — revisar en
    el resto del rollout.
  - **Patrón para fetches disparados por señal del padre** (`SeccionRenovaciones`,
    antes `useEffect([refreshSignal])`): la key ahora incluye
    `?refresh=${refreshSignal}` — cuando el padre incrementa la señal
    (tras "Ejecutar control de vigencia"), la key cambia a una nunca
    cacheada y fuerza un fetch fresco, con el mismo efecto que el
    `useEffect` viejo pero conservando el caché normal para una visita
    sin la señal disparada.
  - Verificado en navegador real con **mutaciones reales, una por
    pantalla** (no solo carga): Mantenimiento (orden `DEM-0146`
    ABIERTA→EN_TALLER, lista actualizada sin recargar), Cumplimiento
    ("Ejecutar control de vigencia" disparó un refetch real de
    renovaciones-pendientes, resultado "142 revisados" mostrado), Finanzas
    (liquidación de "Postulante Demo 090" EMITIDA→APROBADA, lista
    actualizada). Sin errores de consola nuevos (solo los 401 del ciclo de
    refresh de token, ya documentado). `npm run build/lint/test` limpios
    en `web-interno` (23/23).

  Lote 2 cerrado: **Catalogos.tsx (4 sub-secciones: zonas, tipos de
  documento, motivos, talleres — las 4 son listas fijas sin filtro/
  paginación), Usuarios.tsx (lista principal paginada/filtrada; el
  fetch on-demand de accesos/sesiones al abrir un detalle se dejó como
  estaba, no es un "revisitar sección" sino un "abrir un registro
  puntual"), Integraciones.tsx (2 sub-secciones: credenciales, servicios
  externos), GobernanzaDatos.tsx (solo la política de retención — la
  sub-sección de anonimización es búsqueda bajo demanda, no fetch al
  montar, así que no aplica el patrón).** Verificado en navegador real
  (cuenta `admin_sistema`) con mutaciones reales por pantalla: Catálogos
  (taller nuevo "Taller QA Caché" creado y visible sin recargar), Usuarios
  (cuenta "QA Nueva Cuenta" ACTIVO→SUSPENDIDO→ACTIVO otra vez, motivo
  reflejado), Integraciones (credencial "Credencial QA Caché" creada y
  visible), GobernanzaDatos (política de retención carga 5 filas reales
  sin errores). `npm run build/lint/test` limpios en `web-interno`
  (23/23) — varios tests preexistentes (Catálogos, Integraciones,
  Usuarios) ya ejercitaban estas mismas mutaciones contra el mock y
  siguieron pasando sin cambios, buena señal adicional de que la
  migración no alteró el contrato observable de cada pantalla.

  Lote 3 cerrado (último lote — **rollout completo**):
  **PanelMantenimiento, PanelDocumentacion, PanelCaptacion,
  PanelConciliacion, PanelLiquidacion, PanelAuditoria, PanelPlataforma**
  (los 7 paneles tácticos restantes — inicialmente se pensó dejar fuera
  `PanelPlataforma` asumiendo que tenía polling propio como Flota/
  Despacho/Monitoreo, pero se verificó el código antes de excluirlo sin
  más: no tiene ningún `setInterval`, es el mismo patrón fetch-on-mount
  con filtros que el resto, así que se migró también). Los 7 son
  dashboards de solo lectura (sin mutaciones): cada uno combina 2-5
  endpoints en un solo `Promise.all` cacheado bajo una única key
  sintética por panel (ej. `/mantenimiento/panel-tactico`, no
  corresponde a un endpoint real, es solo el nombre de la entrada de
  caché). `PanelAuditoria` y `PanelPlataforma` son los únicos con
  filtros que cambian la key (actor/resultado/acción/fechas en el
  primero, dominio/fecha_logica en el segundo) — mismo patrón que
  `Solicitudes`/`HistorialGlobal`.

  **Bug de lint real encontrado y corregido en los 6 archivos** (no
  afecta corrección funcional, sí performance/limpieza): el patrón
  `data?.campo ?? []` usa un array literal `[]` que crea una referencia
  nueva en cada render — como estos paneles alimentan varios `useMemo`
  con esos campos como dependencia, cada uno se recalculaba en *todos*
  los renders, no solo cuando los datos cambiaban de verdad (30 warnings
  nuevos de `react-hooks/exhaustive-deps` al buildear). Corregido
  definiendo constantes `SIN_<CAMPO>` a nivel de módulo en cada archivo
  (`const SIN_ORDENES: Orden[] = []`, etc.) y usándolas como fallback en
  vez del literal inline — misma referencia estable entre renders,
  `useMemo` vuelve a memoizar de verdad. Vale la pena revisar este mismo
  patrón si se sigue extendiendo el hook a pantallas nuevas con
  `useMemo` derivados de datos de `useSwr`.
  Verificado en navegador real (cuenta `staff-verificacion`): los 6
  paneles cargan con datos reales sin errores de consola nuevos
  (`DEM-0146` en PanelMantenimiento mostrando `EN_TALLER`, coherente con
  la mutación real del lote 1); cambiar el filtro "Resultado" de
  PanelAuditoria a "OK" disparó una request nueva
  (`GET /auditoria/eventos?resultado=OK&tamanio_pagina=100`) confirmada
  en el log de red. `npm run build/lint/test` limpios en `web-interno`
  (23/23, 0 warnings nuevos tras el fix de las constantes estables).

  **Con esto, el rollout de caché SWR queda completo**: 2 secciones del
  piloto + 3 del lote 1 + 4 del lote 2 + 7 del lote 3 = 16 pantallas
  migradas. Quedan fuera, por diseño: Flota, PanelFlota, PanelDespacho,
  Monitoreo (polling propio real, confirmado con `setInterval` en cada
  uno), la sub-sección de anonimización de GobernanzaDatos (búsqueda
  bajo demanda, no fetch-on-mount), el fetch de accesos/sesiones al
  abrir un detalle de Usuario (acción puntual, no "revisitar la
  sección"), y las pantallas de acción pura sin listado (VersionSistema,
  Respaldos, ConfiguracionAlertas, etc. — no se auditaron una por una
  porque no encajan en el patrón "lista que se revisita", no porque se
  hayan pasado por alto).


## 12. Nivel estratégico — backend de los 9 dashboards (Fase 3, cerrada)

Spec: `specs/nivel-estrategico/nivel_estrategico.md` (6 objetivos OE1-OE6,
5 casos de uso CU-E01..CU-E05, 8 dashboards de detalle + 1 tablero ejecutivo).
Plan y hallazgos previos: `AUDITORIA_NIVEL_ESTRATEGICO.md` §10 (Fase 3).
**Alcance de este bloque: SOLO backend.** Ningún archivo de `apps/*` se tocó
— el frontend es la Fase 4, con su propio prerrequisito pendiente (H4, el
mecanismo de navegación cruzada entre secciones de `web-interno`, que hoy
sigue sin existir).

Los 9 endpoints quedaron **construidos y verificados con llamada real**
(login real con la cuenta `gerencia` de §8.7, 200 con datos reales, no
mockeados). `pytest` pasó de 327 a **346 passed + 8 skipped**, sin
regresión; `ruff check src/ tests/` limpio.

### 12.1 Dónde vive cada endpoint (y por qué)

Se mantiene el criterio descentralizado que el nivel táctico ya había
decidido explícitamente (cada dominio expone lo suyo, sin módulo central):
7 de los 9 tienen un dominio dueño claro y viven en el router de ese dominio,
con la ruta `GET /<dominio>/panel-estrategico/...`.

| # | Dashboard (spec) | Endpoint | Fuentes `rpt_*` |
|---|---|---|---|
| OE1 | Crecimiento Estratégico | `GET /captacion/panel-estrategico/crecimiento` | `rpt_conversion_captacion`, `rpt_altas_retencion_canal`, `rpt_conversion_onboarding` |
| OE2a | Confiabilidad y Disponibilidad | `GET /viajes/panel-estrategico/confiabilidad` | `rpt_tiempo_asignacion`, `rpt_tasa_cancelacion`, `rpt_flota_activa_franja` |
| OE2b | Estado y Costo de Flota | `GET /mantenimiento/panel-estrategico/estado-costo-flota` | `rpt_cumplimiento_plan_preventivo`, `rpt_costo_mantenimiento_vehiculo` |
| OE3 | Capacidades y Plataforma | `GET /plataforma/panel-estrategico/capacidades` | `rpt_cuarentena_dominio` + tabla `corridas` |
| OE4 | Rentabilidad y Demanda (patrón F) | `GET /estrategico/rentabilidad-demanda` | las 4: margen, costo mantenimiento, tiempo asignación, flota activa |
| OE5 | Integridad Financiera | `GET /liquidaciones/panel-estrategico/integridad-financiera` | `rpt_tasa_discrepancias`, `rpt_margen_comision` |
| OE6a | Cumplimiento Normativo | `GET /cumplimiento/panel-estrategico/cumplimiento-normativo` | `rpt_documentacion_vigente` |
| OE6b | Gobernanza de Datos y Seguridad (patrón F) | `GET /auditoria/panel-estrategico/gobernanza` | ninguna — `bitacora` (Mongo) |
| CU-E01 | Tablero Ejecutivo Consolidado | `GET /estrategico/tablero-ejecutivo` | los 8 anteriores |

**Módulo nuevo `backend/src/estrategico/`** (router/service/schemas), con solo
2 endpoints: OE4 y CU-E01. No es un módulo central "porque sí" — son
exactamente los 2 que no tienen dominio dueño (OE4 cruza finanzas +
mantenimiento + despacho + flota para calcular un margen que no es de ninguno;
CU-E01 cruza los 8 por definición). Si mañana aparece un dashboard estratégico
con dominio dueño, va en el router de su dominio, no acá. Su prefijo ya es
`/estrategico`, por eso esas 2 rutas no repiten el segmento
`/panel-estrategico/`.

**`backend/src/core/agregacion_estrategica.py`** (nuevo): helpers de la
segunda capa de agregación (`variacion_pct`, `promedio_ponderado`, `agrupar`,
`ultimos_periodos`), usados por 7 de los 9. `promedio_ponderado` existe porque
las `rpt_*` publican porcentajes ya calculados por subgrupo — promediarlos sin
ponderar por volumen le daría el mismo peso a una franja con 3 registros que a
una con 30,000.

**Ni una tabla `rpt_estrategico_*` nueva ni un DAG nuevo**, como se pidió. La
"tendencia extendida" sale de dos mecanismos distintos según la fuente, y la
diferencia importa (documentada en el docstring de
`core/agregacion_estrategica.py`):

1. Tablas que YA traen periodo propio (`rpt_margen_comision`,
   `rpt_tasa_cancelacion`, `rpt_conversion_captacion`,
   `rpt_cumplimiento_plan_preventivo`, `rpt_costo_mantenimiento_vehiculo`,
   `rpt_tasa_discrepancias`): el último snapshot ya contiene varios meses →
   `fetch_latest_snapshot` + agrupado por ese periodo.
2. Tablas que son un corte puntual (`rpt_flota_activa_franja`,
   `rpt_documentacion_vigente`, `rpt_tiempo_asignacion`,
   `rpt_cuarentena_dominio`, `rpt_conversion_onboarding`): la tendencia sale de
   `fetch_snapshot_history` sobre `fecha_datos` (son MergeTree, conservan un
   corte por corrida).

### 12.2 Decisiones no triviales tomadas en esta fase

- **`junta_socios` no se crea** (decisión ya aprobada antes de empezar). Los
  dashboards que la spec le asigna (OE2b, OE4, OE5, CU-E01) quedan bajo
  `gerencia`, el otro rol que la propia spec ya lista para los 4. Documentado
  con un comentario junto a cada gate afectado (`mantenimiento/router.py`,
  `recaudacion/router.py`, `estrategico/router.py`). Razón: un rol sin cuenta
  ni pantalla propias repetiría el patrón muerto de `integracion_externa`.
- **Roles por dashboard**: se respeta lo que la spec define, y donde la spec
  solo dice `gerencia` se suma el rol dueño del dominio (`admin_captacion`,
  `coordinador_operaciones`, `jefe_mantenimiento`, `admin_financiero`) —
  **con una excepción deliberada: OE6b (Gobernanza) queda exclusivo de
  `gerencia`**, porque la spec lo declara así explícitamente (no se comparte
  ni con `admin_sistema`, que ya tiene su vista operativa de la misma bitácora
  en Administración). Hay un test que lo fija (`admin_sistema` → 403).
- **Fórmula de margen de OE4** (nadie la había definido con precisión; queda
  documentada en el docstring de
  `estrategico/service.py::obtener_panel_rentabilidad`). Para cada mes `m` y
  franja `f` ∈ {DIURNA, NOCTURNA}:
  `recaudacion = bruto_total[m] * share_demanda[f]`,
  `comision = comisiones_total[m] * share_demanda[f]`,
  `costo_mant = costo_mant_total[m] * share_capacidad[f]`,
  `margen = recaudacion - comision - costo_mant`.
  **Lo importante son las DOS bases de prorrateo distintas**: prorratear los
  3 componentes por la misma participación daría un `margen_pct` idéntico en
  todas las franjas — cierto pero inútil, porque el dashboard existe para
  compararlas. La distinción tiene sustento real: recaudación y comisión
  escalan con los viajes atendidos (`rpt_tiempo_asignacion`), el costo de
  mantenimiento escala con la exposición del activo
  (`rpt_flota_activa_franja` — un vehículo en servicio se desgasta esté
  ocupado o no). Así una franja con mucha flota y poca demanda sale con menor
  margen, que es justo la señal que CU-E02/CU-E03 necesitan. Hay un test que
  fija este comportamiento.
- **Puente de taxonomías de "franja"** (`FRACCION_DIURNA_POR_BUCKET` en
  `estrategico/service.py`): `rpt_flota_activa_franja` publica buckets de 6h
  (`00-06`/`06-12`/`12-18`/`18-24`) y `rpt_tiempo_asignacion` publica
  `DIURNA`/`NOCTURNA`. Como la franja diurna es 05:00-22:00
  (`core/config.py::franja_diurna_desde_hora/hasta_hora`), el reparto es
  aritmética exacta de horas por bucket (00-06 → 1/6 diurna; 18-24 → 4/6;
  los dos del medio, 100%), no una estimación.
- **Tablero ejecutivo: una sola respuesta con los 8 headlines**, no 8 llamadas
  del frontend. Razones: es un índice, se abre entero; `gerencia` es el único
  rol que la spec lista para los 8, así que una respuesta única no filtra nada
  que el actor no pudiera pedir por separado; y evita 8 handshakes en el
  primer render. Cada headline llama al **mismo servicio** que sirve su
  dashboard de detalle (nunca reimplementa el cálculo, para que los dos
  números no puedan divergir), y cada bloque va en su propio `try`: una fuente
  vacía o ClickHouse caído deja esa tarjeta con `disponible=false` en vez de
  tumbar el tablero. El campo `seccion` de cada tarjeta es el identificador
  del dashboard destino del enlace "Ver detalle" — se define en el backend a
  propósito, para que el mapeo tarjeta→destino no sea un mirror manual en TSX
  (mismo problema ya resuelto en Auditoría Administrativa).
- **Excepción documentada a la regla de la Sección 2 de la spec** ("nunca
  Mongo directo, siempre sobre `rpt_*`"): solo OE6b la usa, porque la bitácora
  no tiene ninguna `rpt_*` detrás y la propia spec declara como fuente "los
  eventos de auditoría administrativa ya construidos (Módulo 6.1)". Los otros
  8 respetan la regla. El único otro toque a Mongo es resolver la **placa** de
  un vehículo en OE2b (dato descriptivo, no una métrica — mismo patrón ya
  aceptado en el panel táctico de Mantenimiento).

### 12.3 Limitaciones que los endpoints DECLARAN en vez de disimular

Todas viajan en el campo `metadata` de la respuesta, para que la Fase 4 pueda
mostrar la advertencia en la UI (mismo criterio ya usado con el gap de zona en
el Panel de Flota táctico). Ninguna se rellenó con un dato inventado:

| Bandera | Dónde | Qué significa |
|---|---|---|
| `zona_disponible: false` | OE4 (fijo) y OE2a (calculado del dato real) | `viajes.zona_origen_id` sigue sin resolverse. En OE4 la matriz es mes × franja y no zona × franja, alcance recortado que la propia spec previó. En OE2a la bandera se calcula del snapshot, y hoy da `true` (las filas Gold sí traen Z-NORTE/Z-SUR). |
| `km_disponible: false` | OE2b | La tabla de "candidatos a reemplazo (costo vs. km)" sale sin km: el kilometraje no existe en ninguna `rpt_*` y solo vive en `ordenes` (Mongo), prohibido para este nivel. `km_recorridos` va en `None`. |
| `tasa_cancelacion_disponible: false` | OE2a | **Hallazgo real de esta fase**: `rpt_tasa_cancelacion` no es consolidable como tasa. El query que la publica agrupa por motivo/actor con `HAVING cancelados > 0`, así que en cada fila `solicitados == cancelados` y la tasa vale siempre 1.0 — los viajes NO cancelados nunca llegan a la tabla. Se sirve el **volumen** de cancelaciones por mes (real y consolidable) y su variación; la tasa va en `None`. Arreglarlo de raíz exige cambiar el DAG táctico. |
| `demanda_disponible: false` / `demanda_viajes_disponible: false` | OE1 y OE4 | Ninguna `rpt_*` publica viajes solicitados por mes (ver el punto anterior: la única con periodo y volumen solo trae cancelados). En OE1 `crecimiento_demanda_pct` va en `None`; en OE4 la "tendencia de demanda de largo plazo" se sirve como recaudación bruta por trimestre, explícitamente etiquetada como proxy. |
| `canal_cobertura_parcial: true` | OE1 | 96 de 194 usuarios (49%) no tienen `canal` (hallazgo H3 de la auditoría). El desglose por canal subrepresenta a esa mitad. |
| `capacitacion_disponible: false` | OE3 | No existe dominio de capacitación en el sistema (backlog consciente ya declarado en el nivel táctico). |
| `dataset_mixto: true` | OE5 | Se enciende cuando el rango cubre más de un año: en este entorno eso mezcla el dataset NYC de calibración (2021) con la operación de demo (2026). La comparación interanual se sirve, pero marcada — no como si fuera homogénea. |

Además, **dos taxonomías de "franja" que NO se cruzan** en OE2a: se devuelven
`franjas` (buckets de 6h, de Flota) y `franjas_asignacion` (DIURNA/NOCTURNA,
de Despacho) como listas separadas. Un join por franja daría 100% de nulos.

### 12.4 Verificación real hecha

- Los 9 endpoints llamados con `curl` contra el backend corriendo en Docker
  (hot-reload de uvicorn confirmado: `docker-compose.yml` monta
  `./backend/src:/app/src` y el `CMD` trae `--reload`), con token real de la
  cuenta `gerencia` (`+593900000010` / `Gerencia123!`, §8.7). Los 9 con 200 y
  datos reales — p. ej. Capacidades con 1.93% de cuarentena global real sobre
  1,360,494 registros extraídos y 205 corridas OK; Cumplimiento Normativo con
  63.4% vigente sobre los 142 documentos reales; el tablero ejecutivo con las
  8 tarjetas en `disponible=true`.
- RBAC verificado en vivo: cuenta de conductor → **403** en
  `/estrategico/tablero-ejecutivo`.
- 19 tests nuevos (`backend/tests/estrategico/test_nivel_estrategico.py`):
  403 parametrizado sobre las 9 rutas, el 403 de `admin_sistema` en OE6b, la
  agregación real de OE6b sobre `bitacora` sembrada, los 4 helpers de
  agregación, y la fórmula de OE4 con snapshots `rpt_*` falsos (sin ClickHouse
  real). `pytest` total: **346 passed, 8 skipped** (base: 327 + 8).
- **No hubo verificación en navegador** — esta fase es backend puro, no hay UI
  que abrir todavía (regla de cierre §6: cuando no se puede verificar en
  navegador, se dice explícitamente en vez de simularlo).

### 12.5 Qué queda pendiente para la Fase 4 (frontend)

- Resolver **H4** (`AUDITORIA_NIVEL_ESTRATEGICO.md` §6): `Seccion` en
  `apps/web-interno/src/App.tsx` define `render: () => JSX.Element` sin ningún
  prop de navegación, así que un botón "Ver detalle" dentro de un panel no
  tiene hoy forma de invocar `setSeccionActiva`. Es transversal a los 9 y al
  tablero ejecutivo — construirlo tarde obliga a retocar todos los paneles.
- Grupo nuevo "Panel Estratégico" en el sidebar, mismo patrón que "Panel
  Táctico". Recordatorio ya aprendido dos veces (ver §10, "Mi cuenta" e
  "Historial de viajes"): **agregarlo al final del array `SECCIONES`**, o
  desplaza la sección por defecto de algún rol y rompe tests sin relación
  aparente.
- Patrones de layout por dashboard: `DashboardZ` para 7, `DashboardF` para
  OE4 y OE6b (los 2 que la spec marca como patrón F).
- Consumir las banderas de `metadata` de §12.3 para mostrar las advertencias,
  en vez de dibujar filtros/columnas que no tendrían dato detrás.

## 13. Nivel estratégico — frontend de los 9 dashboards (Fase 4, cerrada)

Cierra el nivel estratégico: los 8 paneles de detalle + el Tablero Ejecutivo
Consolidado (CU-E01) sobre los 9 endpoints que dejó la Fase 3 (§12). **Solo
frontend** — ningún archivo de `backend/src/**` tocado: la forma de las 9
respuestas se leyó del código real (`git show c0a123d`) y se confirmó
llamando los 9 endpoints con un token real de `gerencia` antes de escribir
una sola línea de TSX, no se asumió.

### 13.1 H4 resuelto — navegación cruzada entre secciones

`apps/web-interno/src/navegacion.ts` (nuevo): un React Context que publica la
**misma** `setSeccionActiva` que ya usaba el sidebar vía
`AppShell.onNavigate`, más la lista de ids visibles para el actor. Dos hooks:
`useIrASeccion()` → `(id: string) => void`, y `useSeccionesDisponibles()` →
`string[]`.

- **Ninguna de las ~32 secciones existentes cambió de firma.** `Seccion.render`
  sigue siendo `() => JSX.Element`; solo quien necesita navegar consume el
  hook. El único cambio en `App.tsx` es envolver el `AppShell` en
  `<NavegacionSeccionProvider>`.
- La lista de disponibles **no es decorativa**: `Panel()` resuelve la sección
  activa dentro de `seccionesVisibles`, así que navegar a un id que el rol no
  ve dejaría el área de contenido en blanco. Por eso el enlace secundario
  "Ver táctico" del tablero se **oculta** si el rol no ve ese panel táctico —
  verificado en vivo: con la cuenta `gerencia`, de las 8 tarjetas solo
  Capacidades y Gobernanza muestran "Ver táctico" (los únicos 2 paneles
  tácticos que ese rol ve), las otras 6 no lo pintan.
- Fuera del proveedor los hooks devuelven un no-op / lista vacía en vez de
  lanzar, para poder renderizar un panel aislado en un test.
- Vive en `web-interno` y no en `shared-ui` a propósito: el modelo de
  "secciones con id" es exclusivo de esta app.
- `seccionesVisibles` pasó a `useMemo` (dependía de un `filter` que creaba
  array nuevo en cada render) para que el `value` del contexto sea estable.

### 13.2 Grupo "Panel Estratégico" en el sidebar

9 entradas nuevas en `SECCIONES` con `grupo: "Panel Estratégico"`, ids
`estrategico-tablero` + `estrategico-<seccion>` donde `<seccion>` es
**exactamente** el identificador que el backend ya publica en
`TarjetaEjecutivaOut.seccion` (`_HEADLINES` en `estrategico/service.py`) —
así el mapeo tarjeta→destino no es un mirror manual en TSX, sale del dato.

**Posición: después de "Panel Táctico", antes de "Administración"** — no al
final. El criterio real documentado en §10 no es "al final por costumbre",
es *"no convertirse en la sección por defecto (`seccionesVisibles[0]`) de
ningún rol"*. Se verificó rol por rol: los 7 con acceso a algún panel
estratégico (`gerencia`, `admin_captacion`, `coordinador_operaciones`,
`jefe_mantenimiento`, `responsable_plataforma`, `admin_financiero`,
`supervisor_cumplimiento`) ya tienen al menos una sección más arriba, así
que insertar acá no mueve ningún índice 0. Confirmado en navegador: con
`gerencia` la sección por defecto sigue siendo "Indicadores", con
`staff-verificacion` sigue siendo "Solicitudes", y los 23 tests siguen
pasando. Ubicarlo ahí respeta la jerarquía operativo → táctico →
estratégico del sidebar.

Los `roles` de cada entrada replican **exactamente** el gate del endpoint que
consume — en particular Gobernanza (OE6b) es exclusivo de `gerencia`, sin
OR-gate con `admin_sistema`. Verificado en navegador con `staff-verificacion`
(7 roles tácticos, sin `gerencia`): ve 6 de los 9 y **no** ve Tablero
Ejecutivo, Rentabilidad ni Gobernanza.

### 13.3 Los 9 componentes

En `apps/web-interno/src/sections/estrategico/`: `PanelCrecimiento`,
`PanelConfiabilidad`, `PanelEstadoCostoFlota`, `PanelCapacidades`,
`PanelRentabilidad`, `PanelIntegridadFinanciera`,
`PanelCumplimientoNormativo`, `PanelGobernanza`, `TableroEjecutivo`, más 2
archivos compartidos (`formato.ts`, `comunes.tsx`).

- **Sin componentes de gráfico nuevos** salvo uno justificado (ver 13.4):
  `KpiCard`/`KpiRow`, `CategoryBarChart`/`TrendLineChart`, `DashboardZ`/
  `DashboardF`, `FuenteBadge`, `DataTable` de `shared-ui`, tal cual.
- **Nacen usando el caché SWR** (`useSwr`), no como deuda técnica día uno —
  mismo criterio del rollout completo del lote 3 (§11). Los 9 son de solo
  lectura, así que ninguno necesita `invalidateSwrPrefix`.
- **Constantes `SIN_<CAMPO>` a nivel de módulo** en los 8 paneles con
  `useMemo` derivados, por el problema de referencia inestable de
  `data?.campo ?? []` ya documentado en §11. `npm run lint` quedó en 0
  warnings nuevos.
- **Convención de unidades — el error fácil de este nivel, aislado en
  `formato.ts`**: todo campo `pct_*`/`margen_pct`/`share_*` viaja como
  **fracción 0-1**, mientras que todo `variacion_*_pct` viaja ya en **puntos
  porcentuales**. De ahí dos helpers distintos (`pct()` vs. `variacion()`) en
  vez de uno solo; mezclarlos daría un 9842% donde va 98,4%.
- **Filtros**: cada panel tiene el filtro de ventana temporal
  (`meses`/`cortes`) que va a la **key de caché y al servidor** (dispara
  request nueva real), más filtros client-side del spec por dashboard: canal
  (Crecimiento), franja + zona deshabilitada (Confiabilidad, Rentabilidad),
  vehículo (Costo de Flota), dominio (Capacidades), año (Integridad
  Financiera), tipo de documento (Cumplimiento Normativo), acción + resultado
  (Gobernanza).

### 13.4 Decisiones de diseño no triviales

- **`MiniTendencia` (sparkline SVG inline en `TableroEjecutivo.tsx`) — la
  única visualización nueva de la fase.** La spec §4 pide "KPI +
  mini-tendencia + enlace" dentro de una tarjeta de índice; `TrendLineChart`
  trae ejes con ticks, grilla, tooltip y leyenda, que en 40-90 px de alto
  compiten con el número que la tarjeta existe para mostrar. El SVG usa
  `seriesColor(0)` de la paleta ya validada, así que **no introduce ningún
  color fuera del sistema**; se degrada a un hueco vacío con menos de 2
  puntos, sin dibujar una línea falsa.
- **Enlace secundario "Ver táctico"** (spec §2, "bajar al detalle
  departamental"): el primario "Ver detalle" va al panel **estratégico**,
  como pide CU-E01; el táctico es adicional y condicional al rol.
  `rentabilidad` es la única tarjeta sin equivalente táctico — el margen por
  franja es un cálculo nuevo de este nivel, no la consolidación de un panel
  táctico existente, así que ahí no se inventa un destino.
- **Limitaciones de `metadata` mostradas, nunca fabricadas** — las banderas
  de §12.3 se leen y se pintan como nota explícita junto al KPI/columna
  afectada, con el valor en "—": demanda por mes (Crecimiento), tasa de
  cancelación + zona (Confiabilidad), km de vehículo (Costo de Flota),
  capacitación (Capacidades), zona + demanda de viajes (Rentabilidad),
  dataset mixto 2021/2026 (Integridad Financiera), cobertura parcial de canal
  (Crecimiento). Los filtros de **zona** de Confiabilidad y Rentabilidad se
  renderizan `disabled` con la leyenda "No disponible" en vez de omitirse:
  deja visible que la spec los pide y por qué no están.
- **Dos taxonomías de "franja" conviven a propósito** en Confiabilidad (los
  buckets de 6 h del ping GPS y DIURNA/NOCTURNA de la franja tarifaria) — van
  en tablas separadas, con nota, en vez de cruzarse en una sola.

### 13.5 Verificación real en navegador (cuenta `gerencia`, 1440x900)

Los 9 dashboards + el tablero abiertos uno por uno contra el stack real
(`docker compose ps` con los 8 servicios arriba), **sin un solo error de
consola** en toda la sesión:

- **Los 9 endpoints devolvieron 200 con datos reales**, confirmado en el log
  de red — incluidos los 9 pares OPTIONS/GET.
- **Patrón Z vs. F medido con `getComputedStyle`, no a ojo**: los 7 paneles Z
  miden `544.5px 544.5px` (`.dashboard-z-row`); Rentabilidad y Gobernanza
  miden `320px 769px` (`.dashboard-f-row`) — dos layouts genuinamente
  distintos, no el mismo grid reusado.
- **Un filtro interactivo probado por dashboard**, con efecto real
  verificado: el de ventana disparó una request nueva en los 8 paneles
  (`?meses=12` → `?meses=3`, `?cortes=12` → `?cortes=3`, etc., todos los GET
  visibles en el log); los client-side se midieron sobre el DOM (Confiabilidad
  franja `12-18`: 4 filas → 1; Costo de Flota búsqueda "DEM": 5 → 3;
  Capacidades dominio `dag_flota_gold`: 7 → 1; Rentabilidad franja DIURNA:
  2 → 1; Cumplimiento tipo `MATRICULA_VEHICULAR`: 2 → 1; Integridad
  Financiera año `2026`: el eje X del gráfico pasó de
  `2021-01/2021-02/2026-07/2026-08` a `2026-07/2026-08`).
- **Navegación cruzada real, sin recargar la página** (`location.href` intacto
  en `http://localhost:5175/`): desde el Tablero, "Ver detalle" de Crecimiento
  → "Panel de Crecimiento Estratégico"; "Ver detalle" de Gobernanza → "Panel
  de Gobernanza de Datos y Seguridad"; "Ver táctico" de Capacidades → "Panel
  de Salud del Pipeline y Capacitación" (el táctico de Plataforma).
- **Tablero ejecutivo**: 8 tarjetas, "8 de 8 indicadores con dato publicado",
  valores coincidiendo con el panel de detalle de cada uno (98.4% conversión,
  91.5% flota activa, 60.0% preventivo, 1.9% cuarentena, 80.0% margen, 100.0%
  conciliación, 63.4% documentación, 79 eventos administrativos).
- **RBAC confirmado con una segunda cuenta** (`staff-verificacion`,
  `+593900000001`): ve exactamente los 6 paneles estratégicos que sus roles
  habilitan y **no** ve Tablero Ejecutivo, Rentabilidad ni Gobernanza; su
  sección por defecto sigue siendo Solicitudes.

**Regresión**: `npm run build`, `npm run lint` (0 errores; los 3 warnings de
`useEffect` en `ParametrosGlobales`/`PoliticasAuth`/`PoliticasSeguridad` son
preexistentes, no de esta fase) y `npm run test` (23/23) limpios en
`web-interno`, más `npm run lint` limpio en `shared-ui`. Backend sin tocar,
así que no se re-corrió `pytest` (la última corrida registrada es la de la
Fase 3: 346 passed + 8 skipped).

**Con esto, el nivel estratégico queda completo de extremo a extremo** —
Fase 3 (backend, §12) + Fase 4 (frontend, §13). Los ítems que siguen
abiertos son los que la propia auditoría clasificó como fuera de este
alcance: resolución real del gap de zona (toca código operativo), Parquet
versionado más allá del piloto de `dag_mantenimiento_gold` (Fase 2), y los 2
gaps operativos heredados (`movimientos.tipo="AJUSTE"`, cobertura de `canal`).

## 14. Fase 5 — regresión final consolidada (cierre del bloque de nivel estratégico)

Corrida después de que las Fases 0-4 (`AUDITORIA_NIVEL_ESTRATEGICO.md` §10)
quedaran cada una cerrada por separado, para confirmar que el conjunto
completo convive sin romperse — no solo cada fase aislada. Resultado real:

- Backend: `pytest` **346 passed, 8 skipped** (mismo número que al cierre de
  la Fase 3 — el trabajo de Fase 4 no tocó backend, confirmado corriendo la
  suite de nuevo de todas formas en vez de asumirlo).
- Frontend `web-interno`: `npm run build` ✅, `npm run lint` 0 errores (los
  mismos 3 warnings preexistentes de `useEffect` en
  `ParametrosGlobales`/`PoliticasAuth`/`PoliticasSeguridad`, no de este
  bloque), `npm run test` **23/23**.
- Verificación adicional en navegador real (cuenta `gerencia`,
  `+593900000010`), con foco específico en los 2 dashboards que la regla de
  cierre del proyecto (§6) exige verificar con más rigor por tocar cálculo
  financiero/dato sensible:
  - **Rentabilidad y Demanda (OE4)**: fórmula real confirmada en pantalla
    (margen 80% idéntico en ambas franjas porque, con costo de mantenimiento
    en $0 para el periodo real disponible, `margen% = 1 − comisión%` da 80%
    en cualquier franja — consistente con la comisión fija del 20% del
    proyecto, no un bug ni un dato fabricado). Nota de zona no disponible
    visible tal como se diseñó.
  - **Gobernanza de Datos y Seguridad (OE6b)**: bitácora real con 79+ eventos
    administrativos reales (`admin_sistema`, `pasajero`, `jefe_mantenimiento`
    con acciones reales trazables — `CATALOGO_EDICION`, `RESPALDO_DISPARO`,
    `USUARIO_ANONIMIZACION`, etc.), no datos de ejemplo.
  - **Tablero Ejecutivo**: 8/8 headlines con el mismo valor que su panel de
    detalle correspondiente (98.4%, 91.5%, 60.0%, 1.9%, 80.0%, 100.0%, 63.4%,
    79), navegación cruzada probada de nuevo de forma independiente (clic en
    "Ver detalle" de Rentabilidad desde el tablero cambió la sección activa
    sin recargar la página).

**El bloque completo del nivel estratégico (Fases 0-5) queda cerrado.** Ver
`AUDITORIA_NIVEL_ESTRATEGICO.md` para el informe de auditoría original y el
detalle de las decisiones aprobadas por el usuario antes de construir.

## 15. Bug real — estampida de refresh de token (401 a mitad de sesión), cerrado

Reportado por el usuario tras ver, ya logueado y en medio de uso normal (no al
cargar la página, no al cambiar de cuenta), tres 401 seguidos:
`GET /notificaciones/mias?limite=1` (dos veces) y
`GET /usuarios?limit=20&offset=0`. Distinto del patrón benigno ya conocido de
"401 → refresh → reintento" al cargar.

**Lo que NO era** (descartado con evidencia antes de tocar código, no asumido):

- **No era un TTL corto olvidado.** El valor de prueba de 7 minutos del Módulo
  6.2 sí se había revertido: `db.parametros` con `tipo:"seguridad"` tiene 3
  versiones y la vigente (`vigente_hasta:null`, desde 2026-08-07T05:06) trae
  `access_token_minutos: 15`, el default de `DEFAULTS_SEGURIDAD`. La versión de
  7 minutos quedó correctamente cerrada con `vigente_hasta`. No se corrigió
  nada acá.
- **No era un componente saltándose el cliente compartido** (sospecha inicial
  sobre `NotificacionesBell`/`UserPicker`). Los dos usan `apiFetch`, leído
  línea por línea. Un grep de `fetch(` en `apps/*/src` devuelve exactamente 3
  usos de `fetch` nativo, los 3 legítimos: los 2 de `api/client.ts` (el propio
  `apiFetch` y el POST a `/auth/refresh`, que no debe llevar interceptor) y el
  de `web-pasajero/src/rutas.ts` (geocoding de Google, no es la API propia).
  `/usuarios?limit=20&offset=0` sale de `Usuarios.tsx` vía `useSwr` + `apiFetch`.
  Las 3 peticiones del incidente pasaban por el interceptor.

**Causa raíz real: `apiFetch` no tenía single-flight en la renovación.** El
interceptor de 401 llamaba `refreshTokens()` sin ninguna deduplicación, así
que en cada expiración del access token TODAS las peticiones en vuelo en ese
instante (el polling de 20s de `NotificacionesBell` + la revalidación SWR de
la sección abierta) recibían 401 a la vez y cada una disparaba su propio
`POST /auth/refresh` con el MISMO refresh token.

Evidencia directa, no hipótesis:

- **Reproducido con curl**: 3 `POST /auth/refresh` concurrentes con el mismo
  refresh token devolvieron los 3 un 200 (el backend no invalida el refresh
  token al usarlo, no hay rotación) y el set de sesiones del usuario en Redis
  pasó de 11 a 14 — una sesión nueva por cada renovación redundante, porque
  `_emitir_tokens` llama `core/sessions.py::registrar_sesion` siempre.
- **Huella del incidente real del usuario en Redis**: `GET
  /usuarios/{admin_sistema}/sesiones` mostró 3 sesiones con el MISMO user
  agent de navegador y `ts_inicio` a 3 milisegundos una de otra
  (`15:12:54.056`, `.058`, `.059`) — exactamente 3 renovaciones simultáneas
  desde una sola pestaña, coincidiendo con los 3 endpoints reportados. Esas
  son las "sesiones fantasma" que inflaban la lista de "Mis sesiones"
  (Módulo 1.4).

Además de las sesiones fantasma, la estampida traía dos riesgos reales: las N
escrituras a `tokenStorage` se pisan entre sí (access y refresh se guardan en
dos `setItem` separados, un entrelazado desafortunado deja un par mezclado), y
`_registrar_fallo_refresh` suspende la cuenta ENTERA a los 3 fallos de refresh
— una estampida de 3 alcanza ese umbral de un solo golpe en vez de a lo largo
de 3 incidentes distintos.

**Corregido en el punto central, `apps/shared-ui/src/api/client.ts`** (un solo
archivo, hereda a las 3 apps — no se parcheó ningún componente por separado):

1. **Single-flight** (`renovarUnaSolaVez()`): una única promesa de renovación
   en vuelo, compartida por todas las peticiones que chocaron con el mismo
   401. N peticiones → 1 `/auth/refresh` → 1 sesión nueva.
2. **Reintento sin renovar** cuando otra petición ya renovó mientras esta
   viajaba: `apiFetch` captura el access token con el que salió y, si al
   volver con 401 ya no es el vigente, reintenta directo sin gastar una
   renovación de más.
3. **Fallo de red ya no cierra la sesión**: `refreshTokens()` solo llama
   `tokenStorage.clear()` cuando el backend RECHAZA el refresh token
   (`!response.ok`); si el `fetch` revienta por red (backend caído, wifi
   cortado) devuelve `false` sin borrar nada — antes un corte transitorio en
   una de las N renovaciones concurrentes borraba los tokens de todas las
   demás en vuelo, que es el camino por el que un 401 podía terminar en un
   cierre de sesión visible en vez de autocurarse.

**Nota de diseño, para no reabrirlo**: un 401 en el log de red al expirar el
token sigue siendo esperado — `apiFetch` es reactivo (pide, recibe 401,
renueva, reintenta), no renueva de forma proactiva antes de que expire. Lo que
se corrigió no es que aparezca UN 401, es que aparecieran N en paralelo con N
renovaciones detrás. Cambiar a renovación proactiva (mirar el `exp` del token
antes de cada petición) sería un rediseño aparte, no hacía falta para este bug.

**Test de regresión**: `apps/web-interno/src/apiClient.test.ts` (nuevo, 4
casos). Vive en `web-interno` y no en `shared-ui` porque `shared-ui` no tiene
infraestructura de tests propia (solo lint, §5) y se consume como fuente TS.
Confirmado que el test REPRODUCE el bug: revirtiendo temporalmente el fix, el
caso de concurrencia falla con `expected 3 to be 1` — los 3 refresh de la
estampida.

**Verificación real en navegador** (`web-interno`, cuenta `admin_sistema`,
`+593900000099`): en vez de esperar los 15 min de TTL se invalidó la firma del
access token vigente desde la consola (mismo 401 del backend, refresh token
intacto). Dos rondas:

- Abrir el detalle de un usuario (dispara `/accesos` y `/sesiones` en
  `Promise.all`): los 2 dieron 401 → **un solo** `POST /auth/refresh` 200 →
  los 2 reintentos 200. El set de sesiones en Redis pasó de 9 a 10, no a 11.
- El trío exacto del reporte: `/usuarios?limit=20&offset=0` y
  `/notificaciones/mias` con 401 concurrentes → **un solo** `/auth/refresh`
  200 → ambos reintentos 200. Sin banner de error ni pantalla rota.

**Regresión**: `npm run build` ✅, `npm run lint` 0 errores (los mismos 3
warnings preexistentes de `useEffect` en `ParametrosGlobales`/`PoliticasAuth`/
`PoliticasSeguridad`), `npm run test` **27/27** en `web-interno` (subió de 23
por los 4 casos nuevos, ningún test preexistente cambió); `npm run lint`
limpio en `shared-ui`. **Backend sin tocar**, así que no se re-corrió `pytest`
(última corrida registrada: 346 passed + 8 skipped, §14).
