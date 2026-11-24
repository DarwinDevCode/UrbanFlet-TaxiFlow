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


async def _subir_archivo_renovacion(client, headers_conductor):
    """Sube un archivo real (contexto `documento_renovacion`) y devuelve su
    id -- mismo flujo real que ahora exige `POST .../renovacion`, en vez del
    `url_objeto` de texto libre que aceptaba antes de cerrar el gap."""
    resp = await client.post(
        "/archivos",
        headers=headers_conductor,
        data={"contexto": "documento_renovacion"},
        files={"file": ("renovacion.jpg", b"\xff\xd8\xff" + b"0" * 50, "image/jpeg")},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


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

    headers_conductor = auth_headers("c4", ["conductor"])
    archivo_id = await _subir_archivo_renovacion(client, headers_conductor)
    subir = await client.post(
        "/cumplimiento/documentos/doc4/renovacion",
        headers=headers_conductor,
        json={"archivo_id": archivo_id, "fecha_vencimiento": "2027-01-01"},
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
    headers_conductor = auth_headers("c5", ["conductor"])
    archivo_id = await _subir_archivo_renovacion(client, headers_conductor)
    await client.post(
        "/cumplimiento/documentos/doc5/renovacion",
        headers=headers_conductor,
        json={"archivo_id": archivo_id, "fecha_vencimiento": "2027-01-01"},
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
    headers_conductor = auth_headers("c6", ["conductor"])
    archivo_id = await _subir_archivo_renovacion(client, headers_conductor)
    await client.post(
        "/cumplimiento/documentos/doc7/renovacion",
        headers=headers_conductor,
        json={"archivo_id": archivo_id, "fecha_vencimiento": "2027-01-01"},
    )

    resp = await client.get("/cumplimiento/documentos/renovaciones-pendientes", headers=headers)

    assert resp.status_code == 200
    pendientes = resp.json()
    assert any(p["documento_id"] == "doc7" for p in pendientes)


async def test_documentos_por_vencer_permite_gerencia_ademas_de_supervisor(client, db):
    """Ronda de mejoras (agosto 2026, punto 4 corregido): el KPI "Documentos
    vencidos" del panel ESTRATÉGICO de Cumplimiento Normativo (gateado a
    gerencia+supervisor_cumplimiento) reusa este endpoint táctico para su
    drill-down -- confirmado real en navegador que sin el OR-gate, gerencia
    veía el KPI pero el clic daba 403. `admin_captacion` (un rol cualquiera
    sin relación) debe seguir sin acceso."""
    headers_supervisor = await _supervisor_headers(db)
    await crear_usuario_activo(db, usuario_id="u-gerencia-doc", telefono="+593952000099", roles=["gerencia"])
    headers_gerencia = auth_headers("u-gerencia-doc", ["gerencia"])
    await crear_usuario_activo(db, usuario_id="u-otro-rol-doc", telefono="+593952000098", roles=["admin_captacion"])
    headers_otro = auth_headers("u-otro-rol-doc", ["admin_captacion"])

    resp_supervisor = await client.get("/cumplimiento/panel-tactico/documentos-por-vencer", headers=headers_supervisor)
    resp_gerencia = await client.get("/cumplimiento/panel-tactico/documentos-por-vencer", headers=headers_gerencia)
    resp_otro = await client.get("/cumplimiento/panel-tactico/documentos-por-vencer", headers=headers_otro)

    assert resp_supervisor.status_code == 200
    assert resp_gerencia.status_code == 200
    assert resp_otro.status_code == 403


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


# ---------------------------------------------------------------------------
# Cierre del gap real: autoservicio del conductor + endpoint asegurado
# ---------------------------------------------------------------------------


async def test_subir_renovacion_sin_sesion_es_401(client, db):
    await _conductor_con_vehiculo(db, 20, cumplimiento_ok_conductor=False)
    await db.documentos.insert_one(
        {
            "_id": "doc20",
            "tipo": "LICENCIA",
            "propietario_tipo": "CONDUCTOR",
            "propietario_id": "c20",
            "fecha_vencimiento": "2020-01-01",
            "estado_verificacion": "CONFORME",
        }
    )

    resp = await client.post(
        "/cumplimiento/documentos/doc20/renovacion",
        json={"archivo_id": "no-importa", "fecha_vencimiento": "2027-01-01"},
    )

    assert resp.status_code == 401


async def test_subir_renovacion_de_documento_ajeno_es_403(client, db):
    await _conductor_con_vehiculo(db, 21, cumplimiento_ok_conductor=False)
    await _conductor_con_vehiculo(db, 22, cumplimiento_ok_conductor=False)
    await db.documentos.insert_one(
        {
            "_id": "doc21",
            "tipo": "LICENCIA",
            "propietario_tipo": "CONDUCTOR",
            "propietario_id": "c21",
            "fecha_vencimiento": "2020-01-01",
            "estado_verificacion": "CONFORME",
        }
    )
    headers_otro = auth_headers("c22", ["conductor"])
    archivo_id = await _subir_archivo_renovacion(client, headers_otro)

    resp = await client.post(
        "/cumplimiento/documentos/doc21/renovacion",
        headers=headers_otro,
        json={"archivo_id": archivo_id, "fecha_vencimiento": "2027-01-01"},
    )

    assert resp.status_code == 403
    assert resp.json()["code"] == "DOCUMENTO_NO_PROPIO"


async def test_subir_renovacion_con_archivo_de_otro_contexto_es_422(client, db):
    await _conductor_con_vehiculo(db, 23, cumplimiento_ok_conductor=False)
    await db.documentos.insert_one(
        {
            "_id": "doc23",
            "tipo": "LICENCIA",
            "propietario_tipo": "CONDUCTOR",
            "propietario_id": "c23",
            "fecha_vencimiento": "2020-01-01",
            "estado_verificacion": "CONFORME",
        }
    )
    headers_conductor = auth_headers("c23", ["conductor"])
    subida = await client.post(
        "/archivos",
        headers=headers_conductor,
        data={"contexto": "reporte_falla"},
        files={"file": ("foto.jpg", b"\xff\xd8\xff" + b"0" * 50, "image/jpeg")},
    )
    archivo_id = subida.json()["id"]

    resp = await client.post(
        "/cumplimiento/documentos/doc23/renovacion",
        headers=headers_conductor,
        json={"archivo_id": archivo_id, "fecha_vencimiento": "2027-01-01"},
    )

    assert resp.status_code == 422
    assert resp.json()["code"] == "ARCHIVO_NO_VALIDO_PARA_RENOVACION"


async def test_listar_mis_documentos_incluye_los_del_conductor_y_de_su_vehiculo(client, db):
    await _conductor_con_vehiculo(db, 24, cumplimiento_ok_conductor=False)
    await db.documentos.insert_one(
        {
            "_id": "doc24-lic",
            "tipo": "LICENCIA_CONDUCIR",
            "propietario_tipo": "CONDUCTOR",
            "propietario_id": "c24",
            "fecha_vencimiento": "2020-01-01",
            "estado_verificacion": "CONFORME",
        }
    )
    await db.documentos.insert_one(
        {
            "_id": "doc24-mat",
            "tipo": "MATRICULA_VEHICULAR",
            "propietario_tipo": "VEHICULO",
            "propietario_id": "v24",
            "fecha_vencimiento": "2030-01-01",
            "estado_verificacion": "CONFORME",
        }
    )
    headers_conductor = auth_headers("c24", ["conductor"])

    resp = await client.get("/cumplimiento/documentos/mios", headers=headers_conductor)

    assert resp.status_code == 200
    ids = {d["id"] for d in resp.json()}
    assert ids == {"doc24-lic", "doc24-mat"}
    vencida = next(d for d in resp.json() if d["id"] == "doc24-lic")
    assert vencida["dias_restantes"] < 0


async def test_listar_mis_documentos_no_incluye_los_de_otro_conductor(client, db):
    await _conductor_con_vehiculo(db, 25, cumplimiento_ok_conductor=False)
    await _conductor_con_vehiculo(db, 26, cumplimiento_ok_conductor=False)
    await db.documentos.insert_one(
        {
            "_id": "doc26-lic",
            "tipo": "LICENCIA_CONDUCIR",
            "propietario_tipo": "CONDUCTOR",
            "propietario_id": "c26",
            "fecha_vencimiento": "2020-01-01",
            "estado_verificacion": "CONFORME",
        }
    )
    headers_c25 = auth_headers("c25", ["conductor"])

    resp = await client.get("/cumplimiento/documentos/mios", headers=headers_c25)

    assert resp.status_code == 200
    assert resp.json() == []


async def test_flujo_completo_de_renovacion_real_del_conductor(client, db):
    """Extremo a extremo: el conductor ve su documento vencido, sube la
    renovación real, y aparece en la bandeja del supervisor -- el flujo que
    antes era estructuralmente imposible."""
    await _conductor_con_vehiculo(db, 27, cumplimiento_ok_conductor=False)
    await db.documentos.insert_one(
        {
            "_id": "doc27",
            "tipo": "LICENCIA_CONDUCIR",
            "propietario_tipo": "CONDUCTOR",
            "propietario_id": "c27",
            "fecha_vencimiento": "2020-01-01",
            "estado_verificacion": "CONFORME",
        }
    )
    headers_conductor = auth_headers("c27", ["conductor"])

    mios = await client.get("/cumplimiento/documentos/mios", headers=headers_conductor)
    assert mios.json()[0]["tiene_renovacion_pendiente"] is False

    archivo_id = await _subir_archivo_renovacion(client, headers_conductor)
    subir = await client.post(
        "/cumplimiento/documentos/doc27/renovacion",
        headers=headers_conductor,
        json={"archivo_id": archivo_id, "fecha_vencimiento": "2027-06-01"},
    )
    assert subir.status_code == 200

    mios2 = await client.get("/cumplimiento/documentos/mios", headers=headers_conductor)
    assert mios2.json()[0]["tiene_renovacion_pendiente"] is True

    headers_supervisor = await _supervisor_headers(db)
    pendientes = await client.get("/cumplimiento/documentos/renovaciones-pendientes", headers=headers_supervisor)
    assert any(p["documento_id"] == "doc27" for p in pendientes.json())


# ---------------------------------------------------------------------------
# Consulta documental de un socio por parte de personal interno (Fase 3 de
# gestión documental en la postulación). Solo lectura: ninguna acción de
# bloqueo operativo cuelga de este endpoint, a propósito.
# ---------------------------------------------------------------------------


async def test_personal_interno_consulta_los_documentos_de_un_conductor(client, db):
    await _conductor_con_vehiculo(db, 40, cumplimiento_ok_conductor=False)
    await db.documentos.insert_many(
        [
            {
                "_id": "doc40-lic",
                "tipo": "LICENCIA_CONDUCIR",
                "propietario_tipo": "CONDUCTOR",
                "propietario_id": "c40",
                "fecha_vencimiento": "2020-01-01",
                "estado_verificacion": "CONFORME",
            },
            {
                "_id": "doc40-mat",
                "tipo": "MATRICULA_VEHICULAR",
                "propietario_tipo": "VEHICULO",
                "propietario_id": "v40",
                "fecha_vencimiento": "2099-01-01",
                "estado_verificacion": "CONFORME",
            },
        ]
    )
    headers = await _supervisor_headers(db)

    resp = await client.get("/cumplimiento/documentos/conductor/c40", headers=headers)

    assert resp.status_code == 200
    # Mismo criterio de propiedad que el autoservicio: documentos del propio
    # conductor MÁS los de sus vehículos.
    assert {d["id"] for d in resp.json()} == {"doc40-lic", "doc40-mat"}
    assert next(d for d in resp.json() if d["id"] == "doc40-lic")["dias_restantes"] < 0


async def test_admin_captacion_tambien_puede_consultar_el_estado_documental(client, db):
    """Quien aprueba la postulación que originó esos documentos tiene que poder
    revisarlos después, no solo en el momento de decidir."""
    await _conductor_con_vehiculo(db, 41, cumplimiento_ok_conductor=False)
    await crear_usuario_activo(db, usuario_id="u-cap-doc", telefono="+593952000041", roles=["admin_captacion"])
    headers = auth_headers("u-cap-doc", ["admin_captacion"])

    resp = await client.get("/cumplimiento/documentos/conductor/c41", headers=headers)

    assert resp.status_code == 200


async def test_consulta_documental_interna_rechaza_un_rol_sin_relacion(client, db):
    await _conductor_con_vehiculo(db, 42, cumplimiento_ok_conductor=False)
    await crear_usuario_activo(db, usuario_id="u-pas-doc", telefono="+593952000042", roles=["pasajero"])
    headers = auth_headers("u-pas-doc", ["pasajero"])

    resp = await client.get("/cumplimiento/documentos/conductor/c42", headers=headers)

    assert resp.status_code == 403
