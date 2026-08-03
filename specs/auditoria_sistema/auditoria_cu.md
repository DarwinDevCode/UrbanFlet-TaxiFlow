# Auditoría de conformidad — Fases 1-4 vs. `nivel-operativo/`

Fecha: 2026-08-01

Auditoría estricta punto por punto entre las especificaciones de `specs/nivel-operativo/` y lo realmente implementado (backend + frontend) para las 19 CUs de Fases 1-4, marcadas previamente como "completas". Criterio aplicado: un paso solo cuenta como **Implementado** si la interfaz expone la interacción tal como la describe la spec — que el dato exista o sea alcanzable vía API no equivale a que el flujo esté implementado.

Nota de alcance: la migración de OTP/Firebase a login autocontenido (teléfono/correo + contraseña) se trata como un cambio de arquitectura ya aprobado, no como una desviación, aunque el texto de la spec original todavía describa pasos de OTP.

## Hallazgo transversal más grave

**CU-O15 (transformación de datos) y CU-O16 (publicación de indicadores) están al 0% — no parcialmente implementados.** `analytics/dags/` y `analytics/plugins/` están vacíos; no hay ni un DAG stub, ni cliente ClickHouse, ni una sola pantalla en ninguna de las 3 apps que muestre indicadores a gerencia/responsable_plataforma. Docker-compose levanta la infraestructura (Airflow, ClickHouse) pero no hay una sola línea de código de negocio dentro. Esto no debería estar marcado "completo".

Segundo patrón sistemático: **el frontend de `web-pasajero` carece de mapa en absoluto** — ningún componente `<canvas>`/mapa, ninguna vista de taxis cercanos, ninguna posición del vehículo asignado en tiempo real, ningún desglose de tarifa. Esto rompe pasos centrales de CU-O04, CU-O05, CU-O06, CU-O07, CU-O08 y CU-O14 simultáneamente, no solo el ejemplo puntual detectado en CU-O04.

---

## CU-O01 — Registrar la solicitud de un conductor

| Paso/Flujo | Estado | Evidencia |
|---|---|---|
| P1 Requisitos previos | Ausente | `apps/web-conductor/src/App.tsx:76-85` — formulario abre directo, sin checklist |
| P2 Cuenta + OTP | Implementado (password sustituye OTP, cambio aprobado) | `App.tsx:88-94`; `backend/src/auth/service.py:47-99` |
| P3(a)(b) Datos personales + vehículo | Implementado | `App.tsx:95-104` |
| P3(c) Carga de documentos | **Ausente** | `App.tsx:64` — `documentos: []` hardcodeado, sin UI de subida |
| P4 Validación formato/tamaño/vista previa | Ausente | No existe upload en frontend; schema acepta URLs arbitrarias sin validar |
| P5 Enviar solicitud (valida completitud) | Parcial | Fija `ENVIADA`+timestamp+notifica, pero sin chequeo de completitud documental |
| P6 Pantalla de estado con número de solicitud | Parcial | `App.tsx:924-935` — no muestra el número de solicitud |
| A1 Guardar incompleta/BORRADOR/EXPIRADA 30d | Ausente | Frontend siempre `enviar:true`; sin job de expiración |
| A2 Cédula ya socio activo | Implementado | `backend/src/captacion/service.py:141-144`, 409 |
| A3 Placa ya en flota → advertencia | Parcial | Flag interno `revision_reforzada`, nunca mostrado al usuario |
| A4 OTP | N/A (diseño aprobado) | — |
| A5 Documento vencido bloquea carga | Ausente | No hay carga de documentos |
| Postcondición: documentos+metadatos persistidos | Parcial | Modelo lo soporta; en la práctica siempre vacío |

**El hueco más grande de esta CU: no existe forma de subir un solo documento desde ningún frontend**, lo que rompe P3(c), P4, P5(completitud), A5 y la postcondición a la vez.

## CU-O02 — Registrar un pasajero

