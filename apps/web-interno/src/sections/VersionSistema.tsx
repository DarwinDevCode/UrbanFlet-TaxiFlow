import { ApiError, Button, Card, DataTable, Select, TextArea, TextField, apiFetch } from "@urbanflet/shared-ui";
import { useEffect, useState } from "react";

interface Version {
  backend: string;
  web_pasajero: string;
  web_conductor: string;
  web_interno: string;
}

interface Despliegue {
  id: string;
  componente: string;
  version: string;
  notas: string;
  desplegado_en: string;
  desplegado_por: string | null;
}

const COMPONENTES = ["backend", "web-pasajero", "web-conductor", "web-interno", "todos"];

export function SeccionVersionSistema() {
  const [version, setVersion] = useState<Version | null>(null);
  const [despliegues, setDespliegues] = useState<Despliegue[]>([]);
  const [componente, setComponente] = useState("backend");
  const [versionTexto, setVersionTexto] = useState("");
  const [notas, setNotas] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);

  const cargar = async () => {
    const [v, d] = await Promise.all([
      apiFetch<Version>("/sistema/version"),
      apiFetch<Despliegue[]>("/sistema/despliegues"),
    ]);
    setVersion(v);
    setDespliegues(d);
  };

  useEffect(() => {
    cargar().catch((e) => setError(e instanceof ApiError ? e.message : "No se pudo cargar la versión del sistema"));
  }, []);

  const registrar = async () => {
    setError(null);
    setOk(null);
    setCargando(true);
    try {
      await apiFetch("/sistema/despliegues", { method: "POST", body: { componente, version: versionTexto, notas } });
      setOk("Despliegue registrado.");
      setVersionTexto("");
      setNotas("");
      await cargar();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo registrar el despliegue");
    } finally {
      setCargando(false);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
      <Card>
        <h2 style={{ marginTop: 0, fontSize: "var(--font-size-lg)" }}>Versión del sistema</h2>
        {error && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</p>}
        {version && (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: "var(--space-3)" }}>
            <div>
              <p style={{ margin: 0, fontSize: "var(--font-size-sm)", color: "var(--color-text-muted)" }}>Backend</p>
              <p style={{ margin: 0, fontSize: "var(--font-size-lg)", fontWeight: 700 }}>{version.backend}</p>
            </div>
            <div>
              <p style={{ margin: 0, fontSize: "var(--font-size-sm)", color: "var(--color-text-muted)" }}>web-pasajero</p>
              <p style={{ margin: 0, fontSize: "var(--font-size-lg)", fontWeight: 700 }}>{version.web_pasajero}</p>
            </div>
            <div>
              <p style={{ margin: 0, fontSize: "var(--font-size-sm)", color: "var(--color-text-muted)" }}>web-conductor</p>
              <p style={{ margin: 0, fontSize: "var(--font-size-lg)", fontWeight: 700 }}>{version.web_conductor}</p>
            </div>
            <div>
              <p style={{ margin: 0, fontSize: "var(--font-size-sm)", color: "var(--color-text-muted)" }}>web-interno</p>
              <p style={{ margin: 0, fontSize: "var(--font-size-lg)", fontWeight: 700 }}>{version.web_interno}</p>
            </div>
          </div>
        )}
      </Card>

      <Card>
        <h3 style={{ marginTop: 0, fontSize: "var(--font-size-md)" }}>Registrar un despliegue</h3>
        <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>
          Registro manual — este proyecto no tiene un proceso de CI/CD que lo llene automáticamente. Se agrega a
          mano al cerrar una sesión de desarrollo que cambió la versión de un componente.
        </p>
        {ok && <p style={{ color: "var(--color-success)", fontSize: "var(--font-size-sm)" }}>{ok}</p>}
        <div style={{ display: "flex", gap: "var(--space-3)", flexWrap: "wrap", alignItems: "flex-end" }}>
          <div style={{ minWidth: 180 }}>
            <Select label="Componente" value={componente} onChange={(e) => setComponente(e.target.value)} options={COMPONENTES.map((c) => ({ value: c, label: c }))} />
          </div>
          <div style={{ minWidth: 160 }}>
            <TextField label="Versión" value={versionTexto} onChange={(e) => setVersionTexto(e.target.value)} placeholder="0.2.0" />
          </div>
        </div>
        <div style={{ marginTop: "var(--space-3)" }}>
          <TextArea label="Notas (opcional)" value={notas} onChange={(e) => setNotas(e.target.value)} />
        </div>
        <div style={{ marginTop: "var(--space-3)", minWidth: 180 }}>
          <Button onClick={registrar} loading={cargando} disabled={!versionTexto}>
            Registrar despliegue
          </Button>
        </div>
      </Card>

      <Card>
        <h3 style={{ marginTop: 0, fontSize: "var(--font-size-md)" }}>Historial de despliegues</h3>
        <DataTable
          rows={despliegues}
          keyField={(d) => d.id}
          vacio="No hay despliegues registrados todavía."
          columns={[
            { header: "Fecha", render: (d) => new Date(d.desplegado_en).toLocaleString() },
            { header: "Componente", render: (d) => d.componente },
            { header: "Versión", render: (d) => d.version },
            { header: "Notas", render: (d) => d.notas || "—" },
          ]}
        />
      </Card>
    </div>
  );
}
