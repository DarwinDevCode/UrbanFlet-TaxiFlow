import {
  AjustesPropios,
  ApiError,
  apiFetch,
  AppShell,
  Button,
  Card,
  CentroAyuda,
  LoginLogo,
  NotificacionesBell,
  PasswordField,
  PerfilPropio,
  SeccionNotificaciones,
  type NotificacionOut,
  TextField,
  useAuth,
  type PreguntaFrecuente,
} from "@urbanflet/shared-ui";
import { useEffect, useMemo, useState } from "react";
import { SeccionAuditoriaAdmin } from "./sections/AuditoriaAdmin";
import { SeccionCatalogos } from "./sections/Catalogos";
import { SeccionComision } from "./sections/Comision";
import { SeccionConfiguracionAlertas } from "./sections/ConfiguracionAlertas";
import { SeccionCumplimiento } from "./sections/Cumplimiento";
import { SeccionFeatureFlags } from "./sections/FeatureFlags";
import { SeccionFinanzas } from "./sections/Finanzas";
import { SeccionFlota } from "./sections/Flota";
import { SeccionGobernanzaDatos } from "./sections/GobernanzaDatos";
import { SeccionHistorialGlobal } from "./sections/HistorialGlobal";
import { SeccionIndicadores } from "./sections/Indicadores";
import { SeccionIntegraciones } from "./sections/Integraciones";
import { SeccionMantenimiento } from "./sections/Mantenimiento";
import { SeccionMonitoreo } from "./sections/Monitoreo";
import { SeccionParametrosGlobales } from "./sections/ParametrosGlobales";
import { SeccionPoliticasAuth } from "./sections/PoliticasAuth";
import { SeccionPoliticasSeguridad } from "./sections/PoliticasSeguridad";
import { SeccionRespaldosYContinuidad } from "./sections/Respaldos";
import { SeccionSolicitudes } from "./sections/Solicitudes";
import { SeccionUsuarios } from "./sections/Usuarios";
import { SeccionVersionSistema } from "./sections/VersionSistema";
import { PanelAuditoria } from "./sections/tactico/PanelAuditoria";
import { PanelCaptacion } from "./sections/tactico/PanelCaptacion";
import { PanelConciliacion } from "./sections/tactico/PanelConciliacion";
import { PanelDespacho } from "./sections/tactico/PanelDespacho";
import { PanelRendimientoConductores } from "./sections/tactico/PanelRendimientoConductores";
import { PanelDocumentacion } from "./sections/tactico/PanelDocumentacion";
import { PanelLiquidacion } from "./sections/tactico/PanelLiquidacion";
import { PanelPlataforma } from "./sections/tactico/PanelPlataforma";
import { PanelFlota } from "./sections/tactico/PanelFlota";
import { PanelMantenimiento } from "./sections/tactico/PanelMantenimiento";
import { PanelCapacidades } from "./sections/estrategico/PanelCapacidades";
import { PanelConfiabilidad } from "./sections/estrategico/PanelConfiabilidad";
import { PanelCrecimiento } from "./sections/estrategico/PanelCrecimiento";
import { PanelCumplimientoNormativo } from "./sections/estrategico/PanelCumplimientoNormativo";
import { PanelDesempenoConductores } from "./sections/estrategico/PanelDesempenoConductores";
import { PanelEstadoCostoFlota } from "./sections/estrategico/PanelEstadoCostoFlota";
import { PanelGobernanza } from "./sections/estrategico/PanelGobernanza";
import { PanelIntegridadFinanciera } from "./sections/estrategico/PanelIntegridadFinanciera";
import { PanelRentabilidad } from "./sections/estrategico/PanelRentabilidad";
import { TableroEjecutivo } from "./sections/estrategico/TableroEjecutivo";
import { NavegacionSeccionProvider, useIrASeccion } from "./navegacion";

