import type { PropsWithChildren } from "react";

export function Card({ children }: PropsWithChildren) {
  return (
    <div
      style={{
        background: "var(--color-surface)",
        border: "1px solid var(--color-border)",
        borderRadius: "var(--radius-lg)",
        boxShadow: "var(--shadow-sm)",
        padding: "var(--space-5)",
      }}
    >
      {children}
    </div>
  );
}
