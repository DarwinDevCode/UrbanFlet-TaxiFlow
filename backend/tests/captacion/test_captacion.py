from tests.utils import auth_headers, crear_usuario_activo

_VEHICULO = {"placa": "ABC-1234", "marca": "Toyota", "modelo": "Yaris", "anio": 2020, "color": "Blanco", "capacidad": 4}


def _solicitud_payload(**overrides) -> dict:
    payload = {
        "nombre": "Postulante Uno",
        "telefono": "+593910000001",
        "password": "clave-larga-123",
        "cedula": "0102030405",
        "licencia_numero": "LIC-001",
        "vehiculo": _VEHICULO,
        "documentos": [],
        "enviar": True,
    }
    payload.update(overrides)
    return payload


async def _admin_headers(db):
    await crear_usuario_activo(db, usuario_id="u-admin-captacion", telefono="+593920000000", roles=["admin_captacion"])
    return auth_headers("u-admin-captacion", ["admin_captacion"])


async def test_registrar_pasajero_asigna_rol_y_consentimiento(client, db):
    resp = await client.post(
        "/captacion/pasajeros/registro",
        json={
            "nombre": "Pasajera Uno",
            "telefono": "+593911111199",
            "password": "clave-larga-123",
            "version_consentimiento": "v1-2026-07",
        },
    )
    assert resp.status_code == 201
    usuario_id = resp.json()["usuario_id"]

    usuario = await db.usuarios.find_one({"_id": usuario_id})
    assert "pasajero" in usuario["roles"]
    assert usuario["consentimiento"]["version"] == "v1-2026-07"
    assert usuario["pasajero"]["calificacion_promedio"] is None


async def test_crear_solicitud_queda_enviada_y_notifica(client, db):
    resp = await client.post("/captacion/solicitudes", json=_solicitud_payload())

    assert resp.status_code == 201
    body = resp.json()
    assert body["estado"] == "ENVIADA"
    assert body["revision_reforzada"] is False

    solicitud = await db.solicitudes.find_one({"_id": body["id"]})
    assert solicitud["fecha_envio"] is not None


async def test_crear_solicitud_borrador_no_queda_enviada(client, db):
    resp = await client.post(
        "/captacion/solicitudes", json=_solicitud_payload(telefono="+593910000002", cedula="0102030406", enviar=False)
    )

    assert resp.status_code == 201
    assert resp.json()["estado"] == "BORRADOR"


async def test_crear_solicitud_con_cedula_activa_devuelve_409(client):
    await client.post("/captacion/solicitudes", json=_solicitud_payload(telefono="+593910000003"))

    resp = await client.post(
        "/captacion/solicitudes",
        json=_solicitud_payload(telefono="+593910000004", vehiculo={**_VEHICULO, "placa": "XYZ-0001"}),
    )

    assert resp.status_code == 409
    assert resp.json()["code"] == "SOLICITUD_CEDULA_ACTIVA"


async def test_crear_solicitud_marca_revision_reforzada_si_placa_ya_existe(client, db):
    await db.vehiculos.insert_one(
        {"_id": "veh-existente", "placa": "REP-9999", "estado_habilitacion": "HABILITADO", "propietario_id": "otro"}
    )

    payload = _solicitud_payload(
        telefono="+593910000005", cedula="0102030407", vehiculo={**_VEHICULO, "placa": "REP-9999"}
    )
    resp = await client.post("/captacion/solicitudes", json=payload)

    assert resp.status_code == 201
    assert resp.json()["revision_reforzada"] is True


async def test_listar_solicitudes_requiere_admin_captacion(client):
    resp = await client.get("/captacion/solicitudes")
    assert resp.status_code == 401


