# Plan de rediseño visual — UrbanFleet TaxiFlow

Documento corto para tu revisión y aprobación antes de tocar código de producción (Fase de plan
del brief, `brief_rediseno_visual.md`). Se apoya en los hallazgos de
[`AUDITORIA_DISENO_ACTUAL.md`](AUDITORIA_DISENO_ACTUAL.md) (Fase 0) — no repito ahí lo ya
documentado, solo lo referencio.

## Dirección de marca — resumen en una frase

**Cooperativa de taxi urbano, no dashboard SaaS**: ámbar de taxi como acento de marca sobre una
base de neutros *cálidos* (crema/tinta), en vez de los grises azulados fríos actuales — porque el
problema real de identidad no es el ámbar (ya es un acento correcto), es que convive con una base
de neutros genérica que no tiene ninguna relación de temperatura con él. Esa desconexión entre
acento y neutros es, literalmente, la fórmula "gris neutro + un acento brillante" que el brief
señala como uno de los 3 esquemas genéricos por defecto.

## 1. Paleta — 6 valores hex núcleo, verificados con WCAG real (no a ojo)

| # | Rol | Hex | Por qué |
|---|---|---|---|
| 1 | Ámbar de marca (fondos, elementos grandes, rail activo) | `#f2a413` | Se mantiene igual al actual — es el acento con más continuidad y reconocimiento ya construido en el sistema; el problema nunca fue el tono, era dónde y cómo se usaba (ver auditoría §5.2) |
| 2 | Ámbar profundo (texto/enlaces sobre superficie clara — nuevo rol) | `#8a4b0a` | Resuelve el hallazgo de la auditoría: el ámbar de marca da 2.08:1 como texto (falla AA). Este tono profundo da **6.69:1** sobre `--color-surface` — pasa cómodo sin dejar de leerse como parte de la familia ámbar |
| 3 | Tinta cálida (texto principal, ancla, sidebar) | `#241a10` | Reemplaza el `#16202e` azulado actual — un casi-negro con matiz cálido en vez de frío, para que el ámbar se sienta parte de la misma familia de color, no un acento aislado sobre gris |
| 4 | Crema (fondo de página) | `#f7f1e6` | Reemplaza el `#eff2f6` gris azulado — 15.18:1 con la tinta cálida, holgado |
| 5 | Blanco cálido (superficie — tarjetas, tablas, inputs) | `#fffdf9` | Casi blanco puro pero con la misma temperatura que el resto — evita el contraste "gris frío + blanco puro + ámbar caliente" de 3 temperaturas distintas que tiene el sistema hoy |
| 6 | Ladrillo (peligro) | `#b23a1f` | Reemplaza `#d64545` — un rojo con temperatura cálida en vez de un rojo frío/genérico, para que el sistema completo respire una sola paleta térmica; **5.88:1** como texto, **5.97:1** como fondo con texto blanco |

### 1.1 Tokens semánticos derivados (para completar el sistema, no cuentan como "hex núcleo" nuevos)

Ajuste mínimo y dirigido — **solo** para resolver el hallazgo cuantificado de la auditoría (los 3
tonos de `Badge` fallan AA hoy contra su propio fondo tenue), sin tocar la paleta de gráficos
(`--chart-series-*`) ni los tonos de KPI (`--status-*`), que la propia auditoría confirma que deben
quedar fuera de esta ronda.

| Token | Valor nuevo | Contraste verificado |
|---|---|---|
| `--color-text-muted` | `#7a6a58` | 4.64:1 sobre `--color-bg`, 5.13:1 sobre `--color-surface` (el actual falla 4.30:1 sobre bg) |
| `--color-success` | `#15794f` | **4.56:1** sobre su propio badge (tinte 11%) — el actual daba 2.94:1 |
| `--color-warning` | `#9c5b0a` | **4.55:1** sobre su propio badge (tinte 11%) — deliberadamente más oscuro/ocre que el ámbar de marca (`#f2a413`) para que "advertencia" no se confunda visualmente con "acento de marca", un problema ya presente en el sistema actual donde ambos tonos son casi el mismo ámbar |
| `--color-danger` | `#b23a1f` (= hex núcleo 6) | 4.76:1 sobre su propio badge (tinte 14%) — el actual daba 3.62:1 |
| `--color-accent-contrast` | `#241a10` | 8.21:1 sobre el ámbar de marca — mejor que el 7.89:1 actual |
| `--color-danger-contrast` (**nuevo token**, no existe hoy) | `#ffffff` | Hallazgo de la auditoría §2: `Button` variant `danger` usa `#fff` fijo en vez de un token — se formaliza como token simétrico a `--color-accent-contrast` |

### 1.2 Modo oscuro — misma familia, roles invertidos (no una paleta nueva independiente)

