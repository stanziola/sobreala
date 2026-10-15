"""El registro, las verificaciones con documento y el límite de envío.

Desde octubre de 2026 el registro trae el teléfono personal (con su país), los de
la empresa y la dirección. **La identificación no se escribe**: es solo el
documento, que junto con el de la dirección se envía en un formulario aparte
(`/verification`) y se borra en cuanto el administrador decide. El resultado se
lo manda el administrador con un botón, y rechazar limita la cuenta sola.
"""

from __future__ import annotations

import io

from test_admin import make_admin, make_client_account

from models import account as accounts
from models import admin_event as decisions
from models import mail_log
from models import verification_doc as verification_docs
from services import countries, sender

CLIENTA = "socia@ejemplo.com"
PDF = b"%PDF-1.4\n% una cedula de mentira\n"
JPG = b"\xff\xd8\xff\xe0" + b"0" * 64
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64


def other(client):
    return client.application.test_client()


def csrf(browser, url):
    browser.get(url)
    with browser.session_transaction() as sess:
        return sess["_csrf"]


def signup(browser, **changes):
    """Registrarse como lo hace la pantalla, con lo que se quiera cambiar."""
    data = {"csrf_token": csrf(browser, "/signup"), "company_name": "Tienda Ana",
            "contact_name": "Ana", "email": CLIENTA, "phone_country": "PA",
            "phone": "6000-0000", "address": "Calle 10, Santiago de Veraguas",
            "password": "Contrasena-Larga1"}
    data.update(changes)
    return browser.post("/signup", data=data)


def enviar(browser, *, identity=(PDF, "cedula.pdf"), address=(PDF, "recibo.pdf")):
    """Enviar el formulario de documentos, con lo que se quiera mandar."""
    data = {"csrf_token": csrf(browser, "/verification")}
    if identity is not None:
        data["identity"] = (io.BytesIO(identity[0]), identity[1])
    if address is not None:
        data["address"] = (io.BytesIO(address[0]), address[1])
    return browser.post("/verification", data=data,
                        content_type="multipart/form-data")


def decide(admin, cliente, kind, decision, motivo=""):
    return admin.post(f"/admin/accounts/{cliente['_id']}/verify/{kind}", data={
        "csrf_token": csrf(admin, "/admin/"), "decision": decision,
        "reason": motivo})


def avisar(admin, cliente):
    return admin.post(f"/admin/accounts/{cliente['_id']}/notify", data={
        "csrf_token": csrf(admin, "/admin/")})


def limit(admin, cliente, *, lift=False, nota=""):
    data = {"csrf_token": csrf(admin, "/admin/"), "note": nota}
    if lift:
        data["lift"] = "1"
    else:
        data["reason"] = accounts.LIMIT_VERIFICATION
    return admin.post(f"/admin/accounts/{cliente['_id']}/limit", data=data)


def avisos(database, purpose):
    return list(database.mail_log.find({"purpose": purpose}))


# ----------------------------------------------------------------- el registro

def test_el_registro_pide_telefono_y_direccion_y_ya_no_la_identificacion(
        client, database, outbox):
    pantalla = client.get("/signup").get_data(as_text=True)
    # El país con su bandera y su prefijo, y nada más: sin el nombre.
    assert ('<option value="PA" title="Panamá" selected>\U0001F1F5\U0001F1E6 +507</option>'
            in pantalla)
    assert "+507 Panamá" not in pantalla and "Panamá +507" not in pantalla
    assert pantalla.index('value="PA"') < pantalla.index('value="AF"')
    # La identificación ya no se escribe: es solo el documento.
    assert 'name="tax_id"' not in pantalla
    assert "Identificación personal" not in pantalla

    faltan = signup(other(client), phone="", address="")
    assert faltan.get_data(as_text=True).count('class="error"') >= 2
    assert accounts.by_email(database, CLIENTA) is None

    malo = signup(other(client), phone="seis mil")
    assert "Ese número no parece válido" in malo.get_data(as_text=True)
    assert accounts.by_email(database, CLIENTA) is None


