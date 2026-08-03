import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "danger";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  loading?: boolean;
}

const variantStyle: Record<Variant, React.CSSProperties> = {
  primary: { background: "var(--color-accent)", color: "var(--color-accent-contrast)", border: "none" },
  secondary: { background: "var(--color-surface)", color: "var(--color-text)", border: "1px solid var(--color-border)" },
  danger: { background: "var(--color-danger)", color: "#fff", border: "none" },
};

export function Button({ variant = "primary", loading = false, disabled, children, style, ...rest }: ButtonProps) {
  return (
    <button
      {...rest}
      disabled={disabled || loading}
      style={{
        ...variantStyle[variant],
        borderRadius: "var(--radius-md)",
        padding: "var(--space-3) var(--space-4)",
        fontSize: "var(--font-size-md)",
        fontWeight: 600,
        cursor: disabled || loading ? "not-allowed" : "pointer",
        opacity: disabled || loading ? 0.6 : 1,
        width: "100%",
        ...style,
      }}
    >
      {loading ? "…" : children}
    </button>
  );
}
