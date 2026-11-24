# Auditoría del sistema de diseño actual — Fase 0 del rediseño visual

Fase 0 del brief de rediseño visual (`brief_rediseno_visual.md`). Inventario del estado real del
sistema de diseño de UrbanFleet TaxiFlow, leído directamente del código — no de lo que CLAUDE.md
documenta como intención, aunque coincide en casi todo. Objetivo: saber qué ya está bien resuelto
estructuralmente (para no tocarlo) y qué es realmente identidad visual (lo que el rediseño debe
cambiar), más un inventario honesto de gaps de accesibilidad/prevención de errores que el brief
pide *documentar*, no arreglar, en esta ronda.

## 1. Tokens de diseño actuales

Un solo archivo fuente: [`apps/shared-ui/src/tokens.css`](apps/shared-ui/src/tokens.css). Las 3
apps lo importan literal (`@import "@urbanflet/shared-ui/src/tokens.css";`) en su propio
`index.css` y no declaran overrides propios — confirmado leyendo los 3 archivos
(`web-pasajero/src/index.css`, `web-conductor/src/index.css`, `web-interno/src/index.css`): los 2
últimos incluso tienen un comentario explícito documentando que un override de `--color-accent`
existió antes y se quitó a propósito. Este es el mayor acierto estructural del sistema actual — no
hay fragmentación entre portales, así que el rediseño solo necesita tocar un archivo de tokens para
propagarse a los 3.

### 1.1 Paleta actual (tema claro, `:root`)

| Token | Valor | Uso |
|---|---|---|
| `--color-bg` | `#eff2f6` | Fondo de página |
| `--color-surface` | `#ffffff` | Tarjetas, tablas, inputs |
| `--color-surface-muted` | `#f4f6f9` | Fondos secundarios (celdas vacías de mapa de calor, etc.) |
| `--color-text` | `#16202e` | Texto principal |
| `--color-text-muted` | `#647388` | Labels, texto secundario |
| `--color-border` / `--color-border-soft` | `#e1e7ef` / `#edf1f6` | Bordes |
| `--color-accent` | `#f2a413` | Ámbar/dorado — botón primario, rail de nav activo, enlaces de acción |
| `--color-accent-contrast` | `#16202e` | Texto sobre fondo de acento |
| `--color-danger` / `-bg` | `#d64545` / `rgba(…,0.14)` | Badges/botones de peligro |
| `--color-success` / `-bg` | `#1f9d6b` / `rgba(…,0.14)` | Badges de éxito |
| `--color-warning` / `-bg` | `#d98a0b` / `rgba(…,0.16)` | Badges de advertencia |
| `--status-good/warning/serious/critical` | `#1f9d6b` / `#d98a0b` / `#c2570e` / `#d64545` | Semántica de KPI — **reservada, nunca reusada** en series de gráfico (regla explícita de la skill `dataviz`, ya documentada en CLAUDE.md) |
| `--chart-series-1..8` | 8 hex fijos, orden validado | Paleta categórica de gráficos — mismo criterio de reserva |
| `--radius-sm/md/lg` | 8/10/12px | — |
| `--space-1..6` | 6/10/14/18/24/30px | — |
| `--font-sans` | `"Barlow", system-ui, …` | Única familia tipográfica del sistema — **un solo rol**, no hay una face distinta para títulos vs. cuerpo vs. datos todavía |
| `--font-size-xs..2xl` | 12/13/14/16/22/26px | — |
| `--control-height` | 38px | Altura fija de botón/input/select en todo el sistema |
| `--color-sidebar-*` | fondo `#101a26`, fijo | Sidebar del `AppShell` — **no reactivo al tema claro/oscuro por diseño**, ver §2 |

**Hallazgo relevante para el brief**: contrario a la premisa de que "el fondo oscuro es el
default", el tema `:root` (sin ningún atributo `data-theme`) YA es el claro (`--color-bg:
#eff2f6`). El bloque oscuro vive exclusivamente bajo el selector `:root[data-theme="dark"]` (ver
§2). El respaldo server-side (`backend/src/preferencias/service.py::DEFAULTS`) también fija
`"tema": "claro"` para toda cuenta nueva. La percepción de "oscuro por defecto" probablemente viene
de que el propio dueño de producto tiene el toggle personal en oscuro (usado activamente en varias
sesiones de verificación previas, según el historial de CLAUDE.md) — no de un default real del
sistema. Esto no cambia el pedido del brief (mantener oscuro como opción explícita, nunca
default), solo aclara que técnicamente ya se cumple; lo que sí cambia con el rediseño es *qué*
paleta clara es esa por defecto.

