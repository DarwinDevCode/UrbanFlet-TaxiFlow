const SIDEBAR_TONO_KEY = "urbanflet.sidebar_tono";

export type SidebarTono = "claro" | "ambar" | "oscuro" | "grafito";

interface SwatchSidebar {
  bg: string;
  text: string;
  textStrong: string;
  textMuted: string;
  border: string;
  hover: string;
  activeBg: string;
  activeText: string;
  railSubtle: string;
  railBold: string;
  /** "0"/"1": qué variante del logotipo mostrar (tinta oscura de fábrica vs.
   * la recoloreada en crema) -- la tinta del PNG es un valor fijo horneado
   * en el raster, no reacciona a ninguna variable CSS por sí sola, así que
   * cada swatch declara aquí cuál de las 2 imágenes es legible sobre su
   * propio fondo. Ver el comentario junto a `--logo-invertido` en
   * `tokens.css` para el resto del mecanismo. */
  logoInvertido: "0" | "1";
}

/** Segundo rediseño visual (v2, PLAN_REDISENO_V2.md §3): el sidebar dejó de
 * ser fijo (decisión ya revertida) y pasó a ser una preferencia por cuenta,
 * mismo patrón que `theme.ts`/`densidad.ts`/`tamanoTexto.ts`. 4 opciones
 * predefinidas, nunca un selector de color libre -- cada una ya viene con
 * su set completo de tokens verificado con WCAG real (ver el plan), incluido
 * el color del rail/marcador de nivel, que necesita ser distinto según el
 * fondo: el ámbar de marca (`--color-accent`) falla el mínimo de 3:1 contra
 * un sidebar claro, así que "Claro"/"Ámbar" usan un ámbar profundo como rail
 * y "Oscuro"/"Grafito" usan el ámbar brillante -- igual que ya pasaba antes
 * de esta ronda, pero ahora explícito por opción en vez de fijo.
 *
 * "Claro" son los valores por defecto ya declarados en `tokens.css` --
 * `SWATCHES.claro` está aquí solo para poder VOLVER a esos valores
 * explícitamente cuando la cuenta cambia de otra opción a "Claro" (`
 * aplicarSidebarTono("claro")` limpia las propiedades inline en vez de
 * fijarlas, para no divergir de la fuente de verdad en CSS). */
const SWATCHES: Record<Exclude<SidebarTono, "claro">, SwatchSidebar> = {
  ambar: {
    bg: "#fbe3ad",
    text: "#241a10",
    textStrong: "#241a10",
    textMuted: "#6b5c48",
    border: "#f0d38f",
    hover: "#f6cf78",
    activeBg: "#f6cf78",
    activeText: "#241a10",
    railSubtle: "#8a4b0a",
    railBold: "#b36a0a",
    logoInvertido: "0",
  },
  oscuro: {
    bg: "#1c140c",
    text: "#d9c9b4",
    textStrong: "#f7f1e6",
    textMuted: "#96826a",
    border: "#33261a",
    hover: "#2c2015",
    activeBg: "#2c2015",
    activeText: "#f7f1e6",
    railSubtle: "#f6c667",
    railBold: "#f2a413",
    logoInvertido: "1",
  },
  grafito: {
    bg: "#24211d",
    text: "#e8e4da",
    textStrong: "#f7f1e6",
    textMuted: "#a89f8f",
    border: "#3a352c",
    hover: "#34302a",
    activeBg: "#34302a",
    activeText: "#f7f1e6",
    railSubtle: "#f6c667",
    railBold: "#f2a413",
    logoInvertido: "1",
  },
};

const PROPIEDADES: Array<[keyof SwatchSidebar, string]> = [
  ["bg", "--color-sidebar-bg"],
  ["text", "--color-sidebar-text"],
  ["textStrong", "--color-sidebar-text-strong"],
  ["textMuted", "--color-sidebar-text-muted"],
  ["border", "--color-sidebar-border"],
  ["hover", "--color-sidebar-hover"],
  ["activeBg", "--color-sidebar-active-bg"],
  ["activeText", "--color-sidebar-active-text"],
  ["railSubtle", "--color-sidebar-rail-subtle"],
  ["railBold", "--color-sidebar-rail-bold"],
  ["logoInvertido", "--logo-invertido"],
];

function aplicarAtributo(tono: SidebarTono): void {
  const raiz = document.documentElement.style;
  if (tono === "claro") {
    // "Claro" = los valores por defecto de tokens.css -- se limpia
    // cualquier override inline en vez de fijar los mismos valores a mano,
    // para que la fuente de verdad siga siendo un solo lugar.
    for (const [, propiedad] of PROPIEDADES) raiz.removeProperty(propiedad);
    return;
  }
  const swatch = SWATCHES[tono];
  for (const [campo, propiedad] of PROPIEDADES) raiz.setProperty(propiedad, swatch[campo]);
}

/** Llamar de forma sincrónica en `main.tsx`, antes del primer render --
 * mismo criterio que `aplicarTemaInicial`: aplica el último valor conocido
 * (cache local) sin esperar `GET /preferencias`, para no parpadear. */
export function aplicarSidebarTonoInicial(): void {
  const guardado = localStorage.getItem(SIDEBAR_TONO_KEY);
  if (guardado === "claro" || guardado === "ambar" || guardado === "oscuro" || guardado === "grafito") {
    aplicarAtributo(guardado);
  }
}

/** Aplica el tono real (server-truth, vía `GET /preferencias`) y lo cachea
 * localmente para la próxima carga. */
export function aplicarSidebarTono(tono: SidebarTono): void {
  aplicarAtributo(tono);
  localStorage.setItem(SIDEBAR_TONO_KEY, tono);
}
