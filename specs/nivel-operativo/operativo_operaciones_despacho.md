# Especificación operativa — Operaciones y Despacho

Paquete: `pkg-viajes` · Objetivos: OP2.1 (asignación automática), OP2.2 (consistencia de estado del viaje) · OE2

Máquina de estados del viaje (referencia para todos los CU de este documento):

```
SOLICITADO → OFERTADO → ASIGNADO → EN_CAMINO → EN_CURSO → FINALIZADO → PAGADO
     │           │          │           │           │
     └───────────┴──────────┴───────────┴───────────┴──→ CANCELADO (con motivo y actor)
SOLICITADO → SIN_CONDUCTOR (agotados los reintentos)
```

Toda transición de estado la ejecuta exclusivamente el backend y queda sellada en la bitácora de auditoría (ver `operativo_cumplimiento.md`, CU-O17). Ningún cliente (app de pasajero o de conductor) escribe estados directamente.

---

## CU-O04 — Solicitar un viaje

**Actores:** Pasajero, Sistema

**Precondiciones:**
- Pasajero autenticado con sesión activa y perfil en estado `ACTIVO`.
- Permisos de ubicación concedidos en el dispositivo.
- El pasajero no tiene otro viaje en estado `SOLICITADO`, `OFERTADO`, `ASIGNADO`, `EN_CAMINO` ni `EN_CURSO`.

**Flujo principal:**
1. El pasajero abre el portal web y ve un mapa centrado en su ubicación (Geolocation API), con los taxis disponibles en un radio de 300 m representados como íconos anónimos (sin identidad del conductor).
2. El pasajero marca el punto de destino en el mapa o lo escribe en el buscador de direcciones (geocodificación).
3. El sistema calcula y muestra: distancia estimada de la ruta, duración estimada y **tarifa estimada** según la fórmula vigente (ver CU-O08), etiquetada explícitamente como estimación.
4. El pasajero pulsa "Solicitar taxi". El sistema crea el viaje en estado `SOLICITADO` con: `pasajero_id`, coordenadas y dirección de origen, coordenadas y dirección de destino, timestamp de solicitud, tarifa estimada y franja tarifaria (diurna/nocturna) determinada por la hora de solicitud.
5. El sistema dispara el proceso de asignación automática (CU-O05) y muestra al pasajero una pantalla de espera con animación de búsqueda y botón "Cancelar solicitud".

**Flujos alternos:**
- **A1 — Pasajero sin destino marcado:** el botón "Solicitar taxi" se habilita igualmente. El viaje se crea con `destino = null`; la tarifa estimada no se muestra y el cierre del viaje sigue el flujo alterno A3 de CU-O08 (destino = ubicación al finalizar).
- **A2 — GPS desactivado o sin permiso:** el portal bloquea la solicitud y muestra el paso para conceder el permiso de ubicación del navegador. No se permite ingresar origen manual (previene fraude de posición).
- **A3 — Pasajero con viaje activo:** el sistema rechaza la creación con error `TRIP_ALREADY_ACTIVE` y redirige a la pantalla del viaje en curso.
- **A4 — Cancelación durante la búsqueda:** si el pasajero cancela mientras el viaje está en `SOLICITADO` u `OFERTADO`, el viaje pasa a `CANCELADO` con `motivo=CANCELADO_PASAJERO_PREVIO` y sin penalización. Las ofertas pendientes a conductores se retiran con notificación de "solicitud retirada".
- **A5 — Pérdida de conexión del pasajero durante la búsqueda:** la búsqueda continúa en el servidor. Al reconectar o recargar la página, el portal consulta `GET /viajes/activo` y restaura la pantalla que corresponda al estado real.

**Postcondiciones:** viaje persistido en estado `SOLICITADO` (o `CANCELADO`), con origen, destino (si existe), tarifa estimada, franja tarifaria y timestamps. Evento registrado en la bitácora.

---

## CU-O05 — Asignar conductor (auto-despacho)

