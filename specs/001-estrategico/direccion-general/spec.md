# Especificación: Dirección General (Nivel Estratégico)

> Documento retroactivo — describe el sistema tal como funciona hoy. Fuente principal:
> `AUDITORIA_FUNCIONAL_ESTRATEGICO.md` (verificado en navegador con la cuenta real `gerencia`),
> `CLAUDE.md` §12-13 (Fases 3-4 del bloque estratégico), y lectura directa de
> `backend/src/estrategico/` donde hizo falta precisión adicional.

## 1. Objetivo

Dar a la dirección de la cooperativa (`gerencia`) una vista consolidada del estado del negocio
completo — crecimiento, confiabilidad del servicio, costo de flota, calidad de los datos,
rentabilidad, integridad financiera, cumplimiento normativo y gobernanza — para detectar en
segundos qué área necesita atención, sin tener que revisar cada departamento por separado.

## 2. Contexto

Los niveles operativo y táctico ya dan visibilidad departamento por departamento, pero ningún rol
individual tenía antes una vista que cruzara los 6 departamentos a la vez. Este módulo existe para
cerrar esa brecha: un "Tablero Ejecutivo" con una cifra por área, y 9 paneles de detalle (uno o dos
por departamento, más 2 que cruzan varios departamentos a la vez — Rentabilidad y Gobernanza).

## 3. Actores

- **`gerencia`** — único rol que ve el Tablero Ejecutivo consolidado y los 2 paneles exclusivos
  (Rentabilidad y Demanda; Gobernanza de Datos y Seguridad).
- **`admin_captacion`, `coordinador_operaciones`, `jefe_mantenimiento`, `admin_financiero`,
  `supervisor_cumplimiento`, `responsable_plataforma`** — cada uno ve además el/los panel(es)
  estratégico(s) de su propio departamento (vía OR-gate con `gerencia`), pero **nunca** el Tablero
  Ejecutivo consolidado ni Rentabilidad ni Gobernanza — verificado explícitamente con la cuenta
  `staff-verificacion` (7 roles tácticos acumulados, sin `gerencia`): ve 6 de los 9 paneles, no ve
  los 3 exclusivos.

## 4. Requisitos funcionales

### RF-EST-001 — Tablero Ejecutivo Consolidado
El sistema debe mostrar, en una sola pantalla, una tarjeta por cada una de las 8 áreas (Crecimiento,
Confiabilidad del servicio, Costo de flota, Capacidades y plataforma, Rentabilidad, Integridad
financiera, Cumplimiento normativo, Gobernanza de datos), cada una con su cifra headline actual y un
enlace "Ver detalle" al panel completo correspondiente.

### RF-EST-002 — Consistencia entre Tablero y detalle
Cada cifra del Tablero Ejecutivo debe ser exactamente la misma que muestra el panel de detalle de esa
área — nunca un cálculo recalculado por separado. Verificado en navegador: 98.4%/87.8%/100.0%/1.9%/
80.0%/100.0%/53.5%/142 coinciden en ambos lugares.

### RF-EST-003 — Panel de Crecimiento Estratégico
Debe mostrar conversión de altas (cuentas activas, no primer-viaje — ver glosario), retención a 90
días, y altas de socios del período, más tendencia de altas/solicitudes y conversión por canal.

### RF-EST-004 — Panel de Confiabilidad y Disponibilidad del Servicio
Debe mostrar tiempo de asignación promedio, tasa de cancelación, cancelaciones del período, % de
flota activa promedio, y la franja con menor cobertura — más tendencias en el tiempo y desglose por
franja diurna/nocturna.

### RF-EST-005 — Panel de Estado y Costo de Flota
Debe mostrar % de cumplimiento del plan preventivo, costo del último período y costo acumulado —
más tendencia de costo/cumplimiento y una tabla de vehículos candidatos a reemplazo (sin
kilometraje, dato no disponible en este panel).

### RF-EST-006 — Panel de Capacidades y Plataforma
Debe mostrar % global de registros rechazados por el proceso de datos, el dominio más afectado,
corridas OK y corridas fallidas — más tendencia de calidad de datos y desglose por los 7 dominios.

### RF-EST-007 — Panel de Rentabilidad y Demanda
Debe mostrar margen promedio, la franja menos rentable con su margen, y la recaudación del último
trimestre como aproximación de demanda de largo plazo — más una matriz de rentabilidad por mes y
franja. Exclusivo de `gerencia`.

### RF-EST-008 — Panel de Integridad Financiera
Debe mostrar % conciliado, tasa de discrepancias, y margen de comisión promedio — más tendencia,
composición del margen, y comparación entre años (con aviso explícito cuando el rango mezcla el
dataset histórico 2021 con operación real 2026).

