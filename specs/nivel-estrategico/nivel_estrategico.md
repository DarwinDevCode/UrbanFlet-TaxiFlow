# Especificación — Nivel Estratégico

Fuente de referencia (no definitiva, ver nota): `UrbanFleet-Documentacion-Organizacional.md`,
sección 4.1. Responsables: Junta de Socios y Gerencia General.

## 0. Nota sobre la fuente

El documento organizacional define 6 objetivos estratégicos (OE1-OE6) y 5 casos de uso (CU-E01 a
CU-E05), pero — a diferencia de la spec táctica — no especifica qué informes compuestos concretos
corresponden a cada uno. Esta spec completa ese vacío, siguiendo el mismo criterio que ya se aplicó
al construir `specs/nivel-tactico/`: cada informe debe responder una pregunta de negocio concreta,
y su fuente/transformación debe quedar explícita antes de construir.

## 1. Objetivos estratégicos y casos de uso

| Código | Objetivo estratégico |
|---|---|
| OE1 | Crecimiento sostenido de la base de socios conductores y de la demanda de pasajeros |
| OE2 | Continuidad y calidad del servicio de transporte en toda la zona de operación |
| OE3 | Capacidades propias: plataforma tecnológica sostenible y personas formadas |
| OE4 | Decisiones de demanda, tarifa y rentabilidad basadas en datos de la propia operación |
| OE5 | Integridad de la recaudación y transparencia en la liquidación a los socios |
| OE6 | Gobernanza de los datos y cumplimiento de la normativa de transporte |

| CU | Actor | Objetivo(s) |
|---|---|---|
| CU-E01 — Consultar el tablero de indicadores de la cooperativa | Gerente General | Todos (OE1-OE6) |
| CU-E02 — Analizar la rentabilidad por zona y franja horaria | Gerente General | OE4 |
| CU-E03 — Definir la política tarifaria | Junta de Socios | OE4 |
| CU-E04 — Auditar la integridad de la recaudación | Junta de Socios | OE5 |
| CU-E05 — Supervisar la gobernanza de datos y los accesos | Gerente General | OE6 |

## 2. Regla de nivel — solo informes compuestos, con acceso al nivel táctico

Ningún informe estratégico se consulta directo de MongoDB. Todos requieren agregación —
generalmente una segunda capa de agregación **sobre** las vistas `rpt_*` tácticas ya publicadas, no
sobre los hechos Gold directamente (evita reprocesar lo que el nivel táctico ya resolvió).

El tablero estratégico (CU-E01) debe incluir enlaces de navegación hacia los 9 dashboards tácticos
correspondientes, para bajar del resumen al detalle departamental sin salir del sistema.

## 3. Estructura de dashboards — análisis objetivo por objetivo

Regla aplicada: un objetivo se divide en más de un dashboard solo cuando agrupa decisiones de
naturaleza genuinamente distinta (audiencia, urgencia o tipo de decisión diferente) — nunca por
buscar simetría con el nivel táctico. Resultado: **8 dashboards por objetivo + 1 tablero ejecutivo
consolidado = 9**.

### 3.1. OE1 — Crecimiento (1 dashboard)

**Panel de Crecimiento Estratégico**
- **Objetivo:** OE1.
- **Propósito:** confirmar si la cooperativa crece de forma sostenida, tanto en oferta (socios
  conductores) como en demanda (pasajeros/viajes) — ambos lados del mismo motor de crecimiento,
  por eso caben en un solo dashboard sin perder claridad.
- **Información:** tendencia de altas de socios y de pasajeros; retención a 90 días; conversión de
  onboarding, en ventana de varios meses (no solo el mes actual, a diferencia de lo táctico).
- **KPIs:** conversión de onboarding (%, tendencia), retención a 90 días (%), altas de socios/mes,
  crecimiento de demanda (viajes solicitados/mes, variación %).
- **Visualizaciones:** 4 tarjetas KPI arriba; gráfico de líneas de tendencia (altas + demanda) a la
  izquierda; tabla de conversión por canal (consolidada) a la derecha.
- **Patrón:** Z — resumen antes que detalle, mismo criterio que el nivel táctico.
- **Usuarios:** `gerencia`.
- **Decisiones que habilita:** hacia dónde reforzar la captación, si el crecimiento de oferta
  sigue el ritmo de la demanda o va desalineado.
