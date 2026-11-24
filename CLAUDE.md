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
| Captación (`operativo_captacion.md`) | CU-O01 (postulación conductor, con carga real de documentos + revisión en Captación, aprobar/rechazar), CU-O02 (registro pasajero/login) | La carga de documentos de postulación dejó de ser backlog — cerrada de extremo a extremo, ver §26.3 |
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
     filtra bien, y borrándolo después). **Desactualizado desde §26.3**:
     `documentos` hoy tiene 162 registros reales — primero por
     `seed_solicitudes_demo.py` (140) y después por la carga de documentos
     de postulación, que dejó de ser backlog. Este párrafo se conserva como
     registro histórico de por qué el dashboard salió vacío en su momento.
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
| Bloqueo automático de operaciones por documentación vencida | CU-O01/CU-O03 | **Decisión operativa pendiente de la cooperativa, no un olvido** (ver §26.3): afecta la capacidad de un socio de trabajar. Hoy solo hay advertencia visible al conductor y al personal interno, sin bloquear ninguna acción — no activarlo sin pedido explícito |

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

### 8.6a Límites de memoria del stack Docker (techo total 7-8GB)

Pedido explícito del usuario: con 24GB de RAM totales y otras apps abiertas
en simultáneo, el stack completo llegó a verse en 10GB — sin ningún techo,
Mongo en particular (WiredTiger reserva por defecto ~50% de la RAM que ve
el contenedor) puede crecer indefinidamente. **Detalle técnico importante**:
`deploy.resources.limits` en Compose se ignora en silencio fuera de modo
Swarm — el límite real y efectivo en `docker compose up` normal es
`mem_limit` a nivel de servicio (fuera de `deploy`), que es lo que se usó
acá.

| Servicio | `mem_limit` | Por qué |
|---|---|---|
| `mongo` | 2200m | El de mayor volumen real (1.3M+ viajes NYC sembrados) — más margen. `--wiredTigerCacheSizeGB 1` explícito en el `command` (sin esto, el caché apunta a ~50% de lo que ve el contenedor); deja ~1.2GB para conexiones/índices/oplog. |
| `clickhouse` | 1400m | Segundo en volumen real (tablas `bronze_*`/`fact_*`). Uso real medido bajo carga (DAG corriendo en paralelo): 350-450MB — 3x de margen real. |
| `airflow-scheduler` | 1300m | Con `LocalExecutor` este contenedor **ejecuta las tareas por fork()** (no solo agenda) — es el componente de Airflow con más variabilidad de memoria bajo carga real (ETL en chunks de `pymongo`/`clickhouse-connect`). |
| `airflow-webserver` | 1000m | Bajado también el **número de workers gunicorn** de 4 (default de Airflow) a 2 vía `AIRFLOW__WEBSERVER__WORKERS: "2"` — cada worker carga su propia copia del DAG bag, 4 workers multiplicaban el consumo sin ningún beneficio real (un solo usuario, sin concurrencia de navegador). Con 800m el proceso quedó estable en 99.3% bajo carga real (sin OOM, pero sin margen de verdad); 1000m es el primer nivel con margen real verificado (~87% bajo Grid view + 3 DAGs disparados en simultáneo). |
| `airflow-db` (Postgres, metastore) | 400m | Solo guarda DAG runs/task instances — dataset pequeño para este volumen de metadata. |
| `backend` | 500m | FastAPI/Uvicorn de un solo worker, 107MB en frío — margen generoso para picos de request concurrente. |
| `redis` | 150m | Cache de posiciones/sesiones/colas de oferta, datos pequeños y con TTL corto. |
| `pocketbase` | 150m | Binario Go liviano, solo sirve el dataset crudo NYC de solo lectura. |
| `mongo-init` / `airflow-init` | 300m / 400m | One-shot (salen tras `rs.initiate`/`db migrate`), límite defensivo — no cuentan contra el presupuesto porque no quedan vivos en operación normal. |

**Total (8 servicios persistentes): 7100MB (~6.93GB)** — dentro del rango
7-8GB pedido incluso si todos llegaran a su techo a la vez (no pasa en la
práctica). Uso real medido en operación normal (login + navegación en
`web-interno`, sin DAGs corriendo): **~2.8GB total**.

**Ajuste real durante la verificación** (documentado porque cambia el
razonamiento inicial, no solo el resultado): la primera pasada dejó
`airflow-webserver` en 900m — bajo carga real (login + Grid view de un DAG)
llegó a 94.8%, y con un DAG pesado (`dag_viajes_core`) disparado en
paralelo llegó a 99.3% del límite. La causa no era "poca memoria" sino que
Airflow arranca **4 workers gunicorn por defecto**, cada uno con su propia
copia del DAG bag parseado — bajar a 2 workers (config de arriba) resolvió
la causa real, y subir el límite a 1000m (compensado bajando `clickhouse`
de 1600m a 1400m, que sobraba) dejó un margen real verificado, no solo
teórico.

**Verificación real hecha**: stack completo reiniciado desde cero
(`docker compose down && docker compose up -d`) con los límites finales;
los 8 servicios llegaron a `healthy`/`Up` sin reintentos. Bajo carga real
simultánea — Grid view de Airflow abierta en el navegador +
`dag_viajes_core` + `dag_flota_gold` + `dag_disparar_viajes_programados`
(éste corriendo solo cada 2 min de fondo) disparados a la vez — **las 3
corridas terminaron en `success`, sin OOM-kill, sin reinicios**
(`docker inspect ... OOMKilled=false restarts=0` confirmado en el
contenedor de `airflow-webserver`, el más ajustado de los 8). Verificado
también que `--wiredTigerCacheSizeGB 1` se aplicó de verdad:
`db.serverStatus().wiredTiger.cache["maximum bytes configured"]` = exactos
1073741824 bytes (1GB), no el default.

**Respaldo adicional — techo global de la VM de WSL2** (Windows, Docker
Desktop): esto es un límite duro sobre TODO Docker Desktop, independiente
de si algún contenedor individual se pasa de su `mem_limit`. Archivo
`%UserProfile%\.wslconfig` (no existe todavía en esta máquina — crearlo si
se quiere este respaldo):

```ini
[wsl2]
memory=8GB
```

Tras crear/editar el archivo, reiniciar WSL2 completo desde PowerShell
(fuera de cualquier terminal que dependa de WSL) para que tome efecto:

```powershell
wsl --shutdown
```

Docker Desktop vuelve a levantar su VM con el nuevo techo la próxima vez
que arranque. Este límite es independiente del reparto de `mem_limit` por
servicio de arriba — ambos se complementan, ninguno reemplaza al otro.

### 8.6b Regresión real (2026-08-18): `dag_viajes_core` sin poder correr por techo de memoria de ClickHouse — sin resolver, decisión de parar tomada con el usuario

Encontrado durante la preparación de una sesión de demo (levantar el stack + verificar frescura de
los informes de Airflow antes de presentar). `dag_viajes_core` llevaba **3 corridas diarias
consecutivas fallando** (2026-08-15, 16, 17) con `MEMORY_LIMIT_EXCEEDED` real de ClickHouse en la
tarea `silver_y_cuarentena` — la consulta de deduplicación contra `fact_viaje`/`fact_ciclo_viaje`
(~1.3M filas cada una) ya no cabe en el margen que dejaba el `mem_limit` de 1400m documentado en
§8.6a. Efecto real: `fact_viaje`/`fact_ciclo_viaje` (y `rpt_tiempo_asignacion`/`rpt_tasa_cancelacion`
que dependen de ellas — Despacho táctico, Confiabilidad del Servicio estratégico) quedaron
congeladas en datos del 2026-08-14, 4 días desactualizadas al momento del hallazgo. Los otros 5 DAGs
de dominio (finanzas, captación, cumplimiento, mantenimiento, flota) seguían corriendo bien —
esto es un problema aislado de este DAG en particular, no del stack completo.

**2 intentos de arreglo, ninguno resolvió el problema — decisión tomada con el usuario de parar ahí
en vez de seguir escalando**, documentado explícitamente para que una sesión futura no vuelva a
intentar los mismos 2 caminos sin saber que ya se probaron y fallaron:

1. **Subir `mem_limit` del contenedor** (1400m → 1700m, con permiso explícito del usuario, ver el
   comentario junto a `mem_limit` del servicio `clickhouse` en `docker-compose.yml`). **No alcanzó**:
   ClickHouse resuelve `max_server_memory_usage=0` (default) contra
   `max_server_memory_usage_to_ram_ratio` (0.9 de fábrica) del RAM que ve el contenedor — al subir el
   `mem_limit`, ese techo interno sube proporcionalmente con él (de ~1.23GiB a ~1.49GiB, siempre
   ~90% del límite), así que el margen real para una consulta nueva casi no crece por más que se
   suba el contenedor.
2. **Techo absoluto de memoria + cachés reducidas** (`clickhouse/config.d/memoria.xml`, nuevo,
   montado en `docker-compose.yml`): `max_server_memory_usage` fijado en 1400MB (en vez de dejarlo
   en el 90% relativo) y `uncompressed_cache_size`/`mark_cache_size` bajados de sus defaults de
   fábrica (8GB y 5GB — nunca sirvieron para limitar nada en este entorno) a 300MB cada uno, para
   que las cachés no se comieran el margen nuevo. **Tampoco alcanzó**: el RSS en reposo de
   ClickHouse siguió en ~1.36GiB incluso con las cachés casi vacías — confirma que el consumo grande
   **no viene de las cachés** como se asumió al diseñar este segundo intento, viene de otra parte
   (candidato más probable: metadata/índices primarios en memoria de las tablas MergeTree grandes —
   `fact_viaje`, `fact_ciclo_viaje`, `bronze_viaje_historico_nyc`, `bronze_ciclo_viaje`, todas con
   cientos de miles a más de un millón de filas — MergeTree mantiene esto siempre en memoria por
   diseño, independiente de `mark_cache_size`/`uncompressed_cache_size`; no confirmado con certeza,
   solo descartado lo que sí se probó). El archivo de config queda aplicado (no hace daño, las
   cachés más chicas no perjudican nada en este entorno) pero **no resuelve el problema real**.

**Decisión explícita del usuario tras el segundo intento fallido**: parar ahí en vez de seguir
escalando (la alternativa ofrecida — subir a ~2.2GB de techo con más margen real, sin garantía de
que alcance — se dejó sin intentar, decisión consciente de no seguir arriesgando la estabilidad del
entorno justo antes de una presentación). Los 3 `DagRun` que quedaron atascados reintentando
(2026-08-15, 16, 17) se resolvieron a `FAILED` limpiamente vía el ORM de Airflow directamente (mismo
patrón ya usado en §8.8), sin dejar reintentos automáticos corriendo de fondo.

**Para la próxima sesión que retome esto**: el gap real de frescura es de 4+ días en
`fact_viaje`/`fact_ciclo_viaje` únicamente (crece un día más cada día que pase sin resolver esto,
mientras el resto de tablas Gold sigue sano). Antes de intentar un tercer arreglo, medir primero
cuánta memoria ocupan realmente las partes/índices de esas 4 tablas grandes (`system.parts`,
columna `primary_key_bytes_in_memory`/`marks_bytes`) en vez de seguir adivinando por descarte — eso
habría ahorrado los 2 intentos de esta sesión. Alternativa a considerar sin tocar memoria: correr
`OPTIMIZE TABLE ... FINAL` sobre esas 4 tablas para consolidar partes pequeñas en menos partes
grandes (menos partes = menos índices primarios separados en memoria) — no probado en esta sesión,
queda como hipótesis para la próxima.

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

## 16. Sistema de diseño visual (agosto 2026) — rediseño completo de las 3 apps

Pedido explícito del usuario: adoptar el sistema de diseño de una referencia
visual (`app-shell.jsx`, un componente React de ejemplo, solo como fuente de
tokens/estilo — su estructura de componentes no se copió). Regla explícita
del pedido: **solo aspecto visual, nada de lógica/comportamiento/endpoints**.
Mismo patrón de rollout que ya funcionó en el rediseño de dashboards
tácticos (§5.1): tokens + componentes base de `shared-ui` primero, un piloto
de verificación en 2-3 pantallas por app, reporte antes de dar por bueno el
resto (que se propaga solo, al vivir en componentes compartidos).

### 16.1 Tokens adoptados (`apps/shared-ui/src/tokens.css`)

| Token | Valor |
|---|---|
| Tipografía | `Barlow` (Google Fonts, `@import` en `tokens.css`), pesos 400/500/600/700, para toda la app |
| Escala de texto | `--font-size-xs/sm/md/lg/xl/2xl` = 12/13/14/16/22/26px (antes 14/16/20/28/36 en rem) — `--font-size-xs` es nuevo |
| Radios | `--radius-sm/md/lg` = 8/10/12px (antes 6/10/16) |
| Espaciado | `--space-1..6` = 6/10/14/18/24/30px (antes 4/8/12/16/24/32) |
| Altura de control | `--control-height: 38px` (nuevo) — aplicado a `Button`/`TextField`/`Select` |
| Acento | `--color-accent: #f2a413` (ámbar/dorado) en ambos temas — antes azul en claro (`#2a78d6`) y celeste en oscuro |
| Chips de estado | `--color-{success,warning,danger,neutral}-bg` (nuevos) — fondo suave + texto del color semántico, ver `Badge.tsx` |
| Sidebar (fija, independiente del tema) | `--color-sidebar-bg: #101a26`, `--color-sidebar-hover/active-bg: #1b2a3a`, rail de 3px con `--color-accent` en el ítem activo |

**Deliberadamente NO tocado**: la paleta categórica de gráficos
(`--chart-series-1..8`) y los colores de estado usados por
`CategoryBarChart`/`TrendLineChart`/`KpiCard` (`--status-good/warning/
serious/critical`) — es la paleta validada por la skill `dataviz` (script
`validate_palette.js`), documentada en este mismo archivo como "reservada,
nunca reusada". El nuevo acento ámbar es independiente de esa paleta, no la
reemplaza ni se mezcla con ella.

**Mecanismos existentes preservados, no reemplazados** (como exigía el
pedido): el toggle claro/oscuro (`theme.ts`, `data-theme` en `<html>`) sigue
funcionando igual — los nuevos valores de color se mapearon sobre los MISMOS
nombres de variable, nunca un mecanismo nuevo. La densidad de tablas
(`densidad.ts`, `--table-cell-padding-y/x`) tampoco se tocó. El patrón de
layout Z/F de los dashboards (`DashboardLayout.tsx`) no cambió su
disposición de bloques, solo hereda la piel visual nueva vía los mismos
tokens.

### 16.2 Componentes de `shared-ui` actualizados

- `Button`/`TextField`/`Select`: altura fija `--control-height`, radio y
  tipografía vía tokens (sin cambio de props/API).
- `Badge` y el chip de modo de `DetailPanel`: de píldora sólida + texto
  blanco a fondo suave + texto semántico (`tonoEstilo`/`estiloModo`, mismo
  patrón, sin cambiar la prop `tono`/`modo` que ya consumían ~35+ pantallas).
- `DataTable`: encabezado en mayúsculas pequeñas (`--font-size-xs` +
  `letter-spacing`), fila con hover sutil (`DataTable.css`, nuevo — no se
  puede expresar `:hover` en estilo inline), scroll oculto visualmente en
  contenedores con `altoMaximo` (clase `.no-scrollbar`, ver 16.3).
- `AppShell`: indicador de riel (3px, color de acento) en el ítem de
  navegación activo; fondo de sidebar activo cambia de blanco-sólido a
  tono oscuro de hover; scroll del nav oculto visualmente.
- `KpiCard`/`Card`/`CategoryBarChart`/`TrendLineChart`: sin cambios de
  código — ya eran 100% tokens, heredan el sistema nuevo automáticamente.
- **Overrides de acento por app eliminados**: `web-conductor` (`#b5760a`) y
  `web-interno` (`#14161a`) tenían su propio `--color-accent` en
  `index.css`, rompiendo la "misma familia visual" entre las 3 apps que
  pide este rediseño — se quitaron, las 3 apps comparten ahora el mismo
  ámbar.

### 16.3 Scrollbars ocultas, scroll funcional intacto

Utilidad global `.no-scrollbar` en `tokens.css` (`scrollbar-width: none` +
`-ms-overflow-style: none` + `::-webkit-scrollbar{display:none}`) —
`overflow` sigue siendo `auto` en todos los casos, nunca `hidden`. Aplicada
al `<nav>` del sidebar (`AppShell.tsx`) y al contenedor de `DataTable` con
`altoMaximo` (`AuditoriaAdmin.tsx`, el único que la usa hoy). El propio
`.shell-sidebar` (contenedor exterior) recibió el mismo tratamiento
directamente en `AppShell.css`. Verificado en navegador real: la tabla de
Solicitudes y el sidebar siguen recibiendo scroll con mouse/rueda sin
mostrar la barra.

### 16.4 Verificación real (piloto, antes de dar el rollout por completo)

Pantallas verificadas en navegador real contra el stack corriendo, con
`getComputedStyle` (no solo inspección visual):

- **web-interno**: Solicitudes (tabla simple) — encabezados uppercase 12px,
  chip `OBSERVADA` con fondo `rgba(217,138,11,.16)` y texto `#D98A0B`
  (antes píldora sólida blanca); botones `Nuevo`/`Buscar`/`Salir` a
  exactamente 38px de alto, radio 10px, fuente Barlow. Modal de edición
  (`DetailPanel`) — radio 12px, chip "Modo: Edición" con el mismo
  tratamiento de fondo suave. Panel de Flota (táctico, dashboard con
  KPI+chart) — etiqueta KPI 13px, valor 26px/700, rail del ítem activo del
  sidebar en `rgb(242,164,19)` (`#F2A413`), fondo del ítem activo
  `rgb(27,42,58)` (`#1B2A3A`). Tema oscuro confirmado: `bg` pasa a
  `rgb(12,20,29)` (`#0C141D`), texto a `rgb(231,237,245)` (`#E7EDF5`),
  sidebar se mantiene en el MISMO `rgb(16,26,38)` que en tema claro
  (confirma que la sidebar es fija, no reactiva al tema).
- **web-pasajero**: login — botón "Entrar" y campo de contraseña a 38px,
  botón en `rgb(242,164,19)`, fuente Barlow confirmada en `body`.
- **web-conductor**: login — mismos 4 checks (fuente, acento, alto de
  control) confirmados iguales a `web-pasajero`, prueba directa de que las
  3 apps ya comparten el mismo acento tras quitar su override propio.

**Regresión completa** (las 3 apps + backend, tal como pidió el usuario
pese a ser un cambio solo visual): `npm run build` ✅ en las 3 apps
(`tsc -b` sin errores — ningún cambio de props rompió un consumidor),
`npm run lint` limpio en `shared-ui` + las 3 apps (mismos 3 warnings
preexistentes de `useEffect`, no nuevos), `npm run test` **10/10**
(`web-pasajero`), **5/5** (`web-conductor`), **27/27** (`web-interno`) —
sin ningún test roto por el cambio de estructura de `Badge`/`DetailPanel`/
`DataTable`. `pytest` backend **346 passed + 8 skipped** (sin cambios,
backend no se tocó, corrido igual para confirmarlo).

### 16.5 Rollout completo — aprobado y propagado (cierre)

El usuario aprobó el piloto sin objeciones, incluida la decisión de quitar
los overrides de acento propios de `web-conductor`/`web-interno` (ver
16.2). El cambio de tokens se propaga automáticamente a las ~35+ pantallas
que reutilizan los componentes de `shared-ui` — no hizo falta tocar cada
pantalla una por una.

**Ajuste real encontrado durante el rollout, no solo en el piloto**: el
grep de colores hexadecimales fuera de tokens (16.5 original) había
marcado `Catalogos.tsx`/`Integraciones.tsx`/`Respaldos.tsx` como "sin
relación, no requieren cambio" — expresión demasiado apresurada. Los 3
usan `color: activa ? "#fff" : "var(--color-text)"` en su pestaña de
filtro activa, con fondo `var(--color-accent)` — con el acento nuevo
(ámbar brillante `#f2a413`), texto blanco sólido da bajo contraste, un
problema real de accesibilidad que no existía con el acento azul/oscuro
anterior. Corregido en los 3 archivos a `var(--color-accent-contrast)`
(el mismo token que ya usa `Button` variant primary para este propósito
exacto) — mismo patrón, cero tokens nuevos.

**Verificación real por tipo de pantalla** (pedida explícitamente antes de
dar el rollout por cerrado, con `getComputedStyle`, no solo inspección
visual):

| Tipo | Pantalla | Confirmado |
|---|---|---|
| Work panel | Mantenimiento (`web-interno`) | ActionBar a 38px/10px real; hover de fila real disparado con `computer{action:"hover"}` (no solo CSS leído) → `rgb(24,36,47)` (`--color-row-hover` oscuro) |
| Dashboard Z | Flota (táctico) | KPI 13px/26px-700, rail del ítem activo en `rgb(242,164,19)` (piloto, 16.4) |
| Dashboard F | Auditoría (táctico) | `.dashboard-f-row` sigue en `320px 608.8px` (mismo ratio de siempre, la piel visual cambió, la disposición no), encabezado de tabla `uppercase 12px` |
| Formulario de confirmación en 2 pasos | Gobernanza de datos → Anonimizar | Diálogo real abierto (búsqueda de usuario real → botón "Anonimizar" → modal con campo de texto exacto) — radio 12px, Barlow, input 38px, botón "Anonimizar de forma permanente" a 38px con `rgb(242,164,19)`. Cancelado sin enviar, no se anonimizó ninguna cuenta real |
| Overlay de mapa — pasajero | Panel "¿A dónde vamos?" (`web-pasajero`) | Panel flotante blanco, radio 10px, Barlow; botón "Solicitar taxi" 38px en `rgb(242,164,19)` |
| Overlay de mapa — conductor | Panel "Mi turno" (`web-conductor`) | Barlow confirmado, botón "Iniciar turno" 38px en `rgb(242,164,19)` |

**Regresión final** (tras los 3 archivos corregidos): `npm run build` ✅ en
`web-interno` (`tsc -b` limpio), `npm run lint` limpio en `shared-ui` + las
3 apps (mismos 3 warnings preexistentes), `npm run test` **27/27**
(`web-interno`), **10/10** (`web-pasajero`), **5/5** (`web-conductor`),
`pytest` backend **346 passed + 8 skipped** (backend no tocado en todo el
bloque, corrido de nuevo para confirmarlo). **Con esto, el rediseño visual
completo (shared-ui + las 3 apps + modales/formularios) queda cerrado.**

## 17. Ronda de mejoras de claridad y profundidad analítica (agosto 2026) — los 4 puntos cerrados

Pedido explícito del usuario tras evaluar personalmente el rediseño visual (§16): 4 puntos
independientes, con distinto nivel de aprobación requerido cada uno. Reporte por punto, no
esperar a los 4.

### 17.1 Punto 1 — Unificación de lenguaje/terminología — cerrado y verificado

Auditoría completa de texto visible al usuario en las 3 apps (delegada a un agente Explore en
background, que devolvió un informe estructurado archivo/línea) — reportada primero como tabla
de propuestas, **sin aplicar nada hasta la aprobación explícita del usuario**. Aprobación real:
"aplica todos los reemplazos de tu tabla EXCEPTO FuenteBadge — ese se mantiene igual
(MongoDB/ClickHouse), es un recurso de transparencia técnica deliberado, no un descuido de
lenguaje."

**Cambios aplicados** (solo texto visible — JSX/props de string, nunca nombres de variable,
interfaz, ruta de API o campo de esquema):

- **Nombres de rol crudos → nombres legibles**: nuevo `apps/shared-ui/src/roles.ts`
  (`NOMBRE_ROL`/`nombreRol()`, 13 roles) — vive en `shared-ui` (no en `web-interno`) porque
  `PerfilPropio.tsx` (compartido por las 3 apps, "Mi cuenta"/"Mi perfil") también lo necesitaba.
  Aplicado en `Usuarios.tsx` (filtro de rol, checkboxes, columna Roles),
  `FeatureFlags.tsx` (checkboxes, columna Roles) y `PerfilPropio.tsx` (badges de rol propio —
  este último no lo había detectado el agente de auditoría, se encontró al implementar por un
  test que fallaba mostrando `jefe_mantenimiento` crudo en "Mi cuenta").
- **"feature flag(s)" → "funcionalidad(es) activable(s))"**: `FeatureFlags.tsx` (título, texto,
  tooltips, diálogos, mensajes de error) + una mención en `AuditoriaAdmin.tsx`.
- **"onboarding" → "altas"**: `PanelCrecimiento.tsx` (estratégico) y `PanelCaptacion.tsx`
  (táctico) — solo etiquetas/títulos visibles, los identificadores internos
  (`SIN_ONBOARDING`, `pct_conversion_onboarding`, etc.) se dejaron intactos a propósito, son
  código, no texto.
- **"Share demanda/capacidad" → "Participación en demanda/capacidad"**: tabla de
  `PanelRentabilidad.tsx`.
- **"key" → "clave"** (contexto de credencial de Google Maps): `Integraciones.tsx` (columna,
  botón, título de diálogo, label, mensaje de error) — incluyó un ajuste colateral menor en la
  misma oración ("sin reiniciar el backend" → "sin reiniciar el sistema"), disclosed al usuario
  como tidy-up puntual, no como categoría nueva de reemplazo.
- **"pipeline" → "proceso de carga de datos" / "proceso de datos"**: `ConfiguracionAlertas.tsx`,
  `Indicadores.tsx`, `PanelPlataforma.tsx` (táctico), `PanelCapacidades.tsx` (estratégico),
  `PanelGobernanza.tsx` (estratégico), `VersionSistema.tsx`.
- **"cuarentena" → "registros rechazados"** (donde es una etiqueta/título de UI, nunca el nombre
  de columna Mongo/ClickHouse real): `PanelPlataforma.tsx`, `PanelCapacidades.tsx` — incluye
  títulos de gráfico, columnas de tabla, filtros.
- **"DAG" → "Dominio"** (donde el usuario ve el filtro/columna, el `dag_id` interno no cambió):
  `PanelPlataforma.tsx`, `PanelCapacidades.tsx`.
- **"Redis — hit rate" → "Redis — % de aciertos de caché"**: `Monitoreo.tsx`.
- **"dataset mixto" → "datos mixtos"**: `PanelIntegridadFinanciera.tsx`.

**Deliberadamente NO tocado** (hallazgos del agente sin una redacción de reemplazo ya aprobada
en la tabla original — quedan abiertos, no resueltos ni descartados): "webhook", "backend" en
aislado (fuera del ajuste colateral de Integraciones), nombres crudos de tabla `rpt_*`/Mongo en
textos de `NotaLimitacion`, "API"/"endpoint", "observabilidad", "GPS spoofing". Si se retoma
este punto, no asumir que ya se cubrieron.

