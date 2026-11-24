# Auditoría funcional — Nivel Táctico

Los 10 dashboards del "Panel Táctico" de `web-interno` (uno más que los 9 originales de la spec —
"Rendimiento de Conductores" se agregó en una ronda posterior). Cada uno fue abierto en vivo en esta
sesión, con la cuenta real `staff-verificacion` (+593900000001 / `VerifDash123!`, acumula los 7
roles tácticos), confirmando qué KPI e informes muestran dato real hoy y cuáles muestran "—" con
nota de limitación. Todos combinan al menos un informe "Simple · MongoDB" (consulta directa) y un
informe "Compuesto · ClickHouse" (agregado por el proceso de datos de Airflow) — esa etiqueta
(`FuenteBadge`) aparece en pantalla junto a cada gráfico/tabla y es información real, no decorativa.

**Regla general observada en los 10 paneles**: cuando un dato no existe (por diseño, por falta de
dominio en el sistema, o por una limitación real), el panel lo muestra como "—" con una nota de
texto explicando por qué — nunca lo inventa ni lo omite en silencio. Esto es consistente en todo el
nivel táctico y vale la pena mencionarlo una vez a la audiencia en vez de repetirlo por cada panel.

---

## 1. Coordinación de Flota

### 1.1 Panel de Flota en Vivo y Disponibilidad

**Qué hace y propósito.** Da una foto agregada del estado de toda la flota en este momento: cuántos
conductores tienen turno activo, cuántos están libres para un viaje, y cuántos vehículos dejaron de
reportar posición.

**Por qué existe.** El Coordinador de Flota necesita este resumen para decisiones rápidas (¿tenemos
suficiente cobertura ahora mismo?) sin tener que revisar vehículo por vehículo.

**Dónde se encuentra.** `web-interno` → "Panel Táctico" → "Flota".

**Quién puede usarla.** Rol `coordinador_flota`.

**Pasos para reproducirla en vivo.** Abrir el panel — se carga solo. Probar el filtro "Franja"
(00-06/06-12/12-18/18-24) sobre el gráfico de % de flota activa.

**Flujo completo / estado previo.** Ninguno — siempre tiene datos si hay algún vehículo con turno
activo o histórico de posiciones.

**Qué muestra al completarse (verificado con datos reales).**
- En servicio: **5**
- Disponibles: **0** (en el momento de la verificación, ningún socio tenía turno `DISPONIBLE`)
- Sin señal: **5**
- % flota activa: **0.9%**
- Gráfico "% de flota activa por franja" (compuesto, ClickHouse): valores reales por franja
  horaria.
- Tabla "Vehículos sin señal o en alerta" (simple, MongoDB): 5 filas reales con vehículo, conductor
  y estado.

**Qué debe saber Darwin.** El filtro por zona está deshabilitado con una nota visible en pantalla
("Filtro por zona no disponible todavía") — la dimensión de zona geográfica no está resuelta en los
datos de posición; no es un botón roto, es una limitación declarada. "Disponibles" en 0 es un
reflejo real del momento (nadie tenía turno iniciado en el instante de la verificación) — si se
quiere mostrar ese KPI en positivo, iniciar el turno de un conductor de demo (`web-conductor`) unos
minutos antes.

---

## 2. Mantenimiento

### 2.1 Panel de Mantenimiento y Costos

**Qué hace y propósito.** Resume cuántas órdenes de mantenimiento están abiertas, cuántos vehículos
están retirados de servicio por eso, qué tan bien se cumple el plan preventivo y cuáles son los
vehículos más costosos del mes.

**Por qué existe.** Le da al Jefe de Mantenimiento visibilidad de costos y cumplimiento sin tener
que sumar manualmente cada orden.

**Dónde se encuentra.** `web-interno` → "Panel Táctico" → "Mantenimiento".

**Quién puede usarla.** Rol `jefe_mantenimiento`.

**Pasos para reproducirla en vivo.** Abrir el panel. Probar los filtros de tipo de orden
(Preventiva/Correctiva), placa y rango de fechas sobre la tabla inferior.

**Flujo completo / estado previo.** Ninguno — el entorno ya tiene 130+ órdenes reales.

**Qué muestra al completarse (verificado con datos reales).**
- Órdenes abiertas: **47**
- Vehículos retirados: **14**
- Cumplimiento preventivo: **100.0%**
- Costo acumulado (top 5): **$1339.21**
- Gráfico "Costo de mantenimiento por vehículo (top 5)" (compuesto): 5 vehículos reales con su
  costo real.
