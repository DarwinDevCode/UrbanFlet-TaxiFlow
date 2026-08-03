# Auditoría de conformidad #2 — Backend vs. Frontend, CU por CU

Fecha: 2026-08-02

Segunda auditoría de conformidad del proyecto (ver también `auditoria_cu.md`, la primera). A diferencia de la anterior, esta evalúa **backend y frontend por separado** para cada paso/flujo de cada CU — un CU no cuenta como "construido" si solo uno de los dos lados existe. Metodología: lectura completa de cada documento de spec en `specs/nivel-operativo/`, comparado contra el código real (no contra reportes previos ni memoria de conversación).

Leyenda: **Construido** / **A medias** / **No construido**.

---

## Resumen — patrón "backend sí, frontend no" más relevante

- **CU-O01 (postulación de conductor)**: el backend modela documentos con metadatos, revisión reforzada y borrador — pero `PostulacionForm` en `web-conductor` envía `documentos: []` siempre (hardcodeado, `App.tsx:66`), es un solo paso, y nunca ofrece correo como identificador aunque el backend lo acepta.
- **CU-O05 P5**: el backend ya envía `vehiculo_marca`, `vehiculo_color`, `conductor_calificacion` — el frontend del pasajero simplemente no los renderiza (solo nombre y placa).
- **CU-O05 A3 (SIN_CONDUCTOR)**: el backend transiciona bien, pero no hay botón "Reintentar búsqueda" — el pasajero queda atascado en la UI.
- **CU-O08 P5**: el backend acepta `comentario` en la calificación — ninguna de las dos UIs de calificación tiene campo de texto para capturarlo.
- **CU-O14 P2/P3**: el backend soporta filtro de fechas y expone detalle enriquecido — el frontend no implementa ni el filtro ni ninguna vista de detalle clicable en el historial.
- **CU-O12/O13 (mantenimiento)**: `repuestos_estimados`, `repuestos_consumidos`, `horas_taller`, y `ajuste_justificado`/`motivo_ajuste` existen en el backend — cero de esos campos tienen un input en la UI.
- **CU-O17/CU-O18**: el backend dispara alertas de seguridad (`ALERTA_SEGURIDAD`) al Supervisor de Cumplimiento — no existe ningún canal en el frontend para que las vea. Tampoco hay pantalla de "bitácora de auditoría" pese a que `GET /auditoria/eventos` está listo y con RBAC correcto.
- **CU-O16**: `admin_plataforma` está autorizado en el backend (`router.py:9`) pero falta en la lista de roles del sidebar frontend (`App.tsx:75-80`) — un usuario con ese rol nunca vería la sección aunque la API le respondería bien.
- **CU-O10 A2**: el ajuste autorizado por viaje (que se había decidido corregir explícitamente en una sesión anterior) sigue sin construirse — `ajustes = 0.0` fijo en `generar_liquidaciones`, ningún movimiento tipo `AJUSTE` se crea nunca.
- **CU-O01/O02**: ningún lado captura fecha de nacimiento (bloqueo de menores) ni ofrece foto de perfil.
- **Referidos (OT1.2)**: 0% construido en ambos lados. Además, no se encontró ningún documento de spec en este repo que describa un caso de uso de "Referidos" u "OT1.2" — el término "referido" aparece una sola vez en todo `specs/`, como valor de ejemplo en un comentario de `diseno_base_datos.md` (`dim_canal`), no como caso de uso descrito.

---

## Captación

### CU-O01 — Registrar la solicitud de un conductor

