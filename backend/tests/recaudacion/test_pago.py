from datetime import UTC, datetime, timedelta

from tests.utils import auth_headers, crear_conductor_con_vehiculo, crear_usuario_activo


async def _admin_headers(db):
    await crear_usuario_activo(db, usuario_id="admin-fin", telefono="+593970500099", roles=["admin_plataforma"])
    return auth_headers("admin-fin", ["admin_plataforma"])


async def _sembrar_comision(client, db, porcentaje=0.20):
    headers_admin = await _admin_headers(db)
    resp = await client.post(
        "/parametros/comisiones",
        headers=headers_admin,
        json={"porcentaje": porcentaje, "vigente_desde": "2020-01-01T00:00:00Z"},
    )
    assert resp.status_code == 201


def _doc_viaje_finalizado(*, viaje_id, conductor_id, tarifa_final, ts_fin=None):
    return {
        "_id": viaje_id,
        "pasajero_id": "pas-pago",
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


async def _viaje_finalizado(db, *, viaje_id, conductor_id, tarifa_final):
    await crear_conductor_con_vehiculo(
        db,
        conductor_id=conductor_id,
        telefono=f"+593970{ord(conductor_id[-1]):03d}",
        vehiculo_id=f"v-{viaje_id}",
        placa=f"PAG{ord(conductor_id[-1]):04d}",
    )
    await db.viajes.insert_one(
        _doc_viaje_finalizado(viaje_id=viaje_id, conductor_id=conductor_id, tarifa_final=tarifa_final)
    )
    return auth_headers(conductor_id, ["conductor"])


async def test_registrar_pago_efectivo_monto_correcto_valida_y_paga(client, db):
    await _sembrar_comision(client, db, porcentaje=0.20)
    headers = await _viaje_finalizado(db, viaje_id="viaje-pago-1", conductor_id="cp1", tarifa_final=3.50)

    resp = await client.post(
        "/pagos/efectivo", headers=headers, json={"viaje_id": "viaje-pago-1", "monto_cobrado": 3.50}
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["estado"] == "VALIDADO"
    assert body["diferencia"] is None

    viaje_db = await db.viajes.find_one({"_id": "viaje-pago-1"})
    assert viaje_db["estado"] == "PAGADO"

    movimientos = await db.movimientos.find({"viaje_id": "viaje-pago-1"}).to_list(length=10)
    assert len(movimientos) == 2
    comision = next(m for m in movimientos if m["tipo"] == "COMISION")
    neto = next(m for m in movimientos if m["tipo"] == "NETO_SOCIO")
    assert comision["monto_firmado"] == -0.70  # 3.50 * 0.20
    assert neto["monto_firmado"] == 2.80  # 3.50 - 0.70
    assert round(neto["monto_firmado"] - comision["monto_firmado"], 2) == 3.50  # bruto = neto - comisión (negativa)


async def test_registrar_pago_efectivo_monto_incorrecto_entra_en_discrepancia(client, db):
    await _sembrar_comision(client, db)
    headers = await _viaje_finalizado(db, viaje_id="viaje-pago-2", conductor_id="cp2", tarifa_final=4.00)

    resp = await client.post(
        "/pagos/efectivo", headers=headers, json={"viaje_id": "viaje-pago-2", "monto_cobrado": 3.00}
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["estado"] == "DISCREPANCIA"
    assert body["diferencia"] == -1.00

    viaje_db = await db.viajes.find_one({"_id": "viaje-pago-2"})
    assert viaje_db["estado"] == "FINALIZADO"  # no pasa a PAGADO

    movimientos = await db.movimientos.find({"viaje_id": "viaje-pago-2"}).to_list(length=10)
    assert movimientos == []  # CU-O10 precondición: solo sobre recaudación VALIDADA


async def test_registrar_pago_sin_viaje_finalizado_devuelve_409(client, db):
    await crear_conductor_con_vehiculo(
        db, conductor_id="cp3", telefono="+593970500003", vehiculo_id="v3", placa="PAG0003"
    )
    headers = auth_headers("cp3", ["conductor"])

    resp = await client.post(
        "/pagos/efectivo", headers=headers, json={"viaje_id": "no-existe", "monto_cobrado": 3.00}
    )

    assert resp.status_code == 409
    assert resp.json()["code"] == "VIAJE_NO_FINALIZADO"


async def test_registrar_pago_duplicado_devuelve_409(client, db):
    await _sembrar_comision(client, db)
    headers = await _viaje_finalizado(db, viaje_id="viaje-pago-4", conductor_id="cp4", tarifa_final=2.00)

    primero = await client.post(
        "/pagos/efectivo", headers=headers, json={"viaje_id": "viaje-pago-4", "monto_cobrado": 2.00}
    )
    assert primero.status_code == 201

    # El viaje ya pasó a PAGADO — ya no coincide con el filtro
    # {_id, conductor_id, estado: FINALIZADO}, así que el error correcto es
    # "sin viaje", no "ya pagado".
    segundo = await client.post(
        "/pagos/efectivo", headers=headers, json={"viaje_id": "viaje-pago-4", "monto_cobrado": 2.00}
    )
    assert segundo.status_code == 409
    assert segundo.json()["code"] == "VIAJE_NO_FINALIZADO"


async def test_registrar_pago_con_multiples_viajes_finalizados_paga_el_correcto(client, db):
    """Reproduce el bug real encontrado verificando este slice en
    navegador: un conductor puede tener MÁS DE UN viaje FINALIZADO sin pagar
    a la vez (CU-O09 A4 lo anticipa — el pago puede demorarse hasta 24h). Sin
    viaje_id explícito en la petición, un find_one({conductor_id, estado})
    sin desambiguar podía registrar el pago contra el viaje equivocado."""
    await _sembrar_comision(client, db)
    conductor_id = "cp8"
    await crear_conductor_con_vehiculo(
        db, conductor_id=conductor_id, telefono="+593970500008", vehiculo_id="v8", placa="PAG0008"
    )
    # Un viaje FINALIZADO más viejo, arrastrado sin pagar.
    await db.viajes.insert_one(
        _doc_viaje_finalizado(
            viaje_id="viaje-viejo",
            conductor_id=conductor_id,
            tarifa_final=1.75,
            ts_fin=datetime.now(UTC) - timedelta(hours=2),
        )
    )
    # El viaje que el conductor realmente quiere pagar ahora.
    await db.viajes.insert_one(
        _doc_viaje_finalizado(viaje_id="viaje-nuevo", conductor_id=conductor_id, tarifa_final=1.50)
    )
    headers = auth_headers(conductor_id, ["conductor"])

    resp = await client.post(
        "/pagos/efectivo", headers=headers, json={"viaje_id": "viaje-nuevo", "monto_cobrado": 1.50}
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["viaje_id"] == "viaje-nuevo"
    assert body["estado"] == "VALIDADO"  # 1.50 coincide con viaje-nuevo, no con viaje-viejo (1.75)

    viaje_nuevo_db = await db.viajes.find_one({"_id": "viaje-nuevo"})
    assert viaje_nuevo_db["estado"] == "PAGADO"
    viaje_viejo_db = await db.viajes.find_one({"_id": "viaje-viejo"})
    assert viaje_viejo_db["estado"] == "FINALIZADO"  # intacto — no se tocó por error


async def test_no_se_puede_pagar_el_viaje_de_otro_conductor(client, db):
    """Ownership explícito: viaje_id ahora lo manda el cliente, así que debe
    quedar blindado contra un conductor que intente pagar el viaje de otro
    (por error o a propósito) solo por conocer o adivinar su id."""
    await _sembrar_comision(client, db)
    # viaje-ajeno le pertenece a cp6, no a cp7.
    await _viaje_finalizado(db, viaje_id="viaje-ajeno", conductor_id="cp6", tarifa_final=2.00)
    await crear_conductor_con_vehiculo(
        db, conductor_id="cp7", telefono="+593970500007", vehiculo_id="v7", placa="PAG0007"
    )
    headers_cp7 = auth_headers("cp7", ["conductor"])

    resp = await client.post(
        "/pagos/efectivo", headers=headers_cp7, json={"viaje_id": "viaje-ajeno", "monto_cobrado": 2.00}
    )

    assert resp.status_code == 409
    assert resp.json()["code"] == "VIAJE_NO_FINALIZADO"  # mismo error que "no existe" — no filtra el ajeno

    # El viaje de cp6 no debe haberse tocado.
    viaje_db = await db.viajes.find_one({"_id": "viaje-ajeno"})
    assert viaje_db["estado"] == "FINALIZADO"
    assert await db.pagos.find_one({"viaje_id": "viaje-ajeno"}) is None


async def test_sin_comision_vigente_no_registra_pago_en_mongomock(client, db):
    """Sin parámetro de comisión vigente, la cadena debe fallar. Con
    mongomock (fallback sin sesión real) esto documenta que la excepción se
    propaga; la garantía de que NO queda aplicado nada a medio camino (pago
    o viaje sin sus movimientos) se prueba aparte contra Mongo real en
    test_pago_write_ahead_integration.py — igual que el resto de las
    cadenas transaccionales de este proyecto."""
    headers = await _viaje_finalizado(db, viaje_id="viaje-pago-5", conductor_id="cp5", tarifa_final=2.00)

    resp = await client.post(
        "/pagos/efectivo", headers=headers, json={"viaje_id": "viaje-pago-5", "monto_cobrado": 2.00}
    )

    assert resp.status_code == 409
    assert resp.json()["code"] == "PARAMETRO_NO_VIGENTE"
