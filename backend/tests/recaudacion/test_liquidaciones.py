from datetime import UTC, datetime, timedelta

from src.recaudacion.service import _periodo_cerrado_mas_reciente
from tests.utils import auth_headers, crear_conductor_con_vehiculo, crear_usuario_activo


async def _admin_financiero_headers(db):
    await crear_usuario_activo(db, usuario_id="admin-fin-liq", telefono="+593970600199", roles=["admin_financiero"])
    return auth_headers("admin-fin-liq", ["admin_financiero"])


def _periodo_actual_cerrado() -> tuple[datetime, datetime]:
    return _periodo_cerrado_mas_reciente(datetime.now(UTC))


async def _sembrar_viaje_pagado(db, *, viaje_id, conductor_id, monto, comision_pct, ts):
    await db.viajes.insert_one(
        {
            "_id": viaje_id,
            "pasajero_id": "pas-liq",
            "conductor_id": conductor_id,
            "vehiculo_id": f"v-{viaje_id}",
            "estado": "PAGADO",
            "origen_lat": -0.18,
            "origen_lon": -78.5,
            "origen_direccion": "Origen",
            "destino_lat": None,
            "destino_lon": None,
            "destino_direccion": None,
            "franja": "DIURNA",
            "ts_solicitud": ts,
            "ts_inicio": ts,
            "ts_fin": ts,
            "km_recorridos": 3.0,
            "min_espera": 0.0,
            "tarifa_estimada": monto,
            "tarifa_final": monto,
        }
    )
    pago_id = f"pago-{viaje_id}"
    await db.pagos.insert_one(
        {
            "_id": pago_id,
            "viaje_id": viaje_id,
            "conductor_id": conductor_id,
            "metodo": "EFECTIVO",
            "monto": monto,
            "tarifa_final": monto,
            "diferencia": None,
            "estado": "VALIDADO",
            "referencia_externa": None,
            "ts_registro": ts,
            "ts_confirmacion": ts,
            "resuelto": False,
            "resolucion_motivo": None,
            "resolucion_aceptado": None,
            "resolucion_autorizador_id": None,
            "resolucion_ts": None,
        }
    )
    comision = round(monto * comision_pct, 2)
    neto = round(monto - comision, 2)
    await db.movimientos.insert_many(
        [
            {
                "_id": f"mov-com-{viaje_id}",
                "viaje_id": viaje_id,
                "tipo": "COMISION",
                "monto_firmado": -comision,
                "comision_version_id": "com-x",
                "motivo": None,
                "autorizador_id": None,
                "ts": ts,
                "liquidacion_id": None,
            },
            {
                "_id": f"mov-neto-{viaje_id}",
                "viaje_id": viaje_id,
                "tipo": "NETO_SOCIO",
                "monto_firmado": neto,
                "comision_version_id": "com-x",
                "motivo": None,
                "autorizador_id": None,
                "ts": ts,
                "liquidacion_id": None,
            },
        ]
    )
    return comision, neto


async def test_generar_liquidaciones_consolida_un_socio_del_periodo_cerrado(client, db):
    inicio, _fin = _periodo_actual_cerrado()
    ts = inicio + timedelta(hours=1)
    await crear_conductor_con_vehiculo(
        db, conductor_id="cliq1", telefono="+593970700001", vehiculo_id="vliq1", placa="LIQ0001"
    )
    await _sembrar_viaje_pagado(db, viaje_id="vjliq1", conductor_id="cliq1", monto=10.0, comision_pct=0.20, ts=ts)
    headers_admin = await _admin_financiero_headers(db)

    resp = await client.post("/liquidaciones/generar", headers=headers_admin)

    assert resp.status_code == 201
    body = resp.json()
    assert body["ya_existian"] == []
    assert len(body["generadas"]) == 1
    liq = body["generadas"][0]
    assert liq["conductor_id"] == "cliq1"
    assert liq["estado"] == "EMITIDA"
    assert liq["bruto"] == 10.0
    assert liq["comisiones"] == 2.0
    assert liq["neto"] == 8.0
    assert liq["saldo"] == -2.0
    assert liq["ajustes"] == 0.0
    assert len(liq["detalle"]) == 1
    assert liq["detalle"][0]["viaje_id"] == "vjliq1"