**Actores:** Sistema (actor principal), Conductor (receptor de la oferta)

**Precondiciones:**
- Existe un viaje en estado `SOLICITADO`.
- El registro de posiciones de flota está actualizado (ver `operativo_flota.md`).

**Flujo principal:**
1. El sistema construye la lista de candidatos: conductores en estado `DISPONIBLE`, con documentación vigente (bandera de Cumplimiento en verde), con vehículo habilitado (bandera de Mantenimiento en verde) y con última posición GPS a menos de 60 segundos de antigüedad, dentro de un radio inicial de 300 m del origen.
2. El sistema ordena los candidatos por: (1º) distancia en ruta al origen, (2º) tiempo desde su último viaje finalizado (reparte trabajo entre socios), (3º) calificación promedio.
3. El sistema envía la oferta al primer candidato (CU-O06) y marca el viaje como `OFERTADO`. La oferta expira en **20 segundos**.
4. Si el conductor acepta, el sistema valida que el conductor siga `DISPONIBLE` (protección contra doble asignación), transiciona el viaje a `ASIGNADO`, marca al conductor como `OCUPADO` y calcula la ruta óptima conductor → origen.
5. El sistema notifica al pasajero la asignación con: nombre y foto del conductor, teléfono enmascarado, calificación promedio, placa, marca y color del vehículo, y tiempo estimado de llegada.
6. A partir de este punto el pasajero ve en el mapa únicamente el vehículo asignado, en tiempo real.

**Flujos alternos:**
- **A1 — El conductor rechaza o expira la oferta:** el sistema pasa al siguiente candidato de la lista. El rechazo/expiración se registra por conductor (insumo del informe táctico de cancelaciones).
- **A2 — Lista agotada en el radio:** el sistema amplía el radio a 600 m y luego a 1 000 m, reconstruyendo la lista en cada ampliación. Máximo **3 radios** y **10 ofertas totales** por solicitud.
- **A3 — Reintentos agotados:** el viaje pasa a `SIN_CONDUCTOR`. El pasajero recibe la opción "Reintentar búsqueda" (crea una nueva solicitud reutilizando origen/destino). El evento alimenta la alerta de zona desatendida (CU-T08).
- **A4 — Doble aceptación simultánea:** la aceptación es una operación condicional sobre el estado del viaje (`OFERTADO` + `conductor_ofertado_id` correcto). El segundo intento recibe `OFFER_NO_LONGER_AVAILABLE`.
- **A5 — El conductor asignado se desconecta antes de llegar:** si su posición no se actualiza por más de 120 segundos, el sistema le notifica; a los 180 segundos reabre la asignación (viaje vuelve a `SOLICITADO`, conductor pasa a `FUERA_DE_LINEA`) y notifica al pasajero "buscando un nuevo conductor".

**Postcondiciones:** viaje en `ASIGNADO` con `conductor_id` y `vehiculo_id`, o en `SIN_CONDUCTOR`. Cada oferta, respuesta y expiración registrada con timestamps.

---

## CU-O06 — Ofrecer el viaje al conductor

**Actores:** Conductor, Sistema

**Precondiciones:** el conductor está `DISPONIBLE` y fue seleccionado como candidato por CU-O05.

**Flujo principal:**
1. El conductor recibe una notificación de pantalla completa con cuenta regresiva de 20 segundos.
2. Antes de decidir, ve: ubicación del pasajero en el mapa, distancia y tiempo estimado hasta el origen, nombre de pila y calificación promedio del pasajero, y si existe destino, la zona de destino (no la dirección exacta, para evitar rechazo selectivo por destino).
3. El conductor pulsa "Aceptar" o "Rechazar".
4. Si acepta, el portal cambia a modo navegación hacia el origen y habilita el canal de chat y llamada con el pasajero (CU-O07 paso 2).