| Paso/Flujo | Estado | Evidencia |
|---|---|---|
| P1 Crear cuenta | Implementado | `apps/web-pasajero/src/App.tsx:97-104` |
| P2 Nombre+teléfono+correo, consentimiento con timestamp/versión | Parcial | UI fuerza elegir teléfono O correo, no ambos como implica la spec; consentimiento sí correcto |
| P3 OTP | N/A (diseño aprobado) | — |
| P4 Cuenta ACTIVO, viaja de inmediato | Implementado | `backend/src/captacion/service.py:84,112` |
| A1 Foto opcional, recordatorio 3er uso | Ausente | No existe campo `foto` en ningún nivel |
| A2 Teléfono duplicado → recuperación de cuenta | Parcial | Duplicado bloqueado (409), pero no existe ningún flujo de recuperación/reset de contraseña |
| A3 Menor de edad bloquea registro | Ausente | No existe campo de fecha de nacimiento |
| Postcondición | Implementado | `backend/src/captacion/service.py:101-110` |

## CU-O03 — Verificar la documentación del postulante

| Paso/Flujo | Estado | Evidencia |
|---|---|---|
| P1 Bandeja con semáforo de plazo | Parcial | Orden por antigüedad sí; semáforo verde/ámbar/rojo ausente |
| P2 Tomar solicitud (evita doble revisión) | Implementado | `backend/src/captacion/service.py:204-232`; `apps/web-interno/src/sections/Solicitudes.tsx:117-121` |
| P3 Checklist por documento CONFORME/OBSERVADO | **Ausente** | Solo hay una decisión agregada única; el backend marca "CONFORME" a todos los documentos sin loop real |
| P4 Aprobar → socio ACTIVO, vehículo HABILITADO, agenda vencimientos | Parcial | Creación correcta; "agenda" es indirecta (job separado de otro módulo) |
| P5 Métrica de tiempo total de aprobación | Ausente | No se calcula ni persiste ningún duration/metric |
| A1 Observado con lista exacta de observaciones, re-carga solo lo observado | Parcial | Transición de estado sí; sin modelo por documento, sin re-upload UI |
| A2 Rechazo, bloqueo de reenvío 90 días | Parcial | Motivo obligatorio sí; el bloqueo de 90 días **no está implementado** |
| A3 3 ciclos sugiere rechazo | Ausente | Sin contador de ciclos |
| A4 EN_VERIFICACION >24h vuelve a bandeja | Ausente | Sin scheduler |

## CU-O17 — Registrar un evento en la bitácora

| Paso/Flujo | Estado | Evidencia |
|---|---|---|
| P1 Campos completos (evento_id, ts, actor, IP, dispositivo...) | Parcial | Todo presente en schema, pero **`ip`/`dispositivo` nunca se pasan desde ningún caller** — siempre `null` |
| P2 Catálogo mínimo de eventos sensibles | Implementado | `backend/src/core/audit.py:34-59` |
| P3 Solo inserción, sin update/delete | Implementado | Verificado sin llamadas de update/delete a `bitacora` |
| P4 Alerta inmediata al Supervisor en eventos de seguridad | Parcial | Funciona para denegaciones RBAC; **no dispara** para `POSIBLE_GPS_SPOOFING` ni `LOGIN_FALLIDO_CONSECUTIVO` |
| A1 Ráfaga, orden garantizado | Parcial | Orden por contador atómico sí; el "encolado en memoria" de la spec no existe (inserción síncrona directa) |
| A2 Anonimización LOPDP | Ausente | No existe ningún endpoint de anonimización |

`ResultadoAuditoria.ERROR` también es código muerto — nunca se usa.

## CU-O18 — Controlar el acceso por rol

| Paso/Flujo | Estado | Evidencia |
|---|---|---|
| Catálogo de roles | Implementado | `backend/src/core/rbac.py:23-38` |
| P1 Token de sesión o credencial de integración | Parcial | Sesión completa; **`integracion_externa` no tiene ningún mecanismo de autenticación propio** |
| P2 Middleware resuelve permisos | Implementado | `rbac.py:139-154` |
| P3 Registrar lectura de datos sensibles de terceros | Ausente | No existe auditoría del lado de lectura, solo escritura/denegación |
| P4 403 sin revelar existencia + registro | Implementado | `rbac.py:149-152` |
| A1 Token expirado, 3 fallos cierran sesión | Implementado | `backend/src/auth/service.py:29,205-210` |
| A2 Credencial de integración revocada | Ausente | No existe el concepto de credencial de integración |
| A3 Cambio de rol en caliente | Implementado | `rbac.py:88-96` |
| A4 5 denegaciones/10min suspenden + alertan | Implementado | `rbac.py:40-42,126-136` |

