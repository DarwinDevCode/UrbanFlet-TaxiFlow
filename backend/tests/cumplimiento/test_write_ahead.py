from pymongo.errors import PyMongoError

from tests.utils import auth_headers, crear_conductor_con_vehiculo, crear_usuario_activo


async def test_bitacora_caida_impide_aprobacion_de_renovacion(client, db, monkeypatch):
    await crear_usuario_activo(db, usuario_id="u-sup-wa", telefono="+593953000001", roles=["supervisor_cumplimiento"])
    headers = auth_headers("u-sup-wa", ["supervisor_cumplimiento"])
    await crear_conductor_con_vehiculo(
        db,
        conductor_id="c-wa",
        telefono="+593953000002",
        vehiculo_id="v-wa",
        placa="WAH-C001",
        cumplimiento_ok_conductor=False,
    )
    await db.documentos.insert_one(
        {
            "_id": "doc-wa",
            "tipo": "LICENCIA",
            "propietario_tipo": "CONDUCTOR",
            "propietario_id": "c-wa",
            "fecha_vencimiento": "2020-01-01",
            "estado_verificacion": "CONFORME",
            "renovacion_pendiente": {
                "url_objeto": "https://x",
                "hash_archivo": "abc",
                "fecha_vencimiento": "2027-01-01",
            },
        }
    )

    async def _insert_one_falla(*args, **kwargs):
        raise PyMongoError("Mongo caído")

    monkeypatch.setattr(type(db.bitacora), "insert_one", _insert_one_falla)

    resp = await client.post(
        "/cumplimiento/documentos/doc-wa/renovacion/verificacion", headers=headers, json={"aprobar": True}
    )

    assert resp.status_code == 503
    assert resp.json()["code"] == "AUDIT_WRITE_FAILED"

    documento = await db.documentos.find_one({"_id": "doc-wa"})
    assert documento["fecha_vencimiento"] == "2020-01-01", "la renovación no debe aplicarse si la bitácora falló"
    assert documento.get("renovacion_pendiente") is not None

    usuario = await db.usuarios.find_one({"_id": "c-wa"})
    assert usuario["conductor"]["cumplimiento_ok"] is False, "la bandera no debe restaurarse sin el commit real"
