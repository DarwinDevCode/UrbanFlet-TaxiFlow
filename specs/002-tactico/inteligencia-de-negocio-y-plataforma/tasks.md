# Tareas (retroactivo): Inteligencia de Negocio y Plataforma (Táctico)

1. Construir `rpt_cuarentena_dominio` + tarea nueva en `dag_publicar_indicadores`.
2. Construir `PanelPlataforma.tsx`, último de los 9 dashboards originales por diseño (explica "de
   dónde sale todo lo demás", buen cierre).
3. Quitar el KPI "Capacitación" de la interfaz (nunca tuvo dato real detrás).
4. Resolver el techo de memoria de ClickHouse que bloqueaba corridas reales de varios DAGs de forma
   intermitente (causa real: tablas de log internas del propio motor sin TTL, no el volumen de
   datos de negocio) — corregido con TTL real en esas tablas, sin subir `mem_limit`.

Trazabilidad completa en `CLAUDE.md` §7 punto 5, entrada 7, y §34.