async def test_generar_liquidaciones_es_idempotente(client, db):
    inicio, _fin = _periodo_actual_cerrado()
    ts = inicio + timedelta(hours=1)
    await crear_conductor_con_vehiculo(
        db, conductor_id="cliq2", telefono="+593970700002", vehiculo_id="vliq2", placa="LIQ0002"
    )
    await _sembrar_viaje_pagado(db, viaje_id="vjliq2", conductor_id="cliq2", monto=5.0, comision_pct=0.20, ts=ts)
    headers_admin = await _admin_financiero_headers(db)

    primera = await client.post("/liquidaciones/generar", headers=headers_admin)
    assert len(primera.json()["generadas"]) == 1

    segunda = await client.post("/liquidaciones/generar", headers=headers_admin)
    body = segunda.json()
    assert body["generadas"] == []
    assert body["ya_existian"] == ["cliq2"]

    # No debe haber duplicado en la base.
    total = await db.liquidaciones.count_documents({"conductor_id": "cliq2"})
    assert total == 1


async def test_generar_liquidaciones_excluye_viajes_fuera_del_periodo(client, db):
    inicio, fin = _periodo_actual_cerrado()
    await crear_conductor_con_vehiculo(
        db, conductor_id="cliq3", telefono="+593970700003", vehiculo_id="vliq3", placa="LIQ0003"
    )
    # Un viaje pagado ANTES de que el periodo cerrado actual empezara.
    await _sembrar_viaje_pagado(
        db, viaje_id="vjliq3", conductor_id="cliq3", monto=7.0, comision_pct=0.20, ts=inicio - timedelta(hours=1)
    )
    # Y otro pagado DESPUÉS de que cerrara (todavía en curso, no se liquida aún).
    await _sembrar_viaje_pagado(
        db, viaje_id="vjliq3b", conductor_id="cliq3", monto=7.0, comision_pct=0.20, ts=fin + timedelta(minutes=1)
    )
    headers_admin = await _admin_financiero_headers(db)

    resp = await client.post("/liquidaciones/generar", headers=headers_admin)

    body = resp.json()
    conductores = [g["conductor_id"] for g in body["generadas"]]
    assert "cliq3" not in conductores


async def test_generar_liquidaciones_excluye_discrepancia_sin_resolver(client, db):
    inicio, _fin = _periodo_actual_cerrado()
    ts = inicio + timedelta(hours=2)
    await crear_conductor_con_vehiculo(
        db, conductor_id="cliq4", telefono="+593970700004", vehiculo_id="vliq4", placa="LIQ0004"
    )
    # Viaje FINALIZADO con pago en DISCREPANCIA sin resolver: nunca genera
    # movimientos, así que no debe entrar al periodo (CU-O11 A1).
    await db.viajes.insert_one(
        {
            "_id": "vjliq4",
            "pasajero_id": "pas-liq4",
            "conductor_id": "cliq4",
            "vehiculo_id": "vliq4",
            "estado": "FINALIZADO",
            "origen_lat": -0.18,
            "origen_lon": -78.5,
            "origen_direccion": "Origen",
            "destino_lat": None,
            "destino_lon": None,
            "destino_direccion": None,
            "franja": "DIURNA",
            "ts_solicitud": ts,
            "ts_inicio": ts,
            "ts_fin": ts,
            "km_recorridos": 3.0,
            "min_espera": 0.0,
            "tarifa_estimada": 4.0,
            "tarifa_final": 4.0,
        }
    )
    await db.pagos.insert_one(
        {
            "_id": "pago-vjliq4",
            "viaje_id": "vjliq4",
            "conductor_id": "cliq4",
            "metodo": "EFECTIVO",
            "monto": 3.0,
            "tarifa_final": 4.0,
            "diferencia": -1.0,
            "estado": "DISCREPANCIA",
            "referencia_externa": None,
            "ts_registro": ts,
            "ts_confirmacion": None,
            "resuelto": False,
            "resolucion_motivo": None,
            "resolucion_aceptado": None,
            "resolucion_autorizador_id": None,
            "resolucion_ts": None,
        }
    )
    headers_admin = await _admin_financiero_headers(db)

    resp = await client.post("/liquidaciones/generar", headers=headers_admin)

    body = resp.json()
    assert body["generadas"] == []
    assert body["ya_existian"] == []


