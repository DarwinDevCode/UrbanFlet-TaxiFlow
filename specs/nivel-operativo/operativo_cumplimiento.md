# Especificación operativa — Cumplimiento Regulatorio

Paquetes: `pkg-cumplimiento`, `pkg-auditoria` · Objetivos: OP6.1 (bitácora de auditoría), OP6.2 (control de acceso por rol) · OE6

Principio de mínimo privilegio del sistema: existe un único perfil administrador de plataforma con privilegios de escritura sobre los esquemas de datos; todos los demás actores (apps, analistas, integraciones externas) operan con roles de solo lectura o con permisos acotados a las operaciones de su caso de uso. Ningún cliente escribe directamente en las bases: toda escritura pasa por la API con validación de rol.

---

## CU-O17 — Registrar un evento en la bitácora de auditoría

**Actores:** Sistema (único escritor)

**Precondiciones:** ninguna; la bitácora está siempre disponible. Si la bitácora no puede escribirse, la operación de negocio que la origina **falla** (write-ahead: primero el evento, luego el efecto).

**Flujo principal:**
1. Ante cualquier evento sensible, el sistema construye el registro con: `evento_id` secuencial, timestamp del servidor, actor (usuario o proceso), rol del actor, acción, entidad afectada e id, resultado (`OK`/`DENEGADO`/`ERROR`), IP/dispositivo de origen y datos previos/posteriores cuando la acción es una modificación.
2. Catálogo mínimo de eventos sensibles: transiciones de estado de viaje, decisiones sobre solicitudes de conductor, retiros y habilitaciones de vehículo, registros y ajustes de pago, emisión/aprobación/pago de liquidaciones, bloqueos por documentación, creación y revocación de credenciales, cambios de parámetros tarifarios y de comisión, intentos de operación denegados por rol, e inicios de sesión fallidos consecutivos.
3. El registro se persiste en almacenamiento de solo inserción: no existen operaciones de actualización ni borrado sobre la bitácora en ninguna API.
4. Los eventos con severidad de seguridad (denegaciones, spoofing GPS detectado, fallos de sesión repetidos) disparan además una alerta inmediata al Supervisor de Cumplimiento.

**Flujos alternos:**
- **A1 — Ráfaga de eventos (pico de operación):** los eventos se encolan en memoria local del servicio con reintento; el orden se garantiza por `evento_id` asignado en la recepción, no en la persistencia.
- **A2 — Solicitud de borrado de datos personales (LOPDP, derechos ARCO):** los datos personales se anonimizan en las entidades de negocio, pero los eventos de bitácora se conservan con el identificador seudonimizado; la propia anonimización queda registrada como evento.

**Postcondiciones:** evento inmutable persistido; alerta emitida si aplica.

---

## CU-O18 — Controlar el acceso por rol

**Actores:** Sistema; cualquier actor autenticado como sujeto controlado

**Precondiciones:** catálogo de roles vigente: `pasajero`, `conductor`, `admin_captacion`, `coordinador_operaciones`, `coordinador_flota`, `jefe_mantenimiento`, `admin_financiero`, `supervisor_cumplimiento`, `responsable_plataforma`, `gerencia`, `integracion_externa` (por credencial), `admin_plataforma`.

**Flujo principal:**
1. Toda petición a la API llega con un token de sesión (usuarios) o una credencial de integración (sistemas externos).
2. El middleware de autorización resuelve el rol y lo contrasta con la matriz de permisos del endpoint (verbo + recurso + condición de propiedad: un conductor solo lee *sus* viajes; un pasajero solo los *suyos*).
3. Si el permiso existe, la petición continúa; el acceso de lectura a datos personales de terceros se registra en bitácora cuando el recurso es sensible (perfiles, documentos, liquidaciones ajenas).
4. Si el permiso no existe, el sistema responde `403` con código `INSUFFICIENT_ROLE`, **sin revelar** si el recurso existe, y registra el intento (CU-O17) con actor, endpoint y condición violada.

**Flujos alternos:**
- **A1 — Token expirado:** `401` y renovación por refresh token; tres renovaciones fallidas cierran la sesión.
- **A2 — Credencial de integración revocada:** `401` definitivo con evento de bitácora; la revocación (CU-T03 «extend») surte efecto en la siguiente petición, sin ventana de gracia.
- **A3 — Cambio de rol de un usuario en caliente:** los permisos se resuelven por consulta al perfil en cada petición (no van embebidos en el token), de modo que un bloqueo o degradación aplica de inmediato.
- **A4 — Cinco denegaciones del mismo actor en 10 minutos:** el sistema suspende la sesión y alerta al Supervisor de Cumplimiento con el detalle de los intentos.

**Postcondiciones:** solo las operaciones permitidas por rol se ejecutan; todo intento denegado queda registrado; las suspensiones automáticas notificadas.

---

## Operación continua del departamento: control documental

Aunque el control de vigencia es un caso de uso táctico (CU-T10), su efecto operativo diario es automático y se especifica aquí para el equipo de desarrollo:

1. Un job diario (06:00) recorre los documentos de conductores y vehículos y clasifica: `VIGENTE`, `POR_VENCER` (≤ 30 días) y `VENCIDO`.
2. `POR_VENCER` genera notificaciones al socio a los 30, 15, 7 y 1 día del vencimiento.
3. `VENCIDO` pone la bandera de Cumplimiento del conductor o vehículo en rojo: no puede iniciar turno (flujo A5 de `operativo_flota.md`). Si está en viaje, el bloqueo aplica al finalizar el viaje, nunca en medio.
4. La carga del documento renovado por el socio la verifica el Supervisor (mismo patrón de verificación de CU-O03); al aprobarla, la bandera vuelve a verde en el acto.
