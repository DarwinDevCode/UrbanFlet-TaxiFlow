import { useMemo, useState } from "react";
import { useAuth } from "../auth/AuthProvider";
import { apiFetch } from "../api/client";
import { invalidateSwrPrefix, useSwr } from "../api/swrCache";
import { camposLegibles, ETIQUETA_POR_TIPO, etiquetaNotificacion, type NotificacionOut } from "../notificacionesCatalogo";
import { Badge } from "./Badge";
import { Card } from "./Card";
import { DataTable, type Column } from "./DataTable";
import { DetailField, DetailPanel } from "./DetailPanel";
import { Button } from "./Button";
import { Select } from "./Select";
import { TextField } from "./TextField";

export { ETIQUETA_POR_TIPO } from "../notificacionesCatalogo";

interface NotificacionListOut {
  items: NotificacionOut[];
  total: number;
  no_leidas: number;
}

interface AccionRapida {
  etiqueta: string;
  onClick: () => void;
}

export interface SeccionNotificacionesProps {
  /** Tipos de notificación que este rol/portal puede llegar a recibir --
   * controla las opciones del filtro "Tipo" (no vale la pena ofrecer, por
   * ejemplo, "Nueva orden de mantenimiento" en la bandeja de un pasajero,
   * que nunca la va a recibir). Sin esta prop, se listan los 13 tipos
   * reales completos. */
  tiposRelevantes?: string[];
  /** Resuelve la acción rápida (etiqueta + destino) para una notificación
   * concreta -- cada app conoce sus propias pantallas/rutas, este
   * componente compartido no. `null`/`undefined` = sin acción rápida (la
   * notificación es solo informativa, ej. "tu solicitud fue aprobada" en
   * un portal sin pantalla propia para verla). */
  resolverAccionRapida?: (n: NotificacionOut) => AccionRapida | null | undefined;
}

const SIN_ITEMS: NotificacionOut[] = [];

const RECURSO_MIAS = "/notificaciones/mias";

/**
 * Sección completa del Centro de notificaciones -- listado con filtros
 * (tipo/estado/rango de fecha), distinción visual leída/no leída, detalle
 * (`DetailPanel`) que marca como leída al abrirse, y acción rápida por tipo.
 *
 * Compartida por los 3 portales, parametrizada por `tiposRelevantes` (qué
 * mostrar en el filtro) y `resolverAccionRapida` (a dónde navegar) -- nunca
 * 3 implementaciones paralelas. El listado en sí y el marcado de lectura son
 * exactamente los mismos endpoints que ya usa la campana
 * (`GET /notificaciones/mias`, `PATCH .../leida`), ampliados con filtros
 * server-side en esta misma ronda -- no un sistema de notificaciones nuevo.
 */
