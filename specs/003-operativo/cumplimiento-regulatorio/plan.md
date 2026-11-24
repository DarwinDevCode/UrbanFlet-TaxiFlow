# Plan técnico (retroactivo): Cumplimiento Regulatorio

## Backend

- `backend/src/cumplimiento/` (`router.py`/`service.py`): `ejecutar_control_vigencia_documental`,
  `listar_mis_documentos` (autoservicio del conductor), `subir_renovacion`, `verificar_renovacion`.
- Colección `documentos`: compartida con Captación (los documentos de una postulación aprobada
  entran aquí sin ningún paso adicional).

## Frontend

- `apps/web-interno/src/sections/Cumplimiento.tsx` — WorkPanel + botón de control de vigencia +
  bandeja de renovaciones pendientes.
- `apps/web-conductor/src/App.tsx` — sección "Mis documentos" (autoservicio del conductor: ver
  vigencia propia, subir renovación).

## Decisión de arquitectura: por qué el cálculo de vencimiento usa UTC explícito

`date.today()` habría usado la zona horaria local del sistema/contenedor donde corre el proceso —
inconsistente con el resto de la arquitectura, que exige timestamps en UTC precisamente para evitar
que el mismo cálculo dé un resultado distinto según dónde se ejecute.
