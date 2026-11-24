# Checklist de validación: Inteligencia de Negocio y Plataforma (Táctico)

## Funcional (nuevos)

- [ ] **CHK-TPL-001** — Filtrar la tabla de corridas por dominio reduce el resultado con efecto
  real.
- [ ] **CHK-TPL-002** — Una corrida real con % de rechazo alto se ve como `WARN`, no oculta ni
  redondeada a "OK".

## Automatizado

- [ ] `backend/tests/plataforma/`.

## No verificable automáticamente

- [ ] Corrida real de cualquiera de los 7 DAGs de dominio, observando su reflejo en este panel.
