# Especificación: Captación y Talento (Nivel Operativo)

> Documento retroactivo. Fuente principal: `AUDITORIA_FUNCIONAL_OPERATIVO.md` §1, verificada contra
> el código real. **Aviso de discrepancia real, encontrada al construir este documento**: el §1.1
> de esa auditoría afirma "la carga de documentos... está fuera de alcance a propósito" — eso fue
> cierto cuando se escribió, pero quedó desactualizado por una ronda posterior de este mismo
> proyecto (`CLAUDE.md` §26.3, "Gestión documental en la postulación"), que sí implementó la carga
> real de licencia y matrícula durante la postulación. Este documento describe el **estado actual
> verificado**, no el de esa auditoría puntual.

## 1. Objetivo

Dar de alta nuevas cuentas de dos tipos — socios conductores (con verificación documental) y
pasajeros (sin verificación) — como puerta de entrada controlada a la cooperativa.

## 2. Contexto

La cooperativa no puede aceptar automáticamente a cualquier persona que quiera manejar para ella:
alguien tiene que verificar identidad, licencia y vehículo antes de dejarla operar. Del lado del
pasajero, en cambio, no hay ningún control de calidad que aplicar — cualquiera puede pedir un taxi.

## 3. Actores

- **Postulante** (sin cuenta previa) — crea su propia postulación de conductor.
- **Persona sin cuenta** — se registra directamente como `pasajero`.
- **`admin_captacion`** (personal interno) — revisa, decide y corrige solicitudes de conductor.

## 4. Requisitos funcionales

### RF-CAP-001 — Postulación de conductor con documentos
El sistema debe permitir que una persona sin cuenta cree una postulación con sus datos, los del
vehículo, y **adjunte licencia de conducir y matrícula del vehículo con fecha de caducidad**, en un
flujo de 3 pasos: crear la solicitud en `BORRADOR` → autenticarse con la cuenta recién creada → subir
los 2 archivos y enviar la solicitud (`POST /captacion/solicitudes/mia/documentos`), que la pasa a
`ENVIADA`. Verificado en vivo esta sesión con 2 imágenes reales subidas y confirmadas en Mongo con su
hash SHA-256.

### RF-CAP-002 — Registro directo de pasajero
El sistema debe permitir que cualquier persona cree su propia cuenta de pasajero en un único paso,
sin revisión posterior, con login automático inmediato.

### RF-CAP-003 — Revisión de la documentación adjunta
`admin_captacion` debe poder ver las imágenes reales de los documentos (no solo saber que existen),
su fecha de caducidad, y un semáforo de vigencia calculado contra la fecha actual, antes de decidir.

### RF-CAP-004 — Toma y decisión de una solicitud
Una solicitud `ENVIADA` solo puede decidirse después de "Tomar" (pasa a `EN_VERIFICACION`). La
decisión final es `APROBADA`, `RECHAZADA` u `OBSERVADA` (esta última exige un motivo de texto
obligatorio).

### RF-CAP-005 — Efectos automáticos de la aprobación
Al aprobar, el sistema debe crear automáticamente: el rol `conductor` sobre la cuenta, un documento
`vehiculos` nuevo (`HABILITADO`), y **2 registros reales en la colección `documentos`** (uno por cada
archivo adjunto) — la misma entidad que consumen los paneles de Vigencia Documental (táctico) y
Cumplimiento Normativo (estratégico), sin ningún paso manual adicional.

### RF-CAP-006 — Catálogo cerrado de tipos de documento
El tipo de cada documento adjunto (`LICENCIA_CONDUCIR`, `MATRICULA_VEHICULAR`) se valida contra el
catálogo real `tipos_documento` — un tipo inexistente o inactivo se rechaza con 422 antes de crear
ninguna cuenta.

## 5. Requisitos no funcionales

### RNF-CAP-001 — Propiedad del archivo verificada, nunca confiada del cliente
El `archivo_id` que el cliente manda al adjuntar un documento se resuelve contra un archivo real ya
subido por esa misma cuenta con el contexto `documento_postulacion` — nunca se confía en la palabra
del cliente sobre qué subió.

### RNF-CAP-002 — Ninguna solicitud enviada queda sin documentos
Si el flujo de 3 pasos se corta a mitad de camino, la solicitud queda en `BORRADOR` (invisible para
Captación) en vez de en `ENVIADA` sin adjuntos — el postulante puede reintentar sin perder los datos
ya ingresados.

## 6. Reglas de negocio

### RN-CAP-001
Una solicitud es corregible (RN-SIS-005) solo mientras esté en `ENVIADA`/`EN_VERIFICACION`/
`OBSERVADA`. **Corrección eliminada**: existió un endpoint de corrección de cédula/licencia/vehículo
para `admin_captacion`, pero se retiró por completo en una ronda posterior por permitir edición
libre de datos que el propio postulante había enviado — decisión ya tomada, no reintroducir sin
pedido explícito (`CLAUDE.md` §28.10).

