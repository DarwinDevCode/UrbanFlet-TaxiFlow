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
  Select,
  TextArea,
  TabButton,
  TextField,
  useAuth,
} from "@urbanflet/shared-ui";
import { useEffect, useState } from "react";

interface Respaldo {
  id: string;
  motor: "mongo" | "clickhouse";
  estado: "en_progreso" | "completado" | "error";
  ts_inicio: string;
  ts_fin: string | null;
  duracion_segundos: number | null;
  tamano_bytes: number | null;
  hash_sha256: string | null;
  colecciones: string[] | null;
  error_detalle: string | null;
  disparado_por: string;
}

interface Restauracion {
  id: string;
  respaldo_id: string;
  motor: "mongo" | "clickhouse";
  estado: "en_progreso" | "completado" | "error";
  base_destino: string;
  ts_inicio: string;
  ts_fin: string | null;
  duracion_segundos: number | null;
  conteos: Record<string, number> | null;
  error_detalle: string | null;
}

interface PlanDrItem {
  dominio: string;
  rto: string;
  rpo: string;
  notas: string;
  actualizado_en: string | null;
  actualizado_por: string | null;
}

interface Simulacro {
  id: string;
  fecha: string;
  resultado: "exitoso" | "parcial" | "fallido";
  notas: string;
  registrado_por: string;
  registrado_en: string;
}

const NOMBRE_MOTOR: Record<Respaldo["motor"], string> = { mongo: "MongoDB", clickhouse: "ClickHouse" };
const NOMBRE_DOMINIO: Record<string, string> = {
  captacion: "Captación",
  operaciones_despacho: "Operaciones y Despacho",
  flota: "Flota",
  mantenimiento: "Mantenimiento",
  finanzas: "Finanzas",
  cumplimiento: "Cumplimiento",
  plataforma: "Plataforma",
};

const tonoEstado: Record<Respaldo["estado"], "neutral" | "exito" | "advertencia" | "peligro"> = {
  en_progreso: "advertencia",
  completado: "exito",
  error: "peligro",
};

