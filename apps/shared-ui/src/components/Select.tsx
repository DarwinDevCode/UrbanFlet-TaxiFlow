import type { SelectHTMLAttributes } from "react";

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label: string;
  options: { value: string; label: string }[];
}

export function Select({ label, options, id, style, ...rest }: SelectProps) {
  const fieldId = id ?? label.toLowerCase().replace(/\s+/g, "-");
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-1)", width: "100%" }}>
      <label htmlFor={fieldId} style={{ fontSize: "var(--font-size-sm)", color: "var(--color-text-muted)" }}>
        {label}
      </label>
      <select
        {...rest}
        id={fieldId}
        style={{
          border: "1px solid var(--color-border)",
          borderRadius: "var(--radius-sm)",
          padding: "var(--space-3)",
          fontSize: "var(--font-size-md)",
          background: "var(--color-surface)",
          color: "var(--color-text)",
          ...style,
        }}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </div>
  );
}