---

## CU-O04 — Solicitar un viaje

| Paso/Flujo | Estado | Evidencia |
|---|---|---|
| P1 Mapa con taxis en 300m como íconos | **Ausente** (confirmado) | `apps/web-pasajero/src/App.tsx:247-343` — solo inputs de texto |
| P2 Marcar destino en mapa/buscador con geocodificación | Ausente | Dos `TextField` numéricos |
| P3 Distancia/duración/tarifa estimada antes de solicitar | Ausente | Nada se muestra antes del POST |
| P4 Crear viaje SOLICITADO | Implementado | `backend/src/viajes/service.py:92-137` |
| P5 Pantalla de espera con animación + botón Cancelar | Ausente | Solo un `Badge` de texto; **no existe botón de cancelación en absoluto** |
| A1 Sin destino | Implementado | — |
| A2 GPS desactivado bloquea input manual | Parcial | Bloqueo correcto, mensaje de error genérico (no guía al usuario a conceder permiso) |
| A3 Viaje activo → TRIP_ALREADY_ACTIVE | Parcial | Error correcto, pero no redirige al viaje en curso |
| A4 Cancelación durante búsqueda | **Ausente** | No existe endpoint de cancelación por pasajero en absoluto |
| A5 Pérdida de conexión → GET /viajes/activo | Implementado | `App.tsx:530-542` |

## CU-O05 — Asignar conductor (auto-despacho)

| Paso/Flujo | Estado | Evidencia |
|---|---|---|
| P1-P2 Candidatos válidos, orden por distancia/ocio/calificación | Implementado | `backend/src/viajes/service_dispatch.py:57-113` |
| P3 Ofertar 20s | Implementado | `service_dispatch.py:140-193` |
| P4 Aceptación con ruta óptima | Parcial | Transición correcta; ruta óptima no existe (línea recta) |
| P5 Notificar con foto/teléfono enmascarado/ETA | Parcial | Faltan foto, teléfono enmascarado, ETA en el schema; frontend ni siquiera renderiza calificación/marca/color que el backend ya provee |
| P6 Pasajero ve vehículo asignado en mapa | Ausente | Sin mapa |
| A1 Rechazo/expiración → siguiente candidato | Implementado | — |
| A2 Amplía radio 600m/1000m | Implementado | — |
| A3 Reintentos agotados → botón "Reintentar" | Parcial | Backend marca `SIN_CONDUCTOR`; sin botón en UI, y el estado además desaparece de `/viajes/activo` |
| A4 Doble aceptación | Implementado | — |
| A5 Conductor se desconecta → reabre asignación | Ausente | Documentado como diferido (falta scheduler) |

## CU-O06 — Ofrecer el viaje al conductor

| Paso/Flujo | Estado | Evidencia |
|---|---|---|
| P1 Notificación pantalla completa 20s | Implementado | `apps/web-conductor/src/App.tsx:184-248` |
| P2 Mapa, tiempo estimado, zona de destino | Parcial | Solo distancia y nombre/calificación; sin mapa, sin ETA, sin zona real |
| P3 Aceptar/Rechazar | Implementado | — |
| P4 Modo navegación + chat/llamada | Ausente | Corte de alcance documentado |
| A1 Expira sin respuesta | Implementado | — |
| A3 Fallas repetidas → FUERA_DE_LINEA automático | Ausente | No existe esa transición |

## CU-O07 — Ejecutar el viaje

