import type { ChangeEvent } from "react";
import type { InputHTMLAttributes } from "react";
import "./campos.css";

interface TextFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  error?: string;
  /** Texto de ayuda bajo el campo. Se oculta mientras hay `error` -- el
   * error tiene prioridad, nunca se muestran los dos a la vez. Para inputs
   * numéricos con `min`/`max`, ver `rangeHint`. */
  hint?: string;
  /** Bitácora de revisión (2026-08-26, hallazgo #2): bloquea el signo "-" en
   * el propio tecleo de un `type="number"` -- el atributo nativo `min` NO
   * impide escribir "-5" en un input numérico, solo afecta el stepper y la
   * validación nativa del formulario (que este proyecto no usa, los
   * formularios se envían con fetch manual). Al ser un input controlado,
   * simplemente no propagar el onChange cuando el valor tecleado incluye "-"
   * hace que React revierta el DOM al valor anterior en el siguiente
   * render -- mismo patrón ya usado en el resto de la app para inputs
   * controlados. Usar en cantidades/costos/kilometraje; NUNCA en montos de
   * ajuste financiero con signo (`recaudacion` ya acepta negativos a
   * propósito para descontar). */
  bloquearNegativo?: boolean;
}

/** Genera "Entre X y Y" / "Mínimo X" / "Máximo Y" a partir de los props
 * nativos `min`/`max` de un `<input type="number">` — para que el límite
 * permitido se vea junto al campo en vez de descubrirse por ensayo y error
 * contra un error del servidor. */
export function rangeHint(min?: number | string, max?: number | string): string | undefined {
  if (min === undefined && max === undefined) return undefined;
  if (min !== undefined && max !== undefined) return `Entre ${min} y ${max}`;
  if (min !== undefined) return `Mínimo ${min}`;
  return `Máximo ${max}`;
}

/** EL CAMPO — ver `campos.css` para la decisión de diseño. Misma API que
 * la versión anterior; lo que cambia es que se apoya en una línea en vez
 * de vivir dentro de una caja. */
export function TextField({ label, error, hint, id, style, bloquearNegativo, onChange, ...rest }: TextFieldProps) {
  const fieldId = id ?? label.toLowerCase().replace(/\s+/g, "-").replace(/[^a-z0-9-]/g, "");
  const ayuda = hint ?? (rest.type === "number" ? rangeHint(rest.min, rest.max) : undefined);
  const manejarCambio = bloquearNegativo
    ? (e: ChangeEvent<HTMLInputElement>) => {
        if (e.target.value.includes("-")) return;
        onChange?.(e);
      }
    : onChange;
  return (
    <div className="uf-campo">
      <label htmlFor={fieldId} className="uf-rotulo uf-campo-label">
        {label}
      </label>
      <input
        {...rest}
        id={fieldId}
        onChange={manejarCambio}
        aria-invalid={error ? true : undefined}
        className={`uf-campo-control${error ? " uf-campo-control--error" : ""}`}
        style={style}
      />
      {error ? (
        <span className="uf-campo-error">{error}</span>
      ) : (
        ayuda && <span className="uf-campo-ayuda">{ayuda}</span>
      )}
    </div>
  );
}
