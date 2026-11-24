# Tareas (retroactivo): Cumplimiento Regulatorio

1. Construir el control de vigencia documental (barrido completo, notificación al propietario real
   — conductor directo, o dueño del vehículo si el documento es del vehículo).
2. Cerrar el gap real: construir el autoservicio del conductor (`GET /cumplimiento/documentos/mios`,
   `subir_renovacion`) — antes de esto no existía ninguna pantalla desde donde generar una
   renovación pendiente, así que la bandeja de Cumplimiento estaba condenada a quedar vacía para
   siempre.
3. Construir la aprobación/rechazo de una renovación por `supervisor_cumplimiento`.
4. Confirmar el aprovechamiento downstream sin trabajo adicional: los documentos de una postulación
   aprobada (Captación) entran solos al barrido del control de vigencia.