### 1.2 Un solo rol tipográfico — gap real frente al brief

El brief pide "tipografía para 2+ roles (una face con carácter para títulos, una complementaria
para cuerpo, una utilitaria para datos/tablas si hace falta)". Hoy hay **una sola familia** (Barlow)
para todo — títulos, cuerpo, tablas, KPIs numéricos. La jerarquía se logra solo con tamaño/peso
(`--font-size-2xl`/700 para el valor de un KPI, `--font-size-xs`/600 uppercase para su etiqueta),
nunca con una face distinta. Confirmado que sí hay uso de `fontVariantNumeric: "tabular-nums"` en
cifras (`KpiCard.tsx:97`, `DataTable` no lo usa) — una decisión tipográfica real ya tomada para
alinear dígitos en columnas, vale la pena conservarla si se introduce una face de datos nueva.

## 2. Mecanismo de tema claro/oscuro

Confirmado un mecanismo real y ya generalizable, no un caso aislado:

- **Fuente de verdad**: `preferencias_usuario` (Mongo, vía `GET/PATCH /preferencias`) — el tema NO
  se decide por `prefers-color-scheme` del sistema operativo solo, aunque el `@media
  (prefers-color-scheme: dark)` sigue siendo relevante para el primer render de un visitante sin
  sesión (no verificado en este documento, fuera de alcance de un vistazo de tokens).
- **Aplicación**: [`apps/shared-ui/src/theme.ts`](apps/shared-ui/src/theme.ts) — dos funciones,
  `aplicarTemaInicial()` (llamada sincrónica en `main.tsx` de las 3 apps, antes del primer render,
  leyendo el último valor cacheado en `localStorage` para no parpadear en claro) y `aplicarTema()`
  (aplica + cachea el valor real que devuelve el backend). Ambas solo tocan
  `document.documentElement.dataset.theme`.
- **CSS**: `:root` = claro (sin atributo), `:root[data-theme="dark"]` = oscuro — un solo bloque de
  overrides, todos los demás selectores del sistema referencian variables, nunca un hex directo
  (confirmado por inspección de los 20 componentes de `shared-ui/src/components/`, con una sola
  excepción real: `Button.tsx` variant `danger` usa `color: "#fff"` fijo en vez de un token de
  "texto sobre fondo de peligro" — inconsistente con `--color-accent-contrast`, que sí existe para
  el caso del acento. Vale la pena que el rediseño introduzca el token simétrico, p.ej.
  `--color-danger-contrast`, si el nuevo color de peligro no es blanco-compatible).
- **Sidebar**: deliberadamente **no** reactiva al tema — mismo fondo oscuro fijo en claro y en
  oscuro (documentado en el comentario de `tokens.css:80-82`). Esto es una decisión de diseño ya
  tomada, no un olvido — el rediseño puede mantenerla o revisarla, pero debe ser una decisión
  explícita, no un accidente de qué tokens se tocan.

### 2.1 `color-mix()` — base real y reusable, no un caso aislado

El brief pregunta específicamente por esto. Confirmado: **sí hay una base reusable**, no solo el
mapa de calor de Rentabilidad. [`apps/shared-ui/src/components/charts/HeatMap.tsx`](apps/shared-ui/src/components/charts/HeatMap.tsx)
es un componente genérico (`HeatMap<T>`, sin acoplarse a ningún dominio) que calcula intensidad
0-100% y la resuelve así:

```css
background: color-mix(in srgb, var(--chart-series-1) ${pct}%, var(--color-surface));
```

