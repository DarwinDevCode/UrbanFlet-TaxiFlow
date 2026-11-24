# Tareas (retroactivo): Administración del Sistema

Los 8 módulos se construyeron en orden secuencial, cada uno cerrado y verificado antes de pasar al
siguiente. Trazabilidad completa en `CLAUDE.md` §9 (`PLAN_ADMIN_SISTEMA.md` es la fuente de
detalle por módulo, no duplicada aquí).

1. **Módulo 1 (IAM)** — cuentas, roles, políticas de contraseña/bloqueo, sesiones activas
   revocables. Primer uso de Redis para sesiones stateful del proyecto.
2. **Módulo 2 (Configuración General)** — parámetros globales versionados + funcionalidades
   activables.
3. **Módulo 6.1 (Auditoría administrativa)** — construido junto al resto pese al número, por
   dependencia técnica directa con el resto de módulos (ver `004-transversal/
   auditoria-y-trazabilidad`).
4. **Módulo 3 (Catálogos)** — zonas de despacho (extendiendo `parametros/` existente) + tipos de
   documento/motivos (módulo nuevo `catalogos/`).
5. **Módulo 8.1 (Versión/Despliegue)** — registro manual, sin CI/CD real en el proyecto.
6. **Módulo 6.2 (Políticas de seguridad)** — TTL de tokens y umbrales de rate limiting, antes
   constantes fijas.
7. **Módulo 6.3 (Alertas del sistema)** — de las 3 alertas que la spec asumía ya conectadas, solo 1
   lo estaba realmente (denegaciones RBAC); GPS spoofing se corrigió para disparar notificación
   real.
8. **Módulo 4 (Integraciones)** — CRUD de credenciales + rotación de Google Maps con efecto
   inmediato verificado en la petición saliente real.
9. **Módulo 5 (Monitoreo)** — bajo demanda, no vigilancia continua (decisión de alcance re-aprobada
   explícitamente).
10. **Módulo 8.2 (Gobernanza de datos)** — anonimización con doble confirmación real, política de
    retención con TTL leído del índice real de Mongo.
11. **Módulo 7 (Respaldos y Continuidad)** — el recorte de alcance más grande del bloque, con la
    opción de exportar vía drivers ya usados en producción (aprobada explícitamente tras confirmar
    que la imagen no tiene binarios de respaldo instalados).
12. **Ronda de usabilidad post-cierre (7 puntos)**: manejo de errores transversal, selects para
    valores finitos, catálogo de talleres, modo solo-lectura por defecto, selector real de
    usuarios, monitoreo con histórico + auto-refresco, gestión de conductores/pasajeros visible en
    Usuarios.
