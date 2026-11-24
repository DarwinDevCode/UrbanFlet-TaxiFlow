## Context

`GET /mantenimiento/vehiculos/{vehiculo_id}/ficha` (`backend/src/mantenimiento/router.py:124-143`)
ya expone la ficha completa, gateado en exclusiva a `_jefe_mantenimiento = require_roles("jefe_mantenimiento")`
(`router.py:11`). El cálculo vive en `service.obtener_ficha_vehiculo(db, *, vehiculo_id)`
(`service.py:287-…`) y no depende de nada específico al rol que la consulta — recibe un
`vehiculo_id` y devuelve el dict con `km_acumulado`, `fecha_ultima_intervencion`,
`km_ultima_intervencion`, `proxima_km_preventivo`, `le_toca_preventivo`, `umbral_km_preventivo`.

El proyecto ya tiene 3 precedentes directos de "autoservicio de datos propios para el conductor",
todos con el mismo patrón: un endpoint nuevo `/…/mios` o `/…/mio/...`, gateado solo a `conductor`,
que resuelve el recurso propio del actor y reusa el servicio ya existente sin tocarlo:

- `flota/service.py:97-98` — `_vehiculo_del_conductor(db, conductor_id)` → `db.vehiculos.find_one({"propietario_id": conductor_id})`.
- `reportes_falla/service.py:98` — la misma consulta, inline, para `GET /reportes-falla/mias`.
- `cumplimiento/router.py:32-38` — `GET /documentos/mios`, gateado a `_conductor`, reusa
  `service.listar_mis_documentos(db, conductor_id=actor.usuario_id)`.

En el frontend, `apps/web-conductor/src/App.tsx` ya tiene 2 pantallas de autoservicio en el grupo
"Operación" del `CalleShell` (`FallasView`, `MisDocumentosView`, líneas 1946-1947) y un comentario
explícito (línea ~2300-2302) que documenta que `ORDEN_MANTENIMIENTO_REGISTRADA`/`_CERRADA` "siguen
sin pantalla propia, sin acción rápida fabricada" — el gap exacto que esta propuesta cierra.

## Goals / Non-Goals

**Goals:**
- Exponer la ficha al conductor reusando el cálculo existente sin duplicarlo ni modificarlo.
- Mantener el alcance RBAC mínimo: el conductor solo puede ver el vehículo del que es socio
  propietario, nunca un `vehiculo_id` elegido por el cliente.
- Conectar las 2 notificaciones ya existentes a la pantalla nueva, sin inventar ninguna
  notificación ni cambiar su disparo.

**Non-Goals:**
- No se toca el endpoint `/vehiculos/{id}/ficha` existente de `jefe_mantenimiento` ni su gate.
- No se agrega ninguna acción de escritura para el conductor sobre su vehículo (sigue siendo de
  solo lectura, igual que "Mis documentos").
- No se cambia el umbral de preventivo, la fórmula de proyección, ni ningún otro cálculo de
  `obtener_ficha_vehiculo` — se consume tal cual.
- No se toca `web-pasajero` ni `web-interno`.

## Decisions

### D1 — Endpoint nuevo `GET /mantenimiento/vehiculos/mio/ficha`, no un OR-gate sobre el existente
Se añade una ruta nueva en vez de ampliar `_jefe_mantenimiento` a
`require_roles("jefe_mantenimiento", "conductor")` sobre `/vehiculos/{vehiculo_id}/ficha`.

**Por qué**: el endpoint existente acepta cualquier `vehiculo_id` del cliente — es correcto para
`jefe_mantenimiento` (audita cualquier vehículo de la flota) pero sería un IDOR real si se le diera
acceso a `conductor` sobre esa misma ruta (podría pedir la ficha de cualquier otro socio cambiando
el id en la URL). Un endpoint separado que resuelve el vehículo desde `actor.usuario_id` — nunca
desde un parámetro de ruta — cierra esa clase de fallo por construcción, mismo criterio ya aplicado
en el proyecto para todo autoservicio (`/documentos/mios`, `/reportes-falla/mias`,
`/liquidaciones/mias`) y documentado explícitamente en una ronda de RBAC anterior
(`GET /viajes/historial-global/{id}` vs. `GET /viajes/{id}`, ver `CLAUDE.md` §26.2) como el patrón
correcto para separar "un actor viendo lo suyo" de "un rol interno viendo cualquier cosa".

**Alternativa descartada**: OR-gate + chequeo de pertenencia inline dentro del mismo handler
(`if "conductor" in actor.roles and vehiculo_id != mi_vehiculo: 403`). Descartada porque mezclaría
2 semánticas de autorización distintas en una sola ruta (rol interno sin restricción de recurso +
autoservicio con restricción de recurso), más difícil de auditar de un vistazo que 2 rutas
separadas con un gate simple cada una.

### D2 — Resolución del vehículo: `db.vehiculos.find_one({"propietario_id": actor.usuario_id})` inline en `mantenimiento/service.py`
Se agrega la función nueva (p. ej. `obtener_ficha_de_mi_vehiculo(db, *, conductor_id)`) dentro de
`mantenimiento/service.py`, que resuelve el `vehiculo_id` propio y delega en
`obtener_ficha_vehiculo` ya existente — no se importa el helper privado `_vehiculo_del_conductor`
de `flota/service.py`.

