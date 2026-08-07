# PLAN — Módulo de Administración del Sistema

Spec fuente: `specs/specs-administrativas/admin_sistema.md`. Este archivo se
actualiza conforme avanza el trabajo — cada tarea se marca `[x]` al cerrarse
(con verificación en navegador donde aplique), nunca se da por completa solo
porque el código fue escrito.

**Decisión confirmada por el usuario (2026-08-04):** se crea el rol nuevo
`admin_sistema`, separado de `admin_plataforma`. Justificación: principio de
mínimo privilegio ya declarado en `operativo_cumplimiento.md` — separa
permisos de seguridad/infraestructura de los permisos de negocio de datos
que ya tiene `admin_plataforma`.

Leyenda de estado: ⬜ pendiente · 🔶 en curso · ✅ completo y verificado ·
✂️ alcance recortado (aprobado) · 🚫 fuera de alcance (backlog consciente)

---

## 0. Hallazgos de la exploración previa (no duplicar)

- **RBAC** (`backend/src/core/rbac.py`): `ROLES` frozenset, `require_roles()`,
  `Actor`, suspensión de sesión vía Redis. Se **extiende** (agregar
  `admin_sistema` al frozenset), no se reemplaza.
- **Auditoría** (`backend/src/core/audit.py::write_audit_event`,
  `AccionAuditoria` StrEnum): único escritor de bitácora, insert-only. Se
  **reutiliza** para todo el Módulo 6 y las acciones de los Módulos 1/2/8 —
  requiere ampliar el catálogo `AccionAuditoria` con las acciones
  administrativas nuevas (mismo patrón, no un enum paralelo).
- **Parámetros versionados** (`backend/src/parametros/service.py::_crear_version`):
  patrón cerrar-versión-anterior + insertar-nueva ya probado con
  `PARAMETRO_TARIFA`/`PARAMETRO_COMISION`. Se **reutiliza** para Módulo 2.1.
- **Zonas** (`parametros/service.py`, colección `zonas`): CRUD-lite
  (crear+listar, sin editar/eliminar). Módulo 3.1 lo **extiende** con
  editar/eliminar-con-bloqueo-si-en-uso, no lo duplica.
- **Redis** (`backend/src/core/db_redis.py`): patrones ya en uso
  (`auth:login_locked:*`, `rbac:suspended:*`, `rbac:denials:*`,
  `pos:{vehiculo_id}`). **No existe** un registro de sesiones activas — el
  Módulo 1.4 requiere una estructura nueva (`sesion:{usuario_id}:{jti}` o
  similar), construida sobre la misma infraestructura Redis ya presente.
- **Frontend**: `SECCIONES` en `apps/web-interno/src/App.tsx` (patrón
  `{id, etiqueta, roles, grupo?, render}`) — se agrega un grupo
  `"Administración"` nuevo, mismo mecanismo que `"Panel Táctico"`. Reutilizar
  `DataTable`, `Pagination`, `DetailPanel`/`DetailField`, `ActionBar`
  (patrón WorkPanel), `KpiCard`/`KpiRow`, `CategoryBarChart`/`TrendLineChart`,
  `DashboardZ`/`DashboardF`, `FuenteBadge` — todos en `shared-ui`, ninguno se
  reconstruye.
- **Sin infraestructura previa** para: usuarios-CRUD/roles-UI, políticas de
  auth configurables, feature flags, credenciales de integración, monitoreo/
  health-checks, respaldos/DR, versión/deploy-history, gobernanza de
  datos/anonimización. Los 8 módulos son, en su mayoría, dominio nuevo.

---

## 1. Orden de construcción propuesto y dependencias

```
Módulo 1 (IAM)  ──┐
                   ├─→ Módulo 6.1 (auditoría admin, filtra eventos de 1/2/8)
Módulo 2 (Config) ─┤
Módulo 3 (Catálogos) (independiente, sin dependencias)
Módulo 4 (Integraciones) (independiente)
Módulo 5 (Monitoreo) (independiente)
Módulo 6.2/6.3 (Seguridad/Notificaciones) ── depende de Módulo 1.3/1.4 (políticas) y notificaciones existentes
Módulo 7 (Respaldos/DR) (independiente, más aislado)
Módulo 8.1 (Versión) (independiente, trivial)
Módulo 8.2 (Gobernanza de datos) ── depende de auditoría (6.1) para el evento de anonimización
```

Razón del orden: Módulo 1 primero porque el rol `admin_sistema` y el gate de
acceso a **todo** lo demás dependen de que exista la UI de administración de
cuentas/roles (aunque el rol en sí se agrega a `rbac.py` desde el día 1,
antes de tener UI). Módulo 6.1 se construye justo después de 1 y 2 porque
son los primeros módulos que generan eventos que necesita mostrar. El resto
(3, 4, 5, 7, 8) son independientes entre sí y pueden reordenarse sin costo —
se proponen en el orden de menor a mayor esfuerzo relativo dentro de ese
grupo para entregar valor incremental rápido.

**Orden final de construcción:**

1. Módulo 1 — Gestión de Usuarios y Control de Acceso (IAM)
2. Módulo 2 — Configuración General (parámetros + feature flags)
3. Módulo 6.1 — Auditoría de cambios administrativos (vista filtrada)
4. Módulo 3 — Catálogos y Parámetros de Negocio
5. Módulo 8.1 — Versión/despliegue (trivial, alto valor/esfuerzo)
6. Módulo 6.2 — Políticas de seguridad
7. Módulo 6.3 — Alertas y notificaciones del sistema
8. Módulo 4 — Integraciones Externas
9. Módulo 5 — Monitoreo y Observabilidad
10. Módulo 8.2 — Gobernanza de datos y cumplimiento
11. Módulo 7 — Respaldos, Recuperación y Continuidad (último — el más
    "infraestructura simulada", tiene sentido cerrarlo con todo lo demás ya
    auditable)

---

## 2. Decisión de modelo de roles (ya confirmada)

- [x] Agregar `"admin_sistema"` a `ROLES` en `backend/src/core/rbac.py`.
- [x] Documentado en este plan y pendiente de reflejar en `CLAUDE.md` al
      cierre (Fase 3).
- [ ] Crear cuenta de demo `admin_sistema` (nueva, análoga a las de §8.7 de
      `CLAUDE.md`) una vez exista el login — se crea junto con Módulo 1.

