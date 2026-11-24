# Especificación: Inteligencia de Negocio y Plataforma (Nivel Táctico)

> Documento retroactivo. Fuente principal: `AUDITORIA_FUNCIONAL_TACTICO.md` §7, verificada contra
> `backend/src/plataforma/`.

## 1. Objetivo

Dar visibilidad de si el proceso automático de carga de datos (Airflow) está sano — porque si falla,
todos los demás dashboards tácticos y estratégicos empiezan a mostrar información vieja sin que nadie
lo note.

## 2. Contexto

Este es el único departamento táctico cuya "operación" real es automática (el proceso de datos
corre solo) — el rol humano es de **monitoreo**, no de operación diaria. Por eso, a diferencia de
los otros 6 departamentos, no tiene un módulo operativo propio con acción humana diaria (ver la nota
de alcance en `000-sistema-general/spec.md` §5).

## 3. Actores

- **`responsable_plataforma`** — único actor con acceso.

## 4. Requisitos funcionales

### RF-TPL-001 — KPIs de salud del proceso de datos
Corridas OK hoy, % de registros rechazados, hora de la última corrida (fecha/hora real, no un valor
fijo).

### RF-TPL-002 — % de registros rechazados por dominio (compuesto)
Los 7 dominios reales (captación, cumplimiento, finanzas, flota, mantenimiento, viajes, histórico).

### RF-TPL-003 — Tabla de corridas por dominio
Servida desde ClickHouse (tabla `corridas`, real) — la colección Mongo que la spec original pedía
nunca se construyó, el seguimiento vive en ClickHouse por diseño desde el origen.

### RF-TPL-004 — Filtro por dominio

## 5-6. Requisitos no funcionales / Reglas de negocio

Ninguno propio adicional.

## 7-8. Entradas / Salidas

Filtro de dominio → KPIs + gráfico + tabla de corridas.

## 9. Estados posibles

Corrida (`corridas.estado`): `OK` / `WARN` (registros rechazados sobre el umbral, sin ser un fallo
total) / fallida.

## 10. Escenarios

### Escenario 1: Corrida con advertencia real
Dado que un dominio tuvo un % de rechazo alto en una corrida real
Cuando se abre la tabla de corridas
Entonces esa fila aparece en estado `WARN`, con su porcentaje real — evidencia de que el sistema de
calidad de datos realmente descarta registros problemáticos, no acepta todo ciegamente.

## 11. Criterios de aceptación

### CA-TPL-001
"Última corrida" muestra una fecha/hora real, verificable contra la corrida más reciente en
ClickHouse.

## 12. Dependencias

- **004-transversal/auditoria-y-trazabilidad** — comparte el mismo mecanismo de proceso de datos
  que alimenta el catálogo de informes.
- **Los 6 departamentos operativos** — cada uno es la fuente real de un dominio de datos.

## 13. Fuera de alcance

- **KPI "Capacitación"** — quitado de la interfaz, no existe ningún dominio de capacitación en el
  sistema.
- **Colección Mongo `corridas_etl`** que la spec original pedía — nunca se construyó; el
  seguimiento real vive en ClickHouse, decisión de diseño desde el origen, no un incumplimiento.