| Paso/Flujo | Backend | Frontend | Detalle |
|---|---|---|---|
| P1 Listado de requisitos previo | No construido | No construido | Ni el router ni `PostulacionForm` (`App.tsx:17-114`) presentan un checklist antes de empezar. |
| P2 Cuenta con correo y teléfono, OTP | A medias | A medias | `SolicitudCrearRequest` acepta ambos (`schemas.py:49-64`); frontend solo pide teléfono, nunca correo. OTP ausente por diseño ya aprobado. |
| P3 Pasos + carga de documentos | A medias | No construido | Backend acepta metadatos de documentos, sin endpoint de subida real. Frontend envía `documentos: []` siempre (`App.tsx:66`) — un solo paso, sin componente de carga en todo el repo. |
| P4 Validar formato/tamaño/vista previa | No construido | No construido | Consecuencia directa de la ausencia de carga de archivos. |
| P5 Enviar, valida completitud, notifica admin | Construido | A medias | Backend válido y notifica; frontend llama con `enviar:true` fijo, pero nunca compone una solicitud realmente completa (sin documentos). |
| P6 Pantalla de estado con número de solicitud | No construido | A medias | El `id` se devuelve en el POST pero la pantalla `postulacion-enviada` no lo muestra (`App.tsx:1058-1069`). |
| A1 Guardar `BORRADOR`, expira 30 días | Construido (borrador) / No construido (expiración) | No construido | Sin job de expiración; frontend no ofrece "guardar y salir" en absoluto. |
| A2 Cédula ya socio activo | Construido | A medias | Error correcto, pero frontend solo muestra el mensaje genérico, sin flujo de recuperación. |
| A3 Placa ya en flota → revisión reforzada | Construido | No construido | Se calcula y se ve en la bandeja interna, pero el postulante nunca se entera — sin advertencia en `PostulacionForm`. |
| A4 OTP | N/A (diseño aprobado) | N/A | — |
| A5 Documento vencido bloquea carga | No construido | No construido | Sin carga de documentos, no aplica. |

### CU-O02 — Registrar un pasajero

| Paso/Flujo | Backend | Frontend | Detalle |
|---|---|---|---|
| P1 Crear cuenta | Construido | Construido | — |
| P2 Nombre+teléfono+correo, consentimiento con timestamp/versión | Construido | Construido | Frontend permite teléfono O correo (switch exclusivo), consentimiento correcto. |
| P3 OTP | N/A (diseño aprobado) | N/A | — |
| P4 Cuenta ACTIVO de inmediato | Construido | Construido | Login automático tras registro. |
| A1 Foto opcional, recordatorio 3er uso | No construido | No construido | Sin campo `foto` en ningún esquema ni componente. |
| A2 Teléfono duplicado → recuperación | Construido (bloqueo) | No construido | Backend evita duplicados correctamente; sin flujo de recuperación de cuenta en ningún lado. |
| A3 Menor de edad bloquea registro | No construido | No construido | Sin campo de fecha de nacimiento en ningún esquema ni formulario. |

### CU-O03 — Verificar la documentación del postulante

| Paso/Flujo | Backend | Frontend | Detalle |
|---|---|---|---|
| P1 Bandeja con semáforo de plazo | A medias | No construido | Orden por antigüedad sí; sin cálculo de semáforo verde/ámbar/rojo en ningún lado. |
| P2 Tomar (evita doble revisión) | Construido | Construido | Update condicional atómico. |
| P3 Checklist por documento CONFORME/OBSERVADO | No construido | No construido | Backend aprueba todos los documentos en bloque; frontend solo tiene una decisión global — laguna compartida, no divergencia. |
| P4 Aprobar: socio ACTIVO, vehículo HABILITADO | Construido | Construido | Transacción completa. |
| P5 Métrica de tiempo total de aprobación | A medias | No construido | Fechas se guardan, pero nunca se calcula/muestra la duración. |
| A1 Observado, lista exacta, recarga solo observados | No construido | No construido | Solo motivo de texto libre a nivel de solicitud completa. |
| A2 Rechazo, bloqueo 90 días | A medias | Construido (lo existente) | Motivo obligatorio y en bitácora sí; el bloqueo de 90 días no existe — cédula rechazada puede postular de inmediato. |
| A3 3 ciclos sugiere rechazo | No construido | No construido | Sin contador de ciclos. |
| A4 EN_VERIFICACION >24h vuelve a bandeja | No construido | No construido | Sin job. |

---

## Cumplimiento

### CU-O17 — Registrar un evento en la bitácora

| Paso/Flujo | Backend | Frontend | Detalle |
|---|---|---|---|
| P1 Campos completos | Construido (falta ip/dispositivo) | N/A | `ip`/`dispositivo` existen en el esquema pero nunca se pasan desde ningún caller — siempre `null`. |
| P2 Catálogo de eventos sensibles | Construido | N/A | Cobertura completa. |
| P3 Solo inserción | Construido | N/A | Sin update/delete en ninguna API. |
| P4 Alerta inmediata al Supervisor | Construido (backend) | No construido | Se despacha `ALERTA_SEGURIDAD`, pero no hay ningún consumidor en `web-interno` — el Supervisor no tiene forma de verla. |
| Lectura de bitácora | Construido | No construido | `GET /auditoria/eventos` listo y con RBAC correcto; ninguna pantalla en `web-interno` lo consume. |
| A1 Ráfaga, orden garantizado | Construido | N/A | Contador atómico. |
| A2 Anonimización LOPDP | No construido | No construido | Sin endpoint de "derecho al olvido". |

