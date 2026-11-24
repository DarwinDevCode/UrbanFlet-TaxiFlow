from tests.utils import auth_headers, crear_conductor_con_vehiculo, crear_usuario_activo


async def _jefe_headers(db):
    await crear_usuario_activo(db, usuario_id="u-jefe-mant", telefono="+593950000001", roles=["jefe_mantenimiento"])
    return auth_headers("u-jefe-mant", ["jefe_mantenimiento"])


async def _conductor_con_vehiculo(db, n: int, **overrides):
    return await crear_conductor_con_vehiculo(
        db, conductor_id=f"c{n}", telefono=f"+59395000001{n}", vehiculo_id=f"v{n}", placa=f"MNT-000{n}", **overrides
    )


async def test_crear_orden_sin_retiro_no_cambia_estado_del_vehiculo(client, db):
    headers = await _jefe_headers(db)
    await _conductor_con_vehiculo(db, 1)

    resp = await client.post(
        "/mantenimiento/ordenes",
        headers=headers,
        json={
            "vehiculo_id": "v1",
            "tipo": "PREVENTIVA",
            "descripcion": "Cambio de aceite",
            "km_entrada": 15000,
            "taller": "Taller Central",
            "fecha_programada": "2026-08-01",
            "retirar_vehiculo": False,
        },
    )

    assert resp.status_code == 201
    assert resp.json()["estado"] == "ABIERTA"
    v = await db.vehiculos.find_one({"_id": "v1"})
    assert v["estado_habilitacion"] == "HABILITADO"


async def test_crear_orden_con_retiro_marca_vehiculo_retirado(client, db):
    headers = await _jefe_headers(db)
    await _conductor_con_vehiculo(db, 2)

    resp = await client.post(
        "/mantenimiento/ordenes",
        headers=headers,
        json={
            "vehiculo_id": "v2",
            "tipo": "CORRECTIVA",
            "descripcion": "Falla de frenos",
            "km_entrada": 20000,
            "taller": "Taller Norte",
            "fecha_programada": "2026-08-02",
            "retirar_vehiculo": True,
        },
    )

    assert resp.status_code == 201
    v = await db.vehiculos.find_one({"_id": "v2"})
    assert v["estado_habilitacion"] == "RETIRADO_DE_SERVICIO"

    evento = await db.bitacora.find_one({"entidad_id": "v2", "accion": "VEHICULO_RETIRO"})
    assert evento is not None


async def test_flujo_completo_taller_y_cierre_con_habilitacion(client, db):
    headers = await _jefe_headers(db)
    await _conductor_con_vehiculo(db, 3)

    creada = await client.post(
        "/mantenimiento/ordenes",
        headers=headers,
        json={
            "vehiculo_id": "v3",
            "tipo": "CORRECTIVA",
            "descripcion": "Revisión motor",
            "km_entrada": 30000,
            "taller": "Taller Sur",
            "fecha_programada": "2026-08-03",
            "retirar_vehiculo": True,
        },
    )
    orden_id = creada.json()["id"]

    en_taller = await client.post(f"/mantenimiento/ordenes/{orden_id}/taller", headers=headers)
    assert en_taller.status_code == 200
    assert en_taller.json()["estado"] == "EN_TALLER"

    cierre = await client.post(
        f"/mantenimiento/ordenes/{orden_id}/cierre",
        headers=headers,
        json={
            "trabajos_realizados": "Cambio de bomba de agua",
            "repuestos_consumidos": [{"descripcion": "Bomba de agua", "cantidad": 1, "costo_unitario": 80.0}],
            "costo_total": 95.5,
            "km_salida": 30010,
            "habilitar_vehiculo": True,
        },
    )
    assert cierre.status_code == 200
    assert cierre.json()["estado"] == "CERRADA"

    v = await db.vehiculos.find_one({"_id": "v3"})
    assert v["estado_habilitacion"] == "HABILITADO"

    evento_habilitacion = await db.bitacora.find_one({"entidad_id": "v3", "accion": "VEHICULO_HABILITACION"})
    assert evento_habilitacion is not None


async def test_cerrar_orden_no_en_taller_devuelve_409(client, db):
    headers = await _jefe_headers(db)
    await _conductor_con_vehiculo(db, 4)
    creada = await client.post(
        "/mantenimiento/ordenes",
        headers=headers,
        json={
            "vehiculo_id": "v4",
            "tipo": "PREVENTIVA",
            "descripcion": "Filtro",
            "km_entrada": 1000,
            "taller": "Taller",
            "fecha_programada": "2026-08-04",
        },
    )
    orden_id = creada.json()["id"]

    resp = await client.post(
        f"/mantenimiento/ordenes/{orden_id}/cierre",
        headers=headers,
        json={"trabajos_realizados": "x", "costo_total": 10, "km_salida": 1010},
    )

    assert resp.status_code == 409
    assert resp.json()["code"] == "ORDEN_ESTADO_INVALIDO"


async def test_cerrar_orden_km_salida_menor_sin_ajuste_devuelve_400(client, db):
    headers = await _jefe_headers(db)
    await _conductor_con_vehiculo(db, 5)
    creada = await client.post(
        "/mantenimiento/ordenes",
        headers=headers,
        json={
            "vehiculo_id": "v5",
            "tipo": "PREVENTIVA",
            "descripcion": "Filtro",
            "km_entrada": 5000,
            "taller": "Taller",
            "fecha_programada": "2026-08-05",
        },
    )
    orden_id = creada.json()["id"]
    await client.post(f"/mantenimiento/ordenes/{orden_id}/taller", headers=headers)

    resp = await client.post(
        f"/mantenimiento/ordenes/{orden_id}/cierre",
        headers=headers,
        json={"trabajos_realizados": "x", "costo_total": 10, "km_salida": 4990},
    )

    assert resp.status_code == 400
    assert resp.json()["code"] == "KM_SALIDA_MENOR"


