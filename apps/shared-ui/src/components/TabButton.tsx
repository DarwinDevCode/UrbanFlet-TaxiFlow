/**
 * Botón de pestaña -- segundo rediseño visual (v2). Antes existían 4 copias
 * idénticas, byte por byte, de este mismo componente local en `web-interno`
 * (`Catalogos.tsx`, `Integraciones.tsx`, `Mantenimiento.tsx`,
 * `Respaldos.tsx`) -- mismo estilo inline repetido 4 veces, encontrado en la
 * auditoría de componentes de esta ronda. Se centraliza tal cual estaba
 * (mismo aspecto, mismos props), sin inventar una API nueva.
 */
export function TabButton({
  activa,
  onClick,
  children,
}: {
  activa: boolean;
  onClick: () => void;
  children: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        padding: "var(--space-2) var(--space-4)",
        borderRadius: "var(--radius-md)",
        border: "1px solid var(--color-border)",
        background: activa ? "var(--color-accent)" : "var(--color-surface)",
        color: activa ? "var(--color-accent-contrast)" : "var(--color-text)",
        fontWeight: 600,
        cursor: "pointer",
      }}
    >
      {children}
    </button>
  );
}