### RF-EST-009 — Panel de Cumplimiento Normativo
Debe mostrar % de documentación vigente, cantidad de documentos vencidos (con detalle navegable por
clic), y el tipo de documento más expuesto — más tendencia por tipo.

### RF-EST-010 — Panel de Gobernanza de Datos y Seguridad
Debe mostrar cantidad de eventos administrativos, accesos denegados, y alertas de seguridad — más la
bitácora completa filtrable por acción/resultado. Exclusivo de `gerencia`. Patrón F (la tabla domina
la pantalla).

### RF-EST-011 — Panel de Desempeño de Conductores (estratégico)
Debe mostrar cuántos socios entran en la ventana de análisis, viajes completados e ingreso neto
agregados, con un top 10 por viajes y detalle por socio/trimestre. Añadido en una ronda posterior a
los 9 originales de la spec — hoy son 9 paneles + Tablero, no 8.

### RF-EST-012 — Filtros por panel
Cada panel debe ofrecer al menos un filtro real (ventana temporal, canal, franja, tipo de documento,
dominio, año, acción/resultado) que dispare un recálculo real al aplicarse — no un adorno visual.

### RF-EST-013 — Navegación cruzada sin recargar
Un clic en "Ver detalle" (desde el Tablero) o en un KPI con drill-down debe llevar al panel/lista
correspondiente sin recargar la página completa (`location.href` intacto).

## 5. Requisitos no funcionales

### RNF-EST-001 — RBAC verificado explícitamente
El acceso a cada panel se define por un objeto de dependencia de rol propio, nunca heredado por
convención. Rentabilidad y Gobernanza son los únicos 2 exclusivos de `gerencia` sin ningún OR-gate.

### RNF-EST-002 — Nunca Mongo directo, salvo 1 excepción documentada
Los 8 paneles de detalle (salvo Gobernanza) leen exclusivamente de tablas `rpt_*` en ClickHouse
(agregadas por Airflow), nunca de una consulta directa a la colección operativa. La única excepción
es Gobernanza (bitácora, `bitacora` en Mongo) porque la propia spec original declara esa fuente
explícitamente — no hay ninguna `rpt_*` de bitácora.

### RNF-EST-003 — Honestidad de dato faltante
Cada limitación real (zona sin resolver, kilometraje no disponible, demanda por mes sin fuente,
cobertura parcial de canal, dataset mixto) viaja en el campo `metadata` de la respuesta y se muestra
como advertencia explícita en pantalla — nunca se omite ni se aproxima en silencio.

## 6. Reglas de negocio

### RN-EST-001
El Tablero Ejecutivo es una sola respuesta con los 8 headlines (no 8 llamadas separadas del
frontend) — cada bloque va en su propio `try`: una fuente vacía o ClickHouse caído deja esa tarjeta
en `disponible=false` sin tumbar el resto del tablero.

### RN-EST-002
El margen de rentabilidad (RF-EST-007) prorratea recaudación/comisión por la participación en
demanda de cada franja, pero el costo de mantenimiento se prorratea por participación en
**capacidad** (flota activa) — son dos bases distintas a propósito: recaudación y comisión escalan
con los viajes atendidos, el costo de mantenimiento escala con la exposición del activo (un vehículo
en servicio se desgasta esté ocupado o no).

### RN-EST-003
El campo `seccion` de cada tarjeta del Tablero (que define a qué panel navega "Ver detalle") lo
define el backend, no un mapeo manual en el frontend — evita que el enlace y el destino real diverjan
con el tiempo.

## 7. Entradas

- Filtros por panel: ventana temporal (meses/cortes), canal, franja horaria, tipo de documento,
  dominio, año, acción, resultado (según el panel).
- Clic en "Ver detalle" de una tarjeta del Tablero.
- Clic en un KPI con drill-down (ej. "Documentos vencidos" en Cumplimiento Normativo).

## 8. Salidas

- Cifras headline, tendencias temporales, tablas/matrices de detalle por panel.
- Banderas de limitación (`zona_disponible`, `km_disponible`, `tasa_cancelacion_disponible`,
  `demanda_disponible`, `canal_cobertura_parcial`, `capacitacion_disponible`, `dataset_mixto`) —
  cada una con su nota visible en pantalla cuando es `false`.
- Navegación al panel de detalle correspondiente, o al panel táctico relacionado cuando existe.

## 9. Estados posibles

No aplica — este nivel no gestiona una entidad con máquina de estados propia; agrega datos de
entidades cuyo estado se gestiona en el nivel operativo (ver `003-operativo/*`).

## 10. Escenarios

### Escenario 1: Gerencia revisa el estado general de la cooperativa
Dado que el usuario tiene el rol `gerencia`
Cuando entra a "Panel Estratégico" → "Tablero Ejecutivo"
Entonces ve las 8 tarjetas con su cifra real y el aviso "8 de 8 indicadores con dato publicado"
Y cada cifra coincide exactamente con la de su panel de detalle.

