# Especificación: Control Financiero (Nivel Operativo)

> Documento retroactivo. Fuente principal: `AUDITORIA_FUNCIONAL_OPERATIVO.md` §5, verificada contra
> `backend/src/recaudacion/`.

## 1. Objetivo

Cerrar financieramente cada semana: detectar y resolver discrepancias entre lo cobrado y la tarifa
real, generar el lote de liquidaciones de socios, y aprobarlas/pagarlas — con alerta para socios que
acumulan periodos consecutivos en rojo.

## 2. Contexto

El cobro es en efectivo, reportado por el propio conductor — sin un mecanismo de control, un error
(intencional o no) al reportar el monto cobrado no se detectaría nunca, y no habría forma
sistemática de saldar cuentas con los socios semana a semana.

## 3. Actores

- **`admin_financiero`** (personal interno) — único actor con acceso.
- **`conductor`** — genera las discrepancias/liquidaciones simplemente al cobrar viajes, sin
  interacción directa con este módulo.

## 4. Requisitos funcionales

### RF-FIN-001 — Bandeja de discrepancias de pago
El sistema debe listar todo pago cuyo monto cobrado no coincida con la tarifa final, con la
diferencia exacta, y permitir resolverlas.

### RF-FIN-002 — Viajes finalizados sin pago
El sistema debe listar viajes `FINALIZADO` hace más de 24h sin ningún pago registrado (informativo,
sin acción de resolución propia todavía).

### RF-FIN-003 — Generación de liquidaciones semanales
El sistema debe generar el lote de liquidaciones de la semana viernes-a-viernes más reciente ya
cerrada, sin duplicar lo ya emitido si se vuelve a pulsar.

### RF-FIN-004 — Ciclo de aprobación de una liquidación
Una liquidación debe poder pasar de `EMITIDA` a `OBSERVADA`/`APROBADA`, y de `APROBADA` a `PAGADA`.

### RF-FIN-005 — Alerta de saldo negativo consecutivo
El sistema debe señalar a los socios con 2+ periodos consecutivos con saldo negativo sin
regularizar, como monitoreo — sin acción automática asociada.

## 5. Requisitos no funcionales

### RNF-FIN-001 — Comisión versionada, no un valor fijo en código
El porcentaje de comisión de la cooperativa es un parámetro versionado con vigencia por fecha
(`parametros`, `tipo=comision`), nunca una constante en el código — un cambio de comisión aplica a
los viajes desde su fecha de vigencia, sin recalcular los ya finalizados antes de esa fecha.

## 6. Reglas de negocio

### RN-FIN-001
Un socio sin viajes pagados en el periodo simplemente no genera liquidación — no es un error si
algunos conductores no aparecen en un periodo dado.

### RN-FIN-002
Solo existe **una** versión vigente de comisión a la vez, exigida por un índice único parcial en
Mongo sobre `{tipo, franja, vigente_hasta:null}` — una inserción manual que intentara crear una
segunda versión vigente falla a nivel de base de datos, no solo de aplicación.

### RN-FIN-003
La corrección de una liquidación ya `PAGADA` no es posible directamente — requeriría una nota de
ajuste, fuera de alcance por decisión consciente (RN-SIS-005).

## 7. Entradas

- Resolución manual de una discrepancia (monto correcto).
- Fecha de disparo de "Generar liquidaciones" (siempre calcula la semana ya cerrada respecto a
  ahora, no acepta un periodo como parámetro).
- Decisión sobre una liquidación (aprobar/observar/marcar pagada).

## 8. Salidas

- Discrepancias con su diferencia exacta.
- Lote de liquidaciones nuevas, con conductor, periodo, estado, neto en mano y saldo.
- Alertas de saldo negativo consecutivo.

## 9. Estados posibles

Liquidación: `EMITIDA` → `OBSERVADA`/`APROBADA` → `PAGADA`.

## 10. Escenarios

### Escenario 1: Resolución de una discrepancia real
Dado que existe un pago con monto cobrado distinto a la tarifa final
Cuando `admin_financiero` revisa la diferencia y la resuelve
Entonces la discrepancia deja de aparecer en la bandeja.

### Escenario 2: Generación sin duplicar
Dado que ya se generaron las liquidaciones de la semana cerrada más reciente
Cuando `admin_financiero` vuelve a pulsar "Generar liquidaciones"
Entonces no se crea ningún duplicado.

### Escenario 3: Cambio de comisión sin afectar viajes ya cobrados
Dado que existe una nueva versión de comisión con vigencia desde una fecha futura
Cuando se cobran viajes antes y después de esa fecha
Entonces cada viaje aplica la comisión vigente en su propia fecha, no la más reciente.

## 11. Criterios de aceptación

Reusa `PLAN_DE_PRUEBAS.md` (los pagos/liquidaciones forman parte del ciclo verificado en **PD-01**).

### CA-FIN-001
Un intento de insertar manualmente una segunda versión de comisión vigente en Mongo es rechazado
por el índice único, no solo por validación de aplicación.

### CA-FIN-002
Una liquidación `PAGADA` no ofrece ningún botón de edición directa de su monto.

## 12. Dependencias

- **003-operativo/operaciones-y-despacho** — origen de cada pago y su tarifa real.
- **002-tactico/control-financiero** — agrega discrepancias y liquidaciones en 2 dashboards
  propios.
- **001-estrategico** (Rentabilidad, Integridad Financiera) — consume el margen de comisión real.

## 13. Fuera de alcance

- **Corrección de una liquidación `PAGADA`** vía nota de ajuste — decisión consciente, no
  implementada.
- **Pago electrónico** — solo efectivo.
- **Suspensión automática de turno** para socios con saldo negativo consecutivo — la alerta es
  puramente informativa.
