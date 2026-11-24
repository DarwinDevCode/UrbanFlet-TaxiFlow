import { useState, type InputHTMLAttributes } from "react";
import "./campos.css";

interface PasswordFieldProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "type"> {
  label: string;
  error?: string;
  hint?: string;
  /** Cuando este campo confirma a otro, se le pasa el valor del otro:
   * muestra en vivo si coinciden, antes de dejar guardar. Sin esta prop se
   * comporta como un campo de contraseña normal (login, "contraseña
   * actual"), sin ningún mensaje de coincidencia. */
  confirmarContra?: string;
}

function IconoOjo({ visible }: { visible: boolean }) {
  return visible ? (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8Z" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  ) : (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <path
        d="M17.94 17.94A10.94 10.94 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <line x1="1" y1="1" x2="23" y2="23" strokeLinecap="round" />
    </svg>
  );
}

/** EL CAMPO RESERVADO — el campo de línea del sistema (ver `campos.css`)
 * más el control de revelado anclado al extremo de la línea. */
export function PasswordField({
  label,
  error,
  hint,
  confirmarContra,
  id,
  style,
  value,
  ...rest
}: PasswordFieldProps) {
  const [visible, setVisible] = useState(false);
  const fieldId = id ?? label.toLowerCase().replace(/\s+/g, "-").replace(/[^a-z0-9-]/g, "");

  const valorActual = typeof value === "string" ? value : "";
  const mostrarCoincidencia = confirmarContra !== undefined && valorActual.length > 0;
  const coincide = valorActual === confirmarContra;

  return (
    <div className="uf-campo">
      <label htmlFor={fieldId} className="uf-rotulo uf-campo-label">
        {label}
      </label>
      <div className="uf-campo-caja">
        <input
          {...rest}
          id={fieldId}
          type={visible ? "text" : "password"}
          value={value}
          aria-invalid={error ? true : undefined}
          className={`uf-campo-control uf-campo-control--con-accion${error ? " uf-campo-control--error" : ""}`}
          style={style}
        />
        <button
          type="button"
          onClick={() => setVisible((v) => !v)}
          aria-label={visible ? "Ocultar contraseña" : "Mostrar contraseña"}
          className="uf-campo-accion"
        >
          <IconoOjo visible={visible} />
        </button>
      </div>
      {error ? (
        <span className="uf-campo-error">{error}</span>
      ) : mostrarCoincidencia ? (
        <span className={coincide ? "uf-campo-ok" : "uf-campo-error"}>
          {coincide ? "Coinciden" : "No coinciden"}
        </span>
      ) : (
        hint && <span className="uf-campo-ayuda">{hint}</span>
      )}
    </div>
  );
}
