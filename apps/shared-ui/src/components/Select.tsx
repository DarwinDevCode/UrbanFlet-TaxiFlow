import type { SelectHTMLAttributes } from "react";
import "./campos.css";

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label: string;
  options: { value: string; label: string }[];
}

/** EL SELECTOR — mismo campo de línea que el resto (ver `campos.css`),
 * conservando el `<select>` nativo: su menú desplegable es el que mejor
 * funciona en móvil y con teclado, y reemplazarlo por una lista propia
 * costaría accesibilidad sin ganar identidad. */
export function Select({ label, options, id, style, ...rest }: SelectProps) {
  const fieldId = id ?? label.toLowerCase().replace(/\s+/g, "-").replace(/[^a-z0-9-]/g, "");
  return (
    <div className="uf-campo">
      <label htmlFor={fieldId} className="uf-rotulo uf-campo-label">
        {label}
      </label>
      <select {...rest} id={fieldId} className="uf-campo-control uf-campo-control--select" style={style}>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </div>
  );
}