function formatearTamano(bytes: number | null): string {
  if (bytes === null) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

type Pestana = "respaldos" | "continuidad";

function SeccionRespaldos() {
  const [respaldos, setRespaldos] = useState<Respaldo[]>([]);
  const [restauraciones, setRestauraciones] = useState<Restauracion[]>([]);
  const [seleccionado, setSeleccionado] = useState<Respaldo | null>(null);
  const [verificacion, setVerificacion] = useState<{ integro: boolean; hash_calculado: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);
  const [disparando, setDisparando] = useState(false);

  const cargar = async () => {
    setError(null);
    try {
      const [r, rr] = await Promise.all([
        apiFetch<Respaldo[]>("/respaldos"),
        apiFetch<Restauracion[]>("/respaldos/restauraciones"),
      ]);
      setRespaldos(r);
      setRestauraciones(rr);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo cargar el historial de respaldos");
    }
  };

  useEffect(() => {
    cargar();
  }, []);

  const disparar = async () => {
    setError(null);
    setDisparando(true);
    try {
      await apiFetch("/respaldos", { method: "POST" });
      await cargar();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo disparar el respaldo");
    } finally {
      setDisparando(false);
    }
  };

  const abrirDetalle = (r: Respaldo) => {
    setSeleccionado(r);
    setVerificacion(null);
    setError(null);
  };

  const verificar = async () => {
    if (!seleccionado) return;
    setError(null);
    setCargando(true);
    try {
      const resultado = await apiFetch<{ integro: boolean; hash_calculado: string }>(
        `/respaldos/${seleccionado.id}/verificar`,
        { method: "POST" },
      );
      setVerificacion(resultado);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo verificar el respaldo");
    } finally {
      setCargando(false);
    }
  };

  const restaurar = async () => {
    if (!seleccionado) return;
    setError(null);
    setCargando(true);
    try {
      await apiFetch(`/respaldos/${seleccionado.id}/restaurar`, { method: "POST" });
      setSeleccionado(null);
      await cargar();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo iniciar la restauración");
    } finally {
      setCargando(false);
    }
  };

  return (
    <Card>
      <h3 style={{ marginTop: 0, fontSize: "var(--font-size-md)" }}>Respaldos</h3>
      <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>
        Exportación real de los datos de MongoDB y ClickHouse. Corre siempre contra las bases de este entorno
        de desarrollo. Cifrado en reposo: <strong>no implementado</strong> en este entorno.
      </p>
      {/* "Eliminar"/"Buscar" quitados (segunda pasada, punto 1): un respaldo
          no se elimina desde esta interfaz y la lista no pagina -- ningún
          rol tiene un uso real para ninguno de los dos acá. */}
      <ActionBar
        nuevo={{ onClick: disparar, disabled: disparando }}
        actualizar={{ onClick: () => cargar() }}
        salir={{ onClick: () => setSeleccionado(null) }}
      />
      {error && !seleccionado && (
        <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)", marginTop: "var(--space-3)" }}>
          {error}
        </p>
      )}
      <div style={{ marginTop: "var(--space-3)" }}>
        <DataTable
          rows={respaldos}
          keyField={(r) => r.id}
          vacio="Sin respaldos todavía. Usa 'Nuevo' para disparar uno real."
          columns={[
            { header: "Motor", render: (r) => NOMBRE_MOTOR[r.motor] },
            { header: "Estado", render: (r) => <Badge texto={r.estado.toUpperCase()} tono={tonoEstado[r.estado]} /> },
            { header: "Inicio", render: (r) => new Date(r.ts_inicio).toLocaleString() },
            { header: "Duración", render: (r) => (r.duracion_segundos !== null ? `${r.duracion_segundos.toFixed(1)} s` : "—") },
            { header: "Tamaño", render: (r) => formatearTamano(r.tamano_bytes) },
            { header: "Detalle", render: (r) => <Button variant="secondary" onClick={() => abrirDetalle(r)}>Ver</Button> },
          ]}
        />
      </div>

      <h3 style={{ fontSize: "var(--font-size-md)", marginTop: "var(--space-5)" }}>Restauraciones de prueba</h3>
      <div style={{ marginTop: "var(--space-3)" }}>
        <DataTable
          rows={restauraciones}
          keyField={(r) => r.id}
          vacio="Sin restauraciones todavía."
          columns={[
            { header: "Motor", render: (r) => NOMBRE_MOTOR[r.motor] },
            { header: "Base destino", render: (r) => r.base_destino },
            { header: "Estado", render: (r) => <Badge texto={r.estado.toUpperCase()} tono={tonoEstado[r.estado]} /> },
            {
              header: "Conteos",
              render: (r) =>
                r.conteos ? Object.entries(r.conteos).map(([k, v]) => `${k}: ${v}`).join(", ") : "—",
            },
          ]}
        />
      </div>

      {seleccionado && (
        <DetailPanel
          titulo={`Respaldo ${NOMBRE_MOTOR[seleccionado.motor]} — ${new Date(seleccionado.ts_inicio).toLocaleString()}`}
          modo="consulta"
          onSalir={() => setSeleccionado(null)}
          accionesExtra={
            <>
              <div style={{ minWidth: 140 }}>
                <Button variant="secondary" onClick={verificar} loading={cargando}>Verificar integridad</Button>
              </div>
              {seleccionado.estado === "completado" && (
                <div style={{ minWidth: 140 }}>
                  <Button onClick={restaurar} loading={cargando}>Restaurar en base de prueba</Button>
                </div>
              )}
            </>
          }
        >
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
            {error && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</p>}
            <DetailField label="Estado" value={<Badge texto={seleccionado.estado.toUpperCase()} tono={tonoEstado[seleccionado.estado]} />} />
            <DetailField label="Hash SHA-256" value={seleccionado.hash_sha256 ?? "—"} />
            <DetailField label="Colecciones/tablas incluidas" value={seleccionado.colecciones?.join(", ") ?? "—"} />
            {seleccionado.error_detalle && <DetailField label="Detalle del error" value={seleccionado.error_detalle} />}
            <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>
              Restaurar solo escribe en una base de prueba aislada ({seleccionado.motor === "mongo" ? "urbanflet_restore_test" : "urbanflet_gold_restore_test"}) — nunca en la base real de la cooperativa.
            </p>
            {verificacion && (
              <p style={{ color: verificacion.integro ? "var(--color-success)" : "var(--color-danger)", fontWeight: 600 }}>
                {verificacion.integro ? "Íntegro: el hash coincide." : "Corrompido: el hash no coincide."}
              </p>
            )}
          </div>
        </DetailPanel>
      )}
    </Card>
  );
}

