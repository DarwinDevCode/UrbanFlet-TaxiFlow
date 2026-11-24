## Why

El backend ya calcula la ficha de mantenimiento de un vehículo (`mantenimiento/service.py::obtener_ficha_vehiculo`
— kilometraje acumulado, fecha/km de la última intervención, próxima preventiva proyectada, aviso
`le_toca_preventivo`), pero el único endpoint que la expone (`GET /mantenimiento/vehiculos/{id}/ficha`)
está gateado en exclusiva a `jefe_mantenimiento`. El conductor socio propietario de ese vehículo —el
principal interesado en saber si le toca preventivo o cuándo se hizo la última intervención— no tiene
ninguna forma de verla. Además, las 2 notificaciones que el propio backend ya le dispara al conductor
cuando se registra o se cierra una orden de su vehículo (`ORDEN_MANTENIMIENTO_REGISTRADA`,
`ORDEN_MANTENIMIENTO_CERRADA`) llegan hoy sin ninguna pantalla de destino — confirmado en
`apps/web-conductor/src/App.tsx` (comentario explícito: "el resto de los tipos de este portal
[incluye estos 2] siguen sin pantalla propia, sin acción rápida fabricada"). Esta propuesta cierra
ambos gaps con una sola pantalla nueva de autoservicio.

## What Changes

- Nuevo endpoint de autoservicio `GET /mantenimiento/vehiculos/mio/ficha`, gateado a `conductor`,
  que resuelve el vehículo del propio conductor (`db.vehiculos.find_one({"propietario_id": actor.usuario_id})`,
  mismo patrón ya usado en `flota/service.py`/`reportes_falla/service.py`) y reusa
  `service.obtener_ficha_vehiculo` tal cual — sin duplicar el cálculo de km/próxima preventiva.
- Nuevo error de dominio (404) cuando el conductor no tiene ningún vehículo asignado — caso real
  posible (postulación aprobada sin vehículo, o vehículo dado de baja).
- Nueva pantalla "Mi vehículo" en `web-conductor` (grupo "Operación" del `CalleShell`, junto a
  "Fallas del vehículo" y "Mis documentos"), que muestra kilometraje acumulado, última intervención
  (fecha + km) y próxima preventiva proyectada, con aviso visible si `le_toca_preventivo` es verdadero.
- `resolverAccionRapida` de `SeccionNotificaciones` en `web-conductor` gana una rama nueva para
  `ORDEN_MANTENIMIENTO_REGISTRADA`/`ORDEN_MANTENIMIENTO_CERRADA` → navega a "Mi vehículo".
- Ningún cambio de rol, de máquina de estados de la orden, ni del cálculo existente de la ficha —
  el 100% del cálculo (kilometraje, umbral, proyección) se reusa sin tocarlo.

## Capabilities

### New Capabilities

(ninguna — este cambio extiende una capacidad ya documentada, no introduce una nueva)

### Modified Capabilities

- `003-operativo/mantenimiento`: agrega un requisito nuevo — la ficha del vehículo (RF-MAN-008, hoy
  solo visible para `jefe_mantenimiento`) debe ser consultable también por el conductor socio
  propietario del vehículo, sobre su propio vehículo únicamente; y las notificaciones de orden
  registrada/cerrada deben llevar a esa pantalla.

## Impact

- **Backend**: `backend/src/mantenimiento/router.py` (endpoint nuevo), `backend/src/mantenimiento/service.py`
  (helper de resolución conductor→vehículo + error de dominio nuevo), `backend/src/mantenimiento/schemas.py`
  (sin cambios — reusa `FichaVehiculoOut`).
- **Frontend**: `apps/web-conductor/src/App.tsx` (pantalla nueva "Mi vehículo", entrada de navegación,
  wiring de `resolverAccionRapida`). Ningún cambio en `web-pasajero` ni `web-interno`.
- **Sin cambios** en `apps/shared-ui` (no se necesita ningún componente nuevo — reusa `Card`,
  `KpiCard`, `Alert` ya existentes), en Airflow/ClickHouse, ni en el esquema de Mongo.
