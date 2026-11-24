# Especificación: Autoservicio de Usuario (Transversal)

> Documento retroactivo. Fuente principal: `FUNCIONALIDADES_TRANSVERSALES.md` §3, verificada contra
> `backend/src/perfil/` y `backend/src/preferencias/`.

## 1. Objetivo

Permitir que cada usuario gestione sus propios datos, foto, sesiones y preferencias de apariencia
sin depender de un administrador.

## 2. Contexto

Nadie debería necesitar pedirle a `admin_sistema` que le corrija su propio teléfono o le cambie el
tema — es soporte al uso diario, no una operación de negocio de ningún departamento.

## 3. Actores

- **Cualquier usuario autenticado**, sobre su propia cuenta — incluye los 13 roles del sistema.

## 4. Requisitos funcionales

### RF-AUS-001 — Edición de contacto propio
El usuario debe poder editar su teléfono/correo, confirmando con su contraseña actual (nunca OTP,
RN-SIS-007).

### RF-AUS-002 — Foto de perfil
El usuario debe poder subir/cambiar su foto — reflejada de inmediato en cualquier lugar donde ya se
mostraba su avatar (encabezado, historial de viajes, gestión de usuarios), sin recargar.

### RF-AUS-003 — Sesiones activas
El usuario debe poder ver y cerrar a distancia sus propias sesiones activas en otros dispositivos.

### RF-AUS-004 — Preferencias de apariencia
Tema (claro/oscuro), tamaño de texto, y en `web-interno` densidad de tablas y color del sidebar —
cada cambio se aplica de inmediato y persiste al navegar/recargar.

### RF-AUS-005 — Centro de ayuda
Preguntas frecuentes y contacto, distinto por portal.

## 5. Requisitos no funcionales

### RNF-AUS-001 — Preferencias por cuenta, nunca globales
Dos cuentas distintas en el mismo navegador mantienen sus propios valores de tema/densidad/sidebar
sin interferirse.

## 6. Reglas de negocio

### RN-AUS-001
Un usuario nunca puede cambiar su propio rol desde esta pantalla.

### RN-AUS-002
El contacto del Centro de ayuda usa datos de placeholder (`soporte@urbanfleet.example`) — decisión
permanente y consciente (proyecto académico sin cooperativa real detrás), no un dato pendiente de
completar.

## 7. Entradas

- Teléfono/correo nuevo + contraseña actual.
- Archivo de imagen para la foto.
- Selección de tema/tamaño de texto/densidad/color de sidebar.

## 8. Salidas

- Datos/foto/preferencias actualizados, reflejados en todo el sistema sin recargar.
- Sesión cerrada a distancia (la sesión afectada pierde acceso en su próxima petición).

## 9. Estados posibles

No aplica — no gestiona una entidad con máquina de estados propia.

## 10. Escenarios

### Escenario 1: Cambio de foto reflejado en todo el sistema
Dado que un usuario sube una foto nueva
Cuando la confirma
Entonces aparece de inmediato en el encabezado y en cualquier otro lugar que ya mostraba su avatar,
sin recargar la página.

### Escenario 2: Preferencias aisladas entre cuentas
Dado que la cuenta A cambia su tema a oscuro
Cuando la cuenta B inicia sesión en el mismo navegador
Entonces B ve sus propias preferencias, sin heredar las de A.

## 11. Criterios de aceptación

Reusa `PLAN_DE_PRUEBAS.md`:
- **PD-07** — Foto de perfil y preferencias por cuenta, con verificación técnica de `--font-scale`.
- **PU-06** — Versión en lenguaje simple.

### CA-AUS-001
Un usuario nunca ve un control para cambiar su propio rol en esta pantalla.

## 12. Dependencias

- Consumida por los 3 portales completos — cualquier pantalla con encabezado muestra el avatar de
  este módulo.

## 13. Fuera de alcance

- **Reset de contraseña** — no implementado en ningún flujo.
- **Cambio del propio rol** — nunca disponible desde autoservicio.
- **Contacto real del Centro de ayuda** — placeholder permanente, decisión ya confirmada.
