# Plan técnico (retroactivo): Coordinación de Flota (Táctico)

## Backend

- `GET /flota/panel-tactico/franja-activa` (compuesto, tabla `rpt_flota_activa_franja`) +
  `GET /flota/tablero` reusado tal cual para los KPIs y la lista de sin-señal (informe simple, sin
  endpoint nuevo).
- DAG `dag_flota_gold`: bug real corregido — `posiciones` nunca trae `estado_servicio` en el propio
  documento (vive en `usuarios.conductor.estado_servicio`); corregido con un join de lectura por
  `conductor_id` + columna Bronze relajada a `Nullable(String)` como respaldo.

## Frontend

- `apps/web-interno/src/sections/tactico/PanelFlota.tsx` — patrón Z (`DashboardZ`), `KpiRow` +
  `CategoryBarChart`, `FuenteBadge` junto a cada bloque.

## Decisión de arquitectura

Ningún cálculo nuevo del lado del frontend — el filtro por franja recalcula sobre datos ya
agregados por Airflow, nunca agregando en el cliente (regla transversal del nivel táctico).