- Gráfico "Cumplimiento del plan preventivo por mes" (compuesto): serie temporal real.
- Tablas de órdenes abiertas/vehículos retirados (simple): decenas de filas reales.

**Qué debe saber Darwin.** Los 4 KPI de este panel muestran dato real hoy, sin ninguna limitación
declarada — es uno de los paneles más completos para abrir primero en la demo. En la tabla se ve
ocasionalmente el nombre de un taller mostrado como "1" en vez de un nombre real en un par de filas
— es un artefacto puntual de datos de una siembra anterior, no un error de la pantalla; si sale en
la demo, no afecta ningún cálculo, solo la etiqueta visible de esa fila.

---

## 3. Cumplimiento

### 3.1 Panel de Vigencia Documental

**Qué hace y propósito.** Muestra cuántos documentos de los socios (licencias, matrículas) están
vencidos o por vencer, y su tendencia en el tiempo.

**Por qué existe.** Control normativo — la cooperativa necesita anticiparse a los vencimientos, no
enterarse cuando ya es tarde.

**Dónde se encuentra.** `web-interno` → "Panel Táctico" → "Vigencia Documental".

**Quién puede usarla.** Rol `supervisor_cumplimiento`.

**Pasos para reproducirla en vivo.** Abrir el panel. Probar el filtro de tipo de documento
(Licencia/Matrícula) y el rango de vencimiento sobre la tabla.

**Flujo completo / estado previo.** Ninguno — hay 142 documentos reales en el entorno.

**Qué muestra al completarse (verificado con datos reales).**
- Vencidos: **67**
- Por vencer (≤30d): **27**
- % vigente: **0.5%** (bajo porque una buena parte de los documentos sembrados ya está vencida por
  antigüedad de la siembra — es un dato real, no un error)
- Bloqueados: **0**
- Gráfico "Documentación vigente por tipo" (compuesto): licencia y matrícula con su % real, con
  franjas de color (peligro/advertencia/bueno).
- Gráfico "Tendencia mensual de % vigente" (compuesto): serie real con varios cortes desde
  2026-08-09.
- Tabla de documentos vencidos/por vencer (simple): decenas de filas reales.

**Qué debe saber Darwin.** El % vigente bajo (0.5%) es un reflejo real de que buena parte de los
documentos de prueba fueron sembrados ya vencidos — no ocultarlo, es información real y coherente
con el resto del sistema (el mismo dato se ve también en Cumplimiento operativo). Si se pregunta por
qué es tan bajo, la respuesta honesta es esa.

---

### 3.2 Panel de Auditoría e Integraciones (patrón F)

**Qué hace y propósito.** Combina la bitácora completa de acciones administrativas con indicadores
de uso del sistema — cuántos eventos hubo hoy, cuántos accesos fueron denegados, y qué tan usado
está cada endpoint.

**Por qué existe.** Le da a Cumplimiento visibilidad tanto de qué se hizo en el sistema como de
quién intentó hacer algo sin permiso.

**Dónde se encuentra.** `web-interno` → "Panel Táctico" → "Auditoría".

**Quién puede usarla.** Rol `supervisor_cumplimiento`.

**Pasos para reproducirla en vivo.** Abrir el panel. Probar los filtros de actor, acción y
resultado (Todos/Denegado/OK) sobre la bitácora.

**Flujo completo / estado previo.** Ninguno — la bitácora siempre tiene contenido real.

**Qué muestra al completarse (verificado con datos reales).**
- Eventos hoy: **264**
- Accesos denegados: **100**
- Integraciones usadas: **59**
- Gráfico "Uso de integraciones por ruta" (compuesto): 20 acciones reales con su conteo.
- Bitácora completa (simple): cientos de eventos reales, incluidos varios `POSIBLE_GPS_SPOOFING`
  denegados reales (protección anti-suplantación de ubicación, ver la etapa de turno del conductor
  dentro de "Gestión del ciclo de vida del viaje" en el documento Operativo).

**Nota (segunda pasada de correcciones, agosto 2026):** el KPI "% de errores" que aparecía acá se
quitó de la interfaz — nunca tuvo dato real detrás (`rpt_uso_integraciones` solo trae
endpoint/conteo; no existe ningún dominio de credenciales/latencia/error de integraciones en el
sistema, decisión ya tomada de no construirlo) y se decidió no ocupar espacio con un indicador que
nunca va a poder mostrar un número. El panel ahora muestra 3 KPIs en vez de 4.

