"""CU-O10 A2: movimiento AJUSTE individual vinculado al viaje — distinto de
la observación de un socio sobre su liquidación (CU-O11 A2). Cubre la
creación del movimiento (con la precondición de recaudación VALIDADA) y su
reflejo en `generar_liquidaciones`."""

from datetime import UTC, datetime, timedelta

from src.recaudacion.service import _periodo_cerrado_mas_reciente
from tests.recaudacion.test_liquidaciones import _sembrar_viaje_pagado
from tests.utils import auth_headers, crear_conductor_con_vehiculo, crear_usuario_activo


async def _admin_financiero_headers(db, usuario_id="admin-fin-ajuste"):
    await crear_usuario_activo(db, usuario_id=usuario_id, telefono="+593970800199", roles=["admin_financiero"])
    return auth_headers(usuario_id, ["admin_financiero"])


async def test_crear_ajuste_movimiento_sobre_viaje_pagado(client, db):
    inicio, _fin = _periodo_cerrado_mas_reciente(datetime.now(UTC))
    ts = inicio + timedelta(hours=1)
    await crear_conductor_con_vehiculo(
        db, conductor_id="caj1", telefono="+593970800001", vehiculo_id="vaj1", placa="AJU0001"
    )
    await _sembrar_viaje_pagado(db, viaje_id="vjaj1", conductor_id="caj1", monto=10.0, comision_pct=0.20, ts=ts)
    headers_admin = await _admin_financiero_headers(db)

    resp = await client.post(
        "/pagos/vjaj1/ajuste",
        headers=headers_admin,
        json={"monto": -1.5, "motivo": "Corrección de comisión mal calculada por error de sistema"},
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["viaje_id"] == "vjaj1"
    assert body["tipo"] == "AJUSTE"
    assert body["monto_firmado"] == -1.5
    assert body["autorizador_id"] == "admin-fin-ajuste"
    assert body["motivo"] == "Corrección de comisión mal calculada por error de sistema"

    # No debe haber tocado los movimientos originales COMISION/NETO_SOCIO.
    comision = await db.movimientos.find_one({"viaje_id": "vjaj1", "tipo": "COMISION"})
    neto = await db.movimientos.find_one({"viaje_id": "vjaj1", "tipo": "NETO_SOCIO"})
    assert comision["monto_firmado"] == -2.0
    assert neto["monto_firmado"] == 8.0

    todos = await db.movimientos.find({"viaje_id": "vjaj1"}).to_list(length=10)
    assert len(todos) == 3
    tipos = {m["tipo"] for m in todos}
    assert tipos == {"COMISION", "NETO_SOCIO", "AJUSTE"}


async def test_crear_ajuste_sobre_viaje_sin_pago_validado_devuelve_409(client, db):
    await crear_conductor_con_vehiculo(
        db, conductor_id="caj2", telefono="+593970800002", vehiculo_id="vaj2", placa="AJU0002"
    )
    headers_admin = await _admin_financiero_headers(db, usuario_id="admin-fin-ajuste2")

    resp = await client.post(
        "/pagos/no-existe/ajuste",
        headers=headers_admin,
        json={"monto": 1.0, "motivo": "intento sobre viaje inexistente"},
    )

    assert resp.status_code == 409
    assert resp.json()["code"] == "VIAJE_SIN_RECAUDACION_VALIDA"


async def test_crear_ajuste_requiere_motivo_no_vacio(client, db):
    inicio, _fin = _periodo_cerrado_mas_reciente(datetime.now(UTC))
    ts = inicio + timedelta(hours=1)
    await crear_conductor_con_vehiculo(
        db, conductor_id="caj3", telefono="+593970800003", vehiculo_id="vaj3", placa="AJU0003"
    )
    await _sembrar_viaje_pagado(db, viaje_id="vjaj3", conductor_id="caj3", monto=10.0, comision_pct=0.20, ts=ts)
    headers_admin = await _admin_financiero_headers(db, usuario_id="admin-fin-ajuste3")

    resp = await client.post(
        "/pagos/vjaj3/ajuste", headers=headers_admin, json={"monto": 1.0, "motivo": ""}
    )

    assert resp.status_code == 422


async def test_crear_ajuste_rol_no_admin_financiero_devuelve_403(client, db):
    inicio, _fin = _periodo_cerrado_mas_reciente(datetime.now(UTC))
    ts = inicio + timedelta(hours=1)
    await crear_conductor_con_vehiculo(
        db, conductor_id="caj4", telefono="+593970800004", vehiculo_id="vaj4", placa="AJU0004"
    )
    await _sembrar_viaje_pagado(db, viaje_id="vjaj4", conductor_id="caj4", monto=10.0, comision_pct=0.20, ts=ts)
    headers = auth_headers("caj4", ["conductor"])

    resp = await client.post(
        "/pagos/vjaj4/ajuste", headers=headers, json={"monto": 1.0, "motivo": "no autorizado"}
    )

    assert resp.status_code == 403


async def test_ajuste_se_refleja_en_liquidacion_generada(client, db):
    inicio, _fin = _periodo_cerrado_mas_reciente(datetime.now(UTC))
    ts = inicio + timedelta(hours=1)
    await crear_conductor_con_vehiculo(
        db, conductor_id="caj5", telefono="+593970800005", vehiculo_id="vaj5", placa="AJU0005"
    )
    await _sembrar_viaje_pagado(db, viaje_id="vjaj5", conductor_id="caj5", monto=10.0, comision_pct=0.20, ts=ts)
    headers_admin = await _admin_financiero_headers(db, usuario_id="admin-fin-ajuste5")

    ajuste_resp = await client.post(
        "/pagos/vjaj5/ajuste",
        headers=headers_admin,
        json={"monto": 1.5, "motivo": "Se reconoce cobro de más al socio, se acredita a su favor"},
    )
    assert ajuste_resp.status_code == 201

    generado = await client.post("/liquidaciones/generar", headers=headers_admin)
    assert generado.status_code == 201
    liq = next(g for g in generado.json()["generadas"] if g["conductor_id"] == "caj5")

    # comisiones = 2.0 (10 * 0.20); ajustes = +1.5; saldo = ajustes - comisiones.
    assert liq["comisiones"] == 2.0
    assert liq["ajustes"] == 1.5
    assert liq["saldo"] == round(1.5 - 2.0, 2)

    # El movimiento AJUSTE quedó enlazado a la liquidación igual que
    # COMISION/NETO_SOCIO (mismo criterio de "ya liquidado" para
    # generar_liquidaciones, evita reprocesarlo en un reintento).
    mov_ajuste = await db.movimientos.find_one({"viaje_id": "vjaj5", "tipo": "AJUSTE"})
    assert mov_ajuste["liquidacion_id"] == liq["id"]
