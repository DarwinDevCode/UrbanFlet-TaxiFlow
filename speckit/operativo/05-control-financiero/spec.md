# Especificación: Departamento de Control Financiero

**Nivel:** Operativo · **Objetivo que respalda:** OP5 — Cobro y liquidación de los viajes ·
**Responsable:** Administrador Financiero

## 1. Objetivo

Verificar que lo cobrado en cada viaje sea correcto y liquidar a cada socio conductor lo que le
corresponde, aplicando la comisión que sostiene a la cooperativa.

## 2. Contexto

Es el compromiso central de la cooperativa con sus socios: que cada viaje trabajado se refleje
íntegro en su liquidación. Eso exige tanto detectar discrepancias entre lo cobrado y lo debido como
cerrar, de forma periódica y verificable, el pago real a cada conductor.

## 3. Usuarios o actores

- **Administrador Financiero** — resuelve discrepancias, emite y gestiona liquidaciones.
- **Sistema** — calcula la comisión, agrupa movimientos por período, detecta discrepancias.

## 4. Funcionalidad — Conciliación de pagos y liquidación a socios (CU-O08)

### 4.1 Requisitos funcionales

**Discrepancias**

- **RF-FIN-001**: El sistema debe presentar al Administrador Financiero los pagos en los que el
  monto cobrado no coincide con la tarifa calculada del viaje, con la diferencia exacta.
- **RF-FIN-002**: El sistema debe excluir automáticamente del cierre del período cualquier viaje con
  una discrepancia todavía sin resolver; si se resuelve más tarde, entra al período que corresponda
  al momento de la resolución, sin intervención manual adicional.

**Generación del lote**

- **RF-FIN-003**: El sistema debe permitir emitir, con una sola acción, las liquidaciones del
  período semanal ya cerrado, consolidando por socio los viajes pagados de ese período y aplicando
  la comisión vigente en ese momento.
- **RF-FIN-004**: Repetir la generación para un período ya procesado no debe duplicar ninguna
  liquidación ya emitida.

**Ciclo de aprobación**

- **RF-FIN-005**: El sistema debe permitir que cada liquidación avance por sus estados: emitida →
  (observada) → aprobada → pagada.
- **RF-FIN-006**: El sistema debe mostrar, en el detalle de cada liquidación, los movimientos
  individuales que la componen.

**Alertas de saldo negativo**

- **RF-FIN-007**: El sistema debe identificar a los socios cuyas últimas liquidaciones consecutivas
  (2 o más, según umbral configurado) están todas en saldo negativo y ninguna ha llegado a pagada,
  y presentarlos en una vista separada para seguimiento.

### 4.2 Reglas de negocio

- **RN-FIN-001**: Un viaje con una discrepancia de pago abierta nunca entra en el cálculo de una
  liquidación mientras esa discrepancia no se resuelva.
- **RN-FIN-002**: El saldo de una liquidación se calcula como lo cobrado por medios electrónicos
  menos la comisión retenida sobre el efectivo cobrado por el socio; en el modelo de cobro
  100% en efectivo actual, esto significa que el saldo es la comisión que el socio le debe a la
  cooperativa, no un pago pendiente hacia el socio.
- **RN-FIN-003**: Un ajuste financiero autorizado sobre un viaje ya recaudado se arrastra a la
  primera liquidación que se genere después de creado, sin importar cuándo ocurrió el viaje
  original.
- **RN-FIN-004**: La comisión aplicada es la vigente en el momento del viaje, no la vigente en el
  momento de generar la liquidación.

### 4.3 Entradas

Fecha del viaje/pago, monto cobrado registrado por el conductor, decisión sobre una discrepancia,
decisión sobre una liquidación (aprobar/observar/pagar).

### 4.4 Salidas

Lista de discrepancias con su diferencia; lote de liquidaciones emitidas por período; liquidación
con su estado y detalle de movimientos; lista de socios en alerta de saldo negativo.

### 4.5 Escenarios

**Escenario: generación de lote sin duplicar**
Dado que ya se generaron las liquidaciones del período cerrado la semana pasada
Cuando el Administrador Financiero vuelve a ejecutar la generación
Entonces el sistema informa cuántas liquidaciones ya existían y no crea duplicados.

**Escenario: discrepancia resuelta después del cierre**
Dado que un viaje quedó con una discrepancia sin resolver cuando cerró su período
Cuando el Administrador Financiero la resuelve una semana después
Entonces ese viaje entra en el período correspondiente al momento en que se resolvió, no en el
original.

**Escenario: alerta de saldo negativo**
Dado que un socio acumula 2 liquidaciones consecutivas con saldo negativo, ninguna pagada
Cuando el Administrador Financiero abre la vista de alertas
Entonces ese socio aparece listado con sus 2 períodos consecutivos.

### 4.6 Criterios de aceptación

- **CA-FIN-001**: Repetir la generación de liquidaciones de un mismo período nunca produce una
  segunda liquidación para el mismo socio y período.
- **CA-FIN-002**: Un viaje con discrepancia abierta no aparece en el detalle de ninguna liquidación
  hasta que la discrepancia se resuelve.
- **CA-FIN-003**: El detalle de una liquidación muestra el mismo total que la suma de sus
  movimientos individuales.

## 5. Requisitos no funcionales

- **RNF-FIN-001 (trazabilidad)**: Toda decisión sobre una liquidación (observar, aprobar, pagar)
  queda registrada en la bitácora de auditoría con el actor.

## 6. Dependencias

- Operaciones y Despacho: cada liquidación se construye a partir de los viajes pagados y sus
  discrepancias.
- Parámetro de comisión versionado (compartido con el resto del sistema financiero).

## 7. Fuera de alcance

- Pago electrónico como método de cobro — el modelo de saldo asume 100% de cobro en efectivo; no
  existe todavía un camino de cobro electrónico construido.
- Suspensión automática de turno para un socio con saldo negativo impago sostenido — el sistema
  genera la alerta al Administrador Financiero, pero no bloquea el inicio de turno del conductor.
- Corrección de una liquidación ya pagada mediante una nota de ajuste posterior.

---

**Trazabilidad**: Nivel Operativo → Departamento Control Financiero → OP5 → CU-O08 →
`web-interno` → Finanzas → `backend/src/recaudacion/`.
