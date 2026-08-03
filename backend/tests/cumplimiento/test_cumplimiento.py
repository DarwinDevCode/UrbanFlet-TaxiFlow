from datetime import UTC, datetime, timedelta

from tests.utils import auth_headers, crear_conductor_con_vehiculo, crear_usuario_activo


async def _supervisor_headers(db):
    await crear_usuario_activo(
        db, usuario_id="u-sup-cump", telefono="+593952000001", roles=["supervisor_cumplimiento"]
    )
    return auth_headers("u-sup-cump", ["supervisor_cumplimiento"])


async def _conductor_con_vehiculo(db, n: int, **overrides):
    return await crear_conductor_con_vehiculo(
        db, conductor_id=f"c{n}", telefono=f"+59395200001{n}", vehiculo_id=f"v{n}", placa=f"CMP-000{n}", **overrides
    )


async def test_control_vigencia_marca_vencido_y_bloquea_bandera(client, db):
    headers = await _supervisor_headers(db)
    await _conductor_con_vehiculo(db, 1)
    vencida = (datetime.now(UTC) - timedelta(days=5)).date().isoformat()
    await db.documentos.insert_one(
        {
            "_id": "doc1",
            "tipo": "LICENCIA",
            "propietario_tipo": "CONDUCTOR",
            "propietario_id": "c1",
            "fecha_vencimiento": vencida,
            "estado_verificacion": "CONFORME",
        }
    )

    resp = await client.post("/cumplimiento/control-vigencia", headers=headers)

    assert resp.status_code == 200
    assert resp.json()["vencidos_nuevos"] == 1

    usuario = await db.usuarios.find_one({"_id": "c1"})
    assert usuario["conductor"]["cumplimiento_ok"] is False


async def test_control_vigencia_notifica_por_vencer_en_umbrales(client, db):
    headers = await _supervisor_headers(db)
    await _conductor_con_vehiculo(db, 2)
    en_7_dias = (datetime.now(UTC) + timedelta(days=7)).date().isoformat()
    await db.documentos.insert_one(
        {
            "_id": "doc2",
            "tipo": "MATRICULA",
            "propietario_tipo": "VEHICULO",
            "propietario_id": "v2",
            "fecha_vencimiento": en_7_dias,
            "estado_verificacion": "CONFORME",
        }
    )

    resp = await client.post("/cumplimiento/control-vigencia", headers=headers)

    assert resp.status_code == 200
    assert resp.json()["por_vencer_notificados"] == 1

    usuario = await db.usuarios.find_one({"_id": "c2"})
    # 7 días no es vencido: la bandera no cambia todavía.
    assert (usuario.get("conductor") or {}).get("cumplimiento_ok", True) is True


async def test_control_vigencia_no_repite_efecto_si_ya_estaba_vencido(client, db):
    headers = await _supervisor_headers(db)
    await _conductor_con_vehiculo(db, 3, cumplimiento_ok_conductor=False)
    vencida = (datetime.now(UTC) - timedelta(days=1)).date().isoformat()
    await db.documentos.insert_one(
        {
            "_id": "doc3",
            "tipo": "LICENCIA",
            "propietario_tipo": "CONDUCTOR",
            "propietario_id": "c3",
            "fecha_vencimiento": vencida,
            "estado_verificacion": "CONFORME",
        }
    )

    resp = await client.post("/cumplimiento/control-vigencia", headers=headers)

    assert resp.json()["vencidos_nuevos"] == 0  # ya estaba en rojo, no cuenta como "nuevo"


async def test_renovacion_aprobada_restaura_bandera(client, db):
    headers = await _supervisor_headers(db)
    await _conductor_con_vehiculo(db, 4, cumplimiento_ok_conductor=False)
    await db.documentos.insert_one(
        {
            "_id": "doc4",
            "tipo": "LICENCIA",
            "propietario_tipo": "CONDUCTOR",
            "propietario_id": "c4",
            "fecha_vencimiento": "2020-01-01",
            "estado_verificacion": "CONFORME",
        }
    )

    subir = await client.post(
        "/cumplimiento/documentos/doc4/renovacion",
        json={"url_objeto": "https://x/doc.pdf", "hash_archivo": "abc", "fecha_vencimiento": "2027-01-01"},
    )
    assert subir.status_code == 200

    verificar = await client.post(
        "/cumplimiento/documentos/doc4/renovacion/verificacion", headers=headers, json={"aprobar": True}
    )
    assert verificar.status_code == 200
    assert verificar.json()["fecha_vencimiento"] == "2027-01-01"

    usuario = await db.usuarios.find_one({"_id": "c4"})
    assert usuario["conductor"]["cumplimiento_ok"] is True


async def test_renovacion_rechazada_no_cambia_bandera(client, db):
    headers = await _supervisor_headers(db)
    await _conductor_con_vehiculo(db, 5, cumplimiento_ok_conductor=False)
    await db.documentos.insert_one(
        {
            "_id": "doc5",
            "tipo": "LICENCIA",
            "propietario_tipo": "CONDUCTOR",
            "propietario_id": "c5",
            "fecha_vencimiento": "2020-01-01",
            "estado_verificacion": "CONFORME",
        }
    )
    await client.post(
        "/cumplimiento/documentos/doc5/renovacion",
        json={"url_objeto": "https://x/doc.pdf", "hash_archivo": "abc", "fecha_vencimiento": "2027-01-01"},
    )

    resp = await client.post(
        "/cumplimiento/documentos/doc5/renovacion/verificacion",
        headers=headers,
        json={"aprobar": False, "motivo": "foto ilegible"},
    )

    assert resp.status_code == 200
    usuario = await db.usuarios.find_one({"_id": "c5"})
    assert usuario["conductor"]["cumplimiento_ok"] is False


async def test_listar_renovaciones_pendientes(client, db):
    headers = await _supervisor_headers(db)
    await _conductor_con_vehiculo(db, 6, cumplimiento_ok_conductor=False)
    await db.documentos.insert_one(
        {
            "_id": "doc7",
            "tipo": "LICENCIA",
            "propietario_tipo": "CONDUCTOR",
            "propietario_id": "c6",
            "fecha_vencimiento": "2020-01-01",
            "estado_verificacion": "CONFORME",
        }
    )
    await client.post(
        "/cumplimiento/documentos/doc7/renovacion",
        json={"url_objeto": "https://x/doc.pdf", "hash_archivo": "abc", "fecha_vencimiento": "2027-01-01"},
    )

    resp = await client.get("/cumplimiento/documentos/renovaciones-pendientes", headers=headers)

    assert resp.status_code == 200
    pendientes = resp.json()
    assert any(p["documento_id"] == "doc7" for p in pendientes)


async def test_verificar_sin_renovacion_pendiente_devuelve_409(client, db):
    headers = await _supervisor_headers(db)
    await db.documentos.insert_one(
        {
            "_id": "doc6",
            "tipo": "LICENCIA",
            "propietario_tipo": "CONDUCTOR",
            "propietario_id": "c6",
            "fecha_vencimiento": "2027-01-01",
            "estado_verificacion": "CONFORME",
        }
    )

    resp = await client.post(
        "/cumplimiento/documentos/doc6/renovacion/verificacion", headers=headers, json={"aprobar": True}
    )

    assert resp.status_code == 409
    assert resp.json()["code"] == "SIN_RENOVACION_PENDIENTE"
