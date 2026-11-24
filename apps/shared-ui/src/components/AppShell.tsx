import { useState, type ReactNode } from "react";
import { useAuth } from "../auth/AuthProvider";
import logoHorizontal from "../assets/logo-urbanflet-horizontal.png";
import logoHorizontalInvertido from "../assets/logo-urbanflet-horizontal-invertido.png";
import { Avatar } from "./Avatar";
import { CountBadge } from "./CountBadge";
import "./AppShell.css";

/**
 * EL ANDÉN — chasis del portal interno (Fase 2 del Sistema Riel).
 *
 * Lo que reemplaza: un sidebar oscuro con lista de links + un header que
 * repetía el nombre de la sección activa. Esa estructura venía declarada
 * en el código como "extraída de una referencia de panel admin", y era el
 * origen real de que el sistema se leyera como plantilla.
 *
 * Lo que hace ahora:
 *
 * 1. **La navegación es una línea con paradas.** Mismo contenido, mismos
 *    grupos, mismos clics -- pero se lee como el mapa de una línea de
 *    transporte en vez de una pila de rectángulos. El bloque de color de
 *    fondo desaparece: el andén vive sobre el mismo plano que el resto,
 *    separado por una línea.
 *
 * 2. **El encabezado deja de repetir el título.** Antes decía lo mismo que
 *    el ítem activo del menú Y que el `<h2>` de la propia pantalla: tres
 *    veces el mismo dato. Ahora localiza al usuario en el trayecto --
 *    "tramo → parada" unidos por un fragmento de riel -- y deja el título
 *    real a la pantalla, que es donde tiene contexto.
 */
export interface AppShellNavItem {
  id: string;
  label: string;
  /** Nombre del tramo del andén ("Operación", "Panel Táctico"). Los ítems
   * sin grupo se listan sueltos, sin encabezado de tramo. */
  group?: string;
  /** Contador de no leídas. Ausente o 0 no pinta nada. */
  badge?: number;
}

export interface AppShellProps {
  navItems: AppShellNavItem[];
  activeId: string | undefined;
  onNavigate: (id: string) => void;
  /** Fuerza el nombre de la parada en el encabezado. Sin esto usa la
   * etiqueta del ítem activo. */
  title?: string;
  /** Acciones del encabezado (campana de notificaciones). */
  headerActions?: ReactNode;
  /** Secciones marcadas como favoritas por esta cuenta: se repiten en un
   * tramo "Favoritos" arriba, SIN quitarlas de su tramo real. Sin
   * `onToggleFavorito` no se pinta ninguna estrella. */
  favoritos?: string[];
  onToggleFavorito?: (id: string) => void;
  children: ReactNode;
}

const GRUPO_FAVORITOS = "Favoritos";

interface NavGroup {
  group: string | null;
  items: AppShellNavItem[];
}

function agruparNavItems(items: AppShellNavItem[]): NavGroup[] {
  const grupos: NavGroup[] = [];
  for (const item of items) {
    const clave = item.group ?? null;
    let grupo = grupos.find((g) => g.group === clave);
    if (!grupo) {
      grupo = { group: clave, items: [] };
      grupos.push(grupo);
    }
    grupo.items.push(item);
  }
  return grupos;
}

/** Jerarquía operativo → táctico → estratégico. Se reconoce por el nombre
 * literal del tramo, sin agregar ningún campo a `AppShellNavItem` -- así
 * los portales que no usan estos nombres quedan sin marcador. En el andén
 * el nivel se expresa con el grosor del tramo de línea, no con un cuadrito
 * suelto al lado del texto. */
const NIVEL_TRAMO = new Set(["Panel Táctico", "Panel Estratégico"]);

/** Tramos que son "de la cuenta" y no funcionalidad del portal: se separan
 * del resto con un corte mayor en la línea. */
const GRUPOS_PERSONALES = new Set(["Mi cuenta"]);