async def test_buscar_vehiculo_por_placa(client, db):
    headers = await _jefe_headers(db)
    await _conductor_con_vehiculo(db, 7)

    resp = await client.get("/mantenimiento/vehiculos/buscar", headers=headers, params={"placa": "mnt-000"})

    assert resp.status_code == 200
    resultados = resp.json()
    assert any(v["placa"] == "MNT-0007" for v in resultados)


async def test_anular_orden_reabilita_vehiculo_si_estaba_retirado(client, db):
    headers = await _jefe_headers(db)
    await _conductor_con_vehiculo(db, 6)
    creada = await client.post(
        "/mantenimiento/ordenes",
        headers=headers,
        json={
            "vehiculo_id": "v6",
            "tipo": "CORRECTIVA",
            "descripcion": "Choque",
            "km_entrada": 8000,
            "taller": "Taller",
            "fecha_programada": "2026-08-06",
            "retirar_vehiculo": True,
        },
    )
    orden_id = creada.json()["id"]

    resp = await client.post(
        f"/mantenimiento/ordenes/{orden_id}/anulacion", headers=headers, json={"motivo": "Duplicada por error"}
    )

    assert resp.status_code == 200
    assert resp.json()["estado"] == "ANULADA"
    v = await db.vehiculos.find_one({"_id": "v6"})
    assert v["estado_habilitacion"] == "HABILITADO"


