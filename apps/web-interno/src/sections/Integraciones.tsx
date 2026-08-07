import {
  ActionBar,
  ApiError,
  apiFetch,
  Badge,
  Button,
  Card,
  DataTable,
  DetailField,
  DetailPanel,
  TextField,
  type ModoPanel,
} from "@urbanflet/shared-ui";
import { useEffect, useState } from "react";

interface Credencial {
  id: string;
  nombre: string;
  alcance: string;
  vigente_desde: string;
  vigente_hasta: string | null;
  revocada: boolean;
  usos_registrados: number;
}

interface ServicioExterno {
  nombre: "google_maps" | "sms" | "s3";
  estado: "activo" | "no_configurado";
  key_enmascarada: string | null;
}

const NOMBRE_SERVICIO: Record<ServicioExterno["nombre"], string> = {
  google_maps: "Google Maps (Directions/Geocoding)",
  sms: "SMS",
  s3: "Almacenamiento S3",
};

type Pestana = "credenciales" | "servicios";

function TabButton({ activa, onClick, children }: { activa: boolean; onClick: () => void; children: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        padding: "var(--space-2) var(--space-4)",
        borderRadius: "var(--radius-md)",
        border: "1px solid var(--color-border)",
        background: activa ? "var(--color-accent)" : "var(--color-surface)",
        color: activa ? "#fff" : "var(--color-text)",
        fontWeight: 600,
        cursor: "pointer",
      }}
    >
      {children}
    </button>
  );
}

function SeccionCredenciales() {
  const [credenciales, setCredenciales] = useState<Credencial[]>([]);
  const [seleccionada, setSeleccionada] = useState<Credencial | null>(null);
  const [modo, setModo] = useState<ModoPanel>("consulta");
  const [nombre, setNombre] = useState("");
  const [alcance, setAlcance] = useState("");
  const [secretoNuevo, setSecretoNuevo] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);

  const cargar = async () => setCredenciales(await apiFetch<Credencial[]>("/integraciones/credenciales"));

  useEffect(() => {
    cargar().catch((e) => setError(e instanceof ApiError ? e.message : "No se pudieron cargar las credenciales"));
  }, []);

  const abrirNuevo = () => {
    setSeleccionada(null);
    setModo("nuevo");
    setNombre("");
    setAlcance("");
    setSecretoNuevo(null);
    setError(null);
  };

  const abrirDetalle = (c: Credencial) => {
    setSeleccionada(c);
    setModo("consulta");
    setSecretoNuevo(null);
    setError(null);
  };

  const crear = async () => {
    setError(null);
    setCargando(true);
    try {
      const creada = await apiFetch<Credencial & { secreto: string }>("/integraciones/credenciales", {
        method: "POST",
        body: { nombre, alcance },
      });
      setSecretoNuevo(creada.secreto);
      await cargar();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo crear la credencial");
    } finally {
      setCargando(false);
    }
  };

  const revocar = async () => {
    if (!seleccionada) return;
    setError(null);
    setCargando(true);
    try {
      await apiFetch(`/integraciones/credenciales/${seleccionada.id}/revocar`, { method: "POST" });
      setSeleccionada(null);
      setModo("consulta");
      await cargar();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo revocar la credencial");
    } finally {
      setCargando(false);
    }
  };

  return (
    <Card>
      <ActionBar
        nuevo={{ onClick: abrirNuevo }}
        actualizar={{ onClick: () => cargar() }}
        eliminar={{ onClick: () => {}, disabled: true, title: "No aplica: una credencial se revoca, no se elimina." }}
        buscar={{ onClick: () => {}, disabled: true, title: "No aplica: la lista no pagina." }}
        salir={{ onClick: () => setSeleccionada(null) }}
      />
      {error && !seleccionada && modo !== "nuevo" && (
        <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)", marginTop: "var(--space-3)" }}>
          {error}
        </p>
      )}
      <div style={{ marginTop: "var(--space-3)" }}>
        <DataTable
          rows={credenciales}
          keyField={(c) => c.id}
          vacio="No hay credenciales de integración creadas todavía."
          columns={[
            { header: "Nombre", render: (c) => c.nombre },
            { header: "Alcance", render: (c) => c.alcance || "—" },
            { header: "Usos", render: (c) => c.usos_registrados },
            {
              header: "Estado",
              render: (c) => <Badge texto={c.revocada ? "REVOCADA" : "ACTIVA"} tono={c.revocada ? "neutral" : "exito"} />,
            },
            { header: "Detalle", render: (c) => <Button variant="secondary" onClick={() => abrirDetalle(c)}>Ver</Button> },
          ]}
        />
      </div>

      {modo === "nuevo" && (
        <DetailPanel
          titulo="Nueva credencial de integración"
          modo="nuevo"
          onSalir={() => { setModo("consulta"); setSecretoNuevo(null); }}
          onAceptar={secretoNuevo ? undefined : crear}
          aceptarLabel="Crear"
          aceptarDisabled={!nombre}
          aceptarLoading={cargando}
        >
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
            {error && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</p>}
            {secretoNuevo ? (
              <>
                <p style={{ color: "var(--color-warning)", fontWeight: 600 }}>
                  Este secreto se muestra una sola vez. Cópialo ahora — no queda almacenado en texto plano y no se
                  puede volver a mostrar.
                </p>
                <TextField label="Secreto" value={secretoNuevo} readOnly onFocus={(e) => e.target.select()} />
              </>
            ) : (
              <>
                <TextField label="Nombre" value={nombre} onChange={(e) => setNombre(e.target.value)} />
                <TextField
                  label="Alcance (opcional)"
                  value={alcance}
                  onChange={(e) => setAlcance(e.target.value)}
                />
              </>
            )}
          </div>
        </DetailPanel>
      )}

      {seleccionada && modo === "consulta" && (
        <DetailPanel
          titulo={`Credencial — ${seleccionada.nombre}`}
          modo="consulta"
          onSalir={() => setSeleccionada(null)}
          accionesExtra={
            !seleccionada.revocada ? (
              <div style={{ minWidth: 140 }}>
                <Button variant="danger" onClick={revocar} loading={cargando}>Revocar</Button>
              </div>
            ) : undefined
          }
        >
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
            {error && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</p>}
            <DetailField label="Nombre" value={seleccionada.nombre} />
            <DetailField label="Alcance" value={seleccionada.alcance || "—"} />
            <DetailField label="Usos registrados" value={seleccionada.usos_registrados} />
            <DetailField
              label="Estado"
              value={<Badge texto={seleccionada.revocada ? "REVOCADA" : "ACTIVA"} tono={seleccionada.revocada ? "neutral" : "exito"} />}
            />
            <DetailField label="Vigente desde" value={new Date(seleccionada.vigente_desde).toLocaleString()} />
            {seleccionada.vigente_hasta && (
              <DetailField label="Vigente hasta" value={new Date(seleccionada.vigente_hasta).toLocaleString()} />
            )}
          </div>
        </DetailPanel>
      )}
    </Card>
  );
}

