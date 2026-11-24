# Funcionalidades transversales

## Qué es este documento y por qué existe aparte

Lo que sigue **no son procesos de negocio de la cooperativa de taxis** — ningún socio, pasajero ni
departamento existe para "generar bitácora" o "administrar catálogos". Son la **plataforma que
sostiene a los tres niveles organizacionales** (operativo, táctico, estratégico): trazabilidad,
seguridad, configuración y autoservicio. Un sistema serio necesita esta capa para funcionar en
producción — tenerla construida y funcionando es un mérito real del proyecto, no relleno ni
"funcionalidad de más" para completar un documento.

Mismo estándar de verificación que los otros 3 documentos: cada entrada fue ejecutada personalmente
en el navegador, contra el stack real, con datos reales. La sección de **Administración del
Sistema** en particular se **re-verificó en vivo en esta misma ronda** con la cuenta real
`admin_sistema` — en el entregable anterior se había remitido a evidencia de una sesión previa
(`CLAUDE.md` §9) sin volver a probarla, lo cual no cumplía el estándar propio de esta auditoría.
Ahora sí, los 8 módulos se abrieron uno por uno en esta sesión.

Mismo formato de 9 campos por entrada que en los otros 3 documentos.

---

## 1. Trazabilidad y transparencia de datos

### 1.1 Bitácora de auditoría

**Qué hace y propósito.** Registro cronológico de absolutamente todas las acciones relevantes del
sistema: quién hizo qué, cuándo, sobre qué entidad, y si el sistema lo permitió o lo denegó.

**Por qué existe.** Trazabilidad y rendición de cuentas — cualquier acción de negocio, en
cualquiera de los 3 niveles, debe poder reconstruirse después. Es infraestructura que ningún
departamento "pide" directamente, pero que todos necesitan que exista.

**Dónde se encuentra.** Dos vistas sobre el mismo dato, con propósitos distintos:
- `web-interno` → "Cumplimiento" → bloque "Bitácora de auditoría" — vista completa, todos los
  eventos del sistema (operativos y administrativos mezclados).
- `web-interno` → "Auditoría" (dentro de "Administración") → "Auditoría de cambios
  administrativos" — la misma colección, filtrada solo a las acciones que ocurren dentro de los
  módulos de Administración del Sistema (cuentas, roles, políticas, catálogos, funcionalidades
  activables), sin mezclarlas con los miles de eventos operativos del día a día.

**Quién puede usarla.** La vista completa: rol `supervisor_cumplimiento`. La vista administrativa
filtrada: rol `admin_sistema`.

**Pasos para reproducirla en vivo.** Abrir cualquiera de las 2 pantallas — ya están pobladas.
Filtrar por actor, entidad, acción o resultado (Todos/OK/Denegado/Error en la vista completa;
Todas las administrativas + una lista de 28 acciones específicas en la vista filtrada).

**Flujo completo / estado previo.** Ninguno — crece con cualquier acción que se haga en cualquier
parte del sistema. Confirmado en esta sesión con **3,600 eventos reales** en la vista completa y
**148 eventos administrativos reales** en la vista filtrada.

**Qué muestra al completarse.** Fecha, actor, rol, acción, entidad afectada y resultado de cada
evento. La vista administrativa además ofrece "Ver antes/después" en varios eventos — el valor
exacto del campo antes y después del cambio, no solo que "algo cambió".

**Qué debe saber Darwin.** Es un excelente cierre de cualquier bloque de demo: después de ejecutar
cualquier funcionalidad de los 3 niveles, volver a esta pantalla y mostrar el evento recién
generado — hace tangible que el sistema realmente registra todo, no es una promesa vacía. La vista
administrativa filtrada **no es un segundo registro** — es la misma bitácora, solo enfocada; el
propio sistema lo aclara en pantalla, evita mostrarla como si fuera una fuente de datos distinta.

---

### 1.2 Catálogo de informes publicados

**Qué hace y propósito.** Muestra, en un solo lugar, todos los informes que el proceso automático
de carga de datos (Airflow) ya publicó — cada uno con su fecha de datos y hora de última
actualización.

**Por qué existe.** Es la vitrina de todo lo que alimenta después a los dashboards tácticos y
estratégicos — permite confirmar de un vistazo que el proceso de datos sigue vivo y actualizado.
No es en sí un proceso de negocio de la cooperativa: es la infraestructura de datos que hace
posibles los otros dos niveles.

**Dónde se encuentra.** `web-interno` → sección "Indicadores".

