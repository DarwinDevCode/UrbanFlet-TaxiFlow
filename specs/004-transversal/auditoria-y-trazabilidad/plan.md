# Plan técnico (retroactivo): Auditoría y Trazabilidad

## Backend

- `backend/src/core/audit.py`: `write_audit_event` — el punto único de escritura, llamado desde
  cualquier dominio antes de confirmar un efecto de negocio sensible (RNF-AUD-001).
  `ACCIONES_ADMINISTRATIVAS` — la lista que define qué acciones caen en la vista filtrada de
  Administración, expuesta por `GET /auditoria/acciones-administrativas` para que el frontend nunca
  mantenga un mirror manual desincronizado (ver `plan.md` de Administración del Sistema para el
  hallazgo real que motivó esto).
- `backend/src/auditoria/`: `GET /auditoria/eventos` (vista completa/filtrada, según rol).
- `backend/src/plataforma/`: catálogo de informes, sobre la tabla `corridas` de ClickHouse.
- Colección `bitacora`: insert-only, sin ningún mecanismo de edición ni borrado.

## Frontend

- `apps/web-interno/src/sections/Cumplimiento.tsx` (bloque "Bitácora de auditoría").
- `apps/web-interno/src/sections/AuditoriaAdmin.tsx` (vista filtrada, "Ver antes/después").
- `apps/web-interno/src/sections/Indicadores.tsx` (catálogo de informes).
