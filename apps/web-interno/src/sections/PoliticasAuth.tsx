import { ApiError, Card, ReadOnlyActions, TextField, apiFetch, fieldError, useReadOnlyGate } from "@urbanflet/shared-ui";
import { useEffect, useState } from "react";

interface PoliticaAuthOut {
  id: string | null;
  longitud_minima_password: number;
  umbral_intentos_fallidos: number;
  ventana_minutos: number;
  bloqueo_minutos: number;
  vencimiento_dias_alto_privilegio: number | null;
  vigente_desde: string | null;
  vigente_hasta: string | null;
}

export function SeccionPoliticasAuth() {
  const [vigente, setVigente] = useState<PoliticaAuthOut | null>(null);
  const [longitud, setLongitud] = useState(8);
  const [umbral, setUmbral] = useState(5);
  const [ventana, setVentana] = useState(15);
  const [bloqueo, setBloqueo] = useState(15);
  const [vencimiento, setVencimiento] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);
  const { editando, editar, bloquear } = useReadOnlyGate();

  const aplicarValores = (datos: PoliticaAuthOut) => {
    setVigente(datos);
    setLongitud(datos.longitud_minima_password);
    setUmbral(datos.umbral_intentos_fallidos);
    setVentana(datos.ventana_minutos);
    setBloqueo(datos.bloqueo_minutos);
    setVencimiento(datos.vencimiento_dias_alto_privilegio ? String(datos.vencimiento_dias_alto_privilegio) : "");
  };

  const cargar = async () => aplicarValores(await apiFetch<PoliticaAuthOut>("/seguridad/politica-auth"));

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
      await apiFetch("/seguridad/politica-auth", {
        method: "POST",
        body: {
          longitud_minima_password: longitud,
          umbral_intentos_fallidos: umbral,
          ventana_minutos: ventana,
          bloqueo_minutos: bloqueo,
          vencimiento_dias_alto_privilegio: vencimiento ? Number(vencimiento) : null,
          vigente_desde: new Date().toISOString(),
        },
      });
      setOk("Política publicada. Aplica de inmediato a los próximos inicios de sesión.");
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
        <h2 style={{ marginTop: 0, fontSize: "var(--font-size-lg)" }}>Política de autenticación vigente</h2>
        <p style={{ color: "var(--color-text-muted)" }}>
          {vigente?.id
            ? `Publicada — vigente desde ${vigente.vigente_desde ? new Date(vigente.vigente_desde).toLocaleString() : "—"}.`
            : "Nunca se publicó una política — rigen los valores por defecto del sistema."}
        </p>
        <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>
          Un cambio aquí endurece o relaja la longitud mínima de contraseña y el bloqueo por intentos fallidos de
          <strong> todo el sistema</strong> (pasajeros, conductores y personal interno) — no solo de una cuenta.
          Cualquier publicación queda auditada en la bitácora. Los campos quedan bloqueados hasta pulsar "Editar",
          para evitar un cambio accidental en configuración crítica.
        </p>
      </Card>

      <Card>
        {mensajeGeneral && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{mensajeGeneral}</p>}
        {ok && <p style={{ color: "var(--color-success)", fontSize: "var(--font-size-sm)" }}>{ok}</p>}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "var(--space-3)" }}>
          <TextField
            label="Longitud mínima de contraseña"
            type="number"
            min={6}
            max={64}
            disabled={!editando}
            value={longitud}
            onChange={(e) => setLongitud(Number(e.target.value))}
            error={fieldError(error, "longitud_minima_password")}
          />
          <TextField
            label="Umbral de intentos fallidos"
            type="number"
            min={3}
            max={20}
            disabled={!editando}
            value={umbral}
            onChange={(e) => setUmbral(Number(e.target.value))}
            error={fieldError(error, "umbral_intentos_fallidos")}
          />
          <TextField
            label="Ventana de conteo (minutos)"
            type="number"
            min={1}
            max={180}
            disabled={!editando}
            value={ventana}
            onChange={(e) => setVentana(Number(e.target.value))}
            error={fieldError(error, "ventana_minutos")}
          />
          <TextField
            label="Duración del bloqueo (minutos)"
            type="number"
            min={1}
            max={1440}
            disabled={!editando}
            value={bloqueo}
            onChange={(e) => setBloqueo(Number(e.target.value))}
            error={fieldError(error, "bloqueo_minutos")}
          />
          <TextField
            label="Vencimiento de contraseña para roles de alto privilegio (días, vacío = sin vencimiento)"
            type="number"
            min={1}
            max={3650}
            disabled={!editando}
            value={vencimiento}
            onChange={(e) => setVencimiento(e.target.value)}
            error={fieldError(error, "vencimiento_dias_alto_privilegio")}
          />
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