### CU-O18 — Controlar el acceso por rol

| Paso/Flujo | Backend | Frontend | Detalle |
|---|---|---|---|
| P1 Token en cada petición | Construido | Construido | — |
| P2 Middleware resuelve permisos | Construido | Construido (consumidor) | — |
| P3 Auditar lectura de datos sensibles de terceros | No construido | N/A | Solo se audita escritura, nunca lecturas. |
| P4 403 sin revelar existencia + registro | Construido | A medias | Frontend maneja el error de forma genérica, sin tratamiento específico de `INSUFFICIENT_ROLE`. |
| A1 Token expirado, 3 fallos cierran sesión | A medias | A medias | Backend suspende temporalmente (15min); frontend nunca limpia `actor` cuando el refresh falla — sesión "fantasma" visible en UI. |
| A2 Credencial de integración revocada | No verificado (fuera de alcance de archivos revisados) | N/A | — |
| A3 Cambio de rol en caliente | Construido | Construido (consumidor) | Backend relee siempre de Mongo; sidebar frontend no se refresca hasta nuevo login (UX menor, no seguridad). |
| A4 5 denegaciones/10min suspende + alerta | Construido (backend) | No construido | Mismo hallazgo que CU-O17 P4 — sin canal de alerta en frontend. |

---

## Operaciones / Despacho

### CU-O04 — Solicitar un viaje

| Paso/Flujo | Backend | Frontend | Detalle |
|---|---|---|---|
| P1 Mapa centrado + taxis anónimos en 300m | Construido | Construido | `GET /flota/cercanos`; `RideMap.tsx:35-40` pinta `taxiIcon` sin datos de conductor. |
| P2 Marcar destino en mapa o buscador | Construido | Construido | Click en mapa + geocodificación inversa + campo de texto. |
| P3 Distancia/duración/tarifa estimada etiquetada | Construido | Construido | `GET /viajes/estimacion-ruta` (corrige el bug de CORS de Directions de esta sesión); frontend muestra "aproximada, se confirma al solicitar". |
| P4 Crear viaje SOLICITADO con franja/tarifa | Construido | Construido | — |
| P5 Auto-despacho + pantalla de espera con "Cancelar solicitud" | Construido | Construido | Es un panel flotante, no una pantalla separada — cumple la intención pero cambia la forma literal. |
| A1 Sin destino | Construido | Construido | — |
| A2 GPS desactivado — bloquea solicitud, sin origen manual | Construido | Construido | Sin campo de origen manual en ningún lado. |
| A3 Viaje activo → `TRIP_ALREADY_ACTIVE` y redirección | Construido | Construido | — |
| A4 Cancelación durante SOLICITADO/OFERTADO | Construido | Construido | — |
| A5 Pérdida de conexión → restaurar con `GET /viajes/activo` | Construido | Construido | 200/null en vez de 404 (corregido esta sesión). |

CU-O04 está completo en ambos lados, sin observaciones críticas.

### CU-O05 — Asignar conductor (auto-despacho)

| Paso/Flujo | Backend | Frontend | Detalle |
|---|---|---|---|
| P1 Lista candidatos válidos | Construido | N/A (proceso de sistema) | — |
| P2 Orden por distancia → ocio → calificación | A medias | N/A | "Distancia en ruta" es en realidad línea recta (haversine) — corte de alcance documentado, no motor de ruteo real. |
| P3 Oferta al primer candidato, expira 20s | Construido | Construido | — |
| P4 Aceptación con CAS, ruta óptima conductor→origen | A medias | Construido (para lo que existe) | "Ruta óptima" es línea recta, misma limitación documentada. |
| P5 Notificar al pasajero: nombre, foto, teléfono enmascarado, calificación, placa, marca, color, ETA | A medias | A medias | Backend expone `conductor_nombre/calificacion`, `vehiculo_placa/marca/color` pero no foto/teléfono enmascarado/ETA. **Frontend ni siquiera renderiza `vehiculo_marca`/`vehiculo_color`/`conductor_calificacion`, que ya existen en el payload.** |
| P6 Pasajero ve solo el vehículo asignado en tiempo real | Construido | Construido | `GET /flota/posicion/{conductor_id}`, poll de 15s (no push real). |
| A1 Rechazo/expiración → siguiente candidato | Construido | Construido | — |
| A2 Ampliación de radio 300→600→1000 | Construido | N/A | — |
| A3 Reintentos agotados → SIN_CONDUCTOR, "Reintentar búsqueda" | A medias | **No construido** | Backend transiciona bien; **frontend no tiene botón "Reintentar búsqueda"** ni incluye `SIN_CONDUCTOR` en los estados cancelables — el pasajero queda atascado. |
| A4 Doble aceptación → `OFFER_NO_LONGER_AVAILABLE` | Construido | Construido (implícito) | — |
| A5 Conductor desconectado >120/180s → reabre asignación | No construido | No construido | Requiere scheduler inexistente, corte explícito. |