- **Fuente:** `rpt_conversion_captacion` + `rpt_altas_retencion` (Captación), en tendencia extendida.

### 3.2. OE2 — Continuidad y calidad del servicio (2 dashboards)

Se divide porque mezcla dos preguntas de negocio distintas: *"¿servimos bien ahora mismo?"*
(tiempo real, urgente) vs. *"¿el activo físico es rentable de mantener?"* (inversión, no urgente).

**a) Panel de Confiabilidad y Disponibilidad del Servicio**
- **Objetivo:** OE2 (dimensión despacho + flota).
- **Propósito:** confirmar si el servicio se sostiene con calidad y cobertura suficiente.
- **Información:** tiempo de asignación consolidado, tasa de cancelación, % de flota activa, en
  tendencia de varios meses.
- **KPIs:** tiempo de asignación promedio (tendencia), tasa de cancelación (%, tendencia), % de
  flota activa promedio, franjas/zonas con menor cobertura (si `zona_*` se resuelve — ver 3.4).
- **Visualizaciones:** KPIs arriba; gráfico de tendencia de tiempo de asignación + cancelación;
  lista de franjas con menor disponibilidad.
- **Patrón:** Z.
- **Usuarios:** `gerencia`.
- **Decisiones que habilita:** si la cobertura actual sostiene la calidad de servicio prometida en
  la visión de la cooperativa, o si hace falta reforzar flota en zonas/franjas específicas.
- **Fuente:** `rpt_tiempo_asignacion` + `rpt_tasa_cancelacion` (Despacho) + `rpt_flota_activa_franja`
  (Flota).

**b) Panel de Estado y Costo de Flota**
- **Objetivo:** OE2 (dimensión mantenimiento/activo).
- **Propósito:** decidir sobre inversión y reemplazo de vehículos con datos de costo real.
- **Información:** cumplimiento del plan preventivo consolidado, costo total de flota por periodo,
  vehículos candidatos a reemplazo.
- **KPIs:** % cumplimiento preventivo (tendencia), costo total de mantenimiento/mes, top vehículos
  por costo acumulado.
- **Visualizaciones:** KPIs arriba; gráfico de costo total por mes; tabla de vehículos candidatos a
  reemplazo (costo vs. km recorridos).
- **Patrón:** Z.
- **Usuarios:** `gerencia`, `junta_socios` (o `gerencia` si ese rol no existe como cuenta separada —
  ver nota de roles en la Sección 6).
- **Decisiones que habilita:** presupuesto de mantenimiento del próximo periodo, reemplazo de
  unidades específicas.
- **Fuente:** `rpt_cumplimiento_plan_preventivo` + `rpt_costo_mantenimiento_vehiculo`.

### 3.3. OE3 — Capacidades propias: plataforma y personas (1 dashboard)

**Panel de Capacidades y Plataforma**
- **Objetivo:** OE3.
- **Propósito:** confirmar que la plataforma es estable y que el personal está preparado para
  usarla — ambos son "capacidad instalada", cohesivos en un solo panel.
- **Información:** calidad de datos del pipeline (% cuarentena), avance de capacitación (si el
  backlog ya se resolvió — de lo contrario, se documenta como no disponible, igual que en lo
  táctico).
- **KPIs:** % de cuarentena por dominio (tendencia), corridas OK vs. fallidas del periodo, avance
  de capacitación (si aplica).
- **Visualizaciones:** KPIs arriba; gráfico de tendencia de % de cuarentena por dominio.
- **Patrón:** Z.
- **Usuarios:** `gerencia`, `responsable_plataforma` (lectura).
- **Decisiones que habilita:** priorizar estabilización de un dominio de datos específico, invertir
  en capacitación si el rezago es alto.
- **Fuente:** `rpt_cuarentena_dominio` (Plataforma).

### 3.4. OE4 — Demanda, tarifa y rentabilidad (1 dashboard, patrón F)

**Panel de Rentabilidad y Demanda**
- **Objetivo:** OE4 (CU-E02 y CU-E03 comparten este panel — la decisión de tarifa necesita ver la
  misma matriz de rentabilidad que la analiza).
- **Propósito:** herramienta de **análisis comparativo**, no de resumen de estado — es la razón por
  la que este dashboard usa patrón F en vez de Z, igual que ya se justificó para "Auditoría e
  Integraciones" en lo táctico (herramienta de exploración, no tablero de estado).
