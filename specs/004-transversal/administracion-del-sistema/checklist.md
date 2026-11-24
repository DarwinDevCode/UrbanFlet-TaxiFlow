# Checklist de validación: Administración del Sistema

## Funcional (reusado de `PLAN_DE_PRUEBAS.md`)

- [ ] **PD-05** — Catálogo: alta, edición, baja lógica, verificado en Mongo (`activo:false`, nunca
  borrado).
- [ ] **PD-06** — Baja lógica de cuenta con casos borde (login falla con 401, viaje en curso
  bloquea con 409).
- [ ] **PU-07**/**PU-08** — Versión en lenguaje simple.
- [ ] **PUS-08** — Anonimización exige escribir "ANONIMIZAR" exacto.
- [ ] **PUS-09** — Motivo obligatorio en decisiones graves (rechazar, observar, descartar, dar de
  baja).
- [ ] **PUS-10**/**PUS-11** — Aviso antes de dar de baja; bloqueo real con viaje en curso.
- [ ] **PUS-12** — Botones que no aplican, con tooltip explicando por qué.
- [ ] **PUS-13** — Errores de validación junto al campo, en español.
- [ ] **PUS-14**/**PUS-15** — Catálogo desactivado no ofrecido en selectores; cuenta de baja no
  ofrecida como destinataria de alertas.

## Funcional (nuevos)

- [ ] **CHK-ADM-001** — Rotar la clave de Google Maps se refleja en la siguiente petición real
  saliente, sin reiniciar el backend.
- [ ] **CHK-ADM-002** — Un intento de restauración de prueba nunca acepta un nombre de base
  distinto al fijado en código.
- [ ] **CHK-ADM-003** — La política de retención de `posiciones` muestra el TTL real leído del
  índice de Mongo, no un texto fijo.

## Automatizado

- [ ] `backend/tests/usuarios/`, `configuracion/`, `catalogos/`, `integraciones/`, `sistema/`,
  `seguridad/`, `respaldos/`.
- [ ] `npm run test -w @urbanflet/web-interno`.

## No verificable automáticamente

- [ ] Respaldo real completo con volumen real del entorno (no disparar en cada verificación —
  tarda minutos contra bases reales).
- [ ] Anonimización real completada (irreversible — verificar solo hasta la doble confirmación,
  nunca ejecutar sobre una cuenta real sin ser desechable).
