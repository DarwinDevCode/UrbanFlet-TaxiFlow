import { createContext, useContext, useMemo, useState, type PropsWithChildren } from "react";
import { apiFetch } from "../api/client";
import { tokenStorage } from "../api/tokenStorage";
import { decodeJwtPayload } from "./decodeJwt";

interface TokenPair {
  access_token: string;
  refresh_token: string;
}

interface ActorClaims {
  sub: string;
  roles: string[];
  nombre?: string;
}

interface AuthState {
  actor: ActorClaims | null;
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

  const applyTokens = (tokens: TokenPair) => {
    tokenStorage.set(tokens.access_token, tokens.refresh_token);
    setActor(decodeJwtPayload<ActorClaims>(tokens.access_token));
  };

  const value = useMemo<AuthState>(
    () => ({
      actor,
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
      logout: () => {
        tokenStorage.clear();
        setActor(null);
      },
    }),
    [actor],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth debe usarse dentro de <AuthProvider>");
  return ctx;
}