**Alcance de acceso**: todos los endpoints de los 8 módulos se gatean
exclusivamente a `admin_sistema` (mínimo privilegio, tal como pide la spec),
salvo Módulo 7.2 (plan de DR) y Módulo 8.2, que la spec marca explícitamente
como también visibles a `gerencia` (7.2: "su acceso debe restringirse solo a
`admin_sistema` y gerencia").

---

## 3. Plan por módulo — fases, tareas, esfuerzo, recorte de alcance

Esfuerzo: **S** (una sesión corta, <2h), **M** (media sesión, 2-4h), **L**
(sesión completa o más, 4h+). Es una estimación de trabajo con agente, no de
horas-persona tradicionales.

### Módulo 1 — IAM (esfuerzo total: L)

| # | Tarea | Backend | Frontend | Esfuerzo |
|---|---|---|---|---|
| 1.1 | Administración de cuentas: crear cuenta staff, editar contacto, forzar cambio de contraseña, suspender/dar de baja, ver historial de accesos | `usuarios/router.py`+`service.py` nuevo: `POST /usuarios`, `GET /usuarios`, `GET /usuarios/{id}`, `PATCH /usuarios/{id}`, `POST /usuarios/{id}/suspender`, `POST /usuarios/{id}/reactivar`, `POST /usuarios/{id}/dar-de-baja`, `GET /usuarios/{id}/accesos` (reusa `auditoria` filtrando accion=LOGIN*/actor_id) | `Usuarios.tsx` con WorkPanel (Solicitudes.tsx como referencia) | M |
| 1.2 | RBAC: asignar/revocar roles, consultar matriz de permisos, roles compuestos | `PATCH /usuarios/{id}/roles` (valida contra `rbac.ROLES`); `GET /usuarios/matriz-permisos` (estático, generado del catálogo de `require_roles()` por router — **ver nota de alcance abajo**) | Panel de roles dentro de `Usuarios.tsx` (checkboxes de roles + vista de matriz de solo lectura) | M |
| 1.3 | Políticas de auth: longitud/complejidad de contraseña, umbral de bloqueo, vencimiento periódico | Tabla `POLITICA_AUTH` (patrón versionado de `parametros`) + endpoints `GET/POST /seguridad/politica-auth`; **`auth/service.py` debe leer estos valores en vez de las constantes fijas actuales** (cambio real de comportamiento, no solo UI) | `PoliticasAuth.tsx` (formulario simple) | M |
| 1.4 | Sesiones activas: listar, cerrar remota, ver intentos fallidos | Requiere registro de sesión en Redis al emitir un access token (`sesion:{usuario_id}:{jti}` con TTL = vida del token, valor = {ip, dispositivo, ts_inicio}); `GET /usuarios/{id}/sesiones`, `DELETE /usuarios/{id}/sesiones/{jti}` (borra la clave + agrega `jti` a una blocklist que `rbac.get_current_actor` consulta) | `Sesiones.tsx` (lista + botón cerrar) | L (cambia el flujo de emisión/verificación de tokens, alto cuidado) |

**Nota de alcance 1.2** — "matriz de permisos vigente por rol" no existe
hoy como dato consultable: los roles requeridos están hardcodeados por
`require_roles(...)` en cada router, no en una tabla. Construir un
introspector real (recorrer todas las rutas FastAPI y sus dependencias)
es factible pero fuera de lo que un CRUD académico necesita. **Propuesta
✂️**: generar la matriz de forma **estática** en un módulo Python
(`backend/src/usuarios/permisos_matriz.py`, un diccionario mantenido a mano
`{endpoint: [roles]}` a partir de los routers existentes) en vez de
introspección dinámica de FastAPI. Se actualiza a mano si se agrega un
endpoint nuevo — igual que hoy se actualiza `ROLES` a mano. Pendiente de tu
aprobación (punto 5 de tu instrucción).

**Nota de alcance 1.2 — "crear roles compuestos para necesidades de
prueba"**: interpretado como "asignar múltiples roles ya existentes a una
cuenta" (como `staff-verificacion` ya hace), **no** como crear un rol nuevo
dinámicamente en `ROLES` sin tocar código — eso rompería `require_roles()`,
que valida contra el frozenset en tiempo de arranque. Si se necesitara un
rol verdaderamente nuevo, seguiría requiriendo una línea de código. Esta
interpretación ya cubre el caso de uso real descrito en la spec (combinar
roles existentes), documentado aquí para no reabrir la ambigüedad después.

### Módulo 2 — Configuración General (esfuerzo total: M)

| # | Tarea | Backend | Frontend | Esfuerzo |
|---|---|---|---|---|
| 2.1 | Parámetros globales versionados (idioma, zona horaria, radio despacho, radios de ampliación, expiración de oferta) | Extender `parametros` con `PARAMETRO_SISTEMA` (mismo patrón `_crear_version`); **`viajes/service_dispatch.py` debe leer el radio/expiración desde este parámetro en vez de las constantes 300m/3/20s actuales** | `ParametrosGlobales.tsx` (WorkPanel simple, valores + historial) | M |
| 2.2 | Feature flags: activar/desactivar por % o rol, ver activos | Colección `feature_flags` nueva (`{_id, nombre, activo, porcentaje?, roles?, actualizado_en}`); `GET/POST/PATCH /flags`; helper `is_flag_enabled(nombre, actor)` en `core/` para que otros módulos lo consulten (no se cablea ningún flag real a una función existente en este alcance — ver nota) | `FeatureFlags.tsx` (WorkPanel) | S |

**Nota de alcance 2.2**: la spec sugiere usarlo para gobernar el
"pago electrónico" u otro backlog — **no se conecta ningún flag a
funcionalidad real todavía** (el pago electrónico sigue fuera de alcance,
CLAUDE.md §8.3). Se construye el mecanismo genérico
(crear/activar/desactivar/consultar) y se deja listo para que un futuro
backlog lo use — es infraestructura demostrable, no una integración end-to-end
con una función de negocio inexistente.

### Módulo 6.1 — Auditoría de cambios administrativos (esfuerzo: S)

| # | Tarea | Backend | Frontend | Esfuerzo |
|---|---|---|---|---|
| 6.1 | Vista filtrada de bitácora (solo acciones administrativas), comparación antes/después | Ampliar `AccionAuditoria` con acciones nuevas (`USUARIO_CREADO`, `ROL_MODIFICADO`, `PARAMETRO_SISTEMA_MODIFICADO`, `FLAG_MODIFICADO`, `CATALOGO_MODIFICADO`, `CREDENCIAL_ROTADA`, etc.); `GET /auditoria/eventos` ya soporta filtro por `accion` — **no requiere endpoint nuevo**, solo que los módulos 1/2/3/4/8 llamen `write_audit_event` con antes/después en el payload | `AuditoriaAdmin.tsx` (reusa patrón de tabla, filtro preseleccionado a las acciones administrativas) | S |

**Nota**: "comparación antes/después" requiere que `write_audit_event` (o
quien lo llama) incluya un campo de detalle con el valor viejo/nuevo. Hoy
`EVENTO_AUDITORIA` no tiene un campo genérico para esto — se agrega
`detalle: dict | None` opcional al escritor y al schema `EventoAuditoriaOut`
(cambio aditivo, no rompe los eventos existentes que no lo usan).

### Módulo 3 — Catálogos (esfuerzo: M)

| # | Tarea | Backend | Frontend | Esfuerzo |
|---|---|---|---|---|
| 3.1 | CRUD completo de zonas (editar/eliminar con bloqueo si en uso) | Extender `parametros/service.py`: `PATCH /parametros/zonas/{id}`, `DELETE /parametros/zonas/{id}` (bloquea si hay `viajes`/`fact_viaje` referenciando la zona) | `Catalogos.tsx` — pestaña Zonas | S |
| 3.2 | CRUD tipos de documento | Colección nueva `tipos_documento` | Catalogos.tsx — pestaña Tipos de documento | S |
| 3.3 | CRUD motivos de cancelación/incidencia | Colección nueva `motivos_cancelacion` (**nota**: hoy `motivo_cancelacion` en `viajes` es texto libre, no una FK a catálogo — este CRUD gestiona la taxonomía de referencia, no migra los datos ya existentes a claves foráneas, sería un cambio de esquema mayor fuera de alcance) | Catalogos.tsx — pestaña Motivos | S |

### Módulo 8.1 — Versión/Despliegue (esfuerzo: S)

| # | Tarea | Backend | Frontend | Esfuerzo |
|---|---|---|---|---|
| 8.1 | Ver versión de backend/frontends, historial de despliegues | `GET /sistema/version` (lee de una constante/env `APP_VERSION` + fecha de build); historial de despliegues **✂️ recortado** (ver nota) | `VersionSistema.tsx` (tarjeta simple) | S |

**Nota de alcance 8.1**: no existe pipeline de CI/CD real en este proyecto
(no hay GitHub Actions ni sistema de despliegue automatizado documentado).
**Propuesta ✂️**: "historial de despliegues" se demuestra con una colección
`registro_versiones` donde cada entrada se agrega manualmente (o vía un
script) al cerrar una sesión de desarrollo — mismo espíritu que este propio
`CLAUDE.md` ya lleva un historial de cambios por sesión, pero como dato
consultable desde la UI en vez de markdown. No hay despliegue real que
registrar automáticamente. Pendiente de tu aprobación.

### Módulo 6.2 — Políticas de seguridad (esfuerzo: S)

| # | Tarea | Backend | Frontend | Esfuerzo |
|---|---|---|---|---|
| 6.2 | Configurar TTL de access/refresh token, rate limiting por endpoint | Tabla `POLITICA_SEGURIDAD` (mismo patrón versionado); **cambio real**: `core/security.py::create_token` debe leer el TTL configurado en vez de la constante fija actual | `PoliticasSeguridad.tsx` | S–M |

**Nota de alcance 6.2** — "rate limiting por endpoint sensible": hoy el
rate-limiting real del sistema es específico (login lockout, refresh
lockout, denegaciones RBAC) — no hay un middleware genérico de rate
limiting por ruta. **Propuesta ✂️**: la UI permite configurar el umbral de
estos 3 mecanismos ya existentes (reusa 1.3 en parte), no construye un
rate-limiter genérico nuevo para "cualquier endpoint sensible" — eso sería
un middleware transversal nuevo, fuera de proporción para este alcance.
Pendiente de tu aprobación.

### Módulo 6.3 — Alertas y notificaciones del sistema (esfuerzo: M)

| # | Tarea | Backend | Frontend | Esfuerzo |
|---|---|---|---|---|
| 6.3 | Configurar canal/destinatarios por tipo de alerta (spoofing GPS, denegaciones, pipeline fallido) | Colección `configuracion_alertas` (`{tipo_alerta, canal, destinatarios_adicionales}`); `core/rbac.py::_alertar_supervisores_cumplimiento` y el disparador de "pipeline fallido" (Airflow, si existe) deben leer destinatarios de aquí además del rol fijo actual | `ConfiguracionAlertas.tsx` | M |

### Módulo 4 — Integraciones Externas (esfuerzo: L)

| # | Tarea | Backend | Frontend | Esfuerzo |
|---|---|---|---|---|
| 4.1 | Credenciales de integración: crear (hash, no texto plano), revocar, ver uso | Colección `credenciales_integracion` (`{_id, nombre, hash_secreto, vigente_desde, vigente_hasta, alcance, revocada}`); endpoints CRUD + middleware que valida credencial en `GET /ext/v1/...` (**verificar primero si ese endpoint ya existe** — la spec lo asume) | `Integraciones.tsx` — pestaña Credenciales | M |
| 4.2 | Estado de servicios externos (Maps, SMS, S3), rotar API key enmascarada | `GET /sistema/servicios-externos` (verifica config presente/ausente para Google Maps — S3/SMS no están integrados hoy, se muestran como "no configurado", no simulado como activo); **no hay rotación real de key sin reiniciar backend** — ver nota | Integraciones.tsx — pestaña Servicios externos | M |

**Nota de alcance 4.1 — verificado (2026-08-04), confirmado ANTES de
construir Módulo 1 según pedido del usuario**: `GET /ext/v1/...` **no
existe en el código** — grep completo de `backend/` sin resultados. Solo
está documentado como diseño en `specs/specs-generales/
arquitectura_software.md:103` ("`GET /ext/v1/...` de solo lectura...
autenticada por API key con rate limit"). El informe táctico
`rpt_uso_integraciones` (ya construido, dashboard de Auditoría) no lee
tráfico real de ese endpoint — se alimenta de `fact_integracion_api`, que
`analytics/plugins/indicadores.py:406-409` documenta explícitamente como
"aproximado desde bitácora" vía `dag_cumplimiento_gold`, porque no existe
otra fuente. **Alcance confirmado para 4.1**: el CRUD de credenciales se
construye completo y real (crear con hash irreversible, revocar con efecto
inmediato, listar/ver metadatos, todo auditado) — pero **sin** el
middleware de validación contra un endpoint inexistente. "Uso de cada
credencial" se muestra en 0/sin dato con nota explícita, mismo criterio que
"% error API" ya documentado como backlog consciente en el dashboard de
Auditoría (CLAUDE.md §8.3). No se construye `GET /ext/v1/...` desde cero —
eso sería inventar un consumidor externo real que nadie pidió.

**Nota de alcance 4.2 — "rotar API key sin reiniciar el backend"**: las
claves reales (Google Maps) hoy viven en variables de entorno leídas al
arrancar el proceso (`core/config.py::Settings`) — rotarlas sin reiniciar
requeriría recargar `Settings` en caliente, un cambio de arquitectura no
trivial. **Propuesta ✂️**: se construye el flujo de UI completo (rotar →
nueva key enmascarada, key vieja invalidada, evento de auditoría) escribiendo
la key nueva a una colección Mongo (`servicios_externos_config`) que las
llamadas reales a Google Maps consultan en cada petición **en vez de** la
variable de entorno directamente — esto sí logra "sin reiniciar" de verdad,
con un fallback a la env var si no hay override en Mongo. Pendiente de tu
aprobación (es más trabajo que un mock, pero es honesto).

### Módulo 5 — Monitoreo y Observabilidad (esfuerzo: M)

| # | Tarea | Backend | Frontend | Esfuerzo |
|---|---|---|---|---|
| 5.1 | Panel de estado de componentes (backend, Mongo, ClickHouse, Redis, Airflow) | `GET /sistema/salud` — ping real a cada servicio (Mongo `ping` command, Redis `PING`, ClickHouse `SELECT 1`, Airflow `GET /health` si accesible desde el backend) con latencia medida real, no simulada | `Monitoreo.tsx` — reusa `KpiCard`/`DashboardZ` (patrón visual de los 9 dashboards tácticos) | M |
| 5.2 | Alertas configurables por umbral (ej. latencia API > 2s) | Colección `umbrales_monitoreo`; **sin motor de alertas en tiempo real activo** (no hay proceso de background que evalúe umbrales continuamente) | mismo panel, sección de configuración de umbrales | S |

**Nota de alcance 5.2**: "alertas configurables por umbral" en producción
real implicaría un proceso que sondea continuamente y dispara notificación —
no hay ningún worker/cron en este stack apto para eso sin agregar
infraestructura nueva (Celery beat, etc.), desproporcionado para el alcance.
**Propuesta ✂️**: se construye la configuración de umbrales (guardar el
valor) y el panel de estado los usa para **colorear** la tarjeta
(verde/ámbar/rojo) cuando el humano abre el panel — evaluación bajo demanda,
no vigilancia continua ni alerta push automática. Pendiente de tu aprobación.

### Módulo 8.2 — Gobernanza de datos (esfuerzo: M)

| # | Tarea | Backend | Frontend | Esfuerzo |
|---|---|---|---|---|
| 8.2 | Anonimizar usuario (irreversible, doble confirmación, auditado) | `POST /usuarios/{id}/anonimizar` — seudonimiza `nombre`/teléfono/correo en `usuarios` y en `bitacora.actor_id` (o un mapeo, ver nota), requiere reautenticación o confirmación por texto ("ANONIMIZAR") | `GobernanzaDatos.tsx` — búsqueda de usuario + botón con doble confirmación | M |
| 8.2b | Ver política de retención vigente por tipo de dato | Estático/documentado (TTL de `posiciones` ya es 7 días real en Mongo — se lee del índice TTL existente vía `db.command("listIndexes")`, no hardcodeado) | misma pantalla, sección de solo lectura | S |

**Nota de alcance 8.2**: anonimizar `bitacora.actor_id` retroactivamente
rompe la trazabilidad de eventos pasados (el propio principio de la
auditoría). **Propuesta**: seguir el patrón que CU-O17 A2 ya describe
(seudonimizar el *identificador* que se muestra, no borrar el evento) —
se agrega un campo `actor_id_original` cifrado/hash o un mapeo separado en
una colección `usuarios_anonimizados` para que la bitácora conserve
integridad referencial pero el dato personal (nombre/teléfono real) quede
irrecuperable. Esto es fidelidad al texto de CU-O17 A2 ya existente, no una
interpretación nueva — se documenta aquí porque es la parte más delicada
del módulo.

### Módulo 7 — Respaldos y Continuidad (esfuerzo: M, alcance recortado por diseño)

| # | Tarea | Backend | Frontend | Esfuerzo |
|---|---|---|---|---|
| 7.1 | Estado/fecha de último respaldo, disparar respaldo manual, restaurar en entorno de prueba | Ver nota de alcance — **✂️ recortado explícitamente, ya anticipado en tu instrucción** | `Respaldos.tsx` | M |
| 7.2 | Plan de DR: RTO/RPO documentado por dominio, registro de simulacros | Colección `plan_dr` (RTO/RPO por dominio, texto libre) + `simulacros_dr` (fecha, resultado, notas) — esto sí es 100% real y construible (es un registro, no una operación de infraestructura) | `PlanContinuidad.tsx` (dentro de Respaldos) | S |

**Nota de alcance 7.1 (la más grande del documento)** — construir respaldo
real cifrado en reposo contra Mongo/ClickHouse de producción está fuera de
lo razonable para este entorno académico (requiere gestión de claves de
cifrado real, almacenamiento externo, credenciales de un proveedor cloud).
**Propuesta ✂️ (la que tu instrucción ya sugiere como ejemplo)**:
- `POST /sistema/respaldos` dispara un `mongodump`/`clickhouse-client
  --query` real contra los contenedores del **entorno de desarrollo**,
  escribe el archivo a un volumen local (no a un bucket externo), y
  registra metadatos reales (tamaño, duración, hash del archivo) en una
  colección `respaldos` — el respaldo en sí **es real y funciona**, solo
  que corre contra desarrollo, no contra un producción que no existe fuera
  de este entorno.
- "Restaurar" se demuestra como flujo simulado: un botón que valida que el
  archivo de respaldo existe y es íntegro (hash), pero la restauración
  real (`mongorestore`) solo se ofrece explícitamente contra una base de
  desarrollo/aislada (por ejemplo, una base Mongo `urbanflet_restore_test`
  separada, nunca `urbanflet`), nunca un botón de un clic que sobrescriba
  datos reales de la cooperativa.
- Cifrado en reposo: **no se implementa cifrado real** (sería añadir
  gestión de claves fuera de alcance) — se documenta la limitación
  explícitamente en la UI ("cifrado en reposo: no implementado en este
  entorno de desarrollo") en vez de simular un candado que no protege nada.

Pendiente de tu aprobación explícita antes de construir este módulo (tal
como pide tu instrucción para este tipo de recorte).

---

## 4. Resumen de recortes de alcance que requieren tu aprobación

| Módulo | Recorte propuesto | Motivo |
|---|---|---|
| 1.2 | Matriz de permisos estática (diccionario mantenido a mano), no introspección dinámica de FastAPI | Desproporcionado para el alcance académico |
| 8.1 | "Historial de despliegues" = registro manual/por script, no CI/CD real | No existe pipeline de despliegue automatizado en el proyecto |
| 6.2 | Rate limiting configurable solo para los 3 mecanismos ya existentes (login/refresh/RBAC), no un middleware genérico por endpoint | No hay rate-limiter transversal hoy; construir uno es un cambio de arquitectura mayor |
| 4.2 | Rotación de API key vía override en Mongo (real, sin reiniciar) con fallback a env var — no mock | Balance entre "honesto" y "proporcionado"; ver detalle arriba |
| 5.2 | Umbrales evaluados bajo demanda al abrir el panel, no vigilancia continua con alerta push | No hay worker/cron en el stack apto para esto sin infraestructura nueva |
| 7.1 | Respaldo real contra entorno de desarrollo (no producción), restauración solo contra base aislada de prueba, sin cifrado real (documentado como limitación) | Cifrado real + backups contra producción real están fuera de lo razonable para este entorno |

**Todos los demás módulos/tareas (1.1, 1.3, 1.4, 2.1, 2.2, 3.*, 6.1, 6.3,
7.2, 8.2) se consideran 100% construibles end-to-end sin recorte de
alcance**, usando patrones ya probados en el proyecto (WorkPanel, parámetros
versionados, bitácora existente, Redis).

---

## 5. Checklist de cierre por módulo (repetir por cada uno)

- [ ] Backend: endpoints + tests (`pytest`) verdes.
- [ ] Frontend: pantalla(s) con patrón WorkPanel/Dashboard, cableada a los
      endpoints reales.
- [ ] Toda acción administrativa pasa por `write_audit_event` (Módulo 6.1
      la hace visible).
- [ ] Acceso gateado a `admin_sistema` (+ `gerencia` donde la spec lo indica
      explícitamente: 7.2 y 8.2).
- [ ] Verificación en navegador real (nivel de esfuerzo según complejidad,
      §6 de `CLAUDE.md`).
- [ ] `npm run build/lint/test` en `web-interno` + `pytest` backend, verdes.
- [ ] Estado actualizado en este archivo (✅/✂️/🚫 con motivo).

---

## 6. Estado global de las 8 módulos (vista rápida)

| Módulo | Estado |
|---|---|
| 1 — IAM | ✅ cerrado y verificado (ver §7) |
| 2 — Configuración General | ✅ cerrado y verificado (ver §8) |
| 3 — Catálogos | ✅ cerrado y verificado (ver §10) |
| 4 — Integraciones Externas | ✅ cerrado y verificado (ver §15) |
| 5 — Monitoreo | ✅ cerrado y verificado (ver §16) |
| 6 — Auditoría y Seguridad | ✅ cerrado (6.1 §9, 6.2 §13, 6.3 §14) |
| 7 — Respaldos y Continuidad | ✅ cerrado y verificado (ver §18) |
| 8 — Mantenimiento y Gobernanza | ✅ cerrado — 8.1 (ver §11), 8.2 (ver §17) |

*(Actualizar esta tabla y las de detalle arriba conforme se cierre cada
módulo — no dejar como lista que solo vive en el chat, según instrucción.)*

---

## 7. Módulo 1 (IAM) — cerrado y verificado (2026-08-05)

Las 4 tareas (1.1-1.4) se cerraron juntas en una sesión, backend y frontend
sincronizados como exige la Fase 2.

**Backend** — 3 módulos nuevos:
- `backend/src/usuarios/` (router+service+schemas+`permisos_matriz.py`):
  1.1 (CRUD de cuentas, suspender/reactivar/dar-de-baja, accesos), 1.2
  (roles + matriz estática), 1.4 (listar/cerrar sesiones). Todo gateado a
  `admin_sistema` en solitario (`require_roles("admin_sistema")`, sin roles
  combinados — nota de seguridad de la spec).
- `backend/src/seguridad/` (router+service): 1.3, política de auth
  versionada reutilizando `parametros/service.py::_crear_version` (mismo
  patrón que `PARAMETRO_TARIFA`, no un mecanismo paralelo). Fallback a
  `DEFAULTS` (8/5/15/15/sin vencimiento — los valores que ya regían antes de
  este módulo) cuando nunca se publicó una versión.
- `backend/src/core/sessions.py` (nuevo): registro de sesiones activas en
  Redis, `sesion:{jti}` (TTL = vida del access token) + `usuario:{id}:sesiones`
  (set de jtis, poda perezosa de expirados al leer) + `sesion:revocada:{jti}`
  (blocklist puntual). `core/rbac.py::get_current_actor` rechaza un jti
  revocado sin tocar `rbac:suspended:{usuario_id}` (ese sigue siendo "toda
  la cuenta", este es "una sesión puntual").
- **Hallazgo real que simplificó 1.1**: no hizo falta ningún mecanismo nuevo
  para "la suspensión invalida la sesión de inmediato" — `get_current_actor`
  YA releía `usuarios.estado` de Mongo en cada petición (CU-O18 A3,
  precondición ya existente). Poner `estado` en `SUSPENDIDO`/`BAJA` lo
  bloquea en la siguiente petición sola. Verificado real: token vivo antes
  de suspender (200), mismo token después de suspender (401
  `INVALID_TOKEN`), mismo token después de reactivar (200 de nuevo — la
  suspensión es reversible, no revoca el token permanentemente, tal como
  pide la spec "bloqueo temporal, reversible").
- `auth/service.py` extendido: longitud mínima de password y umbral/ventana/
  duración de bloqueo de login ahora se leen de la política vigente en cada
  llamada (antes constantes fijas `_MAX_LOGIN_FAILURES=5`/etc., ahora
  eliminadas). Nuevo `POST /auth/cambiar-password` (requiere password
  actual). `TokenPair` gana `debe_cambiar_password: bool`.
- 2 índices nuevos en `usuarios` (`roles`, `estado`) para la búsqueda de
  `GET /usuarios`.
- Catálogo `AccionAuditoria` ampliado con 8 acciones nuevas (`USUARIO_*`,
  `ROL_MODIFICACION`, `POLITICA_AUTH_CAMBIO`, `SESION_CIERRE_REMOTO`,
  `PASSWORD_CAMBIO`) — sin campo nuevo en `EVENTO_AUDITORIA` (el
  antes/después de Módulo 6.1 ya lo cubren `datos_previos`/`datos_posteriores`,
  que ya existían).

**Frontend** (`apps/web-interno`): grupo de nav "Administración" nuevo con
`Usuarios.tsx` (WorkPanel completo: búsqueda con 3 filtros, crear cuenta con
checkboxes de rol, detalle con roles/sesiones/accesos/suspender/reactivar/
dar-de-baja) y `PoliticasAuth.tsx` (formulario simple). `AuthProvider`
(shared-ui) ganó `debeCambiarPassword`/`cambiarPassword` genéricos — usado
en `web-interno` para un gate obligatorio de cambio de contraseña antes de
poder navegar el resto del portal (pantalla nueva `CambiarPasswordCard` en
`App.tsx`), no wireado en `web-pasajero`/`web-conductor` (no lo necesitan
todavía, pero el campo es genérico si algún día lo necesitan).

**Verificación real en navegador** (no solo tests) — cuenta de demo
`admin_sistema` nueva (`+593900000099` / `AdminSistema123!`, agregar a la
tabla de credenciales de `CLAUDE.md` en el mismo commit):
- Login real, sidebar con "Usuarios"/"Políticas de autenticación".
- Crear cuenta nueva (`jefe_mantenimiento`) vía UI → 201 real, documento
  real en Mongo con `forzar_cambio_password: true`, evento
  `USUARIO_CREACION` real con `actor_id` del admin.
- Login con esa cuenta nueva → `debe_cambiar_password: true` real →
  `CambiarPasswordCard` bloqueó la navegación (no se veía ninguna sección
  detrás) → cambio de contraseña real → flag se limpió en Mongo → login
  siguiente ya sin el gate, cae directo al panel de Mantenimiento (su rol).
- Suspender esa cuenta vía UI (motivo obligatorio, botón deshabilitado
  hasta escribirlo) → confirmado con `curl` que un token ya emitido pasó de
  200 a 401 de inmediato, sin esperar expiración.
- Reactivar → mismo token volvió a dar 200 (reversible, confirmado).
- Cerrar UNA sesión específica entre 5 activas (2 tokens curl distintos
  creados a propósito) → confirmado que el token cerrado quedó en 401 con
  el mensaje exacto `"Sesión cerrada por un administrador"`, mientras el
  otro token (sesión distinta, misma cuenta) siguió respondiendo 200 sin
  tocarse — prueba de que la revocación es por sesión, no por cuenta.
- Publicar una política de auth más estricta (longitud mínima 10) →
  confirmado con `curl` que un registro con contraseña de 7 caracteres
  pasó a rechazarse con `WEAK_PASSWORD` real. Revertido a 8 (valor
  default) para no interferir con el resto del entorno de desarrollo
  compartido — confirmado que un registro de 9 caracteres volvió a
  aceptarse. Los 2 eventos `POLITICA_AUTH_CAMBIO` (endurecer + revertir)
  confirmados en Mongo con `datos_previos`/`datos_posteriores` reales.
- Matriz de permisos (`GET /usuarios/matriz-permisos`) confirmada
  accesible y con el contenido esperado.

**Suite automatizada**: `pytest` backend 197 passed + 8 skipped (subió de
177 — 20 tests nuevos: `tests/usuarios/`, `tests/seguridad/`,
`tests/auth/test_cambiar_password.py`), `ruff check` limpio. Frontend:
`npm run build/lint/test` limpios en `web-interno` (5 tests, 2 nuevos sobre
el patrón WorkPanel de Usuarios) + `shared-ui` lint + build de
`web-pasajero`/`web-conductor` confirmados sin romper por el cambio de
`AuthProvider`.

**Pendiente explícito no resuelto en este módulo** (documentado para no
perderlo): "Consultar la matriz de permisos vigente por rol" (1.2) usa el
diccionario estático ya aprobado (§3, nota de alcance) — si se agrega un
`require_roles(...)` nuevo en cualquier router futuro,
`usuarios/permisos_matriz.py` no se actualiza solo, hay que tocarlo a mano.

---

## 8. Módulo 2 (Configuración General) — cerrado y verificado (2026-08-05)

Las 2 tareas (2.1 parámetros globales, 2.2 feature flags) se cerraron
juntas, backend y frontend sincronizados.

**Backend** — 1 módulo nuevo + 1 helper en `core/`:
- `backend/src/configuracion/` (router+service+schemas): 2.1, parámetro
  `PARAMETRO_SISTEMA` (tipo `"sistema"`) reutilizando
  `parametros/service.py::_crear_version` (mismo patrón que
  `seguridad/service.py` — tercer consumidor de ese helper ahora). Router
  también expone 2.2 (`POST/GET /configuracion/flags`,
  `PATCH /configuracion/flags/{nombre}`), delegando la lógica a
  `core/feature_flags.py`.
- `backend/src/core/feature_flags.py` (nuevo): colección `feature_flags`
  (NO versionada, a diferencia de `parametros` — un flag es un interruptor,
  no una regla de negocio con vigencia histórica). `is_enabled(db, nombre,
  actor_id=, roles=)` es el helper genérico para que un módulo de negocio
  futuro lo consulte — combina gate de rol (si el flag define `roles`, el
  actor debe tener al menos uno) Y gate de porcentaje (hash determinista
  `sha256(f"{nombre}:{actor_id}")` → bucket 0-99 estable, mismo patrón que
  ya usa `analytics/scripts/seed_viajes_nyc.py` para fracciones
  deterministas). Fail-closed: flag inexistente o inactivo → `False`,
  nunca una excepción.
- **Cambio real de comportamiento** en `viajes/service_dispatch.py`: los
  radios de despacho (`RADIOS_M`) y la expiración de oferta
  (`OFERTA_EXPIRA_SEGUNDOS`) dejaron de ser constantes de módulo — ahora se
  leen en caliente vía
  `configuracion.service.obtener_parametro_sistema_vigente()` (mismo caché
  de 30s en memoria que ya usa `parametros/service.py` para tarifa/comisión)
  en las 3 funciones que los usaban (`_intentar_emitir_siguiente`,
  `avanzar_despacho`, `construir_oferta_out`). Fallback a
  `configuracion/service.py::DEFAULTS` (300/600/1000m, 20s — los mismos
  valores que regían fijos antes) si nunca se publicó una versión, así el
  comportamiento no cambia hasta que un `admin_sistema` publique la
  primera.
- Índice nuevo: `feature_flags.nombre` único (además de la validación
  explícita en `crear_flag`, defensa contra condición de carrera).
- 2 acciones nuevas en `AccionAuditoria`: `FLAG_CREACION`,
  `FLAG_MODIFICACION` (el cambio de parámetro de sistema reutiliza
  `PARAMETRO_CAMBIO`, ya existente, con `entidad="parametro_sistema"` para
  distinguirlo de tarifa/comisión en la bitácora).

**Frontend** (`apps/web-interno`): 2 pantallas nuevas en el grupo
"Administración" — `ParametrosGlobales.tsx` (formulario simple, mismo
patrón que `PoliticasAuth.tsx` de Módulo 1) y `FeatureFlags.tsx` (WorkPanel
sin paginación — la lista de flags no pagina en el backend, mismo criterio
ya usado en Flota para tableros que no paginan — con creación y edición
completas: activo/porcentaje/roles).

**Verificación real en navegador** (contra el backend/Mongo/Redis reales
de `docker compose`, misma sesión `admin_sistema` de Módulo 1):
- Publicar radios `[150, 300]` (default es `[300, 600, 1000]`) → confirmado
  con una solicitud de viaje real (pasajero nuevo, conductor sembrado a
  ~890m) que el motor de despacho real devolvió `SIN_CONDUCTOR` —
  con los radios por defecto ese mismo conductor habría calificado
  (ya lo prueba `tests/viajes/test_despacho.py::test_candidato_solo_dentro_de_1000m_amplia_radio`).
  Prueba de que el endpoint no solo guarda el valor, el motor de despacho
  real lo lee. Revertido a `[300, 600, 1000]` después para no dejar el
  entorno compartido en un estado no estándar; datos de prueba (conductor,
  vehículo, pasajero, viaje) borrados al cierre.
- Crear flag real `pago_electronico` (activo, 30%, rol `pasajero`) →
  documento real en Mongo, evento `FLAG_CREACION` real con `actor_id` del
  admin. `is_enabled()` probado con 4 actor_id de ejemplo: rechaza
  `conductor` siempre (gate de rol), acepta `pasajero` solo para el actor
  cuyo hash cae dentro del 30% (comportamiento determinista confirmado, no
  aleatorio por request).
  **Nota**: como ya estaba documentado en el alcance de 2.2, este flag no
  gobierna ninguna función real todavía (pago electrónico sigue en
  backlog) — la demo confirma el mecanismo, no una integración con negocio.
- Desactivar el flag vía UI → `Estado` pasó a INACTIVO en la tabla real,
  evento `FLAG_MODIFICACION` real con `datos_previos`/`datos_posteriores`,
  `is_enabled()` volvió a `False` para el mismo actor que antes calificaba.
- Políticas de auth (Módulo 1.3) confirmado que sigue funcionando sin
  regresión tras agregar Módulo 2 (mismo `_crear_version` compartido).

**Suite automatizada**: `pytest` backend 206 passed + 8 skipped (subió de
197 — 9 tests nuevos: `tests/configuracion/test_parametros_sistema.py`
(incluye un test de integración real contra `viajes/service_dispatch.py`,
no solo el CRUD del parámetro) y `test_feature_flags.py`), `ruff check`
limpio. Frontend: `npm run build/lint/test` limpios en `web-interno` (6
tests, 1 nuevo sobre el patrón WorkPanel de Funcionalidades).

**Alcance de 2.2 tal como fue aprobado** (PLAN_ADMIN_SISTEMA.md §3, nota de
2.2): mecanismo genérico completo, sin cablear a ninguna función de
negocio real — confirmado que se respetó ese límite, no se tocó
`captacion`/`recaudacion`/etc. para consumir `is_enabled()`.

---

## 9. Módulo 6.1 (Auditoría de cambios administrativos) — cerrado y verificado (2026-08-05)

Construido fuera de orden numérico respecto a los 8 módulos (6 va después
de 3/4/5 en la enumeración de la spec) pero en el orden de construcción ya
aprobado por el usuario (§1 de este plan), que puso 6.1 justo después de
Módulo 2 a propósito — "los primeros módulos que generan eventos que
necesita mostrar".

**Backend** — sin módulo nuevo, dos extensiones puntuales al ya existente
`auditoria/`:
- `GET /auditoria/eventos` amplía el parámetro `accion` de un solo valor a
  una lista (`?accion=A&accion=B...`, resuelto a `{"$in": [...]}}` en Mongo
  cuando hay más de uno) — necesario porque "solo las acciones
  administrativas" son ~12 valores distintos de `AccionAuditoria`, no uno.
  Retrocompatible: un solo `accion=X` sigue funcionando igual que antes
  (confirmado, los 3 tests preexistentes de `test_auditoria.py` no se
  tocaron y siguen pasando).
- `EventoAuditoriaOut` (schema de respuesta) ahora expone
  `datos_previos`/`datos_posteriores` — ya existían en `EVENTO_AUDITORIA`
  desde el día 1 (CU-O17), simplemente ningún endpoint de lectura los había
  expuesto todavía porque ningún consumidor los necesitaba. Es lo que pide
  la spec como "comparación antes/después" — no hizo falta el campo
  `detalle` genérico que una versión anterior de este plan anticipaba (nota
  ya corregida).
- `core/audit.py::ACCIONES_ADMINISTRATIVAS`: catálogo mantenido a mano
  (mismo criterio que `usuarios/permisos_matriz.py`) con las 12 acciones
  administrativas de Módulos 1 y 2. Su espejo en frontend
  (`AuditoriaAdmin.tsx`) debe actualizarse a mano en el mismo cambio si un
  módulo futuro (3/4/8) agrega una acción nueva — documentado en ambos
  archivos con comentarios cruzados.
- **Hallazgo real corregido de paso**: `configuracion/service.py` (Módulo
  2.1) reutilizaba `AccionAuditoria.PARAMETRO_CAMBIO` (la misma acción que
  tarifa/comisión) para el cambio de parámetro de sistema — eso habría
  mezclado cambios de radio de despacho con cambios de tarifa en el filtro
  administrativo, sin forma limpia de separarlos (misma acción, distinta
  `entidad`, y el filtro de acción no soporta combinarse con entidad en un
  único `$in` legible). Se creó `PARAMETRO_SISTEMA_CAMBIO`, una acción
  propia, y se corrigió `configuracion/service.py` para usarla. Los 2
  eventos ya escritos en la sesión anterior bajo `PARAMETRO_CAMBIO`
  quedaron con el nombre viejo (verificado explícitamente que NO aparecen
  en el filtro administrativo — es el comportamiento correcto, no un dato
  perdido: nunca fueron accesibles como "administrativos" hasta esta
  sesión, y un evento de bitácora nunca se reescribe con normalidad, es
  insert-only).

**Frontend** (`apps/web-interno`): `AuditoriaAdmin.tsx`, nueva pantalla en
"Administración" (no es un dashboard táctico con patrón Z/F — es una tabla
simple con filtros, como el resto de pantallas de Administración). Filtro
de acción preseleccionado a "todas las administrativas" (envía las 12 como
`accion=` repetido) con opción de acotar a una sola. Columna "Cambio" con
un botón "Ver antes/después" que abre un `DetailPanel` con dos bloques
`<pre>` (antes/después) en JSON legible — sin diff visual campo por campo
(fuera de alcance para esta pasada, el JSON crudo ya es suficiente para
"comparación antes/después" tal como lo pide la spec).

**Verificación real en navegador** (misma sesión `admin_sistema`, contra
el backend/Mongo reales): la bitácora real acumulada de las verificaciones
de Módulos 1 y 2 apareció completa y correctamente filtrada — 10 eventos
administrativos reales (USUARIO_CREACION, USUARIO_SUSPENSION,
USUARIO_REACTIVACION, SESION_CIERRE_REMOTO ×2, POLITICA_AUTH_CAMBIO ×2,
FLAG_CREACION, FLAG_MODIFICACION, PASSWORD_CAMBIO) sin mezclar ningún
evento operativo. Publiqué un cambio nuevo de parámetro de sistema durante
esta verificación específicamente para confirmar que
`PARAMETRO_SISTEMA_CAMBIO` aparece correctamente (subió a 11) y que los 2
eventos viejos bajo `PARAMETRO_CAMBIO` (de antes de la corrección) siguen
excluidos, tal como se esperaba. Abrí "Ver antes/después" sobre ese evento
nuevo y confirmé que el JSON mostrado coincide exactamente con lo que se
publicó. Probé el filtro de una sola acción (`SESION_CIERRE_REMOTO`) y
confirmó exactamente 2 eventos, no 10.

**Suite automatizada**: `pytest` backend 208 passed + 8 skipped (subió de
206 — 2 tests nuevos en `tests/auditoria/test_auditoria.py`: filtro
multi-acción y exposición de antes/después), `ruff check` limpio.
Frontend: `npm run build/lint/test` limpios en `web-interno` (7 tests, 1
nuevo).

---

## 10. Módulo 3 (Catálogos y Parámetros de Negocio) — cerrado y verificado (2026-08-05)

Las 3 tareas (3.1 zonas, 3.2 tipos de documento, 3.3 motivos) se cerraron
juntas, backend y frontend sincronizados.

**Backend**:
- **3.1 (zonas)** — extendido `parametros/router.py`/`service.py`
  (existente, creado antes de admin_sistema) en vez de duplicar un segundo
  CRUD de zonas en otro módulo: `PATCH`/`DELETE /parametros/zonas/{id}`
  nuevos. Nueva dependencia `_puede_gestionar_zonas` (`admin_plataforma`,
  `gerencia`, `admin_sistema`), **separada** de `_puede_escribir_parametros`
  (solo `admin_plataforma`/`gerencia`) que sigue gateando tarifa/comisión —
  admin_sistema gana acceso al catálogo de zonas sin ganar acceso a reglas
  de dinero. `crear_zona` (que nunca auditaba nada) ahora también escribe
  `CATALOGO_CREACION`. `DELETE` bloquea con `ZONA_EN_USO` (409) si algún
  viaje referencia la zona por `zona_origen_id`/`zona_destino_id`.
  **Hallazgo real de la investigación previa a construir esto**: esos dos
  campos existen en `viajes/schemas.py` pero **nunca se resuelven** (siempre
  `None`, ver comentario explícito en `viajes/service.py`) — el guard es
  código real y correcto, pero hoy nunca bloquea nada en la práctica hasta
  que esa resolución se implemente. No se fabricó un guard falso solo para
  "aparentar" seguridad.
- **3.2/3.3 (tipos de documento, motivos)** — módulo nuevo
  `backend/src/catalogos/` (router+service+schemas), dos colecciones nuevas
  (`tipos_documento`, `motivos_cancelacion`), exclusivo `admin_sistema` (sin
  precedente que reusar, a diferencia de zonas). **Sin `DELETE`** — solo
  `activo` (toggle), decisión documentada en el docstring de
  `catalogos/service.py`: ambos catálogos alimentan campos hoy de texto
  libre sin FK (`documentos.tipo`, `viajes.motivo_cancelacion` — confirmado
  con una investigación de código antes de construir, cero Literal/enum en
  ningún lado), así que no hay forma confiable de saber si un nombre sigue
  "en uso" tras un rename; desactivar es la única operación segura y
  reversible. Este CRUD gestiona la taxonomía de referencia, no migra los
  datos ya existentes a claves foráneas (confirmado que se respetó ese
  límite, no se tocó ningún schema de `captacion`/`viajes`).
- 3 acciones de auditoría nuevas, genéricas para los 3 catálogos:
  `CATALOGO_CREACION`/`CATALOGO_EDICION`/`CATALOGO_ELIMINACION`
  (`entidad` distingue cuál catálogo cambió) — sumadas a
  `ACCIONES_ADMINISTRATIVAS` (Módulo 6.1) y a su espejo en
  `AuditoriaAdmin.tsx`.
- 2 índices nuevos: `tipos_documento.nombre` y `motivos_cancelacion.nombre`
  (`unique=True`).

**Frontend** (`apps/web-interno`): `Catalogos.tsx`, una sola pantalla con 3
pestañas (Zonas / Tipos de documento / Motivos) en vez de 3 pantallas
separadas — coincide con como la spec agrupa "Catálogos y tablas maestras"
como una sola responsabilidad (3.1). Cada pestaña sigue el patrón WorkPanel
(ActionBar + DataTable + DetailPanel), sin paginación (listas chicas). El
campo `geometria` de zona no se expone en el formulario (queda `{}` fijo al
crear/editar) — el formato de `geometria` nunca quedó especificado en el
diseño original (ver comentario ya existente en `viajes/service.py`),
exponer un editor JSON crudo para un formato indefinido habría sido
confuso sin aportar nada real.

**Verificación real en navegador** (misma sesión `admin_sistema`, contra
el backend/Mongo reales): creé una zona real ("Zona Centro QA") → 201 real,
evento `CATALOGO_CREACION` real con el actor correcto → la edité (rename)
→ tabla actualizada con el nuevo nombre, evento `CATALOGO_EDICION` con
antes/después reales → la eliminé → 204 real, confirmado con consulta
directa a Mongo que el documento ya no existe, evento
`CATALOGO_ELIMINACION` real. Sección Motivos: creé un motivo real
("Conductor no localizado", categoría `incidencia`) → apareció en la
tabla con la categoría correcta → lo desactivé (toggle `activo`) → badge
cambió a INACTIVO en tiempo real, confirmando que el soft-delete funciona
end-to-end. Datos de verificación (zona y motivo de prueba) borrados al
cierre para no dejar artefactos de QA en el catálogo real.

**Suite automatizada**: `pytest` backend 218 passed + 8 skipped (subió de
208 — 10 tests nuevos: `tests/parametros/test_zonas.py` (4) y
`tests/catalogos/test_catalogos.py` (6)), `ruff check` limpio. Frontend:
`npm run build/lint/test` limpios en `web-interno` (8 tests, 1 nuevo).

---

## 11. Módulo 8.1 (Versión/Despliegue) — cerrado y verificado (2026-08-05/06)

**Backend**: módulo nuevo `backend/src/sistema/` (router+service+schemas).
`GET /sistema/version` lee `Settings.app_version` (nuevo campo, sync manual
con `backend/pyproject.toml::version`) + `VERSIONES_FRONTEND` (constantes
en `sistema/service.py`, sync manual con el `version` de cada
`apps/<app>/package.json`) — sin introspección automática, documentado
explícitamente como tal (el backend no tiene acceso al filesystem de los
frontends en producción). `GET`/`POST /sistema/despliegues` — colección
nueva `registro_versiones`, **alcance recortado tal como fue aprobado**:
registro manual, no hay CI/CD real en el proyecto para poblarlo solo.
Acción de auditoría nueva `DESPLIEGUE_REGISTRO`, sumada a
`ACCIONES_ADMINISTRATIVAS` (Módulo 6.1).

**Hallazgo real corregido de paso (no específico de 8.1)**: al construir
esto se detectó que el mirror de `ACCIONES_ADMINISTRATIVAS` en
`AuditoriaAdmin.tsx` (frontend) **nunca se había actualizado con las 3
acciones de catálogo** (`CATALOGO_CREACION`/`EDICION`/`ELIMINACION`) que
Módulo 3 agregó — el propio comentario del archivo advertía sobre este
riesgo exacto ("si se agrega una acción nueva... hay que sumarla acá
también") y aun así se pasó por alto en esa sesión. Corregido junto con
`DESPLIEGUE_REGISTRO`: los 3 eventos reales de catálogo (creación/edición/
eliminación de la zona de prueba de §10) que existían en Mongo pero nunca
habían aparecido en el dashboard de Auditoría ahora se ven correctamente
(confirmado en navegador: pasó de 14 a 17 eventos administrativos visibles
sin haber escrito ningún evento nuevo en el proceso, solo corrigiendo el
filtro). Sirve de recordatorio para las próximas sesiones que agreguen
Módulos 4/5/6.2/6.3/7/8.2: actualizar ese mirror es fácil de olvidar
precisamente porque no rompe ningún test si se omite (los eventos se
siguen escribiendo bien, solo quedan invisibles en el filtro).

**Frontend** (`apps/web-interno`): `VersionSistema.tsx` — tarjeta con las 4
versiones (backend + 3 frontends), formulario para registrar un despliegue
nuevo, y tabla de historial. Nota explícita en la UI de que el registro es
manual, no automatizado.

**Verificación real en navegador** (misma sesión `admin_sistema`, contra
backend/Mongo reales de `docker compose` — Docker Desktop se había
detenido entre sesiones, se relanzó y se esperó a que los healthchecks
quedaran listos antes de continuar): las 4 versiones reales (`0.1.0` los 4
componentes) cargaron correctas: registré un despliegue real
(`componente="todos"`, `version="0.1.0"`, notas describiendo el cierre de
este mismo módulo) → apareció en la tabla de historial real, evento
`DESPLIEGUE_REGISTRO` confirmado en Mongo con el actor correcto. Confirmé
además, como efecto colateral de esta verificación, que el dashboard de
Auditoría (Módulo 6.1) ahora muestra el evento nuevo junto con los 3
eventos de catálogo que habían quedado invisibles por el hallazgo de
arriba.

**Suite automatizada**: `pytest` backend 221 passed + 8 skipped (subió de
218 — 3 tests nuevos en `tests/sistema/test_version.py`), `ruff check`
limpio. Frontend: `npm run build/lint/test` limpios en `web-interno` (9
tests, 1 nuevo).

---

## 12. Corrección estructural — `ACCIONES_ADMINISTRATIVAS` dejó de ser un mirror manual (2026-08-06)

A pedido explícito del usuario, tras el hallazgo real de §11 (el mirror de
`AuditoriaAdmin.tsx` se desincronizó con el backend sin que ningún test lo
detectara). Se evaluaron las 2 alternativas que el usuario planteó
(endpoint que expone la lista real, o un test de sincronización) y se
eligió la primera — elimina la causa raíz en vez de solo detectarla.

- **Backend**: `GET /auditoria/acciones-administrativas` (nuevo, mismo
  gate `_puede_leer_bitacora`) devuelve
  `sorted(a.value for a in core.audit.ACCIONES_ADMINISTRATIVAS)` — cero
  lógica nueva, solo expone el catálogo que ya era la fuente de verdad.
- **Frontend**: `AuditoriaAdmin.tsx` ya no declara ningún array
  hardcodeado — lo pide a este endpoint al montar y lo usa tanto para el
  `<select>` de filtro como para el `accion=` repetido que arma la query
  por defecto ("todas las administrativas"). Ya no existe ningún archivo
  en `apps/web-interno` que necesite tocarse cuando el backend agregue una
  acción administrativa nueva.
- Test backend nuevo (`tests/auditoria/test_auditoria.py::
  test_acciones_administrativas_expone_el_catalogo_real`) que compara el
  endpoint contra `ACCIONES_ADMINISTRATIVAS` directamente — por
  construcción no puede desincronizarse, no hace falta un test de "no se
  desincronizaron" aparte.
- Verificado en navegador real: el `<select>` de "Acción" en
  `/Administración/Auditoría` ahora muestra las 16 acciones reales
  (incluidas las de Módulos 3 y 8.1, que antes de este fix habían quedado
  invisibles) en orden alfabético, tal como las devuelve el endpoint.
- `pytest` backend 222 passed + 8 skipped (subió de 221), `ruff check`
  limpio. Frontend: `npm run build/lint/test` limpios en `web-interno` (9
  tests, sin tests nuevos -- el existente de Módulo 6.1 se actualizó para
  mockear el endpoint nuevo).

---

## 13. Módulo 6.2 (Políticas de seguridad) — cerrado y verificado (2026-08-06)

**Backend**: extendido `seguridad/` (no un módulo nuevo -- ya existía desde
Módulo 1.3, mismo dominio conceptual): `POLITICA_SEGURIDAD` (tipo
`"seguridad"`, mismo patrón `_crear_version`) con 7 campos, 3 mecanismos
reales que dejaron de ser constantes fijas:
- `core/security.py::create_token` acepta `access_ttl_minutos`/
  `refresh_ttl_dias` opcionales (fallback a `Settings` si no se pasan —
  compatibilidad hacia atrás con cualquier llamador que no toque política).
- `auth/service.py::_emitir_tokens` ahora requiere `db` (cambio de firma,
  los 2 call sites -- login y refresh -- ya tenían `db` en scope) para leer
  la política vigente antes de emitir cada par de tokens.
  `_registrar_fallo_refresh` deja de usar `_MAX_REFRESH_FAILURES`/
  `_REFRESH_FAILURE_WINDOW_SECONDS` fijos, recibe la política ya resuelta.
- `core/rbac.py::_register_denial_and_maybe_suspend` deja de usar
  `_DENIAL_THRESHOLD`/`_DENIAL_WINDOW_SECONDS`/`_SUSPENSION_SECONDS`
  fijos — import perezoso de `seguridad.service` (no a nivel de módulo,
  para no acoplar el archivo más foundational del proyecto a un dominio de
  negocio a nivel de import).
- **Hallazgo real corregido de paso**: el TTL con el que `core/sessions.py`
  registraba una sesión en Redis (Módulo 1.4) seguía leyendo
  `Settings.jwt_access_token_expire_minutes` fijo — si se publicaba una
  política con un TTL distinto, el registro de "sesiones activas" habría
  quedado desincronizado del TTL real del token (una sesión reportada como
  viva más tiempo del que su JWT realmente dura, o viceversa).
  `registrar_sesion`/`revocar_sesion` ahora reciben `db` y leen la política
  vigente para ambos TTL (registro y blocklist de revocación).
- Acción de auditoría nueva `POLITICA_SEGURIDAD_CAMBIO`, sumada
  automáticamente al filtro de Auditoría (Módulo 6.1) gracias al fix de
  §12 -- **no hizo falta tocar ningún archivo de frontend** para que
  apareciera, confirmado en la verificación de abajo.

**Alcance tal como fue aprobado originalmente** (PLAN_ADMIN_SISTEMA.md §3,
nota de 6.2): sin rate-limiter genérico por endpoint — solo los 3
mecanismos puntuales que ya existían (login ya cubierto por Módulo 1.3,
refresh y denegaciones RBAC cubiertos aquí).

**Frontend**: `PoliticasSeguridad.tsx` — formulario con 3 secciones (TTL de
tokens, bloqueo de refresh, suspensión RBAC), mismo patrón que
`PoliticasAuth.tsx`.

**Verificación real en navegador** (misma sesión `admin_sistema`, contra
backend/Mongo/Redis reales): publiqué `access_token_minutos=7` → confirmé
con un login real y decodificación del JWT (`exp - iat`) que el token
emitido duró exactamente 420 segundos, no los 900 (15 min) por defecto —
prueba de que el TTL real del token, no solo el valor guardado, cambió.
Revertido a 15 para no dejar el entorno de desarrollo compartido con
sesiones cortas. Confirmé el evento `POLITICA_SEGURIDAD_CAMBIO` real con
antes/después en Mongo, y que apareció automáticamente en el dashboard de
Auditoría sin ningún cambio de frontend (19 eventos, subiendo de 17).

**Suite automatizada**: `pytest` backend 227 passed + 8 skipped (subió de
222 — 5 tests nuevos en `tests/seguridad/test_politica_seguridad.py`,
incluido uno que reutiliza el mismo escenario real de
`tests/core/test_rbac.py::test_cinco_denegaciones_suspenden_la_sesion`
pero con un umbral publicado distinto), `ruff check` limpio. Frontend:
`npm run build/lint/test` limpios en `web-interno` (10 tests, 1 nuevo).

---

## 14. Módulo 6.3 (Alertas y notificaciones del sistema) — cerrado y verificado (2026-08-06)

**Investigación previa a construir** (spec asume que las 3 alertas "ya
generan" notificación; se verificó contra código real antes de asumirlo):
- `denegaciones_rbac` (5 denegaciones, CU-O18 A4): sí estaba realmente
  conectada — `core/rbac.py::_alertar_supervisores_cumplimiento` notificaba
  a `supervisor_cumplimiento`, hardcodeado.
- `gps_spoofing`: **solo auditaba, nunca notificaba a nadie** —
  `flota/service.py::reportar_posicion` escribía `POSIBLE_GPS_SPOOFING` en
  la bitácora pero no llamaba a ningún dispatcher. La spec la lista como
  una alerta que "el sistema ya genera" — no era cierto hasta esta sesión.
- `pipeline_fallido`: **enteramente del lado de Airflow**
  (`analytics/plugins/medallion.py::registrar_alerta_falla`, escribe en
  ClickHouse + log) — no existe ningún webhook Airflow→backend, así que no
  hay ningún punto de enganche real en `backend/src` para esta alerta.
- `responsable_plataforma` (el segundo destinatario que la spec da por
  hardcodeado): grep completo de `backend/src` confirmó que **no está
  conectado a ninguna alerta real** — solo aparece en gates de acceso de
  lectura (`/plataforma/*`), nunca en un envío de notificación.

**Backend**: extendido `notificaciones/` (no un módulo nuevo) con
`configuracion_alertas` (`{_id: tipo_alerta, canal, destinatarios_adicionales,
activo, actualizado_en}`) y `disparar_alerta(db, dispatcher, tipo_alerta,
motivo)` — punto único de disparo que reemplaza el envío hardcodeado que
antes vivía disperso:
- `core/rbac.py::_alertar_supervisores_cumplimiento` ahora delega a
  `disparar_alerta` (import lazy, mismo criterio que `seguridad.service` en
  Módulo 6.2).
- `flota/service.py::reportar_posicion` gana un parámetro `dispatcher`
  (threaded desde `flota/router.py`, que ahora inyecta `Request`) y
  **dispara una notificación real** para `gps_spoofing` — cambio de
  comportamiento genuino, no solo una config nueva sin efecto.
- `pipeline_fallido` queda **configurable pero sin disparo real** — se
  documenta explícitamente en el código y en la UI, no se simula un
  webhook que no existe.
- `canal` limitado a `Literal["web_push"]` en el schema (no
  `"correo"`/`"ambos"` como sugiere la spec) — investigación confirmó que
  **no existe envío de correo en todo el codebase**, Web Push (+ WS en
  vivo) es el único canal real. Aceptar "correo" como opción seleccionable
  habría sido un control que promete algo que nunca ocurre.
- Acción de auditoría nueva `ALERTA_CONFIG_CAMBIO` — cumple la nota de
  seguridad de la spec ("ninguna alerta... sin dejar rastro en la
  auditoría") vía el mismo mecanismo `datos_previos`/`datos_posteriores`
  ya usado en todo el proyecto.

**Frontend** (`apps/web-interno`): `ConfiguracionAlertas.tsx` — tabla de 3
alertas con rol destinatario por defecto (de solo lectura, es el que ya
regía en código) + destinatarios adicionales + activo/inactivo editables.
Nota explícita en la UI para `pipeline_fallido` sobre la ausencia de
disparo real.

**Verificación real en navegador** (misma sesión `admin_sistema`, contra
backend/Mongo/Redis reales): las 3 alertas cargaron con sus roles por
defecto reales. Agregué un destinatario adicional real a `gps_spoofing` →
confirmado en la tabla y con el evento `ALERTA_CONFIG_CAMBIO` real en
Mongo (antes/después). Confirmado que apareció automáticamente en el
dashboard de Auditoría (20 eventos, subiendo de 19) sin tocar ningún
archivo de frontend — tercera confirmación consecutiva de que la
corrección estructural de §12 sigue funcionando. Destinatario de prueba
retirado al cierre.

**Suite automatizada**: `pytest` backend 233 passed + 8 skipped (subió de
227 — 6 tests nuevos en `tests/notificaciones/test_alertas_config.py`,
incluido uno que ejercita el flujo real completo:
`POST /flota/posiciones` con salto imposible → `disparar_alerta` real →
un dispatcher falso capturando la notificación, sin mockear nada de la
lógica de negocio), `ruff check` limpio. Frontend: `npm run build/lint/test`
limpios en `web-interno` (11 tests, 1 nuevo).

---

## 15. Módulo 4 (Integraciones Externas) — cerrado y verificado (2026-08-06)

**Investigación previa a construir** (verificación pedida explícitamente
antes de escribir el middleware de validación, ver §0 y la instrucción del
usuario): confirmado que `GET /ext/v1/...` que la spec da por existente
**no existe en el código** — solo aparece como diseño en
`arquitectura_software.md`. `rpt_uso_integraciones` (dashboard táctico de
Auditoría, punto 6.2) se alimenta de `fact_integracion_api`, que el propio
DAG documenta como "aproximado desde bitácora", no de tráfico real contra
un endpoint que nunca se implementó. Alcance confirmado con el usuario:
CRUD real y completo de credenciales (hash irreversible, revocar con
efecto inmediato), **sin** el middleware de validación contra el endpoint
inexistente — `usos_registrados` queda en 0 con ese motivo explícito,
mismo criterio ya aplicado a "% error API" en el dashboard de Auditoría
(§9).

**Backend** (`backend/src/integraciones/`, módulo nuevo):
- **4.1 (credenciales)**: `crear_credencial`/`listar_credenciales`/
  `revocar_credencial`. El secreto se genera con `secrets.token_urlsafe(32)`,
  se devuelve en texto plano **solo en la respuesta de creación** (nunca
  más) y se persiste como `hash_secreto` vía `hash_password` (bcrypt, mismo
  mecanismo que las contraseñas de usuario) — irreversible, igual que pidió
  la spec. Revocar es idempotente-protegido (`CredencialYaRevocadaError`,
  409 en el segundo intento) y tiene efecto inmediato (`revocada: true` +
  `vigente_hasta`). Dos acciones de auditoría nuevas:
  `INTEGRACION_CREDENCIAL_CREACION`/`INTEGRACION_CREDENCIAL_REVOCACION`,
  con `datos_previos`/`datos_posteriores` reales en la revocación.
- **4.2 (servicios externos)**: Google Maps es el único servicio externo
  real que el sistema ya integra
  (`core/config.py::Settings.google_maps_api_key`, usado en
  `viajes/service.py::estimar_ruta`). SMS y S3 aparecen en la spec como
  servicios "que la arquitectura ya define" pero **no hay integración real
  con ninguno de los dos** (SMS/OTP es backlog consciente desde que el
  login migró a usuario+contraseña, ver CLAUDE.md §4; S3 nunca se
  conectó) — se muestran siempre como `"no_configurado"`, nunca simulados
  como activos. La rotación de la key de Google Maps es real: escribe en
  `servicios_externos_config` (Mongo), que
  `viajes/service.py::estimar_ruta` (vía
  `integraciones/service.py::obtener_google_maps_api_key`) consulta en
  cada llamada **antes** que la variable de entorno — efecto inmediato sin
  reiniciar el backend, no un mock. Acción de auditoría nueva:
  `INTEGRACION_SERVICIO_ROTACION`, con la key enmascarada (`••••` + últimos
  4 caracteres) antes/después — nunca el valor real en la bitácora.
- Cambio de firma en `viajes/service.py::estimar_ruta` (gana `db` como
  primer parámetro) y en `viajes/router_trips.py::obtener_estimacion_ruta`
  (inyecta `db`) para poder consultar el override de Mongo — 3 tests
  preexistentes en `tests/viajes/test_solicitar_viaje.py` que mockeaban
  `viajes_service.get_settings` se actualizaron para mockear
  `integraciones_service.get_settings` (el punto real donde ahora se
  resuelve el fallback a `Settings`).
- Gate: `require_roles("admin_sistema")` exclusivo en los 5 endpoints,
  igual que el resto del módulo — sin OR-gate con `admin_plataforma` ni
  ningún otro rol.

**Frontend** (`apps/web-interno/src/sections/Integraciones.tsx`, 2
pestañas, patrón WorkPanel + `DetailPanel`):
- **Credenciales**: tabla (nombre/alcance/usos/estado) + `Nuevo` abre un
  `DetailPanel` en modo "nuevo" que, tras crear, deja de mostrar el
  formulario y muestra el secreto en un `TextField` de solo lectura con una
  advertencia explícita de que es la única vez que se muestra — sin botón
  "Aceptar" en ese estado (solo "Salir"), para que no se pueda perder el
  secreto por un doble-submit accidental. El detalle de una credencial
  existente es de solo lectura (modo "consulta") con "Revocar" como acción
  extra, oculto si ya está revocada. "Eliminar" deshabilitado con nota
  ("se revoca, no se elimina") — mismo patrón que catálogos del Módulo 3.
- **Servicios externos**: tabla de los 3 servicios con estado/key
  enmascarada; "Rotar key" (solo visible para `google_maps`) abre un
  `DetailPanel` en modo "edición" con un único campo de texto para la key
  nueva. Nota explícita bajo la tabla sobre SMS/S3 sin integración real.
  "Nuevo"/"Eliminar" deshabilitados con nota (los 3 servicios son fijos).

**Verificación real en navegador** (sesión `admin_sistema`, contra
backend/Mongo reales, backend reiniciado tras el cambio de código):
- Credencial real creada ("Municipio de Quevedo — verificación real") →
  secreto de 44 caracteres mostrado una sola vez, confirmado en Mongo que
  `hash_secreto` (bcrypt) es distinto del secreto real y que el evento
  `INTEGRACION_CREDENCIAL_CREACION` quedó con `datos_posteriores` reales.
  Revocada desde el detalle → fila pasó a "REVOCADA" de inmediato, evento
  `INTEGRACION_CREDENCIAL_REVOCACION` con `datos_previos={revocada:false}`/
  `datos_posteriores={revocada:true}` reales en Mongo.
- Servicios externos: Google Maps ya aparecía `ACTIVO` con la key real del
  `.env` enmascarada (`••••8qDM`) — confirma que el fallback a `Settings`
  funciona cuando no hay override en Mongo. Rotado a una key de prueba
  (`AIzaClaveDePruebaVerificacion123`) → tabla actualizada a `••••n123` de
  inmediato, evento `INTEGRACION_SERVICIO_ROTACION` real en Mongo
  (`datos_previos`/`datos_posteriores` enmascarados). **Prueba directa del
  "sin reiniciar backend"**: se llamó `GET /viajes/estimacion-ruta` real
  (login real como `admin_sistema`, sin tocar el backend) y el log del
  contenedor confirmó la petición saliente real a
  `maps.googleapis.com/.../directions/json?...&key=AIzaClaveDePruebaVerificacion123`
  — la key rotada por la UI, no la del `.env`. Google rechazó la key de
  prueba (inválida) y el código cayó correctamente a línea recta
  (`origen_directions: false`), comportamiento esperado, no un error.
  Key real restaurada al cierre (`AIzaSyCq...8qDM`, confirmada en la tabla
  de vuelta a `••••8qDM`) para no dejar rota la integración real de
  Directions para el resto del sistema.
- Credencial de prueba y sus 2 eventos de auditoría de creación/revocación
  borrados al cierre (mismo criterio de limpieza que el resto del
  proyecto, ver CLAUDE.md §8.2) — los 2 eventos `INTEGRACION_SERVICIO_
  ROTACION` (rotar a prueba, restaurar la real) se dejaron en la bitácora:
  son registros legítimos de una acción administrativa real (rotar la key
  configurada), no datos de negocio de prueba.

**Suite automatizada**: `pytest` backend 239 passed + 8 skipped (subió de
233 — 6 tests nuevos en `tests/integraciones/test_credenciales.py`: gate de
rol, creación con secreto expuesto una sola vez, revocación
idempotente-protegida con 409 en el segundo intento, 404 sobre credencial
inexistente, listado de servicios externos con Google Maps
`no_configurado` sin key de entorno, y rotación con verificación de que
`obtener_google_maps_api_key` refleja el valor real de inmediato — no solo
que la respuesta HTTP lo diga). `ruff check` limpio. Frontend: `npm run
build/lint/test` limpios en `web-interno` (13 tests, 2 nuevos).

---

## 16. Módulo 5 (Monitoreo y Observabilidad) — cerrado y verificado (2026-08-06)

**Alcance confirmado por el usuario antes de construir** (re-aprobado
explícitamente al retomar este módulo): "evaluación de umbrales bajo
demanda, no vigilancia continua" — sin motor de alertas en tiempo real
(no hay worker/cron apto en este stack sin agregar infraestructura nueva
tipo Celery beat). Los umbrales se persisten y el panel de estado los usa
para **colorear** cada tarjeta cuando un humano lo abre o presiona
"Actualizar", nunca como alerta push automática. Ver nota de alcance 5.2
original en §3.

**Backend** (extiende `sistema/` en vez de crear un módulo nuevo, mismo
prefijo `/sistema` y gate `admin_sistema` ya usado por Módulo 8.1):
- `GET /sistema/salud` — ping real y concurrente (`asyncio.gather`) a los
  5 componentes que pide la spec (backend, Mongo, Redis, ClickHouse,
  Airflow), con latencia medida real (`time.monotonic`), nunca simulada:
  `db.command("ping")` (Mongo), `redis.ping()`, `SELECT 1` vía
  `clickhouse_connect` (corrido en `asyncio.to_thread` porque el cliente es
  síncrono), `GET {airflow_url}/health` vía httpx. "Backend" se reporta
  como comprobación trivial (el proceso que atiende la petición ya está
  vivo por definición) — no se simula un ping a sí mismo sin sentido.
  Cualquier excepción real (timeout, conexión rechazada) se degrada a
  `disponible=False`/`latencia_ms=None` **sin propagar el texto crudo de
  la excepción** — cumple la nota de seguridad de la spec ("no exponer
  IPs, versiones exactas de software" a través de este panel).
- `GET`/`PUT /sistema/umbrales-monitoreo[/{componente}]` — colección
  `umbrales_monitoreo` con defaults razonables por componente (ej. Mongo
  200ms advertencia / 1000ms crítico), editable con auditoría real
  (`MONITOREO_UMBRAL_CAMBIO`, antes/después). `GET /sistema/salud` calcula
  `estado` (`bien`/`advertencia`/`critico`) combinando disponibilidad +
  latencia contra estos umbrales en el momento de la consulta.
- Nueva variable de configuración `Settings.airflow_url` (hostname interno
  `airflow-webserver:8080` de la red de docker-compose, no accesible desde
  fuera del stack).

**Frontend** (`apps/web-interno/src/sections/Monitoreo.tsx`): `KpiRow` de
5 `KpiCard` (uno por componente, reutilizando la jerarquía tipográfica y
los tonos de estado ya validados en el rediseño de dashboards tácticos,
§5.1) + botón "Actualizar" manual (la única forma de refrescar — no hay
polling automático, consistente con "bajo demanda") + tabla de umbrales
editable (patrón WorkPanel, sin Nuevo/Eliminar — los 5 componentes son
fijos) con una columna de estado actual por fila.

**Verificación real en navegador** (sesión `admin_sistema`, backend
reiniciado tras el cambio de código; Airflow requirió el
`--force-recreate` documentado en CLAUDE.md §3 por un PID de webserver
stale tras el restart previo del backend): los 5 componentes cargaron con
latencias reales y distintas entre sí (Backend 0ms, Mongo ~5.6ms, Redis
~5.7ms, ClickHouse ~14.5ms, Airflow ~39.8ms la primera vez, luego más
rápido con la conexión ya caliente) — nunca 0ms/idéntico entre todos, lo
que hubiera sido señal de datos simulados. Bajé el umbral de Mongo a
1ms/3ms advertencia/crítico → la fila pasó a "CRITICO" y, confirmado con
`getComputedStyle`, el valor de la tarjeta KPI de Mongo pasó a
`rgb(208, 59, 59)` (rojo de `--status-critical`) mientras las otras 4
siguieron en `rgb(12, 163, 12)` (verde de `--status-good`) — prueba
directa de que el color reacciona al umbral real, no a un estado fijo.
Evento `MONITOREO_UMBRAL_CAMBIO` confirmado en Mongo con
`datos_previos`/`datos_posteriores` reales. Gate de rol confirmado con
llamadas reales: `admin_sistema` → 200, `gerencia` → 403 (`GET
/sistema/salud`). Umbral de Mongo restaurado a sus valores por defecto
(200ms/1000ms) al cierre.

**Suite automatizada**: `pytest` backend 243 passed + 8 skipped (subió de
239 — 7 tests nuevos en `tests/sistema/test_monitoreo.py`: gate de rol,
los 5 componentes con disponibilidad real vs. mockeada a fallar para
Airflow — sin propagar el error crudo —, umbrales por defecto + PUT con
efecto real verificado en un `GET /sistema/salud` posterior + evento de
auditoría con antes/después, y 422 sobre un componente inválido). Mongo y
Redis se prueban reales-en-memoria (mongomock/fakeredis, ya provistos por
`conftest.py`) sin mockear nada; solo ClickHouse/Airflow se mockean en los
tests (para no depender de que estén accesibles y rápidos desde el
proceso de pytest). `ruff check` limpio. Frontend: `npm run build/lint/test`
limpios en `web-interno` (14 tests, 1 nuevo).

---

## 17. Módulo 8.2 (Gobernanza de datos) — cerrado y verificado (2026-08-06)

**Matiz confirmado por el usuario antes de construir** (re-explicitado al
autorizar este módulo): seudonimizar el identificador visible en la
bitácora sin romper su integridad referencial, **nunca** eliminar ni
modificar los eventos ya escritos. Fidelidad exacta al texto de CU-O17 A2:
*"los datos personales se anonimizan en las entidades de negocio, pero los
eventos de bitácora se conservan con el identificador seudonimizado; la
propia anonimización queda registrada como evento"*.

**Decisión de diseño clave** (no estaba en el plan original con este nivel
de detalle, se resolvió al construir): `bitacora.actor_id` **ya era** un
UUID opaco desde siempre — nunca fue el dato personal en sí, así que
"conservar el identificador seudonimizado" se cumple trivialmente sin
tocar ningún evento ya escrito, pasado o futuro. Lo que sí requería
diseño real era el **contenido** del nuevo evento de anonimización: se
decidió que `datos_previos`/`datos_posteriores` de
`USUARIO_ANONIMIZACION` **nunca** llevan el nombre/teléfono/correo real
que se está purgando — solo `{"anonimizado": bool}` + el seudónimo nuevo
(que no es información personal). Grabar el dato purgado en un evento de
`bitacora` (insert-only, permanente) habría derrotado el propósito mismo
de la anonimización.

**Backend**:
- **8.2a** (`usuarios/service.py::anonimizar_usuario`, extiende el módulo
  de Módulo 1 en vez de crear uno nuevo — es una operación sobre la misma
  entidad `usuarios`): `POST /usuarios/{id}/anonimizar`, gateado a
  `admin_sistema` como el resto del módulo. Doble confirmación **real**,
  no solo de UI: `AnonimizarConfirmar.confirmacion` es un
  `Literal["ANONIMIZAR"]` de Pydantic — cualquier otro valor es 422 antes
  de que el service se ejecute. Irreversible: no existe ninguna operación
  ni endpoint de "desanonimizar". `nombre` → `"Usuario Anonimizado
  {id[:8]}"`, `telefono`/`email` → **removidos del documento** (`$unset`,
  no solo `null`) — los índices `unique+sparse` de esos dos campos
  (`db_mongo.py::ensure_indexes`) ya toleran ausencia, así que no hace
  falta inventar un valor único de reemplazo. Idempotente-protegido: un
  segundo intento sobre la misma cuenta es 409 (`usuario.anonimizado`
  chequeado primero). Acción de auditoría nueva `USUARIO_ANONIMIZACION`
  (ver decisión de diseño arriba sobre su contenido).
- **8.2b** (`sistema/service.py::obtener_politica_retencion`, extiende el
  módulo de Módulo 8.1/5): `GET /sistema/politica-retencion`. El TTL de
  `posiciones` se lee **real** desde `db.posiciones.index_information()`
  (nunca hardcodeado "7 días" como texto) — si el índice cambiara algún
  día, este endpoint lo reflejaría solo. El resto de colecciones
  (`bitacora`, `viajes/pagos/liquidaciones`, `documentos`, `usuarios`) no
  tienen TTL de Mongo — se documentan con texto explicando la razón real
  de negocio (auditoría permanente, registro contable, vigencia
  contractual, hasta anonimización manual), marcadas `fuente:
  "documentado"` para que el frontend distinga visualmente cuál dato es
  mecánico y cuál es una política escrita.

**Frontend** (`apps/web-interno/src/sections/GobernanzaDatos.tsx`): dos
secciones en una sola pantalla (no pestañas, a diferencia de Catálogos/
Integraciones — aquí ambos bloques son cortos y no compiten por espacio).
"Anonimizar una cuenta": buscador simple (reusa `GET /usuarios?texto=`) +
resultado con botón "Anonimizar" que abre un `DetailPanel` de doble
confirmación real -- el botón "Anonimizar de forma permanente" queda
`aceptarDisabled` hasta que el campo de texto sea exactamente
`"ANONIMIZAR"` (no basta con no estar vacío). Cuentas ya anonimizadas
muestran un `Badge` "YA ANONIMIZADA" en vez del botón. "Política de
retención vigente": tabla de solo lectura, columna "Fuente" con `Badge`
distinguiendo `TTL REAL` (verde) de `DOCUMENTADO` (neutral).

**Bug real encontrado y corregido durante la verificación en navegador**
(no específico de este módulo — afecta a `shared-ui` completo): el label
del campo de confirmación contiene comillas (`Escribe "ANONIMIZAR" para
confirmar`), y `TextField.tsx` generaba su `id` con
`label.toLowerCase().replace(/\s+/g, "-")` **sin quitar las comillas** —
el `id` resultante rompía el árbol de accesibilidad de la herramienta de
verificación (`querySelector` con un selector inválido) y, más
relevante, es un `id` HTML frágil en general (cualquier consumidor de
`for="…"`/`querySelector` con ese id se rompe igual). Corregido
generalizando el saneo: `.replace(/[^a-z0-9-]/g, "")` después de
minúsculas+guiones — beneficia a cualquier label futuro con puntuación,
no solo a este caso. Verificado que no rompió ningún test/build existente
en las 3 apps + `shared-ui` (ver Suite automatizada abajo).

**Verificación real en navegador** (sesión `admin_sistema`, backend
reiniciado tras el cambio de código): cuenta de prueba real creada vía
`POST /usuarios` ("Persona Prueba Gobernanza", con teléfono/correo
reales), encontrada por el buscador, botón "Anonimizar de forma
permanente" confirmado **deshabilitado** con texto incorrecto ("si") y
habilitado solo con "ANONIMIZAR" exacto. Tras confirmar: la fila
desapareció de los resultados (la cuenta ya no matchea la búsqueda con el
nombre viejo). Confirmado en Mongo: `usuarios` con `nombre="Usuario
Anonimizado 8f2ec490"`, **sin** los campos `telefono`/`email` en el
documento (no solo `null`), `anonimizado: true`. Evento
`USUARIO_ANONIMIZACION` real confirmado con `datos_previos={"anonimizado":
false}` / `datos_posteriores={"anonimizado": true, "nombre_seudonimo":
"Usuario Anonimizado 8f2ec490"}` — **sin** rastro del nombre/teléfono/
correo real en ningún campo del evento (grepeado el documento completo
para confirmarlo). Idempotencia confirmada con una llamada real de API
directa: segundo intento de anonimizar la misma cuenta → 409. Gate de rol
confirmado con llamadas reales: `admin_sistema` → 200 (implícito, la
sesión de navegador ya lo probó), `gerencia` → 403. Política de retención
confirmada con datos reales: `posiciones` → "7 días (TTL automático
real)" con `fuente: indice_ttl_real`, el resto con `fuente: documentado`.
Cuenta de prueba borrada de Mongo al cierre (ya no tenía ningún dato
personal real que perder — la anonimización ya lo había purgado; se borró
el documento entero solo para no dejar un registro huérfano de prueba).

**Suite automatizada**: `pytest` backend 248 passed + 8 skipped (subió de
243 — 5 tests nuevos en `tests/usuarios/test_gobernanza_datos.py`: gate de
rol, 422 sobre confirmación incorrecta, purga real de datos personales +
409 en el segundo intento, evento de auditoría sin exponer el dato
purgado -- verificado con un `assert "dato" not in str(evento)` literal
sobre nombre/teléfono/correo --, y TTL real de `posiciones` vía
`index_information`). `ruff check` limpio. Frontend: `npm run
build/lint/test` limpios en las 3 apps (`web-pasajero` 5, `web-conductor`
3, `web-interno` 15 — 1 nuevo) + `shared-ui` lint, confirmando que el fix
de `TextField.tsx` no rompió nada fuera de este módulo.

---

## 18. Módulo 7 (Respaldos y Continuidad) — cerrado y verificado (2026-08-07)

**El recorte de alcance más grande del documento — repasado y aprobado en
detalle antes de construir**, con un ajuste real sobre la propuesta
original:

- **Verificado antes de escribir código**: la imagen del backend
  (`python:3.11-slim`) **no tiene instalados** `mongodb-database-tools`
  (`mongodump`/`mongorestore`) ni `clickhouse-client` — la spec y la
  propuesta original del plan asumían esas herramientas disponibles. Se
  presentaron 2 opciones al usuario (instalar los binarios y reconstruir
  la imagen, vs. exportar vía los drivers que el backend ya usa en
  producción) y **se aprobó explícitamente la Opción B (drivers)** — no es
  una limitación descubierta a medias, es una decisión de arquitectura
  documentada: menos superficie nueva (sin paquetes de sistema nuevos, sin
  reconstruir la imagen para una función administrativa) a costa de un
  formato propio (JSONL para Mongo vía `bson.json_util`, pickle para
  ClickHouse) en vez del formato binario nativo de `mongodump`. El
  respaldo resultante es real, restaurable y verificado extremo a extremo
  (ver más abajo) — "no usa mongodump" no significa "no es un respaldo
  real".
- **Alcance de qué se respalda, decidido con datos reales del entorno**
  (consultado `system.tables`/`countDocuments` antes de decidir, no a
  ciegas): Mongo respalda **todas** las colecciones de negocio, incluida
  `bitacora` (permanente, perderla sería grave) y `posiciones` (TTL propio
  de 7 días, pero sin razón para excluirla de un respaldo puntual) —
  excluye solo las 4 colecciones propias de este módulo
  (`respaldos`/`plan_dr`/`simulacros_dr`/`restauraciones`). ClickHouse
  respalda solo las tablas `rpt_*` (capa de reporting, la que alimenta los
  9 dashboards tácticos) + un puñado de tablas de referencia — **excluye
  deliberadamente** `bronze_*`/`fact_*`/`cuarentena_*`: en este entorno de
  desarrollo esas capas intermedias del ETL suman más de 6 millones de
  filas (`bronze_pagos`, `bronze_viaje_historico_nyc`, etc., confirmado
  contra `system.tables` real antes de decidir) y son 100% re-derivables
  re-ejecutando los DAGs de Airflow contra Mongo/PocketBase — no aportan
  resiliencia real (no son la fuente de verdad) y multiplicarían el tiempo
  de respaldo sin necesidad.
- **Restauración de prueba**: `base_destino` está **hardcodeado en el
  código** a `urbanflet_restore_test` (Mongo) / `urbanflet_gold_restore_test`
  (ClickHouse) — nunca acepta un nombre de base del cliente, así que
  "nunca directo a producción" es una garantía de código, no solo un
  texto en la UI.
- **Cifrado en reposo**: no implementado — la UI lo dice explícitamente
  ("Cifrado en reposo: no implementado en este entorno de desarrollo") en
  vez de simular un candado que no protege nada, tal como se aprobó.

**Backend** (`backend/src/respaldos/`, módulo nuevo — `POST`/`GET
/respaldos`, `POST /respaldos/{id}/verificar`, `POST
/respaldos/{id}/restaurar`, `GET /respaldos/restauraciones`, `GET`/`PUT
/respaldos/plan-dr[/{dominio}]`, `GET`/`POST /respaldos/simulacros`):
- **7.1**: `POST /respaldos` dispara los dos respaldos (Mongo + ClickHouse)
  como tareas de fondo reales (`asyncio.create_task`, con referencia
  fuerte guardada en un `set` module-level + `add_done_callback` — sin
  esto, un gotcha real y documentado de `asyncio` permite que la tarea sea
  recolectada a medio correr) y responde `202` de inmediato con los 2
  registros en `en_progreso`. El hash SHA-256 se calcula incrementalmente
  mientras se escribe el archivo (`hasher.update()` por línea/bloque, no
  una segunda pasada sobre el archivo completo). `POST
  /{id}/verificar` recalcula el hash real del archivo en disco y lo
  compara contra el guardado. `POST /{id}/restaurar` solo procede si el
  respaldo está `completado` (409 si no), y también corre en una tarea de
  fondo.
- **7.2**: `plan_dr` (colección con 7 documentos fijos, uno por dominio,
  `_id=dominio`) y `simulacros_dr` (insert-only, como la bitácora). Gate
  `admin_sistema` **o** `gerencia` — el único OR-gate real de todo el
  bloque de admin_sistema, porque la spec lo pide explícitamente para este
  punto ("su acceso debe restringirse solo a admin_sistema y gerencia").
  7.1 (respaldos técnicos) sigue siendo exclusivo de `admin_sistema`, sin
  excepción.
- Volumen Docker nuevo `respaldos_data` (`docker-compose.yml`), montado en
  `/app/respaldos` — separado del bind mount de `./backend/src`, para que
  un respaldo real sobreviva a recrear el contenedor y nunca se mezcle con
  el código fuente. Requirió reconstruir la imagen del backend
  (`docker compose up -d --build backend`) para que el volumen nuevo
  quedara montado — un simple restart no alcanza para un cambio de
  volúmenes.
- 4 acciones de auditoría nuevas: `RESPALDO_DISPARO`,
  `RESPALDO_RESTAURACION_PRUEBA`, `PLAN_DR_CAMBIO`,
  `SIMULACRO_DR_REGISTRO`.
- **Bug real encontrado y corregido durante las pruebas** (no específico
  de tests — habría fallado igual contra el Mongo real de producción):
  Mongo devuelve `datetime` **naive** en UTC al leer un documento (BSON no
  guarda tzinfo), pero el cálculo de duración restaba contra un
  `datetime.now(UTC)` recién creado (aware) — `TypeError: can't subtract
  offset-naive and offset-aware datetimes`, con el respaldo real fallando
  silenciosamente a `estado="error"` cada vez. Corregido con un helper
  `_como_utc()` que normaliza cualquier `datetime` leído de Mongo antes de
  restar, aplicado en los 2 puntos donde se calcula `duracion_segundos`
  (fin de respaldo y fin de restauración).

**Frontend** (`apps/web-interno/src/sections/Respaldos.tsx`, 2 pestañas):
"Respaldos" (tabla de respaldos con Nuevo/Actualizar + detalle con
Verificar/Restaurar + tabla de restauraciones de prueba) y "Plan de
continuidad" (tabla de 7 dominios editable + registro de simulacros). Un
actor `gerencia` (sin `admin_sistema`) ve **solo** la pestaña de
continuidad — ni las pestañas ni el nav rendering intentan cargar
`/respaldos`, que el backend le rechazaría con 403; la sección aterriza
directo en "Plan de continuidad" sin ofrecer una pestaña que fallaría.

**Bug real encontrado y corregido durante la verificación en navegador**
(no específico de este módulo — afecta a `shared-ui` completo, ver
detalle igual en §17 porque se encontró en la misma sesión de trabajo):
el `id` autogenerado de `TextField` no sanitizaba comillas/puntuación del
label. Ya corregido en el cierre de Módulo 8.2; sin impacto adicional
aquí.

**Verificación real en navegador y por API** (sesión `admin_sistema`,
backend reconstruido y reiniciado con el volumen nuevo montado
-- confirmado con `docker inspect` que `/app/respaldos` apunta al volumen
con nombre, no al bind mount de código):
- **Respaldo real disparado** (`POST /respaldos`) contra la base de
  desarrollo real (~2.6M documentos reales entre `viajes`/`pagos` del
  dataset NYC sembrado en sesiones previas): Mongo completó en **78.5s**
  (2312.9 MB, 25 colecciones reales incluidas, `bitacora` y `posiciones`
  entre ellas), ClickHouse en **0.09s** (529.3 KB, 17 tablas — confirmado
  que NINGUNA `bronze_*`/`fact_*`/`cuarentena_*` quedó incluida).
- **Hash verificado dos veces** — una vez por API directa
  (`POST /{id}/verificar`, `integro: true` con hash recalculado real
  sobre el archivo de 2.4GB) y una vez en navegador real (botón "Verificar
  integridad" → "Íntegro: el hash coincide." renderizado con datos reales
  del backend, no simulado).
- **Restauración real ejecutada** contra las bases de prueba aisladas:
  Mongo en 107.1s (`urbanflet_restore_test`, conteos exactos —
  `viajes: 1,334,886`, `pagos: 1,241,750` — coincidiendo con los conteos
  reales de origen), ClickHouse en 0.4s (`urbanflet_gold_restore_test`,
  17 tablas con conteos exactos). **Confirmado con consultas directas a
  Mongo y ClickHouse** (no solo confiando en la respuesta de la API) que
  los documentos/filas reales aparecen en las bases de prueba Y que las
  bases reales (`urbanflet`/`urbanflet_gold`) siguen con exactamente los
  mismos conteos que antes — la restauración nunca las tocó.
- **Gate de rol confirmado con llamadas reales**: `admin_sistema` → 200 en
  `GET /respaldos`; `gerencia` → 403 en el mismo endpoint pero 200 en
  `GET /respaldos/plan-dr` — exactamente la separación de privilegios
  diseñada.
- **Plan de continuidad**: editado un dominio real (`captacion`, RTO "30
  minutos" / RPO "1 hora") desde el navegador, confirmado en la tabla
  tras guardar.
- **Auditoría real confirmada en Mongo**: eventos `RESPALDO_DISPARO`
  (`datos_posteriores.motores: ["mongo","clickhouse"]`) y 2×
  `RESPALDO_RESTAURACION_PRUEBA` (uno por motor, cada uno con
  `datos_posteriores.base_destino` apuntando a la base de prueba
  correspondiente, nunca a la real).
- **Limpieza al cierre**: las 2 bases de prueba
  (`urbanflet_restore_test`/`urbanflet_gold_restore_test`) se
  eliminaron tras confirmar la restauración — eran contenido
  reconstruible desde el respaldo, no datos originales. La entrada de
  prueba en `plan_dr` (dominio `captacion`) se revirtió a su estado vacío
  por defecto. **Se conservaron** los registros reales de
  `respaldos`/`restauraciones` y sus 3 eventos de auditoría — documentan
  una acción administrativa real que de hecho ocurrió (mismo criterio que
  la rotación de key de Google Maps en Módulo 4, §15): no son datos de
  negocio de prueba, son el registro legítimo de que el mecanismo de
  respaldo/restauración se probó de verdad contra datos de escala real.

**Suite automatizada**: `pytest` backend 259 passed + 8 skipped (subió de
248 — 11 tests nuevos en `tests/respaldos/test_respaldos.py`: gate de rol,
disparo real de 2 registros en_progreso, respaldo Mongo real con hash
válido recalculado desde el archivo, detección de archivo corrompido,
restauración Mongo confirmada consultando la base de prueba directamente
(nunca tocando `urbanflet`), 409 al restaurar un respaldo no completado,
scope real de tablas ClickHouse (`rpt_*` sí, `bronze_*` no, vía un cliente
ClickHouse falso para no depender de que el ClickHouse real del stack
esté accesible desde pytest), restauración ClickHouse con comandos/inserts
reales verificados, gate admin_sistema-o-gerencia en plan-dr, edición real
con evento de auditoría, y registro/listado de simulacros). Corregido de
paso el bug real de timezone descrito arriba (afecta producción, no solo
tests). `ruff check` limpio. Frontend: `npm run build/lint/test` limpios
en las 3 apps (17 tests en `web-interno`, 2 nuevos) + `shared-ui` lint.

**Con este cierre, los 8 módulos de `specs/specs-administrativas/
admin_sistema.md` quedan completos.**

---

## 19. Ronda de usabilidad post-cierre (2026-08-07) — Punto #3: catálogo `talleres` + validación de `tipos_documento`

Tras el cierre de los 8 módulos (§0–§18), el usuario hizo pruebas manuales
reales y pidió una ronda de 7 mejoras transversales de usabilidad/
automatización (documentada en `CLAUDE.md` §9, no duplicada aquí). Los
puntos 3 y 6 requerían una propuesta previa aprobada antes de construir —
esta sección cierra el punto 3, ya aprobado explícitamente: *"construye
'talleres' + el fix de tipos_documento en Captación. Canal queda fuera por
ahora... Confirmado no tocar ninguna máquina de estado."*

**Catálogo `talleres` — nuevo, mismo patrón que `tipos_documento`/
`motivos_cancelacion`** (`backend/src/catalogos/`): `TallerCreate`/
`TallerEditar`/`TallerOut` en `schemas.py`; `crear_taller`/
`listar_talleres`/`editar_taller` + `TallerNoEncontradoError`/
`TallerYaExisteError` en `service.py`; 3 endpoints (`GET`/`POST
/catalogos/talleres`, `PATCH /catalogos/talleres/{id}`) en `router.py`,
gateados a `admin_sistema` exclusivo, igual que el resto de Módulo 3.
Índice único `talleres.nombre` agregado a `ensure_indexes()`
(`backend/src/core/db_mongo.py`). Solo activar/desactivar, sin DELETE —
mismo razonamiento que los otros 2 catálogos: `mantenimiento.ordenes.taller`
(`OrdenCrearRequest`/`OrdenCerrarRequest`) es texto libre sin FK real, así
que desactivar es la única operación segura y reversible. **No se tocó
ninguna máquina de estado** (`EstadoOrden`/`TipoOrden` siguen intactos) ni
el módulo de mantenimiento en sí — este catálogo queda listo para que un
futuro cambio en `mantenimiento` lo consuma como validación, igual que
`tipos_documento` ahora lo hace en captación (ver abajo), pero esa
integración con `mantenimiento/service.py` **no se hizo** en este punto —
quedó fuera del pedido explícito ("construye 'talleres' + el fix de
tipos_documento en Captación").

**Fix de `tipos_documento` en Captación** (`backend/src/captacion/
service.py::crear_solicitud`): nueva excepción `TipoDocumentoInvalidoError`
(422, `TIPO_DOCUMENTO_INVALIDO`). Antes de registrar el usuario, si la
solicitud trae `documentos`, valida que cada `tipo` pedido exista en
`tipos_documento` con `activo: true` — si alguno no está reconocido o está
inactivo, rechaza toda la solicitud con el/los nombres no reconocidos en
el mensaje. Cierra el gap real que motivó este punto: hasta ahora
`documentos[].tipo` era texto 100% libre sin ninguna validación contra el
catálogo que Módulo 3.2 ya gestiona — un admin podía desactivar un tipo en
el catálogo y captación seguía aceptándolo sin aviso.

**Verificación real (no solo tests)**:
- Backend: `pytest tests/catalogos tests/captacion -q` → 30 passed, 1
  skipped. Suite completa: **270 passed, 8 skipped** (subió de 259 — 4
  tests nuevos de `talleres` en `test_catalogos.py` [crear/listar/editar +
  evento de auditoría, 409 duplicado, 404 no encontrado, 403 sin rol] + 3
  tests nuevos de validación en `test_captacion.py` [tipo no reconocido →
  422, tipo inactivo → 422, tipo activo → 201] + 1 test existente
  (`test_flujo_completo_tomar_y_aprobar_solicitud`) ajustado para sembrar
  `LICENCIA`/`MATRICULA` como tipos activos antes de crear la solicitud —
  sin ese seed, la nueva validación lo hubiera roto, ya que antes no
  validaba nada). `ruff check src tests` limpio.
- Frontend: pestaña "Talleres" agregada a `apps/web-interno/src/sections/
  Catalogos.tsx` (`SeccionTalleres`, mismo patrón WorkPanel-lite que
  `SeccionMotivos`/`SeccionTiposDocumento` — sin paginación server-side,
  igual que sus 2 vecinas). `npm run build/lint/test -w
  @urbanflet/web-interno` limpios (20 tests, sin regresión — no se sumó
  test dedicado a Talleres, el patrón ya está cubierto por el test
  existente de Catálogos sobre Tipos de documento).
- **Navegador real** (login `admin_sistema` ya persistido en sesión):
  pestaña Talleres carga vacía, "Nuevo" abre el detalle, se creó un taller
  real ("Taller Central QA") que apareció en la tabla — confirmado también
  directo en Mongo (`db.talleres`) con su evento `CATALOGO_CREACION` real
  en `bitacora` (`datos_posteriores.nombre` correcto, `datos_previos:
  null`).
- **API real** (`POST /captacion/solicitudes`): un `documentos[].tipo` no
  reconocido devolvió `422 TIPO_DOCUMENTO_INVALIDO` con el nombre exacto
  en el mensaje; el mismo request con un tipo activo real (`"Prueba
  documento"`, ya en el catálogo desde antes) devolvió `201` normal.
- **Limpieza**: el taller de prueba y las 2 solicitudes/usuarios/vehículos
  de prueba de la verificación de API se eliminaron de Mongo al cerrar —
  confirmado con conteos en 0 tras el borrado.

Punto #3 de la ronda de usabilidad — **cerrado**.

---

## 20. Ronda de usabilidad post-cierre (2026-08-07) — Punto #6: mejoras de Monitoreo

Aprobado explícitamente por el usuario: *"adelante con el enfoque
propuesto — indicadores vía serverStatus/dbStats (Mongo), INFO (Redis),
system.metrics (ClickHouse), sin Airflow por ahora. Histórico en Mongo con
TTL de 7 días, auto-refresco de 20s con pausa manual."*

**Indicadores reales por motor** (`backend/src/sistema/service.py`, nuevas
`_indicadores_mongo`/`_indicadores_redis`/`_indicadores_clickhouse` +
`obtener_indicadores`, expuestas en `GET /sistema/indicadores`): Mongo vía
`db.command("serverStatus")` + `db.command("dbStats")` (conexiones activas/
disponibles, operaciones totales, tamaño de datos/almacenamiento,
colecciones, índices, tiempo de actividad); Redis vía `INFO` (memoria
usada, clientes conectados, hit rate de keyspace, tiempo de actividad);
ClickHouse vía `system.metrics`/`system.asynchronous_metrics` (consultas
activas, memoria residente real, tiempo de actividad). Mismo patrón de
degradación que `_medir()` (Módulo 5 original): cualquier fallo del driver
degrada a `disponible: false` sin propagar el error crudo, nunca revienta
el endpoint. **Bug real encontrado y corregido durante la verificación en
navegador**: el metric name inicial (`MemoryTracking`) no existe en
`system.asynchronous_metrics` de la versión real de ClickHouse del stack
(24.x) — confirmado con `clickhouse-client` directo contra el contenedor
real; corregido a `MemoryResident` (RSS real del proceso), que sí existe y
devuelve un valor real (896 MB contra el ClickHouse real del entorno).

**Histórico con TTL de 7 días** (`historial_monitoreo`, índice TTL nuevo en
`db_mongo.py::ensure_indexes()` — `expireAfterSeconds=7*24*60*60` — +
índice `{componente:1, ts:1}` para la consulta por ventana): cada llamada
real a `obtener_salud()` (incluida cada vez que el auto-refresco de 20s del
frontend consulta el panel) escribe un snapshot por componente —
**sin ningún worker/cron nuevo**, el propio uso del panel genera la serie
de tiempo. Escritura best-effort (`try/except` silencioso): un fallo al
guardar el histórico nunca debe romper la respuesta de `/sistema/salud`
que sí es crítica para el panel. Nuevo endpoint `GET
/sistema/historial-latencia?horas=N` (`N` entre 1 y 168, default 24) para
leer la ventana.

**Auto-refresco de 20s con pausa manual** (`apps/web-interno/src/sections/
Monitoreo.tsx`): `setInterval` con un `ref` que lee el estado de pausa en
cada tick (evita el closure-stale de un `useEffect` con `[]` de
dependencias), botón "Pausar actualización automática" ↔ "Reanudar
actualización automática (20s)". El timestamp "Última consulta" ya existía
del Módulo 5 original — se mantuvo tal cual, ahora también se congela
correctamente cuando el usuario pausa.

**Gráfico de tendencia** (`TrendLineChart` ya existente de `shared-ui`,
sin componente nuevo): los puntos de `historial_monitoreo` (una fila por
componente, mismo `ts` exacto entre componentes de la misma consulta) se
pivotan client-side a una fila por `ts` con un campo por componente — mismo
criterio ya usado para "tendencia mensual" en varios dashboards tácticos
(pivot es solo reshape para el eje X, la agregación real ya viene hecha).
Eje X en hora local (`HH:MM:SS`), 5 series (una por componente), leyenda
visible (>1 serie).

**Verificación real (no solo tests)**:
- Backend: `pytest tests/sistema -q` → 11 passed (4 nuevos: degradación a
  no disponible contra mongomock/fakeredis reales que no implementan
  `serverStatus`/`dbStats`/`INFO` — confirmado explícitamente que
  mongomock_motor y fakeredis no soportan esos comandos antes de escribir
  el test, para que la aserción `disponible is False` sea determinista y no
  un accidente; gate de rol en `/sistema/indicadores`; histórico se registra
  en cada consulta de salud con el conteo exacto esperado 5×N; filtro de
  ventana de horas con 422 fuera de rango `[1,168]`). Suite completa: 274
  passed + 8 skipped (subió de 270). `ruff check src tests` limpio.
- Frontend: `npm run build/lint/test -w @urbanflet/web-interno` limpios (20
  tests, sin regresión — el test existente de Monitoreo se amplió con los 2
  fetches nuevos y una aserción reformulada con `findAllByText` porque
  "No disponible" pasó a aparecer más de una vez en la pantalla, un cambio
  esperado por las tarjetas de indicadores adicionales, no una regresión).
- **Navegador real** (login `admin_sistema`, backend reconstruido y
  reiniciado dos veces — una para el código inicial, otra tras el fix del
  metric name de ClickHouse): "Indicadores adicionales" mostró datos reales
  del entorno vivo (Mongo: 9 conexiones activas, 1810.1 MB de datos reales;
  Redis: 1.3 MB de memoria usada, 0% hit rate — coherente con un Redis que
  recién reinició; ClickHouse: 1 consulta activa, 896 MB de memoria
  residente real tras el fix). El gráfico de tendencia acumuló puntos
  reales entre navegaciones (varias marcas de tiempo distintas visibles
  tras varias consultas). El botón de pausa confirmado: tras pausar, el
  timestamp "Última consulta" dejó de avanzar; el texto del botón cambió a
  "Reanudar actualización automática (20s)".
- **Mongo verificado directo**: `db.historial_monitoreo` con documentos
  reales (`ts`/`componente`/`latencia_ms`/`estado`), índice TTL confirmado
  con `expireAfterSeconds: 604800` (exactamente 7 días) vía
  `getIndexes()`. Los snapshots generados durante la verificación manual se
  limpiaron al cerrar (`deleteMany({})`) — son telemetría reconstruible por
  el propio uso del panel, no un dato que valga la pena preservar como
  evidencia (a diferencia de los eventos de auditoría, que sí se
  conservan).

Punto #6 de la ronda de usabilidad — **cerrado. Con esto, los 7 puntos de
la ronda de usabilidad post-cierre (2026-08-07) quedan completos.**
