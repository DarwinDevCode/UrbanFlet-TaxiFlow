# Tareas (retroactivo): Operaciones y Despacho

Módulo construido en múltiples rondas a lo largo del proyecto; trazabilidad completa en
`CLAUDE.md` (secciones dispersas por ronda, ver el índice de esa bitácora).

1. Ciclo base: solicitar → auto-despacho por radios → aceptar → ejecutar (en camino/llegada/inicio)
   → finalizar → cobrar → calificar.
2. Reintentar búsqueda tras `SIN_CONDUCTOR` (CU-O05 A3), reutilizando origen/destino sin duplicar
   lógica de solicitud.
3. Compartir viaje en tiempo real: diseño anti-enumeración de tokens aprobado antes de construir
   (256 bits, 404 genérico, rate limiting).
4. Programar un viaje: nuevo estado `PROGRAMADO` + disparo diferido por Airflow cada 2 minutos +
   HTTP interno con token compartido — bug real corregido en el camino (`ESTADOS_ACTIVOS` estaba
   sombreado por una segunda definición del mismo nombre a nivel de módulo).
5. Flujo de fallas del vehículo, Fase C: reporte de incidencia del conductor, con cancelación real
   del viaje `EN_CURSO` y generación automática de uno nuevo si "no puedo continuar".
6. Corrección post-cierre: aviso en vivo al `coordinador_operaciones` (CU-O07 A4) — gap real
   encontrado por el usuario, el sistema solo notificaba a Mantenimiento, no a Operaciones.
7. Desglose de tarifa (CU-O08 paso 3): exponer arrancada/distancia/espera/subtotal, antes solo se
   mostraba el número final.
8. Mapa en el historial de viajes: exponer la traza GPS ya acumulada (existía desde siempre, nunca
   se había expuesto por API) en 2 endpoints con RBAC verificado explícitamente, y construir
   `MapaRutaViaje` en los 3 portales.
9. Corrección de layout: mover la calificación dentro del mismo panel flotante que "Tu viaje" (ver
   `plan.md`).