def test_el_registro_guarda_los_telefonos_con_su_pais(client, database, outbox):
    browser = other(client)
    browser.get("/signup")
    with browser.session_transaction() as sess:
        token = sess["_csrf"]
    browser.post("/signup", data={
        "csrf_token": token, "company_name": "Tienda Ana", "contact_name": "Ana",
        "email": CLIENTA, "phone_country": "CR", "phone": "8888 1234",
        "company_phone_country": ["PA", "US", "PA", "PA"],
        "company_phone": ["998-1234", "(305) 555-0101", "", "6000-0009"],
        "address": "Calle 10, Santiago de Veraguas",
        "password": "Contrasena-Larga1"})

    cuenta = accounts.by_email(database, CLIENTA)
    assert cuenta["phone"] == "+50688881234"
    # Hasta tres, y el vacío no cuenta.
    assert cuenta["company_phones"] == ["+5079981234", "+13055550101"]
    assert cuenta["postal_address"] == "Calle 10, Santiago de Veraguas"
    assert "tax_id" not in cuenta
    for kind in accounts.VERIFY_KINDS:
        assert accounts.verification_of(cuenta, kind)["status"] == accounts.MISSING


def test_el_selector_es_solo_bandera_y_prefijo():
    uno = {one["iso"]: one for one in countries.options()}
    assert uno["PA"]["label"] == "\U0001F1F5\U0001F1E6 +507"
    assert uno["PA"]["name"] == "Panamá"
    assert all(" " in one["label"] and not any(c.isalpha() for c in one["label"]
                                              if ord(c) < 0x1F000)
               for one in uno.values())
    assert countries.options()[0]["iso"] == "PA"


# ---------------------------------------------- Configuración: texto y «Editar»

def test_configuracion_enseña_texto_y_editar_abre_el_formulario(client, database,
                                                                outbox):
    browser, cuenta = make_client_account(client, database, CLIENTA)
    accounts.set_phones(database, cuenta["_id"], phone="+50761112222",
                        company_phones=["+5079980000"])

    pantalla = browser.get("/settings/account").get_data(as_text=True)
    # Como texto, con su «Editar», y sin campos ni «Guardar» a la vista.
    assert "Calle 10, Santiago de Veraguas" in pantalla
    assert "+50761112222 · +5079980000" in pantalla
    assert "editar=address" in pantalla and "editar=phones" in pantalla
    assert 'name="address"' not in pantalla and 'name="phone"' not in pantalla
    assert "Guardar" not in pantalla
    # La identificación no se escribe, y los documentos ya no se suben aquí:
    # el único archivo de Cuenta es el logo de la empresa (octubre de 2026).
    assert 'name="tax_id"' not in pantalla
    assert pantalla.count('type="file"') == 1 and 'name="logo" type="file"' in pantalla
    assert 'name="identity"' not in pantalla

    editando = browser.get("/settings?editar=address").get_data(as_text=True)
    assert 'name="address"' in editando and "Guardar" in editando
    assert "Cancelar" in editando and 'name="phone"' not in editando
    editando = browser.get("/settings?editar=phones").get_data(as_text=True)
    assert 'name="phone"' in editando and 'name="address"' not in editando


def test_editar_guarda_los_telefonos_y_la_direccion(client, database, outbox):
    browser, cuenta = make_client_account(client, database, CLIENTA)

    browser.post("/settings/account", data={
        "csrf_token": csrf(browser, "/settings"), "what": "phones",
        "phone_country": "PA", "phone": "6111-2222",
        "company_phone_country": ["PA"], "company_phone": ["998-0000"]})
    cuenta = accounts.by_id(database, cuenta["_id"])
    assert cuenta["phone"] == "+50761112222"
    assert cuenta["company_phones"] == ["+5079980000"]

    # Uno malo se dice dentro del formulario abierto, y no cambia nada.
    malo = browser.post("/settings/account", data={
        "csrf_token": csrf(browser, "/settings"), "what": "phones",
        "phone_country": "PA", "phone": "abc"})
    pantalla = malo.get_data(as_text=True)
    assert "Ese número no parece válido" in pantalla and 'name="phone"' in pantalla
    assert accounts.by_id(database, cuenta["_id"])["phone"] == "+50761112222"

    corta = browser.post("/settings/account", data={
        "csrf_token": csrf(browser, "/settings"), "address": "corta"})
    assert 'name="address"' in corta.get_data(as_text=True)
    assert accounts.postal_of(accounts.by_id(database, cuenta["_id"])) == \
        "Calle 10, Santiago de Veraguas"