function LoginCard() {
  const { login } = useAuth();
  const [identificador, setIdentificador] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);

  const entrar = async () => {
    setError(null);
    setCargando(true);
    try {
      await login(identificador, password);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Credenciales inválidas");
    } finally {
      setCargando(false);
    }
  };

  return (
    <div
      style={{
        minHeight: "100dvh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "var(--space-4)",
        // v2: lavado suave de ámbar de marca (PLAN_REDISENO_V2.md §2), mismo
        // criterio que los otros 2 portales.
        background: "radial-gradient(ellipse at top, color-mix(in srgb, var(--color-accent) 10%, var(--color-bg)) 0%, var(--color-bg) 60%)",
      }}
    >
      <div style={{ width: "min(420px, 100%)" }}>
        <div style={{ display: "flex", justifyContent: "center", marginBottom: "var(--space-4)" }}>
          <LoginLogo />
        </div>
        <Card>
          <h1 style={{ fontSize: "var(--font-size-lg)", margin: 0, marginBottom: "var(--space-2)" }}>
            Portal interno
          </h1>
          <p style={{ color: "var(--color-text-muted)", marginTop: 0, marginBottom: "var(--space-4)" }}>
            Jefes de área y gerencia — acceso con teléfono o correo, y contraseña.
          </p>
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
            <TextField
              label="Teléfono o correo"
              value={identificador}
              onChange={(e) => setIdentificador(e.target.value)}
            />
            <PasswordField
              label="Contraseña"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            {error && <span style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</span>}
            <Button onClick={entrar} loading={cargando} disabled={!identificador || !password}>
              Entrar
            </Button>
          </div>
        </Card>
      </div>
    </div>
  );
}

interface Seccion {
  id: string;
  etiqueta: string;
  roles: string[];
  grupo?: string;
  render: () => JSX.Element;
}

// Sección 3.1 de la spec ux_complementaria.md: visible para los 13 roles de
// `web-interno`, no filtrada por rol como el resto -- `ROL_CUALQUIERA` es un
// sentinel que `Panel()` reconoce más abajo, en vez de listar los 13 roles a
// mano (se rompería en cuanto se agregue un rol 14 nuevo).
const ROL_CUALQUIERA = "*";

const PREGUNTAS_FRECUENTES_INTERNO: PreguntaFrecuente[] = [
  {
    pregunta: "¿Por qué no veo ninguna sección?",
    respuesta: "Tu cuenta no tiene ningún rol con una pantalla asignada todavía — pide al Administrador del Sistema que revise tus roles.",
  },
  {
    pregunta: "¿Cómo actualizo mi propio teléfono o correo?",
    respuesta: "Entra a \"Mi cuenta\" y edita tus datos con tu contraseña actual. No necesitas pedírselo a un administrador.",
  },
  {
    pregunta: "¿Puedo cambiar mi propio rol?",
    respuesta: "No — los roles solo los asigna el Administrador del Sistema desde el módulo de Usuarios.",
  },
];

