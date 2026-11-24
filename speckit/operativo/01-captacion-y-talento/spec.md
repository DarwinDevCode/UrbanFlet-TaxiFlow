# Especificación: Departamento de Captación y Talento

**Nivel:** Operativo · **Objetivo que respalda:** OP1 — Incorporación de socios conductores y
pasajeros · **Responsable:** Administrador de Captación

## 1. Objetivo

Incorporar nuevos participantes al sistema con el control de calidad que corresponde a cada caso:
revisión documental para quienes aportan un vehículo a la flota (socios conductores), alta
inmediata para quienes solo consumen el servicio (pasajeros).

## 2. Contexto

Sin socios conductores habilitados no hay flota que el sistema pueda despachar; sin pasajeros
registrados no hay demanda que atender. Ambos flujos comparten el mismo sistema de cuentas, pero
tienen exigencias de verificación completamente distintas: un conductor aporta un vehículo a un
servicio regulado, un pasajero solo necesita una identidad para pedir un taxi.

## 3. Usuarios o actores

- **Postulante a socio conductor** — persona externa al sistema, sin cuenta previa.
- **Pasajero** — persona externa al sistema, sin cuenta previa.
- **Administrador de Captación** — rol interno (`admin_captacion`), revisa y decide postulaciones.
- **Sistema** — crea automáticamente la cuenta de conductor y el vehículo al aprobar.

## 4. Funcionalidad 1 — Postulación e incorporación de socio conductor (CU-O01)

### 4.1 Requisitos funcionales

- **RF-CAP-001**: El sistema debe permitir a un postulante registrar su solicitud desde el portal
  del conductor con: nombre, teléfono o correo, contraseña, cédula, número de licencia, y los datos
  del vehículo (placa, marca, modelo, año, color, capacidad).
- **RF-CAP-002**: El sistema debe permitir adjuntar, como parte de la misma postulación, la licencia
  de conducir y la matrícula del vehículo, cada una con su fecha de caducidad, subidas como archivo
  real (imagen).
- **RF-CAP-003**: El sistema debe validar cada tipo de documento adjunto contra el catálogo de tipos
  de documento activos antes de aceptar la postulación.
- **RF-CAP-004**: El sistema debe presentar al Administrador de Captación la lista de solicitudes
  pendientes, más reciente primero, filtrable por estado y por cédula.
- **RF-CAP-005**: El sistema debe permitir al Administrador de Captación tomar una solicitud
  enviada (pasa a "en verificación") antes de poder decidirla.
- **RF-CAP-006**: El sistema debe mostrar, dentro del detalle de la solicitud, cada documento
  adjunto de forma visual (no solo su existencia), junto a su fecha de caducidad y un indicador de
  vigencia calculado contra la fecha actual.
- **RF-CAP-007**: El sistema debe permitir al Administrador de Captación decidir la solicitud:
  aprobar, observar (con motivo escrito obligatorio) o rechazar (con motivo escrito obligatorio).
- **RF-CAP-008**: Al aprobar una solicitud, el sistema debe crear automáticamente, en la misma
  operación: la cuenta de usuario con el rol de conductor, el registro del vehículo en la flota
  (habilitado), y los documentos adjuntos como registros de control de vigencia documental —sin
  intervención manual adicional.
- **RF-CAP-009**: El sistema debe permitir al postulante iniciar sesión con el teléfono/correo y la
  contraseña definidos en la postulación inmediatamente después de la aprobación.

### 4.2 Reglas de negocio

- **RN-CAP-001**: No puede existir más de una solicitud activa (enviada, en verificación u
  observada) con la misma cédula.
- **RN-CAP-002**: Si la cédula ya corresponde a un socio conductor activo, la postulación se
  rechaza automáticamente.
- **RN-CAP-003**: Si la placa del vehículo ya existe en la flota, la solicitud queda marcada para
  revisión reforzada (sin bloquear su envío).
- **RN-CAP-004**: Una solicitud solo puede decidirse (aprobar/observar/rechazar) mientras está en
  estado enviada, en verificación u observada.
- **RN-CAP-005**: Observar o rechazar exige un motivo no vacío; no existe forma de completar esas
  dos decisiones sin él.

### 4.3 Entradas

Datos personales del postulante, datos del vehículo, licencia de conducir (archivo + fecha de
caducidad), matrícula del vehículo (archivo + fecha de caducidad).

### 4.4 Salidas

