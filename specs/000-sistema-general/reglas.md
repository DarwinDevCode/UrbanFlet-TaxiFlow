# Reglas transversales — UrbanFleet TaxiFlow

Principios ya establecidos e implementados en todo el sistema, verificados repetidamente a lo largo
del proyecto (no una aspiración) — equivalente a la "constitución" del proyecto. Cada regla indica
en qué evidencia real se apoya.

## RN-SIS-001 — Baja lógica, nunca borrado físico

Ninguna entidad transaccional o de catálogo se elimina de la base de datos. Cuentas de usuario pasan
a `BAJA`/`SUSPENDIDO` (nunca se borran; su historial permanece consultable). Catálogos (talleres,
tipos de documento, motivos, marcas/colores de vehículo, repuestos) se desactivan con `activo:false`
— siguen visibles en el catálogo con su estado, pero desaparecen de los selectores que los consumen.
Verificado repetidamente: `db.usuarios.countDocuments({...})` sigue en 1 tras una baja; un taller
desactivado sigue existiendo pero ya no aparece en el selector de "Nueva orden".

## RN-SIS-002 — Auditoría write-ahead antes de confirmar una acción sensible

El evento de bitácora (`write_audit_event`) se escribe **antes** de persistir el efecto de negocio
en las acciones sensibles (transiciones de estado de viaje, decisiones de solicitud, cierre de
orden, cambios administrativos). Si el evento no se puede escribir, la acción no se confirma. Esto
es lo que permite que la Bitácora de auditoría (`004-transversal/auditoria-y-trazabilidad`) sea
realmente confiable como registro completo, no una foto parcial.

## RN-SIS-003 — RBAC estricto, por rol exacto, nunca por convención de nombre

Cada endpoint y cada pantalla se gatea por el nombre literal del rol (`require_roles("admin_captacion")`,
etc.), nunca por una jerarquía implícita ("cualquier admin puede..."). Cuando dos roles necesitan ver
lo mismo se declara explícitamente como OR-gate (ej. `require_roles("supervisor_cumplimiento",
"gerencia")`), documentado caso por caso. `admin_sistema` está separado de `admin_plataforma` por
principio de mínimo privilegio — uno gobierna la plataforma técnica, el otro administra el pipeline
de indicadores de negocio, y ninguno hereda los permisos del otro.

## RN-SIS-004 — El sistema nunca inventa un dato faltante

Cuando una fuente de datos real no existe (zona geográfica no resuelta, dominio de capacitación
inexistente, latencia/error de integraciones sin dominio propio), la interfaz muestra "—" con una
nota explicando por qué, en vez de simular, aproximar sin decirlo, o esconder el campo. Regla
observada de forma consistente en los 3 niveles (confirmado en `AUDITORIA_FUNCIONAL_TACTICO.md`,
`AUDITORIA_FUNCIONAL_ESTRATEGICO.md`).

## RN-SIS-005 — Corrección acotada por estado en entidades transaccionales

Un registro transaccional solo es corregible mientras no haya alcanzado un estado con efectos
downstream irreversibles. Ejemplo real: una solicitud de conductor es corregible mientras esté en
`ENVIADA`/`EN_VERIFICACION`/`OBSERVADA` — una vez `APROBADA`, sus datos ya se copiaron a
`usuarios.conductor` y a un documento `vehiculos` nuevo, así que corregirla retroactivamente
dejaría esas dos copias desincronizadas. Una liquidación `PAGADA` no admite corrección directa —
requeriría una nota de ajuste (backlog consciente, no implementada).

## RN-SIS-006 — Catálogos activos, patrón fail-safe

Cualquier selector que consume un catálogo (taller, motivo, tipo de documento, marca/color) filtra
siempre por `activo:true`. Varios de estos catálogos ofrecen además una opción "Otro" con campo de
texto libre — deliberadamente, para no bloquear una operación real por un catálogo incompleto,
excepto donde el backend valida contra el catálogo cerrado (tipo de falla de un reporte, tipo de
documento de una postulación) porque existe una razón de negocio real para no aceptar texto libre
ahí.

## RN-SIS-007 — Login con usuario+contraseña, nunca OTP

Decisión de arquitectura ya tomada: el diseño original contemplaba OTP por SMS; se abandonó en
favor de teléfono-o-correo + contraseña para los 3 roles de app pública (`pasajero`, `conductor`,
personal interno). Bloqueo por intentos fallidos vía Redis (5 fallos en 15 min → bloqueo 15 min),
mismo mecanismo para refresh de token y para suspensión por denegaciones RBAC repetidas.

## RN-SIS-008 — Mapas: Leaflet + OpenStreetMap, nunca el SDK de Google Maps

`specs-generales/arquitectura_software.md` lo exige explícitamente. Google se usa exclusivamente
para Geocoding y Directions, siempre resuelto server-side (Directions API no soporta CORS —
llamarla directo desde el navegador falla siempre).

## RN-SIS-009 — El ciclo de vida del viaje es un overlay sobre un mapa persistente

En `web-pasajero`/`web-conductor`, desde que se elige destino hasta que se califica al final, el
componente de mapa se monta una sola vez — nunca cambia de pantalla, solo cambia el panel flotante
encima. Decisión de UX deliberada, documentada explícitamente para que no se reabra por accidente.

## RN-SIS-010 — Patrón WorkPanel en toda pantalla CRUD operativa

Card de búsqueda (filtros) → ActionBar fija (Nuevo/Actualizar/Eliminar/Buscar/Salir, con `disabled`
+ tooltip explicando por qué una acción "no aplica" cuando corresponde) → DataTable + Pagination →
DetailPanel con indicador de modo (consulta/edición/nuevo) al hacer clic en una fila.

## RN-SIS-011 — Ningún flujo publica un dato sensible sin acotar el alcance por rol

Ejemplo real: el conductor solo ve nombre de pila y calificación del pasajero (nunca teléfono ni
historial de ubicación) en el detalle de un viaje — misma limitación aplicada consistentemente al
agregar la foto de perfil de la contraparte (no se trató como una excepción). La traza GPS de un
viaje solo se expone en 2 endpoints de todo el backend, cada uno con su propio alcance verificado
explícitamente con tests — nunca en un listado.