async def test_flujo_completo_tomar_y_aprobar_solicitud(client, db):
    headers = await _admin_headers(db)
    await db.tipos_documento.insert_many(
        [
            {"_id": "td-licencia", "nombre": "LICENCIA", "descripcion": "", "aplica_a": "conductor", "activo": True},
            {"_id": "td-matricula", "nombre": "MATRICULA", "descripcion": "", "aplica_a": "vehiculo", "activo": True},
        ]
    )
    creada = await client.post(
        "/captacion/solicitudes",
        json=_solicitud_payload(
            telefono="+593910000006",
            cedula="0102030408",
            vehiculo={**_VEHICULO, "placa": "APR-0001"},
            documentos=[
                {
                    "tipo": "LICENCIA",
                    "propietario_tipo": "CONDUCTOR",
                    "url_objeto": "https://storage.local/licencia.pdf",
                    "hash_archivo": "abc123",
                },
                {
                    "tipo": "MATRICULA",
                    "propietario_tipo": "VEHICULO",
                    "url_objeto": "https://storage.local/matricula.pdf",
                    "hash_archivo": "def456",
                },
            ],
        ),
    )
    solicitud_id = creada.json()["id"]
    usuario_id = creada.json()["usuario_id"]

    tomar = await client.post(f"/captacion/solicitudes/{solicitud_id}/tomar", headers=headers)
    assert tomar.status_code == 200
    assert tomar.json()["estado"] == "EN_VERIFICACION"

    decidir = await client.post(
        f"/captacion/solicitudes/{solicitud_id}/decision", json={"decision": "APROBADA"}, headers=headers
    )
    assert decidir.status_code == 200
    assert decidir.json()["estado"] == "APROBADA"

    usuario = await db.usuarios.find_one({"_id": usuario_id})
    assert "conductor" in usuario["roles"]
    assert usuario["conductor"]["cedula"] == "0102030408"

    vehiculo = await db.vehiculos.find_one({"placa": "APR-0001"})
    assert vehiculo["estado_habilitacion"] == "HABILITADO"
    assert vehiculo["propietario_id"] == usuario_id

    documentos = await db.documentos.find({"propietario_id": usuario_id}).to_list(length=10)
    assert len(documentos) == 1
    assert documentos[0]["estado_verificacion"] == "CONFORME"

    documentos_vehiculo = await db.documentos.find({"propietario_id": vehiculo["_id"]}).to_list(length=10)
    assert len(documentos_vehiculo) == 1


async def test_decidir_solicitud_rechazada_sin_motivo_devuelve_400(client, db):
    headers = await _admin_headers(db)
    payload = _solicitud_payload(
        telefono="+593910000007", cedula="0102030409", vehiculo={**_VEHICULO, "placa": "REJ-0001"}
    )
    creada = await client.post("/captacion/solicitudes", json=payload)
    solicitud_id = creada.json()["id"]

    resp = await client.post(
        f"/captacion/solicitudes/{solicitud_id}/decision", json={"decision": "RECHAZADA"}, headers=headers
    )

    assert resp.status_code == 400
    assert resp.json()["code"] == "MOTIVO_REQUERIDO"


async def test_decidir_solicitud_rechazada_con_motivo(client, db):
    headers = await _admin_headers(db)
    payload = _solicitud_payload(
        telefono="+593910000008", cedula="0102030410", vehiculo={**_VEHICULO, "placa": "REJ-0002"}
    )
    creada = await client.post("/captacion/solicitudes", json=payload)
    solicitud_id = creada.json()["id"]

    resp = await client.post(
        f"/captacion/solicitudes/{solicitud_id}/decision",
        json={"decision": "RECHAZADA", "motivo": "Licencia vencida"},
        headers=headers,
    )

    assert resp.status_code == 200
    assert resp.json()["estado"] == "RECHAZADA"
    assert resp.json()["motivo_rechazo"] == "Licencia vencida"


async def test_tomar_solicitud_en_estado_invalido_devuelve_409(client, db):
    headers = await _admin_headers(db)
    payload = _solicitud_payload(
        telefono="+593910000009", cedula="0102030411", vehiculo={**_VEHICULO, "placa": "INV-0001"}
    )
    creada = await client.post("/captacion/solicitudes", json=payload)
    solicitud_id = creada.json()["id"]
    await client.post(f"/captacion/solicitudes/{solicitud_id}/tomar", headers=headers)

    resp = await client.post(f"/captacion/solicitudes/{solicitud_id}/tomar", headers=headers)

    assert resp.status_code == 409
    assert resp.json()["code"] == "SOLICITUD_ESTADO_INVALIDO"


