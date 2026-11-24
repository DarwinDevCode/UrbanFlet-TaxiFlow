# Especificación: Administración del Sistema (Transversal)

> Documento retroactivo. Fuente principal: `FUNCIONALIDADES_TRANSVERSALES.md` §4 (re-verificado en
> vivo en esa misma ronda con la cuenta real `admin_sistema`), verificado contra
> `backend/src/usuarios/`, `configuracion/`, `catalogos/`, `integraciones/`, `sistema/`,
> `seguridad/`, `respaldos/`. 8 módulos internos, exclusivos del rol `admin_sistema`.

## 1. Objetivo

Gobernar la plataforma técnica del sistema (identidades, configuración, catálogos, integraciones,
salud de infraestructura, políticas de seguridad, continuidad, privacidad) — separado por principio
de mínimo privilegio de `admin_plataforma` (que gobierna el pipeline de indicadores de negocio, no
la seguridad de la infraestructura).

## 2. Contexto

Un sistema en producción real necesita gobierno propio, no solo funcionalidad de negocio: alguien
tiene que poder revocar el acceso de una cuenta, rotar una clave comprometida, verificar que existe
un plan de respaldo probado, y purgar los datos de una persona que lo pide. Ningún departamento de la
cooperativa "pide" esto directamente — es infraestructura de gobierno.

## 3. Actores

- **`admin_sistema`** — único rol con acceso a los 8 módulos, sin OR-gate con ningún otro rol salvo
  el caso 7.2 (plan de continuidad, compartido con `gerencia` porque la spec real así lo pide).

## 4. Requisitos funcionales

### RF-ADM-IAM-001 — Gestión de identidades y accesos
Consultar/suspender/reactivar/dar de baja cualquier cuenta del sistema (personal interno,
conductores, pasajeros); cerrar sesiones activas a distancia; definir la política de contraseñas y
bloqueo por intentos fallidos que rige a todo el sistema.

### RF-ADM-CFG-001 — Configuración general
Parámetros globales operativos (radios de despacho, expiración de oferta, idioma, zona horaria) y
funcionalidades activables por porcentaje de usuarios o por rol, sin desplegar código nuevo.

### RF-ADM-CAT-001 — Catálogos y parámetros de negocio
Administrar zonas de despacho, tipos de documento, motivos de cancelación/incidencia, talleres,
marcas/colores de vehículo, y repuestos — reemplazando lo que antes vivía fijo en código o como
texto libre sin validación.

### RF-ADM-INT-001 — Integraciones externas
Gestionar credenciales para consumidores externos, y el estado/rotación de servicios externos que el
propio sistema consume (Google Maps real; SMS/S3 declarados "No configurado" honestamente).

### RF-ADM-MON-001 — Monitoreo de infraestructura
Estado de salud (backend, MongoDB, Redis, ClickHouse, Airflow) evaluado bajo demanda, con umbrales
configurables e indicadores adicionales reales por motor.

### RF-ADM-SEC-001 — Políticas de seguridad y alertas
Vida útil de tokens de sesión y umbrales de bloqueo (refresh, denegaciones RBAC repetidas); enrutar
cada tipo de alerta real del sistema al rol que debe atenderla.

### RF-ADM-BAK-001 — Respaldos y continuidad
Respaldo/restauración de prueba de MongoDB y ClickHouse; plan de continuidad (RTO/RPO por dominio) y
registro de simulacros.

### RF-ADM-GOB-001 — Gobernanza de datos
Anonimización irreversible de una cuenta (derechos ARCO/LOPDP) con doble confirmación explícita
(escribir la palabra exacta, no basta un clic); consulta de la política de retención vigente por
tipo de dato.

## 5. Requisitos no funcionales

### RNF-ADM-001 — Mínimo privilegio
`admin_sistema` nunca comparte OR-gate con `admin_plataforma` — son dominios de gobierno distintos.

