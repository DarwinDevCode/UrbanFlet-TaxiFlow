# Especificación operativa — Control Financiero

Paquetes: `pkg-recaudacion`, `pkg-finanzas-ctrl` · Objetivos: OP5.1 (registrar y validar cada pago), OP5.2 (calcular comisión y emitir liquidación) · OE5

Regla inviolable del departamento (heredada del control de integridad financiera, OE5): **ningún pago cuyo monto no sea consistente con la tarifa calculada del viaje entra al circuito de liquidación.** Los registros inconsistentes van a cuarentena, nunca se corrigen en silencio.

---

## CU-O09 — Registrar el pago del viaje

**Actores:** Sistema, Pasajero, Conductor

**Precondiciones:** viaje en estado `FINALIZADO` con tarifa final calculada.

**Flujo principal:**
1. Al finalizar el viaje, el portal del pasajero muestra la tarifa y el método de pago: `EFECTIVO` (por defecto) o `TARJETA/BILLETERA` si la cooperativa tiene pasarela activa.
2. **Efectivo:** el pasajero paga en mano; el conductor pulsa "Pago recibido" e ingresa el monto cobrado. El sistema valida `monto_cobrado == tarifa_final` (tolerancia $0.00; el redondeo ya está resuelto en la tarifa).
3. **Electrónico:** el sistema envía el cobro a la pasarela y espera la confirmación (webhook); registra referencia externa, monto confirmado y comisión de pasarela.
4. Con el pago validado, el sistema crea el registro de recaudación: `viaje_id`, monto, método, timestamps, `conductor_id`, y transiciona el viaje a `PAGADO`.
5. El registro queda disponible para el cálculo de comisión (CU-O10) y para la conciliación diaria.

**Flujos alternos:**
- **A1 — Monto de efectivo distinto a la tarifa:** el registro se acepta pero entra en estado `DISCREPANCIA` con la diferencia calculada; no pasa a liquidación. Aparece en la bandeja de discrepancias del Administrador Financiero (informe simple "viaje sin pago / pago sin viaje" de CU-T09), quien resuelve con un ajuste justificado (CU-T09 «extend»).
- **A2 — Pago electrónico rechazado:** el pasajero puede reintentar o cambiar a efectivo; el intento fallido queda registrado con el código de la pasarela.
- **A3 — Webhook de confirmación no recibido:** a los 10 minutos el sistema consulta activamente el estado en la pasarela; si sigue indeterminado, el pago queda `PENDIENTE_CONFIRMACION` y el viaje no pasa a `PAGADO`. Reconsulta cada hora hasta 24 h; luego, discrepancia.
- **A4 — Viaje finalizado sin registro de pago en 24 h:** el sistema lo marca `VIAJE_SIN_PAGO` en la bandeja de discrepancias.
- **A5 — Pago duplicado (doble confirmación de webhook):** idempotencia por referencia externa; el duplicado se descarta y se registra el evento.

**Postcondiciones:** recaudación registrada (validada, en discrepancia o pendiente); viaje `PAGADO` solo si la validación pasó; evento en bitácora.

---

## CU-O10 — Calcular la comisión de la cooperativa

**Actores:** Sistema

**Precondiciones:** existe un registro de recaudación validado; hay un porcentaje de comisión vigente aprobado por la junta (parámetro versionado con fecha de vigencia).

**Flujo principal:**
1. Sobre cada recaudación validada, el sistema calcula: `comision = monto × porcentaje_vigente_a_la_fecha_del_viaje` (el porcentaje aplicable es el vigente en la fecha del viaje, no en la del cálculo) y `neto_socio = monto − comision`; en pagos electrónicos descuenta además la comisión de pasarela con regla explícita de a quién se imputa (parámetro de la junta, por defecto a la cooperativa).
2. Los tres montos se persisten redondeados a 2 decimales con redondeo bancario, junto con el porcentaje aplicado y su versión.

**Flujos alternos:**
- **A1 — Cambio de porcentaje a mitad de periodo:** cada viaje conserva su porcentaje por fecha; una liquidación puede contener viajes con porcentajes distintos y el desglose lo muestra.
- **A2 — Ajuste autorizado sobre un viaje ya calculado:** el ajuste (CU-T09) nunca modifica el registro original: crea un movimiento de ajuste vinculado, con signo, motivo y autorizador. El neto del socio resulta de la suma de movimientos.

**Postcondiciones:** comisión y neto persistidos e inmutables; los ajustes son movimientos adicionales trazables.

---

## CU-O11 — Generar la liquidación del socio conductor

**Actores:** Sistema, Administrador Financiero, Socio conductor

**Precondiciones:** cierre del periodo de liquidación (semanal, parámetro de la junta); todos los viajes del periodo del socio en estado `PAGADO` o resueltos como discrepancia/ajuste.

**Flujo principal:**
1. Al cierre del periodo, el sistema consolida por socio: viajes pagados, recaudación bruta, comisiones retenidas, ajustes del periodo y neto a liquidar. Distingue lo recaudado en efectivo (que el socio ya tiene en mano) de lo electrónico (que la cooperativa le debe transferir): `saldo = neto_electronico − comision_sobre_efectivo`.
2. El sistema emite la liquidación en estado `EMITIDA` con desglose viaje por viaje, y la notifica al socio en el portal (con Web Push si la pestaña está cerrada).
3. El Administrador Financiero revisa el lote del periodo y lo aprueba; las liquidaciones pasan a `APROBADA` y se ejecuta el movimiento (transferencia al socio o cobro al socio, según el signo del saldo).
4. Confirmado el movimiento, la liquidación pasa a `PAGADA` y el socio puede descargar su comprobante.

**Flujos alternos:**
- **A1 — Viajes con discrepancia abierta al cierre:** quedan **excluidos** de la liquidación del periodo y se arrastran al siguiente una vez resueltos; la liquidación lo indica ("N viajes en revisión").
- **A2 — Socio observa su liquidación:** desde el portal marca "Observar" con motivo; la liquidación pasa a `OBSERVADA` y bloquea su pago individual (no el del lote). El Administrador la revisa y responde con ajuste o ratificación (CU-T12 «extend»); toda la interacción queda en la bitácora.
- **A3 — Saldo negativo (socio debe comisión de efectivo):** el portal lo notifica (y Web Push si la pestaña está cerrada) con el plazo de pago; a los 2 periodos con saldo negativo impago, el sistema alerta al Administrador y puede suspender el inicio de turno del socio (parámetro de la junta).
- **A4 — Error detectado después de `PAGADA`:** la liquidación no se edita; se corrige con una nota de ajuste en el periodo siguiente, referenciando la liquidación original.

**Postcondiciones:** liquidaciones del periodo emitidas, aprobadas y pagadas con desglose completo e inmutable; observaciones y ajustes trazables; datos del periodo disponibles para los informes tácticos de margen de comisión y tiempo de liquidación.