**Flujos alternos:**
- **A1 — Sin respuesta en 20 segundos:** la oferta expira y cuenta como rechazo pasivo para las métricas del conductor.
- **A2 — El conductor cambió de estado entre la selección y la entrega de la oferta:** la oferta no se muestra; el sistema salta al siguiente candidato.
- **A3 — Notificación no entregada (dispositivo sin conexión):** la expiración del lado del servidor opera igual; el conductor cuya conexión falla repetidamente pasa a `FUERA_DE_LINEA` automático.

**Postcondiciones:** respuesta del conductor registrada (aceptada / rechazada / expirada) con timestamp.

---

## CU-O07 — Ejecutar el viaje

**Actores:** Conductor, Pasajero, Sistema

**Precondiciones:** viaje en estado `ASIGNADO`.

**Flujo principal:**
1. El conductor conduce hacia el origen siguiendo la ruta trazada; el viaje pasa a `EN_CAMINO`. El pasajero ve la posición del vehículo y el ETA actualizado en tiempo real.
2. Pasajero y conductor disponen de chat de texto y llamada (con número enmascarado) mientras el viaje esté activo.
3. Al llegar al punto de origen, el conductor pulsa "He llegado"; el pasajero recibe la notificación de arribo.
4. Cuando el pasajero aborda, el conductor pulsa "Iniciar viaje". El sistema valida que la posición del vehículo esté a menos de 150 m del origen declarado y transiciona a `EN_CURSO`, iniciando el registro de la traza GPS (puntos cada 5 segundos) y el contador de tiempo de viaje.
5. Durante el trayecto el sistema acumula distancia recorrida (por odómetro GPS sobre la traza) y minutos de espera (velocidad < 10 km/h).
6. El viaje continúa hasta el flujo de finalización (CU-O08).

**Flujos alternos:**
- **A1 — El pasajero no aparece:** tras 5 minutos de espera en el origen, el conductor puede pulsar "Pasajero ausente". El viaje pasa a `CANCELADO` con `motivo=NO_SHOW_PASAJERO`; se registra para el análisis de cancelaciones. La política de cobro de no-show es una decisión pendiente de la junta (parámetro `cobro_no_show`, por defecto desactivado).
- **A2 — Cancelación del pasajero con conductor en camino:** permitida; se registra `motivo=CANCELADO_PASAJERO_EN_CAMINO` con la distancia ya recorrida por el conductor (insumo para una futura política de compensación).
- **A3 — Cancelación del conductor:** permitida solo antes de `EN_CURSO`, con selección obligatoria de motivo. El viaje vuelve a `SOLICITADO` y se reasigna (CU-O05) sin que el pasajero repita la solicitud.
- **A4 — Incidencia en ruta (avería, siniestro):** el conductor pulsa "Registrar incidencia", selecciona el tipo y el sistema notifica al Coordinador de Operaciones. Si la incidencia impide continuar, el viaje pasa a `CANCELADO` con `motivo=INCIDENCIA`, se registra la posición del evento y se dispara una nueva solicitud automática para el pasajero desde esa posición.
- **A5 — Pérdida de conexión durante `EN_CURSO`:** el portal del conductor almacena la traza localmente en IndexedDB y la sincroniza al reconectar. El estado del viaje no se pierde: el servidor es la fuente de verdad y ambos portales restauran el estado con `GET /viajes/activo` al reconectar. Si la desconexión supera 15 minutos, el sistema marca el viaje `EN_REVISION` para cierre manual por el Coordinador.
- **A6 — Desvío mayor de ruta:** si la posición se aleja más de 2 km de la ruta prevista sin recálculo, el sistema recalcula la ruta y lo registra; no interviene (el pasajero puede haber cambiado el destino de palabra), pero el dato queda para auditoría.

**Postcondiciones:** viaje en `EN_CURSO` con traza GPS acumulándose, o cancelado con motivo, actor y posición registrados.

---

## CU-O08 — Finalizar el viaje

**Actores:** Conductor, Pasajero, Sistema

**Precondiciones:** viaje en estado `EN_CURSO`.

