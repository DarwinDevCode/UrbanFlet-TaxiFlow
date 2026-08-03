from datetime import UTC, datetime, timedelta

from tests.utils import auth_headers, crear_conductor_con_vehiculo, crear_usuario_activo


async def _admin_financiero_headers(db):
    await crear_usuario_activo(db, usuario_id="admin-fin2", telefono="+593970600099", roles=["admin_financiero"])
    return auth_headers("admin-fin2", ["admin_financiero"])


async def _admin_plataforma_headers(db):
    await crear_usuario_activo(db, usuario_id="admin-plat2", telefono="+593970600098", roles=["admin_plataforma"])
    return auth_headers("admin-plat2", ["admin_plataforma"])


async def _sembrar_comision(client, db, porcentaje=0.20):
    headers_admin = await _admin_plataforma_headers(db)
    resp = await client.post(
        "/parametros/comisiones",
        headers=headers_admin,
        json={"porcentaje": porcentaje, "vigente_desde": "2020-01-01T00:00:00Z"},
    )
    assert resp.status_code == 201


def _doc_viaje_finalizado(*, viaje_id, conductor_id, tarifa_final, ts_fin=None):
    return {
        "_id": viaje_id,
        "pasajero_id": "pas-disc",
        "conductor_id": conductor_id,
        "vehiculo_id": f"v-{viaje_id}",
        "estado": "FINALIZADO",
        "origen_lat": -0.18,
        "origen_lon": -78.5,
        "origen_direccion": "Origen",
        "destino_lat": None,
        "destino_lon": None,
        "destino_direccion": None,
        "franja": "DIURNA",
        "ts_solicitud": datetime.now(UTC),
        "ts_inicio": datetime.now(UTC),
        "ts_fin": ts_fin or datetime.now(UTC),
        "km_recorridos": 3.0,
        "min_espera": 0.0,
        "tarifa_estimada": tarifa_final,
        "tarifa_final": tarifa_final,
    }


async def _crear_discrepancia(client, db, *, viaje_id, conductor_id, tarifa_final, monto_cobrado):
    await crear_conductor_con_vehiculo(
        db,
        conductor_id=conductor_id,
        telefono=f"+593970{ord(conductor_id[-1]):03d}",
        vehiculo_id=f"v-{viaje_id}",
        placa=f"DIS{ord(conductor_id[-1]):04d}",
    )
    await db.viajes.insert_one(
        _doc_viaje_finalizado(viaje_id=viaje_id, conductor_id=conductor_id, tarifa_final=tarifa_final)
    )
    headers = auth_headers(conductor_id, ["conductor"])
    resp = await client.post(
        "/pagos/efectivo", headers=headers, json={"viaje_id": viaje_id, "monto_cobrado": monto_cobrado}
    )
    assert resp.status_code == 201
    assert resp.json()["estado"] == "DISCREPANCIA"
    return resp.json()["id"]


async def test_bandeja_lista_discrepancias_no_resueltas(client, db):
    await _sembrar_comision(client, db)
    await _crear_discrepancia(client, db, viaje_id="vd1", conductor_id="cd1", tarifa_final=4.00, monto_cobrado=3.00)
    headers_admin = await _admin_financiero_headers(db)

    resp = await client.get("/pagos/discrepancias", headers=headers_admin)

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["discrepancias"]) == 1
    assert body["discrepancias"][0]["viaje_id"] == "vd1"
    assert body["discrepancias"][0]["diferencia"] == -1.00


async def test_bandeja_lista_viajes_sin_pago_tras_24h(client, db):
    await crear_conductor_con_vehiculo(
        db, conductor_id="cd2", telefono="+593970600002", vehiculo_id="v2", placa="DIS0002"
    )
    await db.viajes.insert_one(
        _doc_viaje_finalizado(
            viaje_id="vd2", conductor_id="cd2", tarifa_final=2.50, ts_fin=datetime.now(UTC) - timedelta(hours=25)
        )
    )
    # Uno reciente (< 24h) que NO debe aparecer todavía.
    await db.viajes.insert_one(_doc_viaje_finalizado(viaje_id="vd3", conductor_id="cd2", tarifa_final=1.50))
    headers_admin = await _admin_financiero_headers(db)

    resp = await client.get("/pagos/discrepancias", headers=headers_admin)

    assert resp.status_code == 200
    body = resp.json()
    ids = [v["viaje_id"] for v in body["viajes_sin_pago"]]
    assert "vd2" in ids
    assert "vd3" not in ids