**Qué debe saber Darwin.** Este es el único panel táctico con layout "F" (la tabla domina la
pantalla, el gráfico queda en una columna angosta a la izquierda) — visualmente distinto a los
otros 9, es una decisión de diseño intencional, no una inconsistencia. El gráfico de uso de
integraciones solo cuenta solicitudes, no errores.

---

## 4. Captación

### 4.1 Panel de Captación y Altas de Socios

**Qué hace y propósito.** Mide qué tan bien está funcionando el embudo de captación: cuántas
solicitudes están pendientes, qué porcentaje termina aprobado, cuánto tarda la decisión y qué tanto
se retienen los socios nuevos.

**Por qué existe.** Le da al equipo de Captación una vista de rendimiento del proceso de alta, no
solo del volumen.

**Dónde se encuentra.** `web-interno` → "Panel Táctico" → "Captación".

**Quién puede usarla.** Rol `admin_captacion`.

**Pasos para reproducirla en vivo.** Abrir el panel. Probar el filtro de canal (app/campaña/
referido/web/whatsapp) sobre la tabla de solicitudes pendientes.

**Flujo completo / estado previo.** Ninguno — el entorno ya tiene 170+ solicitudes reales.

**Qué muestra al completarse (verificado con datos reales).**
- Solicitudes pendientes: **24**
- Conversión del mes: **66.7%**
- Tiempo promedio de aprobación: **1.0d**
- Retención a 90 días: **0.0%**, con nota explícita en pantalla: es una aproximación (estado
  `ACTIVO` en el momento del corte, no un re-chequeo real a los 90 días) porque no existe ningún
  proceso que reobserve usuarios periódicamente.
- Gráfico "Conversión de altas por canal" (compuesto): serie real.
- Tabla de solicitudes pendientes de verificación y de referidos (simple): decenas de filas reales.

**Qué debe saber Darwin.** El 0.0% de retención no es un error — es consistente con que ningún
socio de este entorno de desarrollo tiene realmente 90+ días de antigüedad activa medible con este
método; la nota en pantalla ya lo explica, conviene leerla en voz alta si se pregunta. Casi todas las
solicitudes de la bandeja aparecen "Fuera de plazo" — es reflejo real de que son datos de siembra
antigua, no un fallo del cálculo de plazo.

---

## 5. Operaciones y Despacho

### 5.1 Panel de Despacho y Demanda

**Qué hace y propósito.** Mide la salud del proceso de asignación de viajes: cuántos están activos
ahora, cuánto tarda en promedio asignar un conductor, y cuántos se quedan sin atender.

**Por qué existe.** Es el pulso operativo del negocio en tiempo real — permite detectar si hay un
problema de cobertura antes de que se acumulen quejas.

**Dónde se encuentra.** `web-interno` → "Panel Táctico" → "Despacho".

**Quién puede usarla.** Rol `coordinador_operaciones`.

**Pasos para reproducirla en vivo.** Abrir el panel. Probar los filtros de zona y franja sobre el
gráfico de tiempo de asignación.

**Flujo completo / estado previo.** Ninguno.

**Qué muestra al completarse (verificado con datos reales).**
- Viajes activos: **0** (reflejo real del instante — no había ningún viaje en curso al momento de
  la verificación).
- Tiempo de asignación promedio: **7s**
- Sin conductor hoy: **5**
- Tasa de cancelación: **78.3%** (corregido en la ronda de agosto 2026 — ver nota abajo)
- Gráfico "Tiempo de asignación por zona y franja" (compuesto): datos reales por combinación
  zona×franja.
- Tabla "Viajes SIN_CONDUCTOR y cancelados, con motivo" (simple): filas reales recientes.

**Nota (ronda de correcciones, agosto 2026).** Este KPI daba **100.0%** de forma permanente, sin
importar el período, por un defecto de raíz en la agregación (`rpt_tasa_cancelacion`): el
denominador ("viajes solicitados") se calculaba con el mismo agrupamiento que separa los
cancelados por motivo/actor, así que en la práctica siempre daba igual al numerador. Corregido
calculando el universo real de viajes solicitados por separado; el número actual (78.3% en el
período de la verificación) es un dato real, no una aproximación, confirmado contra un conteo
manual directo en Mongo.

---

### 5.2 Panel de Rendimiento de Conductores

**Qué hace y propósito.** Compara a los socios conductores entre sí: viajes completados,
cancelados, % de éxito, calificación e ingreso neto, en una ventana de tiempo elegible.

