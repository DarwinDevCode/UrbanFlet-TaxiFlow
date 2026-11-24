# Propuesta — CRUD completo y baja lógica

**Estado: solo auditoría y propuesta. Ningún cambio de código de este documento está implementado.**
Queda a la espera de aprobación explícita antes de tocar código — el alcance (todas las entidades
de los 3 portales, con impacto en informes y KPIs de los 3 niveles organizacionales) es demasiado
grande para implementar sin decidir primero qué construir y qué no.

Metodología: cada operación de cada `ActionBar` se verificó contra el `onClick` real en el código
(no contra lo que el botón muestra visualmente) y contra la ruta real del backend — el mismo
criterio que destapó, en la ronda anterior, que "Nuevo" en Reportes de falla estaba deshabilitado a
propósito con un `onClick: () => {}`. Esa verificación exhaustiva se hizo con apoyo de un agente de
investigación de solo lectura; los 4 hallazgos más consecuentes de este documento (el `PATCH` de
usuarios sin cablear, el endpoint de ajuste de pagos sin cablear, el `DELETE` real de zonas, y que
"Nuevo" de Reportes de falla SÍ está cableado hoy) se re-verificaron línea por línea contra el
código real antes de escribir esta propuesta.

---

## Patrón de referencia (ya implementado, no se rediseña)

Los 6 catálogos (`talleres`, `motivos_cancelacion`, `tipos_documento`, `marcas_vehiculo`,
`colores_vehiculo`, `repuestos`) ya implementan el patrón completo y correctamente:

- Campo `activo: bool`.
- `POST` (crear) + `PATCH` (editar, incluye `activo`) reales, ambos cableados en el frontend.
- **Cero rutas `DELETE`** — no es solo el botón deshabilitado, la ruta ni siquiera existe en el
  backend.
- `ActionBar.eliminar` deshabilitado con un tooltip explícito ("se desactiva, no se elimina").

Cero brechas encontradas en el cableado de estos 6. Es la referencia a seguir para cualquier
entidad nueva de este documento — no se propone ningún mecanismo distinto.

**Una excepción real ya existente, y vale la pena tenerla presente**: `zonas` (`parametros/`) es la
única entidad de tipo catálogo con un `DELETE` físico real (`backend/src/parametros/router.py:124`),
protegido por un guard de "en uso" (`ZonaEnUsoError`, 409) — pero ese guard verifica
`viajes.zona_origen_id`/`zona_destino_id`, campos que **nunca se resuelven en la práctica** (0 usos
reales, gap ya documentado en `CLAUDE.md`). `zonas` no tiene `activo`. Se retoma esto en la Fase C.

---

## Fase A — Inventario de entidades

### Grupo 1 — Dato maestro/de referencia (candidatas reales a CRUD + `activo`)

| Entidad | Crear | Leer | Actualizar | Baja | `activo` |
|---|---|---|---|---|---|
| `talleres`, `motivos_cancelacion`, `tipos_documento`, `marcas_vehiculo`, `colores_vehiculo`, `repuestos` | ✅ real | ✅ real | ✅ real | ✅ (desactivar) | ✅ ya existe |
| `zonas` | ✅ real | ✅ real | ✅ real | ✅ (pero **`DELETE` físico**, no lógico) | ❌ no existe |
| `vehiculos` | ⚠️ solo como efecto colateral de aprobar una solicitud | ✅ real (búsqueda por placa + ficha) | ❌ **no existe ningún `PATCH`** | ❌ no existe concepto de baja permanente | ❌ no existe |
| `plan_dr` (Módulo 7) | — (7 filas fijas, un dominio de negocio cada una) | ✅ | ✅ real | N/A (filas fijas) | N/A |
| `umbrales-monitoreo` (Módulo 5) | — (5 filas fijas, componentes monitoreados) | ✅ | ✅ real | N/A (filas fijas) | N/A |
| `servicios_externos` (Integraciones) | — (3 filas fijas) | ✅ | ⚠️ solo "rotar" | N/A (filas fijas) | N/A |
| `credenciales_integracion` | ✅ real | ✅ real | ❌ no existe (correcto — un secreto no se "edita", se reemite) | ✅ (`revocar`, boolean real) | equivalente: `revocada` |
| `feature_flags` | ✅ real | ✅ real | ✅ real | ✅ (`activo` es el propio interruptor del flag) | ✅ ya existe, sin brecha |

