import type { InputHTMLAttributes } from "react";

interface TextFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  error?: string;
  /** Texto de ayuda bajo el campo (ej. "Entre 3 y 20"). Se oculta mientras
   * `error` está presente -- el error tiene prioridad, no se muestran los
   * dos a la vez. Para inputs numéricos con `min`/`max`, ver `rangeHint`
   * más abajo, que genera este texto automáticamente. */
  hint?: string;
}

/** Genera "Entre X y Y" / "Mínimo X" / "Máximo Y" a partir de los props
 * nativos `min`/`max` de un `<input type="number">` -- para que el límite
 * permitido se vea siempre junto al campo, en vez de que el usuario lo
 * descubra por ensayo y error contra un 422 del backend. */
export function rangeHint(min?: number | string, max?: number | string): string | undefined {
  if (min === undefined && max === undefined) return undefined;
  if (min !== undefined && max !== undefined) return `Entre ${min} y ${max}`;
  if (min !== undefined) return `Mínimo ${min}`;
  return `Máximo ${max}`;
}

export function TextField({ label, error, hint, id, style, ...rest }: TextFieldProps) {
  const fieldId = id ?? label.toLowerCase().replace(/\s+/g, "-").replace(/[^a-z0-9-]/g, "");
  const ayuda = hint ?? (rest.type === "number" ? rangeHint(rest.min, rest.max) : undefined);
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-1)", width: "100%" }}>
      <label htmlFor={fieldId} style={{ fontSize: "var(--font-size-sm)", color: "var(--color-text-muted)" }}>
        {label}
      </label>
      <input
        {...rest}
        id={fieldId}
        style={{
          border: `1px solid ${error ? "var(--color-danger)" : "var(--color-border)"}`,
          borderRadius: "var(--radius-sm)",
          padding: "var(--space-3)",
          fontSize: "var(--font-size-md)",
          background: "var(--color-surface)",
          color: "var(--color-text)",
          ...style,
        }}
      />
      {error ? (
        <span style={{ fontSize: "var(--font-size-sm)", color: "var(--color-danger)" }}>{error}</span>
      ) : (
        ayuda && <span style={{ fontSize: "var(--font-size-sm)", color: "var(--color-text-muted)" }}>{ayuda}</span>
      )}
    </div>
  );
}