async def test_listar_solicitudes_devuelve_items_y_total(client, db):
    headers = await _admin_headers(db)
    await client.post(
        "/captacion/solicitudes",
        json=_solicitud_payload(
            telefono="+593910000020", cedula="0900000020", vehiculo={**_VEHICULO, "placa": "PAG-0001"}
        ),
    )

    resp = await client.get("/captacion/solicitudes", headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert "total" in body
    assert body["total"] >= 1


async def test_listar_solicitudes_pagina_resultados(client, db):
    headers = await _admin_headers(db)
    for i in range(3):
        await client.post(
            "/captacion/solicitudes",
            json=_solicitud_payload(
                telefono=f"+59391000005{i}",
                cedula=f"090000005{i}",
                vehiculo={**_VEHICULO, "placa": f"PAG000{i}"},
            ),
        )

    pagina1 = await client.get("/captacion/solicitudes?limit=2&offset=0", headers=headers)
    pagina2 = await client.get("/captacion/solicitudes?limit=2&offset=2", headers=headers)

    assert pagina1.status_code == 200
    body1 = pagina1.json()
    body2 = pagina2.json()
    assert len(body1["items"]) == 2
    assert body1["total"] == body2["total"]
    assert body1["total"] >= 3
    ids_pagina1 = {s["id"] for s in body1["items"]}
    ids_pagina2 = {s["id"] for s in body2["items"]}
    assert ids_pagina1.isdisjoint(ids_pagina2)


async def test_listar_solicitudes_filtra_por_cedula(client, db):
    headers = await _admin_headers(db)
    await client.post(
        "/captacion/solicitudes",
        json=_solicitud_payload(
            telefono="+593910000060", cedula="0911112222", vehiculo={**_VEHICULO, "placa": "CED-0001"}
        ),
    )
    await client.post(
        "/captacion/solicitudes",
        json=_solicitud_payload(
            telefono="+593910000061", cedula="0933334444", vehiculo={**_VEHICULO, "placa": "CED-0002"}
        ),
    )

    resp = await client.get("/captacion/solicitudes?cedula=0911112222", headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["cedula"] == "0911112222"


async def test_crear_solicitud_con_tipo_documento_no_reconocido_devuelve_422(client, db):
    payload = _solicitud_payload(
        telefono="+593910000070",
        cedula="0900000070",
        vehiculo={**_VEHICULO, "placa": "TDN-0001"},
        documentos=[
            {
                "tipo": "TIPO_INEXISTENTE",
                "propietario_tipo": "CONDUCTOR",
                "url_objeto": "https://storage.local/doc.pdf",
                "hash_archivo": "abc123",
            }
        ],
    )
    resp = await client.post("/captacion/solicitudes", json=payload)

    assert resp.status_code == 422
    assert resp.json()["code"] == "TIPO_DOCUMENTO_INVALIDO"


async def test_crear_solicitud_con_tipo_documento_inactivo_devuelve_422(client, db):
    await db.tipos_documento.insert_one(
        {
            "_id": "td-inactivo",
            "nombre": "CERTIFICADO_ANTECEDENTES",
            "descripcion": "",
            "aplica_a": "conductor",
            "activo": False,
        }
    )
    payload = _solicitud_payload(
        telefono="+593910000071",
        cedula="0900000071",
        vehiculo={**_VEHICULO, "placa": "TDN-0002"},
        documentos=[
            {
                "tipo": "CERTIFICADO_ANTECEDENTES",
                "propietario_tipo": "CONDUCTOR",
                "url_objeto": "https://storage.local/doc.pdf",
                "hash_archivo": "abc123",
            }
        ],
    )
    resp = await client.post("/captacion/solicitudes", json=payload)

    assert resp.status_code == 422
    assert resp.json()["code"] == "TIPO_DOCUMENTO_INVALIDO"


async def test_crear_solicitud_con_tipo_documento_activo_es_aceptado(client, db):
    await db.tipos_documento.insert_one(
        {"_id": "td-licencia-2", "nombre": "LICENCIA", "descripcion": "", "aplica_a": "conductor", "activo": True}
    )
    payload = _solicitud_payload(
        telefono="+593910000072",
        cedula="0900000072",
        vehiculo={**_VEHICULO, "placa": "TDN-0003"},
        documentos=[
            {
                "tipo": "LICENCIA",
                "propietario_tipo": "CONDUCTOR",
                "url_objeto": "https://storage.local/doc.pdf",
                "hash_archivo": "abc123",
            }
        ],
    )
    resp = await client.post("/captacion/solicitudes", json=payload)

    assert resp.status_code == 201
