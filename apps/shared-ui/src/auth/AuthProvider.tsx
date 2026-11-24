import { createContext, useContext, useEffect, useMemo, useState, type PropsWithChildren } from "react";
import { apiFetch } from "../api/client";
import { tokenStorage } from "../api/tokenStorage";
import { decodeJwtPayload } from "./decodeJwt";

interface TokenPair {
  access_token: string;
  refresh_token: string;
  // Módulo 1.1/1.3 de admin_sistema (specs/specs-administrativas/
  // admin_sistema.md): un admin forzó el cambio de contraseña al crear/editar
  // la cuenta, o la política de vencimiento periódico para roles de alto
  // privilegio ya venció.
  debe_cambiar_password?: boolean;
}

interface ActorClaims {
  sub: string;
  roles: string[];
  nombre?: string;
}

interface PerfilFotoOut {
  foto_url: string | null;
  /** Autoservicio de baja de cuenta -- ausente/`null` si la cuenta está
   * normal. Se lee del MISMO `GET /perfil` que ya traía la foto, sin
   * agregar una petición nueva por sesión. */
  dias_restantes_baja?: number | null;
}

interface AuthState {
  actor: ActorClaims | null;
  debeCambiarPassword: boolean;
  // Ronda de foto de perfil: id del archivo de foto propia (contexto
  // `foto_perfil`, ver `archivos/service.py`), o `null` sin foto. Vive acá
  // (no solo en `PerfilPropio`/`AjustesPropios`) porque `AppShell` -- un
  // componente hermano, no un padre/hijo de esos dos -- también necesita
  // mostrarla en el header, y sin un estado compartido no se enteraría de
  // un cambio hecho en "Ajustes" sin recargar la página entera.
  fotoUrl: string | null;
  actualizarFoto: (fotoUrl: string | null) => void;
  // Autoservicio de baja de cuenta: días que faltan para que la baja se haga
  // efectiva, o `null` si la cuenta no tiene ninguna baja en curso. Vive acá
  // por el mismo motivo que `fotoUrl` -- `AppShell` (hermano de Ajustes, no
  // su padre) necesita pintar el aviso persistente en cuanto el usuario
  // entra, y tiene que enterarse de una cancelación hecha en Ajustes sin
  // recargar la página.
  diasRestantesBaja: number | null;
  actualizarBajaCuenta: (dias: number | null) => void;
  // Centro de notificaciones (sección completa + campana): contador GLOBAL
  // de no leídas, sin importar ningún filtro que la sección completa tenga
  // aplicado -- vive acá (no en NotificacionesBell) porque tanto la campana
  // como la entrada del sidebar (AppShell, hermano de la campana, no su
  // padre) necesitan mostrar el mismo número sin desincronizarse entre sí.
  noLeidas: number;
  /** Fija el valor directo, sin red -- para cuando otra pantalla (la
   * sección completa) ya trae `no_leidas` en una respuesta que pidió por su
   * cuenta, y así evitar una petición redundante. */
  actualizarNoLeidas: (n: number) => void;
  /** Dispara una petición nueva de `/notificaciones/mias?limite=1` -- para
   * cuando se necesita el valor fresco sin tener ya una respuesta en mano
   * (ej. tras marcar como leída desde la campana). */
  refrescarNoLeidas: () => void;
  // Login autocontenido: teléfono o correo (el que el usuario haya elegido
  // al registrarse) + contraseña — un solo mecanismo para los tres roles,
  // sin verificación externa de ningún tipo.
  registrar: (params: {
    nombre: string;
    telefono?: string;
    email?: string;
    password: string;
    versionConsentimiento: string;
  }) => Promise<void>;
  login: (identificador: string, password: string) => Promise<void>;
  cambiarPassword: (passwordActual: string, passwordNueva: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

function actorFromStoredToken(): ActorClaims | null {
  const token = tokenStorage.getAccess();
  if (!token) return null;
  return decodeJwtPayload<ActorClaims>(token);
}

export function AuthProvider({ children }: PropsWithChildren) {
  const [actor, setActor] = useState<ActorClaims | null>(actorFromStoredToken());
  const [debeCambiarPassword, setDebeCambiarPassword] = useState(false);
  const [fotoUrl, setFotoUrl] = useState<string | null>(null);
  const [diasRestantesBaja, setDiasRestantesBaja] = useState<number | null>(null);
  const [noLeidas, setNoLeidas] = useState(0);

  const applyTokens = (tokens: TokenPair) => {
    tokenStorage.set(tokens.access_token, tokens.refresh_token);
    setActor(decodeJwtPayload<ActorClaims>(tokens.access_token));
    setDebeCambiarPassword(Boolean(tokens.debe_cambiar_password));
  };

  // Una sola lectura de `/perfil` por sesión (al iniciar sesión, o al
  // recargar la página con un token ya guardado) -- suficiente para que el
  // header ya muestre la foto correcta desde el primer render con datos;
  // cambios posteriores los empuja `actualizarFoto` directo, sin refetch.
  useEffect(() => {
    if (!actor) {
      setFotoUrl(null);
      setDiasRestantesBaja(null);
      return;
    }
    apiFetch<PerfilFotoOut>("/perfil")
      .then((p) => {
        setFotoUrl(p.foto_url);
        setDiasRestantesBaja(p.dias_restantes_baja ?? null);
      })
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [actor?.sub]);

  // Contador global de no leídas -- refresco periódico, mismo intervalo que
  // ya usaba NotificacionesBell antes de mudarse acá (20s, igual que otros
  // paneles de "estado casi en vivo" del proyecto, ej. Monitoreo -- sin
  // abrir un WebSocket nuevo solo para esto).
  useEffect(() => {
    if (!actor) {
      setNoLeidas(0);
      return;
    }
    const refrescar = () => {
      apiFetch<{ no_leidas: number }>("/notificaciones/mias?limite=1")
        .then((r) => setNoLeidas(r.no_leidas))
        .catch(() => {});
    };
    refrescar();
    const id = setInterval(refrescar, 20_000);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [actor?.sub]);

  const value = useMemo<AuthState>(
    () => ({
      actor,
      debeCambiarPassword,
      fotoUrl,
      actualizarFoto: setFotoUrl,
      diasRestantesBaja,
      actualizarBajaCuenta: setDiasRestantesBaja,
      noLeidas,
      actualizarNoLeidas: setNoLeidas,
      refrescarNoLeidas: () => {
        apiFetch<{ no_leidas: number }>("/notificaciones/mias?limite=1")
          .then((r) => setNoLeidas(r.no_leidas))
          .catch(() => {});
      },
      registrar: async ({ nombre, telefono, email, password, versionConsentimiento }) => {
        // CU-O02: registro de pasajero (no el /auth/registro genérico) —
        // es lo único que además captura el consentimiento LOPDP y asigna
        // el rol "pasajero" a la cuenta.
        await apiFetch("/captacion/pasajeros/registro", {
          method: "POST",
          auth: false,
          body: { nombre, telefono, email, password, version_consentimiento: versionConsentimiento },
        });
      },
      login: async (identificador, password) => {
        const tokens = await apiFetch<TokenPair>("/auth/login", {
          method: "POST",
          auth: false,
          body: { identificador, password },
        });
        applyTokens(tokens);
      },
      cambiarPassword: async (passwordActual, passwordNueva) => {
        await apiFetch("/auth/cambiar-password", {
          method: "POST",
          body: { password_actual: passwordActual, password_nueva: passwordNueva },
        });
        setDebeCambiarPassword(false);
      },
      logout: () => {
        tokenStorage.clear();
        setActor(null);
        setDebeCambiarPassword(false);
        setFotoUrl(null);
        setNoLeidas(0);
      },
    }),
    [actor, debeCambiarPassword, fotoUrl, diasRestantesBaja, noLeidas],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth debe usarse dentro de <AuthProvider>");
  return ctx;
}