async def test_generar_liquidaciones_agrupa_varios_viajes_del_mismo_socio(client, db):
    inicio, _fin = _periodo_actual_cerrado()
    ts1 = inicio + timedelta(hours=1)
    ts2 = inicio + timedelta(hours=5)
    await crear_conductor_con_vehiculo(
        db, conductor_id="cliq5", telefono="+593970700005", vehiculo_id="vliq5", placa="LIQ0005"
    )
    await _sembrar_viaje_pagado(db, viaje_id="vjliq5a", conductor_id="cliq5", monto=4.0, comision_pct=0.20, ts=ts1)
    await _sembrar_viaje_pagado(db, viaje_id="vjliq5b", conductor_id="cliq5", monto=6.0, comision_pct=0.20, ts=ts2)
    headers_admin = await _admin_financiero_headers(db)

    resp = await client.post("/liquidaciones/generar", headers=headers_admin)

    liq = next(g for g in resp.json()["generadas"] if g["conductor_id"] == "cliq5")
    assert liq["bruto"] == 10.0
    assert liq["comisiones"] == 2.0
    assert liq["neto"] == 8.0
    assert liq["saldo"] == -2.0
    assert len(liq["detalle"]) == 2


async def test_generar_liquidaciones_rol_sin_admin_financiero_devuelve_403(client, db):
    await crear_usuario_activo(db, usuario_id="conductor-curioso-liq", telefono="+593970700099", roles=["conductor"])
    headers = auth_headers("conductor-curioso-liq", ["conductor"])

    resp = await client.post("/liquidaciones/generar", headers=headers)

    assert resp.status_code == 403


async def test_aprobar_y_pagar_liquidacion_transiciona_estados(client, db):
    inicio, _fin = _periodo_actual_cerrado()
    ts = inicio + timedelta(hours=1)
    await crear_conductor_con_vehiculo(
        db, conductor_id="cliq7", telefono="+593970700007", vehiculo_id="vliq7", placa="LIQ0007"
    )
    await _sembrar_viaje_pagado(db, viaje_id="vjliq7", conductor_id="cliq7", monto=9.0, comision_pct=0.20, ts=ts)
    headers_admin = await _admin_financiero_headers(db)
    generado = await client.post("/liquidaciones/generar", headers=headers_admin)
    liquidacion_id = generado.json()["generadas"][0]["id"]

    aprobada = await client.post(f"/liquidaciones/{liquidacion_id}/aprobar", headers=headers_admin)
    assert aprobada.status_code == 200
    assert aprobada.json()["estado"] == "APROBADA"
    assert aprobada.json()["aprobador_id"] == "admin-fin-liq"

    pagada = await client.post(f"/liquidaciones/{liquidacion_id}/pagar", headers=headers_admin)
    assert pagada.status_code == 200
    assert pagada.json()["estado"] == "PAGADA"

    en_db = await db.liquidaciones.find_one({"_id": liquidacion_id})
    assert en_db["estado"] == "PAGADA"
    assert en_db["ts_aprobacion"] is not None
    assert en_db["ts_pago"] is not None