Solicitud creada con estado inicial; tras la decisión, uno de: cuenta de conductor + vehículo +
documentos creados (aprobada), solicitud con motivo de observación (observada), solicitud con
motivo de rechazo (rechazada).

### 4.5 Escenarios

**Escenario: postulación aprobada**
Dado que un postulante completa sus datos y adjunta licencia y matrícula con fechas de caducidad
válidas
Cuando envía la solicitud y el Administrador de Captación la toma y la aprueba
Entonces el sistema crea la cuenta de conductor, habilita el vehículo, registra los 2 documentos, y
el postulante puede iniciar sesión de inmediato.

**Escenario: observación por documentación insuficiente**
Dado que el Administrador de Captación revisa una solicitud en verificación y detecta un problema
en un documento
Cuando decide observarla y escribe el motivo
Entonces la solicitud queda en estado observada con ese motivo, sin crear ninguna cuenta ni vehículo.

**Escenario: cédula duplicada**
Dado que ya existe una solicitud activa con una cédula
Cuando otra persona intenta postular con la misma cédula
Entonces el sistema rechaza el envío antes de crear ninguna cuenta.

### 4.6 Criterios de aceptación

- **CA-CAP-001**: Una postulación completa con documentos válidos queda en estado "enviada" y
  visible primero en la lista del Administrador de Captación.
- **CA-CAP-002**: Al aprobar, en Mongo existen en la misma operación: el usuario con rol
  `conductor`, el vehículo habilitado, y 2 documentos nuevos con la misma fecha de caducidad que se
  adjuntó.
- **CA-CAP-003**: Intentar observar o rechazar sin motivo no completa la acción.
- **CA-CAP-004**: Una segunda postulación con una cédula ya activa es rechazada por el sistema antes
  de llegar a la bandeja del Administrador de Captación.

## 5. Funcionalidad 2 — Registro de pasajero (CU-O02)

### 5.1 Requisitos funcionales

- **RF-CAP-010**: El sistema debe permitir a cualquier persona crear su cuenta de pasajero desde el
  portal del pasajero, indicando nombre, un teléfono o correo, y una contraseña.
- **RF-CAP-011**: El sistema debe iniciar sesión automáticamente al completar el registro, sin paso
  de verificación adicional.

### 5.2 Reglas de negocio

- **RN-CAP-006**: El teléfono o correo usado como identificador debe ser único en el sistema.

### 5.3 Entradas

Nombre, teléfono o correo, contraseña.

### 5.4 Salidas

Cuenta de pasajero creada y sesión iniciada.

### 5.5 Escenarios

**Escenario: registro exitoso**
Dado que una persona completa nombre, un identificador (teléfono o correo) no usado antes, y una
contraseña
Cuando envía el formulario de registro
Entonces el sistema crea la cuenta con rol `pasajero` y la deja con sesión iniciada, lista para
solicitar un viaje.

### 5.6 Criterios de aceptación

- **CA-CAP-005**: Tras el registro, la persona queda autenticada sin necesidad de un segundo paso
  de inicio de sesión.
- **CA-CAP-006**: Un identificador ya usado por otra cuenta es rechazado en el registro.

## 6. Requisitos no funcionales

- **RNF-CAP-001 (trazabilidad)**: Toda decisión sobre una solicitud (tomar, aprobar, observar,
  rechazar) queda registrada en la bitácora de auditoría con el actor y el motivo cuando aplica.

## 7. Dependencias

- Catálogo de tipos de documento (Cumplimiento Regulatorio) para validar qué se puede adjuntar.
- Mecanismo de carga de archivos compartido (usado también por reportes de falla y fotos de perfil).
- Módulo de autenticación (RG-001 de la constitución) para la sesión que se abre al aprobar/registrar.

## 8. Fuera de alcance

- Verificación automática de la autenticidad de los documentos (OCR, validación contra un registro
  externo) — la revisión es siempre humana.
- Postulación o registro con un método distinto a teléfono/correo + contraseña (p. ej. redes
  sociales) — no existe en el sistema.

---

**Trazabilidad**: Nivel Operativo → Departamento Captación y Talento → OP1 → CU-O01/CU-O02 →
`web-conductor` (formulario de postulación, "Mis documentos"), `web-interno` → Solicitudes →
`backend/src/captacion/`, `backend/src/archivos/`, `backend/src/cumplimiento/` (documentos creados
al aprobar).
