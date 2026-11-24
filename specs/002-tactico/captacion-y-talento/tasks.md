# Tareas (retroactivo): Captación y Talento (Táctico)

1. Cerrar el gap de `canal` (campo nuevo, propagado a solicitudes y usuarios, con backfill real).
2. Corregir el bug real de `fact_registro_usuario` (filtro por un campo que nunca existió).
3. Construir `rpt_conversion_captacion`/`rpt_altas_retencion_canal` y `PanelCaptacion.tsx`.
4. Documentar la regresión posterior real: el backfill dejó `usuarios` con 49% sin `canal` tras
   rondas de siembra de datos ricos que no pasaron por el flujo que lo setea — decisión tomada de
   no reintentar el backfill, documentado como limitación conocida en vez de bloquear trabajo
   posterior por esto.

Trazabilidad completa en `CLAUDE.md` §7 punto 5, entrada 4, y hallazgo H3 de
`AUDITORIA_NIVEL_ESTRATEGICO.md`.