### RN-CAP-002
Marca "revisión reforzada" automática si la placa del vehículo ya existe en la flota — solo una
etiqueta informativa en la bandeja, sin flujo adicional automatizado.

### RN-CAP-003
No hay OTP ni verificación de correo/teléfono en ningún punto del alta (RN-SIS-007).

## 7. Entradas

- Postulante: nombre, teléfono/correo, contraseña, cédula, licencia, placa, marca (o "Otro" libre),
  modelo, año, color (o "Otro" libre), capacidad, archivo de licencia + fecha de caducidad, archivo
  de matrícula + fecha de caducidad.
- Pasajero: nombre, teléfono o correo, contraseña.
- `admin_captacion`: decisión (aprobar/rechazar/observar) + motivo si no es aprobación.

## 8. Salidas

- Cuenta creada, con login automático (pasajero) o pendiente de aprobación (conductor).
- Estado final de la solicitud, con los efectos reales de la aprobación (rol, vehículo, 2
  documentos).
- Eventos de bitácora (`SOLICITUD_CONDUCTOR_DECISION`, `VEHICULO_HABILITACION`) con la misma marca
  de tiempo.

## 9. Estados posibles

Solicitud de conductor: `BORRADOR` → `ENVIADA` → `EN_VERIFICACION` → `APROBADA` / `RECHAZADA` /
`OBSERVADA` (puede volver a `EN_VERIFICACION` tras una observación corregida) / `EXPIRADA`.

## 10. Escenarios

### Escenario 1: Postulación completa con documentos, aprobada
Dado que una persona nueva completa el formulario de postulación con licencia y matrícula reales
Cuando envía la solicitud y `admin_captacion` la toma, revisa las 2 imágenes y aprueba
Entonces la solicitud queda `APROBADA`, el usuario gana el rol `conductor`, su vehículo queda
`HABILITADO`, y existen 2 documentos reales en `documentos` con la misma fecha de caducidad que se
subió.

### Escenario 2: Postulación interrumpida a mitad de camino
Dado que el postulante crea la solicitud (paso 1) pero pierde la conexión antes de subir los
archivos
Cuando vuelve a intentarlo
Entonces la solicitud original sigue en `BORRADOR`, invisible para Captación, sin duplicarse.

### Escenario 3: Documento con tipo no reconocido
Dado que un cliente manda un `tipo` de documento que no existe en el catálogo
Cuando intenta crear la solicitud
Entonces el sistema responde 422 `TIPO_DOCUMENTO_INVALIDO` antes de crear la cuenta.

### Escenario 4: Registro de pasajero exitoso
Dado que una persona sin cuenta completa el formulario de registro de pasajero
Cuando confirma
Entonces queda con sesión iniciada de inmediato, sin paso de verificación adicional.

## 11. Criterios de aceptación

Reusa `PLAN_DE_PRUEBAS.md`:
- **PD-02** — Postulación de conductor con documentos y aprobación, con verificación técnica en red
  y en Mongo.
- **PU-03** — Versión en lenguaje simple del mismo flujo.
- **TU-07** — Captación revisa una postulación con documentos y decide, sin instrucciones previas
  (mide además si la palabra "Tomar" se entiende).

### CA-CAP-001
Una solicitud `ENVIADA` con 2 documentos reales muestra ambas imágenes en el detalle de revisión,
con su fecha de caducidad.

### CA-CAP-002
Al aprobar, existen exactamente 2 documentos nuevos en Mongo con el mismo `archivo_id`/hash que se
subió.

### CA-CAP-003
Un registro de pasajero nuevo permite iniciar sesión de inmediato sin ningún paso adicional.

## 12. Dependencias

- **004-transversal/auditoria-y-trazabilidad** — todo el flujo queda registrado en la bitácora.
- **004-transversal/administracion-del-sistema** (Catálogos) — el tipo de documento y el catálogo
  de marcas/colores de vehículo son gestionados ahí.
- **003-operativo/coordinacion-de-flota** — el vehículo creado al aprobar entra directo a la flota.
- **002-tactico/captacion-y-talento** y **001-estrategico** (Crecimiento) — consumen las altas y
  conversiones que este módulo genera.

## 13. Fuera de alcance

- **Validación de legitimidad de los documentos** (que la licencia/matrícula sea auténtica, no solo
  que exista el archivo) — el sistema guarda y muestra el archivo, no lo valida contra un registro
  externo.
- **OTP/verificación de correo** — decisión de arquitectura ya tomada (RN-SIS-007).
- **Corrección de datos de la solicitud por `admin_captacion`** — existió y se retiró (RN-CAP-001).
- **Reset de contraseña** — no implementado en ningún flujo del sistema.