**Flujo principal:**
1. Al llegar al destino, el conductor pulsa "Finalizar viaje".
2. El sistema cierra la traza GPS y calcula la **tarifa final** con la fórmula regulada (metodología ANT de tarifas de taxi, con valores parametrizados por la junta):

```
tarifa = arrancada
       + (costo_km × km_recorridos)
       + (costo_min_espera × minutos_espera)
tarifa_final = max(tarifa, carrera_minima)
```

   Parámetros por franja (valores iniciales de referencia, configurables sin despliegue):

   | Parámetro | Diurna (05:00–22:00) | Nocturna (22:00–05:00) |
   |---|---|---|
   | Arrancada | $0.50 | $0.60 |
   | Costo por km | $0.35 | $0.40 |
   | Costo por minuto de espera | $0.07 | $0.09 |
   | Carrera mínima | $1.50 | $1.75 |

   La franja aplicable es la de la hora de **inicio** del viaje (`EN_CURSO`). Los kilómetros se toman de la traza GPS; los minutos de espera son los acumulados con velocidad < 10 km/h.
3. El sistema muestra la tarifa final a ambos actores con el desglose de los tres rubros.
4. El viaje pasa a `FINALIZADO` y el sistema dispara el registro del pago (CU-O09, Control Financiero).
5. El pasajero recibe la pantalla de calificación (1–5 estrellas + comentario opcional); el conductor califica al pasajero de igual forma. Ambas calificaciones son opcionales y pueden emitirse hasta 24 horas después.
6. El conductor vuelve automáticamente al estado `DISPONIBLE`.

**Flujos alternos:**
- **A1 — Discrepancia entre tarifa estimada y final mayor al 30%:** el sistema la muestra igualmente pero marca el viaje con `revision_tarifa=true` para el muestreo de auditoría de Control Financiero.
- **A2 — Traza GPS incompleta (desconexión no recuperada):** el sistema calcula con los tramos disponibles y estima el tramo faltante con la ruta óptima entre el último punto conocido y el destino; el viaje queda marcado `tarifa_estimada_parcial=true` y entra a revisión.
- **A3 — Viaje sin destino marcado:** el conductor finaliza manualmente; el sistema registra como destino las coordenadas del punto donde se pulsó "Finalizar viaje" y calcula la tarifa con la traza real.
- **A4 — Finalización lejos del destino declarado (> 500 m):** se permite (el pasajero pudo bajarse antes); el sistema registra el destino real y conserva el declarado para análisis.

**Postcondiciones:** viaje `FINALIZADO` con ruta completa, distancia, minutos de espera, desglose tarifario, franja aplicada y calificaciones (si se emitieron). Pago disparado hacia Control Financiero. El registro queda disponible para el pipeline analítico nocturno.

---

## CU-O14 — Consultar el historial de viajes

**Actores:** Pasajero, Conductor

**Precondiciones:** usuario autenticado.

**Flujo principal:**
1. El usuario abre "Mis viajes" y ve la lista paginada de sus viajes ordenada por fecha descendente: fecha y hora, origen → destino, tarifa final, estado y calificación.
2. Puede filtrar por rango de fechas y por estado (finalizados / cancelados).
3. Al abrir un viaje ve el detalle completo: mapa con la ruta recorrida, desglose de tarifa, datos de la contraparte (limitados: nombre y calificación) y estado del pago.
4. Desde el detalle puede emitir el comprobante del viaje en PDF, que incluye los datos fiscales de la cooperativa.

**Flujos alternos:**
- **A1 — Solicitud de comprobante de un viaje cancelado o impago:** el botón no se muestra; solo los viajes `PAGADO` emiten comprobante.
- **A2 — Conductor consultando datos del pasajero:** el historial del conductor muestra del pasajero solo nombre de pila y calificación; nunca teléfono ni historial de ubicaciones.

**Postcondiciones:** cada emisión de comprobante queda registrada con folio secuencial.