El brief exige que ambos temas salgan del mismo sistema de variables. En vez de inventar neutros
oscuros distintos, invierto los roles dentro de la misma familia cálida — la tinta del modo claro
(`#241a10`) se convierte en la superficie del modo oscuro, y el crema del modo claro
(familia de `#f7f1e6`) se convierte en el texto del modo oscuro. Mismos materiales, luz distinta.

| Token (`[data-theme="dark"]`) | Valor | Contraste verificado |
|---|---|---|
| `--color-bg` | `#18110a` | — |
| `--color-surface` | `#241a10` (misma tinta que el texto del modo claro) | texto sobre esto: 14.54:1 |
| `--color-text` | `#f3ece0` | 15.92:1 sobre `--color-bg` |
| `--color-text-muted` | `#b9a793` | 8.02:1 sobre bg, 7.33:1 sobre surface |
| `--color-accent` | `#f2a413` (sin cambio) | 8.21:1 con `--color-accent-contrast` |
| `--color-accent-deep` (variante oscura, para texto ámbar sobre fondo oscuro) | `#f6c667` | 10.72:1 sobre surface oscura |
| `--color-danger` | `#ec8262` | 5.41:1 sobre surface; su badge (tinte 16%) da 4.93:1 |
| `--color-success` | `#5cc48a` | 7.9:1 sobre surface; su badge (tinte 16%) da 5.9:1 |
| `--color-warning` | `#e0a339` | 7.7:1 sobre surface; su badge (tinte 16%) da 5.68:1 |

Se mantiene la decisión ya tomada (documentada en la auditoría §2): oscuro sigue siendo **opción
explícita en Ajustes, nunca default** — ni en el token server-side (`preferencias/service.py`,
ya es `"claro"`) ni en `theme.ts`. Esta ronda no toca ese mecanismo, solo los valores de color que
consume.

## 2. Tipografía — 2 roles, no 3

- **Barlow se mantiene** como face de cuerpo/UI/datos — ya está bien integrada (peso 400-700,
  `tabular-nums` en cifras de `KpiCard`), migrar el sistema entero a una face nueva sería el mayor
  riesgo de regresión visual del rediseño para el menor beneficio de identidad.
- **Nueva face de carácter, solo para títulos y cifras grandes**: **Big Shoulders Display**
  (Google Fonts, pesos 700/900), reservada a: el `<h1>` de pantalla en `web-pasajero`/
  `web-conductor` (ej. "¿A dónde vamos?", "Tu viaje", "Mi turno"), el valor numérico grande de
  `KpiCard` (`--font-size-2xl`), y las cifras del Tablero Ejecutivo. Nunca en labels, botones,
  tablas ni texto de cuerpo — ahí sigue Barlow.
  - **Por qué esta y no una serif elegante o una geométrica tipo Space Grotesk**: Big Shoulders
    tiene herencia real de señalética urbana/civil (nace inspirada en la rotulación de Chicago) —
    encaja con "cooperativa de transporte urbano" sin caer en literalismo de taxi, y sin sonar a
    "startup tech" (geométricas tipo Space Grotesk) ni a "editorial de lujo" (una serif elegante,
    que además chocaría con el carácter de cooperativa de trabajo, no de marca premium).
- **Tercera face para datos/tablas — evaluada y descartada**: Barlow ya trae `tabular-nums` bien
  aplicado donde importa (`KpiCard`); introducir una face monoespaciada solo para tablas
  fragmentaría el sistema por una ganancia de legibilidad que la auditoría no encontró como
  problema real (las tablas actuales no tienen quejas de alineación reportadas). Un sistema sin
  este criterio explícito probablemente habría agregado una tercera face "porque el brief la
  sugiere" — se descarta a propósito por no resolver un problema real.

## 3. Concepto de layout

- **Jerarquía de 3 niveles del sidebar** (criterio 9, hallazgo de auditoría §3): cada grupo
  (ítems sueltos = operativo, "Panel Táctico", "Panel Estratégico") gana un indicador visual
  consistente además del texto de encabezado — la forma exacta (color de eyebrow, tamaño,
  espaciado entre grupos) se define en implementación con verificación real en navegador, pero el
  criterio ya decidido es: **más contraste de peso visual conforme se sube de nivel** (operativo
  más discreto, estratégico con más presencia), coherente con que estratégico es el nivel de
  menor frecuencia de uso pero mayor relevancia ejecutiva.
- **Tarjetas y superficies**: bordes y sombras se mantienen estructuralmente (`--radius-*`,
  `--shadow-*` sin cambio de valores, solo heredan los nuevos colores de superficie/borde) — el
  rediseño no reinventa la geometría de `Card`/`KpiCard`/`DetailPanel`, solo su paleta.
