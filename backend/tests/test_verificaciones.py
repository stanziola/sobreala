"""El registro completo, las verificaciones con documento y el límite de envío.

Desde octubre de 2026 el registro trae lo que después se verifica: el teléfono
personal (con su país), los de la empresa, la dirección y la identificación
personal. La identificación y la dirección se verifican a mano, con un
documento que el cliente sube y que se borra en cuanto el administrador decide.
Y el administrador puede limitar una cuenta: entra y prepara, pero no envía.
"""

from __future__ import annotations

import io

from conftest import login, register
from test_admin import make_admin, make_client_account
from test_payments import confirm

from models import account as accounts
from models import admin_event as decisions
from models import mail_log
from models import verification_doc as verification_docs
from services import sender

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
            "tax_id": "8-123-456", "password": "Contrasena-Larga1"}
    data.update(changes)
    return browser.post("/signup", data=data)


def upload(browser, kind, raw, name="doc.pdf"):
    return browser.post(f"/settings/account/document/{kind}", data={
        "csrf_token": csrf(browser, "/settings"),
        "archivo": (io.BytesIO(raw), name)}, content_type="multipart/form-data")


def decide(admin, cliente, kind, decision, motivo=""):
    return admin.post(f"/admin/accounts/{cliente['_id']}/verify/{kind}", data={
        "csrf_token": csrf(admin, "/admin/"), "decision": decision,
        "reason": motivo})


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

def test_el_registro_pide_telefono_direccion_e_identificacion(client, database,
                                                             outbox):
    pantalla = client.get("/signup").get_data(as_text=True)
    # El país con su bandera, Panamá primero y elegido.
    assert ('<option value="PA" selected>\U0001F1F5\U0001F1E6 +507 Panamá</option>'
            in pantalla)
    assert pantalla.index('value="PA"') < pantalla.index('value="AF"')
    assert "Identificación personal" in pantalla
    assert "RUC o cédula" not in pantalla

    faltan = signup(other(client), phone="", address="", tax_id="")
    texto = faltan.get_data(as_text=True)
    assert texto.count('class="error"') >= 3
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
        "address": "Calle 10, Santiago de Veraguas", "tax_id": "8-123-456",
        "password": "Contrasena-Larga1"})

    cuenta = accounts.by_email(database, CLIENTA)
    assert cuenta["phone"] == "+50688881234"
    # Hasta tres, y el vacío no cuenta.
    assert cuenta["company_phones"] == ["+5079981234", "+13055550101"]
    assert cuenta["postal_address"] == "Calle 10, Santiago de Veraguas"
    assert cuenta["tax_id"] == "8-123-456"
    assert accounts.verification_of(cuenta, accounts.IDENTITY)["status"] == accounts.MISSING


# ------------------------------------------------------------ Configuración

def test_configuracion_cambia_los_telefonos(client, database, outbox):
    browser, cuenta = make_client_account(client, database, CLIENTA)
    pantalla = browser.get("/settings").get_data(as_text=True)
    assert 'id="phones"' in pantalla and 'id="verificaciones"' in pantalla

    browser.post("/settings/account", data={
        "csrf_token": csrf(browser, "/settings"), "what": "phones",
        "phone_country": "PA", "phone": "6111-2222",
        "company_phone_country": ["PA"], "company_phone": ["998-0000"]})
    cuenta = accounts.by_id(database, cuenta["_id"])
    assert cuenta["phone"] == "+50761112222"
    assert cuenta["company_phones"] == ["+5079980000"]

    malo = browser.post("/settings/account", data={
        "csrf_token": csrf(browser, "/settings"), "what": "phones",
        "phone_country": "PA", "phone": "abc"})
    assert "Ese número no parece válido" in malo.get_data(as_text=True)
    assert accounts.by_id(database, cuenta["_id"])["phone"] == "+50761112222"


