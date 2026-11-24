# Checklist de validación: Dirección General

Criterios reales para confirmar que el módulo funciona hoy. Reusa casos de `PLAN_DE_PRUEBAS.md`
donde existen; agrega los que faltan.

## Funcional (reusado de `PLAN_DE_PRUEBAS.md`)

- [ ] **TU-08** — Gerencia, sin instrucciones, navega a un panel estratégico concreto en menos de
  3 minutos y explica correctamente con sus propias palabras qué significa el indicador (no solo
  repite el número). Ver criterio de éxito de 2 partes en el propio caso.
- [ ] **PUS-03** — Los 3 niveles organizacionales (operativo/táctico/estratégico) se distinguen
  visualmente en el menú, no solo por el texto del grupo.
- [ ] **PUS-04** — "Ver detalle" desde una tarjeta del Tablero Ejecutivo lleva al panel completo
  sin recargar la página.
- [ ] **PUS-05** — Un KPI con drill-down abre el detalle en la misma pantalla, sin perder el
  contexto de dónde se estaba.

## Funcional (nuevos, específicos de este módulo)

- [ ] **CHK-EST-001** — Con la cuenta `gerencia`, las 8 tarjetas del Tablero Ejecutivo muestran
  cifra real (no "—") y el pie dice "8 de 8 indicadores con dato publicado".
- [ ] **CHK-EST-002** — Cada cifra del Tablero coincide exactamente con la del panel de detalle
  correspondiente (verificar al menos 3 pares).
- [ ] **CHK-EST-003** — Con una cuenta sin `gerencia` (ej. `staff-verificacion`), el Tablero
  Ejecutivo, Rentabilidad y Gobernanza no aparecen en el menú.
- [ ] **CHK-EST-004** — Un intento directo de `GET /estrategico/tablero-ejecutivo` con un token de
  rol no autorizado (ej. `conductor`) devuelve 403.
- [ ] **CHK-EST-005** — En Confiabilidad y Rentabilidad, el filtro de zona aparece visible pero
  deshabilitado, con una nota explicando por qué (no ausente, no funcional simulado).
- [ ] **CHK-EST-006** — En Integridad Financiera, filtrar por año 2026 excluye del gráfico los
  periodos `2021-01`/`2021-02` del dataset histórico, dejando solo operación real.
- [ ] **CHK-EST-007** — En Rendimiento/Desempeño de Conductores, la advertencia de concentración
  histórica aparece incluso con "Ventana reciente" activada, cuando el rango filtrado igual incluye
  periodos del dataset NYC 2021 (regresión ya cubierta por un test de backend,
  `test_ventana_reciente_no_evita_la_advertencia_si_igual_incluye_nyc`).

## Automatizado

- [ ] `backend/tests/estrategico/test_nivel_estrategico.py` — 19 casos (403 por rol, agregación
  real, fórmula de Rentabilidad). Correr con `docker cp backend/tests
  urbanflet-taxiflow-backend-1:/app/` primero (ver aviso en `PLAN_DE_PRUEBAS.md` §1.2).
- [ ] `npm run build/lint/test -w @urbanflet/web-interno` — sin errores nuevos, 0 warnings nuevos.

## No verificable automáticamente / requiere navegador real

- [ ] Patrón Z (7 paneles) vs. patrón F (Rentabilidad, Gobernanza) medido con `getComputedStyle` —
  confirmar que son dos grids genuinamente distintos, no el mismo layout reusado por accidente.
- [ ] Navegación cruzada real: clic en "Ver detalle" no cambia `location.href`.
