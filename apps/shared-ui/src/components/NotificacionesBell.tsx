import { useEffect, useRef, useState } from "react";
import { apiFetch } from "../api/client";
import { Button } from "./Button";

interface NotificacionOut {
  id: string;
  tipo: string;
  categoria: string;
  payload: Record<string, unknown>;
  ts: string;
  leida: boolean;
}

const ETIQUETA_POR_TIPO: Record<string, string> = {
  NUEVA_SOLICITUD: "Nueva solicitud de conductor",
  SOLICITUD_DECISION: "Tu solicitud tuvo una decisión",
  RENOVACION_DOCUMENTO_DECISION: "Renovación de documento resuelta",
  ORDEN_MANTENIMIENTO_REGISTRADA: "Nueva orden de mantenimiento",
  ORDEN_MANTENIMIENTO_CERRADA: "Orden de mantenimiento cerrada",
  ALERTA_SEGURIDAD: "Alerta de seguridad",
  VIAJE_ASIGNADO: "Se asignó un conductor a tu viaje",
  CONDUCTOR_EN_CAMINO: "El conductor va en camino",
  CONDUCTOR_LLEGO: "El conductor llegó",
  VIAJE_INICIADO: "El viaje comenzó",
  VIAJE_FINALIZADO: "El viaje finalizó",
  VIAJE_CANCELADO_CONDUCTOR: "El conductor canceló el viaje",
};

// Refresco del contador de no leídas -- mismo intervalo que otros paneles
// de "estado casi en vivo" del proyecto (ej. Monitoreo, 20s), sin abrir un
// WebSocket nuevo solo para esto (los eventos en vivo ya tienen su propio
// canal; esta bandeja es la red de seguridad para cuando no se estaba
// conectado en el momento).
const INTERVALO_REFRESCO_MS = 20_000;

/** Campana de notificaciones — Sección 4.2 de `specs/specs-administrativas/
 * ux_complementaria.md`. Reutilizada en el header de las 3 apps vía
 * `AppShell.headerActions`. */
export function NotificacionesBell() {
  const [noLeidas, setNoLeidas] = useState(0);
  const [abierto, setAbierto] = useState(false);
  const [items, setItems] = useState<NotificacionOut[]>([]);
  const [cargando, setCargando] = useState(false);
  const contenedorRef = useRef<HTMLDivElement>(null);

  const refrescarContador = () => {
    apiFetch<{ items: NotificacionOut[]; total: number; no_leidas: number }>("/notificaciones/mias?limite=1")
      .then((r) => setNoLeidas(r.no_leidas))
      .catch(() => {});
  };

  useEffect(() => {
    refrescarContador();
    const id = setInterval(refrescarContador, INTERVALO_REFRESCO_MS);
    return () => clearInterval(id);
  }, []);

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
          setNoLeidas(r.no_leidas);
        })
        .catch(() => {})
        .finally(() => setCargando(false));
    }
  };

  const marcarLeida = async (id: string) => {
    try {
      await apiFetch(`/notificaciones/mias/${id}/leida`, { method: "PATCH" });
      setItems((prev) => prev.map((n) => (n.id === id ? { ...n, leida: true } : n)));
      setNoLeidas((n) => Math.max(0, n - 1));
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
          border: "1px solid var(--color-border)",
          background: "var(--color-surface)",
          color: "var(--color-text)",
          borderRadius: "var(--radius-sm)",
          padding: "6px 10px",
          cursor: "pointer",
          fontSize: "var(--font-size-md)",
        }}
      >
        🔔
        {noLeidas > 0 && (
          <span
            style={{
              position: "absolute",
              top: -4,
              right: -4,
              background: "var(--color-danger)",
              color: "#fff",
              borderRadius: "999px",
              fontSize: "0.65rem",
              fontWeight: 700,
              minWidth: 16,
              height: 16,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              padding: "0 3px",
            }}
          >
            {noLeidas > 9 ? "9+" : noLeidas}
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
            zIndex: 50,
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
                    {ETIQUETA_POR_TIPO[n.tipo] ?? n.tipo}
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
        </div>
      )}
    </div>
  );
}
