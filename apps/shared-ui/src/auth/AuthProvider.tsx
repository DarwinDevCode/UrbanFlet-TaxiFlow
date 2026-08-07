import { createContext, useContext, useMemo, useState, type PropsWithChildren } from "react";
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

interface AuthState {
  actor: ActorClaims | null;
  debeCambiarPassword: boolean;
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

  const applyTokens = (tokens: TokenPair) => {
    tokenStorage.set(tokens.access_token, tokens.refresh_token);
    setActor(decodeJwtPayload<ActorClaims>(tokens.access_token));
    setDebeCambiarPassword(Boolean(tokens.debe_cambiar_password));
  };

  const value = useMemo<AuthState>(
    () => ({
      actor,
      debeCambiarPassword,
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
      },
    }),
    [actor, debeCambiarPassword],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth debe usarse dentro de <AuthProvider>");
  return ctx;
}