// Grupo D de la ronda de correcciones UX/UI. Dos cambios en esta lista, sin
// reordenar NI UN elemento (el orden decide la sección por defecto de cada
// rol, `seccionesVisibles[0]` -- ver los comentarios de "Mi cuenta" e
// "Historial de viajes" más abajo):
//
//  1. Las pantallas operativas, que estaban sueltas sin encabezado, ahora
//     tienen su propio grupo "Operación". Eso permitió quitar el sufijo
//     "(táctico)" de las 10 etiquetas del Panel Táctico -- existía solo para
//     distinguir "Flota" operativa de "Flota" táctica cuando la primera no
//     tenía encabezado; el nivel estratégico nunca lo necesitó (sus
//     etiquetas siempre fueron limpias) porque su encabezado ya lo dice.
//     La jerarquía visual de 3 niveles del sidebar no cambia: sigue siendo
//     sin marcador (operativo) → marcador chico (táctico) → marcador grande
//     (estratégico), ver NIVEL_GRUPO en AppShell.
//  2. Las 3 opciones de cuenta personal (Mi cuenta / Ajustes / Ayuda), antes
//     también sueltas, quedan agrupadas bajo "Mi cuenta" -- la zona personal
//     que AppShell separa con un divisor del resto de la navegación.
// Mapa real de "a dónde lleva cada tipo de notificación" en este portal,
// confirmado contra el código (Fase 0 de esta ronda, no adivinado):
// - NUEVA_SOLICITUD -> admin_captacion recibe esto, Solicitudes es la
//   pantalla donde vive esa solicitud.
// - ALERTA_SEGURIDAD conflacia 5 orígenes reales (`payload.tipo_alerta`,
//   ver notificacionesCatalogo.ts) con destinatario y pantalla propios:
//   denegaciones_rbac/gps_spoofing -> ambos quedan en la MISMA bitácora de
//   Auditoría (CU-O17); pipeline_fallido -> Plataforma (corridas); 
//   reporte_falla -> Mantenimiento (bandeja de reportes); 
//   incidencia_operativa -> Despacho (viajes activos).
// El resto de los 13 tipos reales (SOLICITUD_DECISION, DOCUMENTO_*,
// RENOVACION_*, ORDEN_MANTENIMIENTO_*, VIAJE_*) los recibe siempre un
// conductor/pasajero, nunca un rol de `web-interno` -- no aparecen acá a
// propósito, `resolverAccionRapida` devuelve `null` para ellos (solo
// informativo, ningún destino real que ofrecer en este portal).
const DESTINO_TIPO_ALERTA: Record<string, string> = {
  denegaciones_rbac: "tactico-auditoria",
  gps_spoofing: "tactico-auditoria",
  pipeline_fallido: "tactico-plataforma",
  // La bandeja de reportes de falla vive en el WorkPanel OPERATIVO de
  // Mantenimiento (id "mantenimiento", pestaña "Reportes de falla" -- Fase
  // D de la ronda de fallas del vehículo), no en el dashboard táctico.
  reporte_falla: "mantenimiento",
  incidencia_operativa: "tactico-despacho",
};

function SeccionNotificacionesInterno() {
  const irASeccion = useIrASeccion();
  return (
    <SeccionNotificaciones
      resolverAccionRapida={(n: NotificacionOut) => {
        if (n.tipo === "NUEVA_SOLICITUD") {
          return { etiqueta: "Ver solicitud", onClick: () => irASeccion("solicitudes") };
        }
        if (n.tipo === "ALERTA_SEGURIDAD") {
          const tipoAlerta = typeof n.payload.tipo_alerta === "string" ? n.payload.tipo_alerta : undefined;
          const destino = tipoAlerta ? DESTINO_TIPO_ALERTA[tipoAlerta] : undefined;
          if (destino) {
            const etiquetas: Record<string, string> = {
              "tactico-auditoria": "Ver en Auditoría",
              "tactico-plataforma": "Ver en Plataforma",
              "mantenimiento": "Ver en Mantenimiento",
              "tactico-despacho": "Ver en Despacho",
            };
            return { etiqueta: etiquetas[destino] ?? "Ver detalle", onClick: () => irASeccion(destino) };
          }
        }
        return null;
      }}
    />
  );
}

