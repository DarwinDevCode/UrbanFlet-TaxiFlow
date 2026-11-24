# Especificación: Operaciones y Despacho (Nivel Operativo)

> Documento retroactivo. Fuente principal: `AUDITORIA_FUNCIONAL_OPERATIVO.md` §2, verificada contra
> el código real (`backend/src/viajes/`).

## 1. Objetivo

Gestionar el ciclo de vida completo de un viaje: desde que el pasajero lo pide hasta que ambas
partes se califican, incluidos los caminos alternos (sin conductor disponible, cancelación,
incidencia en ruta, viaje programado, compartir seguimiento con un tercero).

## 2. Contexto

Es el proceso central de todo el negocio — sin esto no hay actividad de la cooperativa. Requiere
coordinar en tiempo real a dos partes que no se conocen de antemano (pasajero y conductor), sobre un
mapa compartido, con una tarifa que se calcula sobre datos reales de recorrido, no un estimado fijo.

## 3. Actores

- **`pasajero`** — solicita, cancela, comparte el seguimiento, califica, recibe el cobro.
- **`conductor`** — inicia turno, acepta/rechaza ofertas, ejecuta el viaje, cobra, califica.
- **`coordinador_operaciones`** (personal interno) — recibe avisos de incidencia operativa en vivo;
  no interviene en el flujo normal.

## 4. Requisitos funcionales

### RF-DES-001 — Turno del conductor
El conductor debe poder iniciar/terminar turno, con reporte de posición real (permiso de
geolocalización del navegador). Sin al menos un conductor `DISPONIBLE`, ningún viaje puede
asignarse.

### RF-DES-002 — Solicitar un viaje
El pasajero debe poder fijar un destino (tocando el mapa o eligiendo una dirección favorita) y ver
distancia/duración/tarifa estimadas antes de confirmar. Alternativa: programar el viaje entre 15
minutos y 7 días en el futuro (`PROGRAMADO`), despachado automáticamente por un proceso cada 2
minutos que reutiliza el mismo mecanismo de auto-despacho, sin duplicar lógica.

### RF-DES-003 — Auto-despacho al conductor disponible más cercano
El sistema debe ofrecer el viaje al conductor `DISPONIBLE` más cercano, con un tiempo límite de
respuesta configurable (20 segundos por defecto). Si expira o rechaza, debe ofrecer a otro. Si nadie
responde en ningún radio, el viaje pasa a `SIN_CONDUCTOR` con la opción de "Reintentar búsqueda"
reutilizando el mismo origen/destino sin pedirlo de nuevo.

### RF-DES-004 — Ejecución del viaje
El conductor debe poder marcar, en secuencia: "Voy en camino" → "He llegado" → "Iniciar viaje" →
"Finalizar viaje". El sistema debe rechazar "Iniciar viaje" si el vehículo está a más de 150m del
origen reportado.

### RF-DES-005 — Compartir seguimiento en vivo
Mientras el viaje está `EN_CAMINO` o `EN_CURSO`, el pasajero debe poder generar un enlace público
(`/compartido/<token>`), sin necesidad de sesión de quien lo abre, con datos del conductor/vehículo y
mapa. El enlace se invalida automáticamente al finalizar o cancelarse el viaje.

### RF-DES-006 — Cancelación con motivo
Cualquiera de las dos partes debe poder cancelar el viaje en cualquier punto antes de finalizar,
eligiendo un motivo de un catálogo (o "Otro" con texto libre).

### RF-DES-007 — Registro de incidencia/avería del conductor
Con el viaje `EN_CURSO`, el conductor debe poder reportar una falla del vehículo desde un catálogo
cerrado de tipos. Si marca "No puedo continuar", el sistema debe cancelar ese viaje y generar
automáticamente uno nuevo para el pasajero desde la posición del incidente, y notificar en vivo al
`coordinador_operaciones`.

### RF-DES-008 — Desglose de tarifa al finalizar
Al finalizar, el sistema debe calcular y mostrar a ambas partes la tarifa desglosada: arrancada +
distancia real recorrida + tiempo de espera, con "Carrera mínima aplicada" visible únicamente si el
subtotal no alcanzaba el piso mínimo.

### RF-DES-009 — Cobro en efectivo
El conductor debe poder ingresar el monto efectivamente cobrado. Si no coincide con la tarifa final,
el viaje debe entrar a la bandeja de discrepancias del proceso de Control Financiero, sin bloquear
la finalización.

### RF-DES-010 — Calificación mutua
Al finalizar el cobro, ambas partes deben poder calificar de 1 a 5 estrellas con comentario
opcional, o "Omitir" — calificar no es obligatorio para seguir usando la app.

### RF-DES-011 — Historial propio de viajes, con mapa del recorrido
Cada parte debe poder consultar sus propios viajes cerrados, con el desglose de tarifa, la
calificación recibida, la foto de la contraparte, y un mapa del recorrido real (traza GPS
acumulada) — nunca una ruta inventada cuando no hay traza real.

## 5. Requisitos no funcionales

### RNF-DES-001 — Protección anti-suplantación de GPS
El sistema debe rechazar reportes de posición que impliquen un salto geográfico imposible entre dos
lecturas consecutivas, registrando el intento como `POSIBLE_GPS_SPOOFING`.

### RNF-DES-002 — Contraparte limitada
El conductor solo ve nombre de pila y calificación del pasajero (nunca teléfono ni historial de
ubicación) — mismo límite aplicado a la foto de perfil cuando se agregó.