### CU-O06 — Ofrecer el viaje al conductor

| Paso/Flujo | Backend | Frontend | Detalle |
|---|---|---|---|
| P1 Notificación de pantalla completa con cuenta regresiva 20s | Construido | A medias | Frontend renderiza un overlay flotante compacto (340px) sobre el mapa, no una notificación de pantalla completa — desviación deliberada y documentada, pero sigue siendo distinta de la spec literal. |
| P2 Ver ubicación pasajero, distancia y tiempo estimado, nombre+calificación, zona de destino | A medias | A medias | Backend no calcula ETA ni resuelve zona de destino (solo boolean). Frontend solo muestra "Con/Sin destino marcado", sin ETA ni zona. |
| P3 Aceptar/Rechazar | Construido | Construido | — |
| P4 Modo navegación + chat/llamada al aceptar | A medias | A medias | Transición a ASIGNADO sí; chat/llamada no existen en absoluto, corte explícito. |
| A1 Sin respuesta 20s → expira | Construido | Construido | — |
| A2 Conductor cambió de estado entre selección y entrega | Construido | N/A | Cubierto por el filtro de `_buscar_candidatos`. |
| A3 Notificación no entregada → FUERA_DE_LINEA automático | No construido | No construido | Sin mecanismo de detección de fallas repetidas. |

### CU-O07 — Ejecutar el viaje

| Paso/Flujo | Backend | Frontend | Detalle |
|---|---|---|---|
| P1 "Voy en camino" → EN_CAMINO, posición+ETA en vivo | A medias | A medias | Posición vía polling 15s; sin ETA actualizado en ningún lado. |
| P2 Chat de texto y llamada con número enmascarado | No construido | No construido | Corte explícito, sin componente en ninguna app. |
| P3 "He llegado" → notifica arribo | Construido | Construido | — |
| P4 "Iniciar viaje" valida <150m, traza cada 5s | Construido | Construido | — |
| P5 Acumula km y minutos de espera | Construido | A medias | Backend calcula ambos; **`min_espera` nunca se muestra** al conductor ni al pasajero durante el trayecto. |
| P6 Continúa hasta CU-O08 | Construido | Construido | — |
| A1 Pasajero ausente 5min → CANCELADO/NO_SHOW | No construido | No construido | Diferido explícitamente. |
| A2 Cancelación pasajero con conductor en camino | No construido | No construido | Diferido explícitamente; coherente entre ambos lados. |
| A3 Cancelación del conductor con motivo obligatorio | Construido | A medias | Backend soporta motivo libre; **frontend manda un motivo hardcodeado** (`"cancelado por el conductor"`) en vez de pedir selección al usuario. |
| A4 Incidencia en ruta → notifica Coordinador | No construido | No construido | Fuera de alcance explícito. |
| A5 Pérdida de conexión, buffer IndexedDB, EN_REVISION tras 15min | A medias | A medias | Restauración de estado sí; buffer offline y `EN_REVISION` no existen (confirmado por grep). |
| A6 Desvío >2km recalcula ruta | No construido | No construido | Requiere motor de ruteo inexistente. |

### CU-O08 — Finalizar el viaje

| Paso/Flujo | Backend | Frontend | Detalle |
|---|---|---|---|
| P1 "Finalizar viaje" | Construido | Construido | — |
| P2 Calcula tarifa final con fórmula, franja de INICIO | Construido | N/A | Fórmula correcta según spec. |
| P3 Tarifa final con desglose de los 3 rubros a ambos actores | A medias | No construido | Backend solo expone `tarifa_final` total, sin campos de desglose; ningún frontend lo mostraría aunque existiera — falta en ambos lados. |
| P4 → FINALIZADO, dispara CU-O09 | Construido | Construido | — |
| P5 Calificación 1-5★ + comentario opcional, ambos lados, 24h | A medias | A medias | Backend acepta `comentario`; **ninguna de las dos UIs de calificación tiene campo de texto** para capturarlo. |
| P6 Conductor vuelve a DISPONIBLE automáticamente | Construido | Construido | — |
| A1 Discrepancia >30% → `revision_tarifa` | Construido | No construido (esperado) | Flag interno, la spec no pide mostrarlo. |
| A2 Traza incompleta → estimar tramo, `tarifa_estimada_parcial` | No construido | N/A | Campo existe en Mongo pero nunca se setea a true; diferido explícitamente. |
| A3 Sin destino → destino = punto de finalización | Construido | Construido (implícito) | — |
| A4 Finaliza >500m del destino, conserva declarado | A medias | N/A | El destino declarado se sobreescribe, no se conserva en paralelo — corte deliberado. |

