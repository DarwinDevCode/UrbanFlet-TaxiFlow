# Arquitectura de software — UrbanFleet

## 1. Visión general

El sistema es **100% web**: no existen aplicaciones móviles nativas. Se compone de tres clientes web, un backend único en Python, tres motores de datos con responsabilidades disjuntas y un orquestador de pipelines. Los portales de pasajero y conductor se construyen como **PWA responsivas** (instalables desde el navegador del teléfono), porque ambos roles usan el sistema principalmente desde el celular. La regla estructural es: **los clientes nunca tocan las bases de datos; toda lectura y escritura pasa por la API del backend**, que aplica autenticación, autorización por rol y registro de auditoría (ver `operativo_cumplimiento.md`).

```
┌──────────────┐ ┌──────────────┐ ┌──────────────────┐
│ Web pasajero  │ │ Web conductor │ │ Portal web interno│
│  (PWA)        │ │  (PWA)        │ │ (jefes de área,   │
└──────┬───────┘ └──────┬───────┘ │  gerencia)        │
       │                │          └────────┬─────────┘
       └────────┬───────┴───────────────────┘
                ▼  HTTPS (REST + WebSocket)
     ┌─────────────────────────────┐
     │   Backend Python (FastAPI)   │
     │  auth · autorización · viajes│
     │  despacho · pagos · bitácora │
     └───┬──────────┬──────────┬───┘
         ▼          ▼          ▼
   ┌──────────┐ ┌─────────┐ ┌────────────┐
   │PocketBase│ │ MongoDB │ │ ClickHouse │
   │dataset   │ │operación│ │ analítica  │
   │NYC crudo │ │OLTP     │ │ (Gold)     │
   └────┬─────┘ └────┬────┘ └─────▲──────┘
        │            │            │
        └────────────┴────► Apache Airflow (ETL Medallion)
```

Comunicación:
- **Clientes ↔ backend:** REST/JSON sobre HTTPS para operaciones; **WebSocket** para lo que exige tiempo real (posición del vehículo en el mapa, oferta de viaje al conductor, estado del viaje) mientras la sesión web está activa, y **Web Push API** para notificar cuando la pestaña está cerrada o en segundo plano. El backend publica los eventos de viaje al canal del pasajero y del conductor correspondientes.
- **Backend ↔ bases:** drivers nativos de Python; ninguna base expone puertos a los clientes.
- **Airflow ↔ bases:** lee de MongoDB y PocketBase, escribe en ClickHouse. Es el único componente autorizado a escribir en ClickHouse.

## 2. Stack tecnológico (obligatorio)

| Capa | Tecnología | Rol |
|---|---|---|
| Frontend | Aplicaciones web (SPA/PWA) servidas como estáticos; responsivas para uso en el navegador del teléfono | Portales de pasajero, conductor e interno |
| Backend | **Python 3.11+** con FastAPI + Uvicorn | API REST, WebSockets, lógica de negocio, máquina de estados del viaje, motor de despacho |
| Validación | Pydantic | Contratos de entrada/salida de la API |
| BD operativa principal | **MongoDB 7.x** | Todas las entidades transaccionales de la cooperativa: usuarios, solicitudes, viajes, posiciones, pagos, liquidaciones, órdenes de mantenimiento, documentos, bitácora de auditoría |
| BD de dataset crudo | **PocketBase 0.22+ (SQLite WAL)** | Almacena exclusivamente el dataset crudo *2021 Yellow Taxi Trip Data* para la analítica histórica de calibración tarifaria y de demanda; expone su API de lectura para la extracción del DAG `dag_historico_nyc` |
| BD columnar | **ClickHouse 24.x** | Capa Gold: hechos y dimensiones para informes compuestos y KPIs de los tres niveles |
| Orquestación ETL | Apache Airflow 2.x (Python) | DAGs Medallion por dominio (ver `operativo_plataforma.md`) |
| Procesamiento en DAGs | Pandas + clickhouse-connect + pymongo | Extracción, validación, cuarentena, carga idempotente |
| Cache y tiempo real | Redis | Última posición conocida por vehículo (clave por `vehiculo_id`, TTL 60 s), sesiones WebSocket, colas de oferta de despacho con expiración de 20 s |
| Contenedores | Docker + docker-compose | Un servicio por componente |

