# Plan de paleta — Segundo rediseño visual (Fase 1)

Documento corto para tu revisión y aprobación antes de tocar código, mismo formato que
[`PLAN_REDISENO_VISUAL.md`](PLAN_REDISENO_VISUAL.md) de la ronda anterior. Se apoya en los
hallazgos de [`AUDITORIA_REDISENO_V2.md`](AUDITORIA_REDISENO_V2.md) (Fase 0) — no repite lo ya
resuelto ahí.

**Alcance de este documento**: solo la paleta y el sidebar configurable, que es lo que pediste
aprobar antes de seguir. El resto de la Fase 2 (reemplazo de emojis, limpieza de texto de
desarrollador, migración a componentes compartidos) no necesita aprobación de paleta — se ejecuta
con los criterios ya fijados en la auditoría, salvo los 3 puntos que dejé marcados ahí como "a
confirmar" (estrellas de calificación, "% error API"/"endpoint", "GPS spoofing").

## 1. Qué se mantiene tal cual (continuidad con la ronda anterior)

- **La familia cálida base** (crema `#f7f1e6` / superficie `#fffdf9` / tinta `#241a10`) — no se
  toca. El problema que resuelve esta ronda no es la base, es la falta de presencia del ámbar y la
  rigidez del sidebar.
- **`--chart-series-1..8` y `--status-good/warning/serious/critical`** — paleta de gráficos y KPI,
  validada por la skill `dataviz`, fuera de alcance otra vez (mismo criterio ya aceptado).
- **`--color-danger`/`--color-success`/`--color-warning`** y sus fondos — ya pasan WCAG real desde
  la ronda anterior, no hay ningún hallazgo nuevo que los toque.
- **El mecanismo de tema claro/oscuro** (`theme.ts`, `data-theme`, preferencia por cuenta) — se
  reutiliza tal cual.
- **La franja de ruta signature** del panel "¿A dónde vamos?" — sigue siendo el único elemento
  signature del sistema, esta ronda no agrega un segundo.

## 2. El amarillo — más presencia, mismo tono

El logo nuevo confirma que el ámbar de marca actual (`#f2a413`) ya es la familia correcta — no
cambio el hex. Lo que cambio es **dónde y cuánto se usa**, sin convertirlo en fondo de página (eso
sí saturaría la interfaz):

| Dónde | Hoy | Propuesta |
|---|---|---|
| Botón primario, rail de ítem activo, indicadores de KPI | `--color-accent` sólido | Sin cambio — ya es correcto |
| Encabezado de las 3 apps (`header`) | Fondo neutro, sin acento | Se mantiene neutro (el header aparece en las ~50 pantallas del sistema — pintarlo de ámbar en todas saturaría exactamente lo que pediste evitar). En su lugar, el logo/marca dentro del header gana una **zona propia** con fondo `--color-accent` (badge cuadrado alrededor del ícono, no toda la barra) |
| Las 3 pantallas de login | Tarjeta neutra sobre fondo `--color-bg` | Fondo de página con un lavado suave de ámbar detrás de la tarjeta (`--color-accent` al 8-10% sobre `--color-bg`, verificado que no baja el contraste de ningún texto porque el texto vive dentro de la tarjeta blanca, no sobre el lavado) — es la pantalla de menor frecuencia de uso y mayor impacto de marca, mismo criterio que ya se usó para elegir dónde poner la franja signature |
| Sidebar, opción "Ámbar" (nueva, ver §3) | No existía | Uso deliberadamente más prominente, pero opt-in — quien lo prefiere neutro se queda con "Claro" |
| Estados positivos / datos | `--status-good` (verde) | **Sin cambio.** "Positivo" en datos (éxito, vigente, aprobado) sigue siendo el verde ya validado — no lo reemplazo por ámbar. Interpreto tu pedido de "estados positivos" como presencia de marca en zonas de énfasis (activo, seleccionado, principal), no como un cambio de semántica de datos. Si querías lo segundo, decímelo y lo rediseño. |

## 3. Sidebar configurable — 4 opciones predefinidas, claro por defecto

**Default: "Claro" en los 3 portales**, sin importar el tema claro/oscuro del contenido — es un
ajuste de cuenta independiente del tema, mismo patrón ya usado para tamaño de texto. No hay selector
de color libre: 4 combinaciones ya armadas y verificadas, cada una con su propio juego completo de
tokens (fondo, texto, texto secundario, borde, hover, fondo activo, texto activo, **color del rail
del ítem activo**).

