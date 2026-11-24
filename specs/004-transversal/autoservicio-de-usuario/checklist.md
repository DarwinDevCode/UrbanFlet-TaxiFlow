# Checklist de validación: Autoservicio de Usuario

## Funcional (reusado de `PLAN_DE_PRUEBAS.md`)

- [ ] **PD-07** — Foto y preferencias por cuenta, con `--font-scale` verificado en el navegador.
- [ ] **PU-06** — Versión en lenguaje simple.

## Funcional (nuevos)

- [ ] **CHK-AUS-001** — Editar el propio teléfono sin la contraseña actual correcta es rechazado.
- [ ] **CHK-AUS-002** — La foto nueva se refleja en el historial de viajes y en Usuarios sin
  recargar.
- [ ] **CHK-AUS-003** — Cerrar una sesión a distancia invalida esa sesión en su siguiente petición.

## Automatizado

- [ ] `backend/tests/perfil/` y `backend/tests/preferencias/`.
- [ ] `npm run test` en las 3 apps (cobertura de perfil/ajustes).

## No verificable automáticamente

- [ ] Subida real de una imagen y su reflejo instantáneo en múltiples pantallas.