Es decir, mezcla el tono de serie 1 con la superficie del tema activo — se adapta solo a claro/
oscuro porque nunca referencia un hex fijo, solo variables. Esto ya es el patrón correcto para
cualquier escala secuencial de intensidad que el rediseño quiera introducir (p.ej. si el acento de
marca nuevo necesita una escala de tinte/sombra derivada, `color-mix()` sobre el token es el
mecanismo ya probado, no hay que inventar uno). Es el único uso de `color-mix()` en todo
`shared-ui` — confirmado por grep, no hay un segundo caso independiente; el hallazgo real es que
**es una base genérica lista para reutilizar**, no que ya se use en más de un lugar.

## 3. Inventario de componentes de `shared-ui`

`apps/shared-ui/src/components/` — 25 archivos. Los agrupo por lo que el rediseño necesita saber
de cada uno: **si ya está bien resuelto estructuralmente** (el rediseño solo cambia tokens que ya
consume) vs. **qué decisión de identidad visual falta**.

| Componente | Rol | Ya resuelto (no tocar estructura) | Decisión de identidad pendiente |
|---|---|---|---|
| `Button.tsx` | Botón, 3 variantes (`primary`/`secondary`/`danger`) | Altura fija, radio, estados disabled/loading | `danger` usa `#fff` fijo en vez de token — ver §2. Ningún estado de foco propio (ver §5). |
| `TextField.tsx` / `Select.tsx` / `TextArea.tsx` | Campos de formulario | Label + control + hint/error, mismo alto que Button, sistema de `rangeHint` automático para límites numéricos | Ninguna — visualmente mínimos, heredan tokens limpio |
| `Badge.tsx` | Chip de estado (4 tonos) | Fondo suave + texto semántico (ya migrado de píldora sólida) | **Contraste real insuficiente** en los 3 tonos de color — ver §5.2, hallazgo cuantificado |
| `Card.tsx` | Contenedor de superficie | — | No inspeccionado en detalle, patrón simple |
| `KpiCard.tsx` / `KpiRow` | Tarjeta de indicador — jerarquía tipográfica (etiqueta 13px/500 uppercase → valor 26px/700), tono de color semántico opcional, `descripcion`/`interpretacion` opcionales, drill-down clicable (`onClick` → `KpiDetalleModal`) | Estructura y jerarquía ya sólidas — es el componente más maduro del sistema | Es candidato fuerte para llevar identidad de marca (ver Fase de plan) |
| `KpiDetalleModal.tsx` | Modal de solo lectura sobre una lista filtrable, mismo chrome que `DetailPanel` | — | Comparte el mismo gap de foco/escape que `DetailPanel`, ver §5 |
| `DetailPanel.tsx` / `DetailField` | Modal de detalle (consulta/edición/nuevo), usado en ~35+ pantallas | `role="dialog"`, `aria-modal="true"`, chip de modo con el mismo tratamiento que Badge | **Sin trampa de foco ni cierre con Escape** — ver §5.1 |
| `DataTable.tsx` | Tabla con `Column<T>[]`, ancho de columna opcional, alto máximo con scroll interno | Encabezado uppercase, hover de fila, soporte de columnas anchas sin romper layout | Sin estrategia de colapso a "tarjetas" en viewport angosto — usa scroll horizontal (`overflowX: auto`) en cualquier ancho, ver §5.3 |
| `Pagination.tsx` | Paginación de `DataTable` | No inspeccionado en detalle | — |
| `ActionBar.tsx` | 5 botones fijos (Nuevo/Actualizar/Eliminar/Buscar/Salir), mismo orden siempre, `disabled+title` si no aplica | Ya fuerza `Eliminar` a `variant="danger"` siempre — el patrón de "peligro reservado" (criterio 12 del brief) ya está aplicado acá | — |
| `AppShell.tsx` / `.css` | Sidebar + header + contenido, mobile-first (sidebar oculta bajo 900px, botón hamburguesa) | Responsive ya resuelto con un solo breakpoint limpio; agrupación de nav items por `group` | **Jerarquía de 3 niveles (operativo/táctico/estratégico) es solo textual** — cada grupo es un encabezado uppercase idéntico visualmente a los demás, sin distinción de nivel más allá del texto de la etiqueta. El brief (criterio 9) pide reforzar esto — es un candidato real de trabajo del rediseño, no solo cosmético |
| `DashboardLayout.tsx` (`DashboardZ`/`DashboardF`) | Grid de 2 columnas (Z: 1fr/1fr, F: 320px/1fr) para los 17 dashboards tácticos/estratégicos | Ya diferenciado y medido con `getComputedStyle` en sesiones previas (documentado en CLAUDE.md §5.1/§13) | — |
| `FuenteBadge.tsx` | Etiqueta "Simple · MongoDB" / "Compuesto · ClickHouse" | Recurso de transparencia técnica deliberado — el brief anterior de unificación de lenguaje (CLAUDE.md §17.1) ya decidió **no tocarlo** | Mantener esa decisión en este rediseño también |
| `ReadOnlyGate.tsx` | Hook + componente para pantallas de configuración sensible bloqueadas por defecto | — | — |
| `UserPicker.tsx` | Selector de usuarios con búsqueda | — | — |
| `NotificacionesBell.tsx` | Campana con contador, único consumidor real del slot `AppShell.headerActions` | — | Usa emoji `🔔` como ícono — ver §5.4 |
| `AjustesPropios.tsx` / `CentroAyuda.tsx` / `PerfilPropio.tsx` | Pantallas de autoservicio compartidas por las 3 apps | — | — |
| `charts/CategoryBarChart.tsx` / `TrendLineChart.tsx` | Wrappers de recharts, paleta categórica fija | Reglas ya establecidas (barras=comparación, líneas=tendencia), documentadas en CLAUDE.md §5.1 | — |
| `charts/HeatMap.tsx` | Mapa de calor genérico (grid CSS, sin librería) | Ver §2.1 — base de `color-mix()` ya reusable | — |
| `charts/WaterfallChart.tsx` / `BulletBarChart.tsx` | Cascada (bruto→comisión→neto) y barra con banda de umbral | Nuevos, del plan de `DIVERSIFICACION_VISUALIZACIONES.md` (documento de propuesta, sin actualizar todavía en CLAUDE.md — confirmado que existen como archivos reales) | No inspeccionados en detalle en esta pasada — mismo criterio de tokens que el resto de `charts/`, revisar en la fase de implementación si introducen algún hex fijo |