async def test_no_se_puede_pagar_una_liquidacion_no_aprobada(client, db):
    inicio, _fin = _periodo_actual_cerrado()
    ts = inicio + timedelta(hours=1)
    await crear_conductor_con_vehiculo(
        db, conductor_id="cliq8", telefono="+593970700008", vehiculo_id="vliq8", placa="LIQ0008"
    )
    await _sembrar_viaje_pagado(db, viaje_id="vjliq8", conductor_id="cliq8", monto=9.0, comision_pct=0.20, ts=ts)
    headers_admin = await _admin_financiero_headers(db)
    generado = await client.post("/liquidaciones/generar", headers=headers_admin)
    liquidacion_id = generado.json()["generadas"][0]["id"]

    resp = await client.post(f"/liquidaciones/{liquidacion_id}/pagar", headers=headers_admin)

    assert resp.status_code == 409
    assert resp.json()["code"] == "LIQUIDACION_ESTADO_INVALIDO"


async def test_no_se_puede_aprobar_una_liquidacion_ya_aprobada(client, db):
    inicio, _fin = _periodo_actual_cerrado()
    ts = inicio + timedelta(hours=1)
    await crear_conductor_con_vehiculo(
        db, conductor_id="cliq9", telefono="+593970700009", vehiculo_id="vliq9", placa="LIQ0009"
    )
    await _sembrar_viaje_pagado(db, viaje_id="vjliq9", conductor_id="cliq9", monto=9.0, comision_pct=0.20, ts=ts)
    headers_admin = await _admin_financiero_headers(db)
    generado = await client.post("/liquidaciones/generar", headers=headers_admin)
    liquidacion_id = generado.json()["generadas"][0]["id"]
    await client.post(f"/liquidaciones/{liquidacion_id}/aprobar", headers=headers_admin)

    resp = await client.post(f"/liquidaciones/{liquidacion_id}/aprobar", headers=headers_admin)

    assert resp.status_code == 409
    assert resp.json()["code"] == "LIQUIDACION_ESTADO_INVALIDO"


async def test_aprobar_liquidacion_inexistente_devuelve_404(client, db):
    headers_admin = await _admin_financiero_headers(db)

    resp = await client.post("/liquidaciones/no-existe/aprobar", headers=headers_admin)

    assert resp.status_code == 404
    assert resp.json()["code"] == "LIQUIDACION_NO_ENCONTRADA"


async def test_listar_liquidaciones_devuelve_las_generadas(client, db):
    inicio, _fin = _periodo_actual_cerrado()
    ts = inicio + timedelta(hours=1)
    await crear_conductor_con_vehiculo(
        db, conductor_id="cliq6", telefono="+593970700006", vehiculo_id="vliq6", placa="LIQ0006"
    )
    await _sembrar_viaje_pagado(db, viaje_id="vjliq6", conductor_id="cliq6", monto=8.0, comision_pct=0.20, ts=ts)
    headers_admin = await _admin_financiero_headers(db)
    await client.post("/liquidaciones/generar", headers=headers_admin)

    resp = await client.get("/liquidaciones", headers=headers_admin)

    assert resp.status_code == 200
    body = resp.json()
    conductores = [liq["conductor_id"] for liq in body["items"]]
    assert "cliq6" in conductores
    assert body["total"] >= 1


async def test_listar_liquidaciones_pagina_resultados(client, db):
    inicio, _fin = _periodo_actual_cerrado()
    ts = inicio + timedelta(hours=1)
    for i in range(3):
        await crear_conductor_con_vehiculo(
            db,
            conductor_id=f"cliqpag{i}",
            telefono=f"+59397071100{i}",
            vehiculo_id=f"vliqpag{i}",
            placa=f"LPG000{i}",
        )
        await _sembrar_viaje_pagado(
            db, viaje_id=f"vjliqpag{i}", conductor_id=f"cliqpag{i}", monto=5.0, comision_pct=0.20, ts=ts
        )
    headers_admin = await _admin_financiero_headers(db)
    await client.post("/liquidaciones/generar", headers=headers_admin)

    pagina1 = await client.get("/liquidaciones?limit=2&offset=0", headers=headers_admin)
    pagina2 = await client.get("/liquidaciones?limit=2&offset=2", headers=headers_admin)

    assert pagina1.status_code == 200
    assert pagina2.status_code == 200
    body1 = pagina1.json()
    body2 = pagina2.json()
    assert len(body1["items"]) == 2
    assert body1["total"] == body2["total"]
    assert body1["total"] >= 3
    ids_pagina1 = {liq["id"] for liq in body1["items"]}
    ids_pagina2 = {liq["id"] for liq in body2["items"]}
    assert ids_pagina1.isdisjoint(ids_pagina2)