**Verificación real en navegador** (cuentas `gerencia`, `admin_sistema`, `staff-verificacion`),
confirmando cada cambio con `get_page_text`/`read_page` contra el stack real, no solo lectura de
código: Crecimiento ("CONVERSIÓN DE ALTAS"), Rentabilidad ("PARTICIPACIÓN EN DEMANDA/CAPACIDAD"),
Usuarios (filtro de rol y columna Roles con nombres legibles), Funcionalidades ("Funcionalidades
activables"), Integraciones ("Rotar clave", "Nueva clave de API", columna "Clave", diálogo con
"sin reiniciar el sistema"), Mi cuenta (badge "Administrador del Sistema"), Monitoreo
("REDIS — % DE ACIERTOS DE CACHÉ"), Plataforma táctico y Capacidades estratégico ("% REGISTROS
RECHAZADOS"/"Dominio"/"Registros rechazados por dominio"). Regresión: `npm run test` **27/27**
en `web-interno` (4 aserciones de `App.test.tsx` actualizadas para los nuevos textos, sin
tocar las 2 aserciones de JSON crudo del toggle "Ver antes/después" de Auditoría, que
correctamente muestran el valor almacenado tal cual). `npm run build`/`lint` limpios en las 3
apps + `shared-ui`.

### 17.2 Punto 2 — Descripción + interpretación en KpiCard — cerrado y verificado

Aprobado tal como quedó, "incluida la consolidación de tarjetas separadas en una sola."
`KpiCard` (`shared-ui`) ganó 3 props opcionales: `descripcion?: string` (texto estático,
siempre disponible, explica qué mide el KPI), `interpretacion?: string` (solo cuando existe una
comparación real período-a-período en el backend — nunca fabricada) e
`interpretacionTono?: "exito" | "peligro"`. 100% retrocompatible (~82 call sites existentes sin
tocar salvo donde se agregó el contenido nuevo).

**Regla aplicada sin excepción**: `interpretacion` solo se pasó donde el backend ya expone un
campo `variacion_*_pct` real — los 8 dashboards estratégicos de dominio + Rentabilidad (los 9
tienen exactamente ese campo, confirmado por esquema, ver `backend/src/*/schemas.py`) lo
recibieron; los 9 dashboards tácticos y `Monitoreo.tsx` **no tienen ningún campo de variación en
el backend** (confirmado, no asumido) — esos KpiCard solo ganaron `descripcion`, nunca una
interpretación inventada. Reutilizado `tonoVariacion()`/`variacion()` de
`sections/estrategico/formato.ts` tal cual, sin reinventar la lógica de qué dirección es buena.
`TableroEjecutivo.tsx` quedó fuera a propósito — no usa `KpiCard`, tiene su propia tarjeta con
mini-sparkline y ya muestra `variacion_pct` por tarjeta desde el backend.

### 17.4 Punto 3 — Panel táctico "Rendimiento de Conductores" — cerrado y verificado

Propuesta aprobada tal como se presentó: dashboard táctico dedicado (no una extensión de
Despacho — esa pantalla es sobre la salud del pipeline de despacho a nivel flota/zona, esta es
sobre identidad y comparación individual de cada socio), gateado a `coordinador_operaciones`,
ventana reciente por defecto con el histórico completo solo como filtro opcional.

**Hallazgo de investigación previo a construir**: ningún `rpt_*` agregaba por conductor.
`fact_viaje`/`fact_recaudacion`/`fact_liquidacion`/`fact_ubicacion_flota` ya tenían
`conductor_id`, pero los `rpt_*` que se construyen sobre ellas siempre colapsan esa dimensión.
Además, `fact_ciclo_viaje` (la única tabla con estados de cancelación) nunca tuvo
`conductor_id` — se omitió a propósito al construirla — y las calificaciones nunca salieron de
Mongo hacia ClickHouse.

**Verificación de compatibilidad de esquema, ANTES de tocar nada** (pedida explícitamente por
el usuario, mismo chequeo que ya se hizo con éxito al agregar `congestion_surcharge`): grep de
cada consumidor real de `fact_ciclo_viaje`/`fact_viaje` en `analytics/` y `backend/` — los 3
sitios reales usan columnas nombradas explícitas (nunca `SELECT *`), el mecanismo de inserción
(`medallion.py::cargar_gold_idempotente`/`insertar_gold_chunk`) construye `column_names` desde
las claves del propio diccionario de cada fila (nunca posicional), y cero código de `backend/`
consulta estas 2 tablas directamente. Confirmado seguro antes de cualquier `ALTER TABLE`.

**Cambios de esquema** (2 columnas nuevas, Nullable, ver `analytics/plugins/medallion.py`):
`fact_ciclo_viaje.conductor_id` (para poder contar cancelados por socio) y
`fact_viaje.calificacion_puntaje` (para el promedio de calificación por socio) —
`dag_viajes_core.py` extrae ambos campos ahora. **Bug real encontrado durante la primera
corrida real** (no en teoría): la extracción Bronze (`bronze_viajes`/`bronze_ciclo_viaje`)
tiene su propio esquema, separado del Gold — se me olvidó agregar las 2 columnas ahí también,
y el primer intento de correr el DAG real reventó con
`Unrecognized column 'calificacion_puntaje' in table urbanflet_gold.bronze_viajes`. Corregido
agregando las mismas 2 columnas a los DDL de Bronze en `medallion.py`, con su propio
`ALTER TABLE ADD COLUMN` en vivo (mismo patrón, 4 tablas en total: 2 Bronze + 2 Gold).

**2 tablas `rpt_*` nuevas** (`analytics/plugins/indicadores.py`): `rpt_desempeno_conductor`
(periodo × conductor_id: completados, cancelados, % éxito, calificación promedio — combina
`fact_viaje` + `fact_ciclo_viaje` con un join de lectura en Python, mismo patrón ya usado por
`dag_flota_gold` para resolver `estado_servicio`) y `rpt_ingreso_conductor` (periodo ×
conductor_id: bruto/comisiones/neto, de `fact_liquidacion`) — 2 tablas y no 1 porque tienen
grano de periodo distinto en origen (viaje vs. ciclo de liquidación semanal, ambas bucketadas a
mes). Nuevo endpoint `GET /viajes/panel-tactico/desempeno-conductores`
(`viajes/service.py::obtener_panel_desempeno_conductores`) las combina por
`(conductor_id, periodo)`, resuelve nombre desde Mongo (mismo patrón que
`recaudacion.service.obtener_nombres_conductores`).

**Hallazgo real de la verificación en navegador (no solo en ClickHouse), que cambió el diseño
del backend**: con `meses=3` (ventana por defecto), el KPI seguía mostrando ~247K viajes por
socio — la advertencia de concentración NO se encendía. Causa real: este entorno tiene un salto
de 5 años sin ningún dato entre el rango NYC (2021-01/02) y la operación real (2026-07+) — con
solo 3 periodos distintos en TOTAL en la tabla, "los 3 más recientes" (`ultimos_periodos`) son
los 3 únicos que existen, incluidos los 2 de NYC. La advertencia (`historico_completo`) nunca
detectaba este caso porque solo miraba el toggle del usuario, no si la concentración había
llegado igual al resultado. Corregido: `advertencia_concentracion_historica` ahora se enciende
también si algún conductor en el resultado YA FILTRADO supera un umbral real
(`UMBRAL_CONCENTRACION_NYC = 1000` viajes/periodo — señal del patrón de siembra, no una fecha de
corte arbitraria que dejaría de ser cierta con más historia real acumulada). Test de regresión
nuevo (`test_ventana_reciente_no_evita_la_advertencia_si_igual_incluye_nyc`) que fija este
comportamiento. El texto de advertencia en el frontend también se corrigió para no decir
"Histórico completo activado" cuando en realidad el toggle seguía en "Ventana reciente".

**Verificado con datos reales, en pantalla** (cuenta `staff-verificacion`, rol
`coordinador_operaciones`): con `meses=1` (ventana reciente, sin histórico) el panel aisló
correctamente a 1 solo socio real (`Conductor Prueba`, 2 viajes completados, calificación real
`5.0★`, sin advertencia); con `meses=3` reapareció la advertencia (corregida, con el texto
correcto) y los 5 socios de siempre a ~247K viajes cada uno del rango NYC. Requests reales
confirmadas en el log de red por cada cambio de filtro (`?meses=1&historico_completo=false` →
200, etc.). Backend: **350 passed + 8 skipped** (subió de 346), `ruff check` limpio. Frontend:
build/lint/test limpios en `web-interno` (27/27) + `shared-ui` lint.

### 17.5 Punto 4 — Drill-down en KPIs — CORREGIDO tras cierre inicial, ver 17.6

**El piloto descrito originalmente en esta sección ("Ver corridas fallidas" → botón → navega a
Plataforma táctico con `estado=FAILED`) NO era el requisito real** — el usuario lo dio por
construido, lo probó, y corrigió explícitamente: el patrón correcto es un **modal en la MISMA
pantalla** al hacer clic directo sobre la tarjeta del KPI (no un botón aparte, no navegación a
otra sección), aplicable a la mayoría de los KPIs de conteo del sistema, no a 1 solo caso.

El mecanismo `ir(id, filtro?)` + `filtroPendiente`/`consumirFiltroInicial`/`useFiltroInicial`
que esta sección documentaba **se retiró por completo** (`navegacion.ts` volvió a su forma
original, solo `ir(id)`) — quedó sin ningún consumidor real una vez migrado el piloto al nuevo
patrón (ver 17.6), y dejarlo vivo habría sido infraestructura muerta. Si esta sección aparece
en un grep histórico o en memoria de una sesión vieja, **no asumir que ese mecanismo sigue
existiendo** — fue reemplazado, no complementado.

### 17.6 Punto 4 corregido — `KpiDetalleModal` + primer lote (4 KPIs) — cerrado y verificado

**Investigación previa (agente Explore, sin construir nada)**: inventario exhaustivo de los 77
`<KpiCard>` reales del sistema (grep de las 3 apps) — 0 en `web-pasajero`/`web-conductor` (esas
apps no tienen dashboards, el patrón es exclusivo de `web-interno`, confirmado explícitamente
con el usuario); de los 77, ~26 son candidatos claros (conteo con una lista real de registros
ya accesible, en la misma pantalla o en otra ya construida), ~4 requieren solo pasar un filtro
nuevo a un endpoint ya existente (no un endpoint nuevo), ~40 no aplican (porcentaje/promedio/
texto, sin una fila real que sea "ese valor"), y los 7 de `Monitoreo.tsx` no aplican por ser
métricas de infraestructura (memoria de Mongo, etc.) sin ningún listado de negocio detrás.
`TableroEjecutivo.tsx` queda fuera — no usa `KpiCard`, tiene su propio patrón de tarjeta con
sparkline + navegación real ("Ver detalle"/"Ver táctico"), anterior a este punto y sin tocar.

**Componente nuevo — `KpiDetalleModal`** (`apps/shared-ui/src/components/KpiDetalleModal.tsx`):
mismo chrome visual que `DetailPanel` (backdrop, `role="dialog"`, `aria-modal`, tarjeta
redondeada) pero de solo lectura, sin la semántica de modo/edición. Genérico sobre `T`: recibe
`rows`/`columns`/`keyField` (reutiliza el tipo `Column<T>` de `DataTable`, ahora exportado) y un
slot `filtros` para controles de filtro — nunca decide qué datos mostrar ni cómo filtrarlos,
eso lo define cada pantalla que lo usa.

**`KpiCard` gana `onClick?: () => void`** (opcional, ninguno de los ~77 sitios existentes
cambia si no se pasa): con `onClick`, la tarjeta es `role="button"`, `tabIndex=0`, cursor
pointer, hover con borde de acento, `aria-label` con etiqueta+valor (accesible, no solo visual
— encontrado y corregido durante la verificación: la primera versión no tenía nombre accesible),
y un hint visible "Ver detalle →". Sigue siendo 100% presentacional — ninguna lógica de datos
entra al componente.

**Primer lote construido (4 KPIs, aprobado explícitamente)**:

| KPI | Pantalla | Fuente del modal | Request nueva |
|---|---|---|---|
| Viajes activos | Despacho (táctico) | `activos` ya en memoria — filtro "Estado" nuevo dentro del modal | No |
| Sin conductor hoy | Despacho (táctico) | `sinConductor` ya en memoria — filtro "Estado" (Sin conductor/Cancelado/Todos) | No |
| Socios en la ventana | Rendimiento de Conductores (táctico) | `filas` ya en memoria — filtro "Buscar por nombre" propio del modal | No |
| Corridas fallidas | Capacidades y Plataforma (estratégico) — **migración del piloto anterior** | `GET /plataforma/panel-tactico/corridas` (ya existente, sin parámetro nuevo) — única request nueva del lote, porque esta pantalla estratégica nunca tuvo las filas crudas en memoria, solo el conteo agregado | Sí, 1 sola, al abrir |

**Migración del piloto**: el botón "Ver corridas fallidas" + la navegación a Plataforma táctico
se eliminaron por completo — clic en la tarjeta ahora abre el modal en la misma pantalla
(Capacidades y Plataforma nunca cambia), con "Estado" preseleccionado en `FAILED` dentro del
modal. `PanelPlataforma.tsx` conserva su filtro "Estado" (útil por sí solo, manual) pero perdió
el `useFiltroInicial` que lo alimentaba desde afuera — ya no tiene ningún consumidor.

**Verificación real en navegador** (cuenta `staff-verificacion`, roles `coordinador_operaciones`
+ `responsable_plataforma` cubren los 3 paneles): clic real en las 4 tarjetas confirmó que el
modal abre EN LA MISMA pantalla (el `<h2>` de la sección nunca cambia) con las filas reales
correctas — "Socios en la ventana" mostró las 11 filas exactas de la tabla de abajo, filtrar por
"Juan" dentro del modal lo redujo a sus 2 filas reales sin afectar el filtro de la pantalla
(estado independiente); "Viajes activos"/"Sin conductor hoy" abrieron con 0 registros (estado
real del entorno en el momento) y su propio filtro "Estado" visible. Para "Corridas fallidas"
(en 0 reales en el entorno) se insertó TEMPORALMENTE 1 fila `FAILED` en ClickHouse — confirmado
en el DOM que el modal abre con esa fila, "Estado" en "Failed", y que ampliar a "Todos" la
mezcla con el resto de corridas reales (confirma el filtro reacciona) — fila borrada
inmediatamente después, confirmado `count()=0`. `npm run build/lint/test` limpios en
`web-interno` (27/27) + `shared-ui` lint. Backend no se tocó en este lote (los 4 KPIs reusan
endpoints ya existentes).

**Backlog identificado por la investigación, no construido — para lotes futuros por
aprobación explícita**: ~22 candidatos (a) restantes + ~4 candidatos (b) (requieren pasar un
filtro nuevo a un endpoint ya existente, no un endpoint nuevo) — ver el mensaje de propuesta
de esta sesión para el inventario completo por pantalla y la priorización por rol
(`coordinador_operaciones` y `supervisor_cumplimiento` primero, por uso operativo diario;
`gerencia` al final, uso de supervisión no de acción inmediata). No se guardó ese inventario
completo en este archivo — retomar pidiendo el detalle si una sesión futura continúa esto.

**Rollout aprobado por lotes tras confirmación manual del usuario sobre el primer lote — en
curso.** Mismo componente (`KpiCard.onClick` + `KpiDetalleModal`), mismo criterio de
elegibilidad, sin repetir la investigación de 17.6.

### 17.7 Lote 2 — Supervisor de Cumplimiento (5 KPIs) — cerrado y verificado

**Vigencia Documental** (`PanelDocumentacion.tsx`): Vencidos, Por vencer (≤30d), Bloqueados —
los 3 comparten la misma fuente en memoria (`porVencer`, ya cargada), solo cambia el
subconjunto (`dias_restantes<0`/`dias_restantes>=0`/`estado_verificacion==='BLOQUEADO'`). Sin
request nueva. Columnas extraídas a `columnasDocumento` (constante a nivel de módulo,
reutilizada por la tabla principal y los 3 modales — evita 4 copias del mismo array de
columnas). Filtro "Tipo de documento" dentro de cada modal, estado independiente del filtro de
la pantalla exterior.

**Auditoría** (`PanelAuditoria.tsx`): Eventos hoy, Accesos denegados.

- **Hallazgo real durante la construcción, no en el inventario original**: "Eventos hoy" NO
  era un candidato (a) tan limpio como parecía. El KPI sale de un conteo (`GET
  /auditoria/eventos?desde=<hoy>&tamanio_pagina=1`, solo `.total`) — la bitácora ya cargada en
  esta pantalla (`eventos`) no está acotada a "hoy" (viene filtrada por `filtroResultado`
  default `DENEGADO`, con su propio rango de fechas). No hay ningún array en memoria que sea
  realmente "los eventos de hoy". Se resolvió con 1 fetch nueva al abrir el modal (mismo
  endpoint, `desde=<medianoche de hoy>&tamanio_pagina=100`) — mismo patrón ya usado para
  "Corridas fallidas" en el lote 1, no un endpoint nuevo.
- "Accesos denegados" sí es un candidato (a) limpio: `eventos.filter(resultado==='DENEGADO')`,
  mismo subconjunto que ya calcula el KPI, sin request nueva.
- Columnas extraídas a `columnasEvento`, reutilizadas por la tabla principal y los 2 modales.
- Filtro "Acción" dentro de cada modal (opciones derivadas de las filas ya cargadas de ESE
  modal, no de toda la bitácora).

**Verificado en navegador real** (cuenta `staff-verificacion`, rol `supervisor_cumplimiento`),
con datos reales del entorno, no simulados: Vencidos abrió con 52 filas (igual al KPI),
filtrar por `LICENCIA_CONDUCIR` lo redujo a 30 sin tocar el filtro "Tipo de documento" de la
pantalla exterior (confirmado leyendo su `value` real, sin cambiar); Por vencer abrió con 40
filas (igual al KPI); Bloqueados (0 reales) mostró el estado vacío correcto, no un error.
Eventos hoy abrió con 80 filas (igual al KPI), confirmado en el log de red que la request
`GET /auditoria/eventos?desde=...&tamanio_pagina=100` se disparó al abrir (no estaba
cacheada), filtrar por acción `ACCESO_DENEGADO` la redujo a 1 fila real. Accesos denegados
abrió con 100 filas (igual al KPI, tope de página ya existente), sin ninguna request nueva
(reusa `eventos`). `npm run build/lint/test` limpios en `web-interno` (27/27, 0 warnings
nuevos) + `shared-ui` lint. Backend no se tocó (los 5 KPIs reusan endpoints existentes, con
parámetros ya soportados).

### 17.8 Lote 3 — Jefe de Mantenimiento / Administrador Financiero (7 KPIs) — cerrado y verificado

**Mantenimiento** (`PanelMantenimiento.tsx`): Órdenes abiertas, Vehículos retirados — ambas ya
completas en memoria (`ordenesAbiertas`/`retirados`), sin request nueva. Columnas extraídas a
`columnasOrden`/`columnasRetirado`. Filtro "Tipo de orden" dentro del modal de Órdenes; "Vehículo
(placa)" dentro del de Retirados.

**Conciliación** (`PanelConciliacion.tsx`): Discrepancias, Monto en disputa, Viajes sin pago.
"Discrepancias" y "Monto en disputa" son 2 KPIs distintos que abren el MISMO modal (ambos
derivan de `bandeja.discrepancias`) — confirmado en navegador que los 2 disparadores llevan al
mismo `titulo="Discrepancias"`. "Viajes sin pago" usa `bandeja.viajes_sin_pago`, sin filtro
propio (la lista siempre es pequeña, spec no pide subdividirla). Columnas extraídas a
`columnasDiscrepancia`/`columnasSinPago`.

**Liquidación** (`PanelLiquidacion.tsx`): Liquidaciones emitidas (`estado==='EMITIDA'`), Por
aprobar (`estado==='OBSERVADA'`) — ambos subconjuntos de `liquidaciones`, ya en memoria.
Columnas extraídas a `columnasLiquidacion`. Filtro "Socio" (búsqueda por nombre) dentro de
cada modal, reseteado al abrir para no heredar el texto del KPI anterior.

**Verificado en navegador real** (cuenta `staff-verificacion`, roles `jefe_mantenimiento` +
`admin_financiero`), con datos reales del entorno: Órdenes abiertas 47 (igual al KPI), filtro
"Correctiva" lo redujo a 17 sin tocar el filtro de tipo de la pantalla exterior; Vehículos
retirados 14 (igual al KPI). Discrepancias/Monto en disputa: ambos en 0 reales, los 2
disparadores abrieron el mismo modal con el estado vacío correcto (no un error). Viajes sin
pago: 2 filas reales (igual al KPI). Liquidaciones emitidas 14, Por aprobar 17 (ambos iguales
al KPI) — confirmado que el filtro "Socio" se reinicia entre aperturas (no arrastra el texto
tecleado en la apertura anterior). Sin errores de consola nuevos (los que aparecieron en el
log eran residuales del hiccup de HMR del lote 1 al editar `navegacion.ts`, confirmados
inofensivos con una recarga forzada — la app cargó y funcionó con datos reales normalmente).
`npm run build/lint/test` limpios en `web-interno` (27/27, 0 warnings nuevos) + `shared-ui`
lint. Backend no se tocó.

### 17.9 Lote 4 — Coordinador de Flota / Administrador de Captación (4 KPIs) — cerrado y verificado

**Flota** (`PanelFlota.tsx`): En servicio, Disponibles, Sin señal — los 3 derivan de
`vehiculos` (ya en memoria, con su propio polling de 10s ya existente, sin tocar). Columnas
extraídas a `columnasVehiculo`, reutilizadas por la tabla principal ("Sin señal") y los 3
modales. Filtro "Vehículo o conductor" (búsqueda de texto) dentro de cada modal.

**Captación** (`PanelCaptacion.tsx`): Solicitudes pendientes — ya completo en memoria
(`pendientes`), sin request nueva. Columnas extraídas a `columnasSolicitud`. Filtro "Canal"
dentro del modal.

**Verificado en navegador real** (cuenta `staff-verificacion`, roles `coordinador_flota` +
`admin_captacion`), con datos reales del entorno: En servicio 3 (igual al KPI); Disponibles 0
(estado vacío correcto); Sin señal 3, con el filtro de búsqueda confirmado narrowing a 0 con
un texto inexistente (el primer intento de probarlo pareció no reaccionar por un artefacto de
la herramienta de automatización al setear `.value` sin pasar por el setter nativo de React —
no un bug real, confirmado repitiendo la prueba con la técnica correcta). Solicitudes
pendientes 25 (igual al KPI), filtrar por canal `web` lo redujo a 7 sin tocar el filtro de
canal de la pantalla exterior (confirmado su `value` real sin cambiar). `npm run
build/lint/test` limpios en `web-interno` (27/27, 0 warnings nuevos) + `shared-ui` lint.
Backend no se tocó.

### 17.10 Lote 5 — Plataforma (táctico) + Gobernanza (estratégico) (3 KPIs) — cerrado y verificado

**Plataforma** (`PanelPlataforma.tsx`): Corridas OK hoy — subconjunto de `corridas`, ya en
memoria, sin request nueva. Columnas extraídas a `columnasCorrida`, reutilizadas por la tabla
principal y el modal.

**Gobernanza** (`PanelGobernanza.tsx`, estratégico): Eventos administrativos, Accesos
denegados.

- "Eventos administrativos" **sí** es (a) limpio: reusa `eventos` completo, confirmado en
  navegador que ambos coinciden en 89.
- **"Accesos denegados" NO era (a) — hallazgo real grave, encontrado y corregido en 2 pasadas
  antes de cerrar el lote.** Primera pasada (incorrecta): asumí que `eventos.filter(resultado
  === 'DENEGADO')` sería el subconjunto correcto, igual que en el lote táctico de Auditoría —
  pero `eventos` en este endpoint sale de `filtro_admin` (`backend/src/auditoria/service.py`,
  `_ACCIONES_ADMIN`), que **excluye por diseño** `ACCESO_DENEGADO` (es un evento de seguridad,
  no una "acción administrativa"). El modal abría con 0 filas mientras el KPI mostraba 19 —
  detectado inmediatamente en la verificación, nunca llegó a reportarse como cerrado con ese
  bug. Segunda pasada: se resolvió con un fetch nuevo al abrir, reutilizando el endpoint táctico
  `GET /auditoria/eventos`, acotado con el mismo `desde` que ya usa el KPI
  (`metadata.desde`) para que el conteo coincida. **Primer intento de esa segunda pasada
  también fue incorrecto**: filtrar por `resultado=DENEGADO` devolvió 100 filas (tope de
  página) sobre un total real de 229 — porque `resultado=DENEGADO` en la bitácora abarca 3
  acciones distintas (`ACCESO_DENEGADO`, `POSIBLE_GPS_SPOOFING`,
  `CUMPLIMIENTO_BANDERA_CAMBIO`), no solo la que cuenta el KPI. Corregido filtrando por
  `accion=ACCESO_DENEGADO` (no por `resultado`) — confirmado con la API real que ese filtro da
  exactamente 19, igual al KPI, antes de dar el punto por cerrado.

**Verificado en navegador real** (cuenta `staff-verificacion` para Plataforma, `gerencia` para
Gobernanza — exclusivo, ni siquiera `admin_sistema` lo ve): Corridas OK hoy 2 (igual al KPI).
Eventos administrativos 89 (igual al KPI). Accesos denegados: tras el fix, 19 filas reales,
las 19 con `accion=ACCESO_DENEGADO`, confirmado en el log de red que la request se dispara al
abrir con los parámetros correctos. `npm run build/lint/test` limpios en `web-interno` (27/27,
0 warnings nuevos) + `shared-ui` lint. Backend no se tocó — los 3 KPIs reusan endpoints ya
existentes, con parámetros ya soportados.

**Lección para los lotes 6+**: cuando un KPI de un dashboard ESTRATÉGICO se parece a un KPI ya
resuelto en el nivel TÁCTICO, no asumir que la misma fuente/filtro aplica — los endpoints
estratégicos suelen agregar sobre un universo de datos distinto (aquí, `filtro_admin` excluye
justo lo que el KPI cuenta). Verificar el conteo real contra la API antes de dar un candidato
por (a), no solo mirar el nombre del campo.

### 17.11 Lote 6 (grupo b) — 2 candidatos descartados del drill-down, 1 es deuda técnica real

Durante la verificación de los ~4 candidatos (b) del inventario original, 2 resultaron no ser
seguros de construir — no se forzaron, siguiendo la instrucción explícita del usuario de
avisar antes de forzar un caso dudoso.

**"Altas de socios (periodo)" (Crecimiento estratégico) — descartado, queda sin drill-down.**
El KPI (`kpis.altas_periodo`) sale de `tendencia_altas[-1]["altas"]`, el último corte de
`rpt_altas_retencion_canal` (ClickHouse, construida desde `fact_registro_usuario` sobre
`usuarios.fecha_registro`). El único endpoint Mongo con pinta de fuente reutilizable
(`GET /captacion/solicitudes?estado=APROBADA`) no tiene filtro de fecha, y no hay garantía de
que "solicitud aprobada" y "usuario registrado" correspondan al mismo campo de fecha ni a los
mismos límites de periodo que usa la tabla `rpt_*`. Decisión del usuario: se queda como KPI
plano, mismo tratamiento que un porcentaje/promedio sin lista real detrás — no reabrir sin
pedido explícito.

**"Cancelaciones del periodo" (Confiabilidad estratégico) — descartado, PERO es deuda técnica
real, no un simple "no aplica".** El KPI (`cancelaciones_periodo` = `tendencia_cancelacion[-1]
["cancelados"]`, suma de `rpt_tasa_cancelacion` para el periodo más reciente) reportó **222**
para 2026-08 en una verificación real contra ClickHouse. El conteo real de viajes en Mongo con
`estado IN (CANCELADO, SIN_CONDUCTOR)` y `ts_solicitud` en ese mismo mes es **45** — una
diferencia de casi 5x, no explicable por ningún filtro de fecha o de estado razonable. Esto
**no es un problema de "qué endpoint reusar"** como los otros casos de este lote — es el mismo
defecto ya documentado en §12.3 (`rpt_tasa_cancelacion` agrupa por motivo/actor/zona con
`HAVING cancelados > 0`, lo que ya se sabía que rompía la "tasa" como porcentaje; esta
verificación confirma que también infla el "volumen" absoluto, no solo el % — la tabla cuenta
de más, no solo divide mal). **Pendiente de investigación aparte, con tiempo dedicado, NO como
parte de este rollout de drill-down**: por qué el `GROUP BY` de `rpt_tasa_cancelacion`
sobre-cuenta, y si corregirlo en el DAG (`analytics/dags/dag_viajes_core.py`/
`analytics/plugins/indicadores.py::refrescar_tasa_cancelacion`) es seguro sin romper el resto
de consumidores de esa tabla (`PanelDespacho.tsx` táctico y `PanelConfiabilidad.tsx`
estratégico ya la leen). Cualquier KPI futuro que dependa de `rpt_tasa_cancelacion` debe
tratarse con la misma sospecha hasta que esto se resuelva.

**"Documentos vencidos" (Cumplimiento Normativo estratégico) — construido, con un hallazgo
real de RBAC encontrado y corregido antes de cerrar.** A diferencia de los 2 anteriores, este
sí calificó: `kpis.documentos_vencidos = round(total_registros * (1 - pct_vigente))` es una
derivación aritmética EXACTA (no una aproximación con pérdida de información) sobre el
snapshot de `rpt_documentacion_vigente` — verificado con la API real: 30 (LICENCIA_CONDUCIR) +
22 (MATRICULA_VEHICULAR) = 52, exactamente el mismo 52 ya verificado en el lote 2 contra el
"Vencidos" real de Mongo en el panel táctico de Documentación. Se construyó reusando ESE mismo
endpoint táctico (`GET /cumplimiento/panel-tactico/documentos-por-vencer`), filtrando a
`dias_restantes<0`, con 1 fetch nueva al abrir (mismo patrón que "Corridas fallidas"/"Eventos
hoy").

**Hallazgo real (RBAC, no de datos)**: ese endpoint táctico estaba gateado en exclusiva a
`supervisor_cumplimiento` — pero el panel ESTRATÉGICO que aloja este KPI es visible también a
`gerencia` (`_cumplimiento_normativo_estrategico = require_roles("gerencia",
"supervisor_cumplimiento")`). Confirmado real en navegador: con la cuenta `gerencia`, el KPI se
veía normal pero el clic daba **403** siempre. Corregido con un OR-gate puntual en
`backend/src/cumplimiento/router.py::listar_documentos_por_vencer` (ahora
`require_roles("supervisor_cumplimiento", "gerencia")`, dependencia inline, no se tocó el
`_supervisor_cumplimiento` compartido por el resto de endpoints de ese router) — **no amplía el
acceso al panel táctico completo**, el sidebar de `web-interno` sigue sin mostrárselo a
`gerencia` (`tactico-documentacion` sigue con `roles: ["supervisor_cumplimiento"]`), solo se
abrió esta lectura puntual que el drill-down necesita. Test de regresión nuevo
(`test_documentos_por_vencer_permite_gerencia_ademas_de_supervisor`) que fija 200 para ambos
roles y 403 para un tercero sin relación.

**Verificado en navegador real** (cuenta `gerencia`): tras el fix, el modal abrió con 52 filas
reales (igual al KPI), filtrar por `LICENCIA_CONDUCIR` lo redujo a 30 (igual a la estimación
por tipo). `npm run build/lint/test` limpios en `web-interno` (27/27, 0 warnings nuevos) +
`shared-ui` lint. Backend: **351 passed + 8 skipped** (subió de 350), `ruff check` limpio.

**Cierre del rollout de KPI drill-down**: de los ~30 candidatos totales identificados en la
investigación original (17.6), quedaron construidos y verificados 1 (piloto) + 3 (lote 1) + 5
(lote 2) + 7 (lote 3) + 4 (lote 4) + 3 (lote 5) + 1 (lote 6) = **24 KPIs con drill-down real**.
2 quedaron deliberadamente sin construir por hallazgos reales durante la verificación (Altas de
socios, Cancelaciones del periodo — esta última señalada como deuda técnica real, no como
"no aplica"). Los ~40 restantes del inventario original (porcentajes/promedios sin lista real
detrás, más los 7 de `Monitoreo.tsx`) nunca calificaron para el patrón, confirmado en 17.6.

## 18. Flujo de fallas del vehículo — Ronda 2 (agosto 2026), las 7 fases (A-G) cerradas

Implementación de `PROPUESTA_FLUJO_FALLA_VEHICULO.md` (propuesta ya aprobada en la auditoría
UX/catálogos previa), con 3 decisiones de mayor alcance ya resueltas antes de construir: carga
real de archivos (opción B, no URLs de texto libre), `km_acumulado` alimentado en esta misma
ronda, y `ESPERANDO_REPUESTO` agregado como estado nuevo de la máquina de estados de
`ordenes`. Reusa tal cual el selector de taller de Catálogos Ronda 1 (§7 punto 5, "Ola 1.1") en
los 3 formularios nuevos que necesitan taller (conversión de reporte, orden encadenada) — nunca
se reconstruyó. 7 fases secuenciales, cada una verificada en navegador real con datos reales
antes de pasar a la siguiente, siguiendo la regla de cierre del §6.

**Fase A — infraestructura de carga de archivos.** Primer mecanismo de `UploadFile`/multipart
del proyecto — antes, "carga de documentos" (`documentos.url_objeto`) siempre fue un `str` que
el cliente pegaba a mano. Nuevo módulo `backend/src/archivos/` (`POST /archivos`,
`GET /archivos/{id}/meta`, `GET /archivos/{id}`), almacenamiento local en disco dentro del
contenedor (volumen con nombre `archivos_data:/app/archivos`, mismo patrón que
`respaldos_data` de Módulo 7.1 de admin_sistema) — sin S3/MinIO, coherente con el techo de
memoria/infraestructura ya documentado (§8.6a). Solo imágenes (`image/jpeg|png|webp`, 5 MB
máx.), streaming real (nunca el archivo completo en memoria), extensión derivada del
`content_type` reportado (nunca del nombre del cliente). Control de acceso por `contexto`
(diccionario `CONTEXTOS_PERMITIDOS: dict[str, frozenset[str]]`, decidido siempre en el
servidor, nunca aceptado del cliente al subir) — diseño deliberadamente genérico para que un
consumidor futuro (la carga de documentos de postulación, backlog ya documentado en §3.1)
pueda reusarlo sin tocar este módulo. 2 contextos reales hoy: `reporte_falla` (Fase C) y
`actividad_orden` (Fase F), ambos con los mismos roles adicionales de lectura
(`jefe_mantenimiento`, `admin_sistema`, `gerencia`, `supervisor_cumplimiento`) más el propio
dueño del archivo. Frontend: como `GET /archivos/{id}` exige Bearer token, un `<img src>` plano
no sirve — `subirArchivo`/`obtenerArchivoBlobUrl` nuevos en `apps/shared-ui/src/api/client.ts`
(el segundo descarga como blob autenticado y genera un Object URL, revocado al desmontar).
Verificado con subida real desde navegador y descarga confirmando el mismo contenido.

**Fase B — `km_acumulado` alimentado (H7).** El campo existía en el esquema de `vehiculos`
desde siempre pero nada lo escribía (81/81 vehículos reales en 0, confirmado en la auditoría
previa). Alimentación hacia adelante: `viajes/service_finalizacion.py::finalizar_viaje` ahora
suma `km_recorridos` a `vehiculos.km_acumulado` en la misma transacción del cierre del viaje.
Backfill del histórico: `backend/scripts/backfill_km_acumulado.py` (idempotente, `$set` a un
valor absoluto recalculado, no `$inc`) — corrida real: 81 vehículos recalculados, 44 con viajes
cerrados reales que aportan km. Ficha del vehículo nueva (`GET
/mantenimiento/vehiculos/{id}/ficha`, H6/CU-O12 P1): km acumulado real, fecha/km de la última
intervención (orden `CERRADA` más reciente por `fecha_cierre`), próxima preventiva proyectada,
aviso `le_toca_preventivo`. **Premisa de la propuesta corregida**: no existe en ningún lado del
código ni del modelo de datos un "plan preventivo diferenciado por antigüedad del vehículo" —
la única referencia es el ejemplo de la spec ("cada 5 000 km", CU-O12 A2). Se implementó con un
umbral GLOBAL único (`UMBRAL_KM_PREVENTIVO = 5000`), documentado explícitamente como
simplificación deliberada en vez de inventar una diferenciación que ningún dato real respalda.
El formulario "Nueva orden" de `Mantenimiento.tsx` prefiltra `km_entrada` con este valor real
(editable, el Jefe sigue verificando contra el tablero físico). **No implementada la pre-orden
automática por umbral (CU-O12 A2)** — explícitamente descartada para esta ronda, el aviso es
solo informativo al abrir la ficha.

**Fase C — reporte de falla del conductor (con y sin viaje).** Nuevo dominio
`backend/src/reportes_falla/` (colección `reportes_falla`: vehículo, conductor, viaje opcional,
tipo de falla del catálogo `motivos` categoría `incidencia` ya sembrado en Ronda 1, descripción,
posición, `impide_continuar`, estado, evidencias). Dos entradas en `web-conductor` que abren el
mismo formulario (`ReportarFallaForm`): "Registrar incidencia" dentro de `ViajeAsignadoCard`
mientras el viaje está EN_CURSO, y "Reportar falla del vehículo" fuera de viaje (turno
FUERA_DE_LINEA o DISPONIBLE sin oferta) — el checkbox "no puedo continuar" solo aparece con
viaje de por medio. CU-O07 A4 real: si `impide_continuar=true` y hay un viaje EN_CURSO, se
cancela (`viajes/service_ejecucion.py::cancelar_por_incidencia`, nueva, mismo patrón
write-ahead que el resto del dominio) y se dispara una nueva solicitud automática para el
pasajero desde la posición del incidente, reutilizando `viajes/service.py::solicitar_viaje`
tal cual (sin duplicar el despacho). **Decisión de diseño explícita, distinta de A3**: a
diferencia de `cancelar_por_conductor` (que hace volver el MISMO documento a SOLICITADO), acá
se cancela el viaje EN_CURSO y se crea uno NUEVO — un viaje EN_CURSO ya acumuló traza/km reales
de un tramo no completado, mezclarlo con un viaje que arranca de cero sería un dato
contaminado. Notificación al Jefe de Mantenimiento vía `disparar_alerta` (Módulo 6.3, mismo
mecanismo ya usado por `flota/service.py` para GPS spoofing) — nuevo tipo `reporte_falla` en
`TIPOS_ALERTA`/`ROL_DEFAULT_POR_ALERTA`. **Limitación real conocida, no corregida**: en un pool
de solo 5 conductores de prueba, el mismo conductor que reportó la incidencia puede ser
re-ofertado su propia nueva solicitud (confirmado en la verificación real) — el conductor queda
`DISPONIBLE` de nuevo (mismo comportamiento que A3) y puede simplemente rechazar la oferta si
esto ocurre; no se implementó exclusión explícita del conductor reportante para no acoplar
`avanzar_despacho` a este caso particular. Verificado con datos reales en ambos casos (con y
sin viaje activo, incl. evidencia fotográfica subida y visible después, por el propio
conductor y por `jefe_mantenimiento`).

**Corrección post-cierre (2026-08-15): aviso en vivo al Coordinador de Operaciones (CU-O07
A4), gap real encontrado por el usuario.** La implementación original de Fase C solo notificaba
al Jefe de Mantenimiento (`reporte_falla`) — eso alimenta la bandeja de pre-órdenes (Fase D),
pero la spec real (CU-O07 A4) pide además un aviso EN VIVO al Coordinador de Operaciones
("hay una incidencia ocurriendo ahora en la operación"), independiente de si el viaje se
cancela. Son dos avisos con propósito distinto, ninguno reemplaza al otro. Verificado el
identificador real de rol antes de tocar código (`core/rbac.py::ROLES`): `coordinador_operaciones`.
Nuevo tipo de alerta `incidencia_operativa` en `TIPOS_ALERTA`/`ROL_DEFAULT_POR_ALERTA` →
`coordinador_operaciones` (mismo patrón "un tipo de alerta = un rol destinatario" ya
establecido para el resto del catálogo — no se reutilizó `reporte_falla` porque tiene un
destinatario y un propósito distintos). `reportes_falla/service.py::crear_reporte_falla` ahora
dispara los DOS `disparar_alerta` en el mismo punto, sin condicionar ninguno a
`impide_continuar` ni a si hay viaje activo — igual que ya hacía el de `reporte_falla`.
Verificado en navegador real: reporte de prueba desde `web-conductor` generó ambas
notificaciones en el mismo instante (confirmado en la bandeja de `staff-verificacion`, que
acumula ambos roles), y la bandeja de pre-órdenes de Mantenimiento (Fase D) siguió mostrando el
mismo reporte sin cambios. Backend **388 passed + 8 skipped** (sin subir de número porque 2
tests de Fase C se ampliaron en vez de sumar tests nuevos, más 1 test de notificaciones
actualizado de "4 alertas" a "5 alertas"), `ruff` limpio; `web-interno` build/lint/**27/27**
(nueva etiqueta en `ConfiguracionAlertas.tsx`), sin cambios en `web-pasajero`/`web-conductor`.

**Fase D — bandeja del Jefe de Mantenimiento y conversión a orden.** Nueva pestaña "Reportes de
falla" en el WorkPanel de Mantenimiento (`Mantenimiento.tsx`, patrón de pestañas ya usado en
Catalogos/Integraciones/Respaldos — `TabButton` local, sin componente compartido). Lista
reportes `PENDIENTE` con miniatura de evidencia (`MiniaturaEvidencia`, blob autenticado). "Convertir
en orden" (`POST /reportes-falla/{id}/convertir`) hereda vehículo, tipo de falla + descripción +
posición (plegados en el texto de `descripcion` de la orden — `ordenes` nunca tuvo campo de
posición propio) y evidencia fotográfica en un campo nuevo `ordenes.evidencias`; reusa el
selector de taller de Ronda 1 tal cual. `tipo` siempre `CORRECTIVA` por definición (una falla
reportada es reactiva, nunca se expone el selector para reclasificarla como preventiva).
"Descartar" con motivo obligatorio. Ambas transiciones marcan `reportes_falla.estado`
(`CONVERTIDO_A_ORDEN` con `orden_id`, o `DESCARTADO` con `motivo_descarte`). Verificado con
datos reales: reporte con evidencia convertido en orden real (`descripcion` compuesta,
`evidencias` heredada, confirmado en Mongo), reporte descartado con motivo real.

**Fase E — estado `ESPERANDO_REPUESTO` (CU-O12 A3).** Nuevo estado intermedio,
`EN_TALLER ⇄ ESPERANDO_REPUESTO`, con motivo obligatorio al entrar (espera visible, no un
limbo silencioso); cierre alcanzable desde cualquiera de los dos (no obliga a "reanudar"
primero si el repuesto llegó y se quiere cerrar de una vez). Panel táctico de Mantenimiento
(`PanelMantenimiento.tsx`) ampliado de 2 a 3 llamadas mezcladas client-side
(ABIERTA+EN_TALLER+ESPERANDO_REPUESTO) para que "órdenes abiertas" siga siendo exhaustivo;
`listar_vehiculos_retirados` (vehículos retirados) también ampliado — una orden
ESPERANDO_REPUESTO retiene el vehículo tanto como una EN_TALLER. **`dag_mantenimiento_gold`
verificado explícitamente, sin necesitar cambios**: su filtro es `{"estado": "CERRADA", ...}`,
así que una orden en este estado nuevo cae en el mismo bucket "sin `fecha_cierre` todavía" que
ya excluía EN_TALLER — el docstring del DAG se actualizó para dejarlo dicho, no solo asumido.
De paso se cerró H8 (marcar_en_taller nunca se auditaba, a diferencia de crear/cerrar/anular) —
ahora escribe `ORDEN_MANTENIMIENTO_EN_TALLER` con el mismo patrón write-ahead del resto.
Verificado con ida y vuelta real en navegador (EN_TALLER → ESPERANDO_REPUESTO → EN_TALLER),
reflejado correctamente en el panel táctico con badge de tono `peligro` (más urgente que
`advertencia` de EN_TALLER, la orden está bloqueada esperando un insumo externo).

**Fase F — actividades embebidas en la orden.** `ordenes.actividades: []` (insert-only, cada
entrada con ts/actor_id/actor_nombre/rol/tipo/detalle/evidencias) — bitácora propia de la
orden, distinta de la bitácora global CU-O17 (esa sigue auditando las transiciones en sí; esto
es el detalle operativo legible para quien abre la orden). Nueva sección "Actividad de la
orden" en el detalle (solo visible con la orden EN_TALLER/ESPERANDO_REPUESTO): timeline
cronológico + formulario para agregar comentario/avance con foto opcional (reusa la
infraestructura de archivos de Fase A, contexto `actividad_orden`), sin cerrar el panel al
agregar (a diferencia de cerrar/anular/esperar, agregar varios comentarios seguidos es el flujo
normal). La transición a `ESPERANDO_REPUESTO`/reanudación (Fase E) queda registrada
automáticamente como actividad `CAMBIO_ESTADO` — no un paso manual aparte, cableado dentro de
las mismas funciones del servicio que ya escriben el evento de auditoría. Verificado en
navegador real: transición automática visible en la cronología con actor/rol/hora reales,
comentario manual con foto agregado sin cerrar el panel, orden cronológico correcto, confirmado
en Mongo.

**Fase G — gaps menores.** (1) Costo estimado vs. real: `mano_obra_estimada` (monto único,
opcional) sumado a `crear_orden`; `costo_estimado` es una proyección SIEMPRE recalculada desde
`mano_obra_estimada` + suma de `repuestos_estimados` (nunca persistida, mismo criterio ya
establecido para `proxima_km_preventivo`), con vista previa en vivo en el formulario "Nueva
orden". Al cerrar, `desviacion_costo_pct` se calcula y se registra en el MISMO evento
`ORDEN_MANTENIMIENTO_CIERRE` de siempre (sin evento nuevo), mostrado en el banner de cierre.
(2) Orden encadenada (CU-O13 A1): checkbox "Abrir una orden correctiva encadenada al cerrar" en
el panel de cierre — crea una orden `CORRECTIVA` hija con `orden_madre_id` (campo que existía en
el schema desde el inicio del proyecto, nunca cableado hasta ahora), `km_entrada` heredado del
`km_salida` de la orden que se cierra (mismo vehículo, mismo instante, no tiene sentido
pedirlo dos veces), creada DESPUÉS de que el cierre ya se confirmó (no en la misma transacción
— el cierre es un hecho de negocio completo por sí solo). (3) H8 — ya cerrado en Fase E, sin
trabajo adicional acá. Verificado en navegador real: orden con repuestos+mano de obra
($55 estimado) cerrada con costo real $72 → banner mostrando "+30.9%" correcto, orden
correctiva hija creada con `km_entrada` heredado y `orden_madre_id` correcto, confirmado en
Mongo junto con el evento de auditoría único que lleva ambos montos.

**Cierre transversal**: ninguna fase reescribió datos históricos, ningún campo de texto libre
se migró a FK (mismo criterio ya establecido en Ronda 1 para motivos/talleres). Regresión final
tras las 7 fases: backend **388 passed + 8 skipped** (subió de 351 al cierre del bloque
anterior), `ruff check` limpio; `web-pasajero` build/lint/**10/10**, `web-conductor`
build/lint/**6/6**, `web-interno` build/lint/**27/27** (mismos 3 warnings preexistentes de
`useEffect`, no nuevos), `shared-ui` lint limpio.

## 19. Catálogo de repuestos (Ola 3) + revisión general de "Otro" — cerrado

Ola 3 de `PROPUESTA_CATALOGOS_Y_ADMINISTRACION.md`, antes aplazada por falta de evidencia,
construida esta sesión por decisión explícita de avanzar sin volver a medir. Mismo patrón CRUD
que talleres/marcas/colores (Ronda 1): colección `repuestos` propia (`nombre` único, `categoria`
Motor/Frenos/Eléctrico/Suspensión/Neumáticos/Otro, `precio_referencial`, `unidad`
unidad/litro/juego, `activo`), auditoría write-ahead (`CATALOGO_CREACION`/`CATALOGO_EDICION`,
`entidad="repuestos"`), pestaña nueva en `Catalogos.tsx` (`SeccionRepuestos`, mismo patrón
`SeccionTalleres`). Lectura gateada a `_cualquier_actor` (como taller, no público como
marca/color — el único consumidor es `Mantenimiento.tsx`, pantalla autenticada), escritura a
`admin_sistema`. Sembrados **19 repuestos reales** (`backend/scripts/seed_repuestos.py`,
idempotente, mismo patrón `uuid5` + `$setOnInsert`) con precios de referencia creíbles: Motor
(6: filtros, aceite, bujías, correa de distribución), Frenos (4: pastillas delanteras/traseras,
disco, líquido DOT4), Eléctrico (4: batería, alternador, foco H4, bomba de combustible),
Suspensión (3: amortiguadores, rótula), Neumáticos (2: neumático 185/65 R15, válvula). Divergencia
deliberada de la propuesta original (que recomendaba NO agregar precio): el pedido explícito de
esta sesión sí lo requiere — documentado en el docstring de `schemas.py`.

**Cableado en `Mantenimiento.tsx`**: `RepuestosEditor` (componente compartido por los 3
formularios que manejan líneas de repuesto — Nueva orden, Cierre, conversión de reporte a orden)
reemplazó el campo `Descripción` de texto libre por un `<Select>` contra el catálogo. Al elegir
un repuesto, `Costo unitario` se precarga con `precio_referencial` pero **sigue siendo editable
sin restricción** — el catálogo solo sugiere un punto de partida, nunca fija el costo real.
Verificado con una orden real (`PBA-1234`, taller Central): "Pastillas de freno delanteras
(juego)" precargó $35.00, editado a $38.50 en el campo, confirmado en el `POST
/mantenimiento/ordenes` real (`costo_unitario: 38.5`) — orden de prueba borrada después de
verificar.

**Revisión general de "Otro"**: inventario completo de selectores cableados contra un catálogo,
con el hallazgo real de que **solo taller** (3 instancias, Ronda 1) ya tenía la opción "Otro" con
campo de texto libre asociado. Agregada de forma consistente (mismo sentinel `"__otro__"`, mismo
patrón visual: `<Select>` con la opción al final + `<TextField>` condicional que solo aparece con
el sentinel seleccionado, mismo criterio de guardado: el valor libre se guarda tal cual, sin FK)
en:

- **Motivo de cancelación del conductor** (`web-conductor`, `ViajeAsignadoCard`).
- **Motivo de cancelación del pasajero** (`web-pasajero`, tarjeta de viaje activo).
- **Marca de vehículo** (`web-conductor`, `PostulacionForm`) — verificado en navegador real:
  postulación completa con marca="MarcaLibreQA" y color="ColorLibreQA" (ambos "Otro"), `POST
  /captacion/solicitudes` 201, confirmado en Mongo que `solicitudes.vehiculo.marca`/`.color`
  guardaron el texto libre exacto, sin ninguna validación de catálogo. Solicitud y cuenta de
  prueba borradas después de verificar (bitácora del evento se dejó intacta, insert-only por
  diseño, mismo criterio ya establecido en §8.2/§17 para limpiezas anteriores).
- **Color de vehículo** (mismo formulario, ver punto anterior).

**Repuestos** no tenía selector antes (era `Descripción` de texto libre puro) — nace con "Otro"
desde el inicio, mismo patrón.

**Caso evaluado y descartado, no agregado — hallazgo real que cambió el plan sobre la marcha**:
`tipo_falla` (`web-conductor`, `ReportarFallaForm`, backed por el catálogo `motivos_cancelacion`
categoría `incidencia`, construido en la Fase C de §18) parecía un candidato natural adicional
(por fuera de la lista explícita del usuario) — pero a diferencia de taller/motivo_cancelacion/
marca/color, **`reportes_falla/service.py::_validar_tipo_falla` exige que el valor exista en el
catálogo con `activo:true`**, rechazando cualquier texto libre con 422 `TIPO_FALLA_INVALIDO`. Se
implementó el patrón "Otro" ahí también en un primer intento, y se detectó el conflicto con una
prueba REAL en navegador (geolocalización mockeada vía `javascript_tool` para evitar el bloqueo
de permisos del entorno automatizado): seleccionar "Otro" y escribir un valor libre devolvió
`422` real del backend. Revertido por completo (UI y estado) — este selector **no** sigue el
patrón de taller porque su "guardado" real es un catálogo cerrado por diseño (misma protección ya
usada por `captacion/service.py` para `tipo_documento`, P3 de la ronda de usabilidad), no texto
libre. No tocar sin decidir explícitamente si se quiere relajar esa validación de negocio — es
una decisión de alcance distinta a esta ronda, no un descuido.

**Regresión final**: backend **393 passed + 8 skipped** (subió de 388, por los 5 tests nuevos de
`test_catalogos.py`), `ruff check` limpio; `web-conductor` build/lint/**6/6** (sin cambio neto de
tests — el revert de `tipo_falla` no tenía test propio), `web-pasajero` build/lint/**10/10**,
`web-interno` build/lint/**27/27** (mismos 3 warnings preexistentes), `shared-ui` lint limpio.

## 20. Rediseño visual de identidad de marca (agosto 2026) — Fases 0-2 cerradas

Encargo del dueño de producto vía `brief_rediseno_visual.md` (documento externo, no versionado en
el repo): el sistema de diseño adoptado en el rediseño de agosto 2026 (§16) no tenía identidad
propia — Barlow + acento ámbar sobre una base de neutros gris-azulados fríos es, literalmente, la
fórmula genérica "gris neutro + un acento brillante". Proceso de 2 pasadas exigido explícitamente
por el brief: auditoría + plan de diseño para aprobación **antes** de tocar código de producción,
implementación por fases después. Las 3 fases quedaron cerradas con aprobación explícita del
usuario en cada punto de decisión.

**Fase 0 — auditoría** (`AUDITORIA_DISENO_ACTUAL.md`, entregable, no se resume aquí en detalle).
Hallazgos más relevantes para el resto del proyecto: (1) el tema por defecto YA era claro
técnicamente (`:root` sin `data-theme` + `preferencias/service.py::DEFAULTS["tema"]="claro"`) —
la percepción de "oscuro por defecto" venía del toggle personal usado en sesiones de verificación
previas, no de un default real; (2) contraste WCAG medido con fórmula real (no a ojo): el ámbar
como texto daba 2.08:1 (falla AA), pero **los 3 tonos de `Badge`** también fallaban contra su
propio fondo tenue resuelto (2.37-3.62:1) — hallazgo más grave que el que el brief anticipaba,
porque `Badge` es de los componentes de mayor reuso del sistema; (3) `HeatMap.tsx` ya usaba
`color-mix()` de forma genérica/reutilizable, no como caso aislado de Rentabilidad; (4) gaps
documentados sin arreglar (por instrucción explícita del usuario, "cero cambios de lógica o
comportamiento"): sin trampa de foco ni cierre con Escape en `DetailPanel`/`KpiDetalleModal`, sin
`prefers-reduced-motion`, jerarquía de 3 niveles del sidebar solo textual, "cerrar sesión" como
única acción irreversible sin ningún tipo de fricción (el resto ya usa el patrón "motivo
obligatorio" como gate, no un diálogo sí/no).

**Fase de plan** (`PLAN_REDISENO_VISUAL.md`, aprobado tal cual, sin cambios). Paleta cálida
(crema/tinta/ámbar) en vez de gris-azulado — cada hex derivado de una verificación WCAG real
contra su combinación de uso real, no solo contra blanco puro. Tipografía: Barlow se mantiene para
cuerpo/UI/datos; Big Shoulders Display (nueva) reservada a títulos de pantalla y cifras grandes,
elegida por su herencia de señalética urbana/civil (no una serif elegante ni una geométrica tipo
Space Grotesk, ambas evaluadas y descartadas por sonar genéricas/desalineadas con "cooperativa de
taxi"). Elemento "signature": franja de ruta punteada en el panel de solicitud del pasajero
(prioriza alcance — es el touchpoint de mayor frecuencia del sistema — sobre el header del Tablero
Ejecutivo, evaluado y descartado por ser de uso ocasional y exclusivo de `gerencia`). Autocrítica
explícita incluida en el documento: qué se descartó por genérico (una segunda familia de color
"cooperativa/confianza" verde-azulado, considerada y descartada por ser el tropo genérico de
"verde=confianza" de cualquier SaaS sin dirección propia, y por competir con `--status-good` ya
reservado).

**Fase 1 — tokens compartidos** (`apps/shared-ui/src/tokens.css`) — cerrada. Paleta completa
recalculada con WCAG real para ambos temas (claro y oscuro, mismos materiales con roles
invertidos: la tinta del modo claro `#241a10` es la superficie del modo oscuro, el crema del modo
claro es el texto del modo oscuro). Tokens nuevos: `--color-accent-deep` (ámbar seguro como texto,
`#8a4b0a` claro / `#f6c667` oscuro) y `--color-danger-contrast` (formalizado desde el `#fff` fijo
que tenía `Button.tsx` variant `danger` — ahora se redefine por tema, porque el rojo del modo
oscuro es CLARO sobre fondo oscuro y necesita texto oscuro, no blanco: 6.45:1 vs. 2.65:1).
`--color-success`/`--color-warning`/`--color-danger` recalibrados (con su alpha de badge ajustado,
11-16% según el caso) para que los 3 tonos de `Badge` pasen 4.5:1 real contra su propio fondo
resuelto — el hallazgo más grave de la auditoría, corregido de raíz. Sidebar (fija, no reactiva al
tema) recalibrada a la misma familia cálida (antes navy `#101a26`, desconectado del resto del
sistema). **`--chart-series-*`/`--status-*` intactos a propósito** — paleta ya validada por la
skill `dataviz`, confirmado fuera de alcance en la auditoría.

Big Shoulders Display alojada localmente (`apps/shared-ui/src/assets/fonts/big-shoulders-display.woff2`,
35KB, subset "latin" — cubre español completo, variable en el eje `wght`, 2 bloques `@font-face`
—700/900— apuntando al mismo archivo, mismo patrón que usa el propio Google Fonts para servir
variable fonts), nunca por CDN — instrucción explícita del usuario, mismo criterio ya aplicado en
el proyecto de evitar dependencias externas de runtime no justificadas. Licencia SIL OFL 1.1
documentada en `LICENSE-big-shoulders-display.txt` junto al archivo. Barlow sigue por CDN
(decisión previa, sin cambios). **Bug real encontrado y corregido durante la verificación**: un
comentario CSS con el texto literal `--chart-series-*/--status-*` rompía el parser de PostCSS —
`*/` es cierre de comentario sin importar que esté dentro de texto, no solo como token real,
tumbando `tokens.css` completo con 500 en dev (`Unknown word quedan`). Corregido reescribiendo el
comentario sin la secuencia `*/` literal.

**Fase 2 — portales, por fases** — cerrada. Orden verificado tal como se aprobó: móvil primero en
`web-pasajero`/`web-conductor`, confirmado después en escritorio; cada fase con regresión completa
(build/lint/test) antes de pasar a la siguiente.

- **2a (`web-pasajero`)**: los 6 `<h1>` de pantalla (login, "¿A dónde vamos?", "Tu viaje", "Califica
  al conductor", "Mis viajes", "Viaje en curso") migrados a `--font-display`/700/`--font-size-xl`.
  Franja de ruta construida en `PanelSolicitar` (`App.tsx`, el componente de "¿A dónde vamos?"):
  conector punteado + punto hueco (origen, ámbar profundo) + punto sólido (destino, tinta) alrededor
  de los 2 `TextField` YA existentes — sin campos ni pasos nuevos, solo el wrapper posicional
  (`position:absolute`, ancla por `top`/`bottom` para que la línea se auto-ajuste sin importar si
  el bloque de favoritas intermedio renderiza o no). Verificado con valores computados reales en
  navegador (login real, marcadores en las coordenadas y colores exactos calculados).
- **2b (`web-conductor`)**: los 10 `<h1>` de pantalla (postulación, portal, "Nuevo viaje", "Pago
  recibido", "Califica al pasajero", reporte de falla, "Viaje asignado", "Mis viajes", "Mis
  liquidaciones", "Mi turno", "Solicitud enviada") con el mismo tratamiento. Sin elemento
  signature propio — el brief lo reserva a un solo lugar (pasajero).
- **2c (`web-interno`)**: jerarquía de 3 niveles del sidebar reforzada en `AppShell.tsx`
  (`NIVEL_GRUPO`, mapeo por nombre literal de grupo — sin campo nuevo en `AppShellNavItem`, así que
  `web-pasajero`/`web-conductor` quedan sin cambios): "Panel Táctico" con marcador 6px en ámbar
  profundo, "Panel Estratégico" con marcador 8px en ámbar de marca + texto casi blanco (más peso
  conforme sube el nivel), "Administración"/"Historial" (grupos ajenos a la escalera
  operativo-táctico-estratégico) sin marcador, a propósito. `KpiCard` (valor grande) y
  `TableroEjecutivo` (`<h2>` + las 8 cifras headline) migrados a `--font-display`. Verificado con
  las 2 cuentas reales que cubren los 3 niveles (`staff-verificacion` para operativo+táctico,
  `gerencia` para estratégico) — marcadores, colores y fuente confirmados con valores computados
  reales, no solo leídos en código.
- **Estado de foco de teclado** (`tokens.css`, regla global nueva): `:focus-visible` con
  `--color-accent-deep` — insuficiente por sí solo para el sidebar (siempre oscura sin importar el
  tema; en tema claro `--color-accent-deep` resuelve a un tono oscuro que da solo 2.68:1 contra
  ese fondo, bajo el mínimo de 3:1 de WCAG 1.4.11 para componentes no textuales) — corregido con
  `.shell-sidebar :focus-visible { outline-color: var(--color-accent) }` (el ámbar brillante, que
  sí funciona sobre fondo oscuro fijo en cualquier tema, 7.62-8.74:1). Verificado con Tab real de
  teclado (no `.focus()` programático, que no siempre dispara el heurístico de `:focus-visible` de
  Chrome) sobre un botón del sidebar: `matches(':focus-visible')` true, color correcto confirmado.
  **Deliberadamente fuera de esta ronda** (instrucción explícita del usuario): trampa de foco y
  cierre con Escape en los modales — eso es un cambio de comportamiento, no de presentación, y
  quedó solo documentado en la auditoría §5.1, no implementado.

**Regresión final**: `web-pasajero` build/lint/**10/10**, `web-conductor` build/lint/**6/6**,
`web-interno` build/lint/**27/27** (mismos 3 warnings preexistentes de `useEffect`, no nuevos),
`shared-ui` lint limpio. Backend no se tocó en ningún punto de este bloque (restricción explícita
del brief: "cero cambios de lógica de negocio, endpoints, o comportamiento funcional"), así que no
se re-corrió `pytest` (última corrida registrada: 393 passed + 8 skipped, §19).

**Limitación de verificación, dicha explícitamente en vez de simulada**: sin herramienta de
automatización de Firefox disponible en el entorno — verificado a fondo en Chrome (móvil y
escritorio, tema claro y oscuro, las 3 apps), con revisión de compatibilidad de las funciones CSS
nuevas (`color-mix()`, custom properties, `@font-face` local, `:focus-visible`) contra Firefox
moderno, pero sin poder manejarlo literalmente. Pendiente de confirmación manual del usuario si le
importa ese navegador específico.

## 21. Ronda de correcciones UX/UI (agosto 2026) — capas, fallas, tablas, sidebar y tipografía

5 grupos de observaciones reales de uso sobre el sistema ya rediseñado visualmente (§20). Regla del
pedido: capa de presentación e interacción, sin reabrir identidad visual ya aprobada y sin cambios
de lógica de negocio. Los 5 quedaron cerrados y verificados en navegador real, uno por uno antes de
pasar al siguiente.

### 21.1 Grupo A — capas flotantes sobre el mapa

**Causa raíz real (una sola, para las 2 observaciones)**: Leaflet fija `position:relative` en su
contenedor pero **nunca un z-index**, así que sus capas internas (`.leaflet-pane` 400,
`.leaflet-control` 800, `.leaflet-top/.leaflet-bottom` 1000) competían en el **contexto de
apilamiento raíz** contra las del `AppShell`. El header es `z-index:20` y crea contexto propio, así
que el panel de `NotificacionesBell` (z-index 50 dentro de él) topaba en 20 efectivo y quedaba por
debajo del mapa. De ahí también el `zIndex:1001` "mágico" que el overlay de `web-conductor` había
necesitado.

- **Escala de capas como tokens** en `tokens.css`: `--z-map: 0`, `--z-map-overlay: 10`,
  `--z-header: 20`, `--z-backdrop: 30`, `--z-sidebar: 40`, `--z-dropdown: 50`, `--z-modal: 100`.
  Todos los z-index sueltos del proyecto (AppShell.css, DetailPanel, KpiDetalleModal,
  NotificacionesBell, los 2 overlays de mapa) apuntan ahora ahí — no queda ninguno hardcodeado.
- **Regla `.leaflet-container { z-index: var(--z-map) }`**: encierra a Leaflet en su propio
  stacking context. Sin esto la escala no sirve de nada — es la pieza que hace comparables los
  valores. No cambia el orden interno del mapa.
- **`MapOverlayCard`** (nuevo, `shared-ui`): la tarjeta flotante sobre el mapa, compartida por
  `web-pasajero` y `web-conductor` (antes cada app repetía el mismo bloque inline con su propio
  z-index). Aporta el plegado a un resumen de una línea (`max-height` animado, no `display:none`,
  con `prefers-reduced-motion`), y se re-expande sola cuando cambia el estado del viaje. Una oferta
  entrante en conductor pasa `plegable={false}` — esconderla sería perder el viaje.
- **El elemento signature se preserva en ambos estados**: los marcadores de la franja de ruta
  (punto hueco / línea punteada / punto sólido) se extrajeron a constantes en `web-pasajero`
  (`puntoOrigenStyle`/`puntoDestinoStyle`) y se usan tanto en la presentación vertical (expandida,
  anclando los 2 `TextField`) como en la horizontal (`ResumenRuta`, el resumen colapsado). Es el
  mismo motivo, no una reconstrucción.
- **Duplicación eliminada de paso** (la detectaron los tests, no una revisión visual): al mover el
  badge de estado al resumen, quedaba repetido en el cuerpo. Se quitó del cuerpo en los 2 portales
  — en conductor eso además borró un `Badge` que mostraba el **enum crudo** del backend
  (`EN_CAMINO`), ahora legible vía `ETIQUETA_ESTADO_VIAJE`.

**Verificado** (móvil 375x812 primero, después escritorio 1280x720, en los 2 portales, con
`getComputedStyle`/`elementsFromPoint` reales): leaflet z=0 / tarjeta z=10 / header z=20; el panel
de notificaciones queda **por encima** de `.leaflet-container` en la pila real de ambos portales;
tarjeta 408px→54px (pasajero) y 320px→54px (conductor) al minimizar, con la franja punteada visible
en el resumen y `aria-expanded`/`aria-label` correctos.

### 21.2 Grupo B — reporte y consulta de fallas del vehículo

- **Sección propia** "Fallas del vehículo" en `web-conductor` (`FallasView`), con el patrón de
  lista/detalle ya establecido: `DataTable` + botón "Ver" por fila + `DetailPanel` en modo consulta,
  con evidencia fotográfica renderizada.
- **Se quitó del flujo de viaje** el botón suelto "Reportar falla del vehículo" (estaba duplicado
  en la tarjeta de FUERA_DE_LINEA y en el panel del mapa). **"Registrar incidencia" DENTRO de
  `ViajeAsignadoCard` se mantiene tal cual** — ese sí es del viaje (CU-O07 A4: puede cancelarlo y
  reasignar al pasajero), no del vehículo.
- **`ReportarFallaForm` migrado al chrome compartido**: era un `Card` suelto embutido en el panel
  flotante de 340px; ahora usa `DetailPanel` (encabezado, chip "Modo: Nuevo registro",
  Aceptar/Salir en posición fija), igual que el resto del sistema.
- **`EvidenciaImagen` movido a `shared-ui`**: `web-interno` tenía la única implementación
  (`MiniaturaEvidencia`, descarga blob autenticada porque `GET /archivos/{id}` exige Bearer). En vez
  de duplicarla en conductor se subió a compartida y `web-interno` la consume; ganó estado de error
  y prop `tamano`.
- **Único cambio de backend de toda la ronda, y fue inevitable**: no existía forma de que un
  conductor listara sus propios reportes (el único `GET /reportes-falla` está gateado a
  `jefe_mantenimiento` y devuelve los de toda la flota). Nuevo `GET /reportes-falla/mias`, **solo
  lectura**, acotado por `actor.usuario_id` del token (nunca por un id del cliente). Sin cambios de
  lógica de negocio. Test de regresión nuevo que fija el aislamiento entre conductores y los 403
  cruzados.

**Verificado** con un reporte real de punta a punta en navegador (foto PNG generada en el navegador
y subida como `File` real vía el input, no un mock del fetch): creado → visible en el listado →
detalle abierto → evidencia renderizada (120×80 real desde blob autenticado). El reporte de prueba
se borró de Mongo al terminar (el evento de bitácora queda, es insert-only por diseño).

### 21.3 Grupo C — tablas que exceden el espacio disponible

**Medido antes de diseñar nada**: la bitácora del panel táctico de Auditoría medía **1240px dentro
de un contenedor de 559px** en un viewport de 1280 — la columna `1fr` del patrón F. Dato clave: el
problema **no se ve desde el viewport**, es del contenedor. Por eso la solución usa
**`@container`**, no `@media`.

Solución general en `DataTable` (ningún consumidor implementa nada por su cuenta):

1. **Techo de ancho por celda** (`.uf-cell-truncable`, 260px por defecto): sin él el layout
   automático de `<table>` estira una columna hasta su celda más larga. Las columnas con `width`
   explícito siguen haciendo wrap, comportamiento previo intacto.
2. **Previsualización del contenido truncado**: al pasar el cursor **o tocar** una celda recortada
   aparece un popover con el valor completo. Solo dispara si `scrollWidth > clientWidth` — un badge
   o un botón corto nunca la abre. Cierra con `mouseleave`, clic fuera o Escape.
3. **Prioridad de columna** (`prioridad: "alta" | "media" | "baja"`, opt-in): `baja` se retira con
   el contenedor bajo 900px, `media` bajo 700px, y el techo por celda baja a 180px/120px. Una tabla
   que no marque nada se comporta exactamente como antes. Solo se marcó lo que ya se puede leer en
   otro lado.

El scroll horizontal se mantiene como red de seguridad.

**Verificado**: bitácora **1240px → 559px exactos** en su contenedor (`desborda: false`) en
escritorio, y 837→667 en tablet 768 tras subir el umbral angosto de 640 a 700px (el caso real
medido: con el patrón F ya colapsado, 667px todavía necesitaba soltar una columna más).
Previsualización probada sobre un UUID real (251px reales en 120px visibles) por hover y por toque,
confirmando que no aparece en celdas que sí entran. Solicitudes a ancho completo (903px): 0 columnas
ocultas, 0 celdas truncadas — sin efecto colateral.

### 21.4 Grupo D — organización del sidebar

Mismo criterio "personal vs. funcional" en los 3 portales, con los nombres de grupo que tienen
sentido para cada uno, **sin reordenar un solo elemento** de `SECCIONES` (el orden decide la sección
por defecto de cada rol, `seccionesVisibles[0]` — trampa ya conocida, ver §10 y §13.2):

| Portal | Zona funcional | Zona personal |
|---|---|---|
| `web-pasajero` | "Viajar": Viaje, Mis viajes | "Mi cuenta": Mi perfil, Ajustes, Ayuda |
| `web-conductor` | "Operación": Mi turno, Mis viajes, Mis liquidaciones, **Fallas del vehículo** | "Mi cuenta": Mi perfil, Ajustes, Ayuda |
| `web-interno` | "Operación" (encabezado nuevo) + Panel Táctico + Panel Estratégico + Administración + Historial | "Mi cuenta": Mi cuenta, Ajustes, Ayuda |

- `AppShell` reconoce la zona personal por el nombre literal del grupo (`GRUPOS_PERSONALES`, mismo
  mecanismo que `NIVEL_GRUPO`) y la separa con un divisor.
- **Sufijo "(táctico)" eliminado de las 10 etiquetas.** Existía solo porque las pantallas operativas
  no tenían encabezado de grupo y "Flota" chocaba con "Flota"; darles el grupo "Operación" lo hizo
  innecesario. Se buscó el patrón equivalente en el nivel estratégico: **no existía** — esas
  etiquetas siempre fueron limpias, así que quitar el sufijo táctico alinea los dos niveles en vez
  de dejarlo a medias.

**Verificado** en los 3 portales: jerarquía de 3 niveles intacta y medida — Panel Táctico con
marcador de 6px en `rgb(138,75,10)` (`--color-accent-deep`), Panel Estratégico con 8px en
`rgb(242,164,19)` (`--color-accent`), Operación sin marcador. Zona personal con
`data-zona="personal"` y borde superior real. Sección por defecto de `staff-verificacion` sigue
siendo **Solicitudes** tras recargar (confirmado explícitamente, es la regresión clásica de tocar
esta lista).

### 21.5 Grupo E — inconsistencia tipográfica: **(a) intencional Y (b) bug real**, las dos cosas

Diagnóstico obligatorio antes de tocar nada. El resultado fue mixto, así que conviene ser preciso:

- **(a) — la diferenciación Barlow / Big Shoulders Display es intencional y NO se tocó.** Medido en
  los 3 portales: los títulos de pantalla del contenido (`¿A dónde vamos?`, `Fallas del vehículo`)
  y los valores de KPI renderizan en `Big Shoulders Display` 22-26px/700; todo lo demás en Barlow.
  El `h1` del header del `AppShell` en Barlow 14px también es deliberado — es chrome de navegación,
  no un título de pantalla.
- **(c) descartado con evidencia**: `document.fonts.check('700 22px "Big Shoulders Display"')` da
  `true` y la face 700 aparece `loaded` en las pantallas que la usan. La face 900 queda registrada
  pero `unloaded` porque **ningún componente usa peso 900** — no es un fallo de carga.
- **(b) — BUG REAL, corregido.** Los controles de formulario **no heredan `font-family`**: la hoja
  del navegador les impone la suya (Arial en Chrome). Medido con `getComputedStyle`: la navegación
  **completa del sidebar**, el botón de menú, el de cerrar sesión, la campana de notificaciones y
  los chips de direcciones favoritas de `web-pasajero` renderizaban en **Arial**, no Barlow. Los
  componentes de `shared-ui` (`Button`/`TextField`/`Select`/`TextArea`) ya traían
  `fontFamily: "inherit"` inline cada uno por su cuenta — el parche existía, pero solo donde alguien
  se acordó de ponerlo. Corregido con una regla global en `tokens.css`
  (`button, input, select, textarea, optgroup { font-family: inherit }`); solo la familia, el
  `font-size` se deja a los tokens de escala de cada control.

**Verificado** en los 3 portales tras el fix: el barrido de todo `button/input/select/textarea` del
DOM comprobando que la familia computada sea Barlow o Big Shoulders devuelve **lista vacía**, con
los títulos de pantalla intactos en display.

### 21.6 Regresión final

Backend **394 passed + 8 skipped** (subió de 393 por el test nuevo de `/reportes-falla/mias`),
`ruff check` limpio. Frontend: `build` ✅ en las 3 apps, `lint` limpio en `shared-ui` +
`web-pasajero` + `web-conductor` y 0 errores en `web-interno` (los mismos 3 warnings preexistentes
de `useEffect`), `test` **10/10** (`web-pasajero`), **6/6** (`web-conductor`), **27/27**
(`web-interno`).

**Limitación de verificación, dicha en vez de simulada**: el panel del navegador de esta sesión no
estaba componiendo frames, así que **no hay capturas de pantalla** — la verificación se hizo sobre
el DOM real y valores computados (`getComputedStyle`, `elementsFromPoint`, `document.fonts`,
`getBoundingClientRect`) contra el stack real, con interacciones reales disparadas en la página. Un
efecto colateral de eso: las transiciones CSS no avanzan sin frames, así que las mediciones del
plegado se tomaron anulando temporalmente la transición **en la página** (nunca en el código) — el
estado final medido es el real, la animación en sí no se pudo observar y queda pendiente de
confirmación visual del usuario.

### 21.7 Ampliación de evidencia fotográfica (lightbox) — cerrado

Bug reportado sobre el detalle de una orden de mantenimiento: las miniaturas de evidencia no se
podían abrir a tamaño completo. **Diagnóstico previo, porque la sospecha inicial (dos
implementaciones distintas) era falsa**: `MiniaturaEvidencia` (`web-interno/sections/
Mantenimiento.tsx`) dejó de ser una implementación propia en §21.2 — hoy es un wrapper de una línea
sobre `EvidenciaImagen` de `shared-ui`. Y el detalle de orden tampoco tiene render propio: pasa por
ese wrapper. Así que el defecto estaba en el componente compartido y afectaba a **los 5 sitios de
uso**, no solo al reportado:

| Sitio | Archivo |
|---|---|
| Detalle de orden — evidencia heredada del reporte de falla | `Mantenimiento.tsx:1177` |
| Cronología de actividades de la orden | `Mantenimiento.tsx:211` (`TimelineActividades`) |
| Bandeja de reportes de falla, columna Evidencia (**fuera de modal**) | `Mantenimiento.tsx:1504` |
| Detalle de un reporte de falla | `Mantenimiento.tsx:1562` |
| Detalle del reporte propio del conductor | `web-conductor/App.tsx:815` |

Arreglado una sola vez en `EvidenciaImagen`. La miniatura pasó a ser un `<button>` (alcanzable por
teclado y con nombre accesible, no un `<img onClick>`), con `cursor: zoom-in`. La ampliación
**reusa el mismo Object URL ya descargado** — abrirla no dispara una segunda petición al endpoint
autenticado. Cierra por clic en el fondo, Escape y un botón ✕; el clic sobre la propia imagen NO
cierra, a propósito. Prop `ampliable` (default `true`) por si algún uso futuro no la quiere.

**Capa**: token nuevo `--z-lightbox: 110` sumado a la escala del Grupo A (§21.1) — deliberadamente
por ENCIMA de `--z-modal: 100`, porque la ampliación casi siempre se abre desde un `DetailPanel` y
tiene que taparlo. Ningún número suelto.

**Fuera de alcance, dicho explícitamente**: los 2 `<img>` restantes que no pasan por el componente
(`Mantenimiento.tsx:1210` y `web-conductor/App.tsx:642`) son previsualizaciones locales del archivo
*antes* de subirlo (`URL.createObjectURL(file)`), no evidencia servida por el backend — no se
tocaron.

**Verificado en navegador con la evidencia real del entorno** (una foto de 1799×887 px que se
mostraba como miniatura de 120×59 — el caso reportado, literalmente ilegible): en `web-interno`
(detalle de la orden CORRECTIVA de `PBA-1234`, EN_TALLER) la ampliación mide 1244×613 con
`object-fit: contain` sobre un fondo al 82%, con z-index real 110 contra el 100 del `DetailPanel`
debajo; y en `web-conductor` (detalle del reporte propio) el mismo archivo amplía correctamente.
Los 3 mecanismos de cierre confirmados uno por uno, y confirmado además que **Escape cierra solo la
ampliación y deja el `DetailPanel` abierto** (no cierra en cascada) y que el clic sobre la imagen
no la cierra.

Regresión: `build` ✅ en las 3 apps, `lint` limpio en `shared-ui`/`web-pasajero`/`web-conductor` y 0
errores en `web-interno` (los mismos 3 warnings preexistentes de `useEffect`), `test` **10/10**,
**6/6**, **27/27**. Backend sin tocar.

## 22. Foto de perfil general (cualquier rol) + siembra de 26 usuarios ficticios — cerrado

Pedido explícito del usuario vía `prompt_foto_perfil_y_siembra_usuarios.md` (documento adjuntado en
la sesión, no versionado en el repo) + un `.zip` con 26 fotos ficticias (`Perfiles de personas o
avatar.zip`) y `AvataPorDefecto.png`. 2 partes con dependencia real: primero la funcionalidad de foto
de perfil de verdad (Fases 1-2), después la siembra (Fase 3) — nunca al revés.

**Hallazgo real de la Fase 0, que cambió el plan**: `usuarios` NO tenía ningún campo de foto
top-level, pero SÍ existía ya `conductor.foto_url` (Sección 2.2 de `ux_complementaria.md`) — un
campo de texto libre (URL pegada a mano, sin upload real), exclusivo de `conductor`, wireado solo en
`PerfilPropio` de `web-conductor` (`mostrarFoto`). **0/194 usuarios reales lo tenían seteado** —
mecanismo construido pero nunca usado. Se reemplazó por completo (no se mantuvo como fallback: no
había ningún dato real que migrar) por un campo general `usuarios.foto_url` (nullable, para
cualquier rol), con upload real reusando la infraestructura de `archivos/` (Fase A de la ronda de
fallas de vehículo, §18) — confirmada como suficientemente genérica sin tocarla más que agregar un
contexto nuevo.

**Backend**:
- `archivos/service.py`: nuevo contexto `foto_perfil`, el único en `CONTEXTOS_LECTURA_PUBLICA` — a
  diferencia de `reporte_falla`/`actividad_orden` (evidencia sensible, gateada por rol), una foto de
  perfil no tiene nada sensible y una superficie sin sesión ya la necesitaba: la vista pública de
  "Compartir viaje" (§10) mostraba `conductor_foto_url` con un `<img src>` directo, asumiendo una URL
  externa pegada a mano — con el nuevo mecanismo ese valor es un id de archivo, así que sin lectura
  pública esa página se hubiera roto. Mismo criterio de "no listable pero sin sesión" que el token de
  256 bits de Compartir viaje. `puede_ver()` ahora acepta `actor_id: str | None`. Nuevo
  `core/rbac.py::get_current_actor_opcional` (token ausente/inválido → `None`, nunca 401) usado solo
  en `GET /archivos/{id}`; `POST /archivos` y el `GET .../meta` siguen exigiendo sesión real.
- `perfil/`: `PerfilOut.foto_url` ahora lee `usuarios.foto_url` (antes `conductor.foto_url`).
  **Nuevo `PATCH /perfil/foto`** (`PerfilFotoEditar{archivo_id: str | None}`), deliberadamente
  separado de `PATCH /perfil` — **no exige `password_actual`** (la decisión D1 de exigirla es
  específica de contacto/teléfono/correo sin OTP, no aplica a una foto, autoservicio de bajo riesgo y
  reversible). `perfil/service.py::editar_foto_perfil` valida que el `archivo_id` exista, pertenezca
  al actor, y tenga `contexto=="foto_perfil"` (`ArchivoNoValidoParaFotoError`, 422) — evita que
  alguien fije como propia la foto de otro o recicle evidencia de una falla como avatar.
- `viajes/service_dispatch.py`: `conductor_foto_url` (snapshot en el viaje al asignar) ahora sale de
  `usuario.get("foto_url")`, no de `conductor.foto_url`.
- Asset `AvataPorDefecto.png` copiado a `apps/shared-ui/src/assets/avatar-por-defecto.png` (mismo
  criterio que los logos, sin optimizar a fondo — cacheado, carga una sola vez). El campo nunca se
  rellena con esa ruta: se queda `null` sin foto propia, el fallback se resuelve en el frontend.
- **`backend/Dockerfile` corregido de paso**: nunca copiaba `scripts/` a la imagen (`COPY scripts
  ./scripts` agregado) — el contenedor real llevaba meses con un subconjunto ad hoc de scripts
  copiados a mano vía `docker cp` suelto, desincronizado del repo (confirmado: `/app/scripts` tenía
  solo 2 de los ~13 scripts reales antes de este fix). Con esto, `docker exec ... python -m
  scripts.<nombre>` vuelve a funcionar para CUALQUIER script del repo tras un rebuild, sin `docker cp`
  manual previo (salvo assets externos como las fotos de la Fase 3, ver abajo).

**Frontend**: nuevo `Avatar` (`shared-ui`, exportado desde `index.ts`) — `fotoUrl` (id de archivo o
`null`) → `<img src>` directo a `GET /archivos/{id}` (público, sin blob-fetch autenticado, a
diferencia de `EvidenciaImagen`) o al asset por defecto; `onError` degrada al default si el id quedó
huérfano. `AuthProvider` ganó `fotoUrl`/`actualizarFoto` — una sola lectura de `/perfil` al iniciar
sesión (no en cada mount de cada componente), compartida entre `AppShell` (header) y
`AjustesPropios`/`PerfilPropio` sin prop drilling ni duplicar el fetch entre componentes hermanos.
Nueva sección "Foto de perfil" en `AjustesPropios.tsx` (compartida, las 3 apps, sin gate de rol) con
input de archivo real (`subirArchivo(file, "foto_perfil")` + `PATCH /perfil/foto`) y "Quitar foto".
`PerfilPropio.tsx` perdió el campo de URL de texto libre y el prop `mostrarFoto` (`web-conductor` ya
no lo pasa) — el avatar ahí pasó a ser de solo lectura, siempre visible para cualquier rol. Completadas
2 superficies de identidad que ya existían pero mostraban solo texto:
`PanelViajeActivo`/`VistaCompartida` en `web-pasajero` (el conductor asignado) ya tenían
`conductor_foto_url` en el backend desde antes, nunca renderizado hasta ahora.

**Regresión de tests**: 3 archivos de mock (`App.test.tsx` de las 3 apps) necesitaron un handler
default nuevo para `GET /perfil` exacto (mismo patrón ya usado para `/notificaciones/mias`) — el
fetch proactivo de `AuthProvider` se dispara en CUALQUIER test que loguea, no solo en los que tocan
perfil. 2 tests preexistentes (`web-interno`, `web-pasajero`) que ya declaraban un único handler
`/perfil` necesitaron un segundo handler duplicado (uno para el fetch de `AuthProvider`, otro para el
de `PerfilPropio`) para no quedarse sin datos. El test de `web-conductor` sobre foto (antes probaba
el campo de URL en "Mi perfil", ya no existe) se reescribió íntegro para el flujo real de Ajustes,
incluyendo un `bodyEsJson` guard nuevo en su `mockFetch` (`subirArchivo` manda `FormData`, no JSON —
`JSON.parse` sobre eso revienta).

**Fase 3 — 26 usuarios ficticios** (`backend/scripts/seed_usuarios_ficticios.py`, nuevo). Cada
usuario se crea vía el servicio real de su rol (nunca `insert_one`): `usuarios.service.
crear_cuenta_staff` (10 roles de personal interno, todos salvo `integracion_externa` — sin pantalla
ni cuenta de demo por diseño, ver §8.7), `captacion.service.registrar_pasajero` (CU-O02, 8
pasajeros), `captacion.service.crear_solicitud`+`decidir_solicitud(APROBADA)` (CU-O01, 8
conductores, mismo flujo real de `seed_solicitudes_demo.py` — genera también vehículo + 2 documentos
reales por conductor). La foto se asocia con el MISMO mecanismo de la Fase 1 (`archivos.service.
guardar_archivo` + `perfil.service.editar_foto_perfil`, nunca escritura directa a Mongo). Teléfono
determinista `+593980<índice:03d>` (prefijo nunca usado por ninguna cuenta demo documentada en
§8.7) — idempotente, si ya existe se salta la fila entera sin tocar nada; corrida dos veces confirmó
"26 creados / 0 saltados" y luego "0 creados / 26 saltados".

Las 26 fotos (`analytics/seed_data/avatares/`, extraídas del zip, **gitignoreado** —51MB, mismo
criterio que `data/nyc_taxi/`, es un recurso externo adjuntado, no código fuente) siguen el patrón
real de nombre `<Genero> <Edad> años.<ext>` (`Hombre`/`Mujer`; un archivo trae el typo real "naños",
el regex del script solo ancla género+número, lo tolera). Único criterio de asignación disponible en
el nombre de archivo: se ordenaron las 26 de mayor a menor edad y se repartieron en 3 bloques
consecutivos — sin que esto sea ninguna regla de negocio real, solo estética. Nombres estadounidenses
clásicos (anglosajones, para no dejar ambigüedad con la instrucción de "evitar otro país de origen"),
sin repetir combinación.

| Nombre | Rol | Foto | Nombre | Rol | Foto |
|---|---|---|---|---|---|
| James Smith | gerencia | ✅ | Kevin Martin | conductor | ✅ |
| Michael Johnson | admin_sistema | ✅ | Susan King | conductor | ✅ |
| Robert Brown | admin_plataforma | ✅ | Brian Lee | conductor | ✅ |
| David Jones | responsable_plataforma | ✅ | Kenneth Thompson | conductor | ✅ |
| Mary Williams | admin_financiero | ✅ | Ryan White | pasajero | ✅ |
| Richard Miller | jefe_mantenimiento | ✅ | Karen Wright | pasajero | ✅ |
| Jennifer Young | supervisor_cumplimiento | ✅ | Jacob Harris | pasajero | ✅ |
| Linda Allen | coordinador_operaciones | ✅ | Justin Clark | pasajero | ✅ |
| Joseph Davis | coordinador_flota | ✅ | Amanda Scott | pasajero | ✅ |
| Thomas Wilson | admin_captacion | ✅ | Brandon Lewis | pasajero | ✅ |
| Christopher Anderson | conductor | ✅ | Eric Robinson | pasajero | ✅ |
| Daniel Taylor | conductor | ✅ | Gary Walker | pasajero | ✅ |
| Matthew Moore | conductor | ✅ | | | |
| Andrew Jackson | conductor | ✅ | | | |

Las 26 con foto (ninguna se dejó sin foto a propósito — el caso "sin foto" ya está cubierto por las
cuentas demo existentes, que nunca la tuvieron). Credenciales: identificador = teléfono de la tabla
de arriba (`+593980000`.."+593980025" en el mismo orden que la tabla, staff primero 000-009,
conductor 010-017, pasajero 018-025), password **`UsuarioDemo123!`** para las 26. **Los 10 staff
tienen `forzar_cambio_password=true`** (efecto real de `crear_cuenta_staff`, Módulo 1.1/1.3) — el
primer login de cada uno exige fijar una contraseña nueva antes de entrar; confirmado que se puede
volver a fijar la MISMA (`UsuarioDemo123!`), así que la tabla de credenciales sigue siendo válida
tras ese primer paso, solo hay que completarlo una vez por cuenta.

**Verificación real**: backend `pytest` **407 passed** (subió de 394 + 6 tests nuevos de
`archivos`/`perfil` -- los 8 "skipped" de la última cuenta documentada ya no aparecen porque
ClickHouse está arriba en esta sesión y esos tests corren de verdad en vez de saltarse; **1 falla
preexistente sin relación** — `test_servicios_externos_google_maps_sin_configurar` espera que
`GOOGLE_MAPS_API_KEY` esté vacío pero este `.env` sí trae una key real configurada, condición del
entorno, no algo que esta ronda haya tocado). `ruff check src/ tests/` limpio. Frontend `build`/
`lint`/`test` limpios en las 3 apps (`web-pasajero` 10/10, `web-conductor` 6/6 con el test de foto
reescrito, `web-interno` 27/27) + `shared-ui` lint.

En navegador real, contra el stack completo: (1) `web-conductor` — subida real de una foto desde
Ajustes, reflejada de inmediato en el header Y en "Mi cuenta" sin recargar (mismo id de archivo en
ambos `<img src>`), "Quitar foto" revirtiendo a `avatar-por-defecto.png` en los dos lugares a la vez,
confirmado con `naturalWidth`/`complete` reales (no un `<img>` roto); (2) mismo flujo repetido en
`web-pasajero` y `web-interno`, éxito en los 3; (3) aislamiento confirmado por consulta directa a
Mongo tras las 3 pruebas: exactamente 2 cuentas con `foto_url` seteado (las 2 recién tocadas), CERO
en cualquier otra — ninguna cuenta demo se contaminó; (4) las 7 cuentas demo de §8.7 confirmadas
intactas (mismo nombre/roles/`foto_url:null`) tras sembrar los 26 nuevos usuarios; (5) 3 de los 26
nuevos probados con login real en su portal correspondiente — `Ryan White` (pasajero), `Christopher
Anderson` (conductor), `Thomas Wilson` (admin_captacion, incl. el paso de cambio de contraseña
obligatorio) — los 3 con su foto real cargando (`naturalWidth=896`, la dimensión real de las fotos
de origen, no una imagen rota ni el placeholder). **Limitación de verificación, dicha explícitamente
en vez de simulada**: no se probó en vivo que la foto del conductor se vea en la tarjeta de viaje
activo del pasajero (`PanelViajeActivo`) durante un viaje real — el vehículo del conductor demo
(`PBA-1234`) está retirado de servicio por mantenimiento en este momento del entorno (estado
preexistente, sin relación con esta ronda), lo que bloqueó iniciar turno. Verificado en su lugar por
lectura de código: `service_dispatch.py` puebla `conductor_foto_url` desde `usuario.foto_url` en la
misma transacción de asignación, y el componente ya renderiza ese campo con `Avatar`.

**Limpieza**: los 6 archivos de prueba subidos durante la verificación (fotos de 1x1 sintéticas,
nunca las 26 reales) se borraron de Mongo y disco al terminar — ninguna cuenta demo quedó con una
foto de prueba puesta.

## 23. Desglose de tarifa (CU-O08 paso 3) — cerrado

Pedido explícito: la spec dice "el sistema muestra la tarifa final a ambos actores con el desglose
de los tres rubros" — hoy solo se mostraba el número final. Confirmado antes de tocar código: los 3
rubros (arrancada, `costo_km * km_recorridos`, `costo_min_espera * min_espera`) YA se calculaban en
`service_finalizacion.py::finalizar_viaje` para llegar a `bruto`, pero se descartaban justo después
de sumarlos — ningún endpoint los exponía desglosados.

**Backend**: los 3 montos se redondean primero a 2 decimales, y el `subtotal` es la suma de esos 3
YA redondeados (no de los valores crudos) — así lo que el frontend muestra en cada línea siempre
suma exacto al "Subtotal" mostrado, sin sorpresas de coma flotante entre el desglose y el total en
una sola línea. `tarifa_final = round(max(subtotal, carrera_minima), 2)`, sin cambio de fórmula
real (ningún test existente asumía un valor exacto). Nuevo `viajes.schemas.DesgloseTarifaOut`
(`arrancada`/`distancia`/`espera`/`subtotal`) + campo `ViajeOut.desglose_tarifa` — persistido en
`viajes.desglose_tarifa` (sub-documento, `None` en el caso degenerado sin tarifa vigente) y expuesto
por `router_trips.py::to_out()`, el único punto de conversión Mongo→API para TODAS las rutas de
viaje (finalizar, activo, historial, GET por id) — un solo cambio alcanza para que el desglose llegue
a cualquier endpoint que ya devuelva `ViajeOut`. **No se agregó un booleano "piso aplicado"**: el
frontend lo determina comparando `subtotal` contra `tarifa_final` (iguales si no se aplicó el piso,
`tarifa_final > subtotal` si sí) — evita un campo redundante.

**Frontend**: `DesgloseTarifa` nuevo en `shared-ui` (compartido por `web-pasajero`/`web-conductor`,
misma pantalla de viaje finalizado en las dos apps) — 3 líneas + separador + Subtotal en negrita,
más "Carrera mínima aplicada" **solo si** `tarifaFinal - subtotal > 0.005` (epsilon para la
comparación de flotantes ya redondeados, evita falsos positivos por representación binaria). Insertada
justo debajo de la línea "Tarifa final: $X.XX" ya existente en ambas apps, sin reemplazarla.
`km_recorridos`/`min_espera` no estaban expuestos en las interfaces TS de ninguna de las 2 apps
(aunque el backend ya los mandaba) — se agregaron junto con `desglose_tarifa`.

**Verificación real, viaje de punta a punta en las 2 apps** (cuentas `Christopher Anderson`
/conductor y `Ryan White`/pasajero, de los 26 usuarios ficticios de §22 — el conductor demo
`+593911223344` sigue con el vehículo `PBA-1234` retirado de servicio, no se pudo usar):

- **Viaje corto** (destino a 0.1 km, sin movimiento real del conductor): `desglose_tarifa =
  {arrancada:0.5, distancia:0, espera:0, subtotal:0.5}`, `tarifa_final:1.5` — confirmado en pantalla
  en las 2 apps: "Arrancada $0.50 / Distancia (0.0 km) $0.00 / Espera (0 min) $0.00 / Subtotal $0.50
  / **Carrera mínima aplicada $1.50**" (línea visible, el piso sí se activó).
- **Viaje con distancia real**: posición del conductor movida 2 veces (`POST /flota/posiciones`, dos
  saltos de ~1.67 km cada uno — bajo el umbral anti-spoofing de 3 km de
  `flota/service.py::_SALTO_IMPOSIBLE_KM`, la misma técnica ya documentada en rondas anteriores para
  simular desvíos de ruta) hasta acumular 3.34 km reales. Resultado: "Arrancada $0.50 / Distancia
  (3.3 km) $1.17 / Espera (0 min) $0.00 / **Subtotal $1.67**" — sin la línea de carrera mínima
  (correctamente omitida, el subtotal ya supera el piso de $1.50). `Tarifa final: $1.67` coincide
  exacto con el subtotal en pantalla, confirmado en las 2 apps.
- Confirmado con `getComputedStyle`: las 5 líneas usan `display:flex; justify-content:space-between`
  (etiqueta a la izquierda, monto a la derecha), "Subtotal" en `font-weight:600`, "Carrera mínima
  aplicada" en `--color-accent-deep` (distinto del resto, gris tenue), separador con
  `border-top:1px solid var(--color-border)`.
- **Hallazgo real de infraestructura, no un bug de esta ronda**: el turno de un conductor recién
  creado queda en `FUERA_DE_LINEA` en pantalla hasta el primer reporte de posición real aceptado
  (el campo Mongo ya está en `DISPONIBLE`, pero la UI de "Mi turno" no lo refleja sin al menos un
  reporte GPS exitoso) — se resolvió simplemente reportando una posición antes de aceptar ofertas,
  no fue necesario tocar código.

**Regresión**: backend `pytest` **409 passed** (subió de 407 por los 2 tests nuevos de
`test_finalizacion.py`, uno con el piso aplicado y otro sin él, ambos verificando que los 3 rubros
ya redondeados suman exacto al subtotal), misma **1 falla preexistente sin relación** (Google Maps).
`ruff check src/ tests/` limpio. Frontend `build`/`lint`/`test` limpios en `shared-ui`,
`web-pasajero` (10/10) y `web-conductor` (6/6); `web-interno` confirmado sin romper (no se tocó,
solo hereda el `index.ts` de `shared-ui` con la exportación nueva).

## 24. Fotos de perfil en historial de viajes, viaje activo y gestión de usuarios — cerrado

**Fase 0 confirmó 2 piezas reales a reusar, ninguna reconstruida**: el lightbox ya existía, pero
**inlineado dentro de `EvidenciaImagen.tsx`** (Ronda 2 de fallas de vehículo) — sin un componente
propio separable. `conductor_foto_url` ya viaja en `ViajeOut` desde la ronda de foto de perfil
(snapshoteado en el viaje al asignar); `pasajero_foto_url` **no existía en ningún lado**, ni
`usuarios.foto_url` estaba expuesto por `UsuarioOut` (pantalla Usuarios). La tarjeta del conductor
en el viaje activo (`web-pasajero`) ya usaba `Avatar` pero sin ningún `onClick`.

**Refactor previo, no opcional**: para reusar el lightbox de verdad (no duplicarlo) se extrajo
`Lightbox.tsx` (`shared-ui`) del modal que vivía inline en `EvidenciaImagen.tsx` — backdrop con
clic para cerrar, botón ✕, Escape, `z-index: var(--z-lightbox)`, sin cambiar una sola línea de
comportamiento (`EvidenciaImagen` quedó igual de afuera, ahora delegando el modal). `Avatar` pasó a
usar el mismo `Lightbox`, sin segunda implementación.

**`Avatar` gana ampliación, automática y consistente en todos los usos** — no un prop por sitio:
se activa solo cuando `fotoUrl` es una foto propia real (`Boolean(fotoUrl) && !roto`); el avatar
por defecto (ícono genérico, no una foto de la persona) queda como `<img>` plano, sin envolver en
botón, sin `cursor:zoom-in` — ampliarlo no mostraría más que el mismo ícono más grande. Un archivo
roto (404 al cargar) también apaga la ampliación vía estado (`onError` → `roto=true`), ya no vía
manipulación directa del DOM como en la versión anterior.

**Backend — 2 campos nuevos, mismo criterio en los dos**: `ViajeOut.pasajero_foto_url` (nuevo,
resuelto en tiempo de consulta por `service_historial.py::enriquecer_con_pasajero` junto al resto
de la "contraparte limitada" de CU-O14 A2 — mismo dato de identidad visual que ya expone
`pasajero_nombre`, nunca abre un dato nuevo) y `UsuarioOut.foto_url` (nuevo, mismo campo general
`usuarios.foto_url` que ya expone `PerfilOut`). Como `enriquecer_con_pasajero` es un único punto
compartido por `listar_historial` (rol conductor) **y** `listar_historial_global` (Historial de
viajes de `web-interno`), un solo cambio de backend resolvió los 2 endpoints a la vez.
`conductor_foto_url` no necesitó ningún cambio de backend (ya viaja desde la ronda anterior) — solo
faltaba en las interfaces TS más angostas de cada pantalla, nunca en la respuesta real.

**Frontend — 3 pantallas de historial + Usuarios**, mismo patrón en las 4: columna/`DetailField`
existente pasa de texto plano a `<Avatar fotoUrl={...} nombre={...} tamano={28|32|40} /> + nombre`,
sin agregar columnas nuevas. `web-conductor` solo gana la foto del pasajero (nunca teléfono/
ubicación, mismo límite de CU-O14 A2 ya vigente). `web-interno` gana la foto de ambos participantes
en "Historial de viajes" (lista + detalle) y la del propio usuario en "Usuarios" (lista + detalle).
La tarjeta de viaje activo en `web-pasajero` no necesitó ningún cambio de código — hereda la
ampliación en automático al ser el mismo `Avatar`.

**Verificación real en navegador, los 5 puntos**, con cuentas de los 26 usuarios ficticios (§22) y
sus 3 viajes reales (PAGADO/FINALIZADO) entre `Christopher Anderson` (conductor) y `Ryan White`
(pasajero) de la ronda anterior:

- **Avatar + lightbox**: clic abre el diálogo (`role="dialog"`, `aria-modal`, imagen real cargada
  — `naturalWidth` de la foto de origen, no un ícono roto), clic sobre la propia imagen NO cierra,
  clic en el fondo SÍ cierra, Escape SÍ cierra (confirmado que Escape cierra solo el lightbox, no
  el `DetailPanel` debajo cuando se abre desde un detalle — mismo criterio de no-cascada ya
  documentado en §21.7). Hallazgo real de la propia verificación: al abrir el lightbox desde dentro
  de un `DetailPanel`, `document.querySelector('[role="dialog"]')` sin más devuelve el
  `DetailPanel` (también tiene ese rol) en vez del lightbox — hay que filtrar por `aria-label`
  (el lightbox siempre lleva el `alt` de la foto, el `DetailPanel` no) para apuntar al correcto;
  confirmado con `zIndex` real que el lightbox (110) queda arriba del `DetailPanel` (100).
- **`web-pasajero` "Mis viajes"**: foto del conductor en lista y detalle, ampliable, confirmada con
  3 viajes reales de `Christopher Anderson`.
- **`web-conductor` "Mis viajes"**: foto del pasajero en lista y detalle (`Ryan`/`Jacob`, solo
  nombre de pila — CU-O14 A2 intacto, sin teléfono ni otro dato nuevo visible).
- **`web-interno` "Historial de viajes"**: foto de AMBOS participantes en la misma fila/detalle,
  confirmado sobre el dataset real de 1,334,917 viajes (no un mock).
- **`web-interno` "Usuarios"**: foto en lista y detalle de los 26 usuarios ficticios, confirmado
  también que una cuenta SIN foto (`Juan Pérez`, conductor demo) muestra el avatar por defecto como
  `<img>` plano, sin envolver en botón, `cursor:auto` — no ampliable, mismo criterio que en
  cualquier otro lugar donde se usa `Avatar`.
- **Viaje activo (`web-pasajero`)**: no se rehizo un viaje real de punta a punta para este punto
  puntual (no es uno de los 5 puntos de verificación explícitos del pedido, que ya anticipaba "no
  debería requerir trabajo adicional") — confirmado en su lugar por lectura de código: el
  `<Avatar fotoUrl={viaje.conductor_foto_url} .../>` de `PanelViajeActivo` no cambió, hereda la
  ampliación del mismo `Avatar` ya verificado funcionando en vivo en los 5 puntos de arriba.

**Regresión**: backend `pytest` **412 passed** (subió de 409 por 3 tests nuevos —
`pasajero_foto_url` en historial de conductor y en historial global, `foto_url` en listar/obtener
usuario), misma 1 falla preexistente sin relación (Google Maps). `ruff check src/ tests/` limpio.
Frontend `build`/`lint`/`test` limpios en `shared-ui`, `web-pasajero` (10/10), `web-conductor`
(6/6) y `web-interno` (27/27, mismos 3 warnings preexistentes de `useEffect`).

## 22. Auditoría funcional para presentación en vivo — 3 documentos, cerrada

Pedido explícito del usuario (`prompt_auditoria_funcional_presentacion.md`): 3 documentos
(`AUDITORIA_FUNCIONAL_OPERATIVO.md`, `AUDITORIA_FUNCIONAL_TACTICO.md`,
`AUDITORIA_FUNCIONAL_ESTRATEGICO.md`, en la raíz del repo) para que Darwin pueda demostrar el
sistema en vivo ante un docente sabiendo con certeza qué funciona. Estándar exigido explícitamente:
**solo funcionalidad ejecutada personalmente de principio a fin en navegador, contra el stack real,
con datos reales** — nunca inferida de la spec, de `CLAUDE.md`, ni del código. Cada entrada
documenta 9 campos fijos (qué hace, por qué existe, dónde está, qué rol la usa, pasos para
reproducirla, flujo completo con estado previo requerido, qué muestra al completarse, y qué matices
debe saber Darwin para explicarla en vivo).

**Metodología real seguida**: gran parte del nivel Operativo se apoyó en verificaciones ya hechas
en vivo dentro de esta misma sesión de trabajo (fotos de perfil, desglose de tarifa, historial con
fotos — puntos 22-24 más abajo... ver también las entradas de esta sesión) más una ronda nueva de
verificación en vivo para todo lo no tocado todavía: postulación de conductor y registro de
pasajero reales (con aprobación real encadenada, confirmada en la bitácora), un ciclo completo de
viaje de punta a punta (solicitar → ofertar → aceptar → en camino → **compartir viaje real,
confirmado abriendo el enlace público sin sesión** → llegar → iniciar → finalizar con desglose →
pagar → calificación mutua en ambos sentidos), programar un viaje real (con cancelación posterior),
direcciones favoritas, y el ciclo completo de una orden de mantenimiento incluyendo las 3 fases más
recientes del flujo de fallas (§18: `ESPERANDO_REPUESTO` con registro automático en la cronología,
cierre con desviación de costo real, y apertura de una orden correctiva encadenada) — las 3 nunca
se habían verificado juntas en una sola pasada hasta ahora. Nivel Táctico: los 10 dashboards (9
originales + "Rendimiento de Conductores") abiertos uno por uno con la cuenta `staff-verificacion`,
confirmando qué KPI muestra dato real y cuál "—". Nivel Estratégico: los 9 dashboards + Tablero
Ejecutivo con la cuenta `gerencia`, incluyendo un drill-down real (clic en la tarjeta "Documentos
vencidos" de Cumplimiento Normativo) y la confirmación en vivo de que roles sin `gerencia` no ven
Tablero/Rentabilidad/Gobernanza.

**Hallazgo real de esta pasada, no documentado antes en ningún lugar**: existe un **9º dashboard
estratégico real, "Desempeño de Conductores"** (equivalente por trimestre del panel táctico
"Rendimiento de Conductores"), funcional y con datos reales, que nunca se documentó en el cierre
original del nivel estratégico (§13) porque no forma parte de las 8 tarjetas del Tablero Ejecutivo
— quedó fuera del inventario de esa fase sin que nadie lo notara hasta esta auditoría. Incluido
como funcionalidad real número 9 en `AUDITORIA_FUNCIONAL_ESTRATEGICO.md`, con la misma advertencia
de concentración de datos del dataset NYC ya conocida.

**Nada se implementó ni se corrigió en esta ronda** — es un trabajo de verificación y
documentación puro, sin tocar `backend/src` ni `apps/*` (salvo, como efecto colateral esperado y
deseado de la propia verificación, datos reales nuevos en el entorno: una solicitud de conductor
aprobada real con su vehículo habilitado, una cuenta de pasajero nueva, varios viajes reales
completados, una orden de mantenimiento cerrada con una orden encadenada real — todo consistente
con el resto de datos de demo ya existentes, nada de prueba desechable quedó a medias).

**Los 3 documentos quedan en la raíz del repo, listos para consulta directa antes de la demo** —
no se resume su contenido completo aquí para no duplicarlo; son la fuente de verdad de qué mostrar
y qué decir sobre cada limitación conocida.

## 23. Reestructuración conceptual de la auditoría funcional — 4 documentos, cerrada

Pedido explícito del usuario (`prompt_reestructuracion_auditoria_funcional.md`) tras revisar el
entregable de §22: mismo contenido verificado (no se repitió la navegación completa del sistema),
pero con 2 problemas de **clasificación y granularidad** corregidos, no de veracidad. (1) Funciones
transversales (bitácora, notificaciones, catálogo de informes, autoservicio, Administración del
Sistema) estaban mezcladas dentro de "nivel operativo" — no son operaciones propias de una
cooperativa de taxis, son la plataforma que sostiene a los 3 niveles. (2) Fragmentación excesiva:
10 entradas separadas para lo que es un solo proceso (ciclo de vida del viaje: solicitar, despachar,
seguir, cancelar/incidencia, finalizar, pagar, calificar), y lo mismo en mantenimiento y finanzas.

**Estructura nueva, 4 archivos**: `AUDITORIA_FUNCIONAL_OPERATIVO.md` reescrito de 24 entradas a
**7** (2 en Captación, 1 en Operaciones/Despacho — el ciclo completo del viaje con ~9 etapas
explicadas adentro, 1 en Flota, 1 en Mantenimiento — 3 etapas fusionadas, 1 en Finanzas — 4 etapas
fusionadas, 1 en Cumplimiento). `AUDITORIA_FUNCIONAL_TACTICO.md` y `AUDITORIA_FUNCIONAL_ESTRATEGICO.md`
se mantuvieron casi intactos (ya estaban bien planteados conceptualmente — un panel = una función
real de análisis departamental, incluida "Auditoría e Integraciones"/"Gobernanza de Datos" que
analizan datos transversales pero son en sí mismas funciones de análisis legítimas de ese nivel, no
transversales) — solo se corrigieron 3 referencias cruzadas a la numeración vieja de Operativo.
`FUNCIONALIDADES_TRANSVERSALES.md` (nuevo) agrupa 14 entradas en 4 secciones: Trazabilidad y
transparencia de datos (bitácora, catálogo de informes), Notificaciones, Autoservicio del usuario
(perfil/foto/ajustes), y Administración del Sistema (8 módulos) — con el encuadre explícito de que
esta capa es "un mérito, no un relleno".

**Los 2 arreglos de paso pedidos explícitamente**:

1. **Administración del Sistema re-verificada en vivo**, esta vez sí (el entregable de §22 remitía
   a `CLAUDE.md` §9 sin volver a probarla, lo cual violaba el estándar propio del documento). Los 8
   módulos abiertos uno por uno con la cuenta real `admin_sistema`: IAM (226 cuentas reales, política
   de autenticación real), Configuración General (parámetros + 2 feature flags reales), Catálogos (5
   talleres reales, zonas vacías — gap ya conocido), Integraciones (Google Maps activo con clave
   enmascarada, 1 credencial revocada real), Monitoreo (latencias reales medidas en vivo, Airflow
   mostrando "No disponible" real — confirma que el chequeo pinga infraestructura real, no simula),
   Políticas de seguridad + Alertas del sistema (política real, 5 alertas reales), Respaldos (4
   respaldos reales de hasta 2.3GB, 2 restauraciones de prueba con conteos exactos por colección —
   `viajes: 1,334,886`, `pagos: 1,241,750`), Gobernanza de datos (búsqueda real de cuentas, diálogo
   de doble confirmación abierto y verificado — **no se completó la anonimización real**, el propio
   flujo de trabajo de la sesión bloqueó ese último paso como medida de seguridad correcta al ser
   irreversible, decisión respetada sin intentar sortearla).
2. **Causa raíz real de la bandeja "renovaciones pendientes" vacía en Cumplimiento, investigada y
   confirmada — no era un filtro, es un gap real de cobertura.** Leyendo
   `backend/src/cumplimiento/service.py::listar_renovaciones_pendientes`: esa bandeja filtra por
   `renovacion_pendiente != null`, un campo que solo se setea si alguien llamó
   `POST /cumplimiento/documentos/{id}/renovacion` (subir una renovación) — un concepto
   *completamente distinto* de "documento vencido" (que sí tiene datos reales, ver el panel táctico
   de Vigencia Documental). Grep confirmó que **ningún frontend de las 3 apps llama nunca a ese
   endpoint** — no existe ningún botón "Subir mi renovación" en `web-conductor` ni en ningún otro
   lado; la propia pantalla lo delata indirectamente (tooltip del botón "Nuevo" deshabilitado: "las
   renovaciones las suben los propios conductores/propietarios, no el personal interno" — pero no
   hay ninguna pantalla donde puedan hacerlo). Reproducido en vivo: "Ejecutar control de vigencia"
   reportó "Revisados: 160 · Por vencer notificados: 2 · Vencidos nuevos: 2" en el mismo instante en
   que la bandeja seguía mostrando "No hay renovaciones pendientes con este filtro" — confirma que
   **la bandeja estará vacía siempre en este entorno, sin importar cuántos documentos venzan**, no
   es cuestión de ajustar un filtro ni de sembrar más datos. Documentado así, con la instrucción
   explícita para Darwin de no abrir esa bandeja en la demo sin aclarar de antemano por qué está
   vacía, y de usar en su lugar el panel táctico de Vigencia Documental si se quiere mostrar
   vencidos/por vencer con datos reales.

**Nada se implementó ni se corrigió en el código** — mismo alcance que §22, trabajo de
reorganización y verificación adicional puro. Los 4 documentos quedan en la raíz del repo.

## 25. Centro de notificaciones — sección completa + reemplazo del ícono, cerrado

Pedido explícito del usuario: llevar el "Centro de notificaciones in-app" (§2.1 de
`FUNCIONALIDADES_TRANSVERSALES.md`) de solo campana desplegable a una sección propia del sidebar
en los 3 portales, más reemplazar el emoji 🔔 por un ícono real. Fase 0 obligatoria antes de
construir, con 2 hallazgos reales que cambiaron el plan:

- **No existe ninguna librería de íconos en el proyecto** (`grep` de `lucide`/`react-icons`/etc.
  en los 4 `package.json`, cero resultados) — la sidebar nunca tuvo íconos, solo texto + los
  glifos Unicode ★/☆ de favoritos. El único precedente real de ícono hecho a mano es el SVG de
  plegado de `MapOverlayCard` (`stroke="currentColor"`, sin dependencia). Se siguió ESE patrón
  para la campana (un SVG de campana, mismo criterio), en vez de instalar una librería nueva —
  es la aplicación correcta de "reusa lo que ya existe, no agregues algo nuevo" cuando la premisa
  de "ya existe una librería" resultó falsa.
- **`DOCUMENTO_VENCIDO`/`DOCUMENTO_POR_VENCER` (cumplimiento) ya se disparaban desde
  `cumplimiento/service.py` pero faltaban en `CATEGORIA_POR_EVENTO`** (backend) y en
  `ETIQUETA_POR_TIPO` (frontend) — un usuario los veía como el enum crudo sin etiqueta. Corregido
  de una vez, ya que "mapear cada tipo real" era justo el encargo.

**Catálogo real confirmado por grep de cada `notify_user(...)`** (no adivinado): 13 `tipo`
distintos + `ALERTA_SEGURIDAD` que conflacia 5 orígenes reales vía `payload.tipo_alerta`
(`denegaciones_rbac`, `gps_spoofing`, `pipeline_fallido`, `reporte_falla`,
`incidencia_operativa`) — nuevo `apps/shared-ui/src/notificacionesCatalogo.ts`, fuente única de
etiquetas para la campana y la sección completa (antes cada consumidor tenía su propio mapa, ya
desincronizado en la práctica).

**Backend**: `GET /notificaciones/mias` ganó filtros opcionales `tipo`/`leida`/`desde`/`hasta`
(antes solo paginaba) — mismo endpoint, sin sistema nuevo. `no_leidas` se calcula SIEMPRE sin
filtro (global), a propósito: filtrar la lista visible no debe hacer parecer que la bandeja está
al día si hay otras notificaciones sin leer fuera del filtro actual — confirmado con un test que
fija este comportamiento.

**Frontend**: `noLeidas` se movió de `NotificacionesBell` a `AuthProvider` (mismo patrón ya usado
para `fotoUrl`/`diasRestantesBaja` — un estado compartido porque la campana y la entrada nueva
del sidebar son hermanas, no padre/hijo). `AppShellNavItem` ganó `badge?: number`, renderizado
con el mismo `CountBadge` que ya usaba la campana (extraído a componente propio) — nunca un
segundo estilo de indicador. `SeccionNotificaciones` (nueva, `shared-ui`) es el componente único
compartido por los 3 portales: filtros (tipo/estado/rango de fecha, mismo patrón que
`AuditoriaAdmin.tsx`), `DataTable` con distinción leída/no leída (peso de fuente + `Badge`, el
mismo lenguaje visual ya usado en el resto del sistema, no uno nuevo), `DetailPanel` que marca
como leída al abrir (además del botón explícito "Marcar leída", ya existente en la campana,
ahora también en cada fila de la lista). Parametrizada por `tiposRelevantes` (qué tipos ofrece el
filtro — un pasajero nunca ve "Nueva orden de mantenimiento") y `resolverAccionRapida` (a dónde
navega cada tipo, app-específico: `web-interno` usa `useIrASeccion()`, los otros 2 usan su propio
`setVista`).

**Mapa real de acción rápida por tipo, confirmado contra roles/destinatarios reales antes de
enrutar** (`web-interno`): `NUEVA_SOLICITUD` → Solicitudes; `denegaciones_rbac`/`gps_spoofing` →
Auditoría (misma bitácora, CU-O17); `pipeline_fallido` → Plataforma (corridas); `reporte_falla` →
Mantenimiento **operativo** (pestaña "Reportes de falla", no el dashboard táctico); 
`incidencia_operativa` → Despacho (viajes activos) — los 5 destinos verificados contra el rol real
que `ROL_DEFAULT_POR_ALERTA` asigna a cada uno, no adivinados. `web-conductor`/`web-pasajero`: de
los 6+6 tipos reales que cada portal recibe, solo el pasajero tiene pantallas propias donde
aterrizar (Viaje / Mis viajes, con `VIAJE_FINALIZADO`/`VIAJE_CANCELADO_CONDUCTOR` yendo a
Historial en vez del viaje activo, que ya no los tendría) — el conductor no tiene ninguna pantalla
de "mis documentos" ni "mis órdenes de mantenimiento" (gap ya conocido), así que sus 6 tipos son
solo informativos, sin acción rápida fabricada.

**Colisión de nombre resuelta**: la pantalla de administración "Configurar quién recibe cada
alerta" (Módulo 6.3, `admin_sistema`) se llamaba también "Notificaciones" en el sidebar —
renombrada a "Configuración de alertas" (su identidad real: `SeccionConfiguracionAlertas`) para
no dejar 2 ítems idénticos en el sidebar del único rol que ve ambos.

**Verificado en navegador real, los 3 portales**: ícono SVG confirmado (sin `🔔`) en los 3;
contador exacto verificado contra Mongo en 2 cuentas (`staff-verificacion` 57→55 tras 2
detalles abiertos, conductor `+593980010` 1→0 tras "Marcar leída") — mismo número en campana Y
sidebar simultáneamente en ambos casos; 2 tipos reales distintos con navegación real confirmada
(`NUEVA_SOLICITUD` → Solicitudes, `gps_spoofing` → Auditoría); filtro "Tipo" acotado a los 6 tipos
reales de un pasajero (no los 13); distinción visual leída/no leída confirmada con
`getComputedStyle` (peso 700→400 tras marcar). Backend **434 passed + 8 skipped** (subió de 429,
6 tests nuevos), `ruff check` limpio. Frontend build/lint/test limpios en las 3 apps
(`web-pasajero` 10/10, `web-conductor` 6/6, `web-interno` 27/27, con 1 test existente ajustado a
la etiqueta renombrada).

## 26. Mapa en el historial de viajes + cierre de la gestión documental de la postulación

Dos bloques independientes en la misma ronda. Los dos empezaron con una auditoría previa contra
el código real, y en los dos la auditoría cambió el plan.

### 26.1 Hallazgo de infraestructura que invalida corridas de `pytest` previas — leer antes de confiar en un número de tests

`docker-compose.yml` monta **solo** `./backend/src:/app/src` en el contenedor `backend`.
`backend/tests/` NO está montado: viene horneado en la imagen desde el último `docker build`.
Consecuencia real, encontrada en esta ronda: `docker compose exec backend python -m pytest`
ejecuta los tests **de la imagen**, no los del repo. En esta sesión eso produjo 9 fallos
fantasma (tests viejos de `captacion`/`cumplimiento`/`preferencias` que usaban contratos ya
migrados) que no existen en el árbol de trabajo. Tras `docker cp backend/tests
urbanflet-taxiflow-backend-1:/app/` los 9 desaparecieron.

**Antes de correr `pytest` en el contenedor, hacer siempre ese `docker cp`** (o agregar el bind
mount, que no se hizo acá para no tocar la infraestructura del stack sin pedido). `ruff` sí es
confiable sobre `src/` porque ese sí está montado — sobre `tests/` aplica la misma advertencia.

### 26.2 Mapa en el detalle del historial — los 3 portales

**Auditoría previa (lo que había de verdad):**

- **La ruta recorrida SÍ está persistida**, y nadie la estaba usando. `viajes.traza` acumula un
  punto (`{lat, lon, ts, velocidad}`) por cada reporte de posición del conductor durante el
  viaje (`service_ejecucion.py::registrar_punto_traza`, tope `TRAZA_MAX_PUNTOS = 20000`). Es la
  misma fuente con la que se calculan `km_recorridos`/`min_espera`, o sea que la tarifa real ya
  dependía de ella. **`ViajeOut` nunca tuvo un campo `traza`**, así que ningún cliente podía
  leerla — pese a que el docstring de `service_historial.py` afirmaba desde hacía rondas que "el
  detalle expone la traza cruda para que un mapa futuro la consuma". Era falso; corregido.
- La polilínea de Google Directions **no** se persiste en ningún lado (solo se usa en vivo para
  estimar; el único rastro es `datos_posteriores.ruta` del evento de auditoría
  `VIAJE_RECALCULO_RUTA`, un registro puntual de desvío, no la ruta del viaje).
- `web-pasajero` **ya tenía un mapa** en el detalle del historial, pero le pasaba como `ruta` una
  **recta origen→destino** — visualmente indistinguible de una ruta real. `web-conductor` y
  `web-interno` no tenían mapa.

**Decisión sobre recalcular bajo demanda: NO.** Se descartó llamar `estimarRuta` al abrir el
detalle, por tres razones: (1) existe el dato real (la traza), y un recálculo sería peor
información, no mejor; (2) devolvería la ruta *óptima de hoy*, no la que el vehículo tomó —
para un viaje de 2021 del dataset NYC eso no significa nada; (3) costaría una llamada a Google
Directions por cada apertura de detalle. **Cuando no hay traza no se dibuja ninguna línea**:
solo los 2 marcadores y una nota que dice por qué. Verificado en navegador que en ese caso el
`overlay-pane` de Leaflet tiene **0 paths** — ni siquiera una recta punteada que pudiera
confundirse con un recorrido.

**Backend** (`ViajeOut.traza: list[tuple[float,float]] | None`):
`service_historial.simplificar_traza()` convierte la traza cruda a pares `[lat, lon]` con
muestreo uniforme si supera `TRAZA_MAX_PUNTOS_SALIDA = 400` — el muestreo **solo descarta puntos
reales** y conserva siempre el primero y el último, nunca interpola (hay un test que lo fija).
Devuelve `None` (no `[]`) cuando no hay traza, para que el frontend distinga "sin recorrido
registrado" de "recorrido de cero puntos", que no es un estado real. `to_out(doc, *,
incluir_traza=False)` — apagado por defecto: la traza solo viaja en endpoints de DETALLE, nunca
en una lista (20 filas × hasta 20 000 puntos sería absurdo; hay un test que lo fija).

**Ruta nueva: `GET /viajes/historial-global/{viaje_id}`** (`router_trips.py`). Existe porque
`GET /viajes/{viaje_id}` exige que el actor sea el pasajero o el conductor de ese viaje — un rol
interno de supervisión nunca lo es y siempre recibiría el 404 genérico. `web-interno` pide la
traza aparte al abrir el detalle (la lista sigue alimentando el resto de campos), y un fallo de
esa llamada degrada al estado "sin traza", no rompe el panel.

**Alcance RBAC de la traza — verificado explícitamente, no "es interno y ya".** La traza es un
dato de ubicación sensible, así que el alcance queda fijado aquí y por tests. Solo **2**
endpoints en todo el backend la serializan (`to_out(..., incluir_traza=True)`; el default es
`False`, así que ninguna lista la lleva, ni siquiera `GET /viajes/activo`):

| Endpoint | Quién puede |
|---|---|
| `GET /viajes/{viaje_id}` (`router_finalizacion.py`) | **Solo los participantes de ESE viaje** — el propio pasajero o el propio conductor. Sin gate de rol: es un chequeo de pertenencia (`pasajero_id`/`conductor_id` contra el actor), y quien no lo es recibe el 404 genérico que no revela si el viaje existe |
| `GET /viajes/historial-global/{viaje_id}` (`router_trips.py`) | Exactamente 4 roles: `coordinador_operaciones`, `supervisor_cumplimiento`, `gerencia`, `admin_sistema` |

Esos 4 no son una lista nueva: el detalle reusa **el mismo objeto de dependencia**
(`_historial_global_roles`) que ya gateaba la lista de la que se abre — **ningún rol ganó ni
perdió acceso** respecto de lo que ya podía ver. En particular, `coordinador_flota`,
`admin_captacion`, `jefe_mantenimiento` y `admin_financiero` **no** pueden abrirlo, igual que no
pueden abrir la lista.

Como este proyecto ya arrastró más de una deriva de alcance de RBAC en endpoints nuevos, hay 9
tests que lo fijan (`tests/viajes/test_historial_global.py`): los 4 roles permitidos
parametrizados (200 + traza no nula), los 4 roles internos denegados parametrizados (403), y un
guard estructural que falla si alguien cambia el gate de la lista o el del detalle sin cambiar
el otro.

**Frontend: `MapaRutaViaje` nuevo en `shared-ui`** (+ `MapaRutaViaje.css`), usado por los 3
portales. De solo lectura — `RideMap`/`DriverMap` siguen siendo los mapas del viaje en curso.
Detalles de diseño:

- Marcadores con **la franja de ruta "signature"** (§20) reusada literalmente: círculo hueco con
  borde `--color-accent-deep` = recogida, círculo sólido de tinta = destino. Van como `L.divIcon`
  y no como el pin PNG de Leaflet — evita el parche de assets del bundler que `RideMap` necesita
  y mantiene el lenguaje visual del sistema dentro del mapa. Debajo, la versión estática
  horizontal de la franja (punto hueco → línea punteada → punto sólido) con las direcciones.
- El trazo usa `pathOptions={{ className: "uf-traza-viaje" }}` + CSS, **no** `color`: el color
  sale de un token que cambia con el tema, y una custom property no se resuelve dentro de un
  atributo de presentación SVG — sí dentro de una propiedad CSS.
- `Encuadrar` hace `fitBounds` sobre todo lo que hay que mostrar (sin esto, un destino fuera del
  zoom inicial quedaba invisible).
- 3 estados honestos: con traza (nota "Recorrido real del vehículo según su traza GPS (N puntos
  registrados)"), sin traza (solo marcadores + nota explícita de que no hay dato real), y sin
  ninguna coordenada (recuadro punteado con el motivo, nunca un mapa vacío roto).

**Verificado en navegador real, con datos reales de este entorno**, los 3 casos:

- `web-pasajero` (`+593980018` Ryan White): viaje PAGADO con traza → `path.uf-traza-viaje` con
  `stroke: rgb(138,75,10)` (= `--color-accent-deep`), 10 tiles, 2 marcadores, nota "3 puntos
  registrados". Viaje SIN_CONDUCTOR → **0 paths en el overlay**, 2 marcadores, nota de "no dejó
  traza GPS".
- `web-conductor` (`+593980010` Christopher Anderson): mismo viaje desde el otro lado, traza real.
- `web-interno` (`staff-verificacion`): el viaje `b68df283-…` con **264 puntos reales** (nota
  confirmada en pantalla), y el caso sin destino (`9828578c-…`): 1 marcador de origen, **0
  marcadores de destino**, leyenda "Sin destino registrado", y la traza real igual dibujada — la
  pantalla no se rompe.
- Sin errores nuevos de consola en ningún portal. 14 tests nuevos en
  `tests/viajes/test_historial_global.py` (5 de comportamiento de la traza + 9 de RBAC).

### 26.3 Gestión documental en la postulación — qué ya existía y qué faltaba conectar

**El backend completo YA estaba construido** (trabajo sin commitear de una sesión previa, no
documentado en este archivo — §3.1 seguía listando "carga de documentos de postulación" como
backlog, y era información vieja). Lo que faltaba era **el frontend de las Fases 1 y 2** y **una
pieza de la Fase 3**. Inventario real:

| Pieza | Estado encontrado |
|---|---|
| Contexto `documento_postulacion` en `archivos/` (roles: dueño + `admin_captacion`/`admin_sistema`) | Ya existía |
| `DocumentoInput.archivo_id` (migrado de `url_objeto`/`hash_archivo` de texto libre) | Ya existía |
| `POST /captacion/solicitudes/mia/documentos` (adjunta + pasa a ENVIADA) | Ya existía |
| `_validar_tipos_documento` contra el catálogo `tipos_documento` | Ya existía |
| `_aprobar_solicitud_en_transaccion` creando registros reales en `documentos` | Ya existía |
| `SolicitudOut.documentos` expuesto por API | Ya existía |
| **Formulario de postulación de `web-conductor`** | **Faltaba** — mandaba `documentos: []` y el texto prometía un "paso posterior" inexistente |
| **Revisión de documentos en `Solicitudes.tsx`** | **Faltaba** — se aprobaba/rechazaba sin ver un solo documento |
| **Consulta del estado documental de UN socio por personal interno** | **Faltaba** — solo había bandejas agregadas por documento, nunca por persona |

**Catálogo de tipos**: `LICENCIA_CONDUCIR` y `MATRICULA_VEHICULAR` (los 2 ya sembrados) alcanzan
para lo pedido. No se agregó ninguno — SOAT y similares no existen en el catálogo real y
inventarlos habría metido un tipo sin respaldo en el dominio.

**Fase 1 — carga real en la postulación** (`web-conductor`). Licencia de conducir + matrícula del
vehículo, cada una con archivo real y fecha de caducidad, ambas obligatorias. El envío pasó
de 1 a **3 llamadas encadenadas, y el orden no es negociable**: `POST /archivos` exige un actor
autenticado y la cuenta del postulante recién existe después de crear la solicitud. Secuencia:
`POST /captacion/solicitudes` con `enviar:false` (BORRADOR — invisible para Captación, sin
notificar a nadie) → `POST /auth/login` con las credenciales que el propio postulante acaba de
definir → `POST /archivos` ×2 → `POST /captacion/solicitudes/mia/documentos` (adjunta y pasa a
ENVIADA de una vez). Si algo falla a mitad, la solicitud queda en BORRADOR y se puede reintentar
— **nunca queda una solicitud enviada sin sus documentos**. La sesión abierta es instrumental y
se cierra en el `finally` (`tokenStorage.clear()`): el postulante termina en "Solicitud enviada"
sin sesión, igual que antes.

**Fase 2 — revisión en Captación** (`Solicitudes.tsx`). Bloque "Documentos enviados" en el panel
de detalle: cada documento se **ve de verdad** (`EvidenciaImagen`, el mismo visor con ampliación
del resto del sistema), con su fecha de caducidad y un semáforo de vigencia calculado contra hoy
(`Vencido hace N d` / `Vence en N d` / `Vigente`) — sirve para detectar de entrada que alguien
mandó una licencia ya vencida. **No se creó ninguna máquina de estados paralela**: aprobar u
observar la documentación ES la decisión de la solicitud (APROBADA/OBSERVADA/RECHAZADA con motivo
obligatorio cuando no es aprobación), que ya vivía en ese mismo panel.

**Fase 3 — aprovechamiento downstream.** De los 5 usos pedidos, **4 ya existían y solo se
confirmaron**, 1 se construyó:

| Uso | Resultado |
|---|---|
| Detectar próximos a vencer / vencidos | **Ya existía.** Confirmado en vivo: `ejecutar_control_vigencia_documental` barre `documentos` sin filtrar por origen, así que los de una postulación entran solos. "Revisados" pasó de 160 (corrida documentada en §23) a **162** tras aprobar la solicitud de prueba — exactamente los 2 documentos nuevos, cero código adicional |
| Notificar al conductor (por vencer) | **Ya existía.** `DOCUMENTO_POR_VENCER` → categoría `cumplimiento`, con `_usuario_a_notificar` resolviendo también los documentos del vehículo hacia su propietario |
| Informar cuando ya venció | **Ya existía.** `DOCUMENTO_VENCIDO`, mismo mecanismo |
| Consulta rápida del estado documental de un conductor por personal interno | **Construido.** `GET /cumplimiento/documentos/conductor/{id}` (mismo servicio y criterio de propiedad que el autoservicio `/documentos/mios`, solo cambia de quién se consulta), gateado a `supervisor_cumplimiento`/`admin_captacion`/`coordinador_flota`/`admin_sistema`/`gerencia`. Se muestra en el detalle de "Administración → Usuarios", **solo** para cuentas con rol `conductor` (para cualquier otro la respuesta sería siempre vacía) |
| Bloquear operaciones por documentación vencida | **NO implementado, por instrucción explícita.** En su lugar hay advertencia visible en los dos lados: banner rojo en "Mis documentos" del conductor y en el detalle de Usuarios. Ambos textos dicen explícitamente que el sistema **no** bloquea nada por este motivo. **El bloqueo queda como decisión operativa pendiente de la cooperativa — no activarlo sin pedido explícito** |

**Verificación real, extremo a extremo, en navegador**: postulación completa de "Postulante
Documental QA" (`+593960000777` / `DocQA12345!`, cédula `0977700077`, placa `DQA-7770`) con 2
PNG reales generados en el canvas del navegador y subidos por el input de archivo real (no un
mock de `fetch`). Cadena de red confirmada: `solicitudes` 201 → `auth/login` 200 → `archivos`
201 ×2 → `mia/documentos` 200. En Mongo: solicitud ENVIADA con los 2 documentos resueltos, y los
`archivos` con **6224 B / 6389 B** — los bytes exactos de los PNG generados — con `hash_sha256`
calculado en el servidor y contexto/dueño correctos. Revisión en `web-interno`: los 2 documentos
visibles con `naturalWidth=320, naturalHeight=200` (las dimensiones reales del canvas), fechas y
badges de vigencia; Tomar → EN_VERIFICACION → Aprobar. Tras aprobar: rol `conductor` asignado,
vehículo `DQA-7770` HABILITADO, y **2 registros reales en `documentos`** con los mismos ids de
archivo y hashes, `estado_verificacion: CONFORME`. Advertencia de vencido confirmada en los dos
lados (se venció temporalmente la licencia del socio de prueba y **se restauró a `2028-05-31`**
al terminar): banner en "Mis documentos" del conductor (`rgb(178,58,31)` sobre
`rgba(178,58,31,0.14)`) y en el detalle de Usuarios de un socio real con licencia vencida hace
218 días.

**La cuenta de prueba se dejó en el entorno a propósito** (no se borró): es coherente con el
resto de datos de demo y es el único socio cuyos documentos entraron por el flujo real de la UI
en vez de por `seed_solicitudes_demo.py` — útil para mostrar el circuito completo.

### 26.4 Regresión

Backend **476 passed** (subió de 459 tras el `docker cp` de §26.1 — 17 tests nuevos: 5 de
comportamiento de la traza, 9 que fijan su alcance RBAC, 3 de la consulta documental interna),
`ruff check src/ tests/` limpio (se corrigieron de paso 2
E501 preexistentes en `captacion/service.py` y 5 en `tests/captacion/test_captacion.py`, dejados
por la sesión previa sin commitear). El único fallo restante es el preexistente y ya documentado
`test_servicios_externos_google_maps_sin_configurar` (condición del `.env` de este entorno, sin
relación). Frontend: `build`/`lint` limpios en `shared-ui` + las 3 apps (los mismos 3 warnings
preexistentes de `useEffect`), `test` **10/10** (`web-pasajero`), **6/6** (`web-conductor`),
**27/27** (`web-interno` — 2 mocks actualizados a los campos nuevos, más una aserción nueva que
ejercita el render real del bloque de documentos).

**Limitación de verificación, dicha en vez de simulada**: el panel del navegador no estaba
componiendo frames, así que **no hay capturas de pantalla** — todo se verificó sobre el DOM real
y valores computados (`getComputedStyle`, `naturalWidth`, conteo de `path` en el overlay de
Leaflet, log de red real) contra el stack real, con interacciones reales disparadas en la página.

## 27. Segundo rediseño visual (v2) — paleta, sidebar configurable, limpieza de jerga, migración de componentes

Continuación del rediseño de agosto 2026 (§16), no un reinicio — mismo criterio: cero cambios de
estructura/navegación/tipografía/lógica de negocio. Documentos de la ronda:
[AUDITORIA_REDISENO_V2.md](AUDITORIA_REDISENO_V2.md) (Fase 0) y
[PLAN_REDISENO_V2.md](PLAN_REDISENO_V2.md) (Fase 1, aprobado tal cual por el usuario, incluidas
las 2 decisiones explícitas: estrellas de calificación se quedan como notación de contenido, y
"estados positivos" se interpretó como énfasis de marca, no como reemplazar el verde de éxito).

**Fase 0 — hallazgos reales**: el sidebar confirmado como fijo oscuro deliberado desde 2 rondas
(`tokens.css`, comentario explícito) — revertido esta ronda. Inventario exhaustivo por rango
Unicode: 13 glifos de emoji en 9 archivos, de los cuales 6 eran iconos funcionales reales (☰ menú,
✕ cerrar, ★/☆ favorito del sidebar, ☆ guardar dirección, 📷 evidencia, ▲/▼ expandir) y 14 usos de
"★" eran notación de calificación ("4.5★"), no iconos — dejados como estaban con aprobación
explícita. Inventario de texto de desarrollador en los 3 niveles y 3 portales (no solo estratégico,
que ya se había limpiado en una ronda anterior): 7 códigos `CU-O*` visibles en pantalla (2
encabezados, 1 tooltip real), 2 referencias directas a `CLAUDE.md`, una nota completa con
Airflow/webhook/backend/log sin traducir, 4 lugares mostrando `dag_id` crudo del backend
(`PanelPlataforma.tsx`/`PanelCapacidades.tsx`) sin diccionario de etiquetas, 2 lugares mostrando
`rol_destinatario_default`/`roles` crudos sin pasar por `nombreRol()` (gap que quedó fuera de la
ronda de unificación de lenguaje anterior), y un párrafo entero en `PanelPlataforma.tsx` que no
tenía ninguna sustancia honesta que conservar (explicaba una divergencia con una spec interna, pura
historia de desarrollo) — eliminado, no reescrito. Nombres de motor de BD en `Monitoreo.tsx`/
`Respaldos.tsx` evaluados y mantenidos (mismo criterio ya aprobado para `FuenteBadge`: son
pantallas técnicas reales para `admin_sistema`, el motor **es** el objeto monitoreado/respaldado) —
salvo una frase de implementación real encontrada **durante la verificación en navegador, no en la
auditoría** ("Exportación real vía los drivers del backend, no `mongodump`/`clickhouse-client`...")
que sí se simplificó, porque no era una pantalla inherentemente técnica que lo requiriera, era una
explicación de implementación sin sustancia para el usuario.

**Bloqueador del logo — cerrado en una sesión posterior.** La imagen que el usuario compartió en
el chat nunca pudo extraerse por esa vía (sigue sin existir ninguna herramienta en este entorno
para leer bytes de un adjunto pegado en la conversación, solo rutas de archivo del repo). El primer
intento de desbloqueo falló: `logo_urbanflet.png` (raíz del repo) seguía siendo el logo anterior
(mismo `mtime` del 7 de agosto, sin diff), verificado con el mismo chequeo dos veces. El archivo
correcto resultó tener **otro nombre**: `Logo_urbanfleet_final.png` (raíz del repo, 1536×1024,
`mtime` 23 de agosto — confirmado antes de tocarlo). Es el taxi amarillo con wordmark "Urban"
(negro) + "Fleet" (ámbar) que el usuario había descrito, con transparencia real (RGBA, no relleno
opaco) — un primer vistazo del PNG completo lo mostraba con fondo negro sólido, pero eso era un
artefacto del visor: el canal alfa confirmó `alpha=0` en las esquinas y en todo el halo de brillo
alrededor del taxi, y "Urban" resultó ser negro **totalmente opaco** (alpha≈254) al inspeccionar
esa región recortada aparte — coincide exacto con la imagen original que el usuario había
compartido. Recortadas las 2 variantes que el sistema ya consume (mismos nombres de archivo, así
que ningún import cambia): `logo-urbanflet-icon.png` (solo el taxi + skyline, sin wordmark, bbox
real vía umbral de alfa en vez de distancia de color contra blanco -- el logo anterior no tenía
canal alfa real y necesitó ese método; este si lo tiene -- cuadrado 500×500 con **relleno
transparente**, no blanco como el logo anterior: el badge del sidebar ya pinta su propio fondo
ámbar vía CSS desde esta misma ronda, así que un relleno opaco blanco taparía ese fondo en vez de
dejarlo pasar) y `logo-urbanflet-full.png` (taxi + skyline + wordmark completo, recorte ajustado al
contenido real, 700×517). Verificado en navegador real en los 3 portales: el badge del sidebar
carga el ícono nuevo (500×500) sobre el fondo ámbar, y las 3 pantallas de login cargan el logo
completo (700×517) sobre el lavado ámbar ya implementado -- ambos casos confirmados por
`naturalWidth`/`naturalHeight` reales, no solo por nombre de archivo.

**Fase 2 — implementado**:

- **Paleta**: `--color-info`/`--color-info-bg` nuevos (ambos temas) — el sistema no tenía ningún
  tono informativo distinto de éxito/advertencia/peligro/neutral. El resto de la paleta de
  contenido (`--color-accent`, danger/success/warning, `--chart-series-*`, `--status-*`) no se
  tocó — el ámbar de marca ya era el tono correcto, confirmado contra el logo nuevo (aunque el
  archivo real del logo sigue pendiente, ver arriba).
- **Sidebar configurable** (`apps/shared-ui/src/sidebarTono.ts`, nuevo, mismo patrón que
  `theme.ts`/`densidad.ts`/`tamanoTexto.ts`): 4 opciones predefinidas (Claro, default; Ámbar;
  Oscuro; Grafito), cada una con su propio set de 10 tokens (`--color-sidebar-bg/text/
  text-strong/text-muted/border/hover/active-bg/active-text` + 2 nuevos,
  `--color-sidebar-rail-subtle/bold`). Preferencia por cuenta real (`sidebar_tono` en
  `preferencias_usuario`, default `"claro"`, mismo endpoint `PATCH /preferencias`), independiente
  del tema claro/oscuro del contenido — verificado en navegador real que cambiar el tema a oscuro
  no mueve el sidebar de su opción elegida, y viceversa. Selector nuevo en "Ajustes" ("Color del
  sidebar"), visible en los 3 portales sin gating de rol.
  - **Hallazgo real que esto obligó a resolver**: el ámbar de marca brillante (`--color-accent`),
    usado hasta ahora directo en 3 lugares del sidebar (rail del ítem activo, estrella de
    favorito, marcador "Panel Estratégico"), da solo **1.65:1** contra un fondo de sidebar claro —
    falla el mínimo de 3:1 de WCAG 1.4.11 para componentes no textuales. Los 3 se migraron a
    `--color-sidebar-rail-bold` (un tono por swatch, no un valor fijo): `#b36a0a` en Claro/Ámbar
    (3.35:1, verificado), `#f2a413` en Oscuro/Grafito (sin cambio de valor, ya validado). El
    marcador "Panel Táctico" (antes `--color-accent-deep`, un token de CONTENIDO ligado al tema)
    pasó a `--color-sidebar-rail-subtle` por el mismo motivo — mezclar un token de contenido con
    un eje de preferencia de sidebar independiente daba combinaciones ilegibles (ej. sidebar
    "Oscuro" + tema de contenido claro). El `:focus-visible` del sidebar (antes fijo en
    `--color-accent`) también pasa a `--color-sidebar-rail-bold`. Los 4 sets de valores quedan
    documentados con su contraste real en `PLAN_REDISENO_V2.md` §3.
  - Verificado en navegador real, cuenta real: las 4 opciones cambian el fondo/texto/rail
    correctamente (valores RGB computados exactos contra los hex esperados), la opción "Claro"
    limpia las propiedades inline en vez de fijarlas (confirmado que `document.documentElement`
    queda sin ningún `--color-sidebar-*` inline tras volver a "Claro"), sobrevive a recarga
    completa de página (cache local + `GET /preferencias`), y el foco de teclado dentro del
    sidebar (`Tab` real, no `.focus()` programático) resuelve al rail-bold correcto.
  - Badge del logo en el sidebar: pasó de fondo blanco fijo a `--color-accent` (más presencia de
    marca en la zona de marca, sin pintar toda la barra) — y el wordmark "UrbanFleet TaxiFlow"
    pasó de `color:"#fff"` fijo (invisible sobre un sidebar claro) a
    `var(--color-sidebar-text-strong)`.
  - Lavado suave de ámbar en las 3 pantallas de login (`radial-gradient` con `color-mix()` sobre
    `--color-bg`) — verificado que el navegador resuelve el `color-mix()` a un color real (no
    quedó como `none`).
- **Emojis reemplazados** (SVG a mano, mismo patrón ya establecido por `NotificacionesBell.tsx` —
  no hay librería de íconos instalada, confirmado antes de tocar nada): ☰, ✕, ★/☆ del sidebar, ☆ de
  "Guardar como favorita", 📷, ▲/▼ (ahora un solo chevron que rota 180° según estado). Las 14
  estrellas de calificación ("N★") se dejaron sin tocar, aprobado explícitamente.
- **Texto de desarrollador limpiado**, con la regla "la sustancia se queda, la jerga se saca"
  aplicada caso por caso (detalle completo en `AUDITORIA_REDISENO_V2.md` §3): 7 códigos `CU-O*`
  quitados sin tocar la frase que los acompañaba; 2 referencias a `CLAUDE.md` quitadas (una de
  ellas, en `PanelDocumentacion.tsx`, además corrigió el mensaje al estado real — ya hay 162
  documentos reales, no "backlog consciente" como decía desde antes de esa ronda); "backlog
  consciente" reemplazado por lenguaje simple en 2 lugares más; "% error API"/"Endpoints
  activos"/"Uso de API por endpoint" renombrados a "% de errores"/"Integraciones usadas"/"Uso de
  integraciones por ruta" (el dato crudo de ruta en el eje del gráfico se mantuvo — es la
  dimensión real que se mide, no jerga decorativa); "GPS spoofing" reemplazado por "falsificación
  de ubicación GPS"; "Monitoreo y observabilidad" reemplazado por "Monitoreo del sistema"; "(DR)"
  suelto quitado de Respaldos (RTO/RPO se dejaron, ya vienen traducidos al lado). Nuevo diccionario
  compartido `apps/shared-ui/src/dominios.ts` (`nombreDominio()`, mismo patrón que
  `roles.ts::nombreRol()`) para los 7 `dag_id` reales (confirmados contra ClickHouse) mostrados
  hasta ahora crudos en 4 lugares de `PanelPlataforma.tsx`/`PanelCapacidades.tsx` (columna de
  tabla, filtro, 2 ejes de gráfico, 1 KPI). `nombreRol()` (ya existente) aplicado en 2 gaps que
  quedaron fuera de la ronda de unificación de lenguaje anterior: `ConfiguracionAlertas.tsx`
  (columna y detalle de "rol por defecto") y `GobernanzaDatos.tsx` (columna "Roles").
- **Componentes migrados** (auditoría de `shared-ui`, `AUDITORIA_REDISENO_V2.md` §4): `TabButton`
  estaba duplicado **4 veces, byte por byte idéntico**, en `Catalogos.tsx`/`Integraciones.tsx`/
  `Mantenimiento.tsx`/`Respaldos.tsx` — centralizado en
  `apps/shared-ui/src/components/TabButton.tsx`, mismo aspecto y props, los 4 archivos solo
  perdieron su definición local y ganaron el import. `Alert` nuevo (`tono: exito/advertencia/
  peligro/informativo`) reemplaza los 2 avisos de "documentación vencida" que estaban hechos a
  mano y duplicados (`web-conductor/App.tsx`, `Usuarios.tsx`) — mismo aspecto visual confirmado en
  navegador (colores RGB idénticos a los que tenían antes de migrar). Modales (`DetailPanel`/
  `KpiDetalleModal`/`Lightbox`) y controles base (`Button`/`Badge`/`Card`/`TextField`/`Select`)
  confirmados ya centralizados — nada que migrar ahí.

**Regresión y verificación real**: backend **477 passed** (subió de 476 por el test nuevo de
`sidebar_tono`), `ruff check src/ tests/` limpio, mismo fallo preexistente de Google Maps sin
relación. Frontend `build`/`lint`/`test` limpios en `shared-ui` + las 3 apps (`web-pasajero`
10/10, `web-conductor` 6/6, `web-interno` 27/27 — 1 test existente actualizado a la etiqueta nueva
de "GPS spoofing", mismos 3 warnings preexistentes de `useEffect`). Verificado en navegador real,
los 3 portales: sidebar Claro por defecto en los 3, las 4 opciones cambiando fondo/texto/rail con
los valores exactos esperados, persistencia tras recarga completa, tema de contenido independiente
del color de sidebar, foco de teclado real (`Tab`) resolviendo al rail correcto, `TabButton`
cambiando de pestaña con normalidad en Mantenimiento/Respaldos, `Alert` migrado con el mismo
aspecto que antes en Usuarios (cuenta con documentación vencida real), diccionarios de dominio/rol
mostrando nombres legibles en Plataforma/Capacidades/Configuración de alertas/Gobernanza de datos,
y ausencia confirmada de la jerga y los emojis listados en cada pantalla tocada.

**Los 2 puntos que habían quedado sin verificar en vivo -- cerrados en la sesión del logo.** El
ícono de cámara sí tenía un caso real disponible sin construir nada: 3 `reportes_falla` ya
existentes en el entorno traían evidencia real (de sesiones de prueba anteriores) -- verificado
con la cuenta de Juan Pérez (uno de los 3 conductores con un reporte real con foto), confirmando en
el DOM el `<svg aria-label="Con evidencia fotográfica">` en la celda real de la tabla, sin rastro
del emoji. El chevron ▲/▼ del detalle del conductor en un viaje activo de `web-pasajero` sigue sin
verificarse en vivo (requiere un viaje real en curso, no solo historial) -- confirmado por build
limpio y mismo patrón SVG ya verificado en vivo en los otros 5 íconos idénticos en estructura.

## 28. Ronda de correcciones (agosto 2026) — indicadores, permisos, contraseñas, UX de 5 pantallas

9 puntos independientes pedidos en una sola ronda. Los 9 quedaron cerrados y verificados en
navegador real; regresión final: backend **480 passed** (mismo fallo preexistente de Google Maps
sin relación, condición del `.env` de este entorno), `ruff check src/ tests/` limpio; frontend
`build`/`lint`/`test` limpios en `shared-ui` + las 3 apps (`web-pasajero` 10/10, `web-conductor`
6/6, `web-interno` 29/29 — subió de 27 por los 2 tests nuevos de contraseña generada/restablecida).

### 28.1 Tasa de cancelación — corregida de raíz, con un hallazgo real de infraestructura

**Causa exacta confirmada** (no la que ya estaba documentada como "no se puede calcular", sino la
razón real del sobreconteo): `indicadores.refrescar_tasa_cancelacion` calculaba `solicitados` con
el MISMO `GROUP BY periodo, zona, motivo, actor` que particiona los cancelados -- como cada fila de
ese agrupamiento (salvo el bucket `motivo='N/A'`, filtrado por `HAVING cancelados > 0`) contiene
EXCLUSIVAMENTE viajes cancelados, `solicitados` terminaba siendo un sinónimo de `cancelados`, y
`tasa_cancelacion` daba SIEMPRE 1.0. Confirmado en vivo: `PanelDespacho.tsx` (táctico) mostraba
**100.0%** de forma permanente, sin importar el período.

**Corregido con un JOIN** contra una segunda agregación sin la dimensión motivo/actor (universo
real de solicitados por periodo+zona) en `analytics/plugins/indicadores.py`. Como `solicitados`
ahora se repite igual en cada fila de desglose de un mismo periodo+zona, los 2 consumidores reales
(`obtener_panel_confiabilidad` en `backend/src/viajes/service.py`, y
`PanelDespacho.tsx::tasaCancelacionGlobal`) se corrigieron para deduplicar por zona antes de sumar
`solicitados` -- sumar la fila cruda multiplicaría el denominador por la cantidad de motivos
distintos de esa zona.

**Verificado contra un conteo manual directo en Mongo (`viajes`), para 3 períodos reales, no solo
el actual**: 2021-01 (92,778/1,330,055 = 6.98%), 2021-02 (311/4,693 = 6.63%), 2026-08 (47/60 =
78.3%, sumando exactamente los días que `fact_ciclo_viaje` tiene ingeridos para ese mes -- el resto
del mes tiene un gap de pipeline ya documentado en §8.6b, no relacionado con este fix). Los 3
coinciden exactos con lo que el snapshot corregido de ClickHouse y el endpoint real devuelven.

**La advertencia "cifra de referencia, puede estar sobreestimada"** (Confiabilidad estratégico,
`PanelConfiabilidad.tsx`) **ya no aplica y se quitó** -- el número ahora es exacto. El KPI "Tasa de
cancelación" de ese mismo panel, que mostraba "—" (`tasa_cancelacion_disponible=false`), ahora
muestra el porcentaje real (`true`). Ambos paneles (Despacho táctico + Confiabilidad estratégico)
confirmados en vivo con **78.3%** para el período actual.

**Hallazgo real de infraestructura, no relacionado con la lógica del fix**: tras corregir el código
y probarlo con un proceso Python nuevo (que sí lo recogía), la corrida programada de Airflow siguió
publicando el snapshot viejo -- exactamente la gotcha ya documentada en este archivo ("el scheduler
de Airflow con LocalExecutor puede quedarse con un import de `analytics/plugins/*.py` cacheado en
memoria"). Resuelto con el procedimiento ya conocido: borrar `analytics/plugins/__pycache__` +
reiniciar `airflow-scheduler`/`airflow-webserver`. Confirmado con una corrida real posterior y con
el panel en navegador mostrando el 78.3% correcto. **Si una sesión futura corrige código de
`analytics/plugins/` y una corrida real de Airflow no lo refleja, este es el primer sospechoso.**

### 28.2 Tres KPIs sin dato posible — eliminados de la interfaz (no dejados en "—")

"Crecimiento de demanda" (Crecimiento estratégico, 4→3 KPIs), "Avance de capacitación" (Capacidades
y Plataforma estratégico, 5→4 KPIs), y "Capacitación" (Plataforma táctico, 4→3 KPIs, más el título
del panel corregido de "Panel de Salud del Proceso de Datos y Capacitación" a "Panel de Salud del
Proceso de Datos") -- los 3 quitados por completo del frontend, confirmado en navegador que el
layout se reacomoda sin espacio vacío ni roto. Los campos de backend correspondientes
(`crecimiento_demanda_pct`, `avance_capacitacion_pct`, sus `metadata.*_disponible`) se dejaron
intactos -- no hace falta tocarlos, nada más los consume. `AUDITORIA_FUNCIONAL_ESTRATEGICO.md`,
`AUDITORIA_FUNCIONAL_TACTICO.md`, `PLAN_DE_PRUEBAS.md` e `INFORME_EJECUCION_PRUEBAS.md`
actualizados para no describir estos 3 indicadores como si siguieran en pantalla, y para reflejar
que la tasa de cancelación ya no es una limitación conocida. **Otras menciones encontradas y
NO tocadas a propósito** (son snapshots históricos por convención de este archivo, ver §1):
`AUDITORIA_ESTRATEGICO_HALLAZGOS.md`, `AUDITORIA_ESTRATEGICO_INVENTARIO.md`,
`AUDITORIA_NIVEL_ESTRATEGICO.md`, `AUDITORIA_REDISENO_V2.md`, `PROPUESTA_ESTRATEGICO_KPIS.md`, y
los `specs/*.md` originales (que describen el pedido de negocio, no el estado de la interfaz).

### 28.3 Eliminación de cuenta — auditado, sin bug real encontrado

Se auditó a fondo (código + llamada directa a la API + navegador real con la cuenta demo de
`gerencia`) por qué `gerencia` supuestamente no podía solicitar la baja de su propia cuenta.
**No se encontró ningún gate, accidental o intencional**: `POST/DELETE /perfil/baja-cuenta` no
tiene ningún `require_roles`, solo `get_current_actor` (cualquier rol autenticado); la sección
"Ajustes" del sidebar usa el sentinel `ROL_CUALQUIERA`, visible a los 13 roles. Probado en vivo con
la cuenta real de `gerencia`: "Solicitar cierre de cuenta" → confirmación con motivo → cancelado
sin confirmar (para no dejar la cuenta demo en baja). El backend también se probó directo por API
(`POST` real devolvió 200 con `dias_restantes_baja:29`, `DELETE` lo canceló) antes de la prueba en
navegador. **No se tocó código** -- no había nada que corregir. `gerencia` no tiene cuenta en
`web-pasajero`/`web-conductor` porque no es un rol de esas apps (no aplica, no es un gap).

### 28.4 Contraseñas — generación automática y restablecimiento por `admin_sistema`

`security.generar_password_segura()` (nuevo, `backend/src/core/security.py`): 14 caracteres,
alfabeto sin ambigüedad visual (sin `0/O/1/l/I`), garantiza al menos una letra y un dígito,
`secrets.SystemRandom` (mismo generador criptográfico que el resto del proyecto). Reusado en 2
lugares:

- `POST /usuarios` (`CuentaStaffCreate.password` ahora opcional) -- si se omite, se genera sola y
  se devuelve UNA vez en `UsuarioCreadoOut.password_generada` (nunca recuperable después, mismo
  patrón ya establecido por `integraciones.CredencialCreadaOut`).
- `POST /usuarios/{id}/restablecer-password` (nuevo) -- genera una contraseña nueva para una
  cuenta existente, fuerza cambio en el próximo login, auditoría write-ahead con la acción nueva
  `USUARIO_PASSWORD_RESTABLECIDA` (distinta de `PASSWORD_CAMBIO`, que es autoservicio -- mismo
  criterio ya usado para `CUENTA_BAJA_SOLICITADA` vs `USUARIO_BAJA`).

Frontend (`Usuarios.tsx`): checkbox "Generar contraseña automáticamente (recomendado)" marcado por
defecto; si se desmarca, exige contraseña + confirmación con retroalimentación de coincidencia
(`PasswordField`, ver §28.5). Tras crear/restablecer, la contraseña se muestra una sola vez en un
campo de solo lectura con el mismo aviso ya usado para el secreto de una credencial de integración.
Botón "Restablecer contraseña" nuevo en el detalle de cualquier cuenta (no solo de personal
interno). **Verificado en vivo, extremo a extremo, no solo en pantalla**: cuenta nueva creada con
contraseña autogenerada real (`VSJF8ivGm55g`) que sí sirvió para hacer login real
(`debe_cambiar_password:true`); "Restablecer contraseña" sobre esa misma cuenta generó una segunda
contraseña real (`aRU5DWba3Lgg`) que confirmó la vieja ya no sirve (401) y la nueva sí (200); evento
`USUARIO_PASSWORD_RESTABLECIDA` confirmado real en `bitacora`. 2 tests nuevos en
`backend/tests/usuarios/test_usuarios.py` (más 2 de RBAC/no-eco) cubren ambos flujos end-to-end
contra login real, no solo el código 201/200.

### 28.5 Mostrar/ocultar contraseña + coincidencia — `PasswordField`, 3 portales

`apps/shared-ui/src/components/PasswordField.tsx` (nuevo): mismo patrón visual de `TextField`, con
un botón de ícono SVG (ojo/ojo tachado, mismo estilo `stroke=currentColor` ya establecido por
`NotificacionesBell`/`AppShell`, sin emoji) que alterna `type="password"`/`"text"`. Prop opcional
`confirmarContra` -- cuando se pasa, el campo se comporta como "confirmación" de otro y muestra en
vivo "Coinciden"/"No coinciden" (color éxito/peligro) debajo, antes de permitir guardar.

Reemplazó `<TextField type="password">` en los **6 lugares reales** que existían en el código (grep
exhaustivo, no de memoria): login de las 3 apps, "contraseña actual" en `PerfilPropio.tsx`
(autoservicio, sin confirmación -- no es una contraseña nueva), y las 2 pantallas que piden una
contraseña nueva sin pedirla dos veces (registro de pasajero, postulación de conductor) -- estas 2
ganaron un segundo campo "Confirmar contraseña" que antes no existía, más el bloqueo del botón de
envío mientras no coincidan. El formulario de cambio de contraseña forzado (`web-interno/App.tsx`,
"Contraseña actual"/"Contraseña nueva") también ganó su "Confirmar contraseña nueva" con la misma
retroalimentación -- antes pedía la nueva una sola vez, sin nada que confirmar.

Verificado en vivo: toggle ojo/ojo-tachado confirmado revelando el valor real tecleado en
`web-interno` (login) y en el formulario de creación de usuario; "No coinciden"/"Coinciden" +
bloqueo/desbloqueo del botón "Crear cuenta" confirmado en `web-pasajero` (registro), con los 2
mismos checks aplicables por código a `web-conductor` (mismo componente, mismo wiring, build+lint
limpios) -- no se repitió la prueba manual ahí por acotar el alcance de esta ronda, ver §28
apertura para el criterio de verificación aplicado.

### 28.6 Finanzas — detalle de "Generar liquidaciones del periodo cerrado"

`GET /liquidaciones` ganó el filtro `periodo_inicio` (comparación exacta contra el mismo valor que
el propio endpoint de generación ya devuelve) en `backend/src/recaudacion/{router,service}.py`.
Tras generar, un botón nuevo "Ver liquidaciones de este periodo" filtra la MISMA tabla de
liquidaciones que ya existía en el workpanel (con su nota "Filtrando por el periodo… — quitar
filtro") -- sin pantalla nueva, sin llamada extra más allá del filtro. **Bug real encontrado y
corregido en el test, no en producción**: el primer intento de test armaba la URL con
`f"...?periodo_inicio={valor.isoformat()}"` interpolado a mano -- un datetime UTC-aware trae
sufijo `+00:00`, y un `+` sin codificar en un querystring se decodifica como espacio, rompiendo el
parseo. El frontend real nunca tuvo este problema (`URLSearchParams` codifica `+` correctamente);
el test se corrigió a usar `params=` de httpx. Verificado en vivo: "0 liquidación(es) emitida(s), 6
ya existían" → clic en el botón → tabla filtrada a exactamente 6 filas del período correcto → "quitar
filtro" la vuelve a la lista completa.

### 28.7 Cumplimiento — detalle de "Ejecutar control de vigencia"

Nueva sección "Documentos vencidos y por vencer" en `Cumplimiento.tsx` (operativo), reusando el
endpoint YA EXISTENTE del panel táctico (`GET /cumplimiento/panel-tactico/documentos-por-vencer`,
ya gateado a `supervisor_cumplimiento`) -- **no** la bandeja "renovaciones pendientes" que ya
estaba en esa pantalla, que es un concepto distinto (`renovacion_pendiente != null`, subidas del
conductor) sin relación con lo que el control de vigencia marca. Mismo truco de `refreshSignal` en
la key de `useSwr` que ya usaba esa bandeja, para refrescar justo después de correr el control.
Filtro cliente por Vencidos/Por vencer + texto. Verificado en vivo: "Revisados: 164 · Por vencer
notificados: 4 · Vencidos nuevos: 0" tras ejecutar el control, con la sección de abajo mostrando
"80 vencido(s), 15 por vencer" reales, y el filtro "Por vencer" acotando la tabla a exactamente 15
filas.

### 28.8 Mantenimiento — 3 ajustes

1. **Consistencia visual**: sin hallazgos de estilo suelto (grep de `<select>`/`<input>` crudos en
   `Mantenimiento.tsx`, cero resultados) -- el único problema real era de UX (ver punto 3), no
   visual.
2. **Acceso directo al mapa del taller**: `EnlaceUbicacionTaller` (nuevo, en `Mantenimiento.tsx`) --
   enlace "Ver ubicación en el mapa ↗" que aparece junto al `<Select>` de taller cuando el
   seleccionado (por NOMBRE, no id -- el catálogo de talleres es texto libre sin FK, mismo criterio
   ya establecido en Ronda 1) tiene `url_maps` real. Cableado en los 5 selectores de taller que
   existen en el archivo (nueva orden, cierre, orden encadenada, corrección, conversión de reporte
   de falla). Verificado en vivo insertando temporalmente una URL real en un taller del catálogo:
   el enlace aparece con el `href` correcto y `target="_blank"`, desaparece al elegir un taller sin
   `url_maps` -- revertido el dato de prueba al terminar.
3. **Sección "Vehículos" exigía buscar por placa primero**: confirmado que esto se refería a la
   PESTAÑA "Vehículos" del WorkPanel (`SeccionVehiculos`), no al selector dentro de "Nueva orden"
   (`VehiculoPicker`, que ya era correcto -- carga toda la flota y filtra en cliente, sin pedir
   nada de memoria). `SeccionVehiculos` se reescribió con el MISMO patrón que `VehiculoPicker`
   (`useSwr` sobre `RECURSO_VEHICULOS` sin `placa`, que el backend ya soportaba desde antes --
   "sin placa devuelve la flota activa completa" -- filtro de texto en cliente en vez de un botón
   "Buscar" obligatorio). Verificado en vivo: la pestaña muestra los 95 vehículos de la flota
   desde el primer render, sin escribir nada.

### 28.9 Historial de viajes — gap de ruta ya resuelto, un caso nuevo confirmado seguro por código

**Verificado ANTES de tocar nada, como pedía la instrucción**: los 3 casos del fix anterior (traza
real / real sin traza con ruta calculada / histórico NYC sin traza) siguen funcionando -- probado
en vivo el caso de ruta calculada (nota, `.uf-ruta-calculada` con `stroke-dasharray:"2 10"` y color
`rgb(122,106,88)`, distinto del trazo real). **El caso nuevo que pedía la instrucción (qué pasa si
la llamada de cálculo de ruta falla)** se confirmó SEGURO por lectura de código, no hacía falta
corregir nada: `estimarRuta` (`apps/shared-ui/src/api/rutas.ts`) tiene su propio `try/catch`
interno que SIEMPRE resuelve con un respaldo de línea recta si la llamada al backend falla por
cualquier motivo (red caída o error del backend) -- nunca rechaza la promesa. Como
`MapaRutaViaje.tsx` consume ese mismo helper (el mismo que ya usa el flujo de viaje activo), el
mapa del historial NUNCA queda sin ninguna línea por un fallo de red: como mínimo obtiene la línea
recta de respaldo, con el mismo estilo punteado ya distintivo. No se modificó código para este
punto -- la garantía ya existía, solo no estaba confirmada explícitamente contra este caso.

### 28.10 Permisos de `admin_captacion` — edición libre de datos del postulante, eliminada

Auditado y confirmado: existía `PATCH /captacion/solicitudes/{id}/correccion` (ronda "corrección
acotada por estado", ya cerrada en una sesión previa) que permitía a `admin_captacion` editar
libremente `cedula`/`licencia_numero`/`vehiculo` -- exactamente los datos que el propio postulante
había enviado -- mientras la solicitud no estuviera decidida. **Eliminado por completo**: endpoint,
función de servicio, schema (`CorregirSolicitudRequest`), y toda la UI de "Corregir" en
`Solicitudes.tsx` (botón, formulario, estado). Se conservan intactas las acciones propias del rol:
tomar, aprobar/observar documentación (ver evidencia real con semáforo de vigencia, ya construido
en una ronda anterior), decidir (aprobar/rechazar/observar con motivo). Test de regresión nuevo
(`test_correccion_de_solicitud_ya_no_existe`) fija el 404; los 3 tests viejos que probaban el
endpoint se eliminaron con él. Verificado en vivo: el panel de detalle de una solicitud
`ENVIADA`/`EN_VERIFICACION` ya no muestra ningún botón "Corregir"; "Tomar" sigue funcionando
(`ENVIADA` → `EN_VERIFICACION` confirmado real).

## 29. SISTEMA RIEL — rediseño de identidad, Fase 1 (fundamentos y componentes base)

Tercer rediseño visual, pero el primero **estructural**. Los dos anteriores (§16 y §27) cambiaron
paleta, tipografías, radios y tonos de sidebar sobre el mismo esqueleto, y el resultado siguió
leyéndose como plantilla de panel administrativo. Motivo real, encontrado en el propio código y no
inferido: `AppShell.tsx` líneas 8-13 declara que su estructura fue *"extraída de la referencia
visual del dueño de producto (panel admin tipo Purelcash)"*. El esqueleto ES una plantilla.

**El principio.** La identidad no se inventó: se tomó de un hecho del dominio que casi ningún otro
sistema comparte — en UrbanFleet **todo objeto del negocio es un trayecto entre paradas conocidas**
(viaje: solicitado→pagado; solicitud: enviada→aprobada; orden: abierta→cerrada; liquidación:
emitida→pagada; documento: vigente→vencido). Un panel genérico aplasta eso a una píldora de color,
que dice EN QUÉ estado está pero nunca CUÁNTO FALTA. El riel muestra ambas cosas y se convierte en
la gramática visual de todo el sistema. El germen ya existía (la franja origen-destino del panel de
solicitud del pasajero); esta fase la asciende de adorno aislado a estructura.

**Qué se conservó a propósito, y por qué** (una identidad se defiende también por lo que no cambia):
el **ámbar de marca** (viene del logotipo, es el color real del dominio) y las **dos tipografías**
(Big Shoulders Display y Barlow, ambas de señalética civil, correctas para transporte urbano y ya
integradas). Cambiarlas por tercera vez habría repetido exactamente el error de las rondas
anteriores. También intactos: `--chart-series-*` y `--status-*` (validados por la skill `dataviz`),
la escala `--z-*`, y `--font-scale` (accesibilidad).

### 29.1 Lo que se construyó

Todo con **API idéntica a la anterior**, que es lo que hace que el cambio se propague solo a las
~40 pantallas sin tocar ninguna:

| Antes | Ahora | Cambio estructural |
|---|---|---|
| — | **`Riel`** (nuevo, `Riel.tsx`/`.css`) | Componente firma. 3 variantes: `completo` (franja de plano), `etiquetado`, `mini` (dentro de una fila). Soporta paradas `adverso` (cancelado/vencido/esperando repuesto) con tono de peligro |
| `KpiCard` (caja + borde + radio + sombra) | **El instrumento** | Sin caja. Cifra apoyada en una **escala con marca de referencia** (props nuevas opcionales `escala`/`referencia`): "78,3%" deja de ser un número suelto y se lee contra su objetivo. `KpiRow` pasó de cajas con `gap` a **franja continua con divisores** |
| `Card` | **El plano** | Sin radio ni sombra; lo define una barra superior de 2px (más gruesa que toda otra línea). Props nuevas opcionales: `titulo`, `rotulo`, `acciones`, `acento`, `sinRelleno` |
| `Button` (rectángulo redondeado) | **La acción** | **Esquina cortada en diagonal** (`clip-path`), geometría de señalética vial. Foco por anillo interior, porque el `clip-path` recorta el `outline` del navegador. Indicador de carga: un nodo de riel que late, no un spinner |
| `Badge` (píldora `999px`) | **La marca** | Bloque recto con barra de color a la izquierda. Queda solo para **categorías** (tipo de orden, método de pago); el estado de un trayecto ahora va en `Riel` |
| `DataTable` | **El registro** | Cabecera sobre línea de 2px, filas con línea suave, primera columna en peso 600 (es lo que se escanea). Prop nueva `numerica` por columna: alinea a la derecha con `tabular-nums`. Toda la lógica previa intacta (truncado, previsualización, prioridad, `altoMaximo`) |
| `TextField`/`Select`/`TextArea`/`PasswordField` | **El campo** | De caja a **una línea inferior** que se enciende al enfocarse (`campos.css` compartida). El label sube a rótulo — mismo tratamiento que cabecera de registro y etiqueta de instrumento: una sola gramática para toda etiqueta de dato |

**Tokens** (`tokens.css` reescrito): neutros con **sesgo frío** (concreto/asfalto) en vez de la
paleta crema anterior — que además era justo el look más repetido de interfaz generada hoy (crema
cálido + acento terracota). Radios casi a cero (2/3/0px), `--shadow-sm: none` (la separación la
hacen líneas y espacio, no elevación), escala de espacio con más aire, `--font-size-3xl` nuevo para
la cifra del instrumento, y `.uf-rotulo` como regla única de etiqueta de dato.

### 29.2 Tema claro principal + oscuro, con la misma identidad

Requisito explícito del usuario. **El mecanismo ya existía y no se duplicó**: `theme.ts` estampa
`data-theme` de forma síncrona antes del primer render, la preferencia vive por cuenta en el
servidor (`preferencias/service.py::DEFAULTS`, default `"claro"`) y el selector ya estaba en
Ajustes. Solo se le dio la paleta nueva a los dos temas.

El oscuro **no es otra interfaz**: mismos componentes, misma distribución, mismos roles de color —
solo cambia el material (concreto claro → asfalto nocturno). El ámbar y el riel se conservan como
lo que se enciende sobre el asfalto, que es literalmente lo que hace un taxi de noche.

### 29.3 Hallazgo real de accesibilidad, corregido antes de cerrar

Contrastes calculados con fórmula WCAG real sobre cada par de uso (no a ojo). Un fallo genuino:
**el nodo actual del riel daba 2.08:1 sobre fondo claro** — el problema ya conocido del ámbar de
marca como elemento fino sobre claro, y justamente el elemento que comunica el estado en el
componente firma, sobre el tema principal.

Corregido **sin apagar el ámbar** (habría perdido la lectura de "encendido" que hace reconocible al
riel): token nuevo `--riel-actual-contorno`, que da contorno al nodo — relleno ámbar vivo, borde a
6.79:1. Es además lo que hacen los mapas de transporte reales con la estación actual. En oscuro el
ámbar ya da 8.03:1 solo, así que ahí el contorno es del mismo ámbar y la forma del nodo queda
idéntica en los dos temas. Mismo criterio aplicado al foco del campo (pasó a `--color-accent-deep`).

Dos contrastes bajos que **no son problema y se dejan a propósito**: el borde divisorio (1.4:1) es
decoración, no un elemento que haya que identificar para operar; y el tramo pendiente del riel
(1.6:1) se distingue por ser **punteado**, es decir, no depende del color en absoluto.

### 29.4 Verificación

Valores computados reales en navegador (`getComputedStyle`), no inspección visual: ground frío
`rgb(238,241,241)`; plano con radio `0px`, sombra `none`, barra superior `2px`; acción con
`clip-path: polygon(...)` real y radio `0px`; registro con cabecera sobre `2px`; campo con borde
superior `0px` e inferior `2px`; franja con 4 instrumentos, divisores de `1px`, cifra en Big
Shoulders `42px` y etiqueta en versalitas espaciadas. Riel montado y medido en **ambos temas**:
en claro contorno `rgb(138,75,10)` sobre relleno `rgb(242,164,19)`; en oscuro nodo recorrido
`rgb(179,106,10)` y tramo pendiente `dotted`. Los 3 portales confirmados con el lenguaje nuevo, sin
errores de consola.

**Persistencia del tema verificada de verdad**: cambio a oscuro desde Ajustes → recarga completa de
página → `data-theme="dark"` sigue estampado y el body sigue en asfalto.

**Artefacto menor documentado, no corregido**: al cambiar el tema **en vivo**, los `<select>` ya
montados pueden tardar en repintar el color de su borde hasta la siguiente navegación o recarga
(confirmado que la variable resuelve correcta y que ninguna regla CSS tiene el literal viejo — es
repintado de Chromium, no un bug del sistema; tras recargar, el borde da `rgb(42,53,60)` correcto).

**Regresión**: `build` ✅ en las 3 apps, `lint` limpio en `shared-ui` y 0 errores en las 3 apps (los
mismos 3 warnings preexistentes de `useEffect`), `test` **10/10** (`web-pasajero`), **6/6**
(`web-conductor`), **29/29** (`web-interno`). **Ningún test se modificó** — la API de los
componentes se conservó exactamente, que era la condición para que el rediseño se propagara solo.
Backend sin tocar.

### 29.5 Qué sigue

- ~~**Fase 2 — chasis del portal interno**~~ — **cerrada, ver §30.**
- ~~**Fase 3 — chasis de pasajero y conductor**~~ — **cerrada, ver §31.**
- ~~**Fase 4 — repaso y verificación** pantalla por pantalla en los 3 portales.~~ — **cerrada, ver §32.**

## 30. SISTEMA RIEL — Fase 2: chasis del portal interno

Aquí muere el `AppShell` heredado de la plantilla. La Fase 1 (§29) cambió el material de todos los
componentes; esta fase cambia **el esqueleto que los sostiene** en `web-interno`, que era el archivo
que literalmente declaraba en su cabecera venir de una referencia de panel administrativo.

Sin mover un solo flujo: ninguna sección cambió de sitio, ningún rol ganó ni perdió acceso, ningún
endpoint se tocó. **Backend sin modificar en toda la fase.**

### 30.1 El andén — la navegación deja de ser una lista de links

`AppShell.tsx`/`AppShell.css` reescritos. La barra lateral pasó de "bloque de color oscuro con
links" a **una línea vertical continua con nodos de parada**, la misma gramática del riel de estado:

- La línea es del **tramo** (el grupo), no un borde por ítem: se lee como UNA línea que atraviesa el
  andén y **se corta entre tramos**, igual que un mapa de línea de transporte.
- La **parada actual** es un nodo encendido con contorno y halo — exactamente el mismo gesto que el
  nodo actual del `Riel`. Es la pieza que hace que el sistema se lea como un solo idioma y no como
  dos invenciones separadas.
- **El bloque de color oscuro desapareció.** El andén vive sobre el mismo suelo que el contenido,
  separado por una línea. El sidebar dejó de ser un panel pegado al lado para ser parte del plano.
- La **jerarquía de 3 niveles** (operativo → táctico → estratégico) pasó del cuadrito suelto al lado
  del texto (§20) al **grosor y color de la línea del tramo** (`.anden-tramo--nivel`). La jerarquía
  se expresa en el riel mismo, que es de lo que trata todo el sistema.

Conservado tal cual, sin reconstruir: favoritos con estrella, badges de contador, separación de la
zona personal (`GRUPOS_PERSONALES`), cerrar sesión, `headerActions`, aviso de baja de cuenta, y el
comportamiento de cajón en móvil con el `@media (min-width: 900px)` que lo fija en escritorio.

### 30.2 El localizador — el encabezado deja de repetir el título

El encabezado mostraba el nombre de la sección, que ya estaba en el sidebar y otra vez en la propia
pantalla: el mismo dato tres veces. Ahora es un **localizador**: `tramo → parada`, unidos por un
fragmento de riel. Dice algo que antes no decía en ningún lado — **en qué parte del sistema estás**,
no solo cómo se llama la pantalla. En anchos angostos se cae el nombre del tramo y queda la parada,
que es el dato que importa cuando sobra poco espacio.

### 30.3 `trayectos.ts` — un solo lugar donde vive el mapa del dominio

`apps/shared-ui/src/trayectos.ts` (nuevo, exportado desde `index.ts`). Declara, para cada objeto del
negocio, cuáles son sus paradas y en cuál cae cada estado del backend: `trayectoSolicitud`,
`trayectoOrden`, `trayectoLiquidacion`, `trayectoViaje`. Sin esto cada pantalla inventaría su propio
mapeo y el riel dejaría de significar lo mismo en dos lugares distintos.

Dos reglas que sostienen la coherencia, documentadas en el propio archivo:

1. **El nombre de la parada es el que lee una persona**, nunca el enum crudo. `EN_VERIFICACION` se
   muestra "En verificación". Es el único lugar del sistema donde se traduce — antes cada tabla
   mostraba el enum tal cual o lo traducía por su cuenta.
2. **Los desvíos no inventan una parada nueva.** Una solicitud `OBSERVADA` sigue en la parada de
   verificación, marcada como adversa; `ESPERANDO_REPUESTO` es la parada de taller detenida. Así el
   trayecto conserva su longitud y **dos filas de la misma tabla se pueden comparar de un vistazo**,
   que es justo lo que una píldora de color no permite.

Detalle de API que importa: el campo del índice se llama `actual` y no `indice`, para que un trayecto
se pase entero al riel con `<Riel {...trayectoOrden(estado)} />` sin que cada pantalla mapee campos
a mano. (El primer intento lo llamó `indice` y reventó con TS2741 en 6 sitios — el nombre es parte
del contrato, no cosmética.)

### 30.4 Riel aplicado a las 3 pantallas de trayecto

`Solicitudes.tsx`, `Mantenimiento.tsx` y `Finanzas.tsx`: la columna de estado pasó de `<Badge>` a
`<Riel {...trayectoX(estado)} variante="etiquetado" />`, y el panel de detalle al riel completo. Se
eliminaron los mapas `tonoPorEstado` de las tres (quedaron sin uso), con un comentario que explica
por qué ya no hacen falta. De paso, la columna "Neto (en mano)" de Finanzas recibió `numerica: true`
(prop nueva de la Fase 1).

Las tres pantallas ganaron información que antes no daban: no solo el estado, también cuánto falta
para el final del trayecto.

### 30.5 Verificación real

Todo con valores computados en navegador contra el stack real, no inspección visual.

**Chasis (tema claro)**: fondo del andén `rgb(231,236,236)`, línea de tramo `2px`, nodo de parada
actual `rgb(242,164,19)` con contorno `rgb(138,75,10)` y halo, línea de tramo de nivel
`rgb(138,75,10)` al 0.55 de opacidad, localizador leyendo "Operación → Solicitudes" y "Panel
Táctico → Despacho", franja con 4 instrumentos.

**Riel con datos reales, los 3 dominios y sus casos adversos**:

| Pantalla | Estados confirmados en pantalla |
|---|---|
| Solicitudes | Enviada 0/3, En verificación 1/3, Aprobada 2/3 — enums crudos ya no aparecen |
| Mantenimiento | Abierta, En taller, Cerrada en ámbar; **Esperando repuesto** y **Anulada** en `rgb(178,58,31)` con nodo adverso |
| Finanzas | Emitida, Aprobada, Pagada; **Observada** adversa. Columna "Neto (en mano)" con `text-align:right` y `font-variant-numeric: tabular-nums` reales |

**Tema oscuro** (recargando con la preferencia persistida, no cambiándola en vivo — ver la nota de
abajo): nodo de parada actual `rgb(242,164,19)` con contorno y halo ámbar, nodo pendiente
`rgb(20,28,33)` con anillo interior, lateral `rgb(20,28,33)`, plano `rgb(23,31,36)` con radio `0px`
y sombra `none`, acción ámbar con texto `rgb(26,18,7)` y el `clip-path` diagonal real, campo
encendiendo a `rgb(246,198,103)` (`--color-accent-deep`) al enfocar y volviendo a `rgb(42,53,60)` en
reposo. **Misma identidad, mismos componentes, misma distribución** — solo cambia el material.

**Dos artefactos del entorno de verificación, no fallos del sistema** (documentados para que una
sesión futura no los persiga como bugs):

- **Cambiar `data-theme` en vivo por JS deja pseudo-elementos con los colores del tema anterior.**
  Medido: el nodo del andén resolvía `--riel-actual: #f2a413` correcto en el elemento, pero su
  `::before` computaba los tres colores del set claro. Tras recargar con el tema persistido, los
  valores son los correctos. Es el mismo repintado de Chromium ya documentado en §29.4 para los
  `<select>`. **Verificar tema recargando, no alternando en vivo.**
- **`:focus` no coincide si el panel del navegador no tiene foco del sistema operativo**
  (`document.hasFocus() === false`), y **las transiciones CSS no avanzan sin frames compuestos**, así
  que `getComputedStyle` devuelve el valor inicial congelado. Para medir el estado final de foco hizo
  falta un clic real por `ref` (dio foco al documento) **más** anular la transición en la página. El
  CSS nunca estuvo mal.

**Limitación dicha en vez de simulada**: el panel del navegador no compone frames en esta sesión, así
que **no hay capturas de pantalla** — la verificación es sobre DOM y valores computados reales, con
interacciones reales disparadas en la página.

**Regresión**: `build` ✅ en las 3 apps; `lint` limpio en `shared-ui`, `web-pasajero` y
`web-conductor`, y 0 errores en `web-interno` (los mismos 3 warnings preexistentes de `useEffect`);
`test` **10/10** (`web-pasajero`), **6/6** (`web-conductor`), **29/29** (`web-interno`). **Ningún
test se modificó** — el chasis cambió sin alterar el contrato observable de ninguna pantalla.
Backend sin tocar, así que no se re-corrió `pytest` (última corrida registrada: 480 passed, §28).

## 31. SISTEMA RIEL — Fase 3: chasis de calle (pasajero y conductor)

Esta es la fase que responde al reclamo original de "portales iguales entre sí". Los 3 portales
venían usando el MISMO esqueleto de escritorio (barra lateral + encabezado), y por eso se leían
como una aplicación repetida tres veces. Pero un pasajero pidiendo un taxi en la vereda y un
supervisor revisando 1,3 millones de viajes en un monitor no hacen el mismo trabajo: uno usa un
pulgar y una pantalla de 375 px con sol encima, el otro mouse y teclado.

**Backend sin tocar.** Ningún endpoint, ningún flujo, ninguna sección movida de sitio.

### 31.1 `CalleShell` — el chasis nuevo

`apps/shared-ui/src/components/CalleShell.tsx`/`.css` (nuevos, exportados desde `index.ts`).
`AppShell` queda intacto y sigue siendo el chasis de `web-interno`; los dos conviven.

Qué comparte con el andén, a propósito: **la línea con paradas**. Acá se acuesta y baja al alcance
del pulgar, con la parada actual encendida con contorno y halo — el mismo nodo del `Riel` de estado
y del andén. El idioma visual es uno solo; lo que cambia es el vehículo.

Qué cambia, y por qué:

- **No hay barra lateral.** En 375 px, una barra lateral o roba un tercio de la pantalla o se
  esconde tras un botón de menú (dos toques para llegar a cualquier lado). El riel inferior deja
  todo a un toque, con objetivos grandes, donde el pulgar llega sin reacomodar la mano.
- **La separación "funcional vs. personal" pasa a ser estructural.** En el andén son dos tramos
  separados por una línea; acá lo operativo vive en el riel y el resto detrás de una sola parada
  que abre una hoja. Misma decisión de siempre, dicha con el chasis en vez de con un divisor.
- **El encabezado se reduce a 52 px**: marca, parada actual y acciones. El nombre de la cuenta y
  el cierre de sesión bajan a la hoja, donde no compiten con el mapa por alto.
- **La hoja nace anclada abajo**, donde el pulgar la abrió, y conserva los tramos con su nombre —
  es la continuación de la misma línea, no otra clase de menú. Cierra con Escape, con el fondo o
  con la ✕.

**Reparto de paradas** (prop `principales`, explícita y no derivada del grupo: cuál es la parada
principal es decisión de cada portal):

| Portal | Riel inferior | Detrás de la hoja |
|---|---|---|
| `web-pasajero` | Viaje · Mis viajes · **Cuenta** | Mi perfil, Notificaciones, Ajustes, Ayuda |
| `web-conductor` | Mi turno · Mis viajes · Mis liquidaciones · **Más** | Fallas del vehículo y Mis documentos (tramo "Operación") + los 4 de "Mi cuenta" |

Fallas y Documentos son de "estar habilitado para trabajar", no de la jornada en curso, así que
quedan en la hoja con su tramo intacto. Un riel de 6 nodos en 375 px dejaría objetivos de 60 px con
etiquetas cortadas — deja de ser un riel de calle.

**Detalle que importa**: si una sección con contador queda en la hoja, su señal sube a la parada que
la contiene (`badgeResto`). Verificado en vivo: la parada "Cuenta" del pasajero muestra `9+` y la
de "Más" del conductor `5`, los mismos no leídos que la campana.

### 31.2 Dos bugs reales encontrados y corregidos por medición, no por revisión visual

- **El nodo actual crecía y se desalineaba de su propia línea.** La primera versión hacía el nodo
  activo de 9 a 13 px; medido, su centro caía en 22 px contra los 20 px de la línea que debe
  atravesarlo. El andén nunca tuvo el problema porque ahí el nodo **no cambia de tamaño, se
  enciende**. Se igualó el gesto: mismo tamaño siempre, el halo da la jerarquía. Los 3 nodos
  quedaron medidos en el mismo centro.
- **El mapa colapsaba a 0 px de alto.** `RideMap`/`DriverMap` con `llenarAltura` usaban
  `height: 100%`, y su contenedor es un flex item con `flex: 1`: su alto resuelto **no cuenta como
  definido** para resolver un porcentaje. Medido sin ambigüedad: con alto fijo el envoltorio daba
  703 px, con `100%` daba 0. Corregido con `position: absolute; inset: 0` sobre el contenedor
  `position: relative` que ambas pantallas **ya declaraban para esto** — el comentario del propio
  contenedor en `App.tsx` anticipaba textualmente "su único contenido es absolutamente
  posicionado". No depende de resolución de porcentajes. Los usos con altura fija (historial, vista
  pública compartida) quedaron sin cambios.

### 31.3 Verificación real

Con valores computados contra el stack real, a 375x812 primero y escritorio después.

**Chasis (móvil, los 2 portales)**: sin barra lateral en ninguno; encabezado 52 px; riel `sticky`
terminando exactamente en el borde inferior del viewport (812). Objetivos táctiles: pasajero 125x56
px, conductor 94x54 px — los dos sobre el mínimo de 48 px. Ninguna etiqueta cortada, incluida "Mis
liquidaciones" (82 px reales dentro de una parada de 94 px). Sin scroll horizontal.

**El mapa como fondo**: 703 px de alto en los dos portales = **87% de la pantalla**, del borde del
encabezado (52) al riel (755). Capas comprobadas con `elementsFromPoint` real, no por lectura de
CSS: mapa z=0 → tarjeta flotante z=10 → riel z=20; el riel gana la pila en sus propias coordenadas,
el mapa nunca lo tapa.

**La hoja**: `role="dialog"`, `aria-modal`, anclada al ras (abajo = 812) con "Cerrar sesión"
visible; en conductor conserva los 2 tramos con su nombre ("Operación" con 2 paradas, "Mi cuenta"
con 4). Navegar desde la hoja cierra la hoja, cambia el título del encabezado y mueve
`aria-current="page"` a la parada que la contiene. Escape la cierra y retira el fondo.

**Escritorio (1280x800)**: el riel no se estira a todo el monitor — se centra en 760 px (padding
260 px por lado), con el encabezado y el contenido alineados al mismo ancho, el riel sigue fijo
abajo y sin scroll horizontal.

**Tema oscuro**: mismos componentes y distribución, solo cambia el material. Nodo actual ámbar con
contorno y halo, nodo pendiente sobre superficie con anillo interior, línea `rgb(51,65,74)`.

**Contraste calculado con fórmula WCAG sobre los pares de uso reales**: etiqueta de parada actual
17.63:1 (claro) / 14.11:1 (oscuro); pendiente 5.52:1 / 6.56:1 — las cuatro sobre 4.5:1. El nodo
encendido reconfirma el hallazgo de §29.3: el relleno ámbar solo da **2.08:1**, por debajo del
mínimo de 3:1 de WCAG 1.4.11 para un elemento no textual que comunica estado; el **contorno da
6.79:1**, que es exactamente para lo que existe `--riel-actual-contorno`.

**Nota de tamaño**: la etiqueta del riel usa `--font-size-xs` a propósito. Es el tamaño que permite
que la etiqueta más larga entre sin cortarse en una parada de 94 px; subirla al siguiente escalón
la truncaría. Quien necesite más tamaño lo tiene en el ajuste de tamaño de texto, que escala este
token como cualquier otro.

**4 tests actualizados, y por qué** (a diferencia de las Fases 1 y 2, donde no se tocó ninguno):
`Mi perfil` y `Ajustes` ya no están en una barra lateral siempre visible, viven detrás de la parada
"Cuenta"/"Más". Los 4 sitios ganaron un clic previo que abre la hoja — es el recorrido real del
usuario, no un parche para que el test pase. Ninguna aserción de comportamiento cambió.

**Condiciones del entorno, dichas en vez de simuladas**: (1) la geolocalización está bloqueada en
el navegador automatizado, así que se simuló `navigator.geolocation` para poder ver el mapa real —
misma técnica ya usada en rondas anteriores; (2) el vehículo del conductor demo habitual sigue
retirado por mantenimiento (estado preexistente del entorno, §22), así que el turno se probó con
`Matthew Moore` (`+593980012`, placa `FIC-0012`), elegido consultando en Mongo qué socio no tenía
orden abierta — el turno se terminó al finalizar la prueba, no quedó nadie en línea; (3) el panel
del navegador no compone frames, así que **no hay capturas** y hubo que anular transiciones y
animaciones **en la página** para medir estados finales (el nodo activo se leía blanco y la hoja
42 px por debajo del viewport: los dos eran la animación congelada en su fotograma inicial, no
fallos — confirmado midiendo con la animación anulada).

**Regresión**: `build` ✅ en las 3 apps; `lint` limpio en `shared-ui`, `web-pasajero` y
`web-conductor`, y 0 errores en `web-interno` (los mismos 3 warnings preexistentes de `useEffect`);
`test` **10/10** (`web-pasajero`), **6/6** (`web-conductor`), **29/29** (`web-interno`). El único
error de consola observado fue un 500 de HMR a mitad de la edición, con 200 en todas las peticiones
posteriores (confirmado en el log de red real). Backend sin tocar: última corrida de `pytest`
registrada sigue siendo 480 passed (§28).

## 32. SISTEMA RIEL — Fase 4: repaso y verificación (cierre del rediseño)

Última fase del rediseño de identidad. No construye nada nuevo — repasa lo que las Fases 1-3
dejaron, con dos objetivos: encontrar cabos sueltos que la verificación de cada fase individual no
podía ver (porque miraba su propio componente, no la consistencia entre pantallas) y confirmar que
el conjunto completo convive sin regresión. **Backend sin tocar en toda la fase.**

### 32.1 Hallazgo real — `trayectoViaje` existía desde la Fase 2 y nunca se había cableado

Barrido de los ~30 usos de `<Badge>` que quedaban en `web-interno` fuera de las 3 pantallas ya
migradas (Solicitudes/Mantenimiento/Finanzas). La mayoría son categorías legítimas que el propio
diseño reserva para `Badge` (tipo de orden, método de pago, resultado de auditoría, estado de
turno de un vehículo en el tablero en vivo de Flota, estado de cuenta en Usuarios) — ninguno de
esos es un trayecto de los 4 que `trayectos.ts` declara, y no se tocaron.

Uno sí lo era: **`HistorialGlobal.tsx`** (el historial de viajes de toda la cooperativa) seguía
mostrando el estado del viaje como píldora de color con su propio `tonoPorEstado`, el mismo enum
crudo que las otras 3 pantallas ya habían dejado atrás en la Fase 2 — pese a que `trayectoViaje` ya
existía en `trayectos.ts` desde esa misma fase. Nadie lo había conectado porque esta pantalla no
formó parte del lote original de migración (era de la ronda de UX complementaria, §10, anterior al
Sistema Riel). Corregido: `<Riel {...trayectoViaje(v.estado)} variante="etiquetado" />` en la
tabla, `<Riel {...trayectoViaje(seleccionado.estado)} />` en el detalle — mismo patrón exacto que
las otras 3, `tonoPorEstado` eliminado con el mismo comentario explicativo que ya llevaban las
demás. Verificado con datos reales (1,334,917+ viajes): tabla mostrando "Pagado"/"Cancelado"/"Sin
conductor" (los 2 últimos marcados adversos), detalle de un viaje real mostrando "Pagado" en la
variante completa del riel.

### 32.2 Foco de teclado real, confirmado con una tecla física — no solo leído en CSS

Con un clic real (no `.focus()` programático) para dar foco genuino al documento y luego una
pulsación real de `Tab`: el ítem del andén enfocado por teclado resuelve `:focus-visible` a
verdadero, con anillo `rgb(179,106,10)` — la regla global de foco compartida por todo el sistema
funciona en el chasis nuevo, no solo en los controles que ya se habían probado en rondas
anteriores. La verificación equivalente en `CalleShell` no pudo repetirse con una pulsación física
en esta sesión (el panel del navegador dejó de estar visible/componiendo frames a mitad de la
fase, ver 32.4) — queda confirmada por lectura de código en su lugar: `CalleShell.css` no declara
ninguna regla de foco propia, así que hereda exactamente la misma regla global ya probada en el
andén.

### 32.3 Anchos intermedios (tablet, 700-768px) — sin cortes ni scroll horizontal

Verificado en los 3 portales a 768px (preset tablet) y en los 2 portales de calle además a 700px
(justo bajo el punto de quiebre de 760px que centra el riel en escritorio): ninguna etiqueta del
riel se corta (`scrollWidth <= clientWidth` en las 4 de conductor, incluida "Mis liquidaciones"),
sin scroll horizontal en ningún caso, el andén de `web-interno` sigue mostrando su cajón móvil
correctamente hasta el punto de quiebre de 900px ya documentado en la Fase 2.

### 32.4 Confirmado: ningún flujo se movió de sitio

La trampa ya conocida de este proyecto (agregar una sección nueva y sin querer desplazar la
sección por defecto de algún rol, ver §10/§13.2) se revisó explícitamente tras las 3 fases: sesión
limpia + login real de `staff-verificacion` sigue abriendo en **Solicitudes**; sesión limpia +
login real de `gerencia` sigue abriendo en **Indicadores**; `web-pasajero` sigue en **Viaje**;
`web-conductor` sigue en **Mi turno**. Los 4 sin cambios respecto a lo documentado en fases
anteriores.

### 32.5 Dos falsas alarmas descartadas con investigación, no con suposición

- **El cajón móvil del andén pareció no abrir/cerrarse de forma consistente** en una primera
  pasada de pruebas encadenadas rápido. Investigado antes de asumir un bug: leer el estado del DOM
  en el MISMO script justo después de llamar `.click()` captura el valor **previo** al re-render de
  React (los `setState` dentro de un handler de evento se aplican en el siguiente ciclo, no de
  forma síncrona) — confirmado abriendo con un clic, leyendo en una llamada de script SEPARADA
  (donde el re-render ya se aplicó), y repitiendo la misma secuencia con el fondo (`backdrop`) y con
  un ítem de navegación real: los 3 mecanismos de cierre (fondo, ítem de navegación, y el propio
  botón como toggle) funcionan exactamente como se documentó en la Fase 2. No hubo que tocar código.
- **Un `requestAnimationFrame` colgó una llamada de script 30s.** Confirmado que es el mismo límite
  ya documentado en Fases 1-3: sin frames compuestos, ningún callback de `rAF` llega a ejecutarse
  nunca. No es específico de esta fase ni de `CalleShell`/`AppShell` — es una propiedad del entorno
  de verificación. Sustituido por `setTimeout` simple para cualquier medición con espera, que sí
  dispara con normalidad.

### 32.6 Regresión final del bloque completo (Fases 1-4)

`npm run lint` limpio en `shared-ui`. Las 3 apps: `build` ✅, `lint` con 0 errores (los mismos 3
warnings preexistentes de `useEffect` en `web-interno`, ninguno nuevo), `test` **10/10**
(`web-pasajero`), **6/6** (`web-conductor`), **29/29** (`web-interno`) — sin tocar un solo test en
esta fase. Sin errores de consola nuevos en ningún portal (los únicos vistos fueron
`ERR_CONNECTION_TIMED_OUT` transitorios durante el arranque de Docker al inicio de la sesión,
confirmado con el log de red que las peticiones posteriores volvieron todas a 200). Backend sin
tocar en las 4 fases completas del Sistema Riel — última corrida de `pytest` sigue siendo 480
passed (§28).

**Con el cierre de la Fase 4, el Sistema Riel (rediseño de identidad completo, iniciado a pedido
del docente que amenazó con nota 0 por interfaces "feísimas e iguales entre sí") queda cerrado de
punta a punta**: fundamentos y componentes base (§29), chasis del portal interno (§30), chasis de
los 2 portales de calle (§31), y este repaso final (§32). Los 3 portales comparten ahora una sola
identidad (el riel de trayecto, ámbar de marca, Big Shoulders Display + Barlow) expresada en 2
chasis genuinamente distintos según el dispositivo real que cada uno usa — ya no la misma
plantilla de panel administrativo repetida 3 veces.

## 33. Comisión de la cooperativa (CU-O10) — consolidación de duplicados, salvaguarda de índice y pantalla nueva

Pedido explícito del usuario tras una investigación previa sobre dónde vive el 20% de comisión:
2 problemas reales encontrados en esa investigación (2 documentos "vigentes para siempre" en
Mongo, y el endpoint de escritura sin ninguna pantalla) se cierran acá, en el mismo orden.

### 33.1 Consolidación de los 2 documentos duplicados de comisión

Confirmado ANTES de tocar nada (paso explícitamente pedido): los 2 documentos manuales
(`comision-v1`, `com-browser-01`) coincidían exactamente en `porcentaje: 0.2` y `vigente_desde:
2020-01-01` — sin divergencia, seguro consolidar. `tarifa` se revisó con el mismo criterio y
**no tenía la misma anomalía**: hay 2 documentos, pero son series distintas por diseño
(`filtro_serie={"franja": franja}`, DIURNA/NOCTURNA), exactamente 1 vigente por franja — no se
tocó.

Consolidado real, no simulado: `POST /parametros/comisiones` (porcentaje=0.2, vigente_desde
preservada en 2020-01-01 para no dejar sin cobertura ningún viaje ya finalizado y aún sin pagar)
generó un id real vía `uuid4()` (`b93a36e8-...`) y, como efecto correcto de `_crear_version`,
cerró los 2 documentos manuales (`vigente_hasta` = `vigente_desde`, ventana de ancho cero,
inertes) — después se eliminaron con `db.parametros.deleteMany({_id:{$in:[...]}})`. Verificado:
queda exactamente 1 documento con `vigente_hasta:null` para `tipo=comision`.

Corrección registrada en la bitácora: `backend/scripts/consolidar_parametro_comision.py` (nuevo,
idempotente) escribe un evento `PARAMETRO_CAMBIO` explícito con `datos_previos` (los 2 documentos
eliminados, completos) y `datos_posteriores.motivo="consolidacion_duplicados_comision"` — aparte
del evento de rutina que la propia llamada a `crear_parametro_comision` ya escribe, que no explica
que fue una consolidación. Confirmado en `bitacora` (evento real, `entidad_id` apuntando al
documento consolidado).

### 33.2 Salvaguarda a nivel de base de datos

Nuevo índice único parcial en `core/db_mongo.py::ensure_indexes()`:

```python
await db.parametros.create_index(
    [("tipo", 1), ("franja", 1)],
    unique=True,
    partialFilterExpression={"vigente_hasta": None},
    name="parametros_vigente_unico",
)
```

`franja` está ausente en los documentos `tipo=comision` (esa serie no se particiona) — Mongo
indexa un campo ausente como `null`, así que los documentos de comisión colisionan entre sí en la
misma entrada de índice (1 serie global, exactamente lo que se quiere); los de `tipo=tarifa` sí
traen `franja`, así que DIURNA/NOCTURNA siguen siendo series independientes. Ya no depende de que
`crear_parametro_comision` cierre bien la versión anterior en código de aplicación: una inserción
manual futura que reproduzca el bug original falla sola contra la base de datos.

**Verificado con una prueba real de la propia salvaguarda**, no solo leído: un
`db.parametros.insertOne(...)` manual reproduciendo exactamente el patrón del bug original
(`tipo:"comision"`, `vigente_hasta:null`, un segundo documento) fue rechazado por Mongo con
`E11000 duplicate key error ... dup key: { tipo: "comision", franja: null }`, sin tocar la
colección. Repetido para `tipo:"tarifa", franja:"DIURNA"` — mismo rechazo correcto, confirmando
que las series de tarifa siguen aisladas entre sí.

### 33.3 Pantalla nueva — "Comisión de la cooperativa"

**No entra en "Parámetros Globales"** (Módulo 2 de admin_sistema, `/configuracion/
parametros-sistema` — un dominio de configuración de sistema completamente distinto: radios de
despacho, idioma, zona horaria) **ni en "Administración"** (grupo de `admin_sistema`, que a
propósito NO puede tocar "reglas de dinero" per el comentario ya existente en
`parametros/router.py`). Sección nueva y propia,
[apps/web-interno/src/sections/Comision.tsx](apps/web-interno/src/sections/Comision.tsx), gateada
en el sidebar EXACTAMENTE a los mismos 2 roles que el propio endpoint
(`admin_plataforma`/`gerencia`) — ni más ni menos. Insertada después de todos los grupos con roles
únicos (mismo criterio ya establecido para "Historial de viajes"), para no desplazar la sección
por defecto de `admin_plataforma` (hoy "Flota") ni de `gerencia` (hoy "Indicadores").

No es un WorkPanel de búsqueda/edición — los parámetros de este tipo son registros versionados e
inmutables (nunca se edita ni se borra una versión, solo se crea una nueva). Patrón: "vigente
actual" + "crear nueva versión" + "historial", 3 `Card` apiladas. Reusa `POST /parametros/
comisiones` tal cual (nada nuevo ahí); sí se agregó `GET /parametros/historial?tipo=comision`
(nuevo, gateado igual a los 2 roles de escritura — revela cómo cambió un parámetro de dinero en el
tiempo, mismo criterio de sensibilidad que la escritura) porque no existía ningún endpoint de
listado, solo el de "vigente actual".

**Bug real encontrado y corregido al construir la pantalla** (preexistente, nunca detectado porque
ningún frontend mostraba `vigente_desde`/`vigente_hasta` hasta ahora): `parametros/router.py::
_to_out` serializaba el datetime tal cual venía de Mongo — naive (BSON no guarda tzinfo) — y
Pydantic serializa un datetime naive SIN sufijo de zona (`"2026-09-01T05:00:00"`, sin `Z`). El
navegador interpreta esa cadena como hora LOCAL, no UTC, así que una comisión con vigencia real a
las 05:00 UTC se mostraba en el historial como "5:00 a.m." en vez de las 00:00 locales correctas
(confirmado con `Intl.DateTimeFormat().resolvedOptions().timeZone` real del navegador:
`America/Guayaquil`, UTC-5). Corregido con el mismo helper `como_utc()` ya establecido en el resto
del proyecto para este gotcha exacto — `_to_out` ahora reetiqueta ambos campos antes de
serializar. Verificado con los 3 valores reales del historial mostrando la hora local correcta
tras el fix (antes/después comparado explícitamente).

**Verificación real en navegador** (cuenta `gerencia`): pantalla cargó con "25.00% · Vigente
desde 14 ago 2026, 7:00 p.m." (=15 ago 00:00 UTC en hora local, correcto) y el historial con las 2
versiones (25%/20%) ordenadas más reciente primero. Formulario real usado para crear una tercera
versión (22%, vigente 1 sept 2026 — a propósito en el futuro, para no alterar ningún dato
histórico con la prueba de la propia pantalla): `POST /parametros/comisiones` real → 201 → mensaje
de éxito con el porcentaje y fecha correctos → "Comisión vigente" siguió mostrando 25% (correcto,
1 sept aún no llega) → historial pasó a 3 filas. Confirmado en el log de red que crear una versión
dispara el refetch de ambos recursos (`invalidateSwrPrefix` de `/parametros/vigente` y
`/parametros/historial`) sin recargar la página.

### 33.4 Verificación de extremo a extremo del efecto real de un cambio de comisión

Se necesitaban viajes reales, ya `FINALIZADO`, sin pagar, a ambos lados de una fecha de vigencia
real para probar "sin alterar viajes ya cerrados antes de esa fecha" con datos genuinos en vez de
razonamiento. Se encontraron 5 (leftover de sesiones anteriores, sin pago registrado): 3 de Juan
Pérez (`ts_fin` 2026-07-30/08-07/08-14) y 2 de Christopher Anderson (`ts_fin` 2026-08-17). Se creó
una versión real de comisión al 25% con `vigente_desde=2026-08-15` (entre los 2 grupos) y se
registraron los 5 pagos reales vía `POST /pagos/efectivo` (login real de cada conductor).

**Resultado real en `movimientos`** (confirmado por consulta directa, no calculado a mano): los 3
viajes de Juan (antes del 15 de agosto) quedaron con comisión al **20%** exacto; los 2 de
Christopher (después) quedaron al **25%** exacto (`0.375` redondeado a `0.38`, redondeo bancario
ya documentado). Prueba directa e inequívoca de que el cambio de comisión aplica por la fecha del
viaje, no por cuándo se paga, y que los viajes previos no se recalculan.

**Un hallazgo real cambió el plan de verificación a mitad de camino**: `rpt_margen_comision` (la
tabla detrás del KPI) se alimenta de `fact_liquidacion`, que a su vez sale ÚNICAMENTE de la
colección `liquidaciones` (CU-O11) — nunca de `pagos`/`movimientos` directo. Los 5 pagos de arriba
no alcanzan solos para mover el KPI; hace falta que `generar_liquidaciones` (CU-O11) los agrupe en
una liquidación real primero. Como esa función siempre opera sobre "la semana YA CERRADA respecto
a ahora" (sin parámetro de periodo, ver §8.8), y los movimientos nacieron hoy dentro de la semana
en curso, se usó el mismo mecanismo ya establecido en `seed_liquidaciones_demo.py`
(`reloj_congelado`, congelar `datetime.now(UTC)` solo en `recaudacion.service`/`core.audit`) para
que el servicio viera un "ahora" el sábado siguiente al cierre real de esa semana — sin fabricar
ningún dato, solo permitiendo que el botón real de "Generar liquidaciones" viera la semana como
cerrada. Resultado real: 6 liquidaciones reales `EMITIDAS`, con el detalle por viaje mostrando
exactamente los mismos montos de comisión ya verificados en `movimientos` (0.20/0.25 según
corresponda), agregados correctamente por socio.

**El último salto (ClickHouse → KPI) no se pudo completar en esta sesión — dicho explícitamente,
no simulado.** Encontrado el mismo límite de memoria de ClickHouse ya documentado en §8.6b (~1.37GB
de techo, "MEMORY_LIMIT_EXCEEDED" real), esta vez disparado por `dag_finanzas_gold` en vez de
`dag_viajes_core` — mismo síntoma, mismo diagnóstico ya cerrado en esa sección (el consumo grande
es de índices/metadata en memoria de las tablas MergeTree grandes del servidor completo, no de las
tablas pequeñas que este DAG toca). Se intentó además correr el DAG por 2 vías (`airflow dags
backfill`, que chocó otra vez con el deadlock ya documentado en §8.8 contra
`disparar_publicacion_indicadores`; y una ejecución directa de las funciones reales del DAG en un
solo proceso Python, sin pasar por el scheduler de Airflow, que sí evitó el deadlock pero llegó
igual al mismo techo de memoria de ClickHouse en el paso de deduplicación). **Decisión: no forzar
más** — coherente con la decisión ya tomada en §8.6b de no seguir escalando la memoria de
ClickHouse sin medir antes, y no es un defecto de esta funcionalidad: el mecanismo completo,
backend hasta `fact_liquidacion`, quedó probado con datos 100% reales; solo el refresco de
`rpt_margen_comision` específicamente para este lote quedó pendiente de una corrida de Airflow que
sí complete, en una sesión donde ese techo de memoria ya documentado se resuelva aparte.
**Resuelto de raíz en la sesión siguiente, ver §34** — la causa real no era ninguna de las
hipótesis de §8.6b.

**Error propio cometido y corregido durante la investigación de Airflow, dicho explícitamente**:
al intentar liberar un DagRun de `dag_finanzas_gold` atascado (bloqueando `max_active_runs`), un
filtro `run_id.like('backfill%')` demasiado amplio marcó como `FAILED` ~35 corridas históricas
legítimas (`success`) del backfill NYC de 2021 sin relación con el problema. Detectado de
inmediato al revisar el resultado del propio comando, corregido en el mismo turno restaurando las
35 a `SUCCESS` (su estado real) y dejando `FAILED` solo la corrida realmente problemática. No hubo
pérdida de datos (`DagRun.state` es metadata de Airflow, no toca Mongo/ClickHouse), pero se deja
documentado como recordatorio: cualquier filtro sobre `run_id`/`execution_date` al hacer cirugía
directa sobre la base de metadata de Airflow debe acotarse por id exacto o rango de fecha
explícito, nunca un `LIKE` amplio.

**Regresión final**: backend `pytest` **482 passed** (subió de 480 por los 2 tests nuevos de
`/parametros/historial`, RBAC + orden), misma 1 falla preexistente sin relación (Google Maps).
`ruff check` limpio. Frontend `build`/`lint`/`test` limpios en `web-interno` (29/29, mismos 3
warnings preexistentes de `useEffect`) — `shared-ui`/`web-pasajero`/`web-conductor` no se tocaron
en este bloque.

## 34. Techo de memoria de ClickHouse — resuelto de raíz (las 2 hipótesis de §8.6b eran incorrectas)

Pedido explícito del usuario tras el cierre parcial de §33: auditar la causa exacta del
`MEMORY_LIMIT_EXCEEDED` que venía bloqueando `rpt_margen_comision` (y, antes, `dag_viajes_core`,
§8.6b) **con evidencia real, no con el mensaje de error solo**, antes de decidir cualquier ajuste.
La auditoría descartó las 2 hipótesis que §8.6b había dejado como "las más probables" y encontró
una causa completamente distinta — y bastante más simple de corregir.

### 34.1 Auditoría real — la causa NO era el volumen de datos de negocio

Antes de tocar nada: se midió `system.parts` de **todas** las tablas de `urbanflet_gold` (46
tablas, incluidas las 4 grandes ya sospechadas en §8.6b — `bronze_viaje_historico_nyc`,
`fact_viaje_historico`, `bronze_ciclo_viaje`, `fact_ciclo_viaje`). Resultado real:
`primary_key_bytes_in_memory` + `marks_bytes` sumados de las 46 tablas da apenas unos cientos de
KB — nada que explique un RSS de >1GB. La hipótesis de §8.6b ("el consumo grande es de
metadata/índices primarios en memoria de las tablas MergeTree grandes") queda **descartada con
datos reales**, no solo "no confirmada" como decía esa sección.

Se reprodujo la consulta real que fallaba (`SELECT DISTINCT pago_id FROM fact_recaudacion WHERE
fecha != {fecha}`, la misma de `dag_finanzas_gold::_silver_y_cuarentena`) directo por
`clickhouse-client`, con el error real: *"would use 439.33 MiB (attempt to allocate chunk of
99377692 bytes), current RSS 1.30 GiB, maximum: 1.37 GiB"*. Ese "maximum: 1.37 GiB" es
`max_server_memory_usage` (fijado en `clickhouse/config.d/memoria.xml` desde el segundo intento de
§8.6b) — **no** el `mem_limit` del contenedor (1700m). El dato clave: la consulta en sí solo
necesitaba ~100MB de scratch para deduplicar 1.2M filas (una cifra perfectamente normal para un
`DISTINCT`/hash de UUIDs) — el problema es que el **RSS en reposo, sin ninguna consulta corriendo**,
ya ocupaba 1.30GiB de un techo interno de 1.37GiB, dejando ~70MB de margen para cualquier cosa.

**La causa real, encontrada revisando `system.parts` de la base `system` (no `urbanflet_gold` —
un lugar que §8.6b nunca miró):** las tablas de log internas de ClickHouse **no traen ningún TTL
en la imagen stock**, y llevan acumulando sin límite desde que se creó el volumen de datos
(`min(event_time)` real: **2026-07-29**, casi un mes):

| Tabla | Filas | Disco | Descomprimido |
|---|---|---|---|
| `system.text_log` | **51,602,341** | 1.73 GiB | 27.4 GiB |
| `system.asynchronous_metric_log` | **198,785,207** | 59 MiB | 3.05 GiB |
| `system.trace_log` | 7,490,157 | 111 MiB | 2.14 GiB |
| `system.query_log` | 363,150 | 42 MiB | 259 MiB |
| `system.processors_profile_log` | 1,462,382 | 36 MiB | 284 MiB |

Confirmado con el experimento decisivo, antes de decidir cualquier corrección: `TRUNCATE` de estas
6 tablas bajó el RSS real del proceso (medido con `/proc/1/status` VmRSS dentro del contenedor, no
un cálculo indirecto) de **1,181,808 KB a 595,140 KB** — de inmediato, sin reiniciar nada — y la
misma consulta que fallaba pasó a ejecutarse sin error. Ninguna de estas 6 tablas la lee código de
la aplicación (`backend/`, `analytics/`) — confirmado por grep antes de truncar: son puramente de
observabilidad del propio ClickHouse, sin ningún consumidor real en este proyecto.

**Veredicto exacto, respondiendo la pregunta del usuario**: no era una operación ineficiente (la
consulta necesitaba ~100MB, una cifra razonable) ni un límite de memoria genuinamente insuficiente
para el volumen real de datos de negocio (ese volumen es de ~300MB en disco *combinado*, muy por
debajo de cualquier techo razonable). Era una **tercera causa que ninguna de las 2 opciones
anticipaba**: tablas de diagnóstico internas del propio motor, sin relación con los datos de la
aplicación, consumiendo la casi totalidad del presupuesto de memoria antes de que cualquier
consulta real empezara a correr.

### 34.2 Corrección — TTL real, no un `mem_limit` más alto

Como el volumen de negocio real no justificaba subir memoria (eso solo habría corrido el problema
unas semanas más adelante, exactamente lo que ya había pasado entre el primer y el segundo intento
de §8.6b), la corrección es agregar TTL a esas tablas de log, no tocar `mem_limit` ni
`max_server_memory_usage`. Nuevo archivo
[clickhouse/config.d/retencion_logs_sistema.xml](clickhouse/config.d/retencion_logs_sistema.xml),
montado en el servicio `clickhouse` de `docker-compose.yml` junto a `memoria.xml`: redefine
`query_log`/`part_log` (TTL 7 días — algo más útiles para investigar un incidente puntual) y
`trace_log`/`text_log`/`metric_log`/`asynchronous_metric_log`/`processors_profile_log` (TTL 3 días
— diagnóstico de bajo valor pasado el momento), cada uno con `replace="1"` para sobreescribir el
bloque stock en vez de duplicarlo.

**Bug real cometido y corregido en el propio archivo antes de aplicarlo**: la primera versión del
XML usaba `--` (doble guion) varias veces dentro del comentario explicativo, siguiendo el mismo
estilo de prosa que el resto de comentarios de este proyecto — pero un comentario XML **no puede
contener `--` en ningún lugar de su contenido** (restricción real del estándar XML, no de
ClickHouse). El primer intento de recrear el contenedor con este archivo lo dejó en **crash-loop**
(`SAXParseException: Invalid token`, log real confirmado) — corregido reescribiendo el comentario
sin ningún `--`, verificado que el contenedor arrancó limpio en el segundo intento (`Merging
configuration file... retencion_logs_sistema.xml` sin excepción posterior, log real).

**Verificado que el TTL se aplicó de verdad, no solo que el archivo se cargó**: `SHOW CREATE TABLE
system.text_log` después de recrear el contenedor confirma `TTL event_date + toIntervalDay(3)` en
la definición real de la tabla — ClickHouse re-crea la tabla de log automáticamente cuando su
config cambia. `mem_limit: 1700m` se dejó exactamente igual — no hizo falta subirlo, la causa real
no era de volumen.

### 34.3 Verificación de extremo a extremo, con el mismo dato real de la ronda anterior

**Ciclo completado, no un caso de prueba nuevo**: las mismas 6 liquidaciones reales generadas en
§33.4 (comisión real al 20%/25% según la fecha del viaje) se llevaron hasta ClickHouse. Dado que
el scheduler de Airflow seguía sin recoger triggers manuales de este DAG en tiempo razonable (un
problema real mismo síntoma ya visto en §33.4, sin ninguna relación con la memoria de ClickHouse —
ver nota abajo), se corrieron las 4 tareas reales de `dag_finanzas_gold`
(`_extraer`/`_silver_y_cuarentena`/`_gold`/`_metricas`, importadas tal cual del propio archivo del
DAG, sin reescribir nada) en un solo proceso Python dentro del contenedor `airflow-scheduler`, más
`indicadores.refrescar_margen_comision()` — mismo código real, sin la capa de orquestación que
está fallando por un motivo aparte. Resultado real, sin ningún error esta vez: "Silver finanzas: 5
válidos, 0 en cuarentena" (antes: `MEMORY_LIMIT_EXCEEDED` en este mismo paso), "Gold finanzas: 0 en
fact_recaudacion, 5 en fact_liquidacion", "Corrida ... OK: 5/5 validos", `refrescar_margen_comision:
True`.

**Confirmado en ClickHouse**: `rpt_margen_comision` para el periodo 2026-08 pasó de
`margen=0.19970898508548562` (bruto 27.49, comisiones 5.49 — el snapshot viejo, sin las 6
liquidaciones nuevas) a **`margen=0.2032142101924297`** (bruto 47.29, comisiones 9.61) — el
promedio ponderado subió porque ahora mezcla los viajes al 20% de siempre con los 2 de Christopher
Anderson al 25% de la ronda anterior.

**Confirmado en navegador real, los 2 dashboards pedidos** (cuentas `staff-verificacion` y
`gerencia`, sesión limpia cada vez):
- **Panel de Liquidación de Comisiones** (táctico): "MARGEN DE COMISIÓN → **20.3%**" (antes
  mostraba el snapshot viejo, ~20.0%).
- **Panel de Integridad Financiera** (estratégico): "MARGEN DE COMISIÓN PROM. → **20.2%**" (un
  promedio ponderado sobre una ventana más amplia de meses, por eso no es idéntico al del panel
  táctico — mismo mecanismo `promedio_ponderado` ya documentado en §12.2, no una inconsistencia).

### 34.4 El mismo techo bloqueó otros procesos — confirmado con evidencia real, no solo sospechado

Se revisó la metadata real de Airflow (`TaskInstance.state='failed'`, no solo `corridas` de
ClickHouse — esa tabla nunca registra un fallo de memoria porque el crash ocurre ANTES de llegar a
`finalizar_corrida()`, así que un `MEMORY_LIMIT_EXCEEDED` es invisible en `corridas` por diseño,
otro hallazgo real de esta auditoría). Resultado: **sí**, el mismo techo bloqueó silenciosamente
otros 4 refrescos de `dag_publicar_indicadores` en fechas recientes, todos con el mismo
`MEMORY_LIMIT_EXCEEDED` real (confirmado leyendo el log de una de ellas: *"would use 1.20 GiB...
current RSS 1.37 GiB, maximum: 1.37 GiB"*):

| Tarea (`dag_publicar_indicadores`) | Tabla que refresca | Dashboard afectado | Última falla real |
|---|---|---|---|
| `conversion_captacion` | `rpt_conversion_captacion` | Captación (táctico/estratégico) | 2026-08-23 |
| `tasa_cancelacion` | `rpt_tasa_cancelacion` | Confiabilidad del servicio (estratégico), Despacho (táctico) | 2026-08-23 |
| `tiempo_asignacion` | `rpt_tiempo_asignacion` | Confiabilidad del servicio, Despacho | 2026-08-19 |
| `desempeno_conductor` | `rpt_desempeno_conductor` | Rendimiento de Conductores (táctico/estratégico) | 2026-08-18 |

Y **`dag_viajes_core::silver_y_cuarentena`** (el caso original de §8.6b) volvió a fallar el
**2026-08-23** — 8 días después de que esa sección diera el tema por "parar ahí", confirmando que
subir `mem_limit` una vez (1400m→1700m) solo pospuso la recurrencia, exactamente como se sospechaba
sin poder probarlo entonces.

Las 4 tablas de la lista de arriba ya muestran `fecha_datos=2026-08-25` (hoy) al momento de cerrar
esta ronda — se recuperaron solas por el reintento automático de Airflow (`retries: 3`) una vez que
el RSS bajó lo suficiente entre corridas, así que **no están stale ahora mismo** y no hizo falta
volver a correrlas en esta ronda. Pero el patrón (fallo intermitente, no permanente) es la firma
exacta de un baseline pegado al techo — con la causa real ya corregida (TTL en los logs), estas 4
tareas y `dag_viajes_core` deberían dejar de fallar de forma recurrente, sin necesitar ningún ajuste
propio en cada una: la corrección es a nivel de servidor completo, no por tabla.

**Nota aparte, no relacionada con la memoria**: durante esta verificación se confirmó que el
scheduler de Airflow de este entorno sigue sin recoger triggers manuales
(`airflow dags trigger`) de `dag_finanzas_gold` en un tiempo razonable — mismo síntoma ya visto en
§33.4, con causa propia sin investigar todavía (no es el mismo problema que este techo de memoria;
un trigger manual quedó en `queued` sin que ningún log del scheduler mencionara el DAG en varios
minutos, con la cola completamente libre). Dicho explícitamente para que una sesión futura no lo
confunda con este hallazgo — es un problema de Airflow distinto, sin resolver.

### 34.5 Regresión completa del sistema tras el cambio de infraestructura

**Memoria de los demás contenedores, medida después del cambio** (para confirmar que nadie quedó
en riesgo): ClickHouse **433MiB / 25.5%** de su `mem_limit` (bajó desde ~85-90%), mongo 64.7%,
airflow-scheduler 48.2%, airflow-webserver 63.3%, backend 33.5%, pocketbase 13.1%, airflow-db
12.9%, redis 5.4% — ninguno cerca de su techo. Los 8 servicios del stack confirmados `Up`/healthy
tras el `--force-recreate` de ClickHouse (el único contenedor recreado; `clickhouse_data` es un
volumen persistente, así que el recreate no tocó ningún dato real — confirmado con
`fact_liquidacion` mostrando las mismas 12 filas antes y después).

Backend `pytest` **482 passed** (mismo número que al cierre de §33, sin código de aplicación
tocado en este bloque — solo infraestructura), misma 1 falla preexistente sin relación (Google
Maps). `ruff check` limpio. Frontend: `build`/`lint`/`test` limpios en `shared-ui` + las 3 apps
(`web-pasajero` 10/10, `web-conductor` 6/6, `web-interno` 29/29, mismos 3 warnings preexistentes de
`useEffect`) — ningún archivo de `apps/` se tocó en este bloque, corrido igual para confirmar que
el cambio de infraestructura no tuvo ningún efecto colateral sobre el frontend.

**Con esto, el techo de memoria de ClickHouse documentado desde §8.6b queda cerrado de raíz** — no
con más memoria, con la causa real corregida.

## 35. Reemplazo global del logotipo — logotipo horizontal real (isotipo U + "UrbanFleet" + eslogan)

Pedido explícito del usuario: el archivo `logo_urbanfleet.png`/`Logo_urbanfleet_final.png` usado
hasta ahora (taxi amarillo, ver §20) queda reemplazado por un logotipo nuevo,
`logotipo_urbanfleet_transporte_urbano.png` (raíz del repo) — un isotipo "U" ámbar + wordmark
"UrbanFleet" en tinta oscura + eslogan "TRANSPORTE URBANO". Confirmado real antes de tocar nada
(mismo chequeo que falló la vez anterior con el logo que nunca llegó): archivo presente, 333KB,
`git status` lo muestra como no trackeado (nuevo). `PIL` confirmó `RGBA` con canal alfa real
(min 0, max 255) — el fondo blanco visible en el visor es el lienzo del visor, no relleno opaco.

### 35.1 Fase 0 — los 2 usos reales, no solo el del sidebar

Grep de `logoIcon`/`logoUrbanFleetFull` en los 3 portales encontró exactamente **2 puntos
centralizados** (nunca archivo por archivo, ya establecido desde el rediseño anterior) + las 3
pantallas de login que consumen uno de ellos:

| Componente | Usaba antes | Contexto |
|---|---|---|
| `AppShell.tsx` (andén, `web-interno`) | ícono 30×30 + `<span>UrbanFleet</span>` separado | Sidebar fijo, visible todo el tiempo |
| `CalleShell.tsx` (chasis de calle, `web-pasajero`/`web-conductor`) | ícono 26×26, sin texto aparte | Encabezado móvil de 52px, compartido con el título de la parada y las acciones |
| Los 3 `App.tsx` (login) | `logoUrbanFleetFull` a `width:160` | Login de cada portal, sobre el lavado ámbar de marca |

Ningún otro lugar del código usa el ícono o el nombre como identidad visual — confirmado por el
mismo grep, sin resultados sueltos.

### 35.2 Medición real del espacio disponible, antes de decidir variantes

- **Sidebar** (`--shell-sidebar-width: 264px`, padding `--space-4`/`--space-3`/`--space-4`):
  ancho de contenido real ≈ 232px. La franja de marca no comparte fila con ningún otro elemento.
- **Encabezado de calle** (`.calle-cabecera`, 52px de alto fijo): comparte la fila con el título de
  la parada (`flex:1`, a menudo largo — "Comisión de la cooperativa") y las acciones del extremo —
  mucho más restringido que el sidebar.
- **Login**: contenedor de hasta 400-420px de ancho, sin nada más compitiendo por el espacio.

Con eso decidido: el sidebar SÍ tiene margen real para el logotipo horizontal completo (isotipo +
"UrbanFleet") sin el eslogan; el encabezado de calle no, se queda con el isotipo solo; el login usa
el lockup completo con eslogan.

### 35.3 Variantes recortadas del archivo fuente, con bordes verificados

Medido con `PIL`/`numpy` sobre el canal alfa real (nunca a ojo): el bloque principal
("UrbanFleet") ocupa x:[108,1946] y:[162,483]; el eslogan, una franja aparte y más angosta,
y:[542,596]. El isotipo "U" (máscara por color ámbar real, no por posición) termina en x=329; el
texto oscuro de la línea principal empieza en x=345 — 16px de margen real entre ambos. El primer
intento de recortar solo el isotipo (centrado a ojo en un cuadrado) capturó una porción de la "r"
de "Urban"; corregido recortando con el borde real medido (x≤339), verificado visualmente que el
segundo intento queda limpio.

3 archivos nuevos en `apps/shared-ui/src/assets/`, **mismos nombres que los 2 anteriores** (así
ningún import cambia salvo el nuevo tercero):

| Archivo | Contenido | Uso |
|---|---|---|
| `logo-urbanflet-icon.png` (reemplazado) | Solo el isotipo "U", 251×354 | `CalleShell` |
| `logo-urbanflet-horizontal.png` (nuevo) | Isotipo + "UrbanFleet", sin eslogan, 1858×341 | `AppShell` (andén) |
| `logo-urbanflet-full.png` (reemplazado) | Isotipo + "UrbanFleet" + "TRANSPORTE URBANO", 1858×454 | Las 3 pantallas de login |

### 35.4 Hallazgo real de contraste — la tinta del logo es fija, los 4 tonos de sidebar no lo son

Verificación explícitamente pedida antes de dar esto por cerrado: la tinta oscura del logo nuevo
(`#221305`, medida con `PIL`) es un valor FIJO horneado en el PNG — no reacciona a ningún tema ni
tono. Calculado el contraste WCAG real contra los 4 fondos de sidebar (`sidebarTono.ts`) más el
caso real de "Claro" bajo tema de contenido oscuro (`tokens.css` define un segundo valor de
`--color-sidebar-bg` ahí, la opción "Claro" no es un único color fijo):

| Fondo | Contraste real tinta/fondo |
|---|---|
| Claro (tema de contenido claro) — `#e7ecec` | 15.13:1 |
| Ámbar — `#fbe3ad` | 14.35:1 |
| Claro (tema de contenido oscuro) — `#141c21` | **1.05:1** |
| Oscuro — `#1c140c` | **1.01:1** |
| Grafito — `#24211d` | **1.13:1** |

3 de 5 combinaciones reales dejarían el nombre del logo prácticamente invisible — el problema que
la captura compartida por el usuario no mostraba porque esa captura estaba en el tono por defecto.
Como la tinta viene fija dentro del raster, no se puede resolver con una variable CSS. Corregido
con una **placa clara fija** (`#f7f1e6`, el mismo tono crema ya usado en otros lugares del sistema
como texto sobre oscuro) detrás del logo en los 2 componentes que lo montan sobre una superficie
variable (`AppShell.tsx`/`CalleShell.tsx`) — nunca reacciona a tono ni tema, así que la tinta
siempre lee 16:1+ contra ella sin importar qué esté detrás. El ámbar del isotipo da solo
~1.9-2.1:1 contra esa placa clara, por debajo del mínimo de 3:1 para un elemento gráfico funcional
— aceptado a propósito: un logotipo de marca está exento de ese requisito (no es un indicador de
estado como el nodo del riel), y a simple vista un isotipo ámbar grande sobre fondo claro se ve
perfectamente bien pese al número bajo (mismo criterio ya usado para otros elementos de marca
grandes en este proyecto).

Verificado en navegador real, las 4 opciones de "Color del sidebar" cicladas una por una (cada
cambio en una llamada de script separada de la medición — la misma cautela ya documentada en la
Fase 4 del Sistema Riel: leer el DOM en el mismo script que dispara el evento captura el estado
previo al re-render de React): `sidebarBg` cambió correctamente en las 4 (`#e7ecec`/`#fbe3ad`/
`#1c140c`/`#24211d`, confirmados via `getComputedStyle`), `logoPlacaBg` se mantuvo fijo en
`rgb(247,241,230)` (`#f7f1e6`) en las 4, sin excepción.

### 35.5 Implementación

- `AppShell.tsx`: `<img src={logoHorizontal}>` reemplaza el `<img>` de 30×30 **y** el
  `<span className="anden-marca-nombre">UrbanFleet</span>` que iba al lado — el logo nuevo ya trae
  el nombre, dejar el texto aparte lo habría duplicado. `.anden-marca-icono`/`.anden-marca-nombre`
  eliminados de `AppShell.css`, reemplazados por `.anden-marca-logo` (altura fija 34px, ancho
  automático, placa `#f7f1e6`, `object-fit:contain`).
- `CalleShell.tsx`: mismo archivo `logo-urbanflet-icon.png` (el import no cambia de ruta, solo el
  contenido del PNG), pero se quitaron los atributos HTML `width={26} height={26}` — el icono
  nuevo no es cuadrado (251×354, a diferencia del icono cuadrado anterior), forzar un box de 26×26
  lo habría distorsionado. `.calle-marca` pasa a controlar el tamaño por CSS (`height:30px;
  width:auto`) con la misma placa `#f7f1e6`.
- Los 3 `App.tsx` de login: `width:160` → `width:300` en el `<img>` de `logoUrbanFleetFull` — con
  el lockup nuevo (aspecto 4.09:1, más ancho que el anterior casi cuadrado) el mismo ancho de 160
  habría dejado un logo de apenas 39px de alto, perdiendo el "mayor impacto de marca" que el login
  es el lugar indicado para dar. A 300px de ancho renderiza a 300×73 — confirmado en los 3
  portales, sin desbordar el contenedor de 400-420px de la tarjeta de login.

### 35.6 Verificación real en navegador

**Los 3 portales**, confirmando que el logo nuevo aparece donde antes estaba el anterior:
`web-interno` (andén, `logo-urbanflet-horizontal.png` a 151×34, placa `rgb(247,241,230)`, marca
completa en 229px de los 232px de contenido disponibles); `web-pasajero`/`web-conductor`
(`CalleShell`, `logo-urbanflet-icon.png` a 28×30, misma placa). **Sin ningún resto del ícono o
texto viejo**: grep en el DOM real confirmó `document.querySelector('.anden-marca-icono')` y
`.anden-marca-nombre` ausentes, y ningún nodo de texto suelto con contenido exacto "UrbanFleet" en
ninguno de los 3 portales.

**Viewport angosto y ancho**: `web-interno` a 375px con el cajón móvil abierto (logo visible,
151×34 igual que en escritorio, sin scroll horizontal); `web-pasajero`/`web-conductor` a 375px y
1280px (28×30 en ambos, sin scroll horizontal en ninguno). El chasis de calle no cambia el tamaño
del logo entre anchos — el encabezado de 52px es fijo en los 2 anchos.

**Las 3 pantallas de login**: logotipo horizontal completo con eslogan, 300×73, confirmado en los
3 portales (incluido `web-pasajero`/`web-conductor` a 375px de ancho).

**Regresión**: `build`/`lint`/`test` limpios en `shared-ui` + las 3 apps (`web-pasajero` 10/10,
`web-conductor` 6/6, `web-interno` 29/29, mismos 3 warnings preexistentes de `useEffect`). Backend
no se tocó en este bloque.

## 36. El logo nuevo NO tenía el fondo "quemado" — el rectángulo era la placa CSS de §35, corregido con 2 variantes de tinta + crossfade

El usuario reportó, tras §35, que `logotipo_urbanfleet_transporte_urbano.png` se veía con un
rectángulo de color distinto alrededor en el sidebar — pidió inspeccionar el archivo real,
detectar el color de fondo por muestreo de esquinas, y recortarlo con degradado progresivo (no
umbral duro) para no dejar halo en las curvas del isotipo ni en el texto con anti-aliasing.

**La premisa se investigó a fondo y resultó incorrecta — el archivo nunca tuvo el defecto
reportado.** Evidencia real, no una sola comprobación: muestreo de esquinas (alpha=0 en las 4),
muestreo de huecos internos entre isotipo y wordmark (alpha=0), histograma de alfa (bimodal limpio,
sin meseta intermedia ancha que delataría una zona de "casi transparente pero no del todo"), el
canal alfa visualizado como imagen aparte (letras nítidas sobre negro puro, sin ninguna forma de
rectángulo), lectura de píxeles vía `canvas` real en el navegador coincidiendo exacto con el
análisis en Python, y una simulación de reducción de escala 12x (el peor caso para revelar un
lavado de fondo) sin ningún rastro entre huecos. El único hallazgo real, y menor: el relleno sólido
de tinta/ámbar queda en alfa≈252-254 en vez de 255 exacto (~99.2% de opacidad) — imperceptible,
sin relación con lo reportado, no corregido.

La causa real del rectángulo visto en pantalla era **la placa de fondo `#f7f1e6` que yo mismo
agregué en §35** (`.anden-marca-logo`/`.calle-marca`, `background: #f7f1e6`) — necesaria en su
momento porque la tinta oscura horneada en el PNG da menos de 1.2:1 de contraste sobre 3 de las 5
combinaciones reales de tono de sidebar/tema de contenido (§35.4). Comuniqué esto al usuario con la
evidencia antes de "arreglar" un archivo que no tenía ningún defecto, y resolví el problema real
(el rectángulo que sí se ve) con el mecanismo correcto: 2 variantes de tinta + crossfade CSS, en
vez de simplemente quitar la placa (que habría reintroducido la ilegibilidad que la placa existía
para resolver).

### 36.1 Variantes de tinta clara, recoloreadas por luminancia (preservando el alfa exacto)

`logotipo_urbanfleet_transporte_urbano.png` → máscara por luminancia (`0.2126*r + 0.7152*g +
0.0722*b < 120`, sobre píxeles con `alpha>0`) para separar tinta de ámbar sin tocar el ámbar; los
227,202 píxeles de tinta se recolorearon a `#f7f1e6` (el mismo crema ya usado como
`--color-sidebar-text-strong` en Oscuro/Grafito), dejando el canal alfa **sin tocar**. Confirmado
con código, no a ojo: en una fila real de la imagen, `alphaDiffs=0` entre la variante original y la
recoloreada a lo largo de todo el ancho escaneado — el alfa es byte-por-byte idéntico, incluidos
los píxeles de borde con anti-aliasing parcial (251, 248…), así que el recorte no introdujo ningún
halo nuevo.

Recortadas con el MISMO bounding box que las variantes ya existentes de §35 (`(98,152,1956,493)`
horizontal, `(98,152,1956,606)` completo) — dimensiones pixel-idénticas, indispensable para que el
crossfade superponga exactamente:

| Archivo nuevo | Dimensiones | Uso |
|---|---|---|
| `apps/shared-ui/src/assets/logo-urbanflet-horizontal-invertido.png` | 1858×341 (= horizontal) | Andén (`AppShell`) |
| `apps/shared-ui/src/assets/logo-urbanflet-full-invertido.png` | 1858×454 (= full) | Login (`LoginLogo`) |

### 36.2 Mecanismo: 2 imágenes apiladas en la misma celda de grid + interruptor CSS, nunca una placa

Mismo patrón "propiedad por tema" ya establecido en todo `tokens.css` (theme.ts/densidad.ts/
sidebarTono.ts), sin infraestructura nueva:

- **`--logo-invertido`** (0/1): base `:root`=0, `:root[data-theme="dark"]`=1 — y **sobre-escrito
  por tono de sidebar** vía un campo nuevo `logoInvertido` en `SwatchSidebar`
  (`sidebarTono.ts`): `ambar`→"0" (fondo claro, tinta oscura), `oscuro`/`grafito`→"1" (fondo
  oscuro, tinta clara); `claro` no fija nada (limpia el override inline y hereda el valor del
  tema, igual que el resto de `PROPIEDADES`). Usado por `AppShell.tsx`.
- **`--logo-invertido-tema`** (0/1): variable HERMANA, deliberadamente separada, que SOLO
  reacciona al tema de contenido (`:root`=0, `:root[data-theme="dark"]`=1) y que
  `sidebarTono.ts` **nunca toca**. Necesaria porque `aplicarSidebarTonoInicial()` corre en las 3
  apps (la preferencia es de cuenta, "Color del sidebar" es visible hasta en
  `web-pasajero`/`web-conductor`, que no tienen sidebar) — si el login leyera `--logo-invertido`,
  una cuenta que alguna vez eligió "Ámbar" (0) vería tinta oscura ilegible sobre un login en tema
  oscuro, un override de sidebar sin relación filtrándose a una pantalla sin sidebar. Usado por el
  nuevo `LoginLogo.tsx` (`shared-ui`, las 3 pantallas de login).
- **`.anden-marca-logo`/`CalleShell.css` sin `background` en absoluto**: la placa se eliminó de
  los 2 sitios; ninguna imagen queda montada sobre un color fijo.
- **`AppShell.tsx`**: 2 `<img>` en la misma celda de `display:grid` (`.anden-marca-logo--base`/
  `--invertido`), opacidad `calc(1 - var(--logo-invertido, 0))` / `var(--logo-invertido, 0)`,
  transición de 0.15s (`prefers-reduced-motion` respetado).
- **`CalleShell.tsx`/`.css`**: **sin variante invertida** — el recorte de solo-icono
  (`logo-urbanflet-icon.png`) es ámbar puro sobre transparente (confirmado por código: de 27,759
  píxeles visibles solo 17 tienen luminancia baja, y esos 17 son antialiasing de borde con
  alfa 11-21, no tinta real) — un logotipo de marca está exento del mínimo de contraste de un
  indicador funcional, mismo criterio ya aplicado al ámbar del riel.
- **`LoginLogo.tsx`** (nuevo, `shared-ui`, exportado desde `index.ts`): mismo mecanismo de
  crossfade que el andén pero con `--logo-invertido-tema`, extraído a componente porque el
  bloque `<img>` + estilo inline se repetía idéntico en los 3 `App.tsx` de login — mismo criterio
  de extracción ya aplicado a `TabButton`/`Alert` en rondas anteriores. Reemplaza el `<img
  src={logoUrbanFleetFull}>` suelto en los 3 logins.

### 36.3 El archivo viejo (punto 5 del pedido) — no aplica, ya no está en uso

`logo_urbanfleet.png` ya no existe en el repo (fue renombrado a `Logo_urbanfleet_final.png` en
una ronda anterior, §20) y ese sucesor tampoco está referenciado por ningún archivo de `apps/` —
quedó completamente reemplazado por `logotipo_urbanfleet_transporte_urbano.png` en §35. No había
nada que recortar ahí: es arte fuente muerto en la raíz del repo, sin ningún consumidor real.

### 36.4 Verificación real en navegador, las 4 combinaciones + los 2 portales de calle

Contra el stack real (`staff-verificacion` para el andén, cuenta demo de pasajero para
`CalleShell`), con el gotcha ya documentado en §29-31 confirmado de nuevo: alternar el tono/tema
EN VIVO por script dejaba la opacidad calculada en el valor viejo (mismo artefacto de repintado de
Chromium sin frames compuestos) — la verificación correcta, como ya lo dice este archivo, es
**recargar tras fijar la preferencia**, no leer en la misma ejecución que dispara el cambio.

- **Claro** (default): `--logo-invertido:0`, `sidebarBg:#e7ecec`, logo base opacity 1 / invertido
  0. `backgroundColor` de ambas imágenes: `rgba(0,0,0,0)` — sin placa, confirmado.
- **Ámbar**: `sidebarBg:#fbe3ad`, `--logo-invertido` sigue en 0 (tinta oscura correcta sobre fondo
  claro).
- **Oscuro** (tras recarga): `sidebarBg:#1c140c`, `--logo-invertido:1`, base opacity 0 / invertido
  1 — confirmado también por `src` real (`logo-urbanflet-horizontal-invertido.png` visible).
- **Grafito** (tras recarga): `sidebarBg:#24211d`, mismo resultado que Oscuro.
- **Claro de nuevo**: confirmado que `aplicarAtributo("claro")` limpia TODOS los overrides
  inline, incluido el nuevo `--logo-invertido` — `document.documentElement.getAttribute("style")`
  quedó sin ningún `--color-sidebar-*` ni `--logo-invertido` colgando.
- **El caso que el mecanismo de 2 variables existe para evitar, reproducido real**: con
  `sidebar_tono="ambar"` (que fuerza `--logo-invertido:0`) y tema de contenido en oscuro, el login
  de `web-interno` mostró `--logo-invertido-tema:1` (correcto, ignora el tono de sidebar) y la
  imagen invertida con opacity 1 — si el login hubiera reusado `--logo-invertido` habría mostrado
  tinta oscura ilegible sobre el fondo oscuro real (`#10161a`). Confirmado también el caso
  contrario (tema claro → invertido-tema 0, logo de tinta oscura visible).
- **`CalleShell` (`web-pasajero`, cuenta demo de pasajero)**: `.calle-marca` con
  `backgroundColor: rgba(0,0,0,0)`, `src` = `logo-urbanflet-icon.png` — sin placa.
- **Edge del isotipo/curvas, con lectura de canvas real** (no a ojo): franja horizontal de la
  imagen base mostrando el alfa subir de forma progresiva a través de ~8 píxeles
  (0→3→1→10→116→243→249→251→253), nunca un salto abrupto, y sin fringe de color claro en los
  píxeles de alfa parcial (RGB se mantiene ambarino incluso a alfa bajo) — anti-aliasing genuino,
  intacto.
- **Cuenta demo restaurada**: `staff-verificacion` quedó con `sidebar_tono` real en el servidor
  puesto de vuelta en "claro" (vía la UI real, no solo localStorage) tras las pruebas.

**Regresión**: `build`/`lint`/`test` limpios en `shared-ui` + las 3 apps (`web-pasajero` 10/10,
`web-conductor` 6/6, `web-interno` 29/29, mismos 3 warnings preexistentes de `useEffect`). Backend
no se tocó.

## 37. Docker de punta a punta para portafolio (noviembre 2026) + recuperación de código perdido

Objetivo: `cp .env.example .env && docker compose up --build` levanta TODO (incluidos los 3
frontends) con datos de demostración realistas de Quevedo. Ver README, sección "Ejecutar con Docker".

**Pérdida de archivos encontrada al empezar (no causada en esta sesión)**: el 2026-11-23 a las
19:27 se vaciaron `web-interno/src/sections/tactico/`, `.../estrategico/` y
`shared-ui/src/components/charts/` (ya aparecían como borrados en el `git status` inicial), y
desapareció `shared-ui/src/assets/fonts/big-shoulders-display.woff2`. Decisión del usuario:
- 23 archivos restaurados desde el último commit (`84aec17`, versión del 8 de agosto): compilan
  contra la API actual, pero **sin las mejoras posteriores** dentro de esos paneles (modales de
  detalle de KPI de §17.6-17.11, limpieza de jerga de §27, diversificación de gráficos).
- 5 archivos que nunca se commitearon, **reconstruidos**: `HeatMap`, `WaterfallChart`,
  `BulletBarChart` (hoy solo `BulletBarChart` tiene consumidor) y los paneles
  `PanelRendimientoConductores` / `PanelDesempenoConductores` sobre los endpoints reales.
- La fuente Big Shoulders Display ahora se carga desde Google Fonts (`@import` en `tokens.css`,
  igual que Barlow). Esto reemplaza la decisión de §20 de alojarla localmente.
- También se perdieron los volúmenes Docker con el histórico (1.3M viajes NYC): los volúmenes del
  proyecto `urbanflet-taxiflow` fueron recreados el 2026-11-23 21:34 por una sesión anterior en
  la copia vieja `..\UrbanFlet-TaxiFlow`, que declara **el mismo nombre de proyecto Compose** (y
  por lo tanto comparte volúmenes y puertos con esta carpeta).

**Piezas nuevas** (portadas de la sesión anterior en la copia vieja y adaptadas al código actual):
`docker/frontend.Dockerfile` + `docker/nginx-spa.conf` (build de Vite servido por nginx, puertos
5173/5174/5175), `.dockerignore` raíz y `backend/.dockerignore`, servicios nuevos en
`docker-compose.yml`: `seed` (una vez), `flota-simulador` (mueve a los socios en turno),
`web-*` y `airflow-bootstrap` (una vez: ejecuta las tareas reales de los 6 DAGs de dominio
día por día sobre 155 días + `dag_publicar_indicadores`, sin `airflow dags backfill` por el
deadlock de §8.8, y despausa los DAGs). Healthchecks nuevos en `backend` y `clickhouse`.
`airflow-init` ya no sobrescribe el entrypoint (sin él no se instalan `clickhouse-connect`/
`pymongo`). `CLICKHOUSE_PASSWORD` vacío en `.env.example` (el contenedor no define contraseña).

`backend/scripts/seed_demo_portafolio.py`: siembra desde base vacía vía servicios reales y con el
reloj congelado por paso. Crea tarifas, comisión 20%, catálogos (talleres con `url_maps`, marcas,
colores, repuestos), las 7 cuentas de §8.7, 45 pasajeros, 43 postulaciones con licencia y
matrícula subidas como imagen PNG real (generadas con zlib, la imagen no trae Pillow) por el flujo
borrador → `POST /archivos` → `enviar_solicitud_con_documentos`, ~1.960 carreras de 90 días
con traza GPS, calificaciones y discrepancias, liquidaciones semanales, 39 órdenes, 6 reportes de
falla con evidencia, referidos y eventos de seguridad. Idempotente (`_meta_seed`).

**Verificado** en un proyecto Compose aislado (`-p urbanflet-demo`, volúmenes nuevos): seed en
297 s, bootstrap en 208 s (exit 0, las 15 `rpt_*` con filas), las 7 cuentas con login 200,
pantallas operativas con datos, 10 paneles tácticos con gráficos, 10 endpoints estratégicos con
datos (`disponible=true` en las 8 tarjetas del tablero), pasajero y conductor en móvil (historial
con traza en mapa, liquidaciones), sin errores en los logs.