Justificación de la partición de motores (el diseño fino está en `diseno_base_datos.md`):
- **MongoDB** concentra el OLTP propio porque los documentos de viaje (traza embebida, desglose tarifario, calificaciones) y de solicitud (documentos adjuntos con metadatos) son agregados naturales de documento, y el volumen de escritura de posiciones exige inserciones baratas.
- **PocketBase** queda deliberadamente acotado al dataset crudo de NYC: es un dato de solo lectura, ajeno a la operación, y aislarlo evita que 700 000+ registros históricos convivan con el OLTP.
- **ClickHouse** sirve las agregaciones (sumas, promedios, conteos por zona/franja/periodo) que en un motor de documentos serían costosas; ningún informe compuesto consulta las bases operativas.

## 3. Módulos del backend

| Módulo | Paquete de dominio | Responsabilidad |
|---|---|---|
| `auth` | transversal | Registro, OTP, sesiones JWT, refresh, resolución de rol por petición |
| `captacion` | pkg-captacion | Solicitudes de conductor, carga documental, verificación (CU-O01–O03) |
| `viajes` | pkg-viajes | Máquina de estados del viaje, solicitud, ejecución, finalización y tarifa (CU-O04, O07, O08, O14) |
| `despacho` | pkg-viajes | Selección de candidatos, ofertas con expiración, reasignación (CU-O05, O06) — consume Redis |
| `flota` | pkg-flota | Ingesta de posiciones, estados del conductor, detección de sin señal (CU-O19) |
| `mantenimiento` | pkg-mantenimiento | Órdenes, retiro/habilitación de vehículos, pre-órdenes automáticas (CU-O12, O13) |
| `recaudacion` | pkg-recaudacion | Registro y validación de pagos, comisiones, liquidaciones (CU-O09–O11) |
| `cumplimiento` | pkg-cumplimiento | Control documental diario, banderas, bloqueos |
| `auditoria` | pkg-auditoria | Bitácora de solo inserción, alertas de seguridad (CU-O17, O18) |
| `notificaciones` | transversal | Push, SMS (OTP) y eventos WebSocket |
| `parametros` | transversal | Tarifas por franja, % de comisión, radios de despacho — versionados con vigencia |

Cada módulo expone su router de FastAPI y sus servicios; ningún módulo accede a las colecciones de otro dominio directamente (comunicación por servicios internos o eventos).

## 4. APIs

### 4.1. API interna (REST, consumida por las tres apps)

| Grupo | Endpoints principales | Consumidor |
|---|---|---|
| Autenticación | `POST /auth/registro`, `POST /auth/otp`, `POST /auth/login`, `POST /auth/refresh` | Todos |
| Captación | `POST /solicitudes`, `PATCH /solicitudes/{id}`, `POST /solicitudes/{id}/documentos`, `GET /solicitudes` (bandeja), `POST /solicitudes/{id}/decision` | Postulante, Admin. Captación |
| Viajes | `POST /viajes`, `GET /viajes/activo`, `POST /viajes/{id}/cancelar`, `POST /viajes/{id}/iniciar`, `POST /viajes/{id}/finalizar`, `GET /viajes` (historial), `GET /viajes/{id}/comprobante` | Pasajero, Conductor |
| Despacho | `POST /ofertas/{id}/respuesta` (aceptar/rechazar) | Conductor |
| Flota | `POST /posiciones` (batch), `POST /turno/iniciar`, `POST /turno/terminar` | Conductor |
| Tarifas | `GET /tarifas/estimacion?origen&destino` | Pasajero |
| Pagos | `POST /viajes/{id}/pago`, `GET /liquidaciones`, `POST /liquidaciones/{id}/observar` | Conductor, Pasajero, Admin. Financiero |
| Mantenimiento | `POST /ordenes`, `PATCH /ordenes/{id}`, `POST /ordenes/{id}/cerrar` | Jefe Mantenimiento |
| Cumplimiento | `GET /documentos/vencimientos`, `POST /documentos/{id}/verificacion` | Supervisor |
| Informes | `GET /informes/simples/{nombre}` (proxy a MongoDB), `GET /informes/compuestos/{nombre}` (proxy a vistas de ClickHouse) | Jefes de área, gerencia |
| Auditoría | `GET /bitacora?filtros` (solo lectura) | Supervisor, gerencia |