**Quién puede usarla.** Rol `responsable_plataforma`.

**Pasos para reproducirla en vivo.** Abrir "Indicadores" — no requiere ninguna acción, la lista se
carga sola.

**Flujo completo / estado previo.** Ninguno — siempre tiene contenido mientras el proceso de datos
haya corrido al menos una vez (ya corrió muchas veces en este entorno).

**Qué muestra al completarse.** Cada informe publicado (% de flota activa por franja, tasa de
discrepancias, margen de comisión, conversión de onboarding, documentación vigente por tipo, uso de
integraciones por endpoint, entre otros) con su fecha de datos y hora exacta de la última
actualización — confirmado con 7 informes reales, todos con datos frescos del mismo día.

**Qué debe saber Darwin.** Si la corrida de hoy de un dominio falla, el catálogo sigue mostrando la
última versión buena con un aviso de retraso — nunca un informe a medio publicar. Es una buena
antesala antes de mostrar los dashboards tácticos/estratégicos, porque explica de dónde sale el
dato que esos paneles consumen — considerar abrirlo justo antes de pasar de Operativo a Táctico en
la presentación.

---

## 2. Notificaciones

### 2.1 Centro de notificaciones in-app

**Qué hace y propósito.** Campana con contador de no leídas (ícono SVG real, no el emoji 🔔 que
tenía hasta esta ronda) + una sección propia "Notificaciones" en el sidebar de los 3 portales, con
listado completo, filtros (tipo/estado/rango de fecha), detalle y acción rápida por tipo.

**Por qué existe.** Mantiene informado a cada usuario de eventos relevantes de su propio rol sin
depender de un canal externo — es infraestructura de comunicación interna, no una operación de
ningún departamento en particular.

**Dónde se encuentra.** Los 3 portales: ícono de campana en el encabezado (últimas 20, con "Ver
todas") + sección "Notificaciones" en el sidebar, grupo "Mi cuenta" (el contador se ve en los 2
lugares a la vez, mismo número).

**Quién puede usarla.** Cualquier usuario autenticado, en cualquiera de los 3 niveles.

**Pasos para reproducirla en vivo.** Generar cualquier evento que dispare una notificación (por
ejemplo, crear una orden de mantenimiento sobre el vehículo de un conductor logueado en otra
pestaña — ver la sección de Mantenimiento del documento Operativo) → la campana y el sidebar
muestran el contador → abrir la sección completa → filtrar por tipo/estado/fecha si hace falta →
abrir el detalle (se marca como leída automáticamente, o con el botón "Marcar leída" sin abrirlo) →
si el tipo tiene una pantalla de destino real, un botón de acción rápida lleva directo ahí (ej.
"Nueva solicitud de conductor" → Solicitudes; "Posible salto de posición GPS" → Auditoría).

**Flujo completo / estado previo.** Depende de qué notificación se quiera mostrar — la más fácil de
producir en vivo es cualquier acción de negocio de los documentos Operativo/Táctico/Estratégico, ya
que casi todas disparan una notificación a algún rol relacionado.

**Qué muestra al completarse.** El contador baja de forma consistente en campana y sidebar al
marcar como leída, sin necesidad de recargar la página.

**Qué debe saber Darwin.** Las categorías de notificación push (captación, cumplimiento,
mantenimiento, viaje) se pueden activar/desactivar por separado en Ajustes — la de seguridad nunca
es desactivable. No confundir con "Configuración de alertas" (Módulo 6.3, sección 4.6 de este
documento, renombrada en esta ronda para no compartir la etiqueta "Notificaciones" con esta
sección) — esa es la configuración administrativa de a quién le llega cada tipo de alerta; esta es
la bandeja donde el usuario final la recibe. No todos los tipos tienen acción rápida: el conductor
recibe 6 tipos (documentos, órdenes de mantenimiento, decisión de su postulación) sin ninguna
pantalla propia donde verlos en detalle en este portal — quedan como informativos, sin destino
fabricado.

---

## 3. Autoservicio del usuario

### 3.1 Perfil propio, foto y ajustes personales

**Qué hace y propósito.** Cada usuario puede ver y editar sus propios datos de contacto, subir/
cambiar su foto de perfil, revisar y cerrar sus sesiones activas en otros dispositivos, y
personalizar la apariencia (tema claro/oscuro, y en `web-interno` la densidad de las tablas) más un
centro de ayuda con preguntas frecuentes y contacto.

