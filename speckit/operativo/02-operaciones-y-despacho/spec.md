# Especificación: Departamento de Operaciones y Despacho

**Nivel:** Operativo · **Objetivo que respalda:** OP2 — Atención completa de cada solicitud de
viaje · **Responsable:** Coordinador de Operaciones

## 1. Objetivo

Atender cada solicitud de viaje con asignación automática de conductor, manteniendo consistente el
estado del viaje de principio a fin —incluidos los caminos alternos que puede tomar (programación,
reintento, cancelación, incidencia)— y calculando la tarifa final de forma verificable.

## 2. Contexto

El despacho automático es el proceso central del negocio: no hay un operador humano decidiendo qué
conductor atiende cada solicitud. Eso exige que el sistema pueda: encontrar un conductor disponible
sin intervención, sostener el estado del viaje sincronizado en tiempo real entre pasajero y
conductor, y calcular una tarifa que ambas partes puedan verificar al terminar.

## 3. Usuarios o actores

- **Pasajero** — solicita, sigue y cierra el viaje desde su portal.
- **Conductor** — recibe la oferta, ejecuta el viaje, cobra.
- **Sistema** — asigna el conductor, calcula tarifa, dispara viajes programados, genera la
  solicitud de reemplazo tras una incidencia.

## 4. Funcionalidad 1 — Ciclo de vida del viaje (CU-O03)

### 4.1 Requisitos funcionales

**Solicitud y despacho**

- **RF-DESP-001**: El sistema debe permitir al pasajero fijar su destino tocando el mapa o
  eligiendo una dirección favorita, y mostrar distancia, duración y tarifa estimadas antes de
  confirmar.
- **RF-DESP-002**: El sistema debe permitir programar el viaje para una fecha y hora futuras, entre
  15 minutos y 7 días desde el momento de la solicitud, en lugar de despacharlo de inmediato.
- **RF-DESP-003**: El sistema debe ofrecer automáticamente el viaje al conductor disponible más
  cercano, ampliando el radio de búsqueda en pasos sucesivos (300 m, 600 m, 1000 m) y probando hasta
  10 candidatos en total si los anteriores no responden a tiempo.
- **RF-DESP-004**: Si ningún conductor acepta dentro de los radios y candidatos disponibles, el
  sistema debe dejar el viaje en estado "sin conductor" y ofrecer al pasajero reintentar la búsqueda
  reutilizando el mismo origen y destino.
- **RF-DESP-005**: Cuando llega su hora, el sistema debe disparar automáticamente el despacho de un
  viaje programado, sin intervención del pasajero.

**Seguimiento**

- **RF-DESP-006**: El sistema debe permitir al conductor avanzar el viaje por los estados "voy en
  camino", "he llegado" e "iniciar viaje", y reflejar cada cambio en la pantalla del pasajero sin
  que este recargue nada.
- **RF-DESP-007**: El sistema debe exigir que el conductor esté físicamente cerca del origen (dentro
  de 150 metros) para poder iniciar el viaje.
- **RF-DESP-008**: El sistema debe permitir al pasajero generar un enlace público de solo lectura
  para que un tercero sin cuenta siga el viaje en curso; el enlace deja de funcionar al finalizar o
  cancelarse el viaje, o pasadas 4 horas desde que se generó, lo que ocurra primero.

**Finalización y cobro**

- **RF-DESP-009**: Al finalizar, el sistema debe calcular la tarifa como la suma de tres rubros
  (arrancada, distancia recorrida y tiempo de espera) y mostrar el desglose completo a ambas partes,
  incluyendo si se aplicó una carrera mínima por no alcanzar el piso tarifario.
- **RF-DESP-010**: El sistema debe permitir al conductor registrar el monto cobrado en efectivo; si
  no coincide con la tarifa calculada, el pago queda señalado con la diferencia para revisión del
  Control Financiero.
- **RF-DESP-011**: El sistema debe permitir a pasajero y conductor calificarse mutuamente de 1 a 5,
  con comentario opcional, una vez pagado el viaje.

**Cancelación e incidencias**

- **RF-DESP-012**: El sistema debe permitir a cualquiera de las dos partes cancelar el viaje antes
  de finalizarlo, exigiendo un motivo del catálogo (o uno libre si ninguno aplica).
- **RF-DESP-013**: El sistema debe permitir al conductor registrar una avería durante el viaje; si
  indica que le impide continuar, el sistema debe cancelar ese viaje y generar automáticamente una
  nueva solicitud para el pasajero desde la posición donde ocurrió el incidente, sin que el pasajero
  tenga que volver a pedirlo.

### 4.2 Reglas de negocio

- **RN-DESP-001**: Un pasajero no puede tener más de un viaje activo a la vez.
- **RN-DESP-002**: El estado del viaje solo avanza en un sentido: solicitado → ofertado → asignado →
  en camino → en curso → finalizado → pagado (con cancelado y sin conductor como salidas posibles
  antes de finalizar).
- **RN-DESP-003**: La tarifa final nunca es menor que la carrera mínima vigente, sin importar cuán
  corto haya sido el viaje.
- **RN-DESP-004**: Cancelar y registrar una incidencia con "impide continuar" exigen ambos un motivo
  no vacío.
- **RN-DESP-005**: El enlace de viaje compartido nunca expone datos de contacto del conductor ni del
  pasajero — solo nombre, calificación, vehículo y posición en vivo.

### 4.3 Entradas

Origen (posición o dirección buscada), destino, hora deseada (inmediata o programada), motivo de
cancelación o de incidencia, monto cobrado, calificación y comentario.

### 4.4 Salidas