export function AppShell({
  navItems,
  activeId,
  onNavigate,
  title,
  headerActions,
  favoritos,
  onToggleFavorito,
  children,
}: AppShellProps) {
  const { actor, fotoUrl, diasRestantesBaja, logout } = useAuth();
  const [andenAbierto, setAndenAbierto] = useState(false);
  const activo = navItems.find((n) => n.id === activeId);
  const nombreParada = title ?? activo?.label ?? "";
  const nombreTramo = activo?.group ?? null;

  // Un favorito cuyo id ya no está en `navItems` (sección retirada, o rol
  // que perdió el acceso) simplemente no aparece.
  const favoritosVisibles = (favoritos ?? [])
    .map((id) => navItems.find((n) => n.id === id))
    .filter((n): n is AppShellNavItem => n !== undefined);

  const grupos = [
    ...(favoritosVisibles.length > 0
      ? [{ group: GRUPO_FAVORITOS, items: favoritosVisibles.map((n) => ({ ...n, group: GRUPO_FAVORITOS })) }]
      : []),
    ...agruparNavItems(navItems),
  ];

  const irA = (id: string) => {
    onNavigate(id);
    setAndenAbierto(false);
  };

  return (
    <div className="shell-root">
      {andenAbierto && <div className="shell-backdrop" onClick={() => setAndenAbierto(false)} />}

      <aside className={`shell-sidebar${andenAbierto ? " shell-sidebar-open" : ""}`}>
        <div className="anden-marca">
          {/* 2 imágenes superpuestas, nunca una sola con fondo: la tinta del
              PNG es un valor fijo horneado en el raster, no reacciona a
              ninguna variable CSS -- así que la variante legible sobre cada
              tono de sidebar se elige con un crossfade de opacidad dirigido
              por `--logo-invertido` (0 = tinta oscura de fábrica, 1 = tinta
              clara), nunca con una placa de fondo detrás. */}
          <img src={logoHorizontal} alt="UrbanFleet" className="anden-marca-logo anden-marca-logo--base" />
          <img src={logoHorizontalInvertido} alt="" aria-hidden="true" className="anden-marca-logo anden-marca-logo--invertido" />
        </div>

        <nav className="anden no-scrollbar" aria-label="Secciones">
          {grupos.map((grupo, i) => {
            const esPersonal = Boolean(grupo.group && GRUPOS_PERSONALES.has(grupo.group));
            return (
              <div
                key={grupo.group ?? `sin-grupo-${i}`}
                className={`anden-tramo${esPersonal ? " anden-tramo--personal" : ""}${
                  grupo.group && NIVEL_TRAMO.has(grupo.group) ? " anden-tramo--nivel" : ""
                }`}
                data-zona={esPersonal ? "personal" : undefined}
              >
                {grupo.group && <span className="uf-rotulo anden-tramo-nombre">{grupo.group}</span>}

                {grupo.items.map((item) => {
                  const esActivo = item.id === activeId;
                  const esFavorito = (favoritos ?? []).includes(item.id);
                  return (
                    <div
                      // La misma sección aparece 2 veces cuando es favorita
                      // (en "Favoritos" y en su tramo real).
                      key={`${grupo.group ?? "sin-grupo"}-${item.id}`}
                      className={`anden-parada${esActivo ? " anden-parada--actual" : ""}`}
                    >
                      <button type="button" onClick={() => irA(item.id)} className="anden-parada-boton">
                        <span className="anden-parada-nombre">{item.label}</span>
                        {Boolean(item.badge) && <CountBadge valor={item.badge!} />}
                      </button>

                      {onToggleFavorito && (
                        <button
                          type="button"
                          aria-pressed={esFavorito}
                          aria-label={
                            esFavorito ? `Quitar ${item.label} de favoritos` : `Marcar ${item.label} como favorito`
                          }
                          title={esFavorito ? "Quitar de favoritos" : "Marcar como favorito"}
                          onClick={() => onToggleFavorito(item.id)}
                          className={`anden-favorito${esFavorito ? " anden-favorito--on" : ""}`}
                        >
                          <svg
                            width="13"
                            height="13"
                            viewBox="0 0 24 24"
                            fill={esFavorito ? "currentColor" : "none"}
                            stroke="currentColor"
                            strokeWidth="2"
                            aria-hidden="true"
                          >
                            <path
                              d="M12 2.5l2.9 6.6 7.1.7-5.4 4.8 1.6 7-6.2-3.8-6.2 3.8 1.6-7-5.4-4.8 7.1-.7z"
                              strokeLinejoin="round"
                            />
                          </svg>
                        </button>
                      )}
                    </div>
                  );
                })}
              </div>
            );
          })}
        </nav>

        <button type="button" onClick={logout} className="anden-salida">
          Cerrar sesión
        </button>
      </aside>

      <div className="shell-main">
        <header className="shell-header">
          <div className="shell-localizador">
            <button
              type="button"
              className="shell-menu-button"
              aria-label="Abrir menú"
              onClick={() => setAndenAbierto((v) => !v)}
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                <path d="M4 6h16M4 12h16M4 18h16" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>

            {/* Tramo → parada, unidos por un fragmento de riel: dónde está
                el usuario dentro del sistema. Reemplaza al título repetido. */}
            {nombreTramo && (
              <>
                <span className="uf-rotulo shell-tramo">{nombreTramo}</span>
                <span className="shell-conector" aria-hidden="true" />
              </>
            )}
            <h1 className="shell-parada">{nombreParada}</h1>
          </div>

          <div className="shell-header-acciones">
            {headerActions}
            <span className="shell-usuario">
              <Avatar fotoUrl={fotoUrl} nombre={actor?.nombre} tamano={26} />
              <span className="shell-usuario-nombre">{actor?.nombre ?? actor?.sub}</span>
            </span>
          </div>
        </header>

        {/* Aviso del autoservicio de baja: visible en CUALQUIER pantalla
            mientras dure el periodo de gracia, para que el titular no pueda
            olvidarse. Desaparece solo al cancelar. */}
        {diasRestantesBaja !== null && (
          <div role="status" className="shell-aviso-baja">
            {diasRestantesBaja === 0
              ? "Tu cuenta se cerrará hoy."
              : `Tu cuenta se cerrará en ${diasRestantesBaja} ${diasRestantesBaja === 1 ? "día" : "días"}.`}{" "}
            Puedes cancelar la baja desde Ajustes mientras tanto.
          </div>
        )}

        <main className="shell-content">{children}</main>
      </div>
    </div>
  );
}