const SECCIONES: Seccion[] = [
  { id: "solicitudes", etiqueta: "Solicitudes", roles: ["admin_captacion"], grupo: "Operación", render: () => <SeccionSolicitudes /> },
  { id: "mantenimiento", etiqueta: "Mantenimiento", roles: ["jefe_mantenimiento"], grupo: "Operación", render: () => <SeccionMantenimiento /> },
  { id: "cumplimiento", etiqueta: "Cumplimiento", roles: ["supervisor_cumplimiento"], grupo: "Operación", render: () => <SeccionCumplimiento /> },
  { id: "flota", etiqueta: "Flota", roles: ["coordinador_flota", "admin_plataforma"], grupo: "Operación", render: () => <SeccionFlota /> },
  { id: "finanzas", etiqueta: "Finanzas", roles: ["admin_financiero"], grupo: "Operación", render: () => <SeccionFinanzas /> },
  {
    id: "indicadores",
    etiqueta: "Indicadores",
    roles: ["gerencia", "responsable_plataforma", "admin_plataforma"],
    grupo: "Operación",
    render: () => <SeccionIndicadores />,
  },
  {
    id: "tactico-flota",
    etiqueta: "Flota",
    roles: ["coordinador_flota", "admin_plataforma"],
    grupo: "Panel Táctico",
    render: () => <PanelFlota />,
  },
  {
    id: "tactico-mantenimiento",
    etiqueta: "Mantenimiento",
    roles: ["jefe_mantenimiento"],
    grupo: "Panel Táctico",
    render: () => <PanelMantenimiento />,
  },
  {
    id: "tactico-documentacion",
    etiqueta: "Vigencia Documental",
    roles: ["supervisor_cumplimiento"],
    grupo: "Panel Táctico",
    render: () => <PanelDocumentacion />,
  },
  {
    id: "tactico-captacion",
    etiqueta: "Captación",
    roles: ["admin_captacion"],
    grupo: "Panel Táctico",
    render: () => <PanelCaptacion />,
  },
  {
    id: "tactico-despacho",
    etiqueta: "Despacho",
    roles: ["coordinador_operaciones"],
    grupo: "Panel Táctico",
    render: () => <PanelDespacho />,
  },
  {
    id: "tactico-rendimiento-conductores",
    etiqueta: "Rendimiento de Conductores",
    roles: ["coordinador_operaciones"],
    grupo: "Panel Táctico",
    render: () => <PanelRendimientoConductores />,
  },
  {
    id: "tactico-conciliacion",
    etiqueta: "Conciliación",
    roles: ["admin_financiero"],
    grupo: "Panel Táctico",
    render: () => <PanelConciliacion />,
  },
  {
    id: "tactico-liquidacion",
    etiqueta: "Liquidación",
    roles: ["admin_financiero"],
    grupo: "Panel Táctico",
    render: () => <PanelLiquidacion />,
  },
  {
    id: "tactico-auditoria",
    etiqueta: "Auditoría",
    roles: ["supervisor_cumplimiento", "admin_plataforma", "gerencia"],
    grupo: "Panel Táctico",
    render: () => <PanelAuditoria />,
  },
  {
    id: "tactico-plataforma",
    etiqueta: "Plataforma",
    roles: ["gerencia", "responsable_plataforma", "admin_plataforma"],
    grupo: "Panel Táctico",
    render: () => <PanelPlataforma />,
  },
  // ── Panel Estratégico (specs/nivel-estrategico/nivel_estrategico.md) ──
  //
  // Ubicado DESPUÉS de "Panel Táctico" y ANTES de "Administración": respeta
  // la jerarquía operativo → táctico → estratégico del sidebar y, sobre todo,
  // no cambia la sección por defecto (`seccionesVisibles[0]`) de ningún rol —
  // los 7 roles con acceso a algún panel estratégico (`gerencia`,
  // `admin_captacion`, `coordinador_operaciones`, `jefe_mantenimiento`,
  // `responsable_plataforma`, `admin_financiero`, `supervisor_cumplimiento`)
  // ya tienen al menos una sección más arriba en la lista. Mismo cuidado que
  // documentan "Mi cuenta" e "Historial de viajes" más abajo, verificado
  // sección por sección al agregar este grupo.
  //
  // Los `roles` de cada entrada replican EXACTAMENTE el gate del endpoint que
  // consume (Fase 3, commit c0a123d) — en particular Gobernanza es exclusivo
  // de `gerencia`, sin OR-gate con `admin_sistema`, como exige la spec §3.6.b.
  {
    id: "estrategico-tablero",
    etiqueta: "Tablero Ejecutivo",
    roles: ["gerencia"],
    grupo: "Panel Estratégico",
    render: () => <TableroEjecutivo />,
  },
  {
    id: "estrategico-crecimiento",
    etiqueta: "Crecimiento",
    roles: ["gerencia", "admin_captacion"],
    grupo: "Panel Estratégico",
    render: () => <PanelCrecimiento />,
  },
  {
    id: "estrategico-confiabilidad",
    etiqueta: "Confiabilidad del servicio",
    roles: ["gerencia", "coordinador_operaciones"],
    grupo: "Panel Estratégico",
    render: () => <PanelConfiabilidad />,
  },
  {
    id: "estrategico-estado-costo-flota",
    etiqueta: "Estado y costo de flota",
    roles: ["gerencia", "jefe_mantenimiento"],
    grupo: "Panel Estratégico",
    render: () => <PanelEstadoCostoFlota />,
  },
  {
    id: "estrategico-capacidades",
    etiqueta: "Capacidades y plataforma",
    roles: ["gerencia", "responsable_plataforma"],
    grupo: "Panel Estratégico",
    render: () => <PanelCapacidades />,
  },
  {
    id: "estrategico-rentabilidad",
    etiqueta: "Rentabilidad y demanda",
    roles: ["gerencia"],
    grupo: "Panel Estratégico",
    render: () => <PanelRentabilidad />,
  },
  {
    id: "estrategico-integridad-financiera",
    etiqueta: "Integridad financiera",
    roles: ["gerencia", "admin_financiero"],
    grupo: "Panel Estratégico",
    render: () => <PanelIntegridadFinanciera />,
  },
  {
    id: "estrategico-cumplimiento-normativo",
    etiqueta: "Cumplimiento normativo",
    roles: ["gerencia", "supervisor_cumplimiento"],
    grupo: "Panel Estratégico",
    render: () => <PanelCumplimientoNormativo />,
  },
  {
    id: "estrategico-gobernanza",
    etiqueta: "Gobernanza de datos",
    roles: ["gerencia"],
    grupo: "Panel Estratégico",
    render: () => <PanelGobernanza />,
  },
  // N6 rediseñado (Tier 1 de la auditoría, punto 7) -- agregado al FINAL del
  // grupo "Panel Estratégico" (mismo cuidado documentado arriba: no debe
  // desplazar la sección por defecto de `coordinador_operaciones`, que ya
  // tiene "Despacho" táctico más arriba en la lista). Roles idénticos al
  // gate del endpoint (`viajes/router_trips.py::_desempeno_conductores_estrategico`).
  {
    id: "estrategico-desempeno-conductores",
    etiqueta: "Desempeño de conductores",
    roles: ["gerencia", "coordinador_operaciones"],
    grupo: "Panel Estratégico",
    render: () => <PanelDesempenoConductores />,
  },
  {
    id: "admin-usuarios",
    etiqueta: "Usuarios",
    roles: ["admin_sistema"],
    grupo: "Administración",
    render: () => <SeccionUsuarios />,
  },
  {
    id: "admin-politicas-auth",
    etiqueta: "Políticas de autenticación",
    roles: ["admin_sistema"],
    grupo: "Administración",
    render: () => <SeccionPoliticasAuth />,
  },
  {
    id: "admin-parametros-globales",
    etiqueta: "Parámetros globales",
    roles: ["admin_sistema"],
    grupo: "Administración",
    render: () => <SeccionParametrosGlobales />,
  },
  {
    id: "admin-feature-flags",
    etiqueta: "Funcionalidades",
    roles: ["admin_sistema"],
    grupo: "Administración",
    render: () => <SeccionFeatureFlags />,
  },
  {
    id: "admin-auditoria",
    etiqueta: "Auditoría",
    roles: ["admin_sistema"],
    grupo: "Administración",
    render: () => <SeccionAuditoriaAdmin />,
  },
  {
    id: "admin-catalogos",
    etiqueta: "Catálogos",
    roles: ["admin_sistema"],
    grupo: "Administración",
    render: () => <SeccionCatalogos />,
  },
  {
    id: "admin-version",
    etiqueta: "Versión",
    roles: ["admin_sistema"],
    grupo: "Administración",
    render: () => <SeccionVersionSistema />,
  },
  {
    id: "admin-politicas-seguridad",
    etiqueta: "Políticas de seguridad",
    roles: ["admin_sistema"],
    grupo: "Administración",
    render: () => <SeccionPoliticasSeguridad />,
  },
  {
    // Renombrado en la ronda del Centro de notificaciones (sección completa
    // personal, más abajo): esta pantalla es la CONFIGURACIÓN de quién
    // recibe cada alerta (Módulo 6.3), no la bandeja donde un usuario la
    // recibe -- compartir la misma etiqueta "Notificaciones" con la nueva
    // sección personal habría dejado 2 ítems iguales en el sidebar de
    // `admin_sistema` (el único rol que ve ambos).
    id: "admin-notificaciones",
    etiqueta: "Configuración de alertas",
    roles: ["admin_sistema"],
    grupo: "Administración",
    render: () => <SeccionConfiguracionAlertas />,
  },
  {
    id: "admin-integraciones",
    etiqueta: "Integraciones",
    roles: ["admin_sistema"],
    grupo: "Administración",
    render: () => <SeccionIntegraciones />,
  },
  {
    id: "admin-monitoreo",
    etiqueta: "Monitoreo",
    roles: ["admin_sistema"],
    grupo: "Administración",
    render: () => <SeccionMonitoreo />,
  },
  {
    id: "admin-gobernanza-datos",
    etiqueta: "Gobernanza de datos",
    roles: ["admin_sistema"],
    grupo: "Administración",
    render: () => <SeccionGobernanzaDatos />,
  },
  {
    id: "admin-respaldos",
    etiqueta: "Respaldos",
    roles: ["admin_sistema", "gerencia"],
    grupo: "Administración",
    render: () => <SeccionRespaldosYContinuidad />,
  },
  {
    // Sección 3.3 de ux_complementaria.md: acceso restringido por rol
    // (principio de mínimo privilegio ya aplicado en Administración) --
    // distinto grupo del sidebar, no es ni un CRUD operativo ni un panel
    // táctico de agregados, es una consulta puntual de cualquier viaje.
    // Colocado DESPUÉS de todos los grupos con roles únicos (Solicitudes,
    // Mantenimiento, Panel Táctico, Administración) -- mismo motivo que
    // "Mi cuenta" más abajo: no debe convertirse en la sección por defecto
    // de ningún rol ya existente (`seccionesVisibles[0]`), ya que
    // `admin_sistema` (entre otros) también calificaría para esta sección.
    id: "historial-global",
    etiqueta: "Historial de viajes",
    roles: ["coordinador_operaciones", "supervisor_cumplimiento", "gerencia", "admin_sistema"],
    grupo: "Historial",
    render: () => <SeccionHistorialGlobal />,
  },
  {
    // Investigación de la comisión de la cooperativa (CU-O10): el endpoint
    // `POST /parametros/comisiones` ya existía, versionado y auditado, pero
    // sin ninguna pantalla -- la única forma de cambiarlo era una llamada
    // directa a la API. Gateado EXACTAMENTE a los mismos 2 roles que el
    // propio endpoint (`admin_plataforma`/`gerencia`, ver el comentario de
    // `parametros/router.py` sobre "reglas de dinero y estado") -- no entra
    // en "Administración" (grupo de `admin_sistema`, que a propósito NO
    // puede tocar esto) ni en "Parámetros globales" (Módulo 2, un dominio de
    // configuración de sistema completamente distinto). Mismo motivo que
    // "Historial de viajes" arriba para la posición: después de todos los
    // grupos con roles únicos, para no convertirse en la sección por
    // defecto de `admin_plataforma` (hoy "Flota") ni de `gerencia` (hoy
    // "Indicadores").
    id: "comision",
    etiqueta: "Comisión de la cooperativa",
    roles: ["admin_plataforma", "gerencia"],
    grupo: "Comisión",
    render: () => <SeccionComision />,
  },
  // Sección 3.1 de la spec ux_complementaria.md: visible para los 13 roles
  // de `web-interno`, no filtrada por rol como el resto de la lista --
  // `ROL_CUALQUIERA` es un sentinel que `Panel()` reconoce más abajo, en vez
  // de listar los 13 roles a mano (se rompería en cuanto se agregue un rol
  // 14 nuevo). Al final de la lista a propósito: no debe convertirse en la
  // sección por defecto de ningún rol ya existente (`seccionesVisibles[0]`).
  {
    id: "mi-cuenta",
    etiqueta: "Mi cuenta",
    roles: [ROL_CUALQUIERA],
    grupo: "Mi cuenta",
    render: () => <PerfilPropio />,
  },
  {
    // Punto 2 de esta ronda: sección propia además de la campana, mismo
    // sentinel ROL_CUALQUIERA que "Mi cuenta" -- cualquier rol recibe
    // notificaciones propias. El indicador de no leídas se agrega en
    // `Panel()` (necesita `useAuth()`, no disponible en un array estático).
    id: "notificaciones",
    etiqueta: "Notificaciones",
    roles: [ROL_CUALQUIERA],
    grupo: "Mi cuenta",
    render: () => <SeccionNotificacionesInterno />,
  },
  {
    id: "ajustes",
    etiqueta: "Ajustes",
    roles: [ROL_CUALQUIERA],
    grupo: "Mi cuenta",
    render: () => <AjustesPropios version="0.1.0" mostrarDensidad />,
  },
  {
    id: "ayuda",
    etiqueta: "Ayuda",
    roles: [ROL_CUALQUIERA],
    grupo: "Mi cuenta",
    render: () => (
      <CentroAyuda
        preguntas={PREGUNTAS_FRECUENTES_INTERNO}
        correoContacto="soporte@urbanfleet.example"
        telefonoContacto="+593900000000"
      />
    ),
  },
];