### RNF-DES-003 — Traza GPS acotada por endpoint
La traza del recorrido solo se expone en 2 endpoints de todo el sistema, cada uno con su propio
alcance de rol verificado por tests explícitos — nunca en un listado (RN-SIS-011).

## 6. Reglas de negocio

### RN-DES-001
El ciclo de vida completo del viaje vive como overlay sobre un mapa persistente — nunca cambia de
pantalla (RN-SIS-009).

### RN-DES-002
Un viaje `EN_CURSO` cancelado por incidencia (RF-DES-007) nunca reutiliza el mismo documento —
genera uno nuevo, porque el viaje interrumpido ya acumuló traza/km reales de un tramo incompleto que
contaminaría un viaje que arranca de cero.

### RN-DES-003
La línea "Carrera mínima aplicada" solo aparece cuando el piso realmente se activó — nunca se
muestra de forma incondicional.

## 7. Entradas

- Pasajero: origen (geolocalización o mapa), destino, modo (ahora/programar + fecha/hora).
- Conductor: aceptar/rechazar oferta, transiciones de estado, monto cobrado, calificación.
- Ambos: motivo de cancelación, calificación + comentario opcional.

## 8. Salidas

- Estado del viaje en tiempo real para ambas partes.
- Tarifa desglosada al finalizar.
- Enlace público de seguimiento (opcional).
- Historial consultable con mapa del recorrido.

## 9. Estados posibles

`PROGRAMADO` → `SOLICITADO` → `OFERTADO` → `ASIGNADO` → `EN_CAMINO` → `EN_CURSO` → `FINALIZADO` →
`PAGADO`. Caminos alternos: `CANCELADO` (desde cualquier estado activo), `SIN_CONDUCTOR` (desde
`SOLICITADO`/`OFERTADO` si se agotan los radios de búsqueda).

## 10. Escenarios

### Escenario 1: Ciclo completo exitoso
Dado que hay un conductor `DISPONIBLE`
Cuando el pasajero solicita, el conductor acepta, ejecuta el viaje y lo finaliza con el cobro
correcto
Entonces el viaje queda `PAGADO`, con calificación de ambas partes y visible en el historial de las
2 cuentas.

### Escenario 2: Sin conductor disponible, reintento exitoso
Dado que ningún conductor está `DISPONIBLE` al momento de solicitar
Cuando el pasajero ve "No se encontró conductor disponible" y pulsa "Reintentar búsqueda" después de
que un conductor se pone en línea
Entonces se genera una nueva oferta real con el mismo origen/destino, sin pedirlos de nuevo.

### Escenario 3: Incidencia que impide continuar
Dado que un conductor con viaje `EN_CURSO` reporta una avería y marca "No puedo continuar"
Cuando confirma el reporte
Entonces ese viaje se cancela, se crea uno nuevo automáticamente para el mismo pasajero desde la
posición del incidente, y `coordinador_operaciones` recibe un aviso en vivo.

### Escenario 4: Viaje corto con carrera mínima
Dado que un viaje recorrido es muy corto
Cuando se finaliza
Entonces el subtotal calculado no alcanza el mínimo y aparece la línea "Carrera mínima aplicada" con
el ajuste correspondiente.

### Escenario 5: Compartir viaje sin sesión
Dado que un viaje está `EN_CAMINO`
Cuando el pasajero genera el enlace de compartir y un tercero lo abre sin ninguna cuenta
Entonces ve el estado, conductor, placa y mapa reales, sin poder acceder a nada más del sistema.

## 11. Criterios de aceptación

Reusa `PLAN_DE_PRUEBAS.md`:
- **PD-01** — Ciclo de vida completo, con verificación técnica en Mongo.
- **PD-09** — Mapa del recorrido en sus 3 estados (con traza / sin traza / sin destino).
- **PU-01**/**PU-02** — Versión en lenguaje simple, pedir y cobrar/calificar.
- **PU-09** — Ver por dónde pasó un viaje, en lenguaje simple.
- **TU-01** — Pasajero consigue un taxi por primera vez, sin instrucciones, hasta calificar.
- **TU-02** — Cancelar y volver a intentar.
- **TU-03** — Encontrar un viaje concreto en el historial (expone la carencia real de que no hay
  búsqueda por texto, solo por estado/fecha).
- **TU-04** — Conductor completa un turno de principio a fin, sin instrucciones.

### CA-DES-001
Un viaje completado de punta a punta queda `PAGADO`, con `desglose_tarifa` poblado y ambas
calificaciones en Mongo.

### CA-DES-002
Un viaje sin traza GPS muestra en el mapa del historial solo los 2 marcadores, sin ninguna línea, y
un texto explicando por qué.

## 12. Dependencias

- **003-operativo/coordinacion-de-flota** — comparte los datos de posición/turno del conductor.
- **003-operativo/control-financiero** — el cobro en efectivo alimenta discrepancias y
  liquidaciones.
- **003-operativo/mantenimiento** — el kilometraje acumulado de cada viaje alimenta la proyección
  de mantenimiento preventivo.
- **004-transversal/notificaciones** — cada transición relevante dispara notificaciones reales.
- **004-transversal/administracion-del-sistema** (Parámetros globales) — radio de despacho y
  segundos de expiración de oferta son configurables ahí, no fijos en código.

## 13. Fuera de alcance

- **Pago electrónico/pasarela** — solo efectivo implementado.
- **Chat o llamada en vivo** entre pasajero y conductor.
- **Comprobante de viaje en PDF** con folio fiscal.
- **Corrección de una tarifa post-pago** vía nota de ajuste automática.
