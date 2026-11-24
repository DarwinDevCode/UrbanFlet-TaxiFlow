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
 * mismo orden y la misma posición cuando aplican.
 *
 * Bitácora de revisión (segunda pasada, 2026-08-26, punto 1): antes, una
 * pantalla que no usaba un botón lo pasaba con `disabled: true` + `title` —
 * quedaba visible pero atenuado. Confirmado con captura real que eso no era
 * lo pedido: si NINGÚN rol que llega a ese workpanel puede usar la acción
 * ahí (porque ocurre en otra pantalla, o la hace otro tipo de usuario), el
 * botón no debe existir en el árbol en absoluto. Ahora un slot solo se
 * renderiza si su prop viene definida — omitir `nuevo`/`eliminar`/`buscar`
 * lo quita del todo, no solo lo atenúa. `disabled`/`title` siguen existiendo
 * en `AccionBoton` para el caso real distinto: la acción SÍ aplica en este
 * workpanel pero está temporalmente no disponible (ej. sin selección, o
 * mientras carga) — ahí sí corresponde verse deshabilitada con motivo.
 */
export function ActionBar({ nuevo, actualizar, eliminar, buscar, salir }: ActionBarProps) {
  const botones: { key: string; label: string; variant: "primary" | "secondary" | "danger"; accion: AccionBoton }[] = [
    { key: "nuevo", label: "Nuevo", variant: "primary", accion: nuevo },
    { key: "actualizar", label: "Actualizar", variant: "secondary", accion: actualizar },
    { key: "eliminar", label: "Eliminar", variant: "danger", accion: eliminar },
    { key: "buscar", label: "Buscar", variant: "secondary", accion: buscar },
    { key: "salir", label: "Salir", variant: "secondary", accion: salir },
  ].filter((b): b is { key: string; label: string; variant: "primary" | "secondary" | "danger"; accion: AccionBoton } =>
    Boolean(b.accion),
  );

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
        <div key={b.key} style={{ minWidth: 120 }} title={b.accion.title}>
          <Button variant={b.variant} onClick={b.accion.onClick} disabled={b.accion.disabled} loading={b.accion.loading}>
            {b.label}
          </Button>
        </div>
      ))}
    </div>
  );
}
