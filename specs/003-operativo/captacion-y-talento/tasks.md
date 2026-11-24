# Tareas (retroactivo): Captación y Talento

Trazabilidad completa en `CLAUDE.md` §26.3 ("Gestión documental en la postulación").

1. Confirmar el gap real: `DocumentoInput.tipo` era texto libre sin validar contra el catálogo
   (`tipos_documento` ya existía por otro motivo).
2. Validar `documentos[].tipo` contra el catálogo, con 422 `TIPO_DOCUMENTO_INVALIDO` antes de
   cualquier efecto de negocio — sin tocar la máquina de estados de la solicitud.
3. Construir el flujo de 3 pasos: `crear_solicitud(enviar=False)` → login instrumental →
   `POST /archivos` ×2 → `enviar_solicitud_con_documentos`.
4. Construir el frontend de `web-conductor`: sección "Documentos" con `FileField` + fecha por cada
   tipo, deshabilitando "Enviar solicitud" hasta que ambos estén completos.
5. Construir el bloque de revisión en `web-interno` → Solicitudes: visor real de imagen (reusa
   `EvidenciaImagen`) + fecha + semáforo de vigencia calculado contra hoy.
6. Verificar en vivo, extremo a extremo: postulación real con 2 PNG generados en el navegador,
   confirmados en Mongo con su hash SHA-256 exacto; aprobación real generando 2 documentos reales
   vinculados al conductor y al vehículo nuevo.
7. Confirmar aprovechamiento downstream sin trabajo adicional: el control de vigencia diario
   (Cumplimiento) recogió los 2 documentos nuevos en su siguiente corrida, sin ningún cambio de
   código — mismo mecanismo que ya barría `documentos` sin filtrar por origen.
