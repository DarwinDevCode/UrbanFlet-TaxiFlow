import type { ReactNode } from "react";
import { Button } from "./Button";
import { Card } from "./Card";
import { LoginLogo } from "./LoginLogo";

/**
 * Landing page pública real, previa a la sesión — segunda pasada de la
 * bitácora de revisión (2026-08-26, punto 4): reemplaza por completo a
 * `AcercaDeUrbanFleet` (una sola tarjeta informativa breve, insuficiente).
 * Estructura de página de presentación de servicio real: propuesta de
 * valor → sobre la organización → características (con los mismos íconos
 * de trazo ya usados en el resto del sistema, ver `IconoTrazo` más abajo,
 * nunca una ilustración nueva sin relación) → llamados a la acción.
 *
 * Sin sección de "prueba social": no existe ningún endpoint público que
 * exponga una cifra agregada real (los dashboards con datos reales
 * requieren sesión de personal interno) -- se omite en vez de fabricar un
 * número o un testimonio, tal como se pidió explícitamente.
 *
 * Compartida por `web-pasajero` y `web-conductor`, cada una con su propia
 * propuesta de valor y características (`variante`) -- `web-interno` sigue
 * sin landing, decisión ya tomada y no reabierta acá.
 */

interface Caracteristica {
  icono: ReactNode;
  titulo: string;
  texto: string;
}

function IconoTrazo({ children }: { children: ReactNode }) {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      {children}
    </svg>
  );
}

const IconoPin = () => (
  <IconoTrazo>
    <path d="M12 21s7-6.1 7-11.5A7 7 0 0 0 5 9.5C5 14.9 12 21 12 21Z" strokeLinecap="round" strokeLinejoin="round" />
    <circle cx="12" cy="9.5" r="2.3" strokeLinecap="round" strokeLinejoin="round" />
  </IconoTrazo>
);

const IconoRuta = () => (
  <IconoTrazo>
    <circle cx="5" cy="18" r="2" strokeLinecap="round" strokeLinejoin="round" />
    <circle cx="19" cy="6" r="2" strokeLinecap="round" strokeLinejoin="round" />
    <path d="M6.8 16.6 12 11l1.5 1.5c1 1 2.5 1 3.5 0l.2-.2" strokeLinecap="round" strokeLinejoin="round" strokeDasharray="2 3" />
  </IconoTrazo>
);

const IconoBilletera = () => (
  <IconoTrazo>
    <rect x="3" y="6" width="18" height="13" rx="2" strokeLinecap="round" strokeLinejoin="round" />
    <path d="M3 10h18" strokeLinecap="round" strokeLinejoin="round" />
    <path d="M15 14h3" strokeLinecap="round" strokeLinejoin="round" />
  </IconoTrazo>
);

const IconoEstrella = () => (
  <IconoTrazo>
    <path
      d="m12 3 2.6 5.6 6.1.7-4.5 4.2 1.2 6-5.4-3-5.4 3 1.2-6-4.5-4.2 6.1-.7Z"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </IconoTrazo>
);

const IconoVolante = () => (
  <IconoTrazo>
    <circle cx="12" cy="12" r="9" strokeLinecap="round" strokeLinejoin="round" />
    <circle cx="12" cy="12" r="2.6" strokeLinecap="round" strokeLinejoin="round" />
    <path d="M12 3v6.4M6 16.5l4.4-3M18 16.5l-4.4-3" strokeLinecap="round" strokeLinejoin="round" />
  </IconoTrazo>
);

const IconoDocumento = () => (
  <IconoTrazo>
    <path d="M7 3h7l4 4v14H7Z" strokeLinecap="round" strokeLinejoin="round" />
    <path d="M14 3v4h4" strokeLinecap="round" strokeLinejoin="round" />
    <path d="m9.5 14 2 2 3.5-4" strokeLinecap="round" strokeLinejoin="round" />
  </IconoTrazo>
);

const IconoLlave = () => (
  <IconoTrazo>
    <circle cx="8" cy="15" r="4" strokeLinecap="round" strokeLinejoin="round" />
    <path d="M11.2 12 20 3.2M17 6l2 2M14 9l2 2" strokeLinecap="round" strokeLinejoin="round" />
  </IconoTrazo>
);

const CARACTERISTICAS: Record<"pasajero" | "conductor", Caracteristica[]> = {
  pasajero: [
    { icono: <IconoPin />, titulo: "Pide tu taxi en segundos", texto: "Indica dónde te recogemos y a dónde vas, sin llamadas ni esperas en la calle." },
    { icono: <IconoRuta />, titulo: "Sigue tu viaje en vivo", texto: "Mira en el mapa a tu conductor acercarse, desde que acepta hasta que llegas." },
    { icono: <IconoBilletera />, titulo: "Paga como prefieras", texto: "Efectivo o pago electrónico, con el desglose completo de la tarifa antes de bajarte." },
    { icono: <IconoEstrella />, titulo: "Viaja con confianza", texto: "Socios conductores verificados por la cooperativa, y calificación mutua al final de cada viaje." },
  ],
  conductor: [
    { icono: <IconoVolante />, titulo: "Recibe ofertas cercanas", texto: "Viajes cerca de ti mientras estás en turno, con tiempo suficiente para decidir si aceptar." },
    { icono: <IconoRuta />, titulo: "Navega sin salir de la app", texto: "Ruta óptima al pasajero y al destino, integrada en el mismo mapa." },
    { icono: <IconoDocumento />, titulo: "Liquidaciones claras", texto: "Consulta tus pagos semanales y el detalle de cada viaje cobrado, sin sorpresas." },
    { icono: <IconoLlave />, titulo: "Respaldo de la cooperativa", texto: "Reporta una falla del vehículo o una incidencia en el momento, con evidencia fotográfica." },
  ],
};

