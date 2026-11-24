import { useEffect, useState, type ReactNode } from "react";
import { apiFetch, ApiError, fieldError } from "../api/client";
import { nombreRol } from "../roles";
import { Avatar } from "./Avatar";
import { Badge } from "./Badge";
import { Button } from "./Button";
import { Card } from "./Card";
import { PasswordField } from "./PasswordField";
import { ReadOnlyActions, useReadOnlyGate } from "./ReadOnlyGate";
import { TextField } from "./TextField";

interface PerfilOut {
  id: string;
  nombre: string;
  telefono: string | null;
  email: string | null;
  roles: string[];
  fecha_registro: string;
  foto_url: string | null;
}

interface SesionOut {
  jti: string;
  ip: string | null;
  dispositivo: string | null;
  ts_inicio: string | null;
}

/** Sección "Mi perfil"/"Mi cuenta" — Sección 1.3/2.2/3.1 de
 * `specs/specs-administrativas/ux_complementaria.md`. Componente único
 * reutilizado por las 3 apps (pasajero/conductor/interno): edita contacto
 * propio (nunca roles), exige contraseña actual en vez de OTP (decisión D1
 * del plan — sin OTP disponible en el sistema), muestra sesiones activas
 * con cierre remoto. Siempre muestra la foto de perfil propia (de solo
 * lectura acá — cambiarla es autoservicio de bajo riesgo, vive en "Ajustes"
 * vía `AjustesPropios`, no exige contraseña como el resto de este
 * formulario). `extra` es un slot para contenido adicional específico de
 * cada app sin bifurcar el componente. */
