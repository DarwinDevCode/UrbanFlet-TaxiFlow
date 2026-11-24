# Plan técnico (retroactivo): Notificaciones

## Backend

- `backend/src/notificaciones/`: `NotificationService.notify_user()` persiste siempre en
  `notificaciones_usuario` (TTL 30 días) antes de intentar la entrega en vivo — un solo punto de
  cambio, ningún call site existente tocado al construirlo.
- Taxonomía de categorías: `captacion`, `cumplimiento`, `mantenimiento`, `viaje`, `seguridad` (esta
  última nunca configurable).

## Frontend

- `apps/shared-ui/src/components/NotificacionesBell.tsx` — ícono SVG real (feather-style,
  `stroke="currentColor"`), no la librería de íconos que no existe en el proyecto.
- `apps/shared-ui/src/components/SeccionNotificaciones.tsx` — sección completa compartida por los 3
  portales.
- `apps/shared-ui/src/notificacionesCatalogo.ts` — diccionario único de etiquetas por tipo real,
  fuente única para campana y sección completa (antes cada consumidor tenía su propio mapa,
  desincronizado en la práctica).

## Decisión de arquitectura: por qué el contador global ignora el filtro visible

Si el contador reflejara solo lo filtrado, un usuario que filtra por un tipo específico vería "0 no
leídas" aunque tuviera notificaciones sin leer de otro tipo — una falsa sensación de estar al día.
