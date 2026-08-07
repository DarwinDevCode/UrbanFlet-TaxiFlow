import { ApiError, Badge, Card, DataTable, DetailPanel, Select, TextField, apiFetch } from "@urbanflet/shared-ui";
import { useEffect, useState } from "react";

interface EventoAuditoria {
  evento_id: number;
  ts: string;
  actor_id: string | null;
  rol: string | null;
  accion: string;
  entidad: string;
  entidad_id: string | null;
  resultado: string;
  datos_previos: Record<string, unknown> | null;
  datos_posteriores: Record<string, unknown> | null;
}

interface EventosPage {
  items: EventoAuditoria[];
  total: number;
}

export function SeccionAuditoriaAdmin() {
  const [eventos, setEventos] = useState<EventoAuditoria[]>([]);
  const [total, setTotal] = useState(0);
  // Cargado desde el backend (GET /auditoria/acciones-administrativas), no
  // hardcodeado -- evita el mirror manual que se desincronizó una vez ya
  // (Módulo 3 agregó 3 acciones y este archivo no se actualizó, dejándolas
  // invisibles en el filtro sin que ningún test lo detectara).
  const [accionesAdministrativas, setAccionesAdministrativas] = useState<string[]>([]);
  const [actorInput, setActorInput] = useState("");
  const [filtroActor, setFiltroActor] = useState("");
  const [filtroAccion, setFiltroAccion] = useState("");
  const [filtroDesde, setFiltroDesde] = useState("");
  const [filtroHasta, setFiltroHasta] = useState("");
  const [seleccionado, setSeleccionado] = useState<EventoAuditoria | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<string[]>("/auditoria/acciones-administrativas")
      .then(setAccionesAdministrativas)
      .catch((e) => setError(e instanceof ApiError ? e.message : "No se pudo cargar el catálogo de acciones administrativas"));
  }, []);

  const cargar = async () => {
    if (accionesAdministrativas.length === 0) return;
    const params = new URLSearchParams();
    const acciones = filtroAccion ? [filtroAccion] : accionesAdministrativas;
    for (const a of acciones) params.append("accion", a);
    if (filtroActor) params.set("actor_id", filtroActor);
    if (filtroDesde) params.set("desde", new Date(filtroDesde).toISOString());
    if (filtroHasta) params.set("hasta", new Date(filtroHasta + "T23:59:59").toISOString());
    params.set("tamanio_pagina", "100");

    const datos = await apiFetch<EventosPage>(`/auditoria/eventos?${params.toString()}`);
    setEventos(datos.items);
    setTotal(datos.total);
  };

  useEffect(() => {
    cargar().catch((e) => setError(e instanceof ApiError ? e.message : "No se pudo cargar la bitácora administrativa"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filtroActor, filtroAccion, filtroDesde, filtroHasta, accionesAdministrativas]);

  const buscar = () => setFiltroActor(actorInput.trim());

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
      <Card>
        <h2 style={{ marginTop: 0, fontSize: "var(--font-size-lg)" }}>Auditoría de cambios administrativos</h2>
        <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>
          Vista filtrada de la misma bitácora de CU-O17 (Auditoría e Integraciones, panel táctico) — no es un
          segundo registro, solo enfoca las acciones que ocurren dentro de los módulos de Administración del
          Sistema (cuentas, roles, políticas, parámetros globales, feature flags), sin mezclarlas con miles de
          eventos operativos del día a día.
        </p>
      </Card>

      <Card>
        {error && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</p>}
        <div style={{ display: "flex", gap: "var(--space-3)", flexWrap: "wrap", alignItems: "flex-end", marginBottom: "var(--space-3)" }}>
          <div style={{ minWidth: 220 }}>
            <TextField
              label="Actor (id)"
              value={actorInput}
              onChange={(e) => setActorInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && buscar()}
            />
          </div>
          <div style={{ minWidth: 220 }}>
            <Select
              label="Acción"
              value={filtroAccion}
              onChange={(e) => setFiltroAccion(e.target.value)}
              options={[{ value: "", label: "Todas las administrativas" }, ...accionesAdministrativas.map((a) => ({ value: a, label: a }))]}
            />
          </div>
          <div style={{ minWidth: 140 }}>
            <TextField label="Desde" type="date" value={filtroDesde} onChange={(e) => setFiltroDesde(e.target.value)} />
          </div>
          <div style={{ minWidth: 140 }}>
            <TextField label="Hasta" type="date" value={filtroHasta} onChange={(e) => setFiltroHasta(e.target.value)} />
          </div>
        </div>

        <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>{total} evento(s) administrativo(s) con este filtro.</p>

        <DataTable
          rows={eventos}
          keyField={(e) => String(e.evento_id)}
          vacio="No hay eventos administrativos con este filtro."
          altoMaximo={620}
          columns={[
            { header: "Hora", render: (e) => new Date(e.ts).toLocaleString() },
            { header: "Actor", render: (e) => e.actor_id ?? "—" },
            { header: "Rol", width: "160px", render: (e) => e.rol ?? "—" },
            { header: "Acción", render: (e) => e.accion },
            { header: "Entidad", render: (e) => `${e.entidad}${e.entidad_id ? ` (${e.entidad_id})` : ""}` },
            { header: "Resultado", render: (e) => <Badge texto={e.resultado} tono={e.resultado === "DENEGADO" ? "peligro" : "exito"} /> },
            {
              header: "Cambio",
              render: (e) =>
                e.datos_previos || e.datos_posteriores ? (
                  <button
                    type="button"
                    onClick={() => setSeleccionado(e)}
                    style={{ background: "none", border: "none", color: "var(--color-accent)", cursor: "pointer", textDecoration: "underline", padding: 0 }}
                  >
                    Ver antes/después
                  </button>
                ) : (
                  "—"
                ),
            },
          ]}
        />
      </Card>

      {seleccionado && (
        <DetailPanel titulo={`Cambio — ${seleccionado.accion}`} modo="consulta" onSalir={() => setSeleccionado(null)}>
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-4)" }}>
              <div>
                <h3 style={{ fontSize: "var(--font-size-sm)", color: "var(--color-text-muted)", marginBottom: "var(--space-2)" }}>Antes</h3>
                <pre style={{ background: "var(--color-surface-muted, #f5f5f5)", padding: "var(--space-3)", borderRadius: "var(--radius-sm)", fontSize: "var(--font-size-sm)", overflowX: "auto" }}>
                  {seleccionado.datos_previos ? JSON.stringify(seleccionado.datos_previos, null, 2) : "(sin dato previo)"}
                </pre>
              </div>
              <div>
                <h3 style={{ fontSize: "var(--font-size-sm)", color: "var(--color-text-muted)", marginBottom: "var(--space-2)" }}>Después</h3>
                <pre style={{ background: "var(--color-surface-muted, #f5f5f5)", padding: "var(--space-3)", borderRadius: "var(--radius-sm)", fontSize: "var(--font-size-sm)", overflowX: "auto" }}>
                  {seleccionado.datos_posteriores ? JSON.stringify(seleccionado.datos_posteriores, null, 2) : "(sin dato posterior)"}
                </pre>
              </div>
            </div>
          </div>
        </DetailPanel>
      )}
    </div>
  );
}