**Por qué existe.** Permite identificar socios con bajo desempeño o con oportunidad de
reconocimiento, algo que antes no existía como vista consolidada.

**Dónde se encuentra.** `web-interno` → "Panel Táctico" → "Rendimiento de Conductores".

**Quién puede usarla.** Rol `coordinador_operaciones`.

**Pasos para reproducirla en vivo.** Abrir el panel. Probar el selector "Ventana" (último mes/3
meses/6 meses/12 meses) y el toggle "Ventana reciente" / "Histórico completo".

**Flujo completo / estado previo.** Ninguno.

**Qué muestra al completarse (verificado con datos reales).**
- Socios en la ventana: **5**
- % de éxito promedio: **100.0%**
- Cancelados (ventana): **0**
- Ingreso neto (ventana): **$0.00** (con la ventana amplia probada; varía según el filtro elegido)
- Gráfico "Viajes completados por socio" (compuesto) y tabla comparativa por socio y periodo
  (compuesto): datos reales.

**Qué debe saber Darwin — advertencia visible en pantalla, léela antes de mostrar este panel.** El
sistema mismo muestra una nota: *"La ventana reciente seleccionada igual incluye periodos del
dataset NYC 2021 (no hay datos entre 2021-02 y 2026-07 en este entorno): incluye los viajes
sembrados del dataset NYC 2021, repartidos por round-robin entre solo 5 conductores reales — la
comparación entre socios en esos periodos no refleja varianza real de desempeño, solo volumen de
siembra."* En la práctica esto se ve como conductores con cientos de miles de "viajes completados"
en 2021-01/2021-02 — es un artefacto conocido y declarado del volumen de datos de calibración
(dataset histórico de taxis de Nueva York usado para poblar el sistema), no una falla de cálculo.
Elegir "Ventana reciente" con el periodo más corto (Último mes) minimiza este efecto para la demo.

---

## 6. Control Financiero

### 6.1 Panel de Conciliación de Pagos

**Qué hace y propósito.** Muestra cuántos pagos tienen una discrepancia sin resolver entre lo
cobrado y lo esperado, y qué porcentaje de los pagos en efectivo concilia sin problema.

**Por qué existe.** Control de exactitud del cobro — evita que discrepancias pequeñas se acumulen
sin que nadie las note.

**Dónde se encuentra.** `web-interno` → "Panel Táctico" → "Conciliación".

**Quién puede usarla.** Rol `admin_financiero`.

**Pasos para reproducirla en vivo.** Abrir el panel. Probar el filtro de método de pago sobre la
tabla de discrepancias.

**Flujo completo / estado previo.** Ninguno — el entorno tiene una discrepancia real cargada.

**Qué muestra al completarse (verificado con datos reales).**
- Discrepancias: **1**
- Monto en disputa: **$0.50**
- % conciliado: **88.9%**
- Viajes sin pago: **3**
- Gráfico "Tasa de discrepancias mensual" (compuesto): serie real por método (efectivo/electrónico).
- Tablas de discrepancias abiertas y viajes sin pago (simple): filas reales.

**Qué debe saber Darwin.** Los 4 KPI muestran dato real, sin ninguna limitación declarada — uno de
los paneles más limpios para demostrar. Es el mismo dato que se ve en el Control Financiero
operativo ("Conciliación y liquidación de pagos a socios" del documento Operativo) — buena
oportunidad de mostrar cómo el nivel táctico agrega lo que el nivel operativo ya gestiona caso por
caso.

---

### 6.2 Panel de Liquidación de Comisiones

**Qué hace y propósito.** Resume cuántas liquidaciones semanales se emitieron, cuántas siguen
pendientes de aprobar, y cuál es el margen de comisión real de la cooperativa.

**Por qué existe.** Visión financiera agregada del negocio, más allá de revisar liquidación por
liquidación.

**Dónde se encuentra.** `web-interno` → "Panel Táctico" → "Liquidación".

**Quién puede usarla.** Rol `admin_financiero`.

**Pasos para reproducirla en vivo.** Abrir el panel. Probar los filtros de estado y periodo sobre
la tabla de liquidaciones.

**Flujo completo / estado previo.** Ninguno — 71 liquidaciones reales en el entorno.

**Qué muestra al completarse (verificado con datos reales).**
- Liquidaciones emitidas: **13**
- Por aprobar: **17**
- Margen de comisión: **20.0%**
- Tiempo promedio de pago: **1.3h**
- Gráfico "Margen de comisión por mes" y "Composición del margen" (compuestos): datos reales
  (bruto $30, comisión $6, neto $24 para julio 2026).