async def test_conductor_observa_su_liquidacion_y_bloquea_la_aprobacion(client, db):
    inicio, _fin = _periodo_actual_cerrado()
    ts = inicio + timedelta(hours=1)
    await crear_conductor_con_vehiculo(
        db, conductor_id="cliq10", telefono="+593970700010", vehiculo_id="vliq10", placa="LIQ0010"
    )
    await _sembrar_viaje_pagado(db, viaje_id="vjliq10", conductor_id="cliq10", monto=9.0, comision_pct=0.20, ts=ts)
    headers_admin = await _admin_financiero_headers(db)
    generado = await client.post("/liquidaciones/generar", headers=headers_admin)
    liquidacion_id = generado.json()["generadas"][0]["id"]

    headers_conductor = auth_headers("cliq10", ["conductor"])
    resp = await client.post(
        f"/liquidaciones/{liquidacion_id}/observar",
        headers=headers_conductor,
        json={"motivo": "No reconozco uno de estos viajes"},
    )

    assert resp.status_code == 200
    assert resp.json()["estado"] == "OBSERVADA"

    bloqueada = await client.post(f"/liquidaciones/{liquidacion_id}/aprobar", headers=headers_admin)
    assert bloqueada.status_code == 409
    assert bloqueada.json()["code"] == "LIQUIDACION_ESTADO_INVALIDO"


async def test_conductor_no_puede_observar_la_liquidacion_de_otro(client, db):
    inicio, _fin = _periodo_actual_cerrado()
    ts = inicio + timedelta(hours=1)
    await crear_conductor_con_vehiculo(
        db, conductor_id="cliq11", telefono="+593970700011", vehiculo_id="vliq11", placa="LIQ0011"
    )
    await crear_conductor_con_vehiculo(
        db, conductor_id="cliq11b", telefono="+593970700012", vehiculo_id="vliq11b", placa="LIQ0012"
    )
    await _sembrar_viaje_pagado(db, viaje_id="vjliq11", conductor_id="cliq11", monto=9.0, comision_pct=0.20, ts=ts)
    headers_admin = await _admin_financiero_headers(db)
    generado = await client.post("/liquidaciones/generar", headers=headers_admin)
    liquidacion_id = generado.json()["generadas"][0]["id"]

    headers_ajeno = auth_headers("cliq11b", ["conductor"])
    resp = await client.post(
        f"/liquidaciones/{liquidacion_id}/observar", headers=headers_ajeno, json={"motivo": "intento ajeno"}
    )

    assert resp.status_code == 404
    assert resp.json()["code"] == "LIQUIDACION_NO_ENCONTRADA"
    en_db = await db.liquidaciones.find_one({"_id": liquidacion_id})
    assert en_db["estado"] == "EMITIDA"