### CU-O14 — Consultar el historial de viajes

| Paso/Flujo | Backend | Frontend | Detalle |
|---|---|---|---|
| P1 Lista paginada descendente con columnas requeridas | Construido | Construido | — |
| P2 Filtro por rango de fechas y por estado | A medias | A medias | Backend soporta `desde`/`hasta`/`estado`; **frontend solo expone el filtro de estado**, sin control de rango de fechas en ningún lado. |
| P3 Detalle: mapa con ruta, desglose de tarifa, datos contraparte, estado de pago | No construido (mapa/desglose) | No construido | **No existe ninguna vista de detalle clicable** en ninguna de las dos apps — la tabla no es clicable. `GET /viajes/{id}` ya expone datos suficientes para desglose/contraparte, pero nunca se invoca desde `HistorialView`. |
| P4 Emitir comprobante PDF | No construido | No construido | Sin endpoint ni botón en ningún lado; corte explícito documentado. |
| A1 Botón de comprobante oculto si no PAGADO | No construido (no aplica) | No construido | Consecuencia de que P4 no existe. |
| A2 Conductor solo ve nombre+calificación del pasajero | Construido | Construido | — |

**Resumen de divergencias backend↔frontend en Despacho/Viajes**: CU-O05 P5 (campos ya disponibles no renderizados), CU-O05 A3 (sin botón de reintento), CU-O08 P5 (comentario no capturable), CU-O14 P2/P3 (filtro de fechas y detalle no implementados), CU-O07 A3 (motivo hardcodeado en vez de selección).

---

## Finanzas

### CU-O09 — Registrar el pago del viaje

| Paso/Flujo | Backend | Frontend | Detalle |
|---|---|---|---|
| 1. Portal muestra tarifa y método (EFECTIVO default / pasarela) | A medias | A medias | Backend modela `metodo` pero el endpoint es literalmente `/pagos/efectivo`, sin rama electrónica. Frontend solo muestra tarifa y monto a cobrar en efectivo. |
| 2. Efectivo: "Pago recibido", valida monto==tarifa | Construido | Construido | — |
| 3. Electrónico: cobro a pasarela + webhook | No construido | No construido | Corte de alcance explícito y documentado — MVP 100% efectivo. |
| 4. Crea recaudación y transiciona viaje a PAGADO | Construido | Construido | Transacción atómica. |
| 5. Registro disponible para CU-O10 y conciliación | Construido | Construido | — |
| A1 Monto distinto: DISCREPANCIA, bandeja Admin, resolución justificada | Construido | Construido | Tabla inline (no migrada a WorkPanel) en Finanzas.tsx. |
| A2 Pago electrónico rechazado, reintento/cambio a efectivo | No construido | No construido | Sin camino electrónico. |
| A3 Webhook no recibido, reconsulta, PENDIENTE_CONFIRMACION | No construido | No construido | Estado existe solo en el enum, sin lógica. |
| A4 Viaje sin pago 24h → bandeja | Construido | A medias | Frontend muestra la tabla pero es explícitamente solo informativa, sin acción de resolución. |
| A5 Pago duplicado, idempotencia por referencia externa | No construido | No construido | No aplica sin camino electrónico. |
| Postcondición: evento en bitácora | Construido | N/A | — |

### CU-O10 — Calcular la comisión de la cooperativa