def test_cambiar_la_direccion_vuelve_a_pedir_su_documento(client, database, outbox):
    admin, _ = make_admin(client, database)
    browser, cuenta = make_client_account(client, database, CLIENTA)
    enviar(browser)
    decide(admin, cuenta, accounts.ADDRESS, "verified")
    enviar(browser)  # la identificación sigue en revisión: nada que pedir

    browser.post("/settings/account", data={
        "csrf_token": csrf(browser, "/settings"),
        "address": "Avenida Central, Ciudad de Panamá"})

    cuenta = accounts.by_id(database, cuenta["_id"])
    assert accounts.verification_of(cuenta, accounts.ADDRESS)["status"] == accounts.MISSING
    assert verification_docs.of(database, cuenta["_id"], accounts.ADDRESS) is None
    # Y vuelve a pedirse solo ese.
    pantalla = browser.get("/verification").get_data(as_text=True)
    assert 'name="address"' in pantalla and 'name="identity"' not in pantalla


# ------------------------------------------------------ el formulario de documentos

def test_el_aviso_lleva_al_formulario_y_el_formulario_pide_los_dos(client, database,
                                                                   outbox):
    browser, cuenta = make_client_account(client, database, CLIENTA)

    cuenta_ = browser.get("/settings").get_data(as_text=True)
    assert "notice--pending" in cuenta_ and 'href="/verification"' in cuenta_

    pantalla = browser.get("/verification").get_data(as_text=True)
    assert 'name="identity"' in pantalla and 'name="address"' in pantalla
    assert pantalla.count('type="file"') == 2
    assert "Enviar documentos" in pantalla
    assert "cédula o pasaporte" in pantalla and "certifique tu dirección" in pantalla


def test_enviar_deja_los_dos_en_revision_y_no_se_ven_despues(client, database,
                                                             outbox):
    browser, cuenta = make_client_account(client, database, CLIENTA)

    respuesta = enviar(browser, identity=(JPG, "c.jpg"), address=(PNG, "r.png"))
    assert respuesta.headers["Location"].endswith("/verification?sent=1")

    cuenta = accounts.by_id(database, cuenta["_id"])
    for kind in accounts.VERIFY_KINDS:
        assert accounts.verification_of(cuenta, kind)["status"] == accounts.REVIEW
    assert database.verification_docs.count_documents({"account_id": cuenta["_id"]}) == 2
    assert verification_docs.of(database, cuenta["_id"], "identity")["mime"] == "image/jpeg"

    # Después: sin formulario, sin archivos, y el aviso amarillo se fue.
    despues = browser.get("/verification?sent=1").get_data(as_text=True)
    assert "Recibimos tus documentos" in despues
    assert 'type="file"' not in despues
    assert "cedula" not in despues and "recibo" not in despues
    assert "notice--pending" not in browser.get("/settings").get_data(as_text=True)
    # Mandarlo otra vez no cambia nada: ya no hay qué enviar.
    otra = enviar(browser, identity=(PDF, "otro.pdf"))
    assert otra.status_code == 302
    assert verification_docs.of(database, cuenta["_id"], "identity")["mime"] == "image/jpeg"


def test_el_formulario_exige_los_dos_y_buenos(client, database, outbox):
    browser, cuenta = make_client_account(client, database, CLIENTA)

    sin_uno = enviar(browser, address=None)
    assert "Tiene que ser un PDF, JPG o PNG" in sin_uno.get_data(as_text=True)
    mal_tipo = enviar(browser, identity=(b"hola, no soy un documento", "x.pdf"))
    assert "Tiene que ser un PDF, JPG o PNG" in mal_tipo.get_data(as_text=True)
    grande = enviar(browser, address=(PDF + b"0" * verification_docs.MAX_BYTES, "g.pdf"))
    assert "hasta 5 MB" in grande.get_data(as_text=True)

    # Si uno no sirve no se guarda ninguno: no queda uno solo a medias.
    assert database.verification_docs.count_documents({"account_id": cuenta["_id"]}) == 0
    for kind in accounts.VERIFY_KINDS:
        assert accounts.verification_of(accounts.by_id(database, cuenta["_id"]),
                                        kind)["status"] == accounts.MISSING


def test_un_usuario_no_envia_documentos(client, database, outbox):
    from test_users import accept, invite, invite_link

    dueno, cuenta = make_client_account(client, database, CLIENTA)
    database.accounts.update_one({"_id": cuenta["_id"]}, {"$set": {"plan": "negocio"}})
    invite(dueno)
    luis, _ = accept(client, invite_link(outbox))

    assert "/settings/security" in luis.get("/verification").headers["Location"]
    respuesta = luis.post("/verification", data={
        "csrf_token": csrf(luis, "/settings/security"),
        "identity": (io.BytesIO(PDF), "c.pdf"), "address": (io.BytesIO(PDF), "r.pdf")},
        content_type="multipart/form-data")
    assert "/settings/security" in respuesta.headers["Location"]
    assert database.verification_docs.count_documents({"account_id": cuenta["_id"]}) == 0