async def test_admin_ratifica_observacion_y_vuelve_a_emitida(client, db):
    inicio, _fin = _periodo_actual_cerrado()
    ts = inicio + timedelta(hours=1)
    await crear_conductor_con_vehiculo(
        db, conductor_id="cliq12", telefono="+593970700013", vehiculo_id="vliq12", placa="LIQ0013"
    )
    await _sembrar_viaje_pagado(db, viaje_id="vjliq12", conductor_id="cliq12", monto=9.0, comision_pct=0.20, ts=ts)
    headers_admin = await _admin_financiero_headers(db)
    generado = await client.post("/liquidaciones/generar", headers=headers_admin)
    liquidacion_id = generado.json()["generadas"][0]["id"]
    headers_conductor = auth_headers("cliq12", ["conductor"])
    await client.post(
        f"/liquidaciones/{liquidacion_id}/observar", headers=headers_conductor, json={"motivo": "revisar"}
    )
    saldo_antes = (await db.liquidaciones.find_one({"_id": liquidacion_id}))["saldo"]

    resp = await client.post(
        f"/liquidaciones/{liquidacion_id}/responder-observacion",
        headers=headers_admin,
        json={"ratificar": True, "motivo": "Los viajes son correctos, se ratifica"},
    )

    assert resp.status_code == 200
    assert resp.json()["estado"] == "EMITIDA"
    assert resp.json()["saldo"] == saldo_antes

    # Ahora sí se puede aprobar normalmente.
    aprobada = await client.post(f"/liquidaciones/{liquidacion_id}/aprobar", headers=headers_admin)
    assert aprobada.status_code == 200


