# Plan técnico (retroactivo): Autoservicio de Usuario

## Backend

- `backend/src/perfil/`: `GET`/`PATCH /perfil`, `GET`/`DELETE /perfil/sesiones/{jti}` —
  autoservicio, separado de `usuarios/` (exclusivamente administrativo) y de `auth/` (tokens/
  credenciales).
- `backend/src/preferencias/`: documento único por cuenta en `preferencias_usuario`, sin auditoría
  (son ajustes de interfaz, no acciones de seguridad).
- `backend/src/archivos/`: contexto `foto_perfil`, único de lectura pública (sin sesión) — necesario
  porque la vista pública de "Compartir viaje" también muestra la foto del conductor.

## Frontend

- `apps/shared-ui/src/components/PerfilPropio.tsx`, `AjustesPropios.tsx`, `CentroAyuda.tsx`,
  `Avatar.tsx` — componentes únicos reutilizados por los 3 portales, no 3 implementaciones
  paralelas.
- `theme.ts`/`densidad.ts`/`sidebarTono.ts`/`tamanoTexto.ts` — mismo patrón para cada preferencia:
  aplicación síncrona antes del primer render (para no parpadear), variable CSS global.

## Decisión de arquitectura: por qué la foto de perfil es de lectura pública

A diferencia de la evidencia de fallas (gateada por rol), una foto de perfil no tiene ningún dato
sensible, y ya existía una superficie sin sesión que la necesita (Compartir viaje). El id del
archivo (UUID aleatorio) es la única protección — mismo criterio ya usado por el token de 256 bits
de Compartir viaje ("no listable, pero no requiere sesión").
