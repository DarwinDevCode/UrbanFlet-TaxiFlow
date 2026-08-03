import { Button } from "./Button";

interface AccionBoton {
  onClick: () => void;
  disabled?: boolean;
  title?: string;
  loading?: boolean;
}

interface ActionBarProps {
  nuevo?: AccionBoton;
  actualizar?: AccionBoton;
  eliminar?: AccionBoton;
  buscar?: AccionBoton;
  salir?: AccionBoton;
}

/**
 * Barra de acciones fija con los 5 botones estándar de todo panel de
 * trabajo CRUD: Nuevo, Actualizar, Eliminar, Buscar, Salir — siempre en el
 * mismo orden y la misma posición, aunque una pantalla no use todos (en ese
 * caso se pasa `disabled` + `title` explicando por qué, en vez de ocultarlo).
 */
export function ActionBar({ nuevo, actualizar, eliminar, buscar, salir }: ActionBarProps) {
  const botones: { key: string; label: string; variant: "primary" | "secondary" | "danger"; accion?: AccionBoton }[] = [
    { key: "nuevo", label: "Nuevo", variant: "primary", accion: nuevo },
    { key: "actualizar", label: "Actualizar", variant: "secondary", accion: actualizar },
    { key: "eliminar", label: "Eliminar", variant: "danger", accion: eliminar },
    { key: "buscar", label: "Buscar", variant: "secondary", accion: buscar },
    { key: "salir", label: "Salir", variant: "secondary", accion: salir },
  ];

  return (
    <div
      style={{
        display: "flex",
        gap: "var(--space-2)",
        padding: "var(--space-3)",
        background: "var(--color-surface)",
        border: "1px solid var(--color-border)",
        borderRadius: "var(--radius-md)",
        flexWrap: "wrap",
      }}
    >
      {botones.map((b) => (
        <div key={b.key} style={{ minWidth: 120 }} title={b.accion?.title}>
          <Button
            variant={b.variant}
            onClick={b.accion?.onClick ?? (() => {})}
            disabled={!b.accion || b.accion.disabled}
            loading={b.accion?.loading}
          >
            {b.label}
          </Button>
        </div>
      ))}
    </div>
  );
}
