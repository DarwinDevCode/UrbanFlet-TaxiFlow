# Tareas (retroactivo): Mantenimiento

Trazabilidad completa en `CLAUDE.md` §18 ("Flujo de fallas del vehículo — Ronda 2, las 7 fases").

1. **Fase A** — infraestructura de carga de archivos (primer mecanismo `UploadFile`/multipart del
   proyecto), reutilizada después por foto de perfil y documentos de postulación.
2. **Fase B** — alimentar `km_acumulado` hacia adelante (cada viaje finalizado suma su distancia) y
   hacia atrás (backfill sobre el histórico real), más la ficha del vehículo.
3. **Fase C** — reporte de falla del conductor, con y sin viaje activo; corrección post-cierre
   agregando el aviso en vivo a Operaciones que faltaba.
4. **Fase D** — bandeja del Jefe de Mantenimiento y conversión de reporte a orden.
5. **Fase E** — estado nuevo `ESPERANDO_REPUESTO`, con registro automático en la cronología y
   cierre del hallazgo de auditoría faltante en "marcar en taller".
6. **Fase F** — actividades embebidas en la orden (cronología propia, insert-only).
7. **Fase G** — costo estimado vs. real con desviación mostrada al cerrar, y orden correctiva
   encadenada.
8. Catálogo de repuestos (Ola 3): precio referencial sugerido, siempre editable, cableado en los 3
   formularios que manejan líneas de repuesto.
9. Revisión general de "Otro" en selectores de catálogo — con la excepción deliberada de tipo de
   falla, revertida tras encontrar la validación de negocio real.