function SeccionPlanContinuidad() {
  const [plan, setPlan] = useState<PlanDrItem[]>([]);
  const [simulacros, setSimulacros] = useState<Simulacro[]>([]);
  const [seleccionado, setSeleccionado] = useState<PlanDrItem | null>(null);
  const [rto, setRto] = useState("");
  const [rpo, setRpo] = useState("");
  const [notas, setNotas] = useState("");
  const [nuevoSimulacro, setNuevoSimulacro] = useState(false);
  const [fechaSimulacro, setFechaSimulacro] = useState("");
  const [resultadoSimulacro, setResultadoSimulacro] = useState<"exitoso" | "parcial" | "fallido">("exitoso");
  const [notasSimulacro, setNotasSimulacro] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);

  const cargar = async () => {
    setError(null);
    try {
      const [p, s] = await Promise.all([
        apiFetch<PlanDrItem[]>("/respaldos/plan-dr"),
        apiFetch<Simulacro[]>("/respaldos/simulacros"),
      ]);
      setPlan(p);
      setSimulacros(s);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo cargar el plan de continuidad");
    }
  };

  useEffect(() => {
    cargar();
  }, []);

  const abrirEdicion = (item: PlanDrItem) => {
    setSeleccionado(item);
    setRto(item.rto);
    setRpo(item.rpo);
    setNotas(item.notas);
    setError(null);
  };

  const guardar = async () => {
    if (!seleccionado) return;
    setError(null);
    setCargando(true);
    try {
      await apiFetch(`/respaldos/plan-dr/${seleccionado.dominio}`, { method: "PUT", body: { rto, rpo, notas } });
      setSeleccionado(null);
      await cargar();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo guardar el plan");
    } finally {
      setCargando(false);
    }
  };

  const registrarSimulacro = async () => {
    setError(null);
    setCargando(true);
    try {
      await apiFetch("/respaldos/simulacros", {
        method: "POST",
        body: { fecha: fechaSimulacro, resultado: resultadoSimulacro, notas: notasSimulacro },
      });
      setNuevoSimulacro(false);
      setFechaSimulacro("");
      setResultadoSimulacro("exitoso");
      setNotasSimulacro("");
      await cargar();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo registrar el simulacro");
    } finally {
      setCargando(false);
    }
  };

  return (
    <>
      <Card>
        <h3 style={{ marginTop: 0, fontSize: "var(--font-size-md)" }}>RTO / RPO por dominio</h3>
        <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>
          Tiempo objetivo de recuperación (RTO) y pérdida de datos aceptable (RPO) por dominio de negocio.
        </p>
        {error && !seleccionado && (
          <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</p>
        )}
        <div style={{ marginTop: "var(--space-3)" }}>
          <DataTable
            rows={plan}
            keyField={(p) => p.dominio}
            vacio="Sin datos."
            columns={[
              { header: "Dominio", render: (p) => NOMBRE_DOMINIO[p.dominio] ?? p.dominio },
              { header: "RTO", render: (p) => p.rto || "—" },
              { header: "RPO", render: (p) => p.rpo || "—" },
              { header: "Detalle", render: (p) => <Button variant="secondary" onClick={() => abrirEdicion(p)}>Editar</Button> },
            ]}
          />
        </div>
      </Card>

      <Card>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h3 style={{ margin: 0, fontSize: "var(--font-size-md)" }}>Simulacros de recuperación</h3>
          <div style={{ minWidth: 160 }}>
            <Button variant="secondary" onClick={() => setNuevoSimulacro(true)}>Registrar simulacro</Button>
          </div>
        </div>
        <div style={{ marginTop: "var(--space-3)" }}>
          <DataTable
            rows={simulacros}
            keyField={(s) => s.id}
            vacio="Sin simulacros registrados todavía."
            columns={[
              { header: "Fecha", render: (s) => new Date(s.fecha).toLocaleDateString() },
              { header: "Resultado", render: (s) => <Badge texto={s.resultado.toUpperCase()} tono={s.resultado === "exitoso" ? "exito" : s.resultado === "parcial" ? "advertencia" : "peligro"} /> },
              { header: "Notas", render: (s) => s.notas },
            ]}
          />
        </div>
      </Card>

      {seleccionado && (
        <DetailPanel
          titulo={`Plan de continuidad — ${NOMBRE_DOMINIO[seleccionado.dominio] ?? seleccionado.dominio}`}
          modo="edicion"
          onSalir={() => setSeleccionado(null)}
          onAceptar={guardar}
          aceptarLabel="Guardar"
          aceptarDisabled={!rto || !rpo}
          aceptarLoading={cargando}
        >
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
            {error && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</p>}
            <TextField label="RTO (tiempo objetivo de recuperación)" value={rto} onChange={(e) => setRto(e.target.value)} />
            <TextField label="RPO (pérdida de datos aceptable)" value={rpo} onChange={(e) => setRpo(e.target.value)} />
            <TextArea label="Notas" value={notas} onChange={(e) => setNotas(e.target.value)} />
          </div>
        </DetailPanel>
      )}

      {nuevoSimulacro && (
        <DetailPanel
          titulo="Registrar simulacro de recuperación"
          modo="nuevo"
          onSalir={() => setNuevoSimulacro(false)}
          onAceptar={registrarSimulacro}
          aceptarLabel="Registrar"
          aceptarDisabled={!fechaSimulacro || !notasSimulacro}
          aceptarLoading={cargando}
        >
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
            {error && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</p>}
            <TextField label="Fecha" type="datetime-local" value={fechaSimulacro} onChange={(e) => setFechaSimulacro(e.target.value)} />
            <Select
              label="Resultado"
              value={resultadoSimulacro}
              onChange={(e) => setResultadoSimulacro(e.target.value as typeof resultadoSimulacro)}
              options={[
                { value: "exitoso", label: "Exitoso" },
                { value: "parcial", label: "Parcial" },
                { value: "fallido", label: "Fallido" },
              ]}
            />
            <TextArea label="Notas" value={notasSimulacro} onChange={(e) => setNotasSimulacro(e.target.value)} />
          </div>
        </DetailPanel>
      )}
    </>
  );
}