- **Información:** matriz de rentabilidad (margen) por zona y franja horaria; historial de demanda
  de largo plazo para respaldar decisiones de ajuste tarifario.
- **KPIs:** margen promedio por franja (y por zona si se resuelve el gap), franja/zona menos
  rentable, tendencia de demanda trimestral.
- **Visualizaciones:** KPIs como franja superior delgada; tabla/matriz dominante (zona × franja o
  solo franja mientras el gap no se resuelva) con margen; gráfico de tendencia de demanda de largo
  plazo al costado.
- **Patrón:** F.
- **Usuarios:** `gerencia`, `junta_socios`.
- **Decisiones que habilita:** ajustar la tarifa por franja/zona, decidir dónde reforzar flota por
  rentabilidad (no solo por demanda).
- **Fuente:** **nuevo** — margen = recaudación − comisión − costo de mantenimiento prorrateado, por
  zona y franja. **Bloqueado parcialmente**: depende de `zona_origen_id`/`zona_destino_id` en
  viajes (gap ya documentado, Módulo 3 de Administración). Mientras no se resuelva, se construye
  solo por franja, sin dimensión de zona, documentado como limitación explícita en la UI — mismo
  criterio ya aplicado a otros gaps de zona en el proyecto.

### 3.5. OE5 — Integridad de recaudación (1 dashboard)

**Panel de Integridad Financiera**
- **Objetivo:** OE5 (CU-E04).
- **Propósito:** confirmar que la conciliación al 100% se sostiene de forma consistente en el
  tiempo, y que la liquidación a los socios es transparente.
- **Información:** % de conciliación histórico, margen de comisión consolidado, comparación
  interanual si hay suficiente histórico.
- **KPIs:** % conciliado (tendencia), tasa de discrepancias (tendencia), margen de comisión
  promedio.
- **Visualizaciones:** KPIs arriba; gráfico de tendencia de % conciliado; tabla de periodos con
  discrepancia relevante.
- **Patrón:** Z.
- **Usuarios:** `junta_socios`, `gerencia`.
- **Decisiones que habilita:** auditar si la integridad de la recaudación se mantiene, decidir
  intervención si la tasa de discrepancias sube de forma sostenida.
- **Fuente:** `rpt_tasa_discrepancias` + `rpt_margen_comision` (Financiero), en tendencia extendida.

### 3.6. OE6 — Gobernanza y cumplimiento normativo (2 dashboards)

Se divide porque cumplimiento normativo (documentación de flota/conductores) y gobernanza de
datos/seguridad (accesos, auditoría administrativa) sirven audiencias y decisiones distintas —
mismo criterio ya aplicado en el nivel táctico al dividir Cumplimiento Regulatorio en 2.

**a) Panel de Cumplimiento Normativo**
- **Objetivo:** OE6 (dimensión regulatoria).
- **Propósito:** confirmar que la cooperativa opera sin exposición legal por documentación vencida.
- **Información:** % de documentación vigente por tipo, tendencia mensual.
- **KPIs:** % vigente (tendencia), documentos vencidos (conteo), tendencia de mejora/deterioro.
- **Visualizaciones:** KPIs arriba; gráfico de tendencia de vigencia documental.
- **Patrón:** Z.
- **Usuarios:** `gerencia`, `supervisor_cumplimiento` (lectura).
- **Decisiones que habilita:** priorizar campañas de renovación documental si la tendencia empeora.
- **Fuente:** `rpt_documentacion_vigente` (Cumplimiento).

**b) Panel de Gobernanza de Datos y Seguridad**
- **Objetivo:** OE6 (dimensión gobernanza/seguridad, CU-E05).
- **Propósito:** herramienta de supervisión de accesos y eventos administrativos sensibles — es de
  investigación, no de resumen, por eso usa patrón F (mismo criterio que Auditoría en lo táctico).
- **Información:** eventos de auditoría administrativa consolidados (cambios de rol, de política de
  seguridad, de parámetros críticos), alertas de seguridad del periodo, accesos denegados.
- **KPIs:** eventos administrativos del periodo, alertas de seguridad activas, accesos denegados
  (tendencia).
- **Visualizaciones:** KPIs como franja superior; tabla dominante de eventos administrativos
  consolidados (reutiliza el filtro ya construido en Administración, agregado a nivel estratégico).