| Opción | Fondo | Texto | Texto secundario | Fondo activo/hover | Color del rail activo | Contraste texto/fondo |
|---|---|---|---|---|---|---|
| **Claro** (default) | `#efe4d0` | `#241a10` | `#6b5c48` | `#dccb9e` | `#8a4b0a` (ámbar profundo) | **13.56:1** |
| **Ámbar** | `#fbe3ad` | `#241a10` | `#6b5c48` | `#f6cf78` | `#8a4b0a` | **13.57:1** |
| **Oscuro** *(el fijo de la ronda anterior, ahora opcional)* | `#1c140c` | `#d9c9b4` | `#96826a` | `#2c2015` | `#f2a413` (ámbar brillante) | **11.23:1** *(sin cambio, ya validado)* |
| **Grafito** | `#24211d` | `#e8e4da` | `#a89f8f` | `#34302a` | `#f2a413` | **12.62:1** |

**Por qué el color del rail cambia según la opción, y no es un detalle menor**: verifiqué la
fórmula WCAG real y el ámbar brillante (`#f2a413`) da solo **1.65:1** contra los 2 fondos claros
(Claro/Ámbar) — falla el mínimo de 3:1 para un indicador no textual. Contra los 2 fondos oscuros
(Oscuro/Grafito) sigue siendo el correcto, ya validado. Por eso el rail y el foco de teclado del
sidebar (el hallazgo de la Fase 0 §1) quedan atados a la opción elegida, no son un solo valor fijo
como hoy.

**Por qué estas 4 y no otras**: las 4 se quedan dentro de la misma familia cálida (crema/tinta/ámbar)
que ya es la identidad del sistema — evalué y descarté un tono azul/gris frío tipo "sidebar
corporativo genérico" por la misma razón que la ronda anterior descartó un segundo color
"confianza" verde-azulado: sería el tropo genérico de cualquier panel admin sin dirección propia.
Grafito es la única que se aleja del marrón cálido — la incluyo como alternativa neutra para quien
prefiere un sidebar oscuro sin la connotación "café/tinta" del original, pero sigue leyendo como
parte del mismo sistema (mismo ámbar de rail, mismo radio, misma tipografía).

## 4. Color nuevo: informativo

El sistema hoy tiene éxito/advertencia/peligro/neutral pero ningún tono "informativo" — lo pediste
cubrir explícitamente y es un hueco real (confirmado revisando `Badge.tsx`/`KpiCard.tsx`: los tipos
de tono no incluyen ninguna variante informativa). Se usa para el `Alert` compartido nuevo (Fase 0
§4) cuando el mensaje no es ni error ni advertencia ni éxito, solo un dato a tener en cuenta.

Mantuve la temperatura general (nada de azul saturado tipo SaaS) usando un azul-pizarra desaturado,
que igual se distingue con claridad de los otros 4 tonos:

| Token | Claro | Oscuro |
|---|---|---|
| `--color-info` | `#3d6b99` | `#7fb3e0` |
| `--color-info-bg` (tinte 14%/16%, mismo patrón que los otros 4) | `rgba(61, 107, 153, 0.14)` | `rgba(127, 179, 224, 0.16)` |
| Contraste texto/fondo propio | **4.56:1** | **5.74:1** |
| Contraste texto/superficie | 5.50:1 | 7.66:1 |

## 5. Resumen de tokens nuevos/tocados (para implementación)

```
--color-info / --color-info-bg                          (nuevo, ambos temas)
--color-sidebar-bg/text/text-strong/text-muted/border/
  hover/active-bg/active-text/active-rail                (se vuelven 4 sets, uno por opción)
--sidebar-tono                                           (preferencia nueva en preferencias_usuario,
                                                            mismo patrón que tema/tamaño de texto)
```

Nada más cambia de valor — el resto de la paleta (danger/success/warning/neutros/fondos/texto/
accent) queda exactamente como está hoy.

## 6. Qué NO cambia en esta ronda

- Ningún valor de `--chart-series-*`/`--status-*`.
- Ninguna estructura, navegación ni tipografía (regla explícita del pedido).
- `FuenteBadge`, `Monitoreo.tsx`, `Respaldos.tsx` (nombres de motor de base de datos) — se quedan
  igual, ver Fase 0 §3.7.
- El mecanismo de tema claro/oscuro en sí — solo se le agrega la nueva preferencia de sidebar al
  lado, sin tocar cómo funciona el existente.

---

**Quedo a la espera de tu aprobación de este plan (§2, §3, §4) antes de seguir a la Fase 2.** Los 3
puntos que dejé como "a confirmar" en la auditoría (estrellas de calificación, etiquetas de
"API"/"endpoint" en el panel de Auditoría, "GPS spoofing") no bloquean el resto — si no decís nada
sobre ellos, sigo con mi recomendación de cada uno, que ya dejé explícita ahí.