def test_subir_un_documento_lo_deja_en_revision(client, database, outbox):
    browser, cuenta = make_client_account(client, database, CLIENTA)

    for raw in (b"hola, no soy un documento", b""):
        malo = upload(browser, accounts.IDENTITY, raw)
        assert "doc=bad" in malo.headers["Location"]
    grande = upload(browser, accounts.IDENTITY,
                    PDF + b"0" * verification_docs.MAX_BYTES)
    assert "doc=bad" in grande.headers["Location"]
    assert verification_docs.of(database, cuenta["_id"], accounts.IDENTITY) is None

    for kind, raw in ((accounts.IDENTITY, JPG), (accounts.ADDRESS, PDF)):
        bueno = upload(browser, kind, raw)
        assert "doc=ok" in bueno.headers["Location"]
    # Subir otro reemplaza el anterior.
    upload(browser, accounts.IDENTITY, PNG)

    cuenta = accounts.by_id(database, cuenta["_id"])
    for kind in accounts.VERIFY_KINDS:
        assert accounts.verification_of(cuenta, kind)["status"] == accounts.REVIEW
    guardado = verification_docs.of(database, cuenta["_id"], accounts.IDENTITY)
    assert guardado["mime"] == "image/png"
    assert database.verification_docs.count_documents({"account_id": cuenta["_id"]}) == 2
    assert "En revisión" in browser.get("/settings").get_data(as_text=True)


def test_cambiar_el_dato_vuelve_a_pedir_el_documento(client, database, outbox):
    admin, _ = make_admin(client, database)
    browser, cuenta = make_client_account(client, database, CLIENTA)
    upload(browser, accounts.IDENTITY, PDF)
    decide(admin, cuenta, accounts.IDENTITY, "verified")
    upload(browser, accounts.ADDRESS, PDF)

    browser.post("/settings/account", data={
        "csrf_token": csrf(browser, "/settings"), "what": "tax_id",
        "tax_id": "E-8-12345"})
    browser.post("/settings/account", data={
        "csrf_token": csrf(browser, "/settings"),
        "address": "Avenida Central, Ciudad de Panamá"})

    cuenta = accounts.by_id(database, cuenta["_id"])
    assert cuenta["tax_id"] == "E-8-12345"
    for kind in accounts.VERIFY_KINDS:
        assert accounts.verification_of(cuenta, kind)["status"] == accounts.MISSING
    assert database.verification_docs.count_documents({"account_id": cuenta["_id"]}) == 0


def test_un_usuario_no_sube_documentos(client, database, outbox):
    from test_users import accept, invite, invite_link

    dueno, cuenta = make_client_account(client, database, CLIENTA)
    database.accounts.update_one({"_id": cuenta["_id"]}, {"$set": {"plan": "negocio"}})
    invite(dueno)
    luis, _ = accept(client, invite_link(outbox))

    # Su Configuración es solo Seguridad: de ahí sale el token.
    respuesta = luis.post("/settings/account/document/identity", data={
        "csrf_token": csrf(luis, "/settings/security"),
        "archivo": (io.BytesIO(PDF), "doc.pdf")}, content_type="multipart/form-data")
    assert "/settings/security" in respuesta.headers["Location"]
    assert verification_docs.of(database, cuenta["_id"], accounts.IDENTITY) is None


# ----------------------------------------------------------- la ficha

def test_verificar_borra_el_documento(client, database, outbox):
    admin, _ = make_admin(client, database)
    browser, cuenta = make_client_account(client, database, CLIENTA)
    upload(browser, accounts.IDENTITY, PDF)

    ficha = admin.get(f"/admin/accounts/{cuenta['_id']}").get_data(as_text=True)
    assert "Ver documento" in ficha
    bajado = admin.get(f"/admin/accounts/{cuenta['_id']}/document/identity")
    assert bajado.data == PDF
    assert bajado.mimetype == "application/pdf"
    assert bajado.headers["Content-Disposition"].startswith("attachment;")
    # Nadie más lo baja: ni la clienta ni un curioso.
    assert browser.get(f"/admin/accounts/{cuenta['_id']}/document/identity").status_code == 404

    decide(admin, cuenta, accounts.IDENTITY, "verified")

    cuenta = accounts.by_id(database, cuenta["_id"])
    assert accounts.verification_of(cuenta, accounts.IDENTITY)["status"] == accounts.VERIFIED
    assert verification_docs.of(database, cuenta["_id"], accounts.IDENTITY) is None
    assert admin.get(f"/admin/accounts/{cuenta['_id']}/document/identity").status_code == 404
    escrito = decisions.for_account(database, cuenta["_id"])
    assert escrito[0]["kind"] == decisions.VERIFY
    assert "Verificada" in browser.get("/settings").get_data(as_text=True)