function Panel() {
  const { actor, noLeidas } = useAuth();
  const rolesActor = actor?.roles ?? [];
  // Misma lógica de filtrado por rol que antes tenía la nav horizontal — solo
  // cambia dónde se renderiza (sidebar del AppShell en vez de una fila de
  // botones bajo un header ad-hoc).
  const seccionesVisibles = useMemo(
    () =>
      SECCIONES.filter((s) => s.roles.includes(ROL_CUALQUIERA) || s.roles.some((r) => rolesActor.includes(r))),
    // `rolesActor` sale de `actor?.roles ?? []` -- el `??` crea un array nuevo
    // en cada render cuando no hay actor, así que se depende de su contenido
    // serializado y no de la referencia.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [rolesActor.join(",")],
  );
  // OJO: la sección por defecto sigue saliendo de `seccionesVisibles[0]`, que
  // depende del ORDEN de `SECCIONES` -- los favoritos de abajo solo cambian
  // cómo se pinta el sidebar, nunca este cálculo. Es la trampa que ya se pisó
  // dos veces (ver comentarios de "Mi cuenta" e "Historial de viajes").
  const [seccionActiva, setSeccionActiva] = useState(seccionesVisibles[0]?.id);

  // Ronda de personalización: accesos rápidos del sidebar por cuenta. Se leen
  // una sola vez al montar y se guardan con el mismo `PATCH /preferencias`
  // que usa Ajustes -- sin endpoint nuevo. Si la lectura falla, la lista
  // queda vacía y el sidebar se comporta como siempre.
  const [favoritos, setFavoritos] = useState<string[]>([]);
  useEffect(() => {
    apiFetch<{ secciones_favoritas: string[] }>("/preferencias")
      .then((p) => setFavoritos(p.secciones_favoritas ?? []))
      .catch(() => undefined);
  }, []);

  const alternarFavorito = (id: string) => {
    const siguiente = favoritos.includes(id) ? favoritos.filter((f) => f !== id) : [...favoritos, id];
    setFavoritos(siguiente); // optimista: el sidebar responde al instante
    apiFetch("/preferencias", { method: "PATCH", body: { secciones_favoritas: siguiente } }).catch(() =>
      setFavoritos(favoritos),
    );
  };

  const seccion = seccionesVisibles.find((s) => s.id === seccionActiva);
  const navItems = seccionesVisibles.map((s) => ({
    id: s.id,
    label: s.etiqueta,
    group: s.grupo,
    badge: s.id === "notificaciones" ? noLeidas : undefined,
  }));

  // Hallazgo H4 de AUDITORIA_NIVEL_ESTRATEGICO.md: hasta ahora `setSeccionActiva`
  // solo llegaba al sidebar. El contexto publica la MISMA función (más los ids
  // visibles) para que un panel pueda ofrecer "Ver detalle" sin que ninguna de
  // las secciones existentes cambie de firma — ver `navegacion.ts`.
  const navegacion = useMemo(
    () => ({ ir: setSeccionActiva, disponibles: seccionesVisibles.map((s) => s.id) }),
    [seccionesVisibles],
  );

  return (
    <NavegacionSeccionProvider value={navegacion}>
      <AppShell
        navItems={navItems}
        activeId={seccionActiva}
        onNavigate={setSeccionActiva}
        title={seccion?.etiqueta ?? "Portal interno"}
        headerActions={<NotificacionesBell onVerTodas={() => setSeccionActiva("notificaciones")} />}
        favoritos={favoritos}
        onToggleFavorito={alternarFavorito}
      >
        {seccionesVisibles.length === 0 ? (
          <Card>
            <p style={{ color: "var(--color-text-muted)" }}>
              Tu rol no tiene ninguna sección asignada en este panel todavía.
            </p>
          </Card>
        ) : (
          seccion?.render()
        )}
      </AppShell>
    </NavegacionSeccionProvider>
  );
}