- **Estado de foco de teclado** (gap real de la auditoría §5.1): se define un estilo de foco
  propio (`:focus-visible`) usando el ámbar profundo (`#8a4b0a`) como anillo, verificado contra
  los 3 fondos del sistema (superficie clara, superficie oscura, sidebar) antes de darlo por
  bueno — hoy no existe ningún estilo de foco propio, se depende 100% del default del navegador.

## 4. Elemento "signature" — franja de ruta en el panel de solicitud del pasajero

**Un solo lugar**, como pide el brief. Candidato elegido: el panel "¿A dónde vamos?" de
`web-pasajero` (`App.tsx:412-414`), no el header del Tablero Ejecutivo — el pasajero es el
touchpoint de mayor frecuencia de todo el sistema (cada viaje empieza ahí), mientras que el
Tablero solo lo ve el rol `gerencia`, ocasionalmente. Prioricé alcance sobre exclusividad
ejecutiva.

**Qué es**: los 2 campos "Origen"/"Destino" (hoy 2 `TextField` apilados sin relación visual entre
sí) ganan un conector vertical punteado a su izquierda — un punto hueco en ámbar profundo para el
origen, una línea punteada, un punto sólido en tinta cálida para el destino. Es el mismo lenguaje
visual que cualquier usuario de una app de transporte ya reconoce (origen-línea-destino), así que
cumple doble función: identidad de marca Y un patrón ya conocido (criterio 15), no decoración
gratuita. Cero campos nuevos, cero pasos nuevos — es una capa puramente visual sobre los mismos 2
inputs que ya existen.

**Por qué no el Tablero Ejecutivo**: lo evalué explícitamente y lo descarté por alcance — es la
pantalla de menor frecuencia de uso de las 3 apps (un solo rol, uso ocasional). Queda como
candidato futuro si se quisiera un segundo momento de identidad más adelante, pero el brief pide
uno solo para esta ronda.

## 5. Autocrítica — qué se descartó por genérico

- **Paleta cálida crema+ámbar+tinta**: es, honestamente, la resolución más obvia del problema que
  describe el brief — cualquier sistema con este mismo encargo probablemente llegaría a "neutros
  cálidos en vez de fríos". Lo que no es genérico es la ejecución: cada valor de esta paleta salió
  de una medición WCAG real contra su combinación de uso real (no contra blanco puro como atajo),
  incluido el hallazgo no pedido por el brief de que los 3 tonos de `Badge` fallaban contraste — un
  sistema sin ese nivel de auditoría previa probablemente habría cambiado los hex "a ojo" y dejado
  el mismo problema de contraste con colores distintos.
- **Segunda familia de color "cooperativa/confianza" (verde-azulado) — considerada y descartada**:
  pensé en agregar un 7º hex, un verde-azulado como nota de "comunidad/cooperativa", pero lo
  descarté por 2 razones concretas: (1) es el tropo genérico de "verde = confianza" de cualquier
  producto SaaS sin dirección propia — exactamente el tipo de decisión no específica que el brief
  pide evitar; (2) competiría visualmente con `--status-good`, que la propia auditoría confirma
  como paleta reservada y fuera de alcance de este rediseño.
- **Serif elegante para títulos — considerada y descartada**: ver §2, se explica ahí por qué
  Big Shoulders Display es la opción con razón específica (herencia de señalética urbana) en vez
  de genérica ("se ve elegante").
- **Ícono de taxi / patrón de cuadros tipo ajedrez — nunca considerados en serio**: el brief los
  descarta explícitamente y estoy de acuerdo — ninguna propuesta de esta sección los usa.

## 6. Qué NO cambia en esta ronda (alcance explícito)

- Arquitectura de componentes de `shared-ui` — ninguno se reescribe, solo consumen tokens nuevos.
- `--chart-series-1..8` y `--status-good/warning/serious/critical` (paleta de gráficos/KPI,
  validada por la skill `dataviz`) — permanecen exactamente igual.
- Mecanismo de tema claro/oscuro (`theme.ts`, `data-theme`, fuente de verdad en
  `preferencias_usuario`) — se reutiliza tal cual, solo cambian los valores de color que resuelve.
- Ningún flujo, paso nuevo, ni confirmación nueva (criterios 8 y 10 del brief) — los gaps de
  confirmación documentados en la auditoría §5.4 quedan solo documentados, no implementados.
- `FuenteBadge` (etiqueta "Simple · MongoDB" / "Compuesto · ClickHouse") — se mantiene igual, ya
  fue una decisión deliberada de una ronda anterior.

## Próximos pasos

Este plan queda a la espera de tu aprobación. Con luz verde, la implementación sigue el orden que
pide el brief: (1) tokens compartidos en `shared-ui` primero, con verificación visual real en
navegador antes de tocar ningún portal — empezando por viewport angosto en `web-pasajero`/
`web-conductor` (uso real mayoritario) y confirmando después en escritorio; (2) cada portal después,
por fases, con verificación en Chrome y Firefox en cada una — nunca "compiló, listo".