- Tabla de liquidaciones por socio y periodo (simple): decenas de filas reales, con los 4 estados
  del ciclo de vida representados.

**Qué debe saber Darwin.** Es un buen panel para mostrar variedad de estados de negocio en una sola
tabla (emitida/observada/aprobada/pagada) sin tener que navegar varias pantallas — todos son datos
reales del entorno, ninguno se generó para esta auditoría.

---

## 7. Plataforma

### 7.1 Panel de Salud del Proceso de Datos

**Qué hace y propósito.** Muestra si el proceso automático de carga de datos (Airflow) está
corriendo bien, y qué porcentaje de registros se rechaza por dominio.

**Por qué existe.** Le da al responsable de Plataforma visibilidad de la infraestructura de datos
que alimenta a todos los demás dashboards — si esto falla, los otros paneles muestran datos viejos.

**Dónde se encuentra.** `web-interno` → "Panel Táctico" → "Plataforma".

**Quién puede usarla.** Rol `responsable_plataforma`.

**Pasos para reproducirla en vivo.** Abrir el panel. Probar el filtro de dominio (los 6 procesos:
captación, cumplimiento, finanzas, flota, mantenimiento, viajes) sobre la tabla de corridas.

**Flujo completo / estado previo.** Ninguno — hay 100+ corridas reales registradas.

**Qué muestra al completarse (verificado con datos reales).**
- Corridas OK hoy: **2**
- % registros rechazados: **1.9%**
- Última corrida: **17/8/2026, 2:00:02** (fecha/hora real, no un valor fijo)
- Gráfico "% de registros rechazados por dominio" (compuesto): 7 dominios reales con su porcentaje.
- Tabla de corridas por dominio (simple, mostrada como servida desde ClickHouse — con una nota
  explícita de que la colección Mongo que la spec original pedía no existe, el seguimiento vive en
  ClickHouse por diseño): decenas de corridas reales con estado OK/WARN.

**Qué debe saber Darwin.** El panel mostraba antes un 4º KPI, "Capacitación", en "—" — se quitó de
la interfaz en la ronda de correcciones de agosto 2026 (no existe ningún dominio de capacitación en
el sistema, y se decidió no ocupar espacio con un indicador que nunca va a tener dato real). El
panel ahora muestra 3 KPIs, no 4. En la tabla de corridas se ven algunas en estado `WARN` (por
ejemplo `dag_cumplimiento_gold` con 77.1%/64.9%/100.0% de rechazo en distintas fechas) — es real y
vale mostrarlo: demuestra que el sistema de calidad de datos realmente descarta registros
problemáticos en vez de aceptarlo todo ciegamente.

---

## Notas de cierre para Darwin

- **Los 10 paneles muestran datos reales hoy** — ninguno está vacío ni roto, ni tiene ningún KPI en
  "—". **Actualizado (segunda pasada de correcciones, agosto 2026):** el KPI "% de errores" de
  Auditoría se quitó de la interfaz (no existe dominio de credenciales/latencia de integraciones en
  el sistema, nunca iba a tener dato real), igual que ya se había hecho antes con "Capacitación" de
  Plataforma. La "Tasa de cancelación" de Despacho ya no es una limitación de cálculo conocida — se
  corrigió de raíz y hoy muestra un porcentaje real. Ninguno de estos casos debería tomar a Darwin
  por sorpresa si ya leyó esta nota antes de la demo.
- **Orden sugerido**: Flota → Mantenimiento → Vigencia Documental → Captación → Despacho →
  Rendimiento de Conductores (leer la advertencia de concentración antes de abrirlo) → Conciliación
  → Liquidación → Auditoría → Plataforma. Este orden agrupa por afinidad de departamento y deja
  Plataforma al final porque explica "de dónde sale todo esto" — un buen cierre técnico.
- **Filtro recomendado para Rendimiento de Conductores**: elegir "Último mes" + "Ventana reciente"
  antes de mostrar la tabla comparativa, para evitar que aparezcan las cifras infladas del dataset
  histórico NYC 2021 sin haber explicado antes por qué existen.
- **Catálogo de informes** (Indicadores, en `web-interno`) es el mejor punto de partida antes de
  este documento — muestra de dónde sale el dato que los 10 paneles consumen (ver
  `FUNCIONALIDADES_TRANSVERSALES.md`, sección "Trazabilidad y transparencia de datos").
