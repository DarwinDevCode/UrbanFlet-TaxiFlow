import { useState, type ReactNode } from "react";
import { useAuth } from "../auth/AuthProvider";
import "./AppShell.css";

// Estructura extraída de la referencia visual del dueño de producto (panel
// admin tipo "Purelcash"): barra lateral oscura con logo + navegación
// agrupada + logout al fondo, header superior con título + usuario, y un
// slot de contenido. Solo se toma el patrón estructural — nada del
// contenido cripto de la referencia ni secciones/iconos que esta app no
// tiene (calendario, mensajería, etc.).
export interface AppShellNavItem {
  id: string;
  label: string;
  /** Etiqueta de sección en mayúsculas, p. ej. "NAVEGACIÓN". Ítems sin
   * `group` se listan sueltos, sin encabezado. */
  group?: string;
}

export interface AppShellProps {
  navItems: AppShellNavItem[];
  activeId: string | undefined;
  onNavigate: (id: string) => void;
  /** Título del header. Si no se da, usa la etiqueta del ítem activo. */
  title?: string;
  children: ReactNode;
}

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

export function AppShell({ navItems, activeId, onNavigate, title, children }: AppShellProps) {
  const { actor, logout } = useAuth();
  const [sidebarAbierto, setSidebarAbierto] = useState(false);
  const grupos = agruparNavItems(navItems);
  const activo = navItems.find((n) => n.id === activeId);
  const tituloHeader = title ?? activo?.label ?? "";

  const irA = (id: string) => {
    onNavigate(id);
    setSidebarAbierto(false);
  };

  return (
    <div className="shell-root">
      {sidebarAbierto && <div className="shell-backdrop" onClick={() => setSidebarAbierto(false)} />}

      <aside className={`shell-sidebar${sidebarAbierto ? " shell-sidebar-open" : ""}`}>
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", padding: "var(--space-2) 0" }}>
          <div
            style={{
              width: 32,
              height: 32,
              borderRadius: "var(--radius-sm)",
              background: "var(--color-accent)",
              flexShrink: 0,
            }}
          />
          <span style={{ fontWeight: 700, color: "#fff", fontSize: "var(--font-size-md)" }}>UrbanFleet TaxiFlow</span>
        </div>

        <nav style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)", flex: 1, overflowY: "auto" }}>
          {grupos.map((grupo, i) => (
            <div key={grupo.group ?? `sin-grupo-${i}`} style={{ display: "flex", flexDirection: "column", gap: "var(--space-1)" }}>
              {grupo.group && (
                <span
                  style={{
                    fontSize: "0.7rem",
                    letterSpacing: "0.06em",
                    fontWeight: 700,
                    color: "var(--color-sidebar-text-muted)",
                    padding: "var(--space-2) var(--space-2) 0",
                  }}
                >
                  {grupo.group.toUpperCase()}
                </span>
              )}
              {grupo.items.map((item) => {
                const esActivo = item.id === activeId;
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => irA(item.id)}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      textAlign: "left",
                      border: "none",
                      cursor: "pointer",
                      padding: "var(--space-2) var(--space-3)",
                      borderRadius: "var(--radius-md)",
                      fontWeight: 600,
                      fontSize: "var(--font-size-sm)",
                      background: esActivo ? "var(--color-sidebar-active-bg)" : "transparent",
                      color: esActivo ? "var(--color-sidebar-active-text)" : "var(--color-sidebar-text)",
                    }}
                  >
                    {item.label}
                  </button>
                );
              })}
            </div>
          ))}
        </nav>

        <button
          type="button"
          onClick={logout}
          style={{
            display: "flex",
            alignItems: "center",
            textAlign: "left",
            border: "1px solid var(--color-sidebar-border)",
            cursor: "pointer",
            padding: "var(--space-2) var(--space-3)",
            borderRadius: "var(--radius-md)",
            fontWeight: 600,
            fontSize: "var(--font-size-sm)",
            background: "transparent",
            color: "var(--color-sidebar-text)",
          }}
        >
          Cerrar sesión
        </button>
      </aside>

      <div className="shell-main">
        <header className="shell-header">
          <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)", minWidth: 0 }}>
            <button
              type="button"
              className="shell-menu-button"
              aria-label="Abrir menú"
              onClick={() => setSidebarAbierto((v) => !v)}
            >
              ☰
            </button>
            <h1
              style={{
                fontSize: "var(--font-size-md)",
                fontWeight: 700,
                margin: 0,
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {tituloHeader}
            </h1>
          </div>
          <span
            style={{
              color: "var(--color-text-muted)",
              fontSize: "var(--font-size-sm)",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {actor?.nombre ?? actor?.sub}
          </span>
        </header>

        <main className="shell-content">{children}</main>
      </div>
    </div>
  );
}