def test_rechazar_pide_motivo_y_avisa(client, database, outbox):
    admin, _ = make_admin(client, database)
    browser, cuenta = make_client_account(client, database, CLIENTA)
    upload(browser, accounts.ADDRESS, PDF)

    sin_motivo = decide(admin, cuenta, accounts.ADDRESS, "rejected")
    assert "missing=reason" in sin_motivo.headers["Location"]
    assert accounts.verification_of(accounts.by_id(database, cuenta["_id"]),
                                    accounts.ADDRESS)["status"] == accounts.REVIEW

    decide(admin, cuenta, accounts.ADDRESS, "rejected", "el recibo no se lee")

    cuenta = accounts.by_id(database, cuenta["_id"])
    estado = accounts.verification_of(cuenta, accounts.ADDRESS)
    assert estado["status"] == accounts.REJECTED
    assert estado["reason"] == "el recibo no se lee"
    assert verification_docs.of(database, cuenta["_id"], accounts.ADDRESS) is None
    aviso, = avisos(database, mail_log.DOC_REJECTED)
    assert aviso["to"] == CLIENTA and "el recibo no se lee" in aviso["text"]
    assert "el recibo no se lee" in browser.get("/settings").get_data(as_text=True)


def test_el_filtro_por_verificar(client, database, outbox):
    admin, _ = make_admin(client, database)
    browser, cuenta = make_client_account(client, database, CLIENTA)
    cola = "/admin/accounts?status=review"

    assert CLIENTA not in admin.get(cola).get_data(as_text=True)
    upload(browser, accounts.IDENTITY, PDF)
    assert CLIENTA in admin.get(cola).get_data(as_text=True)
    decide(admin, cuenta, accounts.IDENTITY, "verified")
    assert CLIENTA not in admin.get(cola).get_data(as_text=True)


# ----------------------------------------------------------- el límite

def test_limitar_no_deja_enviar_y_se_levanta_al_verificar(client, database, outbox):
    admin, _ = make_admin(client, database)
    browser, cuenta = make_client_account(client, database, CLIENTA)
    database.accounts.update_one({"_id": cuenta["_id"]}, {"$set": {"plan": "negocio"}})

    limit(admin, cuenta, nota="no cuadra la dirección")

    limitada = accounts.by_id(database, cuenta["_id"])
    assert accounts.limited_of(limitada)["reason"] == accounts.LIMIT_VERIFICATION
    assert "limited" in sender.blocked(limitada)
    # Entra y ve por qué, con el enlace a sus documentos.
    envios = browser.get("/campaigns").get_data(as_text=True)
    assert "Tu cuenta está limitada" in envios
    assert "#verificaciones" in envios
    assert "Tu cuenta está limitada." in browser.get("/settings").get_data(as_text=True)
    aviso, = avisos(database, mail_log.LIMITED)
    assert aviso["to"] == CLIENTA
    # La nota es para el registro, no para el correo.
    assert "no cuadra la dirección" not in aviso["text"]

    for kind in accounts.VERIFY_KINDS:
        upload(browser, kind, PDF)
    decide(admin, cuenta, accounts.IDENTITY, "verified")
    assert accounts.limited_of(accounts.by_id(database, cuenta["_id"]))
    decide(admin, cuenta, accounts.ADDRESS, "verified")

    libre = accounts.by_id(database, cuenta["_id"])
    assert accounts.limited_of(libre) is None
    assert "limited" not in sender.blocked(libre)
    tipos = [una["kind"] for una in decisions.for_account(database, cuenta["_id"])]
    assert tipos.count(decisions.LIMIT) == 2


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