### RNF-ADM-002 — Bloqueo por defecto en configuración crítica
Los formularios de política/parámetros globales/seguridad arrancan bloqueados; requieren "Editar"
explícito antes de poder cambiar cualquier valor.

## 6. Reglas de negocio

### RN-ADM-001
No se crean conductores/pasajeros a mano desde Usuarios — el propio sistema lo explica en pantalla:
crear uno a mano saltaría el flujo de verificación documental real (Captación).

### RN-ADM-002
Un cambio de política/parámetro global afecta de inmediato a todo el sistema, sin ventana de
gracia.

### RN-ADM-003
La anonimización exige escribir la palabra "ANONIMIZAR" para confirmar — nunca basta un clic, por
ser irreversible.

### RN-ADM-004
Los eventos de bitácora ya escritos con una cuenta anonimizada se conservan intactos (usan un id
interno, nunca el nombre) — el propio evento de anonimización nunca lleva el dato personal que se
está purgando.

## 7. Entradas

Ver cada RF — filtros de búsqueda, valores de política/parámetro, credenciales, criterios de
anonimización.

## 8. Salidas

Listados filtrables por módulo; confirmaciones de cambio; resultado de respaldo/restauración de
prueba; confirmación de anonimización.

## 9. Estados posibles

Cuenta de usuario: `ACTIVO` / `SUSPENDIDO` / `BAJA` (ver `000-sistema-general/glosario.md`).
Credencial de integración: activa / revocada (idempotente, 409 en un segundo intento de revocar).

## 10. Escenarios

### Escenario 1: Rotación de clave de Google Maps con efecto inmediato
Dado que existe una clave de Google Maps activa
Cuando `admin_sistema` rota la clave desde Integraciones
Entonces la siguiente petición real a `maps.googleapis.com` usa la clave nueva, sin reiniciar el
backend.

### Escenario 2: Anonimización con doble confirmación
Dado que se busca una cuenta real por nombre
Cuando se pulsa "Anonimizar" sin escribir la palabra exacta
Entonces el sistema no ejecuta la acción — solo procede si el texto coincide exactamente.

### Escenario 3: Respaldo real con conteo verificable
Dado que se dispara un respaldo de MongoDB
Cuando se restaura de prueba a una base aislada (nunca la real)
Entonces los conteos por colección coinciden exactamente con la base de origen.

## 11. Criterios de aceptación

Reusa `PLAN_DE_PRUEBAS.md`:
- **PD-05** — Catálogos: alta, edición, baja lógica.
- **PD-06** — Baja lógica de una cuenta y sus casos borde.
- **PU-07**/**PU-08** — Versión en lenguaje simple.
- **PUS-08** — Anonimización exige la palabra exacta.
- **PUS-09** a **PUS-15** — motivo obligatorio, avisos, bloqueo de casos borde, catálogos
  desactivados no ofrecidos.

### CA-ADM-001
Dar de baja una cuenta con un viaje en curso se rechaza con 409 y un mensaje indicando qué viaje
cerrar primero.

### CA-ADM-002
La base de destino de una restauración de prueba está fijada en el código (nunca acepta un nombre
del cliente) — "nunca toca producción" es garantía de código, no solo de la interfaz.

## 12. Dependencias

- **000-sistema-general/reglas.md** — RN-SIS-001 (baja lógica), RN-SIS-003 (RBAC), RN-SIS-007
  (login sin OTP) se gobiernan concretamente desde este módulo.
- **004-transversal/auditoria-y-trazabilidad** — cada acción administrativa queda registrada ahí.
- Consumido indirectamente por los 6 departamentos operativos (catálogos, parámetros).

## 13. Fuera de alcance

- **Cifrado en reposo** de los respaldos — declarado explícitamente como no implementado.
- **RTO/RPO real completado** para los 7 dominios — el campo existe y es editable, pero nunca se
  llenó (campo real sin valor asignado, no un error).
- **Anonimización automática por vencimiento de plazo** — siempre manual, con doble confirmación.
- **Envío de correo/SMS** para alertas — el único canal con entrega real es Web Push.