- **Patrón:** F.
- **Usuarios:** `gerencia` (exclusivo — no se comparte con `admin_sistema`, que ya tiene su propia
  vista operativa de esto en Administración).
- **Decisiones que habilita:** confirmar que la gobernanza de datos y el control de accesos se
  sostienen; escalar si se detecta un patrón preocupante de accesos denegados o cambios sensibles.
- **Fuente:** eventos de auditoría administrativa ya construidos (Módulo 6.1 de Administración),
  agregados a nivel de tendencia.

## 4. Tablero ejecutivo consolidado (CU-E01)

Un dashboard adicional, distinto de los 8 anteriores, que consolida un KPI headline por cada uno de
los 6 objetivos (algunos objetivos aportan más de un KPI headline si tienen 2 dashboards detrás) en
tarjetas de resumen, cada una con un enlace "Ver detalle" que navega al dashboard estratégico
correspondiente — y desde ahí, según ya prevé la Sección 2, al dashboard táctico departamental.

- **KPIs headline** (uno por dashboard de la Sección 3, 8 en total): crecimiento, confiabilidad de
  servicio, costo de flota, capacidades/plataforma, rentabilidad, integridad financiera,
  cumplimiento normativo, gobernanza de datos.
- **Visualizaciones:** grid de 8 tarjetas (KPI + mini-tendencia + enlace), sin gráfico propio — es
  un índice de navegación, no un dashboard analítico en sí mismo.
- **Patrón:** Z — fila(s) de tarjetas homogéneas, lectura horizontal, sin bloque de detalle propio
  que agregar debajo.
- **Usuarios:** `gerencia`, `junta_socios`.

## 5. KPIs compartidos entre dashboards (intencional, no duplicado por descuido)

| KPI | Dashboards donde aparece | Por qué se comparte |
|---|---|---|
| % de flota activa | Confiabilidad y Disponibilidad (detalle) + Tablero Ejecutivo (headline) | Mismo dato, distinto nivel de detalle — el tablero solo necesita el número, el panel de detalle necesita la tendencia y el desglose |
| Margen de comisión | Rentabilidad y Demanda (driver de decisión tarifaria) + Integridad Financiera (indicador de transparencia) | Mismo dato, dos preguntas de negocio distintas: uno lo usa para decidir tarifa, el otro para auditar consistencia — no es duplicación, es reutilización con propósito distinto |
| % documentación vigente | Cumplimiento Normativo (detalle) + Tablero Ejecutivo (headline) | Mismo patrón que flota activa |

Ningún otro KPI se repite entre dashboards — cada uno de los demás pertenece exclusivamente al
dashboard que le corresponde, para evitar inflar paneles con indicadores que no aportan una
pregunta de negocio propia en ese contexto.

## 6. Nota de roles pendiente de confirmar

Esta spec usa `junta_socios` como rol distinto de `gerencia` en varios dashboards (siguiendo la
distinción de actores que ya hace el documento organizacional entre Junta de Socios y Gerente
General). **Verificar contra el código real si `junta_socios` existe como rol o si el sistema solo
tiene `gerencia`** — de no existir, decidir si se crea el rol nuevo o si todos estos dashboards
quedan bajo `gerencia` único, documentando esa simplificación como decisión consciente.

## 5. Infraestructura ETL — generación de Parquet versionado

Requisito nuevo de arquitectura, aplicable tanto a los DAGs existentes como al DAG estratégico
nuevo: además de cargar a ClickHouse (como ya hace el pipeline), cada corrida debe escribir
archivos Parquet versionados en carpetas separadas por etapa:

```
datos/
  extraccion/<dominio>/<fecha_logica>/<ts_corrida>.parquet   (Bronce crudo)
  transformacion/<dominio>/<fecha_logica>/<ts_corrida>.parquet   (Silver validado)
  carga/<dominio>/<fecha_logica>/<ts_corrida>.parquet   (Gold agregado)
```

Estos archivos cumplen doble función: insumo intermedio del pipeline y respaldo/control de
versiones de los datos procesados en cada corrida (independiente del respaldo completo de base de
datos ya construido en el Módulo 7 de Administración — este es un respaldo por corrida ETL, más
granular).

No reemplaza las tablas de ClickHouse ya construidas — se agrega como paso adicional dentro de
cada etapa de los DAGs ya existentes (Bronce→Silver→Gold), sin duplicar la lógica de agregación.
