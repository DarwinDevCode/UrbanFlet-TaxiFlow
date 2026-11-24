import { useEffect, useState, type ReactNode } from "react";
import { apiFetch, ApiError, subirArchivo } from "../api/client";
import { useAuth } from "../auth/AuthProvider";
import { aplicarDensidad } from "../densidad";
import { aplicarSidebarTono } from "../sidebarTono";
import { aplicarTamanoTexto } from "../tamanoTexto";
import { aplicarTema } from "../theme";
import { Avatar } from "./Avatar";
import { Button } from "./Button";
import { FileField } from "./FileField";
import { Card } from "./Card";
import { Select } from "./Select";
import { TextField } from "./TextField";

const TIPOS_FOTO_ACEPTADOS = "image/jpeg,image/png,image/webp";

interface PerfilFotoOut {
  foto_url: string | null;
}

/** Ronda de foto de perfil: sección de "Ajustes" para ver/cambiar/quitar la
 * foto propia -- deliberadamente separada de "Mi cuenta" (`PerfilPropio`),
 * que exige contraseña actual para cualquier cambio (decisión D1, pensada
 * para contacto -- teléfono/correo -- no para una foto). Lee/actualiza
 * `useAuth().fotoUrl` en vez de mantener su propio estado: así el header de
 * `AppShell` (un componente hermano, no un padre/hijo de este) refleja el
 * cambio de inmediato, sin recargar la página. */
function SeccionFotoPerfil() {
  const { fotoUrl, actualizarFoto } = useAuth();
  const [error, setError] = useState<unknown>(null);
  const [subiendo, setSubiendo] = useState(false);

  const cambiarFoto = async (file: File) => {
    setError(null);
    setSubiendo(true);
    try {
      const archivo = await subirArchivo(file, "foto_perfil");
      await apiFetch<PerfilFotoOut>("/perfil/foto", { method: "PATCH", body: { archivo_id: archivo.id } });
      actualizarFoto(archivo.id);
    } catch (e) {
      setError(e);
    } finally {
      setSubiendo(false);
    }
  };

  const quitarFoto = async () => {
    setError(null);
    setSubiendo(true);
    try {
      await apiFetch<PerfilFotoOut>("/perfil/foto", { method: "PATCH", body: { archivo_id: null } });
      actualizarFoto(null);
    } catch (e) {
      setError(e);
    } finally {
      setSubiendo(false);
    }
  };

  const mensaje = error instanceof ApiError ? error.message : error ? "No se pudo actualizar la foto" : null;

  return (
    <Card>
      <h3 style={{ marginTop: 0, fontSize: "var(--font-size-md)" }}>Foto de perfil</h3>
      <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>
        Se muestra junto a tu nombre en el sistema. Formatos aceptados: JPG, PNG o WEBP, hasta 5 MB.
      </p>
      {mensaje && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{mensaje}</p>}
      <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
        <Avatar fotoUrl={fotoUrl} tamano={64} />
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)", alignItems: "flex-start" }}>
          {/* Mismo componente compartido que el resto de campos de archivo del
              sistema. `mostrarNombre` apagado: el avatar de al lado ya se
              actualiza al instante, el nombre del archivo sobraría. */}
          <FileField
            textoBoton="Cambiar foto"
            accept={TIPOS_FOTO_ACEPTADOS}
            disabled={subiendo}
            mostrarNombre={false}
            onChange={(e) => {
              const file = e.target.files?.[0];
              e.target.value = "";
              if (file) cambiarFoto(file);
            }}
          />
          {subiendo && (
            <span style={{ fontSize: "var(--font-size-sm)", color: "var(--color-text-muted)" }}>Subiendo…</span>
          )}
          {fotoUrl && !subiendo && (
            <Button variant="danger" onClick={quitarFoto}>
              Quitar foto
            </Button>
          )}
        </div>
      </div>
    </Card>
  );
}

/** Autoservicio de baja de cuenta con periodo de gracia de 30 días.
 *
 * NO es la anonimización de datos personales (CU-O17 A2): esa la ejecuta un
 * administrador desde Gobernanza de Datos escribiendo "ANONIMIZAR", es
 * irreversible y borra datos personales por obligación legal. Esto es un
 * cierre voluntario de la propia cuenta, con 30 días para arrepentirse. Los
 * dos mecanismos conviven por separado a propósito.
 */