**`vehiculos` es el hallazgo más importante de esta fase.** No existe ningún `PATCH` en todo el
backend para corregir `placa`/`marca`/`modelo`/`color`/`propietario_id` después de creado — un error
de tipeo al aprobar una postulación (por ejemplo, una placa mal escrita) no tiene ningún camino de
corrección hoy, ni en la interfaz ni en la API. Tampoco existe un concepto de "vehículo dado de baja
permanentemente" (vendido, siniestrado, fuera de la flota para siempre) — solo el ciclo automático
`HABILITADO ⇄ RETIRADO_DE_SERVICIO` que ya maneja el mantenimiento (temporal, no una baja real).

### Grupo 2 — Entidad transaccional con máquina de estados propia (no candidata a `activo` genérico)

| Entidad | Estados / transiciones reales | Mecanismo de corrección ya existente |
|---|---|---|
| `usuarios` (personal interno) | `ACTIVO`/`SUSPENDIDO`/`BAJA` + anonimización terminal | Ninguno para nombre/teléfono/correo — ver hallazgo abajo |
| `solicitudes` (captación) | `ENVIADA→EN_VERIFICACION→APROBADA/RECHAZADA/OBSERVADA` | El propio flujo de decisión con motivo |
| `viajes` | 12 rutas, todas `POST`, cero `PATCH`/`DELETE` | El propio ciclo de vida (cancelar, calificar, etc.) |
| `ordenes` (mantenimiento) | `ABIERTA→EN_TALLER⇄ESPERANDO_REPUESTO→CERRADA`/`ANULADA` | **Ya tiene 2 mecanismos reales de corrección**: la cronología de actividades (`POST /ordenes/{id}/actividades`, notas/fotos de seguimiento) y `ajuste_justificado`/`motivo_ajuste` al cerrar, para un costo que se desvía del estimado. Es el mejor ejemplo ya construido de "cómo se ve una corrección específica del dominio". |
| `reportes_falla` | `PENDIENTE→CONVERTIDO_A_ORDEN`/`DESCARTADO` | El propio flujo de conversión/descarte con motivo |
| `documentos` | `estado_verificacion` (CONFORME/otros) | Ver hallazgo abajo — el único camino de corrección está roto en la práctica |
| `liquidaciones` | `EMITIDA→OBSERVADA/APROBADA→PAGADA` | **`responder-observacion` ya acepta `ajuste_monto`** — mecanismo de corrección real y ya cableado |
| `pagos` (discrepancias) | `DISCREPANCIA→resuelto` | `resolver()` (aceptar/rechazar) ya cableado. **Existe además un segundo mecanismo, `POST /pagos/{viaje_id}/ajuste` (CU-O10 A2), completamente construido en el backend pero sin ningún botón que lo llame** — ver hallazgo abajo |
| `respaldos`, `restauraciones`, `simulacros` | Registros de solo-agregar (logs operativos) | Correcto que no tengan ni editar ni eliminar — son bitácoras, no datos de referencia |

**Confirmado por revisión de código, no por suposición**: las 12 rutas de `viajes/` son todas
`POST` — cero `PATCH`/`DELETE` en todo el dominio. `HistorialGlobal.tsx` es 100% de solo lectura.

### Casos ambiguos (con argumento para cada lado, sin forzar clasificación)

- **`documentos`**: es transaccional (tiene `estado_verificacion`), pero su único camino de
  actualización (`POST /documentos/{id}/renovacion` → `verificacion`) es, en la práctica, un
  callejón sin salida: **ninguna pantalla de ninguna de las 3 apps llama al endpoint de subir la
  renovación** — la bandeja que depende de él está permanentemente vacía (gap ya documentado en
  `CLAUDE.md`, confirmado de nuevo acá). No encaja limpio en "falta baja lógica" (es transaccional,
  no debería tener `activo`), pero tampoco encaja en "ya tiene su mecanismo de corrección" (el que
  tiene está roto). Es un hallazgo real de este audit, pero está **fuera del alcance de esta
  propuesta** (no es un problema de CRUD/baja lógica) — se documenta acá para que no se pierda, no
  se prioriza en la Fase C.
- **`usuarios`**: clasificado como transaccional (tiene su propia máquina de estados, correcta y
  completa para suspender/dar de baja/anonimizar) — pero el backend ya expone
  `PATCH /usuarios/{usuario_id}` (nombre/teléfono/correo) que **`Usuarios.tsx` nunca llama**
  (verificado: cero referencias a ese `PATCH` en todo el archivo). Hoy la única forma de corregir el
  nombre mal escrito de un miembro del personal es que esa persona lo edite ella misma desde "Mi
  cuenta", con su propia contraseña — no hay ningún camino para que `admin_sistema` lo haga. No es
  un caso de "falta `activo`" (usuarios ya tiene su propia baja lógica correcta), es un caso de
  "falta cablear una operación de actualización que el backend ya construyó".

