import type { TextareaHTMLAttributes } from "react";

interface TextAreaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label: string;
}

export function TextArea({ label, id, style, ...rest }: TextAreaProps) {
  const fieldId = id ?? label.toLowerCase().replace(/\s+/g, "-");
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-1)", width: "100%" }}>
      <label htmlFor={fieldId} style={{ fontSize: "var(--font-size-sm)", color: "var(--color-text-muted)" }}>
        {label}
      </label>
      <textarea
        {...rest}
        id={fieldId}
        rows={rest.rows ?? 3}
        style={{
          border: "1px solid var(--color-border)",
          borderRadius: "var(--radius-sm)",
          padding: "var(--space-3)",
          fontSize: "var(--font-size-md)",
          background: "var(--color-surface)",
          color: "var(--color-text)",
          fontFamily: "inherit",
          resize: "vertical",
          ...style,
        }}
      />
    </div>
  );
}
