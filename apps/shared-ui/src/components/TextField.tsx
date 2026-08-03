import type { InputHTMLAttributes } from "react";

interface TextFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  error?: string;
}

export function TextField({ label, error, id, style, ...rest }: TextFieldProps) {
  const fieldId = id ?? label.toLowerCase().replace(/\s+/g, "-");
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
      {error && <span style={{ fontSize: "var(--font-size-sm)", color: "var(--color-danger)" }}>{error}</span>}
    </div>
  );
}
