# Plan técnico (retroactivo): Inteligencia de Negocio y Plataforma (Táctico)

## Backend

- `rpt_cuarentena_dominio` (nuevo, agrega la corrida MÁS RECIENTE de cada DAG desde `corridas` — es
  el único informe que no depende del gate OK/WARN de un solo dominio, es meta-informe sobre los 7
  DAGs a la vez).
- `GET /plataforma/panel-tactico/corridas` (filtro dominio/fecha_logica) sobre la tabla real
  `corridas` de ClickHouse.

## Frontend

- `PanelPlataforma.tsx` — patrón Z.

## Decisión de arquitectura: por qué no hay colección `corridas_etl` en Mongo

La spec original la pedía, pero el seguimiento de corridas ya vivía en ClickHouse desde el diseño
original de la plataforma de datos — construir una segunda fuente en Mongo habría duplicado el
mismo dato sin ningún beneficio real, y se documentó la divergencia en vez de forzarla a coincidir.
