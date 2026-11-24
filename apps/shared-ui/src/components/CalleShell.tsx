import { useEffect, useState, type ReactNode } from "react";
import { useAuth } from "../auth/AuthProvider";
import logoIcon from "../assets/logo-urbanflet-icon.png";
import { Avatar } from "./Avatar";
import { CountBadge } from "./CountBadge";
import type { AppShellNavItem } from "./AppShell";
import "./CalleShell.css";

/**
 * EL CHASIS DE CALLE — portales de pasajero y conductor (Fase 3 del
 * Sistema Riel).
 *
 * Por qué existe un chasis aparte y no se reusa `AppShell`: los 3 portales
 * venían usando el MISMO esqueleto de escritorio (barra lateral + header),
 * y por eso se leían como la misma aplicación repetida tres veces. Pero un
 * pasajero pidiendo un taxi en la vereda y un supervisor revisando 1,3
 * millones de viajes en un monitor no hacen el mismo trabajo: uno usa un
 * pulgar y mira una pantalla de 375 px con el sol encima, el otro usa mouse
 * y teclado. Darles el mismo chasis era el origen real de que "todos los
 * portales se vean iguales entre sí".
 *
 * Qué comparte con el andén, a propósito: **la línea con paradas**. Acá se
 * acuesta y baja al alcance del pulgar, con la parada actual encendida con
 * contorno y halo — el mismo nodo del `Riel` de estado y del andén. El
 * idioma visual es uno solo; lo que cambia es el vehículo.
 *
 * Qué cambia respecto del andén, y por qué:
 *
 * 1. **No hay barra lateral.** En 375 px de ancho, una barra lateral o roba
 *    un tercio de la pantalla o se esconde detrás de un botón de menú —
 *    dos toques para llegar a cualquier lado. El riel inferior deja todo a
 *    un toque, con objetivos grandes, en la zona que el pulgar alcanza sin
 *    reacomodar la mano.
 *
 * 2. **La separación "funcional vs. personal" pasa a ser estructural.** En
 *    el andén son dos tramos separados por una línea; acá lo operativo vive
 *    en el riel y la cuenta vive detrás de una sola parada que abre una
 *    hoja. Es la misma decisión de siempre, dicha con el chasis en vez de
 *    con un divisor.
 *
 * 3. **El encabezado se reduce a lo mínimo.** En vertical el alto es el
 *    recurso escaso: queda la marca, la parada actual y las acciones. El
 *    nombre y el cierre de sesión bajan a la hoja, donde no compiten con el
 *    mapa por espacio.
 */
export interface CalleShellProps {
  navItems: AppShellNavItem[];
  activeId: string;
  onNavigate: (id: string) => void;
  /** Ids que viven en el riel inferior, en este orden. Todo lo que no esté
   * acá entra en la hoja, conservando su tramo. Es explícito y no derivado
   * del grupo porque cuál es la parada principal es una decisión de cada
   * portal, no algo que se pueda adivinar del nombre del tramo. */
  principales: string[];
  /** Etiqueta de la parada que abre la hoja. "Cuenta" cuando lo que queda
   * es solo lo personal; "Más" cuando también quedan secciones operativas. */
  etiquetaResto?: string;
  /** Fuerza el nombre de la parada en el encabezado. */
  title?: string;
  headerActions?: ReactNode;
  /** La pantalla llena el alto disponible en vez de crecer con su contenido
   * (vistas de mapa). Sin esto el contenido scrollea normalmente. */
  contenidoLleno?: boolean;
  children: ReactNode;
}

interface TramoHoja {
  group: string | null;
  items: AppShellNavItem[];
}

function agrupar(items: AppShellNavItem[]): TramoHoja[] {
  const tramos: TramoHoja[] = [];
  for (const item of items) {
    const clave = item.group ?? null;
    let tramo = tramos.find((t) => t.group === clave);
    if (!tramo) {
      tramo = { group: clave, items: [] };
      tramos.push(tramo);
    }
    tramo.items.push(item);
  }
  return tramos;
}

