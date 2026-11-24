# Plan técnico (retroactivo): Coordinación de Flota

## Backend

- `backend/src/flota/` (`router.py`/`service.py`): `GET /flota/tablero` (snapshot completo, sin
  paginar), `reportar_posicion` (consumido por el propio conductor durante el turno, no un endpoint
  de este departamento en sí).
- Redis: caché de posición (`pos:{vehiculo_id}`) con `lat`/`lon`/`ts_servidor`/`estado_servicio`.
- Colección `posiciones`: traza cruda de cada reporte, con TTL real (7 días, confirmado en el índice
  de Mongo, no un valor hardcodeado en documentación).

## Frontend

- `apps/web-interno/src/sections/Flota.tsx` — WorkPanel con `ActionBar` sin verbos de edición
  (`Nuevo`/`Eliminar` deshabilitados con tooltip explicando que este módulo es de solo lectura),
  búsqueda/paginación client-side, detalle vía `MapaPosicion` (mapa de un solo punto, reusado del
  sistema de mapas compartido).

## Decisión de arquitectura: por qué la búsqueda es client-side

`GET /flota/tablero` es un snapshot en vivo, no un listado transaccional — paginar en servidor
rompería el refresco automático de 10s (habría que re-pedir la página actual constantemente en vez
de un solo fetch). Se prefirió un solo fetch cada 10s + filtro en el cliente sobre el snapshot ya
descargado.