async def test_viaje_sin_pago_con_discrepancia_no_aparece_como_sin_pago(client, db):
    """Un viaje >24h que SÍ tiene un pago (aunque sea DISCREPANCIA) no debe
    listarse también como VIAJE_SIN_PAGO — ya aparece en la otra lista."""
    await _sembrar_comision(client, db)
    viaje_id = "vd4"
    await crear_conductor_con_vehiculo(
        db, conductor_id="cd4", telefono="+593970600004", vehiculo_id="v4", placa="DIS0004"
    )
    await db.viajes.insert_one(
        _doc_viaje_finalizado(
            viaje_id=viaje_id, conductor_id="cd4", tarifa_final=3.00, ts_fin=datetime.now(UTC) - timedelta(hours=25)
        )
    )
    headers = auth_headers("cd4", ["conductor"])
    await client.post("/pagos/efectivo", headers=headers, json={"viaje_id": viaje_id, "monto_cobrado": 2.00})
    headers_admin = await _admin_financiero_headers(db)

    resp = await client.get("/pagos/discrepancias", headers=headers_admin)

    body = resp.json()
    ids_sin_pago = [v["viaje_id"] for v in body["viajes_sin_pago"]]
    assert viaje_id not in ids_sin_pago
    ids_discrepancia = [p["viaje_id"] for p in body["discrepancias"]]
    assert viaje_id in ids_discrepancia


async def test_resolver_discrepancia_aceptando_paga_sobre_el_monto_cobrado(client, db):
    await _sembrar_comision(client, db, porcentaje=0.20)
    pago_id = await _crear_discrepancia(
        client, db, viaje_id="vd5", conductor_id="cd5", tarifa_final=4.00, monto_cobrado=3.00
    )
    headers_admin = await _admin_financiero_headers(db)

    resp = await client.post(
        f"/pagos/{pago_id}/resolver", headers=headers_admin, json={"aceptar": True, "motivo": "conductor confirma 3.00"}
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["resuelto"] is True
    assert body["resolucion_aceptado"] is True

    viaje_db = await db.viajes.find_one({"_id": "vd5"})
    assert viaje_db["estado"] == "PAGADO"

    movimientos = await db.movimientos.find({"viaje_id": "vd5"}).to_list(length=10)
    comision = next(m for m in movimientos if m["tipo"] == "COMISION")
    neto = next(m for m in movimientos if m["tipo"] == "NETO_SOCIO")
    # Sobre el monto REALMENTE cobrado (3.00), no sobre la tarifa (4.00).
    assert comision["monto_firmado"] == -0.60
    assert neto["monto_firmado"] == 2.40

    # Ya no debe aparecer en la bandeja.
    bandeja = await client.get("/pagos/discrepancias", headers=headers_admin)
    assert bandeja.json()["discrepancias"] == []


async def test_resolver_discrepancia_rechazando_no_pasa_a_liquidacion(client, db):
    await _sembrar_comision(client, db)
    pago_id = await _crear_discrepancia(
        client, db, viaje_id="vd6", conductor_id="cd6", tarifa_final=4.00, monto_cobrado=3.00
    )
    headers_admin = await _admin_financiero_headers(db)

    resp = await client.post(
        f"/pagos/{pago_id}/resolver", headers=headers_admin, json={"aceptar": False, "motivo": "no se pudo verificar"}
    )

    assert resp.status_code == 200
    assert resp.json()["resolucion_aceptado"] is False

    viaje_db = await db.viajes.find_one({"_id": "vd6"})
    assert viaje_db["estado"] == "FINALIZADO"  # sigue sin cobrar

    movimientos = await db.movimientos.find({"viaje_id": "vd6"}).to_list(length=10)
    assert movimientos == []


async def test_resolver_discrepancia_ya_resuelta_devuelve_404(client, db):
    await _sembrar_comision(client, db)
    pago_id = await _crear_discrepancia(
        client, db, viaje_id="vd7", conductor_id="cd7", tarifa_final=4.00, monto_cobrado=3.00
    )
    headers_admin = await _admin_financiero_headers(db)
    await client.post(f"/pagos/{pago_id}/resolver", headers=headers_admin, json={"aceptar": False, "motivo": "x"})

    resp = await client.post(f"/pagos/{pago_id}/resolver", headers=headers_admin, json={"aceptar": True, "motivo": "y"})

    assert resp.status_code == 404
    assert resp.json()["code"] == "DISCREPANCIA_NO_ENCONTRADA"


async def test_rol_sin_admin_financiero_no_puede_ver_bandeja(client, db):
    await crear_usuario_activo(db, usuario_id="conductor-curioso", telefono="+593970600097", roles=["conductor"])
    headers = auth_headers("conductor-curioso", ["conductor"])

    resp = await client.get("/pagos/discrepancias", headers=headers)

    assert resp.status_code == 403
