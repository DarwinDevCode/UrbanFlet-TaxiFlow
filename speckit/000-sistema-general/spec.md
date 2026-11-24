# Especificación general: UrbanFleet TaxiFlow

## 1. Nombre del sistema

UrbanFleet TaxiFlow.

## 2. Objetivo general

Gestionar el ciclo completo de operación de una cooperativa de taxis que trabaja bajo un modelo de
**despacho automático**: incorporación de socios conductores y pasajeros, solicitud y ejecución de
viajes con asignación automática de conductor (sin operador humano), cobro y liquidación a los
socios, mantenimiento de la flota, y control de la vigencia documental exigida por el regulador —
con paneles de control tácticos por área y un nivel estratégico consolidado para la dirección.

## 3. Actores principales

| Actor | Cómo interviene |
|---|---|
| Pasajero | Solicita y sigue sus viajes, consulta su historial, gestiona su cuenta |
| Socio conductor | Gestiona su turno, atiende viajes, reporta fallas del vehículo, consulta sus liquidaciones |
| Administrador de Captación | Revisa y decide postulaciones de conductores |
| Coordinador de Operaciones | Supervisa el despacho y el desempeño de los socios |
| Coordinador de Flota | Supervisa la disponibilidad de vehículos en servicio |
| Jefe de Mantenimiento | Gestiona órdenes de taller y reportes de falla |
| Administrador Financiero | Concilia pagos y emite liquidaciones |
| Supervisor de Cumplimiento | Controla la vigencia documental y la bitácora de auditoría |
| Responsable de Plataforma | Supervisa la salud del proceso de datos |
| Gerencia General | Consulta el nivel estratégico consolidado |
| Administrador del Sistema | Gobierna la infraestructura del sistema (identidades, catálogos, integraciones, respaldos) |
| Sistema | Actor autónomo: despacho automático, viajes programados, cálculo de tarifas/comisiones, control diario de vigencia, proceso de datos |

Detalle completo de responsabilidades por rol y su portal en
[`DOCUMENTACION_ORGANIZACIONAL.md` §8](../../DOCUMENTACION_ORGANIZACIONAL.md).

## 4. Portales

| Portal | Para quién | Puerto de desarrollo |
|---|---|---|
| `web-pasajero` | Pasajeros | 5173 |
| `web-conductor` | Socios conductores | 5174 |
| `web-interno` | Personal de la cooperativa (operativo, táctico, estratégico, administración) | 5175 |

## 5. Módulos del sistema, por nivel organizacional

| Nivel | Departamento | Especificación |
|---|---|---|
| Operativo | Captación y Talento | [`operativo/01-captacion-y-talento/spec.md`](../operativo/01-captacion-y-talento/spec.md) |
| Operativo | Operaciones y Despacho | [`operativo/02-operaciones-y-despacho/spec.md`](../operativo/02-operaciones-y-despacho/spec.md) |
| Operativo | Coordinación de Flota | [`operativo/03-coordinacion-de-flota/spec.md`](../operativo/03-coordinacion-de-flota/spec.md) |
| Operativo | Mantenimiento | [`operativo/04-mantenimiento/spec.md`](../operativo/04-mantenimiento/spec.md) |
| Operativo | Control Financiero | [`operativo/05-control-financiero/spec.md`](../operativo/05-control-financiero/spec.md) |
| Operativo | Cumplimiento Regulatorio | [`operativo/06-cumplimiento-regulatorio/spec.md`](../operativo/06-cumplimiento-regulatorio/spec.md) |
| Táctico | (los 7 departamentos, un panel por área) | *pendiente de esta reconstrucción* |
| Estratégico | Dirección General | *pendiente de esta reconstrucción* |
| Transversal | Bitácora, notificaciones, autoservicio, proceso de datos, administración del sistema | *pendiente de esta reconstrucción* |

## 6. Reglas generales

Ver [`constitucion.md`](../constitucion.md) — reglas que aplican a todo el sistema, no repetidas en
cada especificación de módulo.

## 7. Dependencias generales

| Dependencia | Rol |
|---|---|
| MongoDB (réplica de un nodo) | Base operativa — todo lo transaccional (viajes, solicitudes, órdenes, liquidaciones, documentos, usuarios, bitácora) |
| ClickHouse | Base analítica — indicadores agregados publicados por el proceso de datos, consumidos por los niveles táctico y estratégico |
| Redis | Sesiones activas, contadores de bloqueo por intentos fallidos, caché de posición de flota |
| Apache Airflow | Orquesta el proceso de datos (Bronze → Silver → Gold) por dominio de negocio |
| Google Maps (Geocoding + Directions) | Geocodificación de direcciones y cálculo de ruta óptima, siempre invocado desde el backend |
| PocketBase | Aloja el dataset histórico usado como calibración de los tableros; no forma parte del camino crítico de ningún flujo de negocio |

## 8. Fuera de alcance de esta especificación general

Esta especificación describe el sistema a alto nivel; el detalle de requisitos, reglas de negocio,
entradas, salidas, escenarios y criterios de aceptación vive en la especificación de cada
departamento — no se repite aquí.