### 4.2. WebSocket (tiempo real)

Los canales operan mientras la sesión web está activa; los eventos que llegan con la pestaña cerrada se entregan por Web Push y se recuperan por REST al reabrir (`GET /viajes/activo`).

| Canal | Emite | Recibe |
|---|---|---|
| `/ws/pasajero/{viaje_id}` | Posición del conductor asignado, transiciones de estado, ETA | Mensajes de chat |
| `/ws/conductor` | Ofertas de viaje (con expiración), transiciones, mensajes de chat | Respuesta a oferta, chat |
| `/ws/tablero-flota` | Posiciones y alertas de toda la flota | — (solo Coordinador de Flota) |

### 4.3. API de integraciones externas (credenciales gestionadas por Cumplimiento, CU-T03)

`GET /ext/v1/...` de solo lectura sobre datos agregados (nunca personales), autenticada por API key con rate limit. Consumidor típico: el municipio/regulador que solicita indicadores de servicio.

## 5. Servicios externos requeridos

| Recurso | Propósito | Consumido por |
|---|---|---|
| Mapas, geocodificación y ruteo (Google Maps Platform u OpenStreetMap + OSRM/Nominatim como alternativa autoalojada; render en el navegador con Leaflet/MapLibre) | Mapa en los portales, dirección ↔ coordenadas, ruta óptima y ETA, snap de trazas | Portales y módulo `viajes`/`despacho` |
| Notificaciones **Web Push** (estándar VAPID, sin FCM/APNs nativos) | Ofertas de viaje, arribo del conductor, estados, vencimientos documentales cuando la pestaña no está activa | `notificaciones` |
| SMS transaccional (proveedor local o Twilio) | OTP de verificación de teléfono | `auth` |
| Pasarela de pagos (opcional según decisión de la junta) | Cobro con tarjeta/billetera, webhooks de confirmación | `recaudacion` |
| Llamada/chat enmascarado | Contacto pasajero–conductor sin exponer números | `notificaciones` |
| Almacenamiento de objetos (S3-compatible, p. ej. MinIO autoalojado) | Documentos de solicitudes, comprobantes PDF | `captacion`, `viajes` |

## 6. Requisitos transversales de implementación

1. **Idempotencia:** toda operación crítica acepta una clave de idempotencia (`Idempotency-Key`) — creación de viaje, registro de pago, respuesta a oferta — y las cargas de Airflow son idempotentes por partición de fecha.
2. **Fuente de verdad:** el estado del viaje vive solo en el backend; los clientes web se resincronizan con `GET /viajes/activo` en cada reconexión o recarga de página.
3. **Write-ahead de auditoría:** el evento de bitácora se escribe antes de confirmar el efecto de negocio; si la bitácora falla, la operación falla.
4. **Parámetros versionados:** tarifas, comisión y radios de despacho se leen por fecha de vigencia; ningún valor de negocio va cableado en código.
5. **Zonas horarias:** todos los timestamps se persisten en UTC; la franja tarifaria se resuelve en hora local de la ciudad de operación.
6. **Pruebas:** cobertura mínima 80% en módulos de `viajes`, `recaudacion` y `auditoria` (los tres con reglas de dinero y estado); pruebas de contrato sobre la API pública interna.
7. **Restricciones del entorno web (obligatorio documentarlas al equipo):** la geolocalización usa la Geolocation API del navegador y **no reporta de forma confiable con la pantalla bloqueada o la pestaña en segundo plano**; el portal del conductor debe operar como PWA instalada, mantenerse en primer plano durante el turno y solicitar wake lock (Screen Wake Lock API). El buffer de traza ante desconexiones se implementa en IndexedDB con sincronización al reconectar. La carga de documentos y fotos usa `<input type="file" capture>`.