function SeccionServiciosExternos() {
  const [servicios, setServicios] = useState<ServicioExterno[]>([]);
  const [rotando, setRotando] = useState(false);
  const [apiKey, setApiKey] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);

  const cargar = async () => setServicios(await apiFetch<ServicioExterno[]>("/integraciones/servicios-externos"));

  useEffect(() => {
    cargar().catch((e) => setError(e instanceof ApiError ? e.message : "No se pudieron cargar los servicios externos"));
  }, []);

  const abrirRotar = () => {
    setApiKey("");
    setError(null);
    setRotando(true);
  };

  const rotar = async () => {
    setError(null);
    setCargando(true);
    try {
      await apiFetch("/integraciones/servicios-externos/google_maps/rotar", { method: "POST", body: { api_key: apiKey } });
      setRotando(false);
      await cargar();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo rotar la key");
    } finally {
      setCargando(false);
    }
  };

  return (
    <Card>
      <ActionBar
        nuevo={{ onClick: () => {}, disabled: true, title: "No aplica: los servicios externos son fijos, no se crean." }}
        actualizar={{ onClick: () => cargar() }}
        eliminar={{ onClick: () => {}, disabled: true, title: "No aplica." }}
        buscar={{ onClick: () => {}, disabled: true, title: "No aplica: la lista no pagina." }}
        salir={{ onClick: () => setRotando(false) }}
      />
      {error && !rotando && (
        <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)", marginTop: "var(--space-3)" }}>
          {error}
        </p>
      )}
      <div style={{ marginTop: "var(--space-3)" }}>
        <DataTable
          rows={servicios}
          keyField={(s) => s.nombre}
          vacio="Sin servicios externos."
          columns={[
            { header: "Servicio", render: (s) => NOMBRE_SERVICIO[s.nombre] },
            { header: "Estado", render: (s) => <Badge texto={s.estado === "activo" ? "ACTIVO" : "NO CONFIGURADO"} tono={s.estado === "activo" ? "exito" : "neutral"} /> },
            { header: "Key", render: (s) => s.key_enmascarada ?? "—" },
            {
              header: "Acción",
              render: (s) =>
                s.nombre === "google_maps" ? (
                  <Button variant="secondary" onClick={abrirRotar}>Rotar key</Button>
                ) : (
                  "—"
                ),
            },
          ]}
        />
      </div>
      <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)", marginTop: "var(--space-3)" }}>
        SMS y S3 no tienen integración real en el sistema todavía — se muestran como referencia de la arquitectura,
        siempre "No configurado".
      </p>

      {rotando && (
        <DetailPanel
          titulo="Rotar key de Google Maps"
          modo="edicion"
          onSalir={() => setRotando(false)}
          onAceptar={rotar}
          aceptarLabel="Rotar"
          aceptarDisabled={apiKey.length < 8}
          aceptarLoading={cargando}
        >
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
            {error && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</p>}
            <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>
              La nueva key entra en vigor de inmediato para Directions/Geocoding, sin reiniciar el backend.
            </p>
            <TextField label="Nueva API key" value={apiKey} onChange={(e) => setApiKey(e.target.value)} />
          </div>
        </DetailPanel>
      )}
    </Card>
  );
}

export function SeccionIntegraciones() {
  const [pestana, setPestana] = useState<Pestana>("credenciales");

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
      <Card>
        <h2 style={{ marginTop: 0, fontSize: "var(--font-size-lg)" }}>Integraciones externas</h2>
        <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>
          Credenciales para consumidores externos y estado de los servicios externos que el sistema ya integra
          (hoy, solo Google Maps tiene una integración real).
        </p>
      </Card>

      <div style={{ display: "flex", gap: "var(--space-2)" }}>
        <TabButton activa={pestana === "credenciales"} onClick={() => setPestana("credenciales")}>Credenciales</TabButton>
        <TabButton activa={pestana === "servicios"} onClick={() => setPestana("servicios")}>Servicios externos</TabButton>
      </div>

      {pestana === "credenciales" && <SeccionCredenciales />}
      {pestana === "servicios" && <SeccionServiciosExternos />}
    </div>
  );
}