**Por qué**: es el mismo patrón que el proyecto ya usa en los 3 precedentes citados arriba — cada
dominio resuelve la propiedad del vehículo con su propia consulta inline de una línea, en vez de
acoplarse a un helper privado de otro módulo de dominio. Mantiene `mantenimiento/` sin una
dependencia nueva hacia `flota/`.

### D3 — Error de dominio nuevo cuando el conductor no tiene vehículo
`VehiculoConductorNoAsignadoError` (404), junto a `VehiculoNoEncontradoError` ya existente en
`mantenimiento/service.py:33`. Caso real y alcanzable: una postulación aprobada sin vehículo
(gap de datos ya documentado en otras partes del proyecto) o un vehículo dado de baja
(`estado_habilitacion = DADO_DE_BAJA` sigue teniendo `propietario_id`, así que ese caso SÍ resuelve
una ficha real — solo la ausencia total de vehículo propio es el caso de error).

### D4 — Frontend: pantalla nueva "Mi vehículo" en el grupo "Operación", no una sección dentro de "Fallas del vehículo"
Nueva entrada en el array que alimenta `CalleShell` (`apps/web-conductor/src/App.tsx`, función que
construye `navItemsConductor`, línea ~1931-1953): `{ id: "vehiculo", label: "Mi vehículo", group:
"Operación" }`, agregada al final de las entradas de "Operación" — no altera las posiciones 0/1 del
riel inferior (`Mi turno`/`Mis viajes`/`Mis liquidaciones` siguen igual), cae dentro de la hoja
"Más" junto a `Fallas del vehículo`/`Mis documentos`, mismo criterio ya usado en el resto del
proyecto para no desplazar la sección por defecto de ningún rol (`CLAUDE.md` §10/§13.2/§31/§32.4).

**Alternativa descartada**: mostrar la ficha como una sección superior dentro de `FallasView`.
Descartada porque son 2 datos con propósito distinto (reportar una falla vs. consultar el estado
del vehículo) y el proyecto ya separa "Fallas del vehículo" de "Mis documentos" con el mismo
criterio — juntarlas rompería la simetría de la navegación existente sin necesidad real.

### D5 — Presentación: `KpiCard` con `escala`/`referencia` para el kilometraje, no una tabla
El componente `KpiCard` (`apps/shared-ui/src/components/KpiCard.tsx`) ya soporta `escala`
(fracción 0-1 de un rango) y `referencia` (marca de umbral sobre esa escala) — construido
explícitamente como "la lectura de un tablero de vehículo" (comentario en el propio componente).
Es el ajuste natural para mostrar `km_acumulado` contra `proxima_km_preventivo` como el umbral: la
cifra visible es `km_acumulado`, la escala normaliza contra `proxima_km_preventivo` (con un tope
razonable, p. ej. `Math.max(proxima_km_preventivo, km_acumulado)` para que la marca de referencia
nunca quede fuera de rango), y `referencia` marca exactamente el punto de `proxima_km_preventivo`.
El resto de la ficha (última intervención, aviso de preventivo) va en un `Card` simple con `Alert`
(`tono="advertencia"`) cuando `le_toca_preventivo` es verdadero — mismo componente ya usado en
`MisDocumentosView` para el aviso de documentos vencidos.

**Alternativa descartada**: reusar el `Riel` (componente de trayecto de estado). Descartado porque
la ficha no es un trayecto con paradas discretas (como una orden o una solicitud) — es una medición
continua contra un umbral, que es exactamente el caso de uso para el que `escala`/`referencia` de
`KpiCard` fue construido.

### D6 — Notificaciones: nueva rama en `resolverAccionRapida`, sin nuevo mecanismo
`apps/web-conductor/src/App.tsx`, dentro del `resolverAccionRapida` ya existente (~línea 2297-2306):
agregar `if (n.tipo === "ORDEN_MANTENIMIENTO_REGISTRADA" || n.tipo === "ORDEN_MANTENIMIENTO_CERRADA") return { etiqueta: "Ver mi vehículo", onClick: () => setVista("vehiculo") };`
junto a la rama ya existente de `DOCUMENTO_VENCIDO`/`DOCUMENTO_POR_VENCER`. Ningún cambio en
`notificacionesCatalogo.ts` (las etiquetas de tipo ya existen), ningún cambio de backend en
`notificaciones/service.py` (el payload de ambas notificaciones ya trae `orden_id`, que no hace
falta usar — la ficha es del vehículo completo, no de una orden puntual).

## Risks / Trade-offs

- **[Riesgo] Un conductor con vehículo dado de baja (`DADO_DE_BAJA`) sigue viendo una ficha real
  con datos válidos** → Mitigación: es el comportamiento correcto — la ficha es informativa
  (kilometraje/última intervención/próxima preventiva), no una puerta de acceso; el estado de
  habilitación ya se comunica en otras pantallas (p. ej. el propio `estado_habilitacion` que
  `FichaVehiculoOut` ya expone, sin necesidad de ocultar el resto del dato).
- **[Riesgo] Duplicar el patrón de resolución de vehículo (inline por módulo, D2) en vez de
  centralizarlo** → Mitigación consciente: es el patrón ya establecido en 3 módulos del proyecto;
  centralizarlo ahora sería una refactorización fuera del alcance de este cambio, no una necesidad
  real (la consulta es una línea, sin lógica que diverja entre módulos).

## Open Questions

Ninguna — el alcance, el endpoint, el gate RBAC y la ubicación en la navegación quedan resueltos
arriba sin depender de una decisión pendiente del usuario.
