# Especificación: Departamento de Mantenimiento

**Nivel:** Operativo · **Objetivo que respalda:** OP4 — Mantenimiento de los vehículos de la flota
· **Responsable:** Jefe de Mantenimiento

## 1. Objetivo

Atender el ciclo completo de un desperfecto de un vehículo, desde que se detecta hasta que vuelve a
estar habilitado para operar, dejando registro del costo real de cada intervención.

## 2. Contexto

Un vehículo con una falla no puede prestar servicio, y sin un registro sistemático de
intervenciones la cooperativa no tiene forma de conocer el costo real de sostener su flota ni de
anticipar el mantenimiento preventivo.

## 3. Usuarios o actores

- **Socio conductor** — reporta la falla que detecta en su vehículo.
- **Jefe de Mantenimiento** — evalúa el reporte, gestiona la orden hasta cerrarla.
- **Sistema** — notifica al reportarse una falla, proyecta la próxima intervención preventiva.

## 4. Funcionalidad — Gestión de fallas y órdenes de mantenimiento (CU-O07)

### 4.1 Requisitos funcionales

**Reporte de la falla**

- **RF-MANT-001**: El sistema debe permitir al conductor reportar una falla desde su portal,
  eligiendo un tipo de falla del catálogo, escribiendo una descripción y adjuntando una fotografía
  si lo considera necesario.
- **RF-MANT-002**: El sistema debe permitir reportar la falla tanto durante un viaje en curso (con
  la opción de indicar que impide continuar) como fuera de un viaje.
- **RF-MANT-003**: Al recibirse un reporte, el sistema debe notificar tanto al Jefe de Mantenimiento
  como al Coordinador de Operaciones.

**Evaluación del reporte**

- **RF-MANT-004**: El sistema debe presentar al Jefe de Mantenimiento los reportes pendientes, con
  su evidencia fotográfica visible.
- **RF-MANT-005**: El sistema debe permitir convertir un reporte en una orden de taller, heredando
  automáticamente el vehículo, la descripción y la evidencia fotográfica del reporte.
- **RF-MANT-006**: El sistema debe permitir descartar un reporte que no amerite una orden,
  exigiendo un motivo.

**Ciclo de la orden**

- **RF-MANT-007**: El sistema debe permitir crear una orden de mantenimiento indicando el vehículo,
  kilometraje de entrada, taller, fecha programada, repuestos estimados y mano de obra estimada.
- **RF-MANT-008**: El sistema debe permitir avanzar la orden por sus estados: abierta → en taller →
  (opcionalmente) esperando repuesto, con motivo obligatorio, e ida y vuelta libre entre en taller y
  esperando repuesto → cerrada.
- **RF-MANT-009**: Al cerrar la orden, el sistema debe registrar los trabajos realizados, el costo
  total, las horas de taller, el kilometraje de salida y los repuestos consumidos.
- **RF-MANT-010**: Al cerrar la orden, el sistema debe calcular y mostrar la desviación entre el
  costo estimado y el costo real, y proyectar la próxima intervención preventiva.
- **RF-MANT-011**: El sistema debe permitir, al cerrar una orden, abrir de inmediato una orden
  correctiva encadenada si se detectó un problema adicional durante el trabajo, heredando el
  kilometraje de salida como kilometraje de entrada de la nueva orden.
- **RF-MANT-012**: El sistema debe acumular el kilometraje recorrido por cada vehículo a partir de
  los viajes que realiza, y usarlo para proyectar cuándo corresponde su siguiente mantenimiento
  preventivo (cada 5000 km recorridos desde la última intervención).

### 4.2 Reglas de negocio

- **RN-MANT-001**: Un vehículo con una orden abierta o en taller queda retirado de servicio: no
  puede iniciar turno ni recibir viajes.
- **RN-MANT-002**: Una orden solo puede cerrarse desde "en taller" o "esperando repuesto", nunca
  directamente desde "abierta".
- **RN-MANT-003**: Entrar a "esperando repuesto" exige un motivo escrito.
- **RN-MANT-004**: Descartar un reporte de falla exige un motivo escrito.
- **RN-MANT-005**: El vehículo vuelve a estar habilitado automáticamente al cerrar la orden que lo
  tenía retirado.

### 4.3 Entradas

Tipo de falla, descripción, fotografía opcional; datos de la orden (vehículo, kilometraje, taller,
fecha, repuestos, mano de obra); datos de cierre (trabajos, costo real, horas, kilometraje de
salida, repuestos consumidos).

### 4.4 Salidas

Reporte de falla en la bandeja del Jefe de Mantenimiento; orden con su estado actualizado;
al cerrar, desviación de costo y próxima fecha/kilometraje de mantenimiento preventivo proyectado.

### 4.5 Escenarios

**Escenario: falla reportada y convertida en orden**
Dado que un conductor reporta una avería con foto durante su turno
Cuando el Jefe de Mantenimiento revisa el reporte y decide convertirlo en orden
Entonces se crea una orden abierta con el vehículo, la descripción y la foto ya heredados, y el
vehículo queda retirado de servicio.

**Escenario: cierre con desviación de costo**
Dado que una orden tiene un costo estimado de $55
Cuando se cierra registrando un costo real de $72
Entonces el sistema muestra una desviación de +30.9% y proyecta la próxima intervención preventiva.

**Escenario: espera de repuesto**
Dado que una orden está en taller
Cuando el Jefe de Mantenimiento la pasa a "esperando repuesto" con un motivo
Entonces la orden queda en ese estado, bloqueando igual al vehículo, hasta que se reanude o se
cierre.

### 4.6 Criterios de aceptación

- **CA-MANT-001**: Convertir un reporte en orden completa los campos de vehículo, descripción y
  evidencia sin que el Jefe de Mantenimiento tenga que volver a escribirlos.
- **CA-MANT-002**: Un vehículo con una orden abierta o en taller no puede iniciar turno.
- **CA-MANT-003**: Cerrar una orden con costo real distinto del estimado muestra el porcentaje de
  desviación calculado, nunca solo los dos montos por separado.
- **CA-MANT-004**: Descartar un reporte sin motivo no completa la acción.

## 5. Requisitos no funcionales

- **RNF-MANT-001 (trazabilidad)**: Cada transición de estado de una orden (incluida la automática
  al entrar/salir de "esperando repuesto") queda registrada en la cronología de actividad de la
  propia orden, visible para quien la consulta.

## 6. Dependencias

- Coordinación de Flota: el estado "retirado de servicio" de un vehículo con orden abierta impide
  que inicie turno.
- Operaciones y Despacho: el kilometraje acumulado que alimenta la proyección preventiva proviene de
  los viajes finalizados; una incidencia con "impide continuar" reportada durante un viaje también
  llega a esta bandeja.
- Mecanismo de carga de archivos compartido, para la evidencia fotográfica.

## 7. Fuera de alcance

- Generación automática de una orden preventiva al alcanzar el umbral de kilometraje — la
  proyección es solo informativa, no dispara una orden por sí sola.
- Asignación de un mecánico específico dentro del taller — el sistema registra el taller, no el
  personal que ejecuta el trabajo.

---

**Trazabilidad**: Nivel Operativo → Departamento Mantenimiento → OP4 → CU-O07 →
`web-conductor` (pantalla "Fallas del vehículo"), `web-interno` → Mantenimiento (pestañas Órdenes /
Reportes de falla) → `backend/src/mantenimiento/`, `backend/src/reportes_falla/`.
