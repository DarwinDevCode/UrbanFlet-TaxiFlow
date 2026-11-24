import type { TextareaHTMLAttributes } from "react";
import "./campos.css";

interface TextAreaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label: string;
}

/** EL CAMPO EXTENSO — mismo tratamiento de línea que el resto de campos
 * (ver `campos.css`), con alto propio y redimensionado vertical. */
export function TextArea({ label, id, style, ...rest }: TextAreaProps) {
  const fieldId = id ?? label.toLowerCase().replace(/\s+/g, "-").replace(/[^a-z0-9-]/g, "");
  return (
    <div className="uf-campo">
      <label htmlFor={fieldId} className="uf-rotulo uf-campo-label">
        {label}
      </label>
      <textarea
        {...rest}
        id={fieldId}
        rows={rest.rows ?? 3}
        className="uf-campo-control uf-campo-control--area"
        style={style}
      />
    </div>
  );
}