---

## Fase B — Impacto en consumidores (entidades con `activo`/equivalente)

| Catálogo | Consumidores reales encontrados | ¿Filtran `activo`? |
|---|---|---|
| `talleres` | Selector en "Nueva orden" y en "Convertir en orden" (Mantenimiento.tsx) | ✅ ambos, client-side |
| `repuestos` | `RepuestosEditor` (compartido por 3 formularios) | ✅ client-side |
| `tipos_documento` | Validación server-side en `crear_solicitud` (rechaza con 422 si el tipo está inactivo) | ✅ enforced en el backend, es una validación de escritura, no un selector |
| `motivos_cancelacion` | 4 consumidores reales: cancelación en `web-pasajero`, cancelación en `web-conductor`, "tipo de falla" en `web-conductor`, "tipo de falla" en la conversión admin (Mantenimiento.tsx) | ❌ **ninguno de los 4 filtra** — brecha real y sistemática, a diferencia de `talleres`/`repuestos` |
| `marcas_vehiculo`/`colores_vehiculo` | Selector en el formulario de postulación (`web-conductor`, público, sin sesión) | ❌ no filtra |
| `credenciales_integracion` | Ninguno — no se referencia desde ningún otro formulario | N/A |
| `feature_flags` | `core/feature_flags.py::is_enabled()` | N/A — sin ningún consumidor real todavía (ya documentado así en `CLAUDE.md`) |
| `usuarios`/`vehiculos` en ClickHouse/Airflow | `dag_captacion_gold` (captura `usuarios.estado` como dimensión, sin filtrar SUSPENDIDO/BAJA — correcto, es un snapshot histórico, no debería ocultar el estado) y `dag_flota_gold` (nunca filtra por `estado_habilitacion`, un vehículo retirado simplemente deja de reportar posición y se autoexcluye) | N/A — verificado que ninguno necesita el filtro, ni uno lo tiene |
| `UserPicker` (shared-ui, usado en Configuración de Alertas) | Búsqueda de destinatarios de alertas | ❌ no filtra por `estado` — una cuenta `SUSPENDIDO`/`BAJA` sigue seleccionable como destinataria |

**Matiz importante sobre `motivos_cancelacion`/`marcas_vehiculo`/`colores_vehiculo`**: a diferencia
de `tipos_documento` (que sí se valida estrictamente server-side), estos 3 catálogos conviven con un
patrón "Otro" de texto libre ya aprobado a propósito (Ronda de catálogos, Ola 3) — el campo real
nunca fue una FK estricta. Así que la ausencia de filtro `activo` acá es una brecha de UX real
(se puede seguir eligiendo una opción retirada), no una brecha de integridad de datos — el sistema
nunca prometió que esas 3 listas fueran cerradas. Es la excepción, `tipo_falla` (dentro de
`motivos_cancelacion`, categoría `incidencia`) sí está validado server-side de forma estricta —
ahí el filtro de UI evitaría un 422 al enviar, no solo prolijidad visual.

**No se encontró ninguna vista `rpt_*`/tabla Gold que agregue directamente sobre estos catálogos**
— los 6 se copian como texto libre en el momento de escribir el documento transaccional
(`ordenes.taller`, `viajes.motivo_cancelacion`, `documentos.tipo`), nunca como referencia viva. Esto
significa que desactivar una entrada de catálogo **nunca puede alterar retroactivamente** una orden,
viaje o documento ya existente, ni ningún agregado de ClickHouse — el único radio de impacto real es
la selección futura, ya cubierto en la tabla de arriba.

---

## Fase C — Priorización

### Alto impacto / bajo esfuerzo (sin cambios de esquema ni de ETL)

1. **Cablear `PATCH /usuarios/{id}` en `Usuarios.tsx`.** El backend ya existe y ya valida
   correctamente — solo falta un formulario de edición (nombre/teléfono/correo) en el detalle de
   usuario, mismo patrón `DetailPanel` en modo edición que ya usan las demás pantallas. Riesgo bajo,
   valor claro: hoy `admin_sistema` no puede corregir un dato mal tecleado de otro miembro del
   personal.
