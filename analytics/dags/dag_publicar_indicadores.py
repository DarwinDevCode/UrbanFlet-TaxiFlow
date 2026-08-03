"""CU-O16 -- dag_publicar_indicadores

`schedule_interval=None`: este DAG no corre por cron, corre por evento --
dos caminos posibles para dispararlo:

1. **Automático (CU-O16 P1, "con la carga Gold confirmada, el sistema
   refresca las vistas materializadas")**: cada uno de los 6 DAGs de
   dominio (`dag_viajes_core`, `dag_finanzas_gold`, `dag_captacion_gold`,
   `dag_cumplimiento_gold`, `dag_mantenimiento_gold`, `dag_flota_gold` --
   este último horario, así que dispara varias veces al día) termina su
   propia cadena extraer→silver→gold→métricas con un
   `TriggerDagRunOperator` que dispara una corrida de este DAG. `metricas`
   solo llega a ejecutarse sin excepción cuando la corrida quedó OK o WARN
   (FAILED corta la cadena antes, vía `on_failure_callback`), así que el
   trigger implica la precondición sin necesidad de pasarle el estado
   explícitamente.
2. **Manual (A2)**: "el Responsable puede regenerar [una vista
   materializada corrupta o inconsistente] desde Gold sin re-ejecutar el
   DAG [fuente]" -- disparo manual desde la UI o API de Airflow, exactamente
   igual que el camino automático (misma DAG, mismas tareas).

Las 8 tareas son independientes entre sí (sin `>>`): cada una vuelve a
calcular su informe desde el estado actual de Gold y hace un nuevo INSERT de
snapshot en su tabla `rpt_*` (ver analytics/plugins/indicadores.py para el
porqué ese INSERT es el "swap atómico" de A3). Por diseño, disparar este DAG
de más (p. ej. el trigger de un dominio que no toca un informe en particular)
es inofensivo: cada tarea vuelve a chequear la precondición OK/WARN de SU
PROPIO dominio (`indicadores._ultima_corrida_ok_o_warn`) antes de escribir
-- si esa corrida no cambió, el nuevo snapshot es idéntico al anterior.
"""
from __future__ import annotations

import sys
from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator

sys.path.append("/opt/airflow/plugins")
import indicadores  # noqa: E402

DAG_ID = "dag_publicar_indicadores"

with DAG(
    dag_id=DAG_ID,
    description="CU-O16 P1/A2: regenera los informes tácticos (rpt_*) desde el estado actual de Gold -- disparado automáticamente por los DAGs de dominio al terminar OK/WARN, o manualmente (A2) sin re-ejecutar los DAGs fuente.",
    schedule_interval=None,
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["cu-o16", "indicadores", "trigger-driven"],
) as dag:

    PythonOperator(task_id="flota_activa_franja", python_callable=indicadores.refrescar_flota_activa)
    PythonOperator(task_id="tasa_discrepancias", python_callable=indicadores.refrescar_tasa_discrepancias)
    PythonOperator(task_id="margen_comision", python_callable=indicadores.refrescar_margen_comision)
    PythonOperator(task_id="conversion_onboarding", python_callable=indicadores.refrescar_conversion_onboarding)
    PythonOperator(task_id="documentacion_vigente", python_callable=indicadores.refrescar_documentacion_vigente)
    PythonOperator(task_id="uso_integraciones", python_callable=indicadores.refrescar_uso_integraciones)
    PythonOperator(
        task_id="cumplimiento_plan_preventivo", python_callable=indicadores.refrescar_cumplimiento_plan_preventivo
    )
    PythonOperator(
        task_id="costo_mantenimiento_vehiculo", python_callable=indicadores.refrescar_costo_mantenimiento_vehiculo
    )
    PythonOperator(task_id="conversion_captacion", python_callable=indicadores.refrescar_conversion_captacion)
    PythonOperator(task_id="altas_retencion_canal", python_callable=indicadores.refrescar_altas_retencion_canal)
    PythonOperator(task_id="tiempo_asignacion", python_callable=indicadores.refrescar_tiempo_asignacion)
    PythonOperator(task_id="tasa_cancelacion", python_callable=indicadores.refrescar_tasa_cancelacion)
    PythonOperator(task_id="cuarentena_dominio", python_callable=indicadores.refrescar_cuarentena_dominio)
