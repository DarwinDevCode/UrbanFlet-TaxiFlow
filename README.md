# UrbanFleet TaxiFlow

Sistema web de gestión integral para una **cooperativa de taxis**: captación de
socios conductores, despacho automático de carreras sobre mapa, cobro y
liquidación semanal, mantenimiento de la flota, cumplimiento documental,
bitácora de auditoría y paneles de indicadores operativos, tácticos y
estratégicos.

- **Backend:** Python 3.11 + FastAPI (monolito modular por dominio)
- **Bases de datos:** MongoDB 7 (operativa, replica set), Redis (tiempo real),
  ClickHouse (capa analítica Gold)
- **ETL:** Apache Airflow 2.9 (pipeline Bronze → Silver → Gold)
- **Frontends:** 3 SPA React 18 + TypeScript + Vite (pasajero y conductor como
  PWA, portal interno responsivo), mapa con Leaflet + OpenStreetMap

## Ejecutar con Docker

### Requisitos

- Docker Desktop (o Docker Engine con Compose v2.24 o superior).
- **7 GB de RAM para Docker** y unos 6 GB de disco libre. Cada servicio tiene
  un techo de memoria (`mem_limit` en `docker-compose.yml`) pensado para ese
  total; el consumo real con todo arrancado ronda los 3 GB.
- Puertos libres: 5173, 5174, 5175, 8000, 8080, 8090, 8123, 9000, 27017, 6379.

En Windows (Docker Desktop con WSL2) se puede limitar la memoria de la VM de
Docker creando `%USERPROFILE%\.wslconfig` con `[wsl2]` y `memory=8GB`, y
aplicando el cambio con `wsl --shutdown`.

### Levantar

```bash
cp .env.example .env
docker compose up --build
```

El primer arranque tarda unos 10-15 minutos: construye las imágenes, siembra
los datos de demostración (servicio `seed`) y luego carga la capa analítica
(servicio `airflow-bootstrap`). Esos dos servicios terminan solos con
`exited (0)` y el resto queda corriendo. Los paneles tácticos y estratégicos
se llenan cuando termina `airflow-bootstrap`. Para seguir el progreso:

```bash
docker compose logs -f seed airflow-bootstrap
```

### Detener

```bash
docker compose down          # detiene y conserva los datos
docker compose up -d         # vuelve a levantar con los mismos datos
```

### Reiniciar con datos limpios

```bash
docker compose down -v       # borra los volúmenes (Mongo, ClickHouse, Airflow, archivos)
docker compose up --build    # vuelve a sembrar todo desde cero
```

### URLs

| Aplicación | URL |
|---|---|
| Portal interno (administración, CRUD, dashboards) | http://localhost:5175 |
| App del pasajero (PWA) | http://localhost:5173 |
| App del conductor (PWA) | http://localhost:5174 |
| API (documentación Swagger) | http://localhost:8000/docs |
| Airflow | http://localhost:8080 (usuario `admin` / contraseña `admin`) |

### Usuarios de prueba

Todos los datos son ficticios. El inicio de sesión es con teléfono (o correo)
y contraseña.

| Rol | Aplicación | Teléfono | Contraseña |
|---|---|---|---|
| Pasajera (María José Cedeño) | web-pasajero :5173 | `+593987001122` | `DemoPasajero123!` |
| Conductor (Juan Carlos Pérez, taxi `PBA-1234`) | web-conductor :5174 | `+593911223344` | `DemoConductor123!` |
| Personal con los 7 roles operativos/tácticos (captación, mantenimiento, cumplimiento, flota, operaciones, finanzas, plataforma) | web-interno :5175 | `+593900000001` | `VerifDash123!` |
| Gerencia (tablero ejecutivo y paneles estratégicos) | web-interno :5175 | `+593900000010` | `Gerencia123!` |
| Administrador del sistema (usuarios, políticas, catálogos, respaldos, monitoreo) | web-interno :5175 | `+593900000099` | `AdminSistema123!` |
| Administrador de plataforma | web-interno :5175 | `+593911998822` | `AdminPlataforma123!` |
| Integración externa (rol de API, sin pantallas) | — | `+593900000011` | `Integracion123!` |

Los demás pasajeros sembrados usan la contraseña `Pasajero2026!` y los demás
conductores `Conductor2026!` (sus teléfonos se ven en el portal interno →
Administración → Usuarios).

### Datos de demostración

`backend/scripts/seed_demo_portafolio.py` siembra datos ambientados en
Quevedo (Los Ríos, Ecuador). Todo pasa por los servicios reales del backend,
con auditoría, transacciones y reglas de negocio:

- 45 pasajeros y 43 postulaciones de conductores con licencia y matrícula
  cargadas como imagen (30 aprobadas → socios con taxi y documentos; el resto
  en revisión, observadas o rechazadas).
- Placas con formato ecuatoriano (`RBC-4821`, `GAK-1290`...) y cédulas
  ficticias de Los Ríos.
- ~2.000 carreras de los últimos 3 meses con traza GPS, tarifa diurna y
  nocturna, cobro en efectivo, calificaciones, cancelaciones, carreras sin
  conductor y algunas discrepancias de cobro.
- Liquidaciones semanales por socio (pagadas, aprobadas, emitidas y observadas).
- ~40 órdenes de mantenimiento, reportes de falla con evidencia fotográfica,
  documentos vigentes / por vencer / vencidos, referidos, notificaciones y la
  bitácora de auditoría resultante.
- ~14 socios en turno: el servicio `flota-simulador` los mueve por el mapa
  (solo para la demo; en producción el GPS lo reporta la app del conductor).

Para probar el ciclo completo de una carrera: entra como conductor demo en
:5174 y pulsa **Iniciar turno**; luego, en otra ventana, entra como pasajera en
:5173 y pide un viaje cerca (sin key de Google Maps, el destino se elige
tocando el mapa).

### Variables de entorno

Ver `.env.example`. Ninguna contraseña real se versiona: `.env` está en
`.gitignore`. La key de Google Maps (`GOOGLE_MAPS_API_KEY`,
`VITE_GOOGLE_MAPS_API_KEY`) es opcional.

## Desarrollo sin Docker para los frontends

```bash
npm ci
npm run dev -w @urbanflet/web-interno     # :5175 (igual para web-pasajero / web-conductor)
```