function SeccionBajaCuenta() {
  const { diasRestantesBaja, actualizarBajaCuenta } = useAuth();
  const [confirmando, setConfirmando] = useState(false);
  const [motivo, setMotivo] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<unknown>(null);
  // Caso borde 2: placas que saldrán de la flota al vencer el plazo. Las
  // devuelve el backend al confirmar (advertencia, nunca un bloqueo).
  const [vehiculosARetirar, setVehiculosARetirar] = useState<string[]>([]);

  const solicitar = async () => {
    setError(null);
    setEnviando(true);
    try {
      const p = await apiFetch<{ dias_restantes_baja: number | null; vehiculos_a_retirar?: string[] }>(
        "/perfil/baja-cuenta",
        { method: "POST", body: { motivo: motivo.trim() || null } },
      );
      actualizarBajaCuenta(p.dias_restantes_baja ?? null);
      setVehiculosARetirar(p.vehiculos_a_retirar ?? []);
      setConfirmando(false);
      setMotivo("");
    } catch (e) {
      setError(e);
    } finally {
      setEnviando(false);
    }
  };

  const cancelar = async () => {
    setError(null);
    setEnviando(true);
    try {
      await apiFetch("/perfil/baja-cuenta", { method: "DELETE" });
      actualizarBajaCuenta(null);
      setVehiculosARetirar([]);
    } catch (e) {
      setError(e);
    } finally {
      setEnviando(false);
    }
  };

  const mensaje = error instanceof ApiError ? error.message : error ? "No se pudo completar la operación" : null;

  return (
    <Card>
      <h3 style={{ marginTop: 0, fontSize: "var(--font-size-md)" }}>Cerrar mi cuenta</h3>
      {mensaje && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{mensaje}</p>}

      {diasRestantesBaja !== null ? (
        <>
          <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>
            Tu cuenta se cerrará{" "}
            <strong>
              {diasRestantesBaja === 0
                ? "hoy"
                : `en ${diasRestantesBaja} ${diasRestantesBaja === 1 ? "día" : "días"}`}
            </strong>
            . Hasta entonces puedes seguir usando el sistema con normalidad. Si cambiaste de opinión, cancela
            la baja con un solo clic.
          </p>
          {vehiculosARetirar.length > 0 && (
            <p style={{ color: "var(--color-accent-deep)", fontSize: "var(--font-size-sm)" }}>
              Al cerrarse tu cuenta, {vehiculosARetirar.length === 1 ? "el vehículo" : "los vehículos"}{" "}
              <strong>{vehiculosARetirar.join(", ")}</strong>{" "}
              {vehiculosARetirar.length === 1 ? "saldrá" : "saldrán"} de la flota operativa.
            </p>
          )}
          <div style={{ maxWidth: 220 }}>
            <Button onClick={cancelar} loading={enviando}>
              Cancelar la baja
            </Button>
          </div>
        </>
      ) : confirmando ? (
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
          <p style={{ color: "var(--color-accent-deep)", fontSize: "var(--font-size-sm)", margin: 0 }}>
            Tu cuenta seguirá funcionando con normalidad durante <strong>30 días</strong>. Pasado ese plazo, no
            podrás volver a iniciar sesión. Tu historial se conserva y puedes cancelar en cualquier momento
            desde esta misma pantalla. Esto <strong>no borra tus datos personales</strong>: si además quieres
            solicitar su eliminación, comunícate con la cooperativa.
          </p>
          <TextField
            label="Motivo (opcional)"
            value={motivo}
            onChange={(e) => setMotivo(e.target.value)}
          />
          <div style={{ display: "flex", gap: "var(--space-2)" }}>
            <div style={{ minWidth: 200 }}>
              <Button variant="danger" onClick={solicitar} loading={enviando}>
                Confirmar cierre de cuenta
              </Button>
            </div>
            <div style={{ minWidth: 110 }}>
              <Button variant="secondary" onClick={() => setConfirmando(false)}>
                Cancelar
              </Button>
            </div>
          </div>
        </div>
      ) : (
        <>
          <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>
            Puedes solicitar el cierre de tu cuenta. Tendrás 30 días para arrepentirte antes de que se haga
            efectivo.
          </p>
          <div style={{ maxWidth: 220 }}>
            <Button variant="secondary" onClick={() => setConfirmando(true)}>
              Solicitar cierre de cuenta
            </Button>
          </div>
        </>
      )}
    </Card>
  );
}

