# Plan técnico (retroactivo): Cumplimiento Regulatorio (Táctico)

## Backend

- `cumplimiento/router.py`: 3 endpoints (documentos por vencer, documentación vigente, tendencia)
  — la tendencia mensual se resolvió con `fetch_snapshot_history` sobre `rpt_documentacion_vigente`
  sin crear tabla nueva ni tocar el DAG (esa tabla ya conservaba un corte por corrida).
- `auditoria/router.py`: reusa `GET /auditoria/eventos` tal cual (ya cubría actor/rol/acción/
  entidad/resultado/hora desde el nivel operativo) + `GET /auditoria/panel-tactico/uso-integraciones`
  nuevo, de solo lectura, sobre `rpt_uso_integraciones` (ya existía, alimentaba el catálogo de
  informes).

## Frontend

- `PanelDocumentacion.tsx` — patrón Z.
- `PanelAuditoria.tsx` — patrón F (único de los 10), con `altoMaximo` en la tabla (evita que 100
  filas sin límite estiren la página) y `width` fijo en la columna Rol (evita que un evento con
  varios roles concatenados estire toda la tabla).

## Decisión de arquitectura

"% error API" se muestra como "—" y luego se retira de la interfaz en vez de fabricar el dato —
mismo criterio transversal (RN-SIS-004) aplicado con consecuencia real: el KPI desapareció, no se
dejó como "—" indefinido.
