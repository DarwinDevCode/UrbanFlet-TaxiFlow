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
    assert body["items"][0]["vehiculo_id"] == "v12"