export function CalleShell({
  navItems,
  activeId,
  onNavigate,
  principales,
  etiquetaResto = "Más",
  title,
  headerActions,
  contenidoLleno,
  children,
}: CalleShellProps) {
  const { actor, fotoUrl, diasRestantesBaja, logout } = useAuth();
  const [hojaAbierta, setHojaAbierta] = useState(false);

  // Un id de `principales` que no exista en `navItems` simplemente no pinta
  // parada, en vez de romper el riel.
  const paradasRiel = principales
    .map((id) => navItems.find((n) => n.id === id))
    .filter((n): n is AppShellNavItem => n !== undefined);

  const enHoja = navItems.filter((n) => !principales.includes(n.id));
  const tramosHoja = agrupar(enHoja);

  // Si una sección con contador queda en la hoja, su señal tiene que subir a
  // la parada que la contiene: si no, el usuario pierde el aviso hasta que
  // abra la hoja por su cuenta.
  const badgeResto = enHoja.reduce((total, n) => total + (n.badge ?? 0), 0);
  const activoEnHoja = enHoja.some((n) => n.id === activeId);

  const activo = navItems.find((n) => n.id === activeId);
  const nombreParada = title ?? activo?.label ?? "";

  useEffect(() => {
    if (!hojaAbierta) return;
    const alTeclear = (e: KeyboardEvent) => {
      if (e.key === "Escape") setHojaAbierta(false);
    };
    window.addEventListener("keydown", alTeclear);
    return () => window.removeEventListener("keydown", alTeclear);
  }, [hojaAbierta]);

  const irA = (id: string) => {
    onNavigate(id);
    setHojaAbierta(false);
  };

  return (
    <div className="calle-root">
      <header className="calle-cabecera">
        <img src={logoIcon} alt="UrbanFleet" className="calle-marca" />
        <h1 className="calle-parada-titulo">{nombreParada}</h1>
        <div className="calle-cabecera-acciones">{headerActions}</div>
      </header>

      {/* Mismo aviso de baja que el andén: visible en cualquier pantalla
          mientras dure el periodo de gracia. */}
      {diasRestantesBaja !== null && (
        <div role="status" className="calle-aviso-baja">
          {diasRestantesBaja === 0
            ? "Tu cuenta se cerrará hoy."
            : `Tu cuenta se cerrará en ${diasRestantesBaja} ${diasRestantesBaja === 1 ? "día" : "días"}.`}{" "}
          Puedes cancelar la baja desde Ajustes.
        </div>
      )}

      <main className={`calle-contenido${contenidoLleno ? " calle-contenido--lleno" : ""}`}>{children}</main>

      <nav className="calle-riel" aria-label="Secciones">
        {/* La línea corre por detrás de los nodos, de la primera parada a la
            última — es una sola línea que atraviesa el riel, no un borde por
            botón. Mismo gesto que el tramo del andén, acostado. */}
        <span className="calle-riel-linea" aria-hidden="true" />

        {paradasRiel.map((item) => {
          const esActivo = item.id === activeId;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => irA(item.id)}
              aria-current={esActivo ? "page" : undefined}
              className={`calle-parada${esActivo ? " calle-parada--actual" : ""}`}
            >
              <span className="calle-nodo" aria-hidden="true" />
              <span className="calle-parada-nombre">{item.label}</span>
              {Boolean(item.badge) && (
                <span className="calle-parada-badge">
                  <CountBadge valor={item.badge!} />
                </span>
              )}
            </button>
          );
        })}

        {enHoja.length > 0 && (
          <button
            type="button"
            onClick={() => setHojaAbierta((v) => !v)}
            aria-expanded={hojaAbierta}
            aria-current={activoEnHoja ? "page" : undefined}
            className={`calle-parada${activoEnHoja ? " calle-parada--actual" : ""}`}
          >
            <span className="calle-nodo" aria-hidden="true" />
            <span className="calle-parada-nombre">{etiquetaResto}</span>
            {badgeResto > 0 && (
              <span className="calle-parada-badge">
                <CountBadge valor={badgeResto} />
              </span>
            )}
          </button>
        )}
      </nav>

      {hojaAbierta && (
        <>
          <div className="calle-hoja-fondo" onClick={() => setHojaAbierta(false)} />
          <div className="calle-hoja" role="dialog" aria-modal="true" aria-label={etiquetaResto}>
            <div className="calle-hoja-titular">
              <Avatar fotoUrl={fotoUrl} nombre={actor?.nombre} tamano={34} />
              <span className="calle-hoja-nombre">{actor?.nombre ?? actor?.sub}</span>
              <button
                type="button"
                className="calle-hoja-cerrar"
                aria-label="Cerrar"
                onClick={() => setHojaAbierta(false)}
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                  <path d="M6 6l12 12M18 6L6 18" strokeLinecap="round" />
                </svg>
              </button>
            </div>

            <div className="calle-hoja-tramos no-scrollbar">
              {tramosHoja.map((tramo, i) => (
                <div key={tramo.group ?? `sin-tramo-${i}`} className="calle-hoja-tramo">
                  {tramo.group && <span className="uf-rotulo calle-hoja-tramo-nombre">{tramo.group}</span>}
                  {tramo.items.map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => irA(item.id)}
                      aria-current={item.id === activeId ? "page" : undefined}
                      className={`calle-hoja-parada${item.id === activeId ? " calle-hoja-parada--actual" : ""}`}
                    >
                      <span className="calle-hoja-parada-nombre">{item.label}</span>
                      {Boolean(item.badge) && <CountBadge valor={item.badge!} />}
                    </button>
                  ))}
                </div>
              ))}
            </div>

            <button type="button" onClick={logout} className="calle-hoja-salida">
              Cerrar sesión
            </button>
          </div>
        </>
      )}
    </div>
  );
}
