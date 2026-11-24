# Tareas (retroactivo): Notificaciones

1. Construir el mecanismo de persistencia siempre-primero (`notify_user`).
2. Construir la campana (`NotificacionesBell`) y la sección completa (`SeccionNotificaciones`),
   llevando la sección de solo campana a sección propia del sidebar en los 3 portales.
3. Reemplazar el emoji 🔔 por un ícono SVG real, siguiendo el patrón ya establecido en el proyecto
   (sin librería de íconos instalada).
4. Construir el diccionario único de etiquetas por tipo, cerrando la desincronización real que
   tenían los mapas locales de cada consumidor.
5. Cablear la acción rápida por tipo, verificando contra el rol/destinatario real de cada uno antes
   de enrutar (5 destinos verificados: Solicitudes, Auditoría ×2, Plataforma, Mantenimiento,
   Despacho).

Trazabilidad completa en `CLAUDE.md` §25 y §10 (Sección 4.2 de `ux_complementaria.md`).
