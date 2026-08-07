# Especificación — Administración del Sistema

Paquete propuesto: `pkg-admin-sistema` · Nivel: transversal (no es un caso de uso operativo, táctico ni
estratégico de negocio — es infraestructura de gobierno del sistema mismo) · Rol: `admin_sistema`
(nuevo, distinto de `admin_plataforma`, ver nota de alcance de roles al final)

## 0. Marco de análisis

Esta especificación cubre lo que UrbanFleet necesita para operar, protegerse y mantenerse a sí
misma como software — no la operación de la cooperativa (eso ya está cubierto en
`specs/nivel-operativo/` y `specs/nivel-tactico/`). Se organiza en **8 módulos**. Cada responsabilidad
sigue el mismo formato: objetivo, funciones específicas, beneficio, módulo/sección de implementación,
y consideraciones de seguridad.

Se agregaron 3 responsabilidades no listadas en el pedido original, justificadas en su sección:
**Feature flags** (Módulo 2), **auditoría de acciones administrativas** (Módulo 6, distinta de la
bitácora operativa que ya existe), y **gobernanza de datos y cumplimiento normativo** (Módulo 8, que
resuelve un pendiente ya identificado en el proyecto: la anonimización LOPDP de CU-O17 A2).

Regla transversal de diseño: **ninguna acción administrativa debe evitar la bitácora de auditoría ya
existente** (`CU-O17`). Todo lo que se describe aquí se apoya en esa infraestructura — no la
reemplaza ni crea un segundo sistema de registro paralelo.

---

## Módulo 1 — Gestión de Usuarios y Control de Acceso (IAM)

Es el módulo de mayor criticidad de seguridad: un error aquí compromete todo lo demás. Se apoya
directamente en el catálogo de roles y el middleware de autorización que ya definen
`operativo_cumplimiento.md` (CU-O18).

### 1.1. Administración de cuentas de usuario

- **Objetivo:** dar al Administrador del Sistema control total sobre el ciclo de vida de cualquier
  cuenta, sin necesidad de manipular la base de datos directamente.
- **Funciones específicas:**
  - Crear cuentas de personal interno (los roles operativos como `admin_captacion`,
    `coordinador_flota`, etc. — no las de pasajero/conductor, que se autorregistran).
  - Editar datos de contacto y forzar el cambio de contraseña en el siguiente inicio de sesión.
  - Suspender una cuenta (bloqueo temporal, reversible) y darla de baja (revocación permanente).
  - Ver el historial de accesos de una cuenta específica.
- **Beneficio:** permite reaccionar de inmediato ante una cuenta comprometida o un empleado que deja
  la cooperativa, sin depender de una intervención técnica de backend.
- **Módulo/sección:** `web-interno` → "Administración → Usuarios".
- **Seguridad y buenas prácticas:** la suspensión debe invalidar de inmediato cualquier sesión activa
  de esa cuenta (no esperar a la expiración natural del token); toda acción de este módulo se
  registra en la bitácora (CU-O17) con el actor administrador, no solo el usuario afectado.

### 1.2. Asignación de roles y permisos (RBAC)

- **Objetivo:** administrar qué rol tiene cada cuenta interna, sin tocar código.
- **Funciones específicas:**
  - Asignar o revocar uno o más roles a una cuenta (el sistema ya soporta roles combinados, como se
    vio con `staff-verificacion`).
  - Consultar la matriz de permisos vigente por rol (qué endpoints/acciones puede ejecutar cada uno).
  - Crear roles compuestos para necesidades de prueba o casos especiales, sin crear un rol nuevo en
    código cada vez.
- **Beneficio:** evita que cambios de estructura organizacional (alguien asume dos funciones) requieran
  un despliegue de software.
- **Módulo/sección:** `web-interno` → "Administración → Usuarios → Roles".
- **Seguridad:** la resolución de permisos ya es por consulta al perfil en cada petición (CU-O18 A3),
  no embebida en el token — este módulo no cambia esa garantía, solo administra el dato que esa
  consulta lee. Cualquier cambio de rol se audita con el rol anterior y el nuevo.

