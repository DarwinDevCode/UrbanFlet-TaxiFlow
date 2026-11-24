import type { ButtonHTMLAttributes } from "react";
import "./Button.css";

type Variant = "primary" | "secondary" | "danger";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  loading?: boolean;
}

/**
 * LA ACCIÓN — reemplaza al botón convencional (Fase 1 del Sistema Riel).
 *
 * El botón anterior era un rectángulo de esquinas redondeadas en tres
 * variantes de color: la forma que produce cualquier librería y que no
 * tiene ninguna relación con el dominio.
 *
 * La acción del Sistema Riel conserva exactamente esa API -- las mismas 3
 * variantes, `loading`, y todo lo que acepte un `<button>` -- pero cambia
 * la geometría: **una esquina cortada en diagonal**, tomada de la
 * señalética vial. Es la misma forma que aparece recortando el extremo de
 * una marca de pavimento o de una señal de desvío, y basta para que el
 * control se lea como propio de este sistema sin costarle nada a la
 * usabilidad.
 *
 * El foco de teclado usa un anillo interior en vez de `outline`: el
 * `clip-path` que produce el corte también recorta el outline del
 * navegador, así que un outline normal quedaría mutilado en la esquina.
 */
export function Button({ variant = "primary", loading = false, disabled, children, style, ...rest }: ButtonProps) {
  return (
    <button
      {...rest}
      disabled={disabled || loading}
      className={`uf-accion uf-accion--${variant}${rest.className ? ` ${rest.className}` : ""}`}
      style={style}
    >
      {loading ? <span className="uf-accion-cargando" aria-hidden="true" /> : children}
      {loading && <span className="uf-sr-only">Procesando</span>}
    </button>
  );
}