**Por qué existe.** Autoservicio básico — nadie debería depender de un administrador para corregir
su propio teléfono, subir una foto o cambiar el tema. Es soporte al uso diario, no una operación de
negocio de ningún departamento.

**Dónde se encuentra.** Los 3 portales: "Mi perfil" (pasajero/conductor) o "Mi cuenta"
(`web-interno`, visible para cualquiera de los 13 roles); "Ajustes" y "Ayuda" como secciones
aparte.

**Quién puede usarla.** Cualquier usuario autenticado, sobre su propia cuenta.

**Pasos para reproducirla en vivo.**
- Perfil: "Mi perfil"/"Mi cuenta" → editar teléfono/correo (pide la contraseña actual para
  confirmar, no hay OTP en este sistema) → o clic en el avatar → "Cambiar foto" → subir una imagen.
  La foto nueva se refleja de inmediato en el encabezado y en cualquier otro lugar donde ya se
  mostraba el avatar (historial de viajes, gestión de usuarios, etc.).
- Ajustes: cambiar tema o densidad de tablas — el cambio se aplica de inmediato, sin recargar, y
  persiste al navegar entre secciones.

**Flujo completo / estado previo.** Ninguno.

**Qué muestra al completarse.** Los datos/foto/tema actualizados, reflejados en todo el sistema sin
recargar la página.

**Qué debe saber Darwin.** Un usuario nunca puede cambiar su propio rol desde esta pantalla. El
contacto del Centro de ayuda usa datos de placeholder (`soporte@urbanfleet.example`) — es una
decisión permanente y consciente (proyecto académico, sin cooperativa real detrás), no un dato
pendiente de completar.

---

## 4. Administración del Sistema

Ocho módulos, exclusivos del rol `admin_sistema` (uno de los 13 roles del sistema, separado a
propósito de `admin_plataforma` por principio de mínimo privilegio) salvo donde se indique. **Los 8
se re-verificaron en vivo en esta ronda**, con la cuenta real `admin_sistema`
(+593900000099 / `AdminSistema123!`), no solo citados de una sesión anterior.

### 4.1 Gestión de identidades y accesos (IAM)

**Qué hace y propósito.** Administra las cuentas de todo el sistema (personal interno, conductores
y pasajeros): consultarlas, suspenderlas/reactivarlas, darlas de baja, cerrar sus sesiones activas
a distancia; y define la política de contraseñas y bloqueo por intentos fallidos que rige a todo
el sistema.

**Por qué existe.** Gobierno de acceso — sin esto no hay forma centralizada de revocar el acceso de
alguien, ni de endurecer la seguridad de contraseñas de todos a la vez.

**Dónde se encuentra.** `web-interno` → "Administración" → "Usuarios" y "Políticas de
autenticación".

**Quién puede usarla.** Rol `admin_sistema`.

**Pasos para reproducirla en vivo.** "Usuarios": buscar por rol/estado/nombre, abrir el detalle de
cualquier cuenta. "Políticas de autenticación": "Editar" (los campos están bloqueados hasta pulsar
esto, para evitar un cambio accidental en configuración crítica) → ajustar longitud mínima de
contraseña, umbral de intentos fallidos, ventana de conteo, duración del bloqueo → "Publicar
política" (o "Cancelar" para salir sin cambiar nada).

**Flujo completo / estado previo.** Ninguno — confirmado con **226 cuentas reales** en el listado
de Usuarios (personal interno + conductores + pasajeros), y una política de autenticación real
publicada desde el 7/8/2026.

**Qué muestra al completarse.** El listado filtrable de cuentas con nombre, contacto, roles y
estado; la política vigente con su fecha de publicación real.

**Qué debe saber Darwin. No crear conductores/pasajeros a mano desde aquí** — el propio sistema lo
explica en pantalla: "crear uno a mano saltaría el flujo de verificación documental" (ver la
sección de Captación del documento Operativo, que sí es el camino real). Un cambio de política
aquí afecta de inmediato a todo el sistema (pasajeros, conductores y personal interno) — no
publicar en vivo salvo que se quiera demostrar el efecto real.

---

### 4.2 Configuración general del sistema

**Qué hace y propósito.** Parámetros globales que gobiernan el comportamiento operativo (radios de
despacho para CU-O05, expiración de oferta a conductor, idioma, zona horaria) y funcionalidades
activables por porcentaje de usuarios o por rol, sin desplegar código nuevo.

**Por qué existe.** Permite ajustar comportamiento crítico del sistema (como el radio de búsqueda
de conductor) sin tocar código ni redesplegar — y probar una función nueva con una fracción de
usuarios antes de activarla para todos.