| Paso/Flujo | Estado | Evidencia |
|---|---|---|
| P1 EN_CAMINO con posición/ETA en tiempo real | Parcial | Backend correcto; frontend solo texto, sin mapa/ETA |
| P2 Chat/llamada | Ausente | Corte documentado |
| P3 "He llegado" | Implementado | — |
| P4 "Iniciar viaje" valida <150m, traza cada 5s | Parcial | Validación correcta; cadencia real es **15s fijos, no 5s** |
| P5 Acumula km/minutos de espera | Implementado | — |
| A1 Pasajero ausente 5min | Ausente | Diferido |
| A2 Cancelación pasajero con conductor en camino | Ausente | Sin endpoint de cancelación por pasajero |
| A3 Cancelación conductor con motivo | Parcial | Backend exige motivo; frontend envía **motivo fijo hardcodeado**, sin selector |
| A4 Incidencia en ruta | Ausente | Diferido |
| A5 Pérdida conexión, buffer + EN_REVISION 15min | Parcial | Restauración sí; buffer offline y transición a EN_REVISION ausentes |
| A6 Desvío >2km recalcula | Ausente | Diferido |

## CU-O08 — Finalizar el viaje

| Paso/Flujo | Estado | Evidencia |
|---|---|---|
| P1 "Finalizar viaje" | Implementado | — |
| P2 Tarifa final por franja de inicio | Implementado | `backend/src/viajes/service_finalizacion.py:80-106` |
| P3 Desglose de 3 rubros a ambos actores | **Ausente** | Solo se muestra el total, ningún desglose en ningún lado |
| P4 FINALIZADO + dispara pago | Implementado | — |
| P5 Calificación 1-5, 24h | Implementado | — |
| P6 Conductor vuelve a DISPONIBLE | Implementado | — |
| A1 Discrepancia >30% | Implementado | — |
| A2 Traza incompleta → estimar tramo | Ausente | Diferido explícitamente |
| A4 Finaliza >500m del destino, conserva declarado | Parcial | Se permite, pero el destino declarado se **sobreescribe**, no se conserva para análisis |

## CU-O09 — Registrar el pago del viaje

| Paso/Flujo | Estado | Evidencia |
|---|---|---|
| P1 Muestra tarifa + método de pago | Parcial | Tarifa sí; sin selector/indicador de método |
| P2 Efectivo, validación de monto | Implementado | `backend/src/recaudacion/service.py:161-165` |
| P3 Pago electrónico (webhook/referencia) | **Ausente** | MVP 100% efectivo, documentado explícitamente |
| P4-P5 Recaudación creada, disponible para comisión | Implementado | — |
| A1 Discrepancia → bandeja Admin Financiero | Implementado | `apps/web-interno/src/sections/Finanzas.tsx:181-239` |
| A2-A3-A5 Ruta electrónica (rechazo, webhook, duplicado) | Ausente | No existe camino electrónico |
| A4 Viaje sin pago 24h → bandeja | Implementado | — |

## CU-O10 — Calcular la comisión de la cooperativa

| Paso/Flujo | Estado | Evidencia |
|---|---|---|
| P1-P2 Cálculo por porcentaje vigente, redondeo, versión | Implementado | `backend/src/recaudacion/service.py:88-124` |
| A1 Cambio de porcentaje a mitad de periodo | Implementado | — |
| A2 Ajuste autorizado como movimiento vinculado al viaje | **Parcial** | El código ajusta la liquidación agregada, no crea el movimiento `AJUSTE` individual que pide el flujo |

## CU-O11 — Generar la liquidación del socio conductor

| Paso/Flujo | Estado | Evidencia |
|---|---|---|
| P1-P2 Consolidación, EMITIDA con desglose | Implementado | — |
| P3-P4 Aprobar/Pagar | Implementado | — |
| A1 "N viajes en revisión" visible | Parcial | Exclusión funciona; el texto no se renderiza en la UI |
| A2 Socio observa, Admin responde | Implementado | `Finanzas.tsx:363-417` |
| A3 Saldo negativo notifica al socio con plazo | Parcial | Alerta al Admin sí; notificación proactiva al socio con plazo, ausente |
| A4 Corrección post-PAGADA vía nota de ajuste | **Ausente** | No hay ningún mecanismo para esto |

## CU-O12 — Registrar una orden de mantenimiento