async def test_listar_ordenes_devuelve_items_y_total(client, db):
    headers = await _jefe_headers(db)
    await _conductor_con_vehiculo(db, 8)
    await client.post(
        "/mantenimiento/ordenes",
        headers=headers,
        json={
            "vehiculo_id": "v8",
            "tipo": "PREVENTIVA",
            "descripcion": "Revisión",
            "km_entrada": 1000,
            "taller": "Taller Sur",
            "fecha_programada": "2026-08-08",
            "retirar_vehiculo": False,
        },
    )

    resp = await client.get("/mantenimiento/ordenes", headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert "total" in body
    assert body["total"] >= 1


async def test_listar_ordenes_pagina_resultados(client, db):
    headers = await _jefe_headers(db)
    for i in (9, 10, 11):
        await _conductor_con_vehiculo(db, i)
        await client.post(
            "/mantenimiento/ordenes",
            headers=headers,
            json={
                "vehiculo_id": f"v{i}",
                "tipo": "PREVENTIVA",
                "descripcion": "Revisión periódica",
                "km_entrada": 1000,
                "taller": "Taller Sur",
                "fecha_programada": "2026-08-09",
                "retirar_vehiculo": False,
            },
        )

    pagina1 = await client.get("/mantenimiento/ordenes?limit=2&offset=0", headers=headers)
    pagina2 = await client.get("/mantenimiento/ordenes?limit=2&offset=2", headers=headers)

    assert pagina1.status_code == 200
    body1 = pagina1.json()
    body2 = pagina2.json()
    assert len(body1["items"]) == 2
    assert body1["total"] == body2["total"]
    assert body1["total"] >= 3
    ids_pagina1 = {o["id"] for o in body1["items"]}
    ids_pagina2 = {o["id"] for o in body2["items"]}
    assert ids_pagina1.isdisjoint(ids_pagina2)


async def test_listar_ordenes_filtra_por_placa(client, db):
    headers = await _jefe_headers(db)
    await _conductor_con_vehiculo(db, 12)
    await client.post(
        "/mantenimiento/ordenes",
        headers=headers,
        json={
            "vehiculo_id": "v12",
            "tipo": "PREVENTIVA",
            "descripcion": "Revisión",
            "km_entrada": 1000,
            "taller": "Taller Sur",
            "fecha_programada": "2026-08-12",
            "retirar_vehiculo": False,
        },
    )

    resp = await client.get("/mantenimiento/ordenes?placa=MNT-00012", headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1


# --- Ronda 2, Fase B (H6/H7/H9): ficha del vehículo con km real -----------


async def test_ficha_vehiculo_sin_ordenes_previas_usa_umbral_desde_cero(client, db):
    headers = await _jefe_headers(db)
    await _conductor_con_vehiculo(db, 20)
    await db.vehiculos.update_one({"_id": "v20"}, {"$set": {"km_acumulado": 1200.5}})

    resp = await client.get("/mantenimiento/vehiculos/v20/ficha", headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["km_acumulado"] == 1200.5
    assert body["fecha_ultima_intervencion"] is None
    assert body["km_ultima_intervencion"] is None
    assert body["umbral_km_preventivo"] == 5000
    assert body["proxima_km_preventivo"] == 5000
    assert body["le_toca_preventivo"] is False


async def test_ficha_vehiculo_con_orden_cerrada_calcula_proxima_desde_km_salida(client, db):
    headers = await _jefe_headers(db)
    await _conductor_con_vehiculo(db, 21)

    creada = await client.post(
        "/mantenimiento/ordenes",
        headers=headers,
        json={
            "vehiculo_id": "v21",
            "tipo": "PREVENTIVA",
            "descripcion": "Cambio de aceite",
            "km_entrada": 4000,
            "taller": "Taller Central",
            "fecha_programada": "2026-08-01",
            "retirar_vehiculo": False,
        },
    )
    orden_id = creada.json()["id"]
    await client.post(f"/mantenimiento/ordenes/{orden_id}/taller", headers=headers)
    cierre = await client.post(
        f"/mantenimiento/ordenes/{orden_id}/cierre",
        headers=headers,
        json={
            "trabajos_realizados": "Cambio de aceite y filtros",
            "repuestos_consumidos": [],
            "costo_total": 45.0,
            "km_salida": 4010,
            "habilitar_vehiculo": False,
        },
    )
    assert cierre.status_code == 200
    # H9: la respuesta del cierre ya trae la próxima proyección, sin
    # necesidad de una segunda llamada.
    assert cierre.json()["proxima_km_preventivo"] == 4010 + 5000

    await db.vehiculos.update_one({"_id": "v21"}, {"$set": {"km_acumulado": 9500}})

    resp = await client.get("/mantenimiento/vehiculos/v21/ficha", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["km_ultima_intervencion"] == 4010
    assert body["fecha_ultima_intervencion"] is not None
    assert body["proxima_km_preventivo"] == 9010
    # km_acumulado (9500) ya superó la próxima proyectada (9010) -> aviso.
    assert body["le_toca_preventivo"] is True


async def test_ficha_vehiculo_inexistente_devuelve_404(client, db):
    headers = await _jefe_headers(db)
    resp = await client.get("/mantenimiento/vehiculos/no-existe/ficha", headers=headers)
    assert resp.status_code == 404
    assert resp.json()["code"] == "VEHICULO_NO_ENCONTRADO"


# --- Autoservicio: GET /mantenimiento/vehiculos/mio/ficha ------------------


async def test_ficha_de_mi_vehiculo_conductor_con_vehiculo_propio(client, db):
    await _conductor_con_vehiculo(db, 30)
    await db.vehiculos.update_one({"_id": "v30"}, {"$set": {"km_acumulado": 2500}})
    headers = auth_headers("c30", ["conductor"])

    resp = await client.get("/mantenimiento/vehiculos/mio/ficha", headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == "v30"
    assert body["placa"] == "MNT-00030"
    assert body["km_acumulado"] == 2500
    assert body["proxima_km_preventivo"] == 5000
    assert body["le_toca_preventivo"] is False


async def test_ficha_de_mi_vehiculo_conductor_sin_vehiculo_devuelve_404(client, db):
    await crear_usuario_activo(db, usuario_id="c31-sin-vehiculo", telefono="+593950000031", roles=["conductor"])
    headers = auth_headers("c31-sin-vehiculo", ["conductor"])

    resp = await client.get("/mantenimiento/vehiculos/mio/ficha", headers=headers)

    assert resp.status_code == 404
    assert resp.json()["code"] == "VEHICULO_CONDUCTOR_NO_ASIGNADO"


async def test_ficha_de_mi_vehiculo_rechaza_a_jefe_mantenimiento(client, db):
    headers = await _jefe_headers(db)
    resp = await client.get("/mantenimiento/vehiculos/mio/ficha", headers=headers)
    assert resp.status_code == 403


async def test_ficha_vehiculo_por_id_rechaza_a_conductor(client, db):
    await _conductor_con_vehiculo(db, 32)
    headers = auth_headers("c32", ["conductor"])
    resp = await client.get("/mantenimiento/vehiculos/v32/ficha", headers=headers)
    assert resp.status_code == 403


# --- Ronda 2, Fase E: estado ESPERANDO_REPUESTO ----------------------------


async def _orden_en_taller(client, headers, *, vehiculo_id: str, fecha: str) -> str:
    creada = await client.post(
        "/mantenimiento/ordenes",
        headers=headers,
        json={
            "vehiculo_id": vehiculo_id,
            "tipo": "CORRECTIVA",
            "descripcion": "Revisión",
            "km_entrada": 1000,
            "taller": "Taller Central",
            "fecha_programada": fecha,
            "retirar_vehiculo": False,
        },
    )
    orden_id = creada.json()["id"]
    await client.post(f"/mantenimiento/ordenes/{orden_id}/taller", headers=headers)
    return orden_id


async def test_marcar_en_taller_queda_auditado(client, db):
    """H8 (Fase G, cerrado de paso en Fase E): antes esta transición no
    escribía ningún evento, a diferencia de crear/cerrar/anular."""
    headers = await _jefe_headers(db)
    await _conductor_con_vehiculo(db, 30)
    orden_id = await _orden_en_taller(client, headers, vehiculo_id="v30", fecha="2026-08-13")

    evento = await db.bitacora.find_one({"entidad_id": orden_id, "accion": "ORDEN_MANTENIMIENTO_EN_TALLER"})
    assert evento is not None
    assert evento["datos_posteriores"]["estado"] == "EN_TALLER"


async def test_marcar_esperando_repuesto_exige_estar_en_taller(client, db):
    headers = await _jefe_headers(db)
    await _conductor_con_vehiculo(db, 31)
    creada = await client.post(
        "/mantenimiento/ordenes",
        headers=headers,
        json={
            "vehiculo_id": "v31",
            "tipo": "CORRECTIVA",
            "descripcion": "Revisión",
            "km_entrada": 1000,
            "taller": "Taller Central",
            "fecha_programada": "2026-08-14",
        },
    )
    orden_id = creada.json()["id"]

    resp = await client.post(
        f"/mantenimiento/ordenes/{orden_id}/espera-repuesto", headers=headers, json={"motivo": "Repuesto en tránsito"}
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "ORDEN_ESTADO_INVALIDO"


async def test_marcar_esperando_repuesto_sin_motivo_devuelve_422(client, db):
    headers = await _jefe_headers(db)
    await _conductor_con_vehiculo(db, 32)
    orden_id = await _orden_en_taller(client, headers, vehiculo_id="v32", fecha="2026-08-15")

    resp = await client.post(f"/mantenimiento/ordenes/{orden_id}/espera-repuesto", headers=headers, json={"motivo": ""})
    assert resp.status_code == 422


async def test_flujo_espera_repuesto_ida_y_vuelta_y_cierre_directo(client, db):
    """EN_TALLER -> ESPERANDO_REPUESTO -> EN_TALLER (ida y vuelta), y una
    segunda orden que cierra directo desde ESPERANDO_REPUESTO sin reanudar."""
    headers = await _jefe_headers(db)
    await _conductor_con_vehiculo(db, 33)
    orden_id = await _orden_en_taller(client, headers, vehiculo_id="v33", fecha="2026-08-16")

    espera = await client.post(
        f"/mantenimiento/ordenes/{orden_id}/espera-repuesto",
        headers=headers,
        json={"motivo": "Repuesto importado, llega en 5 días"},
    )
    assert espera.status_code == 200
    assert espera.json()["estado"] == "ESPERANDO_REPUESTO"
    assert espera.json()["motivo_espera"] == "Repuesto importado, llega en 5 días"

    evento_espera = await db.bitacora.find_one(
        {"entidad_id": orden_id, "accion": "ORDEN_MANTENIMIENTO_ESPERA_REPUESTO"}
    )
    assert evento_espera is not None

    # No se puede cerrar mientras sigue esperando repuesto sin que el
    # endpoint lo permita explícitamente -- de hecho SÍ se permite (cierre
    # directo), se prueba en la segunda orden más abajo. Acá se prueba la
    # ida y vuelta primero.
    reanudar = await client.post(f"/mantenimiento/ordenes/{orden_id}/reanudar", headers=headers)
    assert reanudar.status_code == 200
    assert reanudar.json()["estado"] == "EN_TALLER"
    # El motivo se conserva como rastro histórico, no se borra al reanudar.
    assert reanudar.json()["motivo_espera"] == "Repuesto importado, llega en 5 días"

    evento_reanudacion = await db.bitacora.find_one(
        {"entidad_id": orden_id, "accion": "ORDEN_MANTENIMIENTO_REANUDACION"}
    )
    assert evento_reanudacion is not None

    cierre = await client.post(
        f"/mantenimiento/ordenes/{orden_id}/cierre",
        headers=headers,
        json={"trabajos_realizados": "Cambio de repuesto", "costo_total": 50.0, "km_salida": 1010},
    )
    assert cierre.status_code == 200
    assert cierre.json()["estado"] == "CERRADA"

    # Segunda orden: cierre DIRECTO desde ESPERANDO_REPUESTO, sin reanudar.
    await _conductor_con_vehiculo(db, 34)
    orden_id_2 = await _orden_en_taller(client, headers, vehiculo_id="v34", fecha="2026-08-17")
    await client.post(
        f"/mantenimiento/ordenes/{orden_id_2}/espera-repuesto", headers=headers, json={"motivo": "Esperando repuesto"}
    )
    cierre_directo = await client.post(
        f"/mantenimiento/ordenes/{orden_id_2}/cierre",
        headers=headers,
        json={"trabajos_realizados": "Llegó el repuesto y se cerró de una vez", "costo_total": 30.0, "km_salida": 1005},
    )
    assert cierre_directo.status_code == 200
    assert cierre_directo.json()["estado"] == "CERRADA"


async def test_reanudar_taller_exige_estar_esperando_repuesto(client, db):
    headers = await _jefe_headers(db)
    await _conductor_con_vehiculo(db, 35)
    orden_id = await _orden_en_taller(client, headers, vehiculo_id="v35", fecha="2026-08-18")

    resp = await client.post(f"/mantenimiento/ordenes/{orden_id}/reanudar", headers=headers)
    assert resp.status_code == 409
    assert resp.json()["code"] == "ORDEN_ESTADO_INVALIDO"


async def test_vehiculo_retirado_con_orden_esperando_repuesto_sigue_referenciada(client, db):
    """Ronda 2, Fase E: el panel táctico de 'vehículos retirados' filtraba
    solo ABIERTA/EN_TALLER -- una orden ESPERANDO_REPUESTO retiene el
    vehículo igual y debe seguir apareciendo referenciada."""
    headers = await _jefe_headers(db)
    await _conductor_con_vehiculo(db, 36)
    creada = await client.post(
        "/mantenimiento/ordenes",
        headers=headers,
        json={
            "vehiculo_id": "v36",
            "tipo": "CORRECTIVA",
            "descripcion": "Choque",
            "km_entrada": 1000,
            "taller": "Taller Central",
            "fecha_programada": "2026-08-19",
            "retirar_vehiculo": True,
        },
    )
    orden_id = creada.json()["id"]
    await client.post(f"/mantenimiento/ordenes/{orden_id}/taller", headers=headers)
    await client.post(
        f"/mantenimiento/ordenes/{orden_id}/espera-repuesto", headers=headers, json={"motivo": "Repuesto pedido"}
    )

    resp = await client.get("/mantenimiento/panel-tactico/vehiculos-retirados", headers=headers)
    assert resp.status_code == 200
    fila = next(v for v in resp.json() if v["vehiculo_id"] == "v36")
    assert fila["orden_id"] == orden_id
    assert fila["orden_estado"] == "ESPERANDO_REPUESTO"


# --- Ronda 2, Fase F: actividades embebidas en la orden --------------------


async def test_agregar_actividad_queda_visible_con_actor_y_fecha(client, db):
    headers = await _jefe_headers(db)
    await _conductor_con_vehiculo(db, 40)
    orden_id = await _orden_en_taller(client, headers, vehiculo_id="v40", fecha="2026-08-21")

    resp = await client.post(
        f"/mantenimiento/ordenes/{orden_id}/actividades",
        headers=headers,
        json={"detalle": "Se desmontó el motor para inspección"},
    )
    assert resp.status_code == 200
    actividades = resp.json()["actividades"]
    assert len(actividades) == 1
    assert actividades[0]["detalle"] == "Se desmontó el motor para inspección"
    assert actividades[0]["tipo"] == "COMENTARIO"
    assert actividades[0]["actor_id"] == "u-jefe-mant"
    assert actividades[0]["actor_nombre"] == "Actor de prueba"
    assert actividades[0]["rol"] == "jefe_mantenimiento"
    assert actividades[0]["ts"] is not None

    orden_db = await db.ordenes.find_one({"_id": orden_id})
    assert len(orden_db["actividades"]) == 1


async def test_agregar_actividad_fuera_de_taller_devuelve_409(client, db):
    headers = await _jefe_headers(db)
    await _conductor_con_vehiculo(db, 41)
    creada = await client.post(
        "/mantenimiento/ordenes",
        headers=headers,
        json={
            "vehiculo_id": "v41",
            "tipo": "CORRECTIVA",
            "descripcion": "Revisión",
            "km_entrada": 1000,
            "taller": "Taller Central",
            "fecha_programada": "2026-08-22",
        },
    )
    orden_id = creada.json()["id"]

    resp = await client.post(
        f"/mantenimiento/ordenes/{orden_id}/actividades", headers=headers, json={"detalle": "x"}
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "ORDEN_ESTADO_INVALIDO"


async def test_agregar_actividad_sin_detalle_devuelve_422(client, db):
    headers = await _jefe_headers(db)
    await _conductor_con_vehiculo(db, 42)
    orden_id = await _orden_en_taller(client, headers, vehiculo_id="v42", fecha="2026-08-23")

    resp = await client.post(f"/mantenimiento/ordenes/{orden_id}/actividades", headers=headers, json={"detalle": ""})
    assert resp.status_code == 422


async def test_espera_repuesto_y_reanudar_quedan_como_actividad_automatica(client, db):
    """La transición a ESPERANDO_REPUESTO (Fase E) no es un paso manual
    aparte -- se registra sola como actividad CAMBIO_ESTADO."""
    headers = await _jefe_headers(db)
    await _conductor_con_vehiculo(db, 43)
    orden_id = await _orden_en_taller(client, headers, vehiculo_id="v43", fecha="2026-08-24")

    espera = await client.post(
        f"/mantenimiento/ordenes/{orden_id}/espera-repuesto", headers=headers, json={"motivo": "Repuesto pedido"}
    )
    assert espera.status_code == 200
    actividades = espera.json()["actividades"]
    assert len(actividades) == 1
    assert actividades[0]["tipo"] == "CAMBIO_ESTADO"
    assert "Repuesto pedido" in actividades[0]["detalle"]

    reanudar = await client.post(f"/mantenimiento/ordenes/{orden_id}/reanudar", headers=headers)
    assert reanudar.status_code == 200
    actividades_2 = reanudar.json()["actividades"]
    assert len(actividades_2) == 2
    assert actividades_2[1]["tipo"] == "CAMBIO_ESTADO"

    # Cronológico: orden de inserción == orden de tiempo.
    assert actividades_2[0]["ts"] <= actividades_2[1]["ts"]


async def test_actividad_con_evidencia_queda_referenciada(client, db):
    headers = await _jefe_headers(db)
    await _conductor_con_vehiculo(db, 44)
    orden_id = await _orden_en_taller(client, headers, vehiculo_id="v44", fecha="2026-08-25")

    subida = await client.post(
        "/archivos",
        headers=headers,
        data={"contexto": "actividad_orden"},
        files={"file": ("avance.jpg", b"\xff\xd8\xff" + b"0" * 50, "image/jpeg")},
    )
    assert subida.status_code == 201
    archivo_id = subida.json()["id"]

    resp = await client.post(
        f"/mantenimiento/ordenes/{orden_id}/actividades",
        headers=headers,
        json={"detalle": "Repuesto instalado, prueba de funcionamiento OK", "evidencias": [archivo_id]},
    )
    assert resp.status_code == 200
    assert resp.json()["actividades"][0]["evidencias"] == [archivo_id]


# --- Ronda 2, Fase G: gaps menores -----------------------------------------


async def test_costo_estimado_se_calcula_al_crear_y_se_expone_en_la_respuesta(client, db):
    headers = await _jefe_headers(db)
    await _conductor_con_vehiculo(db, 50)

    resp = await client.post(
        "/mantenimiento/ordenes",
        headers=headers,
        json={
            "vehiculo_id": "v50",
            "tipo": "CORRECTIVA",
            "descripcion": "Frenos",
            "km_entrada": 1000,
            "taller": "Taller Central",
            "fecha_programada": "2026-08-26",
            "mano_obra_estimada": 30.0,
            "repuestos_estimados": [
                {"descripcion": "Pastillas", "cantidad": 2, "costo_unitario": 15.0},
                {"descripcion": "Disco", "cantidad": 1, "costo_unitario": 40.0},
            ],
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    # 30 (mano de obra) + 2*15 (pastillas) + 1*40 (disco) = 100.0
    assert body["costo_estimado"] == 100.0
    assert body["mano_obra_estimada"] == 30.0
    assert body["desviacion_costo_pct"] is None


async def test_cierre_calcula_desviacion_de_costo_en_el_mismo_evento_de_auditoria(client, db):
    headers = await _jefe_headers(db)
    await _conductor_con_vehiculo(db, 51)
    creada = await client.post(
        "/mantenimiento/ordenes",
        headers=headers,
        json={
            "vehiculo_id": "v51",
            "tipo": "CORRECTIVA",
            "descripcion": "Frenos",
            "km_entrada": 1000,
            "taller": "Taller Central",
            "fecha_programada": "2026-08-27",
            "mano_obra_estimada": 20.0,
            "repuestos_estimados": [{"descripcion": "Pastillas", "cantidad": 1, "costo_unitario": 30.0}],
        },
    )
    orden_id = creada.json()["id"]
    await client.post(f"/mantenimiento/ordenes/{orden_id}/taller", headers=headers)

    # costo_estimado = 50.0, costo_total real = 65.0 -> desviación +30%
    cierre = await client.post(
        f"/mantenimiento/ordenes/{orden_id}/cierre",
        headers=headers,
        json={"trabajos_realizados": "Cambio de pastillas", "costo_total": 65.0, "km_salida": 1010},
    )
    assert cierre.status_code == 200
    body = cierre.json()
    assert body["costo_estimado"] == 50.0
    assert body["desviacion_costo_pct"] == 30.0

    # Sin evento nuevo -- el mismo ORDEN_MANTENIMIENTO_CIERRE de siempre
    # lleva la desviación en datos_posteriores.
    eventos_cierre = await db.bitacora.find(
        {"entidad_id": orden_id, "accion": "ORDEN_MANTENIMIENTO_CIERRE"}
    ).to_list(length=10)
    assert len(eventos_cierre) == 1
    assert eventos_cierre[0]["datos_posteriores"]["costo_estimado"] == 50.0
    assert eventos_cierre[0]["datos_posteriores"]["desviacion_costo_pct"] == 30.0


async def test_cierre_con_orden_encadenada_crea_correctiva_hija(client, db):
    headers = await _jefe_headers(db)
    await _conductor_con_vehiculo(db, 52)
    orden_id = await _orden_en_taller(client, headers, vehiculo_id="v52", fecha="2026-08-28")

    cierre = await client.post(
        f"/mantenimiento/ordenes/{orden_id}/cierre",
        headers=headers,
        json={
            "trabajos_realizados": "Se detectó una falla adicional en el sistema eléctrico",
            "costo_total": 40.0,
            "km_salida": 1050,
            "orden_encadenada": {
                "descripcion": "Revisar sistema eléctrico detectado durante el cierre anterior",
                "taller": "Taller Norte",
                "fecha_programada": "2026-09-01",
            },
        },
    )
    assert cierre.status_code == 200
    body = cierre.json()
    assert body["estado"] == "CERRADA"
    assert body["orden_encadenada_id"] is not None

    hija = await db.ordenes.find_one({"_id": body["orden_encadenada_id"]})
    assert hija is not None
    assert hija["orden_madre_id"] == orden_id
    assert hija["vehiculo_id"] == "v52"
    assert hija["tipo"] == "CORRECTIVA"
    assert hija["estado"] == "ABIERTA"
    # km_entrada de la hija hereda el km_salida de la orden que se cerró.
    assert hija["km_entrada"] == 1050
    assert hija["taller"] == "Taller Norte"


async def test_cierre_sin_orden_encadenada_no_crea_ninguna_orden_extra(client, db):
    headers = await _jefe_headers(db)
    await _conductor_con_vehiculo(db, 53)
    orden_id = await _orden_en_taller(client, headers, vehiculo_id="v53", fecha="2026-08-29")

    cierre = await client.post(
        f"/mantenimiento/ordenes/{orden_id}/cierre",
        headers=headers,
        json={"trabajos_realizados": "Cierre normal", "costo_total": 10.0, "km_salida": 1005},
    )
    assert cierre.status_code == 200
    assert cierre.json()["orden_encadenada_id"] is None

    total_ordenes_v53 = await db.ordenes.count_documents({"vehiculo_id": "v53"})
    assert total_ordenes_v53 == 1


# ---------------------------------------------------------------------------
# Decisión 3 -- baja lógica de vehículos (estado nuevo DADO_DE_BAJA)
# ---------------------------------------------------------------------------


async def test_dar_de_baja_vehiculo_sin_ordenes_abiertas(client, db):
    headers = await _jefe_headers(db)
    await _conductor_con_vehiculo(db, 70)

    resp = await client.post(
        "/mantenimiento/vehiculos/v70/dar-de-baja", headers=headers, json={"motivo": "Vendido"}
    )

    assert resp.status_code == 200
    assert resp.json()["estado_habilitacion"] == "DADO_DE_BAJA"
    # El documento se conserva -- baja lógica, nunca borrado físico.
    vehiculo = await db.vehiculos.find_one({"_id": "v70"})
    assert vehiculo is not None
    assert vehiculo["estado_habilitacion"] == "DADO_DE_BAJA"
    assert vehiculo["motivo_baja"] == "Vendido"


async def test_no_permite_dar_de_baja_vehiculo_con_orden_abierta(client, db):
    """Mismo patrón que la baja de cuenta con viaje en curso: se rechaza con
    409 y un mensaje que nombra la orden concreta a cerrar."""
    headers = await _jefe_headers(db)
    await _conductor_con_vehiculo(db, 71)
    creada = await client.post(
        "/mantenimiento/ordenes",
        headers=headers,
        json={
            "vehiculo_id": "v71",
            "tipo": "CORRECTIVA",
            "descripcion": "Frenos",
            "km_entrada": 100,
            "taller": "Taller Central",
            "fecha_programada": "2026-09-01",
            "retirar_vehiculo": False,
        },
    )
    assert creada.status_code == 201

    resp = await client.post(
        "/mantenimiento/vehiculos/v71/dar-de-baja", headers=headers, json={"motivo": "Vendido"}
    )

    assert resp.status_code == 409
    assert resp.json()["code"] == "BAJA_VEHICULO_CON_ORDEN_ABIERTA"
    vehiculo = await db.vehiculos.find_one({"_id": "v71"})
    assert vehiculo["estado_habilitacion"] != "DADO_DE_BAJA"


async def test_vehiculo_dado_de_baja_no_aparece_en_la_busqueda(client, db):
    """No debe poder elegirse para procesos nuevos (crear una orden)."""
    headers = await _jefe_headers(db)
    await _conductor_con_vehiculo(db, 72)

    antes = await client.get("/mantenimiento/vehiculos/buscar?placa=MNT-00072", headers=headers)
    assert len(antes.json()) == 1

    await client.post("/mantenimiento/vehiculos/v72/dar-de-baja", headers=headers, json={"motivo": "Siniestro"})

    despues = await client.get("/mantenimiento/vehiculos/buscar?placa=MNT-00072", headers=headers)
    assert despues.json() == []


async def test_cerrar_orden_no_resucita_un_vehiculo_dado_de_baja(client, db):
    """`cerrar_orden` re-habilita el vehículo al terminar; ese camino debe
    respetar una baja permanente en vez de revertirla en silencio."""
    headers = await _jefe_headers(db)
    await _conductor_con_vehiculo(db, 73)
    creada = await client.post(
        "/mantenimiento/ordenes",
        headers=headers,
        json={
            "vehiculo_id": "v73",
            "tipo": "PREVENTIVA",
            "descripcion": "Aceite",
            "km_entrada": 100,
            "taller": "Taller Central",
            "fecha_programada": "2026-09-01",
            "retirar_vehiculo": True,
        },
    )
    orden_id = creada.json()["id"]
    en_taller = await client.post(f"/mantenimiento/ordenes/{orden_id}/taller", headers=headers)
    assert en_taller.status_code == 200
    # Se fuerza el estado a DADO_DE_BAJA para simular una baja que ocurrió
    # por otra vía mientras la orden seguía abierta.
    await db.vehiculos.update_one({"_id": "v73"}, {"$set": {"estado_habilitacion": "DADO_DE_BAJA"}})

    cierre = await client.post(
        f"/mantenimiento/ordenes/{orden_id}/cierre",
        headers=headers,
        json={
            "trabajos_realizados": "Cambio de aceite",
            "costo_total": 50.0,
            "km_salida": 150,
            "horas_taller": 2.0,
            "repuestos_consumidos": [],
        },
    )

    assert cierre.status_code == 200
    vehiculo = await db.vehiculos.find_one({"_id": "v73"})
    assert vehiculo["estado_habilitacion"] == "DADO_DE_BAJA"


# ---------------------------------------------------------------------------
# Punto 3 del cierre integral -- edición de vehículo (la U que faltaba)
# ---------------------------------------------------------------------------


async def test_editar_vehiculo_corrige_datos_descriptivos(client, db):
    headers = await _jefe_headers(db)
    await _conductor_con_vehiculo(db, 80)

    resp = await client.patch(
        "/mantenimiento/vehiculos/v80", headers=headers, json={"placa": "XYZ-9999", "color": "Azul"}
    )

    assert resp.status_code == 200
    assert resp.json()["placa"] == "XYZ-9999"
    vehiculo = await db.vehiculos.find_one({"_id": "v80"})
    assert vehiculo["placa"] == "XYZ-9999"
    assert vehiculo["color"] == "Azul"
    # Los campos no enviados no se tocan.
    assert vehiculo["estado_habilitacion"] == "HABILITADO"
    evento = await db.bitacora.find_one({"accion": "VEHICULO_EDICION", "entidad_id": "v80"})
    assert evento is not None
    assert evento["datos_previos"]["placa"] != "XYZ-9999"


async def test_editar_vehiculo_dado_de_baja_es_conflicto(client, db):
    """Un vehículo fuera de la flota ya no se edita -- mismo criterio que una
    cuenta dada de baja."""
    headers = await _jefe_headers(db)
    await _conductor_con_vehiculo(db, 81)
    await client.post("/mantenimiento/vehiculos/v81/dar-de-baja", headers=headers, json={"motivo": "Vendido"})

    resp = await client.patch("/mantenimiento/vehiculos/v81", headers=headers, json={"color": "Rojo"})

    assert resp.status_code == 409
    assert resp.json()["code"] == "VEHICULO_YA_DADO_DE_BAJA"


async def test_editar_vehiculo_inexistente_da_404(client, db):
    headers = await _jefe_headers(db)
    resp = await client.patch("/mantenimiento/vehiculos/no-existe", headers=headers, json={"color": "Rojo"})
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Ronda "corrección acotada por estado"
# ---------------------------------------------------------------------------


async def test_corregir_orden_abierta_permite_los_5_campos(client, db):
    headers = await _jefe_headers(db)
    await _conductor_con_vehiculo(db, 90)
    creada = await client.post(
        "/mantenimiento/ordenes",
        headers=headers,
        json={
            "vehiculo_id": "v90",
            "tipo": "CORRECTIVA",
            "descripcion": "Frenos",
            "km_entrada": 1000,
            "taller": "Taller Central",
            "fecha_programada": "2026-09-01",
            "retirar_vehiculo": False,
            "repuestos_estimados": [{"descripcion": "Pastillas", "cantidad": 1, "costo_unitario": 20.0}],
            "mano_obra_estimada": 15.0,
        },
    )
    orden_id = creada.json()["id"]

    resp = await client.patch(
        f"/mantenimiento/ordenes/{orden_id}/correccion",
        headers=headers,
        json={
            "descripcion": "Frenos y suspensión",
            "taller": "Taller Norte",
            "fecha_programada": "2026-09-05",
            "mano_obra_estimada": 25.0,
            "motivo": "Se corrigió el alcance real del trabajo",
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["descripcion"] == "Frenos y suspensión"
    assert body["taller"] == "Taller Norte"
    assert body["mano_obra_estimada"] == 25.0

    evento = await db.bitacora.find_one({"accion": "ORDEN_MANTENIMIENTO_CORRECCION", "entidad_id": orden_id})
    assert evento is not None
    assert evento["datos_previos"]["taller"] == "Taller Central"
    assert evento["datos_posteriores"]["taller"] == "Taller Norte"
    assert evento["datos_posteriores"]["motivo"] == "Se corrigió el alcance real del trabajo"

    orden_db = await db.ordenes.find_one({"_id": orden_id})
    assert any("Corrigió" in a["detalle"] for a in orden_db["actividades"])


async def test_corregir_orden_en_taller_solo_permite_repuestos_y_mano_de_obra(client, db):
    headers = await _jefe_headers(db)
    await _conductor_con_vehiculo(db, 91)
    creada = await client.post(
        "/mantenimiento/ordenes",
        headers=headers,
        json={
            "vehiculo_id": "v91",
            "tipo": "CORRECTIVA",
            "descripcion": "Frenos",
            "km_entrada": 1000,
            "taller": "Taller Central",
            "fecha_programada": "2026-09-01",
            "retirar_vehiculo": False,
        },
    )
    orden_id = creada.json()["id"]
    await client.post(f"/mantenimiento/ordenes/{orden_id}/taller", headers=headers)

    # Repuestos/mano de obra sí se pueden corregir en EN_TALLER.
    ok = await client.patch(
        f"/mantenimiento/ordenes/{orden_id}/correccion",
        headers=headers,
        json={"mano_obra_estimada": 40.0, "motivo": "Se subestimó la mano de obra al abrir"},
    )
    assert ok.status_code == 200
    assert ok.json()["mano_obra_estimada"] == 40.0

    # El taller (ya determinó dónde está el vehículo) queda bloqueado.
    bloqueado = await client.patch(
        f"/mantenimiento/ordenes/{orden_id}/correccion",
        headers=headers,
        json={"taller": "Otro taller", "motivo": "Intento fuera de rango"},
    )
    assert bloqueado.status_code == 409
    assert bloqueado.json()["code"] == "CAMPO_NO_CORREGIBLE_EN_ESTE_ESTADO"


async def test_corregir_orden_cerrada_es_conflicto(client, db):
    headers = await _jefe_headers(db)
    await _conductor_con_vehiculo(db, 92)
    creada = await client.post(
        "/mantenimiento/ordenes",
        headers=headers,
        json={
            "vehiculo_id": "v92",
            "tipo": "CORRECTIVA",
            "descripcion": "Frenos",
            "km_entrada": 1000,
            "taller": "Taller Central",
            "fecha_programada": "2026-09-01",
            "retirar_vehiculo": False,
        },
    )
    orden_id = creada.json()["id"]
    await client.post(f"/mantenimiento/ordenes/{orden_id}/taller", headers=headers)
    await client.post(
        f"/mantenimiento/ordenes/{orden_id}/cierre",
        headers=headers,
        json={"trabajos_realizados": "Listo", "costo_total": 50.0, "km_salida": 1050},
    )

    resp = await client.patch(
        f"/mantenimiento/ordenes/{orden_id}/correccion",
        headers=headers,
        json={"mano_obra_estimada": 10.0, "motivo": "ya no debería poder"},
    )

    assert resp.status_code == 409
    assert resp.json()["code"] == "ORDEN_ESTADO_INVALIDO"