**Dónde se encuentra.** `web-interno` → "Administración" → "Parámetros globales" y
"Funcionalidades".

**Quién puede usarla.** Rol `admin_sistema`.

**Pasos para reproducirla en vivo.** "Parámetros globales": mismo patrón de "Editar" bloqueado por
defecto. "Funcionalidades": ver el listado de flags existentes con su estado, porcentaje y roles.

**Flujo completo / estado previo.** Ninguno — confirmado con parámetros reales publicados desde el
7/8/2026, y 2 funcionalidades activables reales en el listado (`pago_electronico` al 30% para
Pasajero/Conductor, y una de prueba al 20%).

**Qué muestra al completarse.** Los valores vigentes de cada parámetro; el listado de
funcionalidades con su estado real.

**Qué debe saber Darwin.** Cambiar los radios de despacho afecta viajes nuevos de inmediato — no
hay ventana de gracia, según lo advierte la propia pantalla. Las funcionalidades activables
gobiernan visibilidad, nunca reemplazan un control de acceso real (RBAC sigue siendo la autoridad).

---

### 4.3 Catálogos y parámetros de negocio

**Qué hace y propósito.** Administra las tablas de referencia que antes vivían fijas en código o
como texto libre sin validación: zonas de despacho, tipos de documento exigidos, motivos de
cancelación/incidencia, talleres, marcas y colores de vehículo, y repuestos.

**Por qué existe.** Evita que un motivo de cancelación o un taller nuevo requieran un cambio de
código — cualquier `admin_sistema` puede agregarlo desde la UI.

**Dónde se encuentra.** `web-interno` → "Administración" → "Catálogos" (7 pestañas internas).

**Quién puede usarla.** Rol `admin_sistema`.

**Pasos para reproducirla en vivo.** Abrir cualquiera de las 7 pestañas — la mayoría ya tiene datos
reales.

**Flujo completo / estado previo.** Ninguno. Confirmado con **5 talleres reales** (Lubricadora
Express, Servicio Rápido Quevedo, Taller Central, Taller El Motor, Taller Norte).

**Qué muestra al completarse.** El listado de cada catálogo, activo/inactivo.

