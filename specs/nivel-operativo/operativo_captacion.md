# Especificación operativa — Captación y Talento

Paquete: `pkg-captacion` · Objetivo: OP1.1 (registrar y verificar solicitudes de conductores y pasajeros) · OE1

Estados de la solicitud de conductor:

```
BORRADOR → ENVIADA → EN_VERIFICACION → APROBADA
                │            │
                │            ├──→ OBSERVADA → ENVIADA (reenvío corregido)
                │            └──→ RECHAZADA (terminal)
                └──→ EXPIRADA (30 días sin completar)
```

---

## CU-O01 — Registrar la solicitud de un conductor

**Actores:** Postulante a socio conductor, Sistema

**Precondiciones:**
- El postulante accede al portal web de la cooperativa desde cualquier navegador.
- No existe otra solicitud `ENVIADA`, `EN_VERIFICACION` u `OBSERVADA` con la misma cédula.

**Flujo principal:**
1. El postulante pulsa "Quiero ser socio conductor" y ve el listado de requisitos antes de iniciar: cédula, licencia profesional vigente, matrícula del vehículo, permiso de operación/habilitación municipal y SOAT o seguro equivalente.
2. El postulante crea su cuenta con correo y teléfono; el sistema verifica el teléfono con un código OTP por SMS.
3. El postulante completa el formulario en pasos: (a) datos personales, (b) datos del vehículo (placa, marca, modelo, año, color, capacidad), (c) carga de documentos — foto o PDF por cada requisito, con fecha de vencimiento cuando aplique.
4. En cada carga, el sistema valida formato (JPG/PNG/PDF), tamaño máximo (10 MB) y legibilidad mínima (resolución), y muestra la vista previa.
5. Al completar todos los pasos, el postulante pulsa "Enviar solicitud". El sistema valida la completitud, marca la solicitud como `ENVIADA` con timestamp y notifica al Administrador de Captación.
6. El postulante ve una pantalla de estado con el número de solicitud y el plazo comprometido de respuesta (5 días hábiles).

**Flujos alternos:**
- **A1 — Guardar como incompleta:** en cualquier paso el postulante puede salir; la solicitud queda en `BORRADOR` y es retomable. A los 30 días sin envío pasa a `EXPIRADA` con notificación previa a los 25 días.
- **A2 — Cédula ya registrada como socio activo:** el sistema rechaza con `APPLICANT_ALREADY_MEMBER` y ofrece recuperación de cuenta.
- **A3 — Placa ya registrada en la flota:** el sistema lo advierte y exige que el postulante declare la relación con el vehículo (compra, cesión); la solicitud continúa pero queda marcada para revisión reforzada.
- **A4 — OTP no recibido:** reintento a los 60 segundos, máximo 3 envíos por hora; opción de verificación por llamada.
- **A5 — Documento con fecha de vencimiento pasada:** el sistema bloquea la carga de ese documento con mensaje explícito; no se permite enviar la solicitud con documentos vencidos.

**Postcondiciones:** solicitud persistida con todos los documentos y sus metadatos (tipo, vencimiento, hash del archivo), en estado `BORRADOR` o `ENVIADA`.

---

## CU-O02 — Registrar un pasajero

**Actores:** Pasajero, Sistema

**Precondiciones:** ninguna (registro abierto).

**Flujo principal:**
1. El pasajero abre el portal web de pasajero (instalable como PWA) y pulsa "Crear cuenta".
2. Ingresa nombre, teléfono y correo; acepta los términos del servicio y la política de datos (consentimiento explícito, registrado con timestamp y versión del texto aceptado — requisito LOPDP).
3. El sistema verifica el teléfono con OTP por SMS.
4. La cuenta queda en estado `ACTIVO` y el pasajero puede solicitar viajes de inmediato.

**Flujos alternos:**
- **A1 — Completar perfil después:** foto y correo son opcionales al inicio; el portal lo recuerda en el tercer uso.
- **A2 — Teléfono ya registrado:** flujo de recuperación de cuenta (OTP al mismo número), nunca creación de duplicado.
- **A3 — Menor de edad declarado:** el registro se bloquea; el servicio requiere mayoría de edad para la cuenta titular.

**Postcondiciones:** pasajero en `ACTIVO`, con consentimiento de datos registrado.

---

## CU-O03 — Verificar la documentación del postulante

**Actores:** Administrador de Captación, Sistema, Postulante (receptor de notificaciones)

**Precondiciones:** existe al menos una solicitud en `ENVIADA`.

**Flujo principal:**
1. El Administrador abre la bandeja de solicitudes, ordenada por antigüedad de envío, con semáforo de plazo (verde < 3 días, ámbar 3–5, rojo > 5).
2. Selecciona una solicitud; el sistema la marca `EN_VERIFICACION` y se la asigna (evita doble revisión).
3. Revisa documento por documento contra una lista de verificación fija: legibilidad, coincidencia de nombres, vigencia, coincidencia de placa entre matrícula y formulario. Registra por documento el resultado: `CONFORME` u `OBSERVADO` con motivo.
4. Si todos los documentos quedan `CONFORME`, aprueba la solicitud. El sistema: crea el perfil de socio conductor en estado `ACTIVO`, crea el vehículo asociado en estado `HABILITADO`, agenda los recordatorios de vencimiento documental (los consume Cumplimiento) y notifica al nuevo socio con sus credenciales de acceso al portal web de conductor.
5. El caso queda cerrado con el tiempo total de aprobación registrado (métrica del informe táctico de conversión).

**Flujos alternos:**
- **A1 — Documento observado:** la solicitud pasa a `OBSERVADA`; el postulante recibe la lista exacta de observaciones y puede recargar solo los documentos observados (los conformes no se tocan). Al reenviar vuelve a `ENVIADA` conservando el historial de intentos.
- **A2 — Rechazo definitivo:** ante causal insubsanable (documento adulterado, inhabilitación del conductor), el Administrador rechaza con motivo obligatorio. El sistema notifica al postulante e impide nueva solicitud con la misma cédula por 90 días. El motivo queda en la bitácora de auditoría.
- **A3 — Tres ciclos de observación sin subsanar:** el sistema sugiere el rechazo y lo deja a decisión del Administrador; no rechaza automáticamente.
- **A4 — Administrador abandona la revisión:** si una solicitud queda `EN_VERIFICACION` más de 24 horas sin actividad, vuelve a la bandeja común.

**Postcondiciones:** solicitud en estado terminal (`APROBADA`/`RECHAZADA`) u `OBSERVADA`; si fue aprobada, existen el socio conductor y el vehículo con sus vencimientos documentales agendados. Toda decisión con actor, timestamp y motivo en la bitácora.
