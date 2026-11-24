# Especificación: Departamento de Cumplimiento Regulatorio

**Nivel:** Operativo · **Objetivo que respalda:** OP6 — Vigencia documental de socios y vehículos ·
**Responsable:** Supervisor de Cumplimiento

## 1. Objetivo

Controlar que la documentación habilitante de conductores y vehículos (licencia de conducir,
matrícula vehicular) se mantenga vigente, anticipando los vencimientos y avisando a tiempo a quien
debe renovar.

## 2. Contexto

Operar con documentación vencida expone legalmente a la cooperativa ante el regulador. El control
debe ser sistemático — revisar la fecha de vencimiento de cada documento registrado — y no depender
de que alguien lo recuerde caso por caso.

## 3. Usuarios o actores

- **Supervisor de Cumplimiento** — dispara la revisión, consulta los resultados.
- **Sistema** — clasifica cada documento y notifica al titular afectado.
- **Socio conductor** — recibe la notificación de vencimiento/proximidad; puede subir una renovación
  sobre un documento ya existente desde su propio portal.

## 4. Funcionalidad — Control de vigencia documental (CU-O09)

### 4.1 Requisitos funcionales

- **RF-CUMP-001**: El sistema debe revisar la fecha de vencimiento de todos los documentos
  registrados y clasificar cada uno como vigente, próximo a vencer o vencido.
- **RF-CUMP-002**: El sistema debe permitir disparar esta revisión bajo demanda desde el portal
  interno, sin necesidad de tocar ninguna otra pantalla.
- **RF-CUMP-003**: Al finalizar la revisión, el sistema debe informar cuántos documentos se
  revisaron, cuántos se notificaron por proximidad de vencimiento y cuántos vencimientos nuevos se
  detectaron.
- **RF-CUMP-004**: El sistema debe notificar al titular de cada documento (o al propietario del
  vehículo, si el documento es del vehículo) cuando su documento entra en alguno de los umbrales de
  aviso: 30, 15, 7 o 1 día antes del vencimiento, y cuando efectivamente vence.
- **RF-CUMP-005**: El sistema debe permitir consultar el resultado como un listado de documentos
  vencidos y por vencer, con su titular y días restantes.
- **RF-CUMP-006**: El sistema debe permitir consultar el estado documental de un socio conductor
  determinado desde su propia ficha en el portal interno.
- **RF-CUMP-007**: El sistema debe permitir al conductor ver su propio estado documental y subir una
  renovación (archivo + nueva fecha de vencimiento) sobre un documento propio ya existente, para que
  el Supervisor de Cumplimiento la verifique.

### 4.2 Reglas de negocio

- **RN-CUMP-001**: Un documento marcado como vencido no vuelve a notificarse por el mismo
  vencimiento una vez que ya se marcó (no se repite el aviso día tras día).
- **RN-CUMP-002**: Una advertencia de documentación vencida es informativa: el sistema no bloquea
  ninguna operación del conductor ni del vehículo por este motivo.

### 4.3 Entradas

Ninguna entrada de usuario para disparar la revisión (opera sobre los documentos ya registrados);
archivo y fecha de vencimiento nueva al subir una renovación.

### 4.4 Salidas

Resumen de la corrida (revisados / notificados / vencidos nuevos); listado de documentos por vencer
o vencidos; notificación al titular afectado; estado documental individual de un socio.

### 4.5 Escenarios

**Escenario: revisión con vencimientos nuevos**
Dado que existen documentos cuya fecha de vencimiento ya pasó y no estaban marcados como vencidos
Cuando el Supervisor de Cumplimiento dispara el control de vigencia
Entonces el sistema los marca como vencidos, notifica a cada titular, e informa el número de
vencimientos nuevos detectados.

**Escenario: aviso de proximidad**
Dado que un documento vence en 7 días
Cuando se ejecuta el control de vigencia
Entonces el sistema notifica al titular por estar dentro de uno de los umbrales de aviso.

**Escenario: consulta de un socio puntual**
Dado que el Supervisor de Cumplimiento necesita saber si un conductor específico está al día
Cuando abre su ficha en el portal interno
Entonces ve el estado de cada uno de sus documentos con su fecha de vencimiento, sin tener que
buscarlo en el listado general.

### 4.6 Criterios de aceptación

- **CA-CUMP-001**: Un documento cuya fecha ya venció, tras correr el control, aparece como vencido
  en el listado y genera una notificación real al titular.
- **CA-CUMP-002**: El resumen mostrado tras ejecutar el control coincide con el número real de
  documentos afectados en esa corrida.
- **CA-CUMP-003**: La advertencia de documentación vencida es visible tanto para el conductor en su
  propio portal como para el personal interno en su ficha, sin bloquear ninguna acción en ninguno de
  los dos casos.

## 5. Requisitos no funcionales

- **RNF-CUMP-001 (trazabilidad)**: Todo cambio de estado de vigencia de un documento (a vencido, o
  restaurado por una renovación aprobada) queda registrado en la bitácora de auditoría.

## 6. Dependencias

- Captación y Talento: los documentos que este control revisa se crean, en su mayoría, al aprobarse
  una postulación de conductor.
- Catálogo de tipos de documento — define qué tipos existen y a qué (conductor o vehículo) aplica
  cada uno.

## 7. Fuera de alcance

- **Ejecución automática y programada del control diario.** El sistema implementa el disparo bajo
  demanda; no existe todavía ningún proceso automático (cron o tarea programada) que lo ejecute sin
  intervención humana. Es una capacidad prevista en el diseño del proceso, no construida.
- Bloqueo de operaciones (iniciar turno, aceptar viajes) por documentación vencida — es una decisión
  operativa pendiente de la cooperativa, no activada.
- Anonimización de datos personales al vencer un documento — no forma parte de este control.

---

**Trazabilidad**: Nivel Operativo → Departamento Cumplimiento Regulatorio → OP6 → CU-O09 →
`web-interno` → Cumplimiento, `web-conductor` → "Mis documentos" →
`backend/src/cumplimiento/`.