async def test_admin_ajusta_observacion_corrige_saldo_y_vuelve_a_emitida(client, db):
    inicio, _fin = _periodo_actual_cerrado()
    ts = inicio + timedelta(hours=1)
    await crear_conductor_con_vehiculo(
        db, conductor_id="cliq13", telefono="+593970700014", vehiculo_id="vliq13", placa="LIQ0014"
    )
    await _sembrar_viaje_pagado(db, viaje_id="vjliq13", conductor_id="cliq13", monto=9.0, comision_pct=0.20, ts=ts)
    headers_admin = await _admin_financiero_headers(db)
    generado = await client.post("/liquidaciones/generar", headers=headers_admin)
    liquidacion_id = generado.json()["generadas"][0]["id"]
    saldo_antes = generado.json()["generadas"][0]["saldo"]
    headers_conductor = auth_headers("cliq13", ["conductor"])
    await client.post(
        f"/liquidaciones/{liquidacion_id}/observar", headers=headers_conductor, json={"motivo": "cobraron de más"}
    )

    resp = await client.post(
        f"/liquidaciones/{liquidacion_id}/responder-observacion",
        headers=headers_admin,
        json={"ratificar": False, "motivo": "Se confirma el error, se ajusta a favor del socio", "ajuste_monto": 1.5},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["estado"] == "EMITIDA"
    assert body["ajustes"] == 1.5
    assert body["saldo"] == round(saldo_antes + 1.5, 2)


async def test_responder_observacion_sin_ajustar_y_sin_monto_devuelve_422(client, db):
    inicio, _fin = _periodo_actual_cerrado()
    ts = inicio + timedelta(hours=1)
    await crear_conductor_con_vehiculo(
        db, conductor_id="cliq14", telefono="+593970700015", vehiculo_id="vliq14", placa="LIQ0015"
    )
    await _sembrar_viaje_pagado(db, viaje_id="vjliq14", conductor_id="cliq14", monto=9.0, comision_pct=0.20, ts=ts)
    headers_admin = await _admin_financiero_headers(db)
    generado = await client.post("/liquidaciones/generar", headers=headers_admin)
    liquidacion_id = generado.json()["generadas"][0]["id"]
    headers_conductor = auth_headers("cliq14", ["conductor"])
    await client.post(
        f"/liquidaciones/{liquidacion_id}/observar", headers=headers_conductor, json={"motivo": "revisar"}
    )

    resp = await client.post(
        f"/liquidaciones/{liquidacion_id}/responder-observacion",
        headers=headers_admin,
        json={"ratificar": False, "motivo": "sin monto"},
    )

    assert resp.status_code == 422
    assert resp.json()["code"] == "AJUSTE_MONTO_REQUERIDO"


async def test_alertas_saldo_negativo_detecta_dos_periodos_consecutivos_impagos(client, db):
    await crear_conductor_con_vehiculo(
        db, conductor_id="cliq15", telefono="+593970700016", vehiculo_id="vliq15", placa="LIQ0016"
    )
    inicio, _fin = _periodo_actual_cerrado()
    # Dos liquidaciones consecutivas insertadas directamente (periodos
    # distintos, ambas con saldo negativo y sin pagar).
    await db.liquidaciones.insert_many(
        [
            {
                "_id": "liq-alerta-1",
                "conductor_id": "cliq15",
                "periodo_inicio": inicio - timedelta(days=14),
                "periodo_fin": inicio - timedelta(days=7),
                "estado": "APROBADA",
                "bruto": 5.0,
                "comisiones": 1.0,
                "ajustes": 0.0,
                "neto": 4.0,
                "saldo": -1.0,
                "detalle": [],
                "ts_emision": inicio - timedelta(days=7),
                "ts_aprobacion": inicio - timedelta(days=6),
                "ts_pago": None,
                "aprobador_id": "admin-fin-liq",
                "liquidacion_ref_id": None,
                "observacion_motivo": None,
                "observacion_ts": None,
            },
            {
                "_id": "liq-alerta-2",
                "conductor_id": "cliq15",
                "periodo_inicio": inicio - timedelta(days=7),
                "periodo_fin": inicio,
                "estado": "EMITIDA",
                "bruto": 5.0,
                "comisiones": 1.0,
                "ajustes": 0.0,
                "neto": 4.0,
                "saldo": -1.0,
                "detalle": [],
                "ts_emision": inicio,
                "ts_aprobacion": None,
                "ts_pago": None,
                "aprobador_id": None,
                "liquidacion_ref_id": None,
                "observacion_motivo": None,
                "observacion_ts": None,
            },
        ]
    )
    headers_admin = await _admin_financiero_headers(db)

    resp = await client.get("/liquidaciones/alertas-saldo-negativo", headers=headers_admin)

    assert resp.status_code == 200
    alertas = resp.json()
    alerta = next(a for a in alertas if a["conductor_id"] == "cliq15")
    assert alerta["periodos_consecutivos"] == 2


async def test_alertas_saldo_negativo_no_dispara_si_una_liquidacion_ya_esta_pagada(client, db):
    await crear_conductor_con_vehiculo(
        db, conductor_id="cliq16", telefono="+593970700017", vehiculo_id="vliq16", placa="LIQ0017"
    )
    inicio, _fin = _periodo_actual_cerrado()
    await db.liquidaciones.insert_many(
        [
            {
                "_id": "liq-alerta-3",
                "conductor_id": "cliq16",
                "periodo_inicio": inicio - timedelta(days=14),
                "periodo_fin": inicio - timedelta(days=7),
                "estado": "PAGADA",
                "bruto": 5.0,
                "comisiones": 1.0,
                "ajustes": 0.0,
                "neto": 4.0,
                "saldo": -1.0,
                "detalle": [],
                "ts_emision": inicio - timedelta(days=7),
                "ts_aprobacion": inicio - timedelta(days=6),
                "ts_pago": inicio - timedelta(days=5),
                "aprobador_id": "admin-fin-liq",
                "liquidacion_ref_id": None,
                "observacion_motivo": None,
                "observacion_ts": None,
            },
            {
                "_id": "liq-alerta-4",
                "conductor_id": "cliq16",
                "periodo_inicio": inicio - timedelta(days=7),
                "periodo_fin": inicio,
                "estado": "EMITIDA",
                "bruto": 5.0,
                "comisiones": 1.0,
                "ajustes": 0.0,
                "neto": 4.0,
                "saldo": -1.0,
                "detalle": [],
                "ts_emision": inicio,
                "ts_aprobacion": None,
                "ts_pago": None,
                "aprobador_id": None,
                "liquidacion_ref_id": None,
                "observacion_motivo": None,
                "observacion_ts": None,
            },
        ]
    )
    headers_admin = await _admin_financiero_headers(db)

    resp = await client.get("/liquidaciones/alertas-saldo-negativo", headers=headers_admin)

    conductores_en_alerta = [a["conductor_id"] for a in resp.json()]
    assert "cliq16" not in conductores_en_alerta
