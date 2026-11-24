# Especificación: Cumplimiento Regulatorio (Nivel Operativo)

> Documento retroactivo. Fuente principal: `AUDITORIA_FUNCIONAL_OPERATIVO.md` §6, verificada contra
> `backend/src/cumplimiento/` — incluye un hallazgo real de la propia investigación de este
> documento, distinto de lo que la auditoría original describía como causa.

## 1. Objetivo

Vigilar la vigencia de los documentos legales de socios y vehículos (licencia, matrícula), avisando
antes de que un vencimiento se convierta en una exposición legal real para la cooperativa.

## 2. Contexto

Un conductor con licencia vencida operando es un riesgo legal directo. Sin un control activo, nadie
se entera de un vencimiento hasta que ya es tarde.

## 3. Actores

- **`supervisor_cumplimiento`** (personal interno) — único actor con acceso operativo.
- **`conductor`** — puede consultar sus propios documentos y subir una renovación (autoservicio,
  ver §13 sobre un gap real de cobertura).

## 4. Requisitos funcionales

### RF-CUM-001 — Control de vigencia bajo demanda
El sistema debe revisar todos los documentos con fecha de vencimiento y marcar cuáles están
vencidos o próximos a vencer, notificando al propietario correspondiente. En producción corre
automáticamente a las 06:00; el botón en pantalla lo dispara bajo demanda.

### RF-CUM-002 — Autoservicio de renovación del conductor
El conductor debe poder ver sus propios documentos con su vigencia, y subir una renovación real
(archivo + nueva fecha de vencimiento) sobre un documento que ya existe.

### RF-CUM-003 — Aprobación de una renovación subida
`supervisor_cumplimiento` debe poder aprobar o rechazar una renovación subida por el conductor, con
motivo si la rechaza.

## 5. Requisitos no funcionales

### RNF-CUM-001 — Cálculo en UTC, no en hora local del servidor
El cálculo de vencimiento usa `datetime.now(UTC).date()` de forma explícita — la arquitectura exige
timestamps en UTC precisamente para que el mismo cálculo no dé un día distinto según dónde corra el
proceso.

## 6. Reglas de negocio

### RN-CUM-001
Un documento vencido baja la bandera `cumplimiento_ok` de su propietario (conductor o vehículo) solo
la primera vez — si ya estaba en rojo, no repite el efecto de negocio ni la auditoría cada día que
corre el control.

### RN-CUM-002
El sistema **advierte** documentación vencida (visible al conductor y a personal interno) pero
**nunca bloquea ninguna operación** por este motivo — decisión operativa pendiente de la
cooperativa, no una carencia técnica (RN-SIS-004, coherente con `spec.md` §10 del nivel sistema).

## 7. Entradas

- Ninguna para el control automático (barre `documentos` completo).
- Conductor: archivo de renovación + nueva fecha de vencimiento, sobre un documento existente.
- `supervisor_cumplimiento`: aprobar/rechazar una renovación, con motivo si rechaza.

## 8. Salidas

- Resultado del control: revisados / por vencer notificados / vencidos nuevos.
- Notificación al propietario correspondiente (conductor, o dueño del vehículo si el documento es
  del vehículo).
- Bandera `cumplimiento_ok` actualizada en el propietario.

## 9. Estados posibles

Documento (`documentos.estado_verificacion`): `CONFORME` / vencido (marcado por fecha, no un campo
de enum separado — el estado real se deriva comparando `fecha_vencimiento` contra hoy).

## 10. Escenarios

### Escenario 1: Control real con documentos vencidos nuevos
Dado que existen documentos cuya fecha de vencimiento ya pasó y que nunca se habían marcado
Cuando `supervisor_cumplimiento` ejecuta el control de vigencia
Entonces el resultado muestra la cantidad real de vencidos nuevos, y cada propietario recibe una
notificación real.

### Escenario 2: Renovación real del conductor
Dado que un conductor tiene un documento próximo a vencer
Cuando sube una renovación con un archivo real y una nueva fecha
Entonces el documento queda con una renovación pendiente de aprobación, visible para
`supervisor_cumplimiento`.

## 11. Criterios de aceptación

Reusa `PLAN_DE_PRUEBAS.md` (el control de vigencia forma parte del flujo verificado en **PD-10**,
sección de Captación, por compartir la misma entidad `documentos`).

### CA-CUM-001
Ejecutar el control de vigencia dos veces seguidas sobre el mismo documento vencido no duplica el
evento de bitácora ni repite la notificación.

### CA-CUM-002
Ninguna acción del sistema queda bloqueada por documentación vencida — solo se muestra una
advertencia visible.

## 12. Dependencias

- **003-operativo/captacion-y-talento** — los documentos aprobados en una postulación entran solos
  al barrido de este control, sin trabajo adicional (verificado: "Revisados" subió exactamente en 2
  tras aprobar una postulación con 2 documentos).
- **004-transversal/notificaciones** — cada vencimiento/próximo a vencer dispara un aviso real.
- **002-tactico/cumplimiento-regulatorio** y **001-estrategico** (Cumplimiento Normativo) — agregan
  este mismo dato.

## 13. Fuera de alcance / discrepancia real encontrada

- **Anonimización LOPDP automática** — existe el mecanismo (transversal, Administración del
  Sistema) pero es manual, nunca automática por vencimiento de plazo.
- **Validación de legitimidad del documento** — igual que en Captación, el sistema guarda y muestra
  el archivo, no lo valida contra un registro externo.
- **Discrepancia real encontrada al escribir este documento, entre dos fuentes propias del
  proyecto**: `AUDITORIA_FUNCIONAL_OPERATIVO.md` §6.1 afirma que la bandeja "Buscar renovaciones
  pendientes" **siempre estará vacía** porque "ninguna pantalla de ninguna de las 3 apps llama" al
  endpoint de subir renovación. Eso es **falso hoy** — verificado contra el código real
  (`web-conductor/App.tsx`, sección "Mis documentos") y contra `PLAN_DE_PRUEBAS.md` (corregido en
  la misma sesión que este documento): el conductor **sí** tiene una pantalla real
  ("Mis documentos") desde donde subir una renovación (`subirArchivo(file,
  "documento_renovacion")`, RF-CUM-002), y el entorno de desarrollo llegó a tener al menos 1
  renovación real pendiente de revisión. La afirmación de la auditoría quedó desactualizada por una
  ronda de trabajo posterior a cuando se escribió — la bandeja está vacía solo cuando nadie subió
  una renovación todavía, que es un estado vacío normal, no una imposibilidad estructural. No
  repetir la afirmación vieja sin volver a verificar contra el código si se retoma este punto.
