import { useEffect, useRef, useState } from "react";
import { useAuth } from "../auth/AuthProvider";
import { apiFetch } from "../api/client";
import { etiquetaNotificacion, type NotificacionOut } from "../notificacionesCatalogo";
import { Button } from "./Button";
import { CountBadge } from "./CountBadge";

interface NotificacionesBellProps {
  /** Navega a la sección completa "Notificaciones" -- cada app resuelve
   * cómo (cambio de `vista`, o `irASeccion` en web-interno). Sin esta prop,
   * "Ver todas" no se pinta -- útil para un consumidor aislado en test. */
  onVerTodas?: () => void;
}

/** Campana de notificaciones — Sección 4.2 de `specs/specs-administrativas/
 * ux_complementaria.md`. Reutilizada en el header de las 3 apps vía
 * `AppShell.headerActions`. El contador de no leídas vive en `AuthProvider`
 * (compartido con la entrada de sidebar "Notificaciones", que necesita el
 * mismo número sin desincronizarse). */
export function NotificacionesBell({ onVerTodas }: NotificacionesBellProps) {
  const { noLeidas, actualizarNoLeidas, refrescarNoLeidas } = useAuth();
  const [abierto, setAbierto] = useState(false);
  const [items, setItems] = useState<NotificacionOut[]>([]);
  const [cargando, setCargando] = useState(false);
  const contenedorRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!abierto) return;
    const alHacerClicFuera = (e: MouseEvent) => {
      if (contenedorRef.current && !contenedorRef.current.contains(e.target as Node)) setAbierto(false);
    };
    document.addEventListener("mousedown", alHacerClicFuera);
    return () => document.removeEventListener("mousedown", alHacerClicFuera);
  }, [abierto]);

  const abrir = () => {
    setAbierto((v) => !v);
    if (!abierto) {
      setCargando(true);
      apiFetch<{ items: NotificacionOut[]; total: number; no_leidas: number }>("/notificaciones/mias?limite=20")
        .then((r) => {
          setItems(r.items);
          actualizarNoLeidas(r.no_leidas);
        })
        .catch(() => {})
        .finally(() => setCargando(false));
    }
  };

  const marcarLeida = async (id: string) => {
    try {
      await apiFetch(`/notificaciones/mias/${id}/leida`, { method: "PATCH" });
      setItems((prev) => prev.map((n) => (n.id === id ? { ...n, leida: true } : n)));
      refrescarNoLeidas();
    } catch {
      /* silencioso -- no bloquea la lectura del resto */
    }
  };

  return (
    <div ref={contenedorRef} style={{ position: "relative" }}>
      <button
        type="button"
        onClick={abrir}
        aria-label="Bandeja de notificaciones"
        style={{
          position: "relative",
          display: "inline-flex",
          alignItems: "center",
          border: "1px solid var(--color-border)",
          background: "var(--color-surface)",
          color: "var(--color-text)",
          borderRadius: "var(--radius-sm)",
          padding: "6px 10px",
          cursor: "pointer",
        }}
      >
        {/* Mismo tratamiento que el resto de los íconos hechos a mano del
            sistema (ej. la flecha de plegado de `MapOverlayCard`): SVG
            inline con `stroke="currentColor"`, sin librería nueva -- el
            proyecto no tiene ninguna instalada (confirmado antes de tocar
            esto, ver resumen de la ronda). */}
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
          <path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" strokeLinecap="round" strokeLinejoin="round" />
          <path d="M13.73 21a2 2 0 0 1-3.46 0" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        {noLeidas > 0 && (
          <span style={{ position: "absolute", top: -4, right: -4 }}>
            <CountBadge valor={noLeidas} />
          </span>
        )}
      </button>

      {abierto && (
        <div
          style={{
            position: "absolute",
            top: "calc(100% + 8px)",
            right: 0,
            width: 320,
            maxHeight: 400,
            overflowY: "auto",
            background: "var(--color-surface)",
            border: "1px solid var(--color-border)",
            borderRadius: "var(--radius-md)",
            boxShadow: "var(--shadow-md)",
            zIndex: "var(--z-dropdown)",
          }}
        >
          <div style={{ padding: "var(--space-3)", borderBottom: "1px solid var(--color-border)", fontWeight: 700 }}>
            Notificaciones
          </div>
          {cargando ? (
            <p style={{ padding: "var(--space-3)", color: "var(--color-text-muted)" }}>Cargando…</p>
          ) : items.length === 0 ? (
            <p style={{ padding: "var(--space-3)", color: "var(--color-text-muted)" }}>Sin notificaciones todavía.</p>
          ) : (
            items.map((n) => (
              <div
                key={n.id}
                style={{
                  padding: "var(--space-3)",
                  borderBottom: "1px solid var(--color-border)",
                  background: n.leida ? "transparent" : "var(--color-bg)",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "flex-start",
                  gap: "var(--space-2)",
                }}
              >
                <div>
                  <p style={{ margin: 0, fontSize: "var(--font-size-sm)", fontWeight: n.leida ? 400 : 700 }}>
                    {etiquetaNotificacion(n)}
                  </p>
                  <p style={{ margin: 0, marginTop: 2, fontSize: "var(--font-size-sm)", color: "var(--color-text-muted)" }}>
                    {new Date(n.ts).toLocaleString()}
                  </p>
                </div>
                {!n.leida && (
                  <div style={{ minWidth: 90, flexShrink: 0 }}>
                    <Button variant="secondary" onClick={() => marcarLeida(n.id)}>
                      Marcar leída
                    </Button>
                  </div>
                )}
              </div>
            ))
          )}
          {onVerTodas && (
            <button
              type="button"
              onClick={() => {
                setAbierto(false);
                onVerTodas();
              }}
              style={{
                display: "block",
                width: "100%",
                padding: "var(--space-2) var(--space-3)",
                border: "none",
                background: "transparent",
                color: "var(--color-accent)",
                fontWeight: 600,
                fontSize: "var(--font-size-sm)",
                textAlign: "center",
                cursor: "pointer",
              }}
            >
              Ver todas
            </button>
          )}
        </div>
      )}
    </div>
  );
}
