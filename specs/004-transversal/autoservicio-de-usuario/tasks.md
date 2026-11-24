# Tareas (retroactivo): Autoservicio de Usuario

1. Construir `perfil/` como dominio separado de `usuarios/`/`auth/`, con edición de contacto
   exigiendo contraseña actual (decisión D1: sin OTP, ya no existe ese mecanismo en el sistema).
2. Construir foto de perfil general (cualquier rol, no solo conductor como en una implementación
   anterior más limitada) — reemplazo completo del campo de texto libre `conductor.foto_url` que
   nunca se usó realmente (0/194 usuarios lo tenían seteado).
3. Construir tema oscuro real (paleta completa nueva), densidad de tablas (variable CSS global, no
   una prop nueva en cada tabla), y color de sidebar configurable.
4. Construir Centro de ayuda como sección del sidebar (no un ícono flotante), mismo patrón que
   "Mi perfil"/"Ajustes".
5. Sembrar 26 usuarios ficticios con foto real, vía los servicios reales de cada rol (nunca
   inserción directa en Mongo) — para tener datos de demo reales con identidad visual completa.

Trazabilidad completa en `CLAUDE.md` §10 y §22.
