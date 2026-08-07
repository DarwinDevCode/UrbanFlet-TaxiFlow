import { useState } from "react";
import { Button } from "./Button";

/** Punto #4 de la ronda de usabilidad de admin_sistema (2026-08-07):
 * pantallas de configuración sensible (políticas, parámetros globales)
 * aparecían inmediatamente editables al entrar, facilitando un cambio
 * accidental. Este hook + `ReadOnlyActions` son el patrón único reutilizado
 * en todas esas pantallas: bloqueado al entrar, "Editar" explícito lo
 * habilita, "Guardar"/"Cancelar" vuelven a bloquear. */
export function useReadOnlyGate() {
  const [editando, setEditando] = useState(false);
  return { editando, editar: () => setEditando(true), bloquear: () => setEditando(false) };
}

interface ReadOnlyActionsProps {
  editando: boolean;
  onEditar: () => void;
  onCancelar: () => void;
  onGuardar: () => void;
  guardarLabel?: string;
  guardarDisabled?: boolean;
  guardarLoading?: boolean;
}

/** Barra de acciones consistente para el patrón solo-lectura-por-defecto:
 * un solo botón "Editar" en reposo, "Guardar"/"Cancelar" mientras se edita. */
export function ReadOnlyActions({
  editando,
  onEditar,
  onCancelar,
  onGuardar,
  guardarLabel = "Guardar",
  guardarDisabled,
  guardarLoading,
}: ReadOnlyActionsProps) {
  if (!editando) {
    return (
      <div style={{ minWidth: 140 }}>
        <Button variant="secondary" onClick={onEditar}>
          Editar
        </Button>
      </div>
    );
  }
  return (
    <div style={{ display: "flex", gap: "var(--space-2)", flexWrap: "wrap" }}>
      <div style={{ minWidth: 140 }}>
        <Button onClick={onGuardar} disabled={guardarDisabled} loading={guardarLoading}>
          {guardarLabel}
        </Button>
      </div>
      <div style={{ minWidth: 140 }}>
        <Button variant="secondary" onClick={onCancelar}>
          Cancelar
        </Button>
      </div>
    </div>
  );
}