**Conclusión de la Fase 0 sobre componentes**: la arquitectura ya es sólida y reutilizable — el
rediseño no necesita reescribir ningún componente desde cero, solo (a) tokens nuevos que estos ya
consumen, (b) 2-3 ajustes puntuales de consistencia (`Button` danger-contrast, `AppShell` jerarquía
de 3 niveles) y (c) decidir dónde vive el elemento "signature" del criterio 14.

## 4. Iconografía actual

No hay librería de íconos instalada (confirmado — sin dependencia nueva en `package.json` de
`shared-ui` más allá de `recharts`). El sistema usa:

- **Texto en botones**, nunca ícono solo, para acciones de `ActionBar` (Buscar/Eliminar/etc.) —
  ya cumple el criterio 15 (no reinventar con íconos donde el texto ya es claro).
- **Emoji sueltos** para 3 casos puntuales: `☰` (menú hamburguesa, `AppShell.tsx:180`), `🔔`
  (campana de notificaciones, `NotificacionesBell.tsx`), `☆`/`★` (favoritos/calificación, en
  `web-pasajero`). Sin SVG propio en ningún lado.

Esto es una decisión pendiente real para el plan: si el rediseño introduce una identidad visual
más cuidada, los emoji del sistema (que rinden distinto según SO/navegador) probablemente deban
convertirse en SVG inline propios — sin agregar una librería de íconos nueva, coherente con el
criterio del proyecto de evitar dependencias no justificadas.

## 5. Gaps documentados para los criterios 3 (accesibilidad) y 10 (prevención de errores)

El brief pide auditar y *documentar* estos gaps en la Fase 0, sin implementarlos todavía.

### 5.1 Foco de teclado y modales — sin trampa de foco, sin cierre por Escape

