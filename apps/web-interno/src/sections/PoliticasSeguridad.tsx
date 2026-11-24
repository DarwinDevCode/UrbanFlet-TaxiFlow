import { ApiError, Card, ReadOnlyActions, TextField, apiFetch, fieldError, useReadOnlyGate } from "@urbanflet/shared-ui";
import { useEffect, useState } from "react";

interface PoliticaSeguridadOut {
  id: string | null;
  access_token_minutos: number;
  refresh_token_dias: number;
  refresh_umbral_fallos: number;
  refresh_ventana_minutos: number;
  rbac_umbral_denegaciones: number;
  rbac_ventana_minutos: number;
  rbac_suspension_minutos: number;
  vigente_desde: string | null;
  vigente_hasta: string | null;
}

export function SeccionPoliticasSeguridad() {
  const [vigente, setVigente] = useState<PoliticaSeguridadOut | null>(null);
  const [accessMinutos, setAccessMinutos] = useState(15);
  const [refreshDias, setRefreshDias] = useState(30);
  const [refreshUmbral, setRefreshUmbral] = useState(3);
  const [refreshVentana, setRefreshVentana] = useState(15);
  const [rbacUmbral, setRbacUmbral] = useState(5);
  const [rbacVentana, setRbacVentana] = useState(10);
  const [rbacSuspension, setRbacSuspension] = useState(30);
  const [error, setError] = useState<unknown>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);
  const { editando, editar, bloquear } = useReadOnlyGate();

  const aplicarValores = (datos: PoliticaSeguridadOut) => {
    setVigente(datos);
    setAccessMinutos(datos.access_token_minutos);
    setRefreshDias(datos.refresh_token_dias);
    setRefreshUmbral(datos.refresh_umbral_fallos);
    setRefreshVentana(datos.refresh_ventana_minutos);
    setRbacUmbral(datos.rbac_umbral_denegaciones);
    setRbacVentana(datos.rbac_ventana_minutos);
    setRbacSuspension(datos.rbac_suspension_minutos);
  };

  const cargar = async () => aplicarValores(await apiFetch<PoliticaSeguridadOut>("/seguridad/politica-seguridad"));

  useEffect(() => {
    cargar().catch(setError);
  }, []);

  const cancelar = () => {
    setError(null);
    if (vigente) aplicarValores(vigente);
    bloquear();
  };

  const publicar = async () => {
    setError(null);
    setOk(null);
    setCargando(true);
    try {
      await apiFetch("/seguridad/politica-seguridad", {
        method: "POST",
        body: {
          access_token_minutos: accessMinutos,
          refresh_token_dias: refreshDias,
          refresh_umbral_fallos: refreshUmbral,
          refresh_ventana_minutos: refreshVentana,
          rbac_umbral_denegaciones: rbacUmbral,
          rbac_ventana_minutos: rbacVentana,
          rbac_suspension_minutos: rbacSuspension,
          vigente_desde: new Date().toISOString(),
        },
      });
      setOk("Política publicada. Aplica de inmediato a las próximas sesiones y peticiones.");
      await cargar();
      bloquear();
    } catch (e) {
      setError(e);
    } finally {
      setCargando(false);
    }
  };

  const mensajeGeneral =
    error instanceof ApiError ? error.message : error ? "No se pudo completar la operación" : null;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
      <Card>
        <h2 style={{ marginTop: 0, fontSize: "var(--font-size-lg)" }}>Políticas de seguridad</h2>
        <p style={{ color: "var(--color-text-muted)" }}>
          {vigente?.id
            ? `Publicada — vigente desde ${vigente.vigente_desde ? new Date(vigente.vigente_desde).toLocaleString() : "—"}.`
            : "Nunca se publicó una política — rigen los valores por defecto del sistema."}
        </p>
        <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>
          Gobierna la vida útil de los tokens de sesión y los 3 mecanismos de bloqueo por intentos ya existentes en
          el sistema (refrescar sesión y denegaciones de permisos — el bloqueo por login incorrecto se configura
          aparte, en "Políticas de autenticación"). No hay un limitador genérico por endpoint: solo estos 3
          mecanismos puntuales. Cambios aquí son de alto impacto y quedan auditados. Los campos quedan bloqueados
          hasta pulsar "Editar", para evitar un cambio accidental en configuración crítica.
        </p>
      </Card>

      <Card>
        {mensajeGeneral && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{mensajeGeneral}</p>}
        {ok && <p style={{ color: "var(--color-success)", fontSize: "var(--font-size-sm)" }}>{ok}</p>}

        <h3 style={{ fontSize: "var(--font-size-md)" }}>Tokens de sesión</h3>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "var(--space-3)" }}>
          <TextField label="Vida del access token (minutos)" type="number" min={1} max={1440} disabled={!editando} value={accessMinutos} onChange={(e) => setAccessMinutos(Number(e.target.value))} error={fieldError(error, "access_token_minutos")} />
          <TextField label="Vida del refresh token (días)" type="number" min={1} max={365} disabled={!editando} value={refreshDias} onChange={(e) => setRefreshDias(Number(e.target.value))} error={fieldError(error, "refresh_token_dias")} />
        </div>

        <h3 style={{ fontSize: "var(--font-size-md)", marginTop: "var(--space-4)" }}>Bloqueo al refrescar sesión</h3>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "var(--space-3)" }}>
          <TextField label="Umbral de fallos" type="number" min={3} max={20} disabled={!editando} value={refreshUmbral} onChange={(e) => setRefreshUmbral(Number(e.target.value))} error={fieldError(error, "refresh_umbral_fallos")} />
          <TextField label="Ventana (minutos)" type="number" min={1} max={180} disabled={!editando} value={refreshVentana} onChange={(e) => setRefreshVentana(Number(e.target.value))} error={fieldError(error, "refresh_ventana_minutos")} />
        </div>

        <h3 style={{ fontSize: "var(--font-size-md)", marginTop: "var(--space-4)" }}>Suspensión por denegaciones de permisos</h3>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "var(--space-3)" }}>
          <TextField label="Umbral de denegaciones" type="number" min={3} max={20} disabled={!editando} value={rbacUmbral} onChange={(e) => setRbacUmbral(Number(e.target.value))} error={fieldError(error, "rbac_umbral_denegaciones")} />
          <TextField label="Ventana (minutos)" type="number" min={1} max={180} disabled={!editando} value={rbacVentana} onChange={(e) => setRbacVentana(Number(e.target.value))} error={fieldError(error, "rbac_ventana_minutos")} />
          <TextField label="Duración de la suspensión (minutos)" type="number" min={1} max={1440} disabled={!editando} value={rbacSuspension} onChange={(e) => setRbacSuspension(Number(e.target.value))} error={fieldError(error, "rbac_suspension_minutos")} />
        </div>

        <div style={{ marginTop: "var(--space-4)" }}>
          <ReadOnlyActions
            editando={editando}
            onEditar={editar}
            onCancelar={cancelar}
            onGuardar={publicar}
            guardarLabel="Publicar política"
            guardarLoading={cargando}
          />
        </div>
      </Card>
    </div>
  );
}