| Paso/Flujo | Backend | Frontend | Detalle |
|---|---|---|---|
| 1. `comision = monto × % vigente a la fecha del viaje`, `neto = monto - comision` | Construido | Construido (visualización) | Porcentaje resuelto por fecha del viaje, correcto. Frontend muestra comisión/neto por viaje pero no el % aplicado ni la versión. |
| 1(cont). Comisión de pasarela | No construido | No construido | Sin camino electrónico. |
| 2. Persistencia con redondeo bancario + porcentaje aplicado y versión | A medias | A medias | Se persiste `comision_version_id` pero el porcentaje en sí no se expone en ningún endpoint de salida. |
| A1 Cambio de % a mitad de periodo, viaje conserva el suyo | Construido (backend) | A medias | Backend correcto por diseño; frontend no muestra el % por viaje ni señala mezclas de % en una misma liquidación. |
| A2 Ajuste autorizado, movimiento vinculado con signo/motivo/autorizador, nunca modifica el original | **No construido** | **No construido** | **Confirmado: `ajustes = 0.0` fijo en `generar_liquidaciones` (`service.py:425-429,495`); el tipo `AJUSTE` existe en el enum pero ningún flujo lo crea.** Esto ya se había decidido corregir explícitamente en una sesión anterior de este mismo trabajo — no llegó a hacerse. |
| Postcondición: comisión/neto inmutables, ajustes trazables | A medias | A medias | Comisión/neto inmutables sí; "ajustes trazables" no existe (ver A2). |

### CU-O11 — Generar la liquidación del socio conductor

| Paso/Flujo | Backend | Frontend | Detalle |
|---|---|---|---|
| 1. Consolidar por socio, distinguir efectivo/electrónico | Construido (MVP 100% efectivo) | Construido | `saldo` siempre negativo dado que no hay electrónico — documentado y esperado. |
| 2. Emitir EMITIDA con desglose + notificación Web Push | A medias | A medias | Backend no notifica al socio al emitir (a diferencia de mantenimiento); frontend solo muestra el desglose al abrir el detalle, sin push activo. |
| 3. Admin aprueba → APROBADA; ejecuta movimiento | Construido (aprobación) / No construido (ejecución real) | Construido | "Ejecutar movimiento" es explícitamente manual fuera del sistema, documentado. |
| 4. Confirmado → PAGADA; socio descarga comprobante | A medias | No construido | Comprobante PDF explícitamente fuera de alcance; sin botón de descarga en ningún lado. |
| A1 Viajes con discrepancia excluidos, se arrastran | Construido | A medias | Backend correcto por construcción; **frontend no muestra el conteo "N viajes en revisión"** que exige la spec. |
| A2 Socio observa con motivo → OBSERVADA; Admin responde | Construido | Construido | — |
| A3 Saldo negativo: alerta Admin a 2 periodos, notificación al socio con plazo, posible suspensión de turno | A medias | A medias | Alerta al Admin sí; **notificación al socio con plazo y suspensión de turno explícitamente en backlog** — no construidas. Socio solo ve el saldo negativo pasivamente en su tabla. |
| A4 Error post-PAGADA: corrección con nota de ajuste referenciando la original | No construido | No construido | `liquidacion_ref_id` se inicializa pero nunca se usa; ya decidido diferir explícitamente. |
| Postcondiciones | A medias | A medias | Trazabilidad parcial dado que CU-O10 A2 y CU-O11 A4 no existen. |

---

## Mantenimiento

### CU-O12 — Registrar una orden de mantenimiento

| Paso/Flujo | Backend | Frontend | Detalle |
|---|---|---|---|
| 1. Ficha del vehículo: km acumulado, última intervención, plan preventivo | No construido | No construido | Búsqueda por placa solo devuelve placa/marca/modelo/estado — sin ficha real. |
| 2. Crear orden: tipo, descripción, km, taller, fecha | Construido | Construido | — |
| 3. "Retirar de servicio" → RETIRADO_DE_SERVICIO, bandera roja | Construido | Construido | Transacción orden+vehículo. |
| 4. Notifica al socio propietario | Construido | N/A | — |
| 5. ABIERTA → EN_TALLER | Construido | Construido | — |
| A1 Pre-orden desde incidencia de viaje, conversión con un clic | No construido | No construido | Depende de CU-O07, fuera de fase, documentado. |
| A2 Umbral preventivo automático → pre-orden | No construido | No construido | Fuera de fase, sin telemetría agregada. |
| A3 Solicitud de repuesto (descripción/cantidad/costo), orden en espera | A medias | **No construido** | Backend acepta `repuestos_estimados` y los persiste; **el formulario de creación no tiene ningún input para repuestos** — campo inalcanzable desde la UI. |
| A4 Anulación solo en ABIERTA, motivo obligatorio, rehabilita si aplica | Construido | Construido | — |
| Postcondición | A medias | A medias | "Costos estimados" en la práctica nunca se llenan porque el frontend no expone el campo. |