`DetailPanel.tsx` y `KpiDetalleModal.tsx` (el patrón modal reusado en ~35+ pantallas) no
implementan **focus trap** (el foco de Tab puede salirse del modal hacia el contenido de fondo) ni
**cierre con la tecla Escape** — solo se cierran con el botón "Salir". Tampoco hay
`ref`+`.focus()` que mueva el foco inicial al abrir el modal. Ningún componente de `shared-ui`
define un estilo de foco propio (`:focus`/`:focus-visible`) — confirmado por grep, cero
coincidencias en todo el paquete — lo que significa que el anillo de foco depende 100% del default
del navegador. Esto normalmente sigue siendo visible sobre los controles estándar de este sistema
(no hay ningún `outline: none` en el código), pero no está *verificado* contra el nuevo acento de
marca ni diseñado a propósito — el brief pide verificarlo explícitamente, así que el plan debe
incluir un estado de foco deliberado, no asumir que el default alcanza.

### 5.2 Contraste — hallazgo cuantificado, no solo la advertencia del brief sobre el amarillo

Calculado con la fórmula de luminancia relativa WCAG (no "a ojo"), sobre los tokens reales de
`tokens.css`:

| Combinación real del sistema | Ratio | Umbral AA aplicable | Resultado |
|---|---|---|---|
| `--color-accent` (`#f2a413`) como texto sobre `--color-surface` blanco (ej. enlace "Ver detalle →" de `KpiCard`) | **2.08:1** | 4.5:1 (texto normal) | ❌ Falla, confirma la advertencia del brief |
| `--color-accent` como fondo + `--color-accent-contrast` (`#16202e`) como texto (botón primario) | 7.89:1 | 4.5:1 | ✅ Pasa holgado |
| `--color-text-muted` (`#647388`) sobre `--color-bg` (`#eff2f6`, fondo de página) | 4.30:1 | 4.5:1 | ❌ Falla por poco |
| `--color-text-muted` sobre `--color-surface` (blanco puro, tarjetas/tablas) | 4.83:1 | 4.5:1 | ✅ Pasa por poco |
| Badge tono `exito`: `--color-success` texto sobre `--color-success-bg` resuelto | 2.94:1 | 4.5:1 (texto ≤13px, aplica aunque sea 600) | ❌ Falla |
| Badge tono `advertencia`: `--color-warning` texto sobre `--color-warning-bg` resuelto | 2.37:1 | 4.5:1 | ❌ Falla, el peor caso |
| Badge tono `peligro`: `--color-danger` texto sobre `--color-danger-bg` resuelto | 3.62:1 | 4.5:1 | ❌ Falla |

**Hallazgo no anticipado por el brief**: el problema de contraste no es solo el amarillo como
texto — **los 3 tonos de `Badge`** (usado en decenas de pantallas para el estado de viajes/
órdenes/solicitudes/liquidaciones) fallan AA para texto normal en su combinación real de
texto-sobre-fondo-propio, no solo contra blanco puro. Esto es más grave que el caso aislado del
amarillo porque `Badge` es uno de los componentes de mayor reuso del sistema. El plan de rediseño
debe verificar contraste de CUALQUIER color semántico nuevo contra su propio fondo tenue resuelto
(no solo contra blanco), con el mismo método cuantificado de esta sección — "se ve bien" no es
suficiente evidencia.

### 5.3 `DataTable` en viewport angosto — sin estrategia de colapso

`DataTable.tsx` envuelve la tabla en un contenedor `overflowX: auto` — en un viewport angosto, una
tabla con muchas columnas simplemente se desplaza horizontalmente, no colapsa a un layout de
tarjetas apiladas. Esto es aceptable para `web-interno` (uso mayoritario en escritorio, per el
propio brief), pero **no hay ninguna tabla en `web-pasajero`/`web-conductor`** — confirmado, esos 2
portales no usan `DataTable` en absoluto (son de flujo de 1-2 toques, sin listados tabulares) — así
que este gap en la práctica solo afecta a `web-interno`, donde el criterio 5 del brief es más
tolerante ("no debe romperse en tablet" es el estándar, no celular). No es un bloqueante para el
rediseño, pero si el plan toca `web-interno` en tablet, verificar con datos reales (una tabla con
6+ columnas) en vez de asumir que el scroll horizontal es suficiente.

### 5.4 Confirmaciones antes de acciones irreversibles — inventario real

