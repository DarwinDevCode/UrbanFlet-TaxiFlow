# Especificación: Auditoría y Trazabilidad (Transversal)

> Documento retroactivo. Fuente principal: `FUNCIONALIDADES_TRANSVERSALES.md` §1, verificada contra
> `backend/src/auditoria/` y `backend/src/plataforma/`.

## 1. Objetivo

Sostener la trazabilidad completa del sistema (quién hizo qué, cuándo, con qué resultado) y la
transparencia de origen de los datos que alimentan los niveles táctico y estratégico. No es un
proceso de negocio de la cooperativa — es la infraestructura que hace posible confiar en todo lo
demás.

## 2. Contexto

Cualquier acción de negocio, en cualquiera de los 3 niveles, debe poder reconstruirse después. Y
cualquier cifra de un dashboard táctico/estratégico debe poder rastrearse hasta su origen real. Esta
capa cubre ambas necesidades con 2 mecanismos relacionados pero distintos: la bitácora (quién hizo
qué) y el catálogo de informes (de dónde sale cada dato agregado).

## 3. Actores

- **`supervisor_cumplimiento`** — vista completa de la bitácora (todos los eventos, operativos y
  administrativos mezclados).
- **`admin_sistema`** — vista de la bitácora filtrada solo a acciones administrativas.
- **`responsable_plataforma`** — catálogo de informes publicados.
- **Cualquier actor del sistema** — genera eventos de bitácora simplemente al usar el sistema, sin
  interacción directa con este módulo.

## 4. Requisitos funcionales

### RF-AUD-001 — Bitácora completa
El sistema debe registrar cronológicamente toda acción relevante: quién, cuándo, sobre qué entidad,
y si se permitió o denegó — consultable con filtros de actor, entidad, acción, resultado.

### RF-AUD-002 — Vista administrativa filtrada
Debe existir una segunda vista sobre la misma colección, acotada a las acciones que ocurren dentro
de Administración del Sistema, sin mezclarlas con el volumen de eventos operativos del día a día —
aclarado en pantalla que es la misma fuente, no un segundo registro.

### RF-AUD-003 — Antes/después en eventos administrativos
Varios eventos de la vista administrativa deben ofrecer "Ver antes/después" con el valor exacto del
campo modificado, no solo que "algo cambió".

### RF-AUD-004 — Catálogo de informes publicados
El sistema debe mostrar, en un solo lugar, todos los informes que el proceso de datos ya publicó,
con su fecha de datos y hora de última actualización real.

### RF-AUD-005 — Degradación honesta ante una corrida fallida
Si la corrida de hoy de un dominio falla, el catálogo debe seguir mostrando la última versión buena
con un aviso de retraso — nunca un informe a medio publicar.

## 5. Requisitos no funcionales

### RNF-AUD-001 — Write-ahead (RN-SIS-002)
El evento de bitácora se escribe antes de confirmar el efecto de negocio en toda acción sensible.

## 6. Reglas de negocio

### RN-AUD-001
La vista administrativa nunca es una fuente de datos independiente — es un filtro sobre la misma
bitácora completa, y el propio sistema lo aclara en pantalla.

## 7. Entradas

Filtros de consulta (actor/entidad/acción/resultado en la bitácora; ninguno en el catálogo, que
siempre muestra todo).

## 8. Salidas

Listado de eventos con fecha/actor/rol/acción/entidad/resultado; listado de informes publicados con
fecha de datos y última actualización.

## 9. Estados posibles

No aplica — ambos son registros de solo lectura sobre eventos ya ocurridos.

## 10. Escenarios

### Escenario 1: Reconstruir una acción reciente
Dado que se ejecutó cualquier acción de negocio en cualquiera de los 3 niveles
Cuando se abre la bitácora y se filtra por la entidad correspondiente
Entonces aparece el evento real con actor, hora y resultado exactos.

### Escenario 2: Confirmar que el proceso de datos sigue vivo
Dado que el proceso de datos corrió al menos una vez
Cuando se abre el catálogo de informes
Entonces se ve cada informe con su hora de actualización real, sin ningún informe a medio publicar.

## 11. Criterios de aceptación

### CA-AUD-001
Toda acción sensible ejecutada en el sistema deja un evento de bitácora verificable en menos de
1 minuto.

### CA-AUD-002
La vista administrativa y la vista completa muestran el mismo evento para una acción administrativa
real, sin divergencia de datos.

## 12. Dependencias

- Consumida por los 3 niveles organizacionales completos — es la única capa transversal que todos
  los módulos de este documento citan como dependencia.

## 13. Fuera de alcance

- **Anonimización automática de la bitácora** — el `actor_id` ya es un UUID opaco desde siempre
  (nunca el dato personal en sí), así que la seudonimización real vive en
  `004-transversal/administracion-del-sistema` (Gobernanza de Datos), no acá.