### 1.3. Políticas de autenticación y contraseñas

- **Objetivo:** definir y hacer cumplir reglas de contraseña y de bloqueo por intentos fallidos,
  configurables sin cambiar código — hoy están fijas en el backend (longitud mínima, rate limiting).
- **Funciones específicas:**
  - Configurar longitud mínima y complejidad de contraseña.
  - Configurar el umbral de intentos fallidos antes de bloquear una cuenta (CU-O18 A4 ya define "cinco
    denegaciones en 10 minutos" como valor fijo; este módulo lo vuelve un parámetro).
  - Forzar el vencimiento periódico de contraseña para roles de alto privilegio, si la junta lo exige.
- **Beneficio:** permite ajustar la postura de seguridad sin depender de un despliegue de backend.
- **Módulo/sección:** `web-interno` → "Administración → Seguridad → Políticas de autenticación".
- **Seguridad:** cualquier relajación de una política (por ejemplo, bajar el umbral de bloqueo) debe
  quedar auditada con el motivo — es el tipo de cambio que un auditor externo revisa primero.

### 1.4. Gestión de sesiones activas y dispositivos autorizados

- **Objetivo:** dar visibilidad y control sobre quién tiene una sesión abierta ahora mismo.
- **Funciones específicas:**
  - Listar sesiones activas por usuario (dispositivo, IP, hora de inicio).
  - Cerrar remotamente una sesión específica (útil si un conductor pierde su teléfono).
  - Ver el historial de intentos de inicio de sesión fallidos por cuenta.
- **Beneficio:** reduce el tiempo de respuesta ante un dispositivo perdido o robado — hoy no hay forma
  de invalidar una sesión sin cambiar la contraseña de raíz.
- **Módulo/sección:** `web-interno` → "Administración → Seguridad → Sesiones".
- **Seguridad:** requiere que el backend registre sesiones activas de forma consultable (hoy JWT es
  stateless; esto implica sostener una lista de revocación o sesiones en Redis, ya presente en la
  arquitectura para otros fines).

---

## Módulo 2 — Configuración General del Sistema

### 2.1. Parámetros globales de la aplicación

- **Objetivo:** centralizar valores que hoy podrían estar dispersos o cableados en código (idioma,
  zona horaria de operación, formatos de fecha/moneda, límites operativos como el radio de despacho).
- **Funciones específicas:**
  - Editar parámetros versionados con fecha de vigencia (mismo patrón ya usado para tarifas y
    comisión en `PARAMETRO_TARIFA`/`PARAMETRO_COMISION`).
  - Configurar límites operativos: radio inicial de despacho, número máximo de radios de ampliación,
    tiempo de expiración de una oferta a conductor (hoy fijos en 300m/3 radios/20s).
  - Ver el historial de cambios de cada parámetro.
- **Beneficio:** permite calibrar el comportamiento del despacho automático (por ejemplo, ampliar el
  radio inicial en zonas de baja densidad de conductores) sin desplegar código nuevo.
- **Módulo/sección:** `web-interno` → "Administración → Configuración → Parámetros globales".
- **Seguridad:** todo parámetro de negocio crítico (tarifa, comisión, radios de despacho) requiere
  doble confirmación y queda con vigencia futura, nunca retroactiva — mismo principio que ya rige
  `PARAMETRO_TARIFA`.

### 2.2. Gestión de feature flags *(agregada — no estaba en la lista original)*

- **Justificación de por qué se agrega:** el proyecto ya tiene un patrón real de "backlog consciente"
  (funcionalidades explícitamente diferidas: pago electrónico, chat, OTP, reset de contraseña). Un
  sistema de feature flags formaliza ese patrón como una capacidad del producto, permitiendo activar
  una función para un subconjunto de usuarios antes de liberarla a todos, sin un despliegue nuevo.
- **Objetivo:** activar o desactivar funcionalidades en producción sin necesidad de un nuevo
  despliegue de código.
- **Funciones específicas:**
  - Activar/desactivar una función por porcentaje de usuarios o por rol.
  - Ver qué flags están activos y desde cuándo.
- **Beneficio:** reduce el riesgo de lanzar una función nueva (como el pago electrónico, hoy en
  backlog) directamente al 100% de usuarios sin poder revertir de inmediato si falla.
- **Módulo/sección:** `web-interno` → "Administración → Configuración → Funcionalidades".
- **Seguridad:** un flag mal configurado no debe poder exponer datos de un rol a otro — los flags
  controlan visibilidad de funcionalidad, nunca deben usarse como mecanismo de autorización.

---

## Módulo 3 — Catálogos y Parámetros de Negocio

### 3.1. Gestión de catálogos y tablas maestras

- **Objetivo:** administrar los datos de referencia que ya existen en el diseño (`ZONA`, tipos de
  documento, motivos de cancelación, tipos de incidencia) sin que cada cambio requiera una migración
  de base de datos.
- **Funciones específicas:**
  - CRUD de zonas de despacho (nombre, geometría) — hoy viven en la colección `zonas`.
  - CRUD del catálogo de tipos de documento exigidos a conductores/vehículos.
  - CRUD del catálogo de motivos de cancelación e incidencia, para mantener la taxonomía consistente
    en los informes tácticos de cancelación (CU-T08).
- **Beneficio:** si la cooperativa empieza a operar en una zona nueva, o cambia su clasificación de
  motivos de cancelación, el cambio lo hace el administrador, no un desarrollador.
- **Módulo/sección:** `web-interno` → "Administración → Catálogos".
- **Seguridad:** eliminar un valor de catálogo que ya está en uso (por ejemplo, una zona con viajes
  históricos) debe bloquearse o requerir migración explícita — nunca un DELETE directo que rompa
  referencias existentes en `fact_viaje`/`viajes`.

---

## Módulo 4 — Integraciones Externas

### 4.1. Gestión de credenciales de integración externa

- **Objetivo:** cerrar un gap que el propio proyecto ya identificó: `CU-T03` (Administrar las
  integraciones externas) y `OT2.1` están definidos en las specs tácticas, pero el dominio de
  credenciales de API nunca se construyó — es la razón por la que el informe "Uso de integraciones
  por credencial y endpoint" quedó en backlog consciente en el dashboard de Auditoría.
- **Funciones específicas:**
  - Registrar una nueva credencial de integración (para el municipio/regulador que consume
    `GET /ext/v1/...`), con fecha de vigencia y alcance de datos permitido.
  - Revocar una credencial, con efecto inmediato en la siguiente petición (sin ventana de gracia, tal
    como ya exige CU-O18 A2).
  - Ver el uso de cada credencial (solicitudes, errores, latencia) — esto es precisamente el informe
    compuesto que hoy no tiene datos porque no existe el dominio que lo alimenta.
- **Beneficio:** construir esto no es solo "una función de administrador" — desbloquea un informe
  táctico que ya está diseñado y documentado, pero vacío.
- **Módulo/sección:** `web-interno` → "Administración → Integraciones".
- **Seguridad:** las credenciales nunca se muestran en texto plano después de su creación (solo al
  generarlas, una vez); se almacenan con hash, igual que una contraseña.

### 4.2. Configuración de servicios externos

- **Objetivo:** administrar la conexión a los servicios de terceros que la arquitectura ya define
  (Google Maps/Geocoding, proveedor de SMS para OTP, almacenamiento de objetos S3-compatible), sin
  que las claves vivan solo en variables de entorno inaccesibles al administrador de negocio.
- **Funciones específicas:**
  - Ver el estado de conexión de cada servicio externo (activo/con error/no configurado).
  - Rotar una API key sin reiniciar el backend.
- **Beneficio:** reduce la dependencia del equipo técnico para diagnosticar por qué, por ejemplo, la
  geocodificación dejó de funcionar.
- **Módulo/sección:** `web-interno` → "Administración → Integraciones → Servicios externos".
- **Seguridad:** las claves de servicios externos se muestran siempre enmascaradas (solo los últimos
  4 caracteres visibles), igual que un número de tarjeta.

---

## Módulo 5 — Monitoreo y Observabilidad

### 5.1. Monitoreo del estado del sistema y rendimiento

- **Objetivo:** dar visibilidad de infraestructura (no de calidad de datos, que ya cubre el dashboard
  de Plataforma) — si el backend, Mongo, ClickHouse o Redis están saludables ahora mismo.
- **Funciones específicas:**
  - Panel de estado con latencia y disponibilidad de cada componente (backend, las 3 bases, Airflow).
  - Alertas configurables por umbral (por ejemplo, latencia de API > 2s sostenida).
- **Beneficio:** detecta un problema de infraestructura (no de negocio) antes de que se traduzca en
  una mala experiencia para pasajeros o conductores.
- **Módulo/sección:** `web-interno` → "Administración → Monitoreo".
- **Seguridad:** este panel no debe exponer detalles internos (IPs, versiones exactas de software) a
  roles que no sean `admin_sistema` — es información útil para un atacante si se filtra.

---

## Módulo 6 — Auditoría y Seguridad

### 6.1. Auditoría de cambios administrativos *(matiz importante frente a lo ya existente)*

- **Justificación del matiz:** el proyecto **ya tiene** una bitácora de auditoría completa (CU-O17),
  que registra toda operación sensible de negocio. Esta responsabilidad no la duplica — es la vista
  especializada, dentro de ese mismo registro, para las acciones que ocurren *dentro de los módulos
  de este documento* (cambios de rol, cambios de parámetro global, rotación de una API key). Se
  agrega como responsabilidad explícita porque, sin ella, sería fácil asumir por error que "la
  bitácora ya cubre esto" y nunca construir una vista filtrada para ese caso específico.
- **Objetivo:** que cualquier cambio hecho desde estos módulos administrativos sea tan trazable como
  un cambio de estado de un viaje o un pago.
- **Funciones específicas:**
  - Vista filtrada de la bitácora, con foco exclusivo en acciones administrativas (no operativas).
  - Comparación de antes/después para cambios de configuración.
- **Beneficio:** en una auditoría externa, poder mostrar en segundos quién cambió qué parámetro y
  cuándo, sin mezclar ese registro con miles de eventos operativos del día a día.
- **Módulo/sección:** `web-interno` → "Administración → Auditoría".
- **Seguridad:** reutiliza `EVENTO_AUDITORIA`, ya de solo inserción — no crea un segundo almacén de
  auditoría paralelo, lo cual sería un riesgo (dos fuentes de verdad que pueden divergir).

### 6.2. Configuración de políticas de seguridad

- **Objetivo:** centralizar reglas de seguridad transversales que hoy son fijas en código (expiración
  de sesión, política de CORS, rate limiting por IP).
- **Funciones específicas:**
  - Configurar el tiempo de vida del token de sesión y del refresh token.
  - Configurar límites de tasa (rate limiting) por endpoint sensible.
- **Beneficio:** permite endurecer la postura de seguridad ante un incidente sin esperar un
  despliegue.
- **Módulo/sección:** `web-interno` → "Administración → Seguridad → Políticas".
- **Seguridad:** cambios aquí son de alto impacto — requieren el rol más restringido de todo el
  sistema y doble confirmación.

### 6.3. Gestión de alertas de seguridad y notificaciones del sistema

- **Objetivo:** administrar a quién y cómo llegan las alertas que el sistema ya genera (spoofing GPS
  detectado, cinco denegaciones consecutivas, corrida de pipeline fallida) — hoy están fijas a
  destinatarios específicos en código (Supervisor de Cumplimiento, Responsable de Plataforma).
- **Funciones específicas:**
  - Configurar el canal de entrega de cada tipo de alerta (correo, Web Push, ambos).
  - Configurar destinatarios adicionales o de respaldo por tipo de alerta.
- **Beneficio:** si el Supervisor de Cumplimiento cambia, la alerta no queda huérfana apuntando a una
  persona que ya no ocupa el cargo.
- **Módulo/sección:** `web-interno` → "Administración → Notificaciones".
- **Seguridad:** ninguna alerta de seguridad debe poder desactivarse por completo sin dejar rastro en
  la auditoría — desactivar la alerta de spoofing GPS, por ejemplo, es en sí mismo un evento sensible.

---

## Módulo 7 — Respaldos, Recuperación y Continuidad

### 7.1. Gestión de respaldos y restauración

- **Objetivo:** asegurar que la pérdida de un contenedor o volumen no signifique pérdida de datos de
  la cooperativa (viajes, pagos, liquidaciones).
- **Funciones específicas:**
  - Ver el estado y la fecha del último respaldo exitoso de MongoDB y ClickHouse.
  - Disparar un respaldo manual antes de un cambio riesgoso (por ejemplo, antes de una migración).
  - Restaurar desde un punto específico, en un entorno de prueba primero, nunca directo a producción.
- **Beneficio:** convierte la recuperación ante desastres de un proceso ad-hoc (como los que ya se
  vieron necesarios al depurar datos de prueba durante el desarrollo) en un procedimiento repetible.
- **Módulo/sección:** `web-interno` → "Administración → Respaldos".
- **Seguridad:** los respaldos de datos personales (documentos de conductores, teléfonos) deben
  cifrarse en reposo — son el mismo dato sensible que ya protege la política LOPDP de la aplicación.

### 7.2. Plan de recuperación ante desastres (DR)

- **Objetivo:** definir y probar periódicamente qué pasa si la infraestructura principal falla por
  completo, no solo un componente.
- **Funciones específicas:**
  - Documentar el tiempo objetivo de recuperación (RTO) y de pérdida de datos aceptable (RPO) por
    dominio de datos (viajes en curso vs. históricos).
  - Registrar simulacros de recuperación y sus resultados.
- **Beneficio:** para una cooperativa cuyo servicio depende de despacho automático en tiempo real, un
  plan de DR probado es la diferencia entre una interrupción de minutos y una de días.
- **Módulo/sección:** `web-interno` → "Administración → Respaldos → Plan de continuidad".
- **Seguridad:** el plan de DR en sí mismo es información sensible (revela puntos únicos de falla) —
  su acceso debe restringirse solo a `admin_sistema` y gerencia.

---

## Módulo 8 — Mantenimiento, Actualizaciones y Gobernanza de Datos

### 8.1. Aplicación de actualizaciones y parches

- **Objetivo:** dar visibilidad (no necesariamente ejecución manual) del estado de versión del
  sistema y sus dependencias críticas.
- **Funciones específicas:**
  - Ver la versión desplegada de backend y de cada frontend.
  - Ver el historial de despliegues recientes.
- **Beneficio:** ante un bug reportado, poder confirmar en segundos si ya se corrigió en la versión
  actual.
- **Módulo/sección:** `web-interno` → "Administración → Sistema → Versión".
- **Seguridad:** esta información no debe ser pública fuera del rol administrativo — revela detalles
  de la pila tecnológica útiles para un atacante.

### 8.2. Gobernanza de datos y cumplimiento normativo *(agregada — no estaba en la lista original)*

- **Justificación de por qué se agrega:** el proyecto ya reconoce una obligación legal pendiente —
  `CU-O17 A2` describe el derecho del usuario a solicitar anonimización de sus datos personales
  (derechos ARCO, LOPDP), y hoy no existe ninguna interfaz para que un administrador la ejecute; solo
  está descrita como flujo de sistema. Sin una responsabilidad explícita de gobernanza de datos, esa
  obligación legal queda sin dueño operativo.
- **Objetivo:** dar al administrador una forma real de atender solicitudes de derechos ARCO y de
  sostener las políticas de retención de datos.
- **Funciones específicas:**
  - Ejecutar la anonimización de un usuario específico (seudonimizando su identificador en la
    bitácora, tal como ya define CU-O17 A2), con confirmación explícita e irreversible.
  - Ver la política de retención vigente por tipo de dato (por ejemplo, cuánto tiempo se conservan
    las posiciones GPS crudas, que hoy ya tienen TTL de 7 días en Mongo).
- **Beneficio:** convierte una obligación legal ya reconocida en el diseño en una capacidad real y
  auditable del sistema, no solo en una nota en la especificación.
- **Módulo/sección:** `web-interno` → "Administración → Gobernanza de datos".
- **Seguridad:** la anonimización es una operación de un solo sentido — debe requerir doble
  confirmación y queda, ella misma, registrada como evento de auditoría (tal como ya exige CU-O17 A2).

---

## Análisis final — ¿módulos independientes o secciones de uno solo?

**Sí, deben ser módulos independientes**, no una sola pantalla de "Administración" con pestañas
planas, por estas razones:

1. **Separación de responsabilidad por audiencia:** no todos los módulos los usa la misma persona.
   Gestión de Usuarios y Seguridad probablemente los opera un administrador técnico; Catálogos y
   Parámetros de Negocio los podría operar gerencia o el Responsable de Plataforma sin tocar nada de
   seguridad. Tratarlos como módulos independientes permite asignar permisos de acceso distintos a
   cada uno (un `admin_sistema` limitado a catálogos, por ejemplo, sin acceso a Seguridad).

2. **Distinto ritmo de cambio:** Catálogos y Configuración General cambian con frecuencia moderada;
   Respaldos y Gobernanza de Datos se usan esporádicamente pero son de alto impacto cuando se usan.
   Mezclarlos en una sola interfaz obliga a un diseño que sirve mal a ambos casos de uso.

3. **Coincide con el patrón ya usado en el resto del proyecto:** UrbanFleet ya organiza `web-interno`
   por secciones de navegación lateral, una por dominio (Solicitudes, Mantenimiento, Cumplimiento,
   Flota, Finanzas, más los 9 paneles tácticos). Los 8 módulos de este documento deben sumarse a esa
   misma navegación bajo un grupo "Administración", no reemplazar el patrón ya establecido.

**Agrupación de navegación recomendada** (para no saturar el menú lateral con 8 entradas sueltas):

| Grupo en el menú | Módulos que contiene |
|---|---|
| Administración → Usuarios | Módulo 1 completo (cuentas, roles, políticas de auth, sesiones) |
| Administración → Configuración | Módulo 2 (parámetros globales, feature flags) + Módulo 3 (catálogos) |
| Administración → Integraciones | Módulo 4 completo |
| Administración → Seguridad y Auditoría | Módulo 6 completo |
| Administración → Monitoreo | Módulo 5 completo |
| Administración → Respaldos y Continuidad | Módulo 7 completo |
| Administración → Sistema | Módulo 8 completo |

Esto deja 7 entradas de navegación de segundo nivel bajo "Administración" — manejable, y coherente
con que Finanzas/Cumplimiento ya se dividen en más de una pantalla cuando el proceso lo justifica
(mismo criterio que ya se aplicó al dividir los dashboards tácticos de Financiero y Cumplimiento en
dos cada uno).

---

## Nota de alcance de roles

Este documento asume un rol nuevo, `admin_sistema`, **distinto** de `admin_plataforma` (que ya existe
y gestiona el pipeline de datos e indicadores tácticos, `CU-T14`/`OT8.1`). Mezclar ambos roles
concentraría permisos de seguridad de infraestructura junto con permisos de negocio de datos, lo cual
va contra el principio de mínimo privilegio ya declarado como regla del sistema en
`operativo_cumplimiento.md`. Si el alcance real del proyecto no permite un rol nuevo, la alternativa
menos mala es que `admin_plataforma` absorba estos módulos, pero debe quedar documentado como una
excepción consciente al principio de mínimo privilegio, no como el diseño ideal.