// Módulo 1.1/1.3 de admin_sistema (specs/specs-administrativas/
// admin_sistema.md): una cuenta creada por un administrador, o cuya
// contraseña venció según la política vigente, no puede navegar el resto
// del portal hasta cambiarla.
function CambiarPasswordCard() {
  const { cambiarPassword, logout } = useAuth();
  const [actual, setActual] = useState("");
  const [nueva, setNueva] = useState("");
  const [confirmarNueva, setConfirmarNueva] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);

  const confirmar = async () => {
    setError(null);
    setCargando(true);
    try {
      await cambiarPassword(actual, nueva);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo cambiar la contraseña");
    } finally {
      setCargando(false);
    }
  };

  return (
    <div style={{ minHeight: "100dvh", display: "flex", alignItems: "center", justifyContent: "center", padding: "var(--space-4)" }}>
      <div style={{ width: "min(420px, 100%)" }}>
        <Card>
          <h1 style={{ fontSize: "var(--font-size-lg)", margin: 0, marginBottom: "var(--space-2)" }}>
            Cambio de contraseña obligatorio
          </h1>
          <p style={{ color: "var(--color-text-muted)", marginTop: 0, marginBottom: "var(--space-4)" }}>
            Un administrador forzó el cambio de contraseña de esta cuenta, o la política de vencimiento periódico ya
            expiró. Debes definir una nueva contraseña antes de continuar.
          </p>
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
            <PasswordField label="Contraseña actual" value={actual} onChange={(e) => setActual(e.target.value)} />
            <PasswordField label="Contraseña nueva" value={nueva} onChange={(e) => setNueva(e.target.value)} />
            <PasswordField
              label="Confirmar contraseña nueva"
              value={confirmarNueva}
              onChange={(e) => setConfirmarNueva(e.target.value)}
              confirmarContra={nueva}
            />
            {error && <span style={{ color: "var(--color-danger)", fontSize: "var(--font-size-sm)" }}>{error}</span>}
            <Button onClick={confirmar} loading={cargando} disabled={!actual || !nueva || nueva !== confirmarNueva}>
              Cambiar contraseña
            </Button>
            <Button variant="secondary" onClick={logout}>
              Cancelar y salir
            </Button>
          </div>
        </Card>
      </div>
    </div>
  );
}

export default function App() {
  const { actor, debeCambiarPassword } = useAuth();
  // Bitácora de revisión (hallazgo #1): `web-pasajero`/`web-conductor` ganaron
  // una página "¿Qué es UrbanFleet?" accesible desde el login. Deliberadamente
  // NO se agrega acá: este portal es de uso exclusivo de personal interno ya
  // capacitado (staff de la cooperativa con cuenta creada por un
  // `admin_sistema`, nunca autorregistro) -- no es una puerta de entrada para
  // público general que necesite entender qué es el sistema antes de usarlo.
  if (!actor) return <LoginCard />;
  if (debeCambiarPassword) return <CambiarPasswordCard />;
  return <Panel />;
}