### CU-O13 — Cerrar la orden y habilitar el vehículo

| Paso/Flujo | Backend | Frontend | Detalle |
|---|---|---|---|
| 1. Trabajos, repuestos consumidos, horas de taller, costo total, km salida | A medias | **No construido** | Backend soporta los 5 campos; **frontend solo envía 3** (trabajos, costo total, km salida) — sin input de repuestos consumidos ni horas de taller. |
| 2. CERRADA; recalcula próxima intervención preventiva | A medias | Construido (para lo que backend hace) | **No hay ningún cálculo de próxima intervención** — ni campo ni lógica, contradice la postcondición explícita de la spec. |
| 3. Si RETIRADO_DE_SERVICIO, "Habilitar vehículo" → bandera verde | A medias | A medias | Backend soporta `habilitar_vehiculo` opcional; **frontend hardcodea `true` siempre**, sin distinguir si el vehículo estaba realmente retirado ni ofrecer el botón separado que pide la spec. |
| 4. Notifica al socio con detalle de costos | Construido | N/A | — |
| A1 Prolongar retiro: cerrar original, abrir correctiva encadenada | No construido | No construido | `orden_madre_id` existe en el schema pero nunca se asigna; sin endpoint ni UI. |
| A2 Cierre sin costos bloqueado | Construido | Construido | Validación Pydantic + frontend deshabilita el botón. |
| A3 Km salida < entrada: validación bloqueante con ajuste justificado en bitácora | Construido (backend) | **No construido** | Backend rechaza y soporta `ajuste_justificado`/`motivo_ajuste`; **el formulario de cierre no tiene ningún campo para esto** — un Jefe de Mantenimiento real queda bloqueado sin salida en la UI. |
| Postcondiciones | A medias | A medias | Solo "vehículo HABILITADO" y "costo total básico" están realmente completos de punta a punta. |

**Divergencias backend/frontend confirmadas en Finanzas/Mantenimiento**: `Finanzas.tsx` — solo "Liquidaciones" fue migrada al patrón WorkPanel (ActionBar/Pagination/DetailPanel); las otras 3 tablas (discrepancias, sin-pago-24h, saldo negativo) siguen inline. `conductor_nombre`/`vehiculo_placa` sí se renderizan correctamente (no UUID crudo) en ambas pantallas. `Mantenimiento.tsx` expone menos de lo que el backend ya soporta: repuestos (creación y consumo), horas de taller, y ajuste justificado — todos "backend Construido, frontend No construido".

---

## Flota

### CU-O19 — Reportar la posición y el estado del vehículo

*Nota de alcance: esta auditoría fue estática (sin navegador, sin Airflow ni API en vivo) — los veredictos de backend descansan en lectura de código, no en ejecución observada.*

| Paso/Flujo | Backend | Frontend | Detalle |
|---|---|---|---|
| P1 Iniciar turno con validación de banderas | Construido | Construido | — |
| P2 Reportar cada 10s/5s, wake lock | A medias | A medias | Frontend usa 15s fijos con `getCurrentPosition` (no `watchPosition`), sin diferenciar DISPONIBLE/OCUPADO. **Sin Wake Lock API en absoluto** — confirmado por grep. |
| P3 Alimenta mapa/candidatos/tablero | Construido | Construido | — |
| P4 Terminar turno, bloqueo con viaje activo | Construido | Construido | — |
| A1 Sin señal 60s, alerta al Coordinador | Construido (bajo demanda) | Construido | Solo polling; sin push proactivo, diferido explícitamente. |
| A2 Sin señal con viaje activo | No construido | No construido | Fuera de alcance explícito. |
| A3 Precisión baja 3 veces excluye de candidatos | Construido (backend) | N/A | El contador se incrementa; no se confirmó en esta pasada si algo lo consume para excluir realmente del despacho. |
| A5 Bandera roja fuerza fin de turno + bloqueo de próximo inicio | A medias | No construido | Solo bloquea el inicio de un turno nuevo; no fuerza el actual ni notifica el motivo. |
| A6 Batería <15% reduce frecuencia | No construido | No construido | Sin Battery Status API. |
| A7 Segundo plano/pantalla bloqueada | No construido | No construido | Sin `visibilitychange` ni Web Push. |

`Flota.tsx` confirmado: sigue sin migrar al patrón WorkPanel (igual que `Cumplimiento.tsx`).

---

## Plataforma

### CU-O15 — Ejecutar el proceso de transformación de datos

