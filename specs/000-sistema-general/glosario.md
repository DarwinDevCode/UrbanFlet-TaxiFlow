# Glosario — UrbanFleet TaxiFlow

Términos usados de forma consistente en toda esta documentación retroactiva, con su significado
real verificado (no el que "sonaría lógico" — donde el nombre en pantalla es engañoso, se aclara).

## Términos de negocio

| Término | Significado real |
|---|---|
| **Socio / socio conductor** | Un `conductor` ya aprobado por Captación, con vehículo habilitado. Antes de la aprobación es un "postulante". |
| **Cooperativa** | La organización dueña del sistema — no es un actor con cuenta propia, es el contexto de negocio. |
| **Franja** | División horaria tarifaria: `DIURNA` (05:00-22:00) / `NOCTURNA`. No confundir con los buckets de 6h (`00-06`/`06-12`/`12-18`/`18-24`) que usa el panel de Flota — son dos taxonomías de "franja" distintas que **no se cruzan** en ningún panel (ver nota en `002-tactico/operaciones-y-despacho`). |
| **Zona** | Dimensión geográfica prevista en el diseño original pero **nunca resuelta en los datos reales** (`viajes.zona_origen_id`/`zona_destino_id` quedan siempre `null`). Cualquier filtro de zona en pantalla aparece deshabilitado con una nota — gap conocido, no un botón roto. |
| **Dominio** (nivel táctico/estratégico de Plataforma) | Cada uno de los 6-7 procesos de datos que corre Airflow (captación, cumplimiento, finanzas, flota, mantenimiento, viajes, histórico NYC) — no confundir con "dominio" en sentido de arquitectura de software. |
| **Conversión de altas** (Crecimiento estratégico) | **Nombre engañoso, verificado contra el cálculo real**: no mide si un conductor ya dio su primer viaje — mide qué fracción de las cuentas del sistema (conductores y pasajeros) sigue habilitada (no suspendida ni dada de baja). Ver `AUDITORIA_FUNCIONAL_ESTRATEGICO.md` §1. |
| **Backlog consciente** | Frase usada en `CLAUDE.md` para una funcionalidad evaluada y descartada a propósito (no un olvido). Cada módulo de esta documentación la traduce a su sección "Fuera de alcance" con la razón real. |

## Siglas de casos de uso de la spec original

| Sigla | Significado |
|---|---|
| `CU-O##` | Caso de Uso Operativo, de `specs/nivel-operativo/*.md` |
| `CU-T##` | Caso de Uso Táctico, de `specs/nivel-tactico/*.md` |
| `CU-E##` | Caso de Uso Estratégico, de `specs/nivel-estrategico/nivel_estrategico.md` |
| `OT#.#` | Informe u objetivo táctico dentro de un `CU-T##` |
| `OE#` | Objetivo Estratégico dentro de `nivel_estrategico.md` |

Estas siglas se citan en esta documentación **solo cuando ayudan a rastrear la spec original** —
nunca como el único nombre de un requisito (cada RF tiene además una descripción en español llano).

## Roles del sistema (13, `core/rbac.py::ROLES`)

Ver tabla completa en `spec.md` §4. Nombres exactos, tal como aparecen en el código y en la base de
datos — nunca una variante genérica ("administrador", "supervisor") que no exista como valor real.

## Estados de las entidades con máquina de estados propia

| Entidad | Estados reales |
|---|---|
| Viaje (`viajes.estado`) | `PROGRAMADO`, `SOLICITADO`, `OFERTADO`, `ASIGNADO`, `EN_CAMINO`, `EN_CURSO`, `FINALIZADO`, `PAGADO`, `CANCELADO`, `SIN_CONDUCTOR` |
| Solicitud de conductor (`solicitudes.estado`) | `BORRADOR`, `ENVIADA`, `EN_VERIFICACION`, `OBSERVADA`, `APROBADA`, `RECHAZADA`, `EXPIRADA` |
| Orden de mantenimiento (`ordenes.estado`) | `ABIERTA`, `EN_TALLER`, `ESPERANDO_REPUESTO`, `CERRADA`, `ANULADA` |
| Reporte de falla (`reportes_falla.estado`) | `PENDIENTE`, `CONVERTIDO_A_ORDEN`, `DESCARTADO` |
| Liquidación (`liquidaciones.estado`) | `EMITIDA`, `OBSERVADA`, `APROBADA`, `PAGADA` |
| Cuenta de usuario (`usuarios.estado`) | `ACTIVO`, `SUSPENDIDO`, `BAJA` |

Detalle de transiciones válidas y quién las dispara: en el `spec.md` del módulo dueño de cada
entidad (sección "Estados posibles").

## Patrones técnicos citados en varios módulos

| Patrón | Qué es |
|---|---|
| `FuenteBadge` | Etiqueta "Simple · MongoDB" / "Compuesto · ClickHouse" junto a cada gráfico/tabla táctico o estratégico — indica si el dato viene de una consulta directa o de una agregación pre-calculada por Airflow. Es información real, no decorativa. |
| Patrón Z / Patrón F | Los dos layouts de dashboard usados en táctico/estratégico. Z: 2 columnas iguales (gráfico + lista). F: columna angosta fija + lista dominante — reservado a los paneles donde la tabla es el elemento principal (Auditoría e Integraciones a nivel táctico; Rentabilidad y Gobernanza a nivel estratégico). |
| WorkPanel | Patrón de pantalla CRUD operativa: Card de búsqueda → ActionBar fija (Nuevo/Actualizar/Eliminar/Buscar/Salir) → DataTable + Pagination → DetailPanel con modo (consulta/edición/nuevo). |
