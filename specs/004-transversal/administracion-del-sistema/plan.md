# Plan técnico (retroactivo): Administración del Sistema

## Backend, uno por submódulo

- **IAM**: `backend/src/usuarios/` + `backend/src/core/sessions.py` (primer registro de sesiones
  activas en Redis del proyecto — JWT era puramente stateless hasta este módulo).
- **Configuración general**: `backend/src/configuracion/` — `service_dispatch.py` ya no tiene
  `RADIOS_M`/`OFERTA_EXPIRA_SEGUNDOS` como constantes fijas, se leen en caliente con los mismos
  valores como fallback si nunca se publicó una versión. `backend/src/core/feature_flags.py`.
- **Catálogos**: `backend/src/catalogos/` — mismo patrón de baja lógica (RN-SIS-001) en los 7
  catálogos.
- **Integraciones**: `backend/src/integraciones/` — `viajes/service.py::estimar_ruta` resuelve la
  clave de Google Maps vía `obtener_google_maps_api_key(db)`, que consulta un override en Mongo
  antes que la variable de entorno.
- **Monitoreo**: `backend/src/sistema/service.py` — `obtener_salud`/`obtener_umbrales`/
  `obtener_indicadores`/`obtener_historial_latencia`, con ping real a cada componente.
- **Políticas de seguridad**: `backend/src/seguridad/` — `core/security.py::create_token` acepta
  TTL opcionales; `core/rbac.py` importa `seguridad.service` de forma perezosa para no acoplar el
  archivo más foundational del proyecto a un dominio de negocio.
- **Respaldos**: `backend/src/respaldos/` — exportación vía los mismos drivers que el backend ya usa
  en producción (`motor`/`bson.json_util`, `clickhouse_connect`/pickle), no `mongodump`/
  `clickhouse-client` (nunca instalados en la imagen).
- **Gobernanza de datos**: `backend/src/usuarios/service.py::anonimizar_usuario` — reemplaza nombre/
  teléfono/correo reales por un seudónimo, de forma permanente.

## Frontend

- `apps/web-interno/src/sections/`: `Usuarios.tsx`, `PoliticasAuth.tsx`, `ParametrosGlobales.tsx`,
  `FeatureFlags.tsx`, `Catalogos.tsx`, `Integraciones.tsx`, `Monitoreo.tsx`,
  `PoliticasSeguridad.tsx`, `ConfiguracionAlertas.tsx`, `Respaldos.tsx`, `GobernanzaDatos.tsx`.

## Decisión de arquitectura: por qué `admin_sistema` es un rol separado, no una extensión de `admin_plataforma`

Principio de mínimo privilegio ya declarado en `operativo_cumplimiento.md`. `admin_plataforma`
administra pipeline/indicadores de negocio (CU-O15/16.1); `admin_sistema` gobierna seguridad de
infraestructura — ninguno hereda los permisos del otro, confirmado con OR-gates explícitos caso por
caso (un único caso real de OR-gate, el plan de continuidad con `gerencia`).

## Decisión de arquitectura: por qué la restauración de prueba tiene la base de destino fija en código

"Nunca toca producción" tenía que ser una garantía verificable en el código, no solo una promesa de
la interfaz — el nombre de la base de prueba (`urbanflet_restore_test`) nunca es un parámetro que el
cliente pueda mandar.