export function PerfilPropio({ extra }: { extra?: ReactNode }) {
  const [perfil, setPerfil] = useState<PerfilOut | null>(null);
  const [sesiones, setSesiones] = useState<SesionOut[]>([]);
  const [nombre, setNombre] = useState("");
  const [telefono, setTelefono] = useState("");
  const [email, setEmail] = useState("");
  const [passwordActual, setPasswordActual] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);
  const { editando, editar, bloquear } = useReadOnlyGate();

  const aplicarValores = (datos: PerfilOut) => {
    setPerfil(datos);
    setNombre(datos.nombre);
    setTelefono(datos.telefono ?? "");
    setEmail(datos.email ?? "");
  };

  const cargar = async () => {
    const [datosPerfil, datosSesiones] = await Promise.all([
      apiFetch<PerfilOut>("/perfil"),
      apiFetch<SesionOut[]>("/perfil/sesiones"),
    ]);
    aplicarValores(datosPerfil);
    setSesiones(datosSesiones);
  };

  useEffect(() => {
    cargar().catch(setError);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const cancelar = () => {
    setError(null);
    setPasswordActual("");
    if (perfil) aplicarValores(perfil);
    bloquear();
  };

  const guardar = async () => {
    setError(null);
    setOk(null);
    setCargando(true);
    try {
      const datos = await apiFetch<PerfilOut>("/perfil", {
        method: "PATCH",
        body: {
          nombre,
          telefono: telefono || undefined,
          email: email || undefined,
          password_actual: passwordActual,
        },
      });
      aplicarValores(datos);
      setPasswordActual("");
      setOk("Datos actualizados.");
      bloquear();
    } catch (e) {
      setError(e);
    } finally {
      setCargando(false);
    }
  };

  const cerrarSesion = async (jti: string) => {
    setError(null);
    try {
      await apiFetch(`/perfil/sesiones/${jti}`, { method: "DELETE" });
      setSesiones((prev) => prev.filter((s) => s.jti !== jti));
    } catch (e) {
      setError(e);
    }
  };

  const mensajeGeneral =
    error instanceof ApiError ? error.message : error ? "No se pudo completar la operación" : null;

  if (!perfil) {
    return (
      <Card>
        <p style={{ color: "var(--color-text-muted)" }}>Cargando…</p>
      </Card>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
      <Card>
        <h2 style={{ marginTop: 0, fontSize: "var(--font-size-lg)" }}>Mi cuenta</h2>
        <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>
          Edita tu nombre, teléfono o correo. Cualquier cambio exige tu contraseña actual y queda registrado. Nunca
          puedes cambiar tu propio rol desde aquí.
        </p>
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)", marginTop: "var(--space-2)" }}>
          <Avatar fotoUrl={perfil.foto_url} nombre={perfil.nombre} tamano={48} />
          <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-2)" }}>
            {perfil.roles.map((r) => (
              <Badge key={r} texto={nombreRol(r)} tono="neutral" />
            ))}
          </div>
        </div>
      </Card>

      <Card>
        {mensajeGeneral && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{mensajeGeneral}</p>}
        {ok && <p style={{ color: "var(--color-success)", fontSize: "var(--font-size-sm)" }}>{ok}</p>}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "var(--space-3)" }}>
          <TextField
            label="Nombre"
            disabled={!editando}
            value={nombre}
            onChange={(e) => setNombre(e.target.value)}
            error={fieldError(error, "nombre")}
          />
          <TextField
            label="Teléfono"
            disabled={!editando}
            value={telefono}
            onChange={(e) => setTelefono(e.target.value)}
            error={fieldError(error, "telefono")}
          />
          <TextField
            label="Correo"
            disabled={!editando}
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            error={fieldError(error, "email")}
          />
          {editando && (
            <PasswordField
              label="Contraseña actual (para confirmar el cambio)"
              value={passwordActual}
              onChange={(e) => setPasswordActual(e.target.value)}
              error={fieldError(error, "password_actual")}
            />
          )}
        </div>
        <div style={{ marginTop: "var(--space-4)" }}>
          <ReadOnlyActions
            editando={editando}
            onEditar={editar}
            onCancelar={cancelar}
            onGuardar={guardar}
            guardarDisabled={!nombre || !passwordActual}
            guardarLoading={cargando}
          />
        </div>
      </Card>

      {extra}

      <Card>
        <h3 style={{ marginTop: 0, fontSize: "var(--font-size-md)" }}>Eliminar mi cuenta</h3>
        <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>
          Eliminar tu cuenta borra tu nombre, teléfono y correo real de forma irreversible (derechos ARCO/LOPDP).
          Es una acción que hoy solo puede ejecutar el Administrador del Sistema, no un autoservicio total — escribe
          a soporte (ver Centro de ayuda) indicando el número o correo de tu cuenta para iniciar el proceso.
        </p>
      </Card>

      <Card>
        <h3 style={{ marginTop: 0, fontSize: "var(--font-size-md)" }}>Sesiones activas</h3>
        <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>
          Dispositivos donde tu cuenta tiene una sesión abierta ahora mismo. Cerrar una sesión que no reconoces la
          desconecta de inmediato.
        </p>
        {sesiones.length === 0 ? (
          <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>Sin sesiones activas.</p>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)", marginTop: "var(--space-3)" }}>
            {sesiones.map((s) => (
              <div
                key={s.jti}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  gap: "var(--space-2)",
                  padding: "var(--space-2) var(--space-3)",
                  border: "1px solid var(--color-border)",
                  borderRadius: "var(--radius-sm)",
                }}
              >
                <div>
                  <div style={{ fontSize: "var(--font-size-sm)", fontWeight: 600 }}>{s.dispositivo ?? "Dispositivo desconocido"}</div>
                  <div style={{ fontSize: "var(--font-size-sm)", color: "var(--color-text-muted)" }}>
                    {s.ip ?? "IP desconocida"} · {s.ts_inicio ? new Date(s.ts_inicio).toLocaleString() : "—"}
                  </div>
                </div>
                <div style={{ minWidth: 140 }}>
                  <Button variant="danger" onClick={() => cerrarSesion(s.jti)}>
                    Cerrar sesión
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