| Paso/Flujo | Estado | Evidencia |
|---|---|---|
| P1 Ficha del vehículo (km, historial, plan) | **Ausente** | Solo búsqueda por placa, sin km acumulado ni historial |
| P2 Crear orden | Implementado | — |
| P3 Retirar de servicio | Implementado | — |
| P4 Notifica al socio | Implementado | — |
| A1-A2 Pre-órdenes por incidencia/umbral | Ausente | Fuera de alcance explícito |
| A3 Registro de repuestos | Parcial | Backend lo soporta; **UI no tiene ningún campo para repuestos** |
| A4 Anulación | Implementado | — |

## CU-O13 — Cerrar la orden y habilitar el vehículo

| Paso/Flujo | Estado | Evidencia |
|---|---|---|
| P1 Repuestos consumidos + horas de taller | Parcial | UI solo tiene trabajos/costo/km salida; faltan los otros dos campos |
| P2 Recalcula próxima intervención preventiva | Ausente | No existe en ningún lado |
| P3 Habilitar vehículo condicional | Parcial | UI **siempre** envía `habilitar_vehiculo:true`, sin distinguir estado previo |
| A1 Prolongar retiro → orden encadenada | Ausente | Campo existe en schema, sin lógica |
| A2 Bloqueo sin costos | Implementado | — |
| A3 Km salida < entrada, ajuste justificado | **Backend sí, UI no** | La UI no tiene campo para justificar el ajuste — un caso real deja al usuario atascado |

## CU-O14 — Consultar el historial de viajes

| Paso/Flujo | Estado | Evidencia |
|---|---|---|
| P1 Lista paginada | Implementado | — |
| P2 Filtro por fecha y estado | Parcial | Estado sí; **filtro de fechas ausente en ambas UIs** aunque el backend lo soporta |
| P3 Detalle con mapa/desglose/estado de pago | **Ausente** | No existe ninguna vista de detalle |
| P4 Comprobante PDF | Ausente | Diferido explícitamente |

## CU-O19 — Reportar la posición y el estado del vehículo

| Paso/Flujo | Estado | Evidencia |
|---|---|---|
| P1 Iniciar turno con validación de banderas | Implementado | — |
| P2 Reportar cada 10s/5s con `watchPosition` + wake lock | Parcial | Usa `getCurrentPosition` a **15s fijos**, sin distinguir DISPONIBLE/OCUPADO, sin wake lock |
| P3 Alimenta mapa del pasajero | **Ausente** | No existe endpoint ni UI |
| P4 Terminar turno | Implementado | — |
| A1 Sin señal 60s, alerta al Coordinador | Parcial | Cálculo bajo demanda, sin job en segundo plano ni push |
| A3 Precisión baja 3 veces excluye de candidatos | **Parcial (código muerto)** | El contador se incrementa pero **nunca se lee** en el despacho |
| A5 Bandera roja fuerza fin de turno | Parcial | Solo bloquea turno nuevo, no fuerza el actual |
| A6 Batería <15% reduce frecuencia | Ausente | Sin Battery Status API |
| A7 Segundo plano/pantalla bloqueada | Ausente | Sin `visibilitychange` ni Web Push |

## CU-O15 — Ejecutar el proceso de transformación de datos

**Todo el CU: 0% implementado.** `analytics/dags/` y `analytics/plugins/` vacíos, sin cliente ClickHouse, sin ninguna transformación Bronze/Silver/Gold, sin cuarentena, sin métricas de corrida. Solo existe el andamiaje de infraestructura en `docker-compose.yml`.

## CU-O16 — Publicar los indicadores para los informes de las áreas

**Todo el CU: 0% implementado.** Depende de CU-O15 (inexistente). No hay ningún tablero, catálogo de informes, ni vista para gerencia/responsable_plataforma en ninguna de las 3 apps.

---

## Orden de remediación sugerido (por severidad)

1. **CU-O15/O16** (0%, bloquean cualquier reporte gerencial).
2. **Mapa + cancelación de solicitud en `web-pasajero`** (afecta CU-O04, O05, O06, O07, O08, O14 a la vez).
3. **Carga de documentos** en CU-O01/CU-O03 (bloquea el flujo real de postulación de conductor).
4. Huecos puntuales de UI en mantenimiento/finanzas donde el backend ya soporta el caso pero la pantalla no lo expone (CU-O12 A3, CU-O13 A3/P1, CU-O11 A1/A3/A4).