# ----------------------------------------------------------- la ficha

def test_verificar_borra_el_documento_y_no_manda_correo(client, database, outbox):
    admin, _ = make_admin(client, database)
    browser, cuenta = make_client_account(client, database, CLIENTA)
    enviar(browser)

    ficha = admin.get(f"/admin/accounts/{cuenta['_id']}").get_data(as_text=True)
    assert "Ver documento" in ficha
    bajado = admin.get(f"/admin/accounts/{cuenta['_id']}/document/identity")
    assert bajado.data == PDF and bajado.mimetype == "application/pdf"
    assert bajado.headers["Content-Disposition"].startswith("attachment;")
    # Nadie más lo baja: ni la clienta ni un curioso.
    assert browser.get(f"/admin/accounts/{cuenta['_id']}/document/identity").status_code == 404

    decide(admin, cuenta, accounts.IDENTITY, "verified")

    cuenta = accounts.by_id(database, cuenta["_id"])
    assert accounts.verification_of(cuenta, accounts.IDENTITY)["status"] == accounts.VERIFIED
    assert verification_docs.of(database, cuenta["_id"], accounts.IDENTITY) is None
    assert admin.get(f"/admin/accounts/{cuenta['_id']}/document/identity").status_code == 404
    assert decisions.for_account(database, cuenta["_id"])[0]["kind"] == decisions.VERIFY
    # El correo lo manda el administrador con su botón, no esto.
    assert avisos(database, mail_log.VERIFICATION_RESULT) == []


def test_rechazar_pide_motivo_limita_sola_y_no_manda_correo(client, database, outbox):
    admin, _ = make_admin(client, database)
    browser, cuenta = make_client_account(client, database, CLIENTA)
    database.accounts.update_one({"_id": cuenta["_id"]}, {"$set": {"plan": "negocio"}})
    enviar(browser)

    sin_motivo = decide(admin, cuenta, accounts.ADDRESS, "rejected")
    assert "missing=reason" in sin_motivo.headers["Location"]
    sin = accounts.by_id(database, cuenta["_id"])
    assert accounts.verification_of(sin, accounts.ADDRESS)["status"] == accounts.REVIEW
    assert accounts.limited_of(sin) is None

    decide(admin, cuenta, accounts.ADDRESS, "rejected", "el recibo no se lee")

    cuenta = accounts.by_id(database, cuenta["_id"])
    estado = accounts.verification_of(cuenta, accounts.ADDRESS)
    assert estado["status"] == accounts.REJECTED and estado["reason"] == "el recibo no se lee"
    assert verification_docs.of(database, cuenta["_id"], accounts.ADDRESS) is None
    # Rechazar limita la cuenta sola, y no manda ningún correo.
    assert accounts.limited_of(cuenta)["reason"] == accounts.LIMIT_VERIFICATION
    assert "limited" in sender.blocked(cuenta)
    assert avisos(database, mail_log.VERIFICATION_RESULT) == []
    assert avisos(database, mail_log.LIMITED) == []

    # Tras el rechazo solo se pide el rechazado, con su motivo.
    pantalla = browser.get("/verification").get_data(as_text=True)
    assert 'name="address"' in pantalla and 'name="identity"' not in pantalla
    assert "el recibo no se lee" in pantalla
    assert "Tu cuenta está limitada" in browser.get("/campaigns").get_data(as_text=True)


def test_volver_a_enviar_y_verificar_los_dos_levanta_el_limite(client, database,
                                                              outbox):
    admin, _ = make_admin(client, database)
    browser, cuenta = make_client_account(client, database, CLIENTA)
    database.accounts.update_one({"_id": cuenta["_id"]}, {"$set": {"plan": "negocio"}})
    enviar(browser)
    decide(admin, cuenta, accounts.IDENTITY, "verified")
    decide(admin, cuenta, accounts.ADDRESS, "rejected", "no se lee")
    assert accounts.limited_of(accounts.by_id(database, cuenta["_id"]))

    enviar(browser, identity=None)  # solo el que se rechazó
    assert accounts.verification_of(accounts.by_id(database, cuenta["_id"]),
                                    accounts.ADDRESS)["status"] == accounts.REVIEW
    # En revisión sigue limitada: lo levanta verificar, no subir.
    assert accounts.limited_of(accounts.by_id(database, cuenta["_id"]))

    decide(admin, cuenta, accounts.ADDRESS, "verified")

    libre = accounts.by_id(database, cuenta["_id"])
    assert accounts.limited_of(libre) is None and "limited" not in sender.blocked(libre)
    assert accounts.all_verified(libre)