### Escenario 2: Bajar del resumen al detalle sin perder contexto
Dado que gerencia está viendo el Tablero Ejecutivo
Cuando hace clic en "Ver detalle" de la tarjeta "Rentabilidad"
Entonces el sistema muestra el panel completo de Rentabilidad y Demanda
Y no recarga la página.

### Escenario 3: Un rol departamental abre su panel, no el Tablero
Dado que el usuario tiene el rol `supervisor_cumplimiento` (sin `gerencia`)
Cuando busca el Tablero Ejecutivo o Rentabilidad en el menú
Entonces esas opciones no aparecen
Y sí ve "Cumplimiento Normativo" en su menú de Panel Estratégico.

### Escenario 4: Un dato no existe, no se inventa
Dado que el sistema no tiene ninguna fuente que registre viajes solicitados por mes de forma
consolidable
Cuando gerencia abre "Crecimiento Estratégico"
Entonces el KPI de crecimiento de demanda no aparece en pantalla (se quitó de la interfaz, no
muestra "—" indefinidamente)
Y ningún otro número del panel se ve afectado.

### Escenario 5: Drill-down real desde un KPI
Dado que gerencia está en "Cumplimiento Normativo"
Cuando hace clic en la tarjeta "Documentos vencidos"
Entonces se abre un modal con el listado real de documentos vencidos, en la misma pantalla
Y puede filtrar ese listado por tipo de documento sin afectar el filtro general del panel.

## 11. Criterios de aceptación

Reusa `PLAN_DE_PRUEBAS.md`:

- **TU-08** (Gerencia entiende un indicador estratégico, no solo lo encuentra): criterio de éxito
  con 2 partes — navegación en menos de 3 minutos, y explicación correcta con palabras propias del
  significado real del indicador (no solo repetir el número).
- **PUS-04**: "Ver detalle" desde el Tablero Ejecutivo lleva al panel completo sin recargar.
- **PUS-05**: un KPI con drill-down abre su detalle en la misma pantalla.
- **PUS-03**: los 3 niveles organizacionales se distinguen visualmente en el menú, no solo por
  texto.

### CA-EST-001
El sistema muestra el Tablero Ejecutivo con las 8 tarjetas y su cifra real a la cuenta `gerencia`.

### CA-EST-002
Una cuenta sin rol `gerencia` no ve el Tablero Ejecutivo, Rentabilidad ni Gobernanza en su menú, y
un intento directo por URL/API es rechazado (403).

### CA-EST-003
Cada cifra del Tablero coincide exactamente con la de su panel de detalle correspondiente.

### CA-EST-004
Un filtro real (ej. franja, canal, ventana temporal) aplicado en cualquiera de los 9 paneles
dispara una nueva consulta al backend, verificable en el registro de red.

## 12. Dependencias

- **002-tactico/** (todos los departamentos) — los paneles estratégicos consumen las mismas tablas
  `rpt_*` que ya alimentan los dashboards tácticos, sin agregación adicional propia en la mayoría de
  los casos.
- **003-operativo/** (todos los departamentos) — fuente última de los datos operativos que Airflow
  agrega.
- **004-transversal/auditoria-y-trazabilidad** — el panel de Gobernanza lee directamente de la
  bitácora transversal, no de una tabla `rpt_*` propia.

## 13. Fuera de alcance

- **Filtro por zona geográfica** (Confiabilidad, Rentabilidad): deshabilitado con nota — el dato de
  zona nunca se resuelve en los viajes reales (gap heredado del nivel operativo).
- **Kilometraje en "candidatos a reemplazo"** (Costo de Flota): no disponible en este panel — el
  kilometraje solo vive en la colección operativa `ordenes`, prohibida como fuente directa para este
  nivel (RNF-EST-002).
- **Tasa de cancelación por fórmula original**: corregida de raíz en agosto 2026 (antes daba 100%
  fijo por un error de agregación en `rpt_tasa_cancelacion`) — ya **no** es una limitación, se deja
  registrado como discrepancia histórica resuelta, no como exclusión vigente.
- **Demanda de viajes por mes de forma consolidable**: no existe ninguna fuente — el KPI
  correspondiente se quitó de la interfaz en vez de mostrar "—" indefinidamente.
- **Avance de capacitación por área**: no existe ningún dominio de capacitación en el sistema — el
  KPI se quitó de la interfaz.
- **Corrección de la cobertura de `canal`**: 49% de usuarios sin canal asignado (deuda de datos
  heredada), afecta el desglose por canal de Crecimiento — declarado con la bandera
  `canal_cobertura_parcial`, no corregido en esta ronda ni en las anteriores por decisión explícita
  de no reabrirlo sin pedido nuevo.
