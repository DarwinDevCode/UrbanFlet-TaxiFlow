# Especificación operativa — Mantenimiento

Paquete: `pkg-mantenimiento` · Objetivo: OP2.4 (ejecutar y registrar las órdenes de mantenimiento de la flota) · OE2

Estados de la orden: `ABIERTA` → `EN_TALLER` → `CERRADA`; `ABIERTA` → `ANULADA`.
Estados del vehículo respecto a mantenimiento: `HABILITADO` ⇄ `RETIRADO_DE_SERVICIO`.

---

## CU-O12 — Registrar una orden de mantenimiento

**Actores:** Jefe de Mantenimiento, Conductor (origen alterno), Sistema

**Precondiciones:** el vehículo existe en la flota.

**Flujo principal:**
1. El Jefe de Mantenimiento abre la ficha del vehículo, que muestra: kilometraje acumulado (sumatoria de trazas GPS de viajes + ajustes manuales), fecha y kilometraje de la última intervención, y el plan preventivo aplicable por antigüedad del vehículo.
2. Crea la orden indicando: tipo (`PREVENTIVA` / `CORRECTIVA`), descripción del trabajo, kilometraje actual verificado en tablero, taller asignado y fecha programada.
3. Si la orden implica indisponibilidad, el Jefe marca "Retirar de servicio". El sistema pone el vehículo en `RETIRADO_DE_SERVICIO`: la bandera de Mantenimiento pasa a rojo y el conductor no puede iniciar turno con ese vehículo (flujo A5 de `operativo_flota.md`).
4. El sistema notifica al socio propietario del vehículo la orden y la fecha programada.
5. La orden queda `ABIERTA`; al ingresar el vehículo al taller, el Jefe la pasa a `EN_TALLER`.

**Flujos alternos:**
- **A1 — Origen en incidencia de viaje:** las incidencias tipo avería registradas por el conductor (CU-O07 A4) aparecen en la bandeja del Jefe como "pre-órdenes"; puede convertirlas en orden con un clic, heredando vehículo, descripción y posición del evento.
- **A2 — Umbral preventivo alcanzado:** cuando el kilometraje del vehículo supera el umbral del plan (p. ej., cada 5 000 km), el sistema crea automáticamente una pre-orden preventiva y notifica al Jefe; no retira el vehículo por sí solo.
- **A3 — Solicitud de repuesto:** desde la orden se registran los repuestos requeridos (descripción, cantidad, costo estimado); la orden puede quedar `ABIERTA` en espera de repuesto, con el motivo visible.
- **A4 — Orden anulada:** solo en estado `ABIERTA`, con motivo obligatorio; si el vehículo había sido retirado, vuelve a `HABILITADO`.

**Postcondiciones:** orden persistida con tipo, kilometraje, costos estimados y estado; vehículo retirado de servicio si aplica; notificaciones emitidas.

---

## CU-O13 — Cerrar la orden y habilitar el vehículo

**Actores:** Jefe de Mantenimiento, Sistema

**Precondiciones:** orden en `EN_TALLER`.

**Flujo principal:**
1. Concluido el trabajo, el Jefe abre la orden y registra: trabajos efectivamente realizados, repuestos consumidos con costo real, horas de taller, costo total y kilometraje de salida.
2. Marca la orden `CERRADA`. El sistema recalcula la fecha/kilometraje de la próxima intervención preventiva del vehículo.
3. Si el vehículo estaba `RETIRADO_DE_SERVICIO`, el Jefe pulsa "Habilitar vehículo": la bandera vuelve a verde y el conductor puede iniciar turno.
4. El sistema notifica al socio propietario el cierre con el detalle de costos.

**Flujos alternos:**
- **A1 — Prolongar el retiro de servicio:** si el trabajo revela un daño mayor, el Jefe cierra la orden original y abre una correctiva encadenada (referencia a la orden madre); el vehículo permanece retirado.
- **A2 — Cierre sin costos registrados:** el sistema lo impide; costo total y kilometraje de salida son obligatorios (alimentan el informe táctico de costo por vehículo, CU-T11).
- **A3 — Kilometraje de salida menor al de entrada:** validación bloqueante con opción de ajuste justificado (cambio de odómetro), que queda en la bitácora.

**Postcondiciones:** orden `CERRADA` con costos reales; vehículo `HABILITADO` (o retirado con orden encadenada); próxima intervención preventiva agendada; datos disponibles para el análisis táctico de costos.