interface PreferenciasOut {
  tema: "claro" | "oscuro";
  densidad_tablas: "comoda" | "compacta";
  tamano_texto: "normal" | "grande" | "muy_grande";
  sidebar_tono: "claro" | "ambar" | "oscuro" | "grafito";
  secciones_favoritas: string[];
  notificaciones_push: Record<string, boolean>;
  sonido_oferta: boolean;
  vibracion_oferta: boolean;
  recordatorio_turno_hora: string | null;
}

interface CategoriaNotificacion {
  valor: string;
  etiqueta: string;
}

/** Sección "Ajustes" — Sección 1.4/2.3/3.2 de
 * `specs/specs-administrativas/ux_complementaria.md`. Componente único
 * reutilizado por las 3 apps: tema claro/oscuro y notificaciones push por
 * categoría siempre presentes; el resto (densidad de tablas, preferencias
 * de turno) son slots opcionales activados por prop, para no forzar campos
 * que no aplican a un rol. Las categorías de push (`/notificaciones/
 * categorias`) nunca incluyen "seguridad" -- esas alertas son exclusivas
 * del Módulo 6.3 de Administración, un usuario final no puede apagarlas. */
export function AjustesPropios({
  mostrarDensidad,
  mostrarTurno,
  version,
  extra,
}: {
  mostrarDensidad?: boolean;
  mostrarTurno?: boolean;
  version: string;
  extra?: ReactNode;
}) {
  const [prefs, setPrefs] = useState<PreferenciasOut | null>(null);
  const [categorias, setCategorias] = useState<CategoriaNotificacion[]>([]);
  const [error, setError] = useState<unknown>(null);
  const [guardandoCampo, setGuardandoCampo] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<PreferenciasOut>("/preferencias")
      .then((datos) => {
        setPrefs(datos);
        aplicarTema(datos.tema);
        aplicarTamanoTexto(datos.tamano_texto);
        aplicarSidebarTono(datos.sidebar_tono);
        if (mostrarDensidad) aplicarDensidad(datos.densidad_tablas);
      })
      .catch(setError);
    apiFetch<CategoriaNotificacion[]>("/notificaciones/categorias")
      .then(setCategorias)
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const guardar = async (campo: string, valor: unknown) => {
    setError(null);
    setGuardandoCampo(campo);
    try {
      const datos = await apiFetch<PreferenciasOut>("/preferencias", { method: "PATCH", body: { [campo]: valor } });
      setPrefs(datos);
      if (campo === "tema") aplicarTema(datos.tema);
      if (campo === "tamano_texto") aplicarTamanoTexto(datos.tamano_texto);
      if (campo === "densidad_tablas") aplicarDensidad(datos.densidad_tablas);
      if (campo === "sidebar_tono") aplicarSidebarTono(datos.sidebar_tono);
    } catch (e) {
      setError(e);
    } finally {
      setGuardandoCampo(null);
    }
  };

  const guardarCategoriaPush = (categoria: string, activo: boolean) =>
    guardar("notificaciones_push", { ...(prefs?.notificaciones_push ?? {}), [categoria]: activo });

  const mensajeGeneral =
    error instanceof ApiError ? error.message : error ? "No se pudo completar la operación" : null;

  if (!prefs) {
    return (
      <Card>
        <p style={{ color: "var(--color-text-muted)" }}>Cargando…</p>
      </Card>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
      <Card>
        <h2 style={{ marginTop: 0, fontSize: "var(--font-size-lg)" }}>Ajustes</h2>
        <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>
          Preferencias de esta cuenta. Los cambios se aplican de inmediato.
        </p>
        {mensajeGeneral && <p style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{mensajeGeneral}</p>}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "var(--space-3)" }}>
          <Select
            label="Tema"
            value={prefs.tema}
            onChange={(e) => guardar("tema", e.target.value)}
            disabled={guardandoCampo === "tema"}
            options={[
              { value: "claro", label: "Claro" },
              { value: "oscuro", label: "Oscuro" },
            ]}
          />
          <Select
            label="Tamaño de texto"
            value={prefs.tamano_texto}
            onChange={(e) => guardar("tamano_texto", e.target.value)}
            disabled={guardandoCampo === "tamano_texto"}
            options={[
              { value: "normal", label: "Normal" },
              { value: "grande", label: "Grande" },
              { value: "muy_grande", label: "Muy grande" },
            ]}
          />
          <Select
            label="Color del sidebar"
            value={prefs.sidebar_tono}
            onChange={(e) => guardar("sidebar_tono", e.target.value)}
            disabled={guardandoCampo === "sidebar_tono"}
            options={[
              { value: "claro", label: "Claro" },
              { value: "ambar", label: "Ámbar" },
              { value: "oscuro", label: "Oscuro" },
              { value: "grafito", label: "Grafito" },
            ]}
          />
          {mostrarDensidad && (
            <Select
              label="Densidad de tablas"
              value={prefs.densidad_tablas}
              onChange={(e) => guardar("densidad_tablas", e.target.value)}
              disabled={guardandoCampo === "densidad_tablas"}
              options={[
                { value: "comoda", label: "Cómoda" },
                { value: "compacta", label: "Compacta" },
              ]}
            />
          )}
        </div>
      </Card>

      <SeccionFotoPerfil />

      {categorias.length > 0 && (
        <Card>
          <h3 style={{ marginTop: 0, fontSize: "var(--font-size-md)" }}>Notificaciones push</h3>
          <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>
            Elige qué categorías te llegan como notificación push (fuera de la app). Desactivar una categoría no
            borra su historial — sigue disponible en la bandeja de notificaciones. Las alertas de seguridad del
            sistema no se pueden desactivar desde aquí.
          </p>
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
            {categorias.map((c) => (
              <label
                key={c.valor}
                style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", fontSize: "var(--font-size-sm)" }}
              >
                <input
                  type="checkbox"
                  checked={prefs.notificaciones_push[c.valor] ?? true}
                  disabled={guardandoCampo === "notificaciones_push"}
                  onChange={(e) => guardarCategoriaPush(c.valor, e.target.checked)}
                />
                {c.etiqueta}
              </label>
            ))}
          </div>
        </Card>
      )}

      {mostrarTurno && (
        <Card>
          <h3 style={{ marginTop: 0, fontSize: "var(--font-size-md)" }}>Preferencias de turno</h3>
          <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>
            Cómo recibes el aviso de una nueva oferta, y un recordatorio para iniciar turno a tu hora habitual. Esto
            no cambia qué ofertas te llegan — el reparto entre socios lo sigue decidiendo el sistema.
          </p>
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
            <label style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", fontSize: "var(--font-size-sm)" }}>
              <input
                type="checkbox"
                checked={prefs.sonido_oferta}
                disabled={guardandoCampo === "sonido_oferta"}
                onChange={(e) => guardar("sonido_oferta", e.target.checked)}
              />
              Sonido al llegar una nueva oferta
            </label>
            <label style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", fontSize: "var(--font-size-sm)" }}>
              <input
                type="checkbox"
                checked={prefs.vibracion_oferta}
                disabled={guardandoCampo === "vibracion_oferta"}
                onChange={(e) => guardar("vibracion_oferta", e.target.checked)}
              />
              Vibración al llegar una nueva oferta
            </label>
            <div style={{ maxWidth: 260 }}>
              <TextField
                label="Recordatorio para iniciar turno (hora habitual)"
                type="time"
                value={prefs.recordatorio_turno_hora ?? ""}
                disabled={guardandoCampo === "recordatorio_turno_hora"}
                onChange={(e) => guardar("recordatorio_turno_hora", e.target.value || null)}
              />
            </div>
          </div>
        </Card>
      )}

      {extra}

      <SeccionBajaCuenta />

      <Card>
        <p style={{ color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)", margin: 0 }}>
          Versión de la app: {version}
        </p>
      </Card>
    </div>
  );
}