| Paso/Flujo | Backend (Airflow) | Frontend | Detalle |
|---|---|---|---|
| P1 Bronze extracción con lote_id/timestamp | Construido | N/A | — |
| P2 Silver validación (5 reglas para viajes) | Construido | N/A | Coincide exactamente con la tabla de la spec. |
| P3 Cuarentena, pipeline nunca se detiene | Construido | N/A | — |
| P4 Gold agregación | Construido | N/A | — |
| P5 Carga idempotente (DELETE+INSERT por fecha) | Construido | N/A | Con una salvedad documentada en el propio código: `ALTER DELETE` de ClickHouse es una mutación asíncrona y el código no espera a que se aplique físicamente antes de insertar — riesgo real bajo reprocesos rápidos, autodeclarado como simplificación. |
| P6 Publicar métricas de la corrida | Construido | N/A | — |
| A1 Fuente inaccesible: retry 5/15/45min, FAILED+alerta, backfill del día perdido | A medias | N/A | Retry y alerta correctos. **El backfill automático del día perdido no está implementado** — cada corrida solo jala su ventana fija (`catchup=False` en las 6 DAGs). |
| A2 % cuarentena >1% → WARN + alerta | Construido | N/A | — |
| A3 Reproceso de lote en cuarentena, idempotente | Construido | N/A | Dedup excluye correctamente la partición actual. |
| A4 Ventana excedida → encolar; 2 encolamientos → alerta de capacidad | A medias | N/A | `max_active_runs=1` cubre el no-concurrencia; **la alerta de capacidad por encolamientos consecutivos no existe**. |
| A5 dag_historico_nyc, reglas adaptadas | Construido (no verificado línea a línea en esta pasada) | N/A | — |

### CU-O16 — Publicar los indicadores para los informes de las áreas

| Paso/Flujo | Backend | Frontend | Detalle |
|---|---|---|---|
| P1 Refresco automático tras Gold confirmado | A medias | N/A | El DAG de publicación es **solo manual** (`schedule_interval=None`) — sin ningún trigger automático desde los 5 DAGs de dominio. |
| P2 Catálogo marca timestamp "datos al..." | Construido | Construido | Coincide exactamente con `InformeOut`. |
| P3 Dashboards solo consultan vistas, nunca tablas transaccionales | Construido | Construido | — |
| A1 Carga fallida → última versión buena, "datos al día anterior" | Construido | Construido | — |
| A2 Regenerar vista corrupta sin re-ejecutar DAG | Construido | N/A | — |
| A3 Refresco atómico durante lectura concurrente | Construido | N/A | — |
| RBAC roles (gerencia/responsable_plataforma/admin_plataforma) | A medias | **Divergencia confirmada** | Backend autoriza los 3 roles (`router.py:9`); **el frontend solo lista `gerencia`/`responsable_plataforma`** (`App.tsx:75-80`) — un usuario con `admin_plataforma` nunca vería la sección aunque la API le respondería bien. |

**Sobre el gap de verificación de navegador**: se confirmó por lectura estática que `Indicadores.tsx` coincide exactamente con la forma de `InformeOut` (nombres de propiedad, ramas null/retrasado), sin bug de shape visible. Pero no se lanzó navegador, no se confirmó que las tablas `rpt_*` tengan filas reales en este entorno en el momento de esta auditoría, y no se observó el render real. La divergencia de roles de arriba es justo el tipo de bug que solo aparece con verificación en vivo — confirma que el gap de navegador sigue siendo real, no una formalidad.

---

## Referidos (OT1.2)

**Confirmado 0% en ambos lados — y una precisión adicional**: no se pudo corroborar que `operativo_captacion.md` (ni ningún otro documento de spec del repo) mencione un módulo de Referidos u "OT1.2" como caso de uso descrito. El término "referido" aparece una sola vez en todo `specs/`, como valor de ejemplo en un comentario de `diseno_base_datos.md` (`dim_canal(canal_id, nombre) -- app, web, referido, campaña`), no como flujo especificado. `specs/nivel-tactico/` está vacío.

- **Backend**: cero archivos. Sin `backend/src/referidos/`, sin router registrado en `main.py` (que lista `auth, captacion, cumplimiento, mantenimiento, flota, viajes_*, recaudacion, liquidaciones, parametros, notificaciones, auditoria, plataforma` — nada de referidos).
- **Frontend**: cero archivos en las 3 apps (confirmado por grep, excluyendo coincidencias irrelevantes en caché de build).