export function SeccionNotificaciones({ tiposRelevantes, resolverAccionRapida }: SeccionNotificacionesProps) {
  const { actualizarNoLeidas } = useAuth();
  const [filtroTipo, setFiltroTipo] = useState("");
  const [filtroLeida, setFiltroLeida] = useState("");
  const [filtroDesde, setFiltroDesde] = useState("");
  const [filtroHasta, setFiltroHasta] = useState("");
  const [seleccionada, setSeleccionada] = useState<NotificacionOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  const query = useMemo(() => {
    const params = new URLSearchParams();
    params.set("limite", "100");
    if (filtroTipo) params.set("tipo", filtroTipo);
    if (filtroLeida) params.set("leida", filtroLeida);
    if (filtroDesde) params.set("desde", new Date(filtroDesde).toISOString());
    if (filtroHasta) params.set("hasta", new Date(filtroHasta + "T23:59:59").toISOString());
    return params.toString();
  }, [filtroTipo, filtroLeida, filtroDesde, filtroHasta]);

  const clave = `${RECURSO_MIAS}?${query}`;
  const { data, refetch } = useSwr<NotificacionListOut>(clave, () => apiFetch<NotificacionListOut>(clave));
  const items = data?.items ?? SIN_ITEMS;

  // El propio fetch de esta sección ya trae `no_leidas` GLOBAL (sin el
  // filtro aplicado, ver `notificaciones/service.py::listar_notificaciones`)
  // -- se propaga al contador compartido sin disparar una petición aparte.
  // `queueMicrotask` (no un `useEffect`) porque no hay nada async que
  // esperar y evita el ciclo extra de render de un efecto; React deduplica
  // el `setState` si el número no cambió.
  if (data && typeof data.no_leidas === "number") {
    queueMicrotask(() => actualizarNoLeidas(data.no_leidas));
  }

  const opcionesTipo = tiposRelevantes ?? Object.keys(ETIQUETA_POR_TIPO);

  const marcarLeida = async (id: string) => {
    try {
      await apiFetch(`${RECURSO_MIAS}/${id}/leida`, { method: "PATCH" });
      invalidateSwrPrefix(RECURSO_MIAS);
      await refetch();
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo marcar como leída");
    }
  };

  const abrirDetalle = (n: NotificacionOut) => {
    setSeleccionada(n);
    if (!n.leida) marcarLeida(n.id);
  };

  const columnas: Column<NotificacionOut>[] = [
    {
      header: "Tipo",
      render: (n) => <span style={{ fontWeight: n.leida ? 400 : 700 }}>{etiquetaNotificacion(n)}</span>,
    },
    {
      header: "Fecha",
      prioridad: "media",
      render: (n) => new Date(n.ts).toLocaleString(),
    },
    {
      header: "Estado",
      sinTruncar: true,
      render: (n) => <Badge texto={n.leida ? "Leída" : "No leída"} tono={n.leida ? "neutral" : "advertencia"} />,
    },
    {
      header: "Detalle",
      // Techo fijo, angosto (menos de la mitad del ancho que tenía la
      // columna con los 2 botones) -- ahora "Ver" es la única acción de la
      // fila; abrir el detalle ya marca como leída sola (`abrirDetalle`), no
      // hace falta un botón aparte para eso.
      width: "100px",
      sinTruncar: true,
      // Sin `variant="secondary"` a propósito: aunque ese es el patrón que
      // ya usan Solicitudes/Mantenimiento/Finanzas para su columna
      // "Detalle" (mismo componente `Button`, no un rectángulo suelto),
      // se pidió explícitamente unificar con el peso visual primario de la
      // acción rápida del detalle -- variant por defecto (ámbar).
      render: (n) => <Button onClick={() => abrirDetalle(n)}>Ver</Button>,
    },
  ];

  const accion = seleccionada ? resolverAccionRapida?.(seleccionada) : null;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
      {/* Sin tarjeta explicativa aparte -- mismo criterio ya aplicado en los
          paneles estratégicos (texto de documentación interna filtrado a la
          UI). El título ya es autoexplicativo. */}
      <h2 style={{ margin: 0, fontSize: "var(--font-size-lg)" }}>Notificaciones</h2>

      <Card>
        {error && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</p>}
        <div style={{ display: "flex", gap: "var(--space-3)", flexWrap: "wrap", alignItems: "flex-end", marginBottom: "var(--space-3)" }}>
          <div style={{ minWidth: 220 }}>
            <Select
              label="Tipo"
              value={filtroTipo}
              onChange={(e) => setFiltroTipo(e.target.value)}
              options={[
                { value: "", label: "Todos los tipos" },
                ...opcionesTipo.map((t) => ({ value: t, label: ETIQUETA_POR_TIPO[t] ?? t })),
              ]}
            />
          </div>
          <div style={{ minWidth: 160 }}>
            <Select
              label="Estado"
              value={filtroLeida}
              onChange={(e) => setFiltroLeida(e.target.value)}
              options={[
                { value: "", label: "Todas" },
                { value: "false", label: "No leídas" },
                { value: "true", label: "Leídas" },
              ]}
            />
          </div>
          <div style={{ minWidth: 140 }}>
            <TextField label="Desde" type="date" value={filtroDesde} onChange={(e) => setFiltroDesde(e.target.value)} />
          </div>
          <div style={{ minWidth: 140 }}>
            <TextField label="Hasta" type="date" value={filtroHasta} onChange={(e) => setFiltroHasta(e.target.value)} />
          </div>
        </div>

        <DataTable
          rows={items}
          keyField={(n) => n.id}
          vacio="No hay notificaciones con este filtro."
          altoMaximo={560}
          columns={columnas}
        />
      </Card>

      {seleccionada && (
        <DetailPanel
          titulo={etiquetaNotificacion(seleccionada)}
          modo="consulta"
          onSalir={() => setSeleccionada(null)}
        >
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
            <p style={{ margin: 0, fontSize: "var(--font-size-sm)", color: "var(--color-text-muted)" }}>
              {new Date(seleccionada.ts).toLocaleString()}
            </p>
            {/* Vista legible por tipo, no el payload crudo -- ver
                `notificacionesCatalogo.ts::camposLegibles`. Cada campo con su
                etiqueta en español, mismo patrón `DetailField` que usa
                cualquier otro `DetailPanel` del sistema. */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "var(--space-3)" }}>
              {camposLegibles(seleccionada).map((c) => (
                <DetailField key={c.etiqueta} label={c.etiqueta} value={c.valor} />
              ))}
            </div>
            {accion && (
              <div style={{ maxWidth: 240 }}>
                <Button onClick={accion.onClick}>{accion.etiqueta}</Button>
              </div>
            )}
          </div>
        </DetailPanel>
      )}
    </div>
  );
}
