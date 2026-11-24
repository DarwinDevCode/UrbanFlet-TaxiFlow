import logoUrbanFleetFull from "../assets/logo-urbanflet-full.png";
import logoUrbanFleetFullInvertido from "../assets/logo-urbanflet-full-invertido.png";

/**
 * Logotipo completo (isotipo + "UrbanFleet" + "TRANSPORTE URBANO") de las 3
 * pantallas de login. Mismo mecanismo de crossfade que el logo del andén
 * (`AppShell`), pero leyendo `--logo-invertido-tema` en vez de
 * `--logo-invertido` -- el login no tiene sidebar, así que su legibilidad
 * depende solo del tema de contenido, nunca de una preferencia de sidebar
 * que además puede seguir cacheada en localStorage tras cerrar sesión. Ver
 * el comentario junto a esa variable en `tokens.css`.
 */
export function LoginLogo() {
  return (
    <div style={{ display: "grid", width: 300, maxWidth: "100%" }}>
      <img
        src={logoUrbanFleetFull}
        alt="UrbanFleet"
        style={{
          gridArea: "1 / 1",
          width: "100%",
          height: "auto",
          opacity: "calc(1 - var(--logo-invertido-tema, 0))",
        }}
      />
      <img
        src={logoUrbanFleetFullInvertido}
        alt=""
        aria-hidden="true"
        style={{
          gridArea: "1 / 1",
          width: "100%",
          height: "auto",
          opacity: "var(--logo-invertido-tema, 0)",
        }}
      />
    </div>
  );
}