def test_el_boton_manda_el_resultado(client, database, outbox):
    admin, _ = make_admin(client, database)
    browser, cuenta = make_client_account(client, database, CLIENTA)
    enviar(browser)

    # Sin ningún resultado no hay nada que contar.
    assert "Enviar correo al cliente" not in admin.get(
        f"/admin/accounts/{cuenta['_id']}").get_data(as_text=True)
    avisar(admin, cuenta)
    assert avisos(database, mail_log.VERIFICATION_RESULT) == []

    decide(admin, cuenta, accounts.IDENTITY, "verified")
    decide(admin, cuenta, accounts.ADDRESS, "rejected", "el recibo no se lee")
    assert "Enviar correo al cliente" in admin.get(
        f"/admin/accounts/{cuenta['_id']}").get_data(as_text=True)
    assert avisos(database, mail_log.VERIFICATION_RESULT) == []

    avisar(admin, cuenta)

    aviso, = avisos(database, mail_log.VERIFICATION_RESULT)
    assert aviso["to"] == CLIENTA
    assert "Identificación personal: verificada" in aviso["text"]
    assert "Dirección: no pudimos verificarla. Motivo: el recibo no se lee" in aviso["text"]
    assert "no puedes enviar campañas" in aviso["text"]
    assert decisions.for_account(database, cuenta["_id"])[0]["kind"] == decisions.NOTIFY

    # Con las dos verificadas, el correo lo confirma.
    enviar(browser, identity=None)
    decide(admin, cuenta, accounts.ADDRESS, "verified")
    avisar(admin, cuenta)
    ultimo = avisos(database, mail_log.VERIFICATION_RESULT)[-1]
    assert "Tu cuenta quedó verificada" in ultimo["text"]


def test_el_filtro_por_verificar(client, database, outbox):
    admin, _ = make_admin(client, database)
    browser, cuenta = make_client_account(client, database, CLIENTA)
    cola = "/admin/accounts?status=review"

    assert CLIENTA not in admin.get(cola).get_data(as_text=True)
    enviar(browser)
    assert CLIENTA in admin.get(cola).get_data(as_text=True)
    decide(admin, cuenta, accounts.IDENTITY, "verified")
    decide(admin, cuenta, accounts.ADDRESS, "verified")
    assert CLIENTA not in admin.get(cola).get_data(as_text=True)


# ----------------------------------------------------------- el límite

def test_limitar_a_mano_no_deja_enviar_y_avisa(client, database, outbox):
    admin, _ = make_admin(client, database)
    browser, cuenta = make_client_account(client, database, CLIENTA)
    database.accounts.update_one({"_id": cuenta["_id"]}, {"$set": {"plan": "negocio"}})

    limit(admin, cuenta, nota="no cuadra la dirección")

    limitada = accounts.by_id(database, cuenta["_id"])
    assert accounts.limited_of(limitada)["reason"] == accounts.LIMIT_VERIFICATION
    assert "limited" in sender.blocked(limitada)
    # Entra y ve por qué, con el enlace al formulario.
    envios = browser.get("/campaigns").get_data(as_text=True)
    assert "Tu cuenta está limitada" in envios and 'href="/verification"' in envios
    assert "Tu cuenta está limitada." in browser.get("/settings").get_data(as_text=True)
    aviso, = avisos(database, mail_log.LIMITED)
    assert aviso["to"] == CLIENTA
    # La nota es para el registro, no para el correo.
    assert "no cuadra la dirección" not in aviso["text"]
    assert "/verification" in aviso["text"]


def test_quitar_el_limite_a_mano(client, database, outbox):
    admin, _ = make_admin(client, database)
    _, cuenta = make_client_account(client, database, CLIENTA)

    limit(admin, cuenta)
    # Limitar otra vez no hace nada ni manda otro correo.
    limit(admin, cuenta)
    assert len(avisos(database, mail_log.LIMITED)) == 1

    limit(admin, cuenta, lift=True, nota="ya lo hablamos")
    assert accounts.limited_of(accounts.by_id(database, cuenta["_id"])) is None
    ficha = admin.get(f"/admin/accounts/{cuenta['_id']}").get_data(as_text=True)
    assert "Limitar la cuenta" in ficha