Viaje con su estado actualizado en tiempo real, tarifa estimada y luego desglosada, enlace de
seguimiento cuando se solicita, calificación registrada.

### 4.5 Escenarios

**Escenario: viaje completo exitoso**
Dado que un conductor tiene el turno iniciado y está disponible
Cuando un pasajero solicita un viaje y el conductor acepta la oferta
Entonces el viaje avanza por sus estados hasta finalizar, se calcula y muestra la tarifa
desglosada, el conductor registra el cobro, y ambas partes pueden calificarse.

**Escenario: sin conductor disponible**
Dado que ningún conductor responde dentro de los radios de búsqueda
Cuando se agotan los candidatos
Entonces el viaje queda en estado "sin conductor" y el pasajero puede reintentar con el mismo
origen y destino.

**Escenario: incidencia que impide continuar**
Dado que un conductor tiene un viaje en curso
Cuando reporta una avería marcando que le impide continuar
Entonces el sistema cancela ese viaje y genera automáticamente una nueva solicitud para el pasajero
desde la posición del incidente.

**Escenario: discrepancia de cobro**
Dado que la tarifa calculada es $2.87
Cuando el conductor registra haber cobrado $2.50
Entonces el pago queda marcado con una diferencia de $0.37 visible para el Control Financiero.

### 4.6 Criterios de aceptación

- **CA-DESP-001**: Un viaje llevado hasta el pago muestra a ambas partes el mismo desglose de
  tarifa (arrancada + distancia + espera = subtotal, con la carrera mínima cuando corresponde).
- **CA-DESP-002**: Un viaje sin conductor tras agotar los 10 candidatos ofrece el botón de
  reintentar, y el reintento reutiliza el origen/destino original.
- **CA-DESP-003**: Un enlace de viaje compartido, abierto sin sesión, muestra la posición en vivo y
  deja de responder una vez finalizado el viaje.
- **CA-DESP-004**: Una incidencia con "impide continuar" marcado dentro de un viaje en curso deja
  ese viaje cancelado y crea uno nuevo activo para el mismo pasajero.

## 5. Funcionalidad 2 — Consulta del historial propio de viajes (CU-O04)

### 5.1 Requisitos funcionales

- **RF-DESP-014**: El sistema debe permitir a pasajero y conductor consultar sus viajes anteriores,
  con fecha, destino, tarifa y estado, más reciente primero, filtrable por estado y rango de fechas.
- **RF-DESP-015**: El sistema debe mostrar, en el detalle de cada viaje, el desglose de tarifa, la
  calificación intercambiada, y un mapa con el recorrido real cuando el viaje registró posiciones
  durante su ejecución.
- **RF-DESP-016**: El sistema debe limitar lo que el conductor ve del pasajero a su nombre de pila y
  calificación — nunca teléfono, correo ni historial de ubicaciones.

### 5.2 Reglas de negocio

- **RN-DESP-006**: El mapa del historial solo dibuja una línea de recorrido cuando existe una traza
  GPS real registrada durante el viaje; si no existe, se muestran únicamente los puntos de origen y
  destino, sin inventar una ruta.

### 5.3 Entradas

Filtro de estado, rango de fechas.

### 5.4 Salidas

Lista paginada de viajes propios; detalle completo de uno seleccionado.

### 5.5 Escenarios

**Escenario: consulta con recorrido real**
Dado que un viaje ya finalizado acumuló puntos de posición durante su ejecución
Cuando el pasajero abre su detalle en el historial
Entonces el mapa dibuja el recorrido real seguido por el vehículo.

**Escenario: viaje sin traza registrada**
Dado que un viaje se canceló antes de que el conductor reportara ninguna posición
Cuando se abre su detalle
Entonces el mapa muestra solo los marcadores disponibles y declara que no hay recorrido registrado,
sin trazar una línea recta como si lo fuera.

### 5.6 Criterios de aceptación

- **CA-DESP-005**: El historial de un conductor nunca expone el teléfono ni el correo del pasajero
  en ninguna fila ni en el detalle.
- **CA-DESP-006**: Un viaje con traza GPS real muestra el recorrido dibujado; uno sin ella muestra
  el estado que lo declara explícitamente.

## 6. Requisitos no funcionales

- **RNF-DESP-001 (usabilidad)**: El estado del viaje se refleja en la pantalla del pasajero sin
  requerir una acción manual de refresco mientras la app permanece abierta.
- **RNF-DESP-002 (seguridad)**: El enlace de viaje compartido usa un token de 256 bits, no
  adivinable ni enumerable.

## 7. Dependencias

- Coordinación de Flota (CU-O05): el despacho depende de que existan conductores con turno activo y
  posición reportada.
- Cumplimiento Regulatorio: catálogo de motivos de cancelación.
- Mantenimiento (CU-O07): un reporte de incidencia con "impide continuar" también genera, en
  paralelo, una notificación al departamento de Mantenimiento.
- Control Financiero (CU-O08): las discrepancias de cobro alimentan la bandeja de conciliación.

## 8. Fuera de alcance

- Pago electrónico o por pasarela — solo se registra cobro en efectivo.
- Chat o llamada en vivo entre pasajero y conductor.
- Comprobante de viaje en PDF.
- Corrección de una tarifa ya conciliada mediante una nota de ajuste posterior al pago.

---

**Trazabilidad**: Nivel Operativo → Departamento Operaciones y Despacho → OP2 → CU-O03/CU-O04 →
`web-pasajero`, `web-conductor` (pantalla "Viaje"/"Mi turno", "Mis viajes") →
`backend/src/viajes/` (`service.py`, `service_dispatch.py`, `service_ejecucion.py`,
`service_finalizacion.py`, `service_compartir.py`, `service_historial.py`).