**Qué debe saber Darwin.** La pestaña "Zonas" está vacía en este entorno ("No hay zonas creadas
todavía") — es consistente con el gap de zona ya declarado en varios paneles tácticos/estratégicos
(el sistema nunca resuelve `zona_origen_id`/`zona_destino_id` de un viaje), no es un error de esta
pantalla en particular.

---

### 4.4 Integraciones externas

**Qué hace y propósito.** Gestiona credenciales para consumidores externos del sistema, y el
estado/rotación de los servicios externos que el propio sistema consume (hoy, solo Google Maps
tiene integración real).

**Por qué existe.** Permite rotar una clave comprometida sin tocar variables de entorno ni
redesplegar, y llevar control de quién tiene acceso externo al sistema.

**Dónde se encuentra.** `web-interno` → "Administración" → "Integraciones" (pestañas
"Credenciales" y "Servicios externos").

**Quién puede usarla.** Rol `admin_sistema`.

**Pasos para reproducirla en vivo.** "Servicios externos": ver el estado real de Google Maps
(ACTIVO, clave enmascarada) vs. SMS/S3 (NO CONFIGURADO). "Credenciales": ver/crear credenciales
para consumidores externos.

**Flujo completo / estado previo.** Ninguno. Confirmado con Google Maps real activo (clave
enmascarada `••••8qDM`) y una credencial de prueba real (revocada).

**Qué muestra al completarse.** Estado real de cada servicio; listado de credenciales con su
alcance, usos y estado.

**Qué debe saber Darwin.** SMS y S3 se muestran siempre como "No configurado" — es honesto, el
sistema no tiene integración real con ninguno de los dos todavía, se listan como referencia de la
arquitectura prevista, no como una carencia oculta.

---

### 4.5 Monitoreo de infraestructura

**Qué hace y propósito.** Estado de salud de la infraestructura (backend, MongoDB, Redis,
ClickHouse, Airflow) evaluado bajo demanda, con umbrales configurables que colorean cada tarjeta, e
indicadores adicionales reales por motor (conexiones activas, memoria, % de aciertos de caché).

**Por qué existe.** Da visibilidad operativa de si el sistema está sano, sin depender de entrar a
cada contenedor por separado.

**Dónde se encuentra.** `web-interno` → "Administración" → "Monitoreo".

**Quién puede usarla.** Rol `admin_sistema`.

**Pasos para reproducirla en vivo.** Abrir "Monitoreo" — se auto-actualiza cada 20 segundos (se
puede pausar). Ver los 5 componentes con su latencia real y las 6 métricas adicionales por motor.

**Flujo completo / estado previo.** Ninguno. Confirmado en vivo con valores reales medidos en el
momento: Backend 0 ms, MongoDB 9 ms, Redis 9.1 ms, ClickHouse 18.8 ms, y **Airflow "No disponible"**
(reflejo real del estado del contenedor en ese instante — evidencia de que el chequeo pinga la
infraestructura real, no un valor fijo simulado).

**Qué muestra al completarse.** Tarjetas por componente con latencia y color según el umbral
configurado; tabla de umbrales editable; tendencia de latencia de la última hora.

**Qué debe saber Darwin.** Es evaluación bajo demanda, no vigilancia continua — no hay alerta push
automática si algo se degrada entre consultas, es una decisión de alcance ya declarada (no hay
worker/cron apto en este stack sin agregar infraestructura nueva). Si Airflow aparece "No
disponible" en la demo, no es un error del panel — confirma que el chequeo es real; solo indica que
ese contenedor específico tardó en responder o no estaba listo en ese instante.

---

### 4.6 Políticas de seguridad y alertas del sistema

**Qué hace y propósito.** Gobierna la vida útil de los tokens de sesión (access/refresh) y los
umbrales de 2 mecanismos de bloqueo (refrescar sesión, denegaciones de permisos repetidas — el
bloqueo por login incorrecto se configura aparte, en Políticas de autenticación); y administra a
qué rol le llega cada tipo de alerta que el sistema ya genera (denegaciones repetidas, posible GPS
spoofing, corrida de datos fallida, falla de vehículo reportada, incidencia operativa en curso).

**Por qué existe.** Control de la superficie de exposición de sesiones activas, y aseguramiento de
que las alertas de seguridad/operación lleguen a quien debe actuar sobre ellas.

**Dónde se encuentra.** `web-interno` → "Administración" → "Políticas de seguridad" y
"Configuración de alertas" (renombrada en la ronda del Centro de notificaciones -- antes
compartía la etiqueta "Notificaciones" con la sección personal de la bandeja, sección 2.1).

**Quién puede usarla.** Rol `admin_sistema`.

**Pasos para reproducirla en vivo.** "Políticas de seguridad": mismo patrón de "Editar" bloqueado
por defecto — confirmado real, publicada desde el 7/8/2026. "Configuración de alertas": listado de las 5
alertas reales con su rol destinatario por defecto y destinatarios adicionales.

**Flujo completo / estado previo.** Ninguno. Confirmado con las 5 alertas reales del sistema,
todas `ACTIVA`, una con un destinatario adicional real agregado.

**Qué muestra al completarse.** Los valores vigentes de la política; el listado de alertas con su
configuración real.

**Qué debe saber Darwin.** El único canal con entrega real hoy es Web Push (no hay envío de
correo en el sistema) — lo dice la propia pantalla. Desactivar una alerta queda registrado en la
bitácora, nunca es una acción silenciosa. No confundir con el "Centro de notificaciones in-app"
(sección 2.1) — esta pantalla configura el enrutamiento administrativo, no es donde el usuario
final las recibe.

---

### 4.7 Respaldos y continuidad

**Qué hace y propósito.** Respaldo y restauración de prueba de MongoDB y ClickHouse, más el plan de
recuperación ante desastres (RTO/RPO por dominio) y registro de simulacros.

**Por qué existe.** Ningún sistema en producción real puede operar sin un plan de respaldo
verificado — esto demuestra que existe y que se probó, no solo que está documentado en un papel.

**Dónde se encuentra.** `web-interno` → "Administración" → "Respaldos" (pestañas "Respaldos" y
"Plan de continuidad").

**Quién puede usarla.** Rol `admin_sistema`.

**Pasos para reproducirla en vivo.** Ver el historial real de respaldos y restauraciones de
prueba ya ejecutados — no hace falta disparar uno nuevo en vivo para demostrar que funciona.

**Flujo completo / estado previo.** Ninguno. Confirmado con **4 respaldos reales completos** de
MongoDB (hasta 2312.9 MB, ~87-150s de duración) y ClickHouse, y **2 restauraciones de prueba
reales** con conteos exactos por colección/tabla (por ejemplo, `viajes: 1,334,886`,
`pagos: 1,241,750` en la restauración de Mongo).

**Qué muestra al completarse.** Historial de respaldos con motor, estado, duración y tamaño real;
conteos reales de la restauración de prueba, tabla por tabla.

**Qué debe saber Darwin. No disparar un respaldo nuevo en vivo durante la demo** — corre contra las
bases reales de este entorno de desarrollo y tarda más de un minuto; el historial ya real es
suficiente para demostrar que la funcionalidad existe y funciona. Cifrado en reposo: no
implementado en este entorno, declarado así explícitamente. El RTO/RPO por dominio está en blanco
para los 7 dominios (editable, pero nunca se llenó) — decirlo así si se pregunta, es un campo real
sin valor asignado, no un error de carga.

---

### 4.8 Gobernanza de datos

**Qué hace y propósito.** Anonimización irreversible de una cuenta (derechos ARCO/LOPDP) con doble
confirmación, y consulta de la política de retención vigente por tipo de dato (con el TTL real leído
del índice de la base de datos donde aplica).

**Por qué existe.** Cumplimiento de derechos de privacidad — un usuario puede pedir que sus datos
personales se eliminen, y el sistema necesita un mecanismo controlado (no un `DELETE` directo en la
base) para hacerlo sin perder la trazabilidad de auditoría.

**Dónde se encuentra.** `web-interno` → "Administración" → "Gobernanza de datos".

**Quién puede usarla.** Rol `admin_sistema`.

**Pasos para reproducirla en vivo.** Buscar una cuenta por nombre/teléfono/correo → botón
"Anonimizar" → se abre un diálogo que exige escribir la palabra "ANONIMIZAR" para confirmar (no
basta un clic) — verificado en vivo hasta este punto: la búsqueda encontró cuentas reales, el
diálogo se abrió con los datos reales de la cuenta y la advertencia completa de irreversibilidad.

**Flujo completo / estado previo.** Ninguno para llegar hasta la confirmación. **No se completó la
acción real de anonimizar en esta verificación** — es una acción irreversible sobre datos del
entorno, y el propio flujo de trabajo de esta auditoría la bloqueó como medida de seguridad
correcta; se confirma real hasta el punto de la doble confirmación, mecanismo suficiente para
demostrarlo en vivo sin ejecutar la purga real durante la demo tampoco.

**Qué muestra al completarse (si se ejecuta).** El nombre, teléfono y correo reales se sustituyen
por un seudónimo, de forma permanente — los eventos de bitácora ya escritos con esa cuenta se
conservan (usan un id interno, nunca el nombre), y el propio evento de anonimización queda
registrado sin exponer el dato purgado.

**Qué debe saber Darwin.** No ejecutar esta acción en vivo durante la demo salvo sobre una cuenta
de prueba desechable creada para ese único propósito — es irreversible. La política de retención es
de solo lectura y mezcla 2 fuentes reales: `posiciones` con un TTL real de 7 días (leído del índice
de Mongo, no un texto escrito a mano) y el resto de colecciones documentadas sin purga automática
(retención indefinida por requisito contable/de auditoría).

---

## Notas de cierre para Darwin

- **Orden sugerido si se dedica un bloque aparte a este documento**: Bitácora + Catálogo de
  informes (para explicar "de dónde sale todo lo que ya viste") → Autoservicio (rápido, cualquiera
  lo reconoce) → Administración del Sistema, con la cuenta `admin_sistema`
  (+593900000099 / `AdminSistema123!`) — recomendado dedicarle 10-15 minutos aparte al final de la
  presentación completa, es un bloque grande (8 módulos) que no encaja limpio en ningún nivel
  organizacional específico.
- **No ejecutar en vivo durante la demo**: publicar un cambio real de política de seguridad/
  autenticación/parámetros globales (afecta todo el sistema de inmediato), disparar un respaldo
  nuevo (tarda minutos), ni completar una anonimización real (irreversible). Todos estos mecanismos
  se confirmaron reales hasta el punto justo antes de la acción irreversible/de alto impacto.
- **Re-verificación de esta ronda**: a diferencia de la Administración del Sistema del documento
  Operativo anterior (que remitía a `CLAUDE.md` §9 sin volver a probarla), los 8 módulos de la
  sección 4 de este documento se abrieron en vivo en esta sesión, con la cuenta real, confirmando
  datos reales en cada uno — cumpliendo el mismo estándar de verificación que el resto de la
  auditoría.
