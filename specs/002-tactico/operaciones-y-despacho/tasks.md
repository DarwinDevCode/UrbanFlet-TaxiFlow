# Tareas (retroactivo): Operaciones y Despacho (Táctico)

1. Construir Despacho: `fact_ciclo_viaje`, 2 endpoints admin, `PanelDespacho.tsx` — el mayor gap
   real del proyecto en su momento (nivel operativo sin panel táctico propio).
2. Verificación de compatibilidad de esquema antes de tocar `fact_ciclo_viaje`/`fact_viaje` para
   agregar Rendimiento de Conductores: grep de cada consumidor real, confirmando que ninguno usa
   `SELECT *`.
3. Agregar `conductor_id` a `fact_ciclo_viaje` y `calificacion_puntaje` a `fact_viaje` (Bronze y
   Gold — bug real corregido cuando la primera corrida reventó por faltar en Bronze).
4. Construir `rpt_desempeno_conductor`/`rpt_ingreso_conductor` y `PanelRendimientoConductores.tsx`.
5. Corregir el bug real de "ventana reciente no evita la advertencia si igual incluye NYC" —
   encontrado en la propia verificación en navegador, no en teoría.
6. Corregir la tasa de cancelación de raíz (ver `spec.md` §13) — mismo defecto presente también en
   el panel estratégico homólogo, corregido en la misma pasada.

Trazabilidad completa en `CLAUDE.md` §7 punto 5, entrada 5, y §17.4.
