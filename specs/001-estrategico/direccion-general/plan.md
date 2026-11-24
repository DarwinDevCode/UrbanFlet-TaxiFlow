# Plan técnico (retroactivo): Dirección General

Diseño tal como quedó construido — no una propuesta.

## Backend

- **Módulo nuevo `backend/src/estrategico/`** (`router.py`/`service.py`/`schemas.py`), pero **no**
  es un módulo central que agrupe todo: solo aloja los 2 endpoints sin dominio dueño claro
  (Rentabilidad, que cruza finanzas+mantenimiento+despacho+flota; Tablero Ejecutivo, que cruza los
  8 por definición). Los otros 7 paneles viven en el router de su propio dominio
  (`GET /<dominio>/panel-estrategico/...`), mismo criterio ya usado en el nivel táctico.
- **`backend/src/core/agregacion_estrategica.py`**: helpers de segunda capa de agregación
  (`variacion_pct`, `promedio_ponderado`, `agrupar`, `ultimos_periodos`) usados por 7 de los 9
  paneles. `promedio_ponderado` existe porque las `rpt_*` publican porcentajes ya calculados por
  subgrupo — promediarlos sin ponderar por volumen le daría el mismo peso a una franja con 3
  registros que a una con 30.000.
- **Sin tabla `rpt_estrategico_*` nueva ni DAG nuevo**: la "tendencia extendida" sale de 2
  mecanismos según la fuente — tablas que ya traen periodo propio (`fetch_latest_snapshot` +
  agrupado), o tablas de corte puntual (`fetch_snapshot_history` sobre `fecha_datos`, aprovechando
  que son MergeTree y conservan un corte por corrida).

## Frontend

- `apps/web-interno/src/sections/estrategico/`: `PanelCrecimiento`, `PanelConfiabilidad`,
  `PanelEstadoCostoFlota`, `PanelCapacidades`, `PanelRentabilidad`, `PanelIntegridadFinanciera`,
  `PanelCumplimientoNormativo`, `PanelGobernanza`, `PanelDesempenoConductores`, `TableroEjecutivo` —
  más `formato.ts`/`comunes.tsx` compartidos.
- Reutiliza en su totalidad los componentes de `shared-ui` ya existentes del nivel táctico
  (`KpiCard`/`KpiRow`, `CategoryBarChart`/`TrendLineChart`, `DashboardZ`/`DashboardF`,
  `FuenteBadge`, `DataTable`, `useSwr`) — **cero componentes de gráfico nuevos**, salvo
  `MiniTendencia` (sparkline SVG inline dentro de `TableroEjecutivo.tsx`), justificado porque
  `TrendLineChart` (ejes, grilla, tooltip, leyenda) compite visualmente con el número en una
  tarjeta de 40-90px de alto.
- **Navegación cruzada** (`apps/web-interno/src/navegacion.ts`): Context de React que publica la
  misma `setSeccionActiva` que ya usaba el sidebar, sin cambiar la firma de ninguna de las ~32
  secciones existentes (`Seccion.render` sigue siendo `() => JSX.Element`).

## Decisión de arquitectura: por qué "Rentabilidad" y "Tablero" no viven en un dominio existente

Si un dashboard estratégico futuro tiene un dominio dueño claro, va en el router de ese dominio — el
módulo `estrategico/` no es un contenedor genérico para "todo lo estratégico", es exclusivamente
para lo que cruza dominios por definición.

## Convención de unidades (fuente real de errores evitados)

Todo campo `pct_*`/`margen_pct`/`share_*` viaja como fracción 0-1; todo `variacion_*_pct` viaja ya
en puntos porcentuales. Dos helpers distintos (`pct()` vs. `variacion()`) en vez de uno solo —
mezclarlos habría dado un "9842%" donde correspondía "98,4%".

## Referencias históricas

Ver `CLAUDE.md` §12 (backend, Fase 3) y §13 (frontend, Fase 4) para el detalle completo de
decisiones tomadas durante la construcción, incluidas las banderas de limitación documentadas caso
por caso.
