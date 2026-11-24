import type { ReactNode } from "react";

export type AlertTono = "exito" | "advertencia" | "peligro" | "informativo";

const ESTILO_TONO: Record<AlertTono, { color: string; background: string; border: string }> = {
  exito: { color: "var(--color-success)", background: "var(--color-success-bg)", border: "var(--color-success)" },
  advertencia: { color: "var(--color-warning)", background: "var(--color-warning-bg)", border: "var(--color-warning)" },
  peligro: { color: "var(--color-danger)", background: "var(--color-danger-bg)", border: "var(--color-danger)" },
  // Único tono sin badge/KPI equivalente todavía (segundo rediseño visual,
  // PLAN_REDISENO_V2.md §4) -- el sistema no tenía ningún tono "informativo"
  // hasta esta ronda.
  informativo: { color: "var(--color-info)", background: "var(--color-info-bg)", border: "var(--color-info)" },
};

export interface AlertProps {
  tono: AlertTono;
  children: ReactNode;
}

/**
 * Aviso en línea (banner), no un modal. Segundo rediseño visual (v2):
 * antes de este componente, cada pantalla que necesitaba un aviso así lo
 * construía a mano con los mismos tokens repetidos -- encontrados 2 casos
 * idénticos ("documentación vencida", en `web-conductor` y en
 * `Usuarios.tsx` de `web-interno`) durante la auditoría de componentes de
 * esta ronda. `role="alert"` siempre -- un lector de pantalla debe
 * anunciarlo igual sin importar el tono.
 */
export function Alert({ tono, children }: AlertProps) {
  const estilo = ESTILO_TONO[tono];
  return (
    <div
      role="alert"
      style={{
        border: `1px solid ${estilo.border}`,
        background: estilo.background,
        color: estilo.color,
        borderRadius: "var(--radius-md)",
        padding: "var(--space-3)",
        fontSize: "var(--font-size-sm)",
      }}
    >
      {children}
    </div>
  );
}