export function SeccionRespaldosYContinuidad() {
  const { actor } = useAuth();
  // 7.1 (respaldos técnicos) es exclusivo de admin_sistema en el backend;
  // 7.2 (plan de continuidad) acepta admin_sistema o gerencia (única
  // excepción de la spec). Un actor solo-gerencia no debe ver una pestaña
  // que el backend le va a rechazar con 403 -- se oculta directamente.
  const puedeVerRespaldos = actor?.roles.includes("admin_sistema") ?? false;
  const [pestana, setPestana] = useState<Pestana>(puedeVerRespaldos ? "respaldos" : "continuidad");

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
      <Card>
        <h2 style={{ marginTop: 0, fontSize: "var(--font-size-lg)" }}>Respaldos y continuidad</h2>
        <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>
          Respaldo/restauración de prueba de MongoDB y ClickHouse, y plan de recuperación ante desastres.
        </p>
      </Card>

      {puedeVerRespaldos && (
        <div style={{ display: "flex", gap: "var(--space-2)" }}>
          <TabButton activa={pestana === "respaldos"} onClick={() => setPestana("respaldos")}>Respaldos</TabButton>
          <TabButton activa={pestana === "continuidad"} onClick={() => setPestana("continuidad")}>Plan de continuidad</TabButton>
        </div>
      )}

      {pestana === "respaldos" && puedeVerRespaldos && <SeccionRespaldos />}
      {pestana === "continuidad" && <SeccionPlanContinuidad />}
    </div>
  );
}