export function LandingPage({
  variante,
  onIniciarSesion,
  onRegistrar,
  registrarLabel,
}: {
  variante: "pasajero" | "conductor";
  onIniciarSesion: () => void;
  onRegistrar: () => void;
  /** "Regístrate" para pasajero, "Postula aquí" para conductor -- mismo
   * verbo que ya usa cada flujo real, no uno genérico inventado acá. */
  registrarLabel: string;
}) {
  const caracteristicas = CARACTERISTICAS[variante];

  const botonesAccion = (
    <div style={{ display: "flex", gap: "var(--space-3)", flexWrap: "wrap" }}>
      <Button onClick={onIniciarSesion} style={{ minWidth: 160 }}>
        Iniciar sesión
      </Button>
      <Button variant="secondary" onClick={onRegistrar} style={{ minWidth: 160 }}>
        {registrarLabel}
      </Button>
    </div>
  );

  return (
    <div
      style={{
        minHeight: "100dvh",
        background: "var(--color-bg)",
      }}
    >
      {/* Héroe — propuesta de valor */}
      <div
        style={{
          padding: "var(--space-6) var(--space-4) var(--space-5)",
          background:
            "radial-gradient(ellipse at top, color-mix(in srgb, var(--color-accent) 14%, var(--color-bg)) 0%, var(--color-bg) 65%)",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          textAlign: "center",
          gap: "var(--space-4)",
        }}
      >
        <LoginLogo />
        <div style={{ maxWidth: 560 }}>
          <h1
            style={{
              margin: 0,
              fontFamily: "var(--font-display)",
              fontWeight: 700,
              fontSize: "var(--font-size-2xl)",
              lineHeight: 1.15,
            }}
          >
            {variante === "pasajero" ? "Tu taxi, a un toque de distancia" : "Maneja con el respaldo de tu cooperativa"}
          </h1>
          <p style={{ marginTop: "var(--space-3)", color: "var(--color-text-muted)", fontSize: "var(--font-size-lg)" }}>
            {variante === "pasajero"
              ? "UrbanFleet conecta a pasajeros con los socios conductores de la cooperativa de transporte — pide, sigue y paga tu viaje desde el celular."
              : "UrbanFleet es la plataforma de la cooperativa para sus socios conductores — recibe viajes, navega y cobra tus liquidaciones desde un solo lugar."}
          </p>
        </div>
        {botonesAccion}
      </div>

      <div style={{ maxWidth: 900, margin: "0 auto", padding: "var(--space-5) var(--space-4)", display: "flex", flexDirection: "column", gap: "var(--space-5)" }}>
        {/* Sobre la organización */}
        <Card>
          <h2 style={{ marginTop: 0, fontSize: "var(--font-size-lg)" }}>Sobre la cooperativa</h2>
          <p style={{ color: "var(--color-text-muted)", margin: 0 }}>
            UrbanFleet es el sistema de una cooperativa de transporte: un grupo de socios conductores organizados
            para ofrecer un servicio de taxi confiable y bajo un mismo estándar de calidad. La cooperativa administra
            la flota, verifica la habilitación de cada conductor y su vehículo, y respalda tanto a quien viaja como a
            quien conduce.
          </p>
        </Card>

        {/* Características del servicio */}
        <div>
          <h2 style={{ fontSize: "var(--font-size-lg)", marginBottom: "var(--space-3)" }}>
            {variante === "pasajero" ? "Qué puedes hacer como pasajero" : "Qué puedes hacer como socio conductor"}
          </h2>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
              gap: "var(--space-3)",
            }}
          >
            {caracteristicas.map((c) => (
              <Card key={c.titulo}>
                <div style={{ color: "var(--color-accent-deep)", marginBottom: "var(--space-2)" }}>{c.icono}</div>
                <h3 style={{ margin: 0, fontSize: "var(--font-size-md)" }}>{c.titulo}</h3>
                <p style={{ marginTop: "var(--space-1)", marginBottom: 0, color: "var(--color-text-muted)", fontSize: "var(--font-size-sm)" }}>
                  {c.texto}
                </p>
              </Card>
            ))}
          </div>
        </div>

        {/* Llamado a la acción de cierre */}
        <Card>
          <div style={{ textAlign: "center" }}>
            <h2 style={{ marginTop: 0, fontSize: "var(--font-size-lg)" }}>
              {variante === "pasajero" ? "¿Listo para tu primer viaje?" : "¿Listo para empezar a manejar con nosotros?"}
            </h2>
            <p style={{ color: "var(--color-text-muted)" }}>
              {variante === "pasajero"
                ? "Crea tu cuenta con tu teléfono o correo y una contraseña — en minutos puedes pedir tu primer taxi."
                : "Envía tu postulación con tus documentos (licencia, matrícula del vehículo). Un coordinador la revisa, y una vez aprobada puedes iniciar sesión y ponerte en turno."}
            </p>
            <div style={{ display: "flex", justifyContent: "center" }}>{botonesAccion}</div>
          </div>
        </Card>
      </div>
    </div>
  );
}