Grep de `window.confirm`/patrones de confirmación en las 3 apps: **cero usos de `window.confirm`
en todo el sistema**. El único mecanismo de doble confirmación real es el de **Gobernanza de
Datos → Anonimizar** (`GobernanzaDatos.tsx`, Módulo 8.2 de admin_sistema): exige escribir la
palabra exacta "ANONIMIZAR" en un campo de texto antes de habilitar el botón — no un diálogo
sí/no, un gate de texto literal.

Para el resto de acciones que el brief nombra como ejemplo:

| Acción irreversible | Mecanismo actual | ¿Es una confirmación real? |
|---|---|---|
| Cancelar viaje (pasajero/conductor) | Requiere abrir un sub-panel y elegir un motivo obligatorio antes de que el botón "Confirmar cancelación" se habilite | Parcial — el motivo obligatorio actúa como fricción/gate, pero no hay un mensaje explícito de "esto no se puede deshacer" |
| Anular orden de mantenimiento (`Mantenimiento.tsx`) | Mismo patrón: sub-panel con motivo obligatorio antes de habilitar "Anular" | Parcial, mismo criterio que cancelar viaje |
| Anonimizar cuenta (Gobernanza de datos) | Texto exacto "ANONIMIZAR" requerido | ✅ Confirmación real y explícita |
| Cerrar sesión (`AppShell.tsx:150-168`, botón "Cerrar sesión") | **Ninguna** — `onClick={logout}` directo, sin verificar si hay un `DetailPanel` abierto en modo edición/nuevo con cambios sin guardar | ❌ Sin confirmación de ningún tipo |
| Suspender/dar de baja usuario, revocar credencial de integración, eliminar en general (`ActionBar` "Eliminar") | Varía por pantalla — algunas piden motivo (ver Usuarios, Cumplimiento), `ActionBar` en sí no impone ningún gate genérico | Inconsistente entre pantallas, no hay un patrón único |

**Conclusión del criterio 10**: el patrón dominante del sistema ya es "motivo obligatorio como
fricción antes de la acción", no "diálogo sí/no" — es una decisión de diseño ya asentada, no un
vacío total. El único hueco limpio y sin ninguna fricción es **cerrar sesión con estado sin
guardar**. Documentado para que el usuario decida si vale la pena proponerlo como cambio de UX
aparte (fuera de esta ronda, por restricción explícita del brief) — no se implementa nada acá.

## 6. Resumen para la Fase de plan

Lo que el plan de diseño (`PLAN_REDISENO_VISUAL.md`) debe resolver, con esta auditoría como base:

1. **Paleta nueva** que resuelva el contraste del amarillo como texto Y de los 3 tonos de `Badge`
   contra su propio fondo — no solo copiar el criterio actual de "tinte al 14-16% sobre blanco".
2. **Segundo rol tipográfico** (o justificar por qué uno solo sigue siendo la decisión correcta).
3. **Reforzar visualmente los 3 niveles del sidebar** (operativo/táctico/estratégico), hoy solo
   distinguidos por texto de grupo.
4. **Token de contraste simétrico para `danger`** (`--color-danger-contrast`), mismo patrón que
   `--color-accent-contrast`.
5. **Un elemento "signature" bien elegido** — 2 candidatos observados con potencial real por estar
   hoy completamente genéricos: el panel "¿A dónde vamos?" de `web-pasajero`
   (`App.tsx:412-414`, tarjeta flotante sin ningún tratamiento especial) y el header de
   `TableroEjecutivo.tsx:120` (`<h2>` plano). Ninguno de los dos tiene identidad visual hoy — son
   candidatos limpios, no hay que competir con nada ya diseñado ahí.
6. **Decisión explícita sobre íconos** — mantener emoji o introducir un set SVG propio mínimo.
7. **Estado de foco de teclado deliberado**, verificado contra la paleta nueva.

Lo que el plan NO necesita resolver (ya está bien y no se toca): arquitectura de componentes,
mecanismo de tema claro/oscuro, estructura de `DashboardLayout` Z/F, patrón `ActionBar`/
`DetailPanel`/`WorkPanel`, paleta de gráficos (`--chart-series-*`/`--status-*`, ya validada por la
skill `dataviz` y fuera de alcance de un rediseño de identidad).