2. **Cablear `POST /pagos/{viaje_id}/ajuste` en `Finanzas.tsx`.** El backend ya existe, ya está
   documentado en el propio código como CU-O10 A2, y su ausencia es exactamente el gap que
   `CLAUDE.md` viene arrastrando hace varias sesiones ("0 documentos reales `movimientos.tipo=AJUSTE`
   pese a que hay tests"). Requiere un formulario nuevo (seleccionar viaje, monto, motivo) — más
   esfuerzo que el punto 1, pero sigue siendo "cablear algo que ya existe", no diseñar nada nuevo.
3. **Filtrar `activo` en los 4 consumidores reales de `motivos_cancelacion`** (cancelación en
   `web-pasajero`/`web-conductor`, tipo de falla en `web-conductor`/Mantenimiento.tsx) — mismo
   `.filter(m => m.activo)` de una línea que ya usan `talleres`/`repuestos`. Trivial, sin riesgo.
4. **Filtrar `activo` en el selector de marca/color del formulario de postulación**
   (`web-conductor`) — mismo patrón, una línea.
5. **Filtrar por `estado` en `UserPicker`** para que una cuenta suspendida/dada de baja no quede
   seleccionable como destinataria de alertas — cambio pequeño en el backend de búsqueda de
   usuarios más el consumidor ya existente.

### Requiere diseño/cambios de esquema más grandes (no son solo "agregar un filtro")

1. **CRUD completo de `vehiculos`.** No es un ajuste menor: hoy no existe ni creación directa
   (solo como efecto colateral de aprobar una solicitud), ni edición de ningún campo, ni un concepto
   de baja permanente distinto del ciclo automático de mantenimiento. Construir esto bien implica
   decidir explícitamente (ver preguntas para Darwin, abajo) si la baja lógica de un vehículo es un
   campo `activo` nuevo o un tercer valor de `estado_habilitacion`, y qué pasa si tiene órdenes
   abiertas en el momento de intentar la baja.
2. **Migrar `zonas` de `DELETE` físico a `activo`**, por consistencia con el resto de catálogos —
   esto es un cambio de esquema (agregar el campo) más una decisión de si vale la pena, dado que hoy
   el guard "en uso" que protege el `DELETE` actual está verificando un campo que nunca se resuelve
   en la práctica (ver nota en el patrón de referencia).

### Fuera de esta propuesta, pero documentado para no perderlo

- El flujo de verificación de renovaciones de `documentos` está roto de punta a punta (ninguna
  pantalla sube una renovación) — no es un problema de CRUD/baja lógica, es un flujo transaccional
  incompleto. Vale una propuesta aparte si se decide retomarlo.
- `vehiculos` tampoco tiene un campo de fecha de creación (hallazgo de la Parte 1 de esta misma
  ronda) — relevante si se decide construir el CRUD completo del punto anterior, porque una pantalla
  de administración de vehículos nueva heredaría el mismo problema de "no hay forma de ordenar por
  más reciente" que ya se corrigió en otras tablas.

---

## Preguntas para Darwin (decisiones de negocio, sin default silencioso)

1. **¿`vehiculos` necesita un campo `activo` nuevo, o conviene extender `estado_habilitacion` con un
   tercer valor** (ej. `DADO_DE_BAJA`, permanente, distinto de `RETIRADO_DE_SERVICIO`, temporal y
   automático)? Tener dos conceptos de "inactivo" superpuestos en la misma entidad sería confuso.
2. **¿Se puede dar de baja un vehículo con órdenes de mantenimiento abiertas** (`ABIERTA`/
   `EN_TALLER`/`ESPERANDO_REPUESTO`)? Si no, hace falta un guard "en uso" como el que ya tiene
   `zonas` (aunque ese guard hoy no verifica nada real, por el gap de zona nunca resuelta — no
   repetir ese patrón sin verificar que el campo de "en uso" sí se resuelve en `vehiculos`).
3. **¿Vale la pena migrar `zonas` de `DELETE` físico a `activo`**, por consistencia con el resto de
   catálogos, sabiendo que hoy su guard de "en uso" no protege nada real en la práctica?
4. **¿El ajuste financiero por viaje (`POST /pagos/{viaje_id}/ajuste`, CU-O10 A2) debería requerir
   una aprobación de un segundo rol**, dado que es dinero, o basta con `admin_financiero` actuando
   solo (mismo nivel de autorización que ya tiene para aprobar/pagar liquidaciones)?

## Nota de cierre

Nada de lo anterior está implementado. Cada punto de la Fase C "alto impacto/bajo esfuerzo" está
listo para construirse en cuanto se apruebe explícitamente cuál — no hace falta aprobar los 5 juntos
si se prefiere ir de a uno.
