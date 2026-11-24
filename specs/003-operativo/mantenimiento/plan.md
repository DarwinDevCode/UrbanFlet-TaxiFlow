# Plan técnico (retroactivo): Mantenimiento

## Backend

- `backend/src/mantenimiento/` (`router.py`/`service.py`/`schemas.py`): CRUD de órdenes, ficha del
  vehículo, transiciones de estado.
- `backend/src/reportes_falla/`: dominio separado de `mantenimiento/` pero con el mismo destino
  operativo (bandeja compartida) — separado porque el conductor y el Jefe de Mantenimiento crean
  reportes por rutas distintas con distinta validación de origen.
- `backend/src/archivos/`: reutilizada para evidencia fotográfica (contexto `reporte_falla` y
  `actividad_orden`), sin mecanismo de subida propio.
- Colecciones: `ordenes` (con `actividades: []` insert-only), `reportes_falla`, `vehiculos`
  (`km_acumulado`).

## Frontend

- `apps/web-interno/src/sections/Mantenimiento.tsx` — 3 pestañas (Órdenes / Reportes de falla /
  Vehículos), patrón WorkPanel en la pestaña de Órdenes.
- `apps/web-conductor/src/App.tsx` — `ReportarFallaForm` (compartido entre "Registrar incidencia"
  dentro de un viaje y "Reportar falla del vehículo" fuera de turno), sección propia "Fallas del
  vehículo".

## Decisión de arquitectura: por qué el umbral preventivo es global

No existe en ningún lado del modelo de datos ni del código un "plan preventivo diferenciado por
antigüedad del vehículo" — la única referencia era un ejemplo ilustrativo de la spec original. Se
implementó con un umbral único (`UMBRAL_KM_PREVENTIVO`) en vez de inventar una diferenciación que
ningún dato real respalda.

## Decisión de arquitectura: por qué el reporte de falla usa un catálogo cerrado, a diferencia de taller/motivo

Se evaluó agregar la opción "Otro" (mismo patrón ya usado en taller/motivo de cancelación/marca/
color de vehículo) pero se revirtió: `reportes_falla/service.py::_validar_tipo_falla` exige que el
valor exista en el catálogo activo — relajar esa validación de negocio es una decisión de alcance
distinta, no se tomó sin pedido explícito.
