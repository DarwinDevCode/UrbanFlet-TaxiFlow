const DENSIDAD_KEY = "urbanflet.densidad";

export type Densidad = "comoda" | "compacta";

const PADDING: Record<Densidad, { y: string; x: string }> = {
  comoda: { y: "8px", x: "12px" },
  compacta: { y: "3px", x: "8px" },
};

function aplicarAtributo(densidad: Densidad): void {
  const { y, x } = PADDING[densidad];
  document.documentElement.style.setProperty("--table-cell-padding-y", y);
  document.documentElement.style.setProperty("--table-cell-padding-x", x);
}

/** Sección 3.2 de ux_complementaria.md, exclusivo `web-interno` (tablas
 * densas de trabajo). Mismo mecanismo que `theme.ts`: aplicación sincrónica
 * en `main.tsx` desde cache local, sin esperar `GET /preferencias`, para
 * que las tablas no "salten" de tamaño al cargar. `DataTable` lee
 * `--table-cell-padding-y/x` con un valor por defecto (`--space-2/3`) --
 * las apps que nunca llaman esto (pasajero/conductor) no se ven afectadas. */
export function aplicarDensidadInicial(): void {
  const guardada = localStorage.getItem(DENSIDAD_KEY);
  if (guardada === "comoda" || guardada === "compacta") {
    aplicarAtributo(guardada);
  }
}

export function aplicarDensidad(densidad: Densidad): void {
  aplicarAtributo(densidad);
  localStorage.setItem(DENSIDAD_KEY, densidad);
}
