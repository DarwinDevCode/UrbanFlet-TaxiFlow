import { ApiError, Badge, Button, Card, DataTable, DetailPanel, UserPicker, apiFetch, type ModoPanel } from "@urbanflet/shared-ui";
import { useEffect, useState } from "react";

interface ConfiguracionAlerta {
  tipo_alerta: string;
  canal: string;
  destinatarios_adicionales: string[];
  activo: boolean;
  rol_destinatario_default: string;
  actualizado_en: string | null;
}

const ETIQUETA_TIPO: Record<string, string> = {
  denegaciones_rbac: "Denegaciones de permisos repetidas (CU-O18 A4)",
  gps_spoofing: "Posible GPS spoofing",
  pipeline_fallido: "Corrida de pipeline fallida",
};

const NOTA_TIPO: Record<string, string> = {
  pipeline_fallido:
    "Configurable, pero sin disparo real todavía: el pipeline (Airflow) no tiene un webhook hacia este backend, solo escribe en ClickHouse y en su propio log. La configuración queda lista para el día en que se agregue ese enlace.",
};

export function SeccionConfiguracionAlertas() {
  const [alertas, setAlertas] = useState<ConfiguracionAlerta[]>([]);
  const [seleccionada, setSeleccionada] = useState<ConfiguracionAlerta | null>(null);
  const [modo, setModo] = useState<ModoPanel>("consulta");
  const [destinatarios, setDestinatarios] = useState<string[]>([]);
  const [activo, setActivo] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);
  const [nombres, setNombres] = useState<Record<string, string>>({});

  const cargar = async () => {
    const datos = await apiFetch<ConfiguracionAlerta[]>("/notificaciones/alertas-config");
    setAlertas(datos);
    // Resuelve los IDs de destinatarios adicionales a nombres legibles para
    // la tabla -- sin esto, la columna mostraría UUIDs crudos (mismo
    // antipatrón del punto #5, ahora del lado de la lectura).
    const idsFaltantes = [...new Set(datos.flatMap((a) => a.destinatarios_adicionales))].filter((id) => !(id in nombres));
    if (idsFaltantes.length > 0) {
      const pares = await Promise.all(
        idsFaltantes.map((id) =>
          apiFetch<{ nombre: string }>(`/usuarios/${id}`)
            .then((u) => [id, u.nombre] as const)
            .catch(() => [id, id] as const),
        ),
      );
      setNombres((prev) => ({ ...prev, ...Object.fromEntries(pares) }));
    }
  };

  useEffect(() => {
    cargar().catch((e) => setError(e instanceof ApiError ? e.message : "No se pudo cargar la configuración de alertas"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const abrirDetalle = (a: ConfiguracionAlerta) => {
    setSeleccionada(a);
    setModo("edicion");
    setDestinatarios(a.destinatarios_adicionales);
    setActivo(a.activo);
    setError(null);
  };

  const guardar = async () => {
    if (!seleccionada) return;
    setError(null);
    setCargando(true);
    try {
      await apiFetch(`/notificaciones/alertas-config/${seleccionada.tipo_alerta}`, {
        method: "PATCH",
        body: { canal: "web_push", destinatarios_adicionales: destinatarios, activo },
      });
      setSeleccionada(null);
      await cargar();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo guardar la configuración");
    } finally {
      setCargando(false);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
      <Card>
        <h2 style={{ marginTop: 0, fontSize: "var(--font-size-lg)" }}>Alertas y notificaciones del sistema</h2>
        <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>
          Administra a quién y cómo llegan las alertas que el sistema ya genera. El único canal con entrega real
          hoy es Web Push (no hay envío de correo en el sistema). Cada tipo de alerta tiene un rol destinatario por
          defecto que siempre la recibe, más los destinatarios adicionales que agregues aquí como respaldo.
          Desactivar una alerta queda registrado en la bitácora — nunca es una acción silenciosa.
        </p>
      </Card>

      <Card>
        {error && !seleccionada && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</p>}
        <DataTable
          rows={alertas}
          keyField={(a) => a.tipo_alerta}
          vacio="Sin configuración."
          columns={[
            { header: "Alerta", render: (a) => ETIQUETA_TIPO[a.tipo_alerta] ?? a.tipo_alerta },
            { header: "Rol por defecto", render: (a) => a.rol_destinatario_default },
            {
              header: "Destinatarios adicionales",
              render: (a) =>
                a.destinatarios_adicionales.length > 0
                  ? a.destinatarios_adicionales.map((id) => nombres[id] ?? id).join(", ")
                  : "—",
            },
            { header: "Estado", render: (a) => <Badge texto={a.activo ? "ACTIVA" : "DESACTIVADA"} tono={a.activo ? "exito" : "peligro"} /> },
            { header: "Detalle", render: (a) => <Button variant="secondary" onClick={() => abrirDetalle(a)}>Ver</Button> },
          ]}
        />
      </Card>

      {seleccionada && (
        <DetailPanel
          titulo={`Alerta — ${ETIQUETA_TIPO[seleccionada.tipo_alerta] ?? seleccionada.tipo_alerta}`}
          modo={modo}
          onSalir={() => setSeleccionada(null)}
          onAceptar={guardar}
          aceptarLabel="Guardar"
          aceptarLoading={cargando}
        >
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
            {error && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</p>}
            {NOTA_TIPO[seleccionada.tipo_alerta] && (
              <p style={{ color: "var(--color-warning)", fontSize: "var(--font-size-sm)" }}>{NOTA_TIPO[seleccionada.tipo_alerta]}</p>
            )}
            <p style={{ fontSize: "var(--font-size-sm)", color: "var(--color-text-muted)" }}>
              Canal: Web Push (único disponible) — Rol que siempre la recibe: {seleccionada.rol_destinatario_default}
            </p>
            <UserPicker label="Destinatarios adicionales" seleccionados={destinatarios} onChange={setDestinatarios} />
            <label style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
              <input type="checkbox" checked={activo} onChange={(e) => setActivo(e.target.checked)} />
              Activa
            </label>
          </div>
        </DetailPanel>
      )}
    </div>
  );
}
