const TEMA_KEY = "urbanflet.tema";

export type Tema = "claro" | "oscuro";

function aplicarAtributo(tema: Tema): void {
  document.documentElement.dataset.theme = tema === "oscuro" ? "dark" : "light";
}

/** Llamar de forma sincrónica en `main.tsx`, antes del primer render --
 * aplica el último tema conocido (cache local) sin esperar la respuesta de
 * `GET /preferencias`, para no parpadear en claro al cargar. */
export function aplicarTemaInicial(): void {
  const guardado = localStorage.getItem(TEMA_KEY);
  if (guardado === "claro" || guardado === "oscuro") {
    aplicarAtributo(guardado);
  }
}

/** Aplica el tema real (server-truth, vía `GET /preferencias`) y lo cachea
 * localmente para la próxima carga (`aplicarTemaInicial`). */
export function aplicarTema(tema: Tema): void {
  aplicarAtributo(tema);
  localStorage.setItem(TEMA_KEY, tema);
}
