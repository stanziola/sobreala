"""El remitente de las campañas: el usuario en envios.sobreala.com, los
dominios propios de cada cliente, sus remitentes con nombre y los «Responder a»
que se confirman con un código. Desde octubre de 2026 hay varios de cada uno,
y cada plantilla elige los suyos.

Lo que se fija aquí es lo que, si se afloja, se afloja con la reputación de
otros: que una campaña nunca salga de la dirección del correo del sistema, que
dos cuentas no compartan usuario ni dominio, que nadie ponga como «Responder
a» la dirección de un tercero, y que un remitente salga solo de un dominio
verificado.
"""

from __future__ import annotations

import sys
import types

import pytest
from bson import ObjectId

from conftest import code_from_outbox, login, register

from config import Config
from models import account as accounts
from models import design as designs
from models import mail_log
from services import sender, ses_identity
from test_campaigns import catch, make, ready, send_it

URL = "/campaigns/sender"


def other(client):
    return client.application.test_client()


def csrf(client, url=URL):
    client.get(url)
    with client.session_transaction() as sess:
        return sess["_csrf"]


def owner(client, database, email="ana@ejemplo.com"):
    register(client, email=email)
    browser = other(client)
    login(browser, email=email)
    return browser, accounts.by_email(database, email)


def post(browser, **data):
    return browser.post(URL, data={"csrf_token": csrf(browser), **data})


def fresh(database, account):
    return accounts.by_id(database, account["_id"])


def verified(database, account, name="coop.org"):
    """Un dominio propio ya verificado, sin pasar por Amazon."""
    accounts.add_domain(database, account["_id"], name, ["a", "b", "c"])
    accounts.set_domain_status(database, account["_id"], name, accounts.DOMAIN_VERIFIED)
    return fresh(database, account)


class FakeSESv2:
    """Lo que el panel le pide a la API v2 de SES, sin salir a Amazon."""

    class exceptions:  # noqa: N801 - mirrors boto3's attribute
        class AlreadyExistsException(Exception):
            pass

        class NotFoundException(Exception):
            pass

    def __init__(self):
        self.calls: list[tuple[str, str]] = []
        self.verified: set[str] = set()
        # El MAIL FROM que se le pidió a cada identidad, y cuáles ya ven sus
        # registros.
        self.mail_from: dict[str, str] = {}
        self.mail_from_ok: set[str] = set()

    def create_email_identity(self, EmailIdentity, **kwargs):  # noqa: N803
        self.calls.append(("create", EmailIdentity))
        return {"DkimAttributes": {"Tokens": ["aaa", "bbb", "ccc"]}}

    def get_email_identity(self, EmailIdentity):  # noqa: N803
        self.calls.append(("get", EmailIdentity))
        ok = EmailIdentity in self.verified
        mail_from = self.mail_from.get(EmailIdentity, "")
        return {"VerifiedForSendingStatus": ok,
                "DkimAttributes": {"Status": "SUCCESS" if ok else "PENDING",
                                   "Tokens": ["aaa", "bbb", "ccc"]},
                "MailFromAttributes": {
                    "MailFromDomain": mail_from,
                    "MailFromDomainStatus": ("SUCCESS" if EmailIdentity in self.mail_from_ok
                                             else "PENDING"),
                    "BehaviorOnMxFailure": "USE_DEFAULT_VALUE"} if mail_from else {}}

    def put_email_identity_mail_from_attributes(self, EmailIdentity, MailFromDomain,  # noqa: N803
                                                BehaviorOnMxFailure):  # noqa: N803
        self.calls.append(("mail_from", EmailIdentity))
        assert BehaviorOnMxFailure == "USE_DEFAULT_VALUE"
        self.mail_from[EmailIdentity] = MailFromDomain
        return {}

    def delete_email_identity(self, EmailIdentity):  # noqa: N803
        self.calls.append(("delete", EmailIdentity))
        return {}

    def send_email(self, **kwargs):
        # El código del registro, que con MAIL_BACKEND=ses también pasa por
        # aquí. Se deja escrito en el buzón de las pruebas como siempre.
        return {"MessageId": "de-mentira"}


@pytest.fixture
def ses(monkeypatch):
    client = FakeSESv2()

    def make_client(service, region_name=None, **kwargs):
        assert service in ("sesv2", "ses")
        return client

    fake_boto3 = types.ModuleType("boto3")
    fake_boto3.client = make_client
    monkeypatch.setitem(sys.modules, "boto3", fake_boto3)
    monkeypatch.setattr(Config, "MAIL_BACKEND", "ses")
    return client


# ------------------------------------------------------------- el remitente

def test_sin_usuario_no_se_envia_y_nunca_sale_del_sistema(client, database, outbox):
    _, cuenta, _ = ready(client, database, handle=False)
    assert "sender" in sender.blocked(cuenta)
    assert sender.sender_email(cuenta) == ""
    assert Config.SYSTEM_FROM_EMAIL not in sender.from_address(cuenta)


def test_con_usuario_nace_su_primer_remitente(client, database, outbox):
    """El usuario en envíos trae el primer remitente, con el nombre de la
    empresa, y queda de predeterminado."""
    _, cuenta, _ = ready(client, database, handle=False)
    accounts.set_handle(database, cuenta["_id"], "coopveraguas")
    cuenta = fresh(database, cuenta)
    (primero,) = accounts.froms_of(cuenta)
    assert primero["shared"] and primero["ready"]
    assert accounts.sender_of(cuenta)["from_default"] == primero["id"]
    assert sender.sender_email(cuenta) == f"coopveraguas@{Config.SENDING_DOMAIN}"
    assert "sender" not in sender.blocked(cuenta)
    # Cambiar el usuario no le agrega otro: la dirección es la misma, nueva.
    accounts.set_handle(database, cuenta["_id"], "coopsantiago")
    assert len(accounts.froms_of(fresh(database, cuenta))) == 1
    assert sender.sender_email(fresh(database, cuenta)) == f"coopsantiago@{Config.SENDING_DOMAIN}"


def test_un_remitente_de_su_dominio_solo_si_esta_verificado(client, database, outbox):
    _, cuenta, _ = ready(client, database)
    accounts.add_domain(database, cuenta["_id"], "coopveraguas.org", ["a", "b", "c"])
    # Pendiente todavía: no se puede.
    assert accounts.add_from(database, fresh(database, cuenta), name="Boletín",
                             local="boletin", domain="coopveraguas.org") == (None, "domain")
    accounts.set_domain_status(database, cuenta["_id"], "coopveraguas.org",
                               accounts.DOMAIN_VERIFIED)
    nuevo, _ = accounts.add_from(database, fresh(database, cuenta), name="Boletín",
                                 local="boletin", domain="coopveraguas.org")
    # Agregarlo no lo hace el predeterminado: eso se elige.
    assert sender.sender_email(fresh(database, cuenta)).endswith("@" + Config.SENDING_DOMAIN)
    accounts.set_from_default(database, fresh(database, cuenta), nuevo)
    cuenta = fresh(database, cuenta)
    assert sender.sender_email(cuenta) == "boletin@coopveraguas.org"
    # Con su nombre, que no es el de la empresa.
    assert sender.remitente(cuenta)["label"] == "Boletín"
    assert sender.from_address(cuenta).endswith(" <boletin@coopveraguas.org>")


def test_el_correo_armado_lleva_el_from_y_el_reply_to(client, database, outbox):
    _, cuenta, pieza = ready(client, database)
    accounts.add_reply_to(database, cuenta["_id"], "socios@coopveraguas.org")
    cuenta = fresh(database, cuenta)
    contacto = database.contacts.find_one({"account_id": cuenta["_id"]})
    piece = sender.Piece(database.designs.find_one({"_id": pieza}))
    message = sender.build(cuenta, {"subject": "Hola", "_id": "x"}, piece, contacto)
    assert sender.sender_email(cuenta) in message["From"]
    assert message["Reply-To"] == "socios@coopveraguas.org"


# ----------------------------------------------------------- los remitentes

def test_varios_remitentes_con_su_nombre(client, database, outbox):
    browser, cuenta, _ = ready(client, database)
    cuenta = verified(database, cuenta, "coop.org")
    # Otro nombre para la dirección de envíos, y uno de su dominio.
    assert post(browser, action="from_add", name="Coop Cobros", local="",
                domain="shared").status_code == 302
    assert post(browser, action="from_add", name="Coop Boletín", local="boletin",
                domain="coop.org").status_code == 302
    nombres = {one["label"]: one["address"] for one in accounts.froms_of(fresh(database, cuenta))}
    assert nombres["Coop Cobros"].endswith("@" + Config.SENDING_DOMAIN)
    assert nombres["Coop Boletín"] == "boletin@coop.org"

    # Repetido, de otro dominio o con una dirección mala: no entra.
    pantalla = post(browser, action="from_add", name="coop cobros", local="",
                    domain="shared").get_data(as_text=True)
    assert "Ya tienes un remitente con ese nombre y esa dirección." in pantalla
    assert "no se puede usar" in post(browser, action="from_add", name="X", local="x",
                                      domain="ajeno.org").get_data(as_text=True)
    assert "sin espacios" in post(browser, action="from_add", name="X", local="con espacio",
                                  domain="coop.org").get_data(as_text=True)
    assert len(accounts.froms_of(fresh(database, cuenta))) == 3

    # Editar: el nombre, y en su dominio la dirección.
    boletin = next(one for one in accounts.froms_of(fresh(database, cuenta))
                   if one["label"] == "Coop Boletín")
    assert "same=1" in post(browser, action="from_edit", id=str(boletin["id"]),
                            name="Coop Boletín", local="boletin").headers["Location"]
    post(browser, action="from_edit", id=str(boletin["id"]), name="Noticias",
         local="noticias")
    editado = accounts.from_of(fresh(database, cuenta), boletin["id"])
    assert editado["label"] == "Noticias" and editado["address"] == "noticias@coop.org"

    # El predeterminado: se elige, y si se quita, vuelve el de envíos.
    post(browser, action="from_default", id=str(boletin["id"]))
    assert sender.sender_email(fresh(database, cuenta)) == "noticias@coop.org"
    post(browser, action="from_remove", id=str(boletin["id"]))
    assert sender.sender_email(fresh(database, cuenta)).endswith("@" + Config.SENDING_DOMAIN)
    assert accounts.default_from(fresh(database, cuenta))["shared"]


def test_hay_un_tope_de_remitentes(client, database, outbox):
    browser, cuenta, _ = ready(client, database)
    database.accounts.update_one({"_id": cuenta["_id"]}, {"$push": {"sender.froms": {"$each": [
        {"id": ObjectId(), "name": f"Nombre {n}", "local": "", "domain": ""}
        for n in range(accounts.FROM_LIMIT - 1)]}}})
    pantalla = post(browser, action="from_add", name="Otro", domain="shared").get_data(as_text=True)
    assert f"Ya tienes {accounts.FROM_LIMIT} remitentes" in pantalla


# ------------------------------------------------------------- el usuario

def test_el_usuario_se_elige_y_no_se_repite(client, database, outbox):
    browser, cuenta = owner(client, database)
    post(browser, action="handle", handle="coopveraguas")
    assert accounts.sender_of(fresh(database, cuenta))["handle"] == "coopveraguas"

    otra, otra_cuenta = owner(client, database, email="bea@ejemplo.com")
    pantalla = post(otra, action="handle", handle="coopveraguas").get_data(as_text=True)
    assert "ya la usa otra cuenta" in pantalla
    assert "handle" not in accounts.sender_of(fresh(database, otra_cuenta))


@pytest.mark.parametrize("malo", ["ab", "info", "soporte", "con espacio",
                                  ".punto", "guion-", "dos..puntos", "tildé"])
def test_los_usuarios_malos_o_reservados_no_entran(malo):
    assert accounts.clean_handle(malo) is None


def test_la_sugerencia_sale_del_nombre_y_esquiva_una_tomada(client, database, outbox):
    _, cuenta = owner(client, database)
    accounts.set_handle(database, cuenta["_id"], "cooperativaveraguas")
    assert accounts.suggest_handle(database, "Cooperativa Veraguas") == "cooperativaveraguas2"
    assert accounts.suggest_handle(database, "Ñandú & Cía") == "nanducia"


# ------------------------------------------------------------- responder a

def test_el_responder_a_espera_su_codigo(client, database, outbox):
    browser, cuenta = owner(client, database)
    respuesta = post(browser, action="reply", reply_to="socios@coop.org")
    assert respuesta.headers["Location"].endswith("/campaigns/sender/code")

    codigo = list(database.mail_log.find({"purpose": mail_log.REPLY_TO_CODE}))
    assert len(codigo) == 1 and codigo[0]["to"] == "socios@coop.org"
    # Mientras no entra el código, las respuestas siguen yendo al dueño.
    assert sender.reply_to(fresh(database, cuenta)) == "ana@ejemplo.com"

    browser.post("/campaigns/sender/code", data={
        "csrf_token": csrf(browser, "/campaigns/sender/code"), "code": list("000000")})
    assert sender.reply_to(fresh(database, cuenta)) == "ana@ejemplo.com"

    browser.post("/campaigns/sender/code", data={
        "csrf_token": csrf(browser, "/campaigns/sender/code"),
        "code": list(code_from_outbox(outbox))})
    # La primera queda de predeterminada.
    assert sender.reply_to(fresh(database, cuenta)) == "socios@coop.org"
    assert "reply_to_pending" not in accounts.sender_of(fresh(database, cuenta))


def test_una_direccion_de_su_dominio_verificado_no_pide_codigo(client, database, outbox):
    browser, cuenta = owner(client, database)
    verified(database, cuenta, "coop.org")
    post(browser, action="reply", reply_to="socios@coop.org")
    assert sender.reply_to(fresh(database, cuenta)) == "socios@coop.org"
    assert not database.mail_log.find_one({"purpose": mail_log.REPLY_TO_CODE})


def test_varios_responder_a_con_su_predeterminado(client, database, outbox):
    browser, cuenta = owner(client, database)
    verified(database, cuenta, "coop.org")
    post(browser, action="reply", reply_to="socios@coop.org")
    post(browser, action="reply", reply_to="gerencia@coop.org")
    cuenta = fresh(database, cuenta)
    assert accounts.reply_tos_of(cuenta) == ["socios@coop.org", "gerencia@coop.org"]
    # La segunda no cambia el predeterminado; eso se elige.
    assert sender.reply_to(cuenta) == "socios@coop.org"
    assert "ya está en la lista" in post(browser, action="reply",
                                         reply_to="SOCIOS@coop.org").get_data(as_text=True)
    post(browser, action="reply_default", address="gerencia@coop.org")
    assert sender.reply_to(fresh(database, cuenta)) == "gerencia@coop.org"
    # Quitar el predeterminado deja el que queda; sin ninguno, el del dueño.
    post(browser, action="reply_remove", address="gerencia@coop.org")
    assert sender.reply_to(fresh(database, cuenta)) == "socios@coop.org"
    post(browser, action="reply_remove", address="socios@coop.org")
    assert sender.reply_to(fresh(database, cuenta)) == "ana@ejemplo.com"


# --------------------------------------------------------------- el dominio

@pytest.mark.parametrize("malo", ["gmail.com", "hotmail.com", "sinpunto",
                                  "envios.sobreala.com", "sobreala.com"])
def test_los_dominios_de_correo_gratis_y_los_nuestros_no_entran(malo):
    assert accounts.clean_domain(malo) is None


def test_el_dominio_pegado_como_venga_se_limpia():
    assert accounts.clean_domain("https://www.CoopVeraguas.org/inicio") == "coopveraguas.org"


def test_conectar_comprobar_y_quitar_un_dominio(client, database, outbox, ses):
    browser, cuenta = owner(client, database)
    post(browser, action="domain", domain="coopveraguas.org")
    (mio,) = accounts.domains_of(fresh(database, cuenta))
    assert mio["name"] == "coopveraguas.org"
    assert mio["dkim_tokens"] == ["aaa", "bbb", "ccc"]
    assert mio["status"] == accounts.DOMAIN_PENDING
    assert ("create", "coopveraguas.org") in ses.calls

    pantalla = browser.get(URL).get_data(as_text=True)
    assert "aaa._domainkey.coopveraguas.org" in pantalla
    assert "aaa.dkim.amazonses.com" in pantalla

    ses.verified.add("coopveraguas.org")
    post(browser, action="check", domain="coopveraguas.org")
    assert accounts.domains_of(fresh(database, cuenta))[0]["status"] == accounts.DOMAIN_VERIFIED

    post(browser, action="remove", domain="coopveraguas.org")
    assert accounts.domains_of(fresh(database, cuenta)) == []
    assert ("delete", "coopveraguas.org") in ses.calls


def test_varios_dominios_y_su_tope(client, database, outbox, ses):
    browser, cuenta = owner(client, database)
    for n in range(accounts.DOMAIN_LIMIT):
        post(browser, action="domain", domain=f"coop{n}.org")
    assert len(accounts.domains_of(fresh(database, cuenta))) == accounts.DOMAIN_LIMIT
    pantalla = post(browser, action="domain", domain="otra.org").get_data(as_text=True)
    assert f"Ya tienes {accounts.DOMAIN_LIMIT} dominios" in pantalla
    # El mismo otra vez tampoco.
    accounts.remove_domain(database, fresh(database, cuenta), "coop4.org")
    assert "ya está en tu lista" in post(browser, action="domain",
                                         domain="coop0.org").get_data(as_text=True)


def test_quitar_un_dominio_se_lleva_sus_remitentes_y_sus_responder_a(
        client, database, outbox, ses):
    browser, cuenta, pieza = ready(client, database)
    cuenta = verified(database, cuenta, "coop.org")
    suyo, _ = accounts.add_from(database, cuenta, name="Boletín", local="boletin",
                                domain="coop.org")
    accounts.set_from_default(database, fresh(database, cuenta), suyo)
    post(browser, action="reply", reply_to="socios@coop.org")
    # La plantilla que salía de ahí vuelve al predeterminado.
    designs.set_sending(database, cuenta["_id"], pieza, send_from=suyo,
                        reply_to="socios@coop.org")

    post(browser, action="remove", domain="coop.org")
    cuenta = fresh(database, cuenta)
    assert accounts.from_of(cuenta, suyo) is None
    assert accounts.reply_tos_of(cuenta) == []
    assert accounts.default_from(cuenta)["shared"]
    plantilla = database.designs.find_one({"_id": pieza})
    assert "send_from" not in plantilla and "reply_to" not in plantilla


def test_los_registros_se_bajan_como_archivo_de_zona(client, database, outbox, ses):
    browser, cuenta = owner(client, database)
    # Un dominio que no es de la cuenta no tiene archivo.
    assert browser.get("/campaigns/sender/records/coopveraguas.org.txt").status_code == 404

    post(browser, action="domain", domain="coopveraguas.org")
    pantalla = browser.get(URL).get_data(as_text=True)
    assert 'href="/campaigns/sender/records/coopveraguas.org.txt"' in pantalla
    assert "Descargar los registros DNS" in pantalla
    # El botón ya no da por hecho Cloudflare, y el archivo tampoco.
    assert "para Cloudflare" not in pantalla

    archivo = browser.get("/campaigns/sender/records/coopveraguas.org.txt")
    assert archivo.status_code == 200
    assert archivo.mimetype == "text/plain"
    assert ('attachment; filename="registros-dns-coopveraguas.org.txt"'
            == archivo.headers["Content-Disposition"])
    texto = archivo.get_data(as_text=True)
    assert "En Cloudflare" not in texto
    lineas = [one for one in texto.splitlines() if one and not one.startswith(";")]
    # Los tres CNAME, con el nombre completo y su punto final, y sin proxy; y
    # el MX y el SPF del MAIL FROM (octubre de 2026), que no pasan por el proxy.
    assert lineas == [
        f"{token}._domainkey.coopveraguas.org.\t3600\tIN\tCNAME\t"
        f"{token}.dkim.amazonses.com.\t; cf_tags=cf-proxied:false"
        for token in ("aaa", "bbb", "ccc")] + [
        f"envios.coopveraguas.org.\t3600\tIN\tMX\t10 feedback-smtp.{Config.AWS_REGION}.amazonses.com.",
        'envios.coopveraguas.org.\t3600\tIN\tTXT\t"v=spf1 include:amazonses.com ~all"']
    # El de otra cuenta, tampoco.
    otra, _ = owner(client, database, email="bea@ejemplo.com")
    assert otra.get("/campaigns/sender/records/coopveraguas.org.txt").status_code == 404

    # Verificado DKIM, quedan los dos del MAIL FROM; con ellos, nada.
    ses.verified.add("coopveraguas.org")
    post(browser, action="check", domain="coopveraguas.org")
    pantalla = browser.get(URL).get_data(as_text=True)
    assert "agrega estos dos registros" in pantalla and "records/" in pantalla
    assert "Esperando los registros" in pantalla
    ses.mail_from_ok.add("coopveraguas.org")
    pantalla = browser.get(URL).get_data(as_text=True)
    assert "records/" not in pantalla and ">\n    Listo</span>" in pantalla


def test_el_dominio_lleva_su_propio_mail_from(client, database, outbox, ses):
    """Lo que Gmail enseña en «enviado por»: envios.<dominio>, pedido al
    conectar; y a un dominio conectado antes, al abrir Remitente."""
    browser, cuenta = owner(client, database)
    post(browser, action="domain", domain="coopveraguas.org")
    assert ses.mail_from["coopveraguas.org"] == "envios.coopveraguas.org"
    pantalla = browser.get(URL).get_data(as_text=True)
    assert "envios.coopveraguas.org" in pantalla
    assert f"feedback-smtp.{Config.AWS_REGION}.amazonses.com" in pantalla

    # Uno de antes, sin MAIL FROM en SES: se le pone al abrir la pantalla.
    del ses.mail_from["coopveraguas.org"]
    browser.get(URL)
    assert ses.mail_from["coopveraguas.org"] == "envios.coopveraguas.org"
    assert ses.calls.count(("mail_from", "coopveraguas.org")) == 2
    # Con el suyo puesto, abrir la pantalla no lo vuelve a pedir.
    browser.get(URL)
    assert ses.calls.count(("mail_from", "coopveraguas.org")) == 2


def test_el_dominio_de_otra_cuenta_no_se_toca(client, database, outbox, ses):
    browser, _ = owner(client, database)
    post(browser, action="domain", domain="coopveraguas.org")
    otra, otra_cuenta = owner(client, database, email="bea@ejemplo.com")
    pantalla = post(otra, action="domain", domain="coopveraguas.org").get_data(as_text=True)
    assert "ya está conectado en otra cuenta" in pantalla
    assert accounts.domains_of(fresh(database, otra_cuenta)) == []
    # Amazon no se entera: se rechaza antes de llamarlo.
    assert ses.calls.count(("create", "coopveraguas.org")) == 1
    # Ni se comprueba ni se quita desde otra cuenta.
    post(otra, action="remove", domain="coopveraguas.org")
    assert ("delete", "coopveraguas.org") not in ses.calls


def test_sin_amazon_el_dominio_se_recorre_de_mentira(client, database, outbox):
    assert Config.MAIL_BACKEND != "ses"
    assert len(ses_identity.create("coop.org")) == 3
    assert ses_identity.status("coop.org") == ses_identity.VERIFIED


# --------------------------------------------------- cada plantilla elige

def elegir(browser, url, **choice):
    """Guardar la plantilla de antes con su remitente y su «Responder a»."""
    datos = {"csrf_token": csrf(browser, url), "nombre": "Aviso", "titulo": "Corte",
             "texto": "El martes", "action": "guardar", **choice}
    return browser.post(url, data=datos)


def test_la_plantilla_elige_de_quien_sale_y_a_donde_se_responde(
        client, database, outbox, monkeypatch):
    browser, cuenta, pieza = ready(client, database)
    cuenta = verified(database, cuenta, "coop.org")
    cobros, _ = accounts.add_from(database, cuenta, name="Coop Cobros", local="cobros",
                                  domain="coop.org")
    post(browser, action="reply", reply_to="caja@coop.org")
    post(browser, action="reply", reply_to="socios@coop.org")

    url = f"/templates/piece/{pieza}"
    pantalla = browser.get(url).get_data(as_text=True)
    assert 'name="remitente"' in pantalla and 'name="responder"' in pantalla
    assert f'<option value="{cobros}">Coop Cobros &lt;cobros@coop.org&gt;</option>' in pantalla
    assert elegir(browser, url, remitente=str(cobros),
                  responder="socios@coop.org").status_code == 302
    guardada = database.designs.find_one({"_id": pieza})
    assert guardada["send_from"] == cobros and guardada["reply_to"] == "socios@coop.org"

    # La campaña con esa plantilla sale de ahí, y la pantalla que pregunta lo dice.
    salidos = catch(monkeypatch)
    make(browser, pieza)
    suya = database.campaigns.find_one({"account_id": cuenta["_id"]})
    pregunta = browser.get(f"/campaigns/{suya['_id']}/send").get_data(as_text=True)
    assert "Coop Cobros &lt;cobros@coop.org&gt;" in pregunta
    assert "socios@coop.org" in pregunta
    send_it(browser, database, cuenta["_id"])
    assert salidos and "cobros@coop.org" in salidos[0]["From"]
    assert salidos[0]["Reply-To"] == "socios@coop.org"

    # Lo de otra cuenta, o lo que no existe, es el predeterminado.
    elegir(browser, url, remitente=str(ObjectId()), responder="ajeno@otra.org")
    guardada = database.designs.find_one({"_id": pieza})
    assert "send_from" not in guardada and "reply_to" not in guardada


def test_si_se_quita_lo_elegido_sale_del_predeterminado(client, database, outbox):
    browser, cuenta, pieza = ready(client, database)
    cuenta = verified(database, cuenta, "coop.org")
    cobros, _ = accounts.add_from(database, cuenta, name="Coop Cobros", local="cobros",
                                  domain="coop.org")
    designs.set_sending(database, cuenta["_id"], pieza, send_from=cobros, reply_to=None)
    post(browser, action="from_remove", id=str(cobros))
    assert "send_from" not in database.designs.find_one({"_id": pieza})
    # Y aunque la plantilla todavía lo nombrara, sale del predeterminado.
    plantilla = dict(database.designs.find_one({"_id": pieza}), send_from=cobros)
    assert sender.sender_email(fresh(database, cuenta), plantilla).endswith(
        "@" + Config.SENDING_DOMAIN)


def test_lo_escrito_sale_del_predeterminado(client, database, outbox):
    _, cuenta, _ = ready(client, database)
    escrito = sender.Piece({"source": sender.WRITTEN, "body": "Hola"})
    contacto = database.contacts.find_one({"account_id": cuenta["_id"]})
    message = sender.build(cuenta, {"subject": "Hola", "_id": "x"}, escrito, contacto)
    assert sender.sender_email(cuenta) in message["From"]
    assert message["Reply-To"] == "ana@ejemplo.com"


# --------------------------------------------------------- la de antes

def test_la_cuenta_de_antes_pasa_a_las_listas(client, database, outbox):
    """Hasta octubre de 2026 había un dominio y un «Responder a» por cuenta.
    `ensure_indexes()` las pasa una vez: el dominio verificado con su
    dirección queda de remitente predeterminado, porque de ahí salían."""
    _, cuenta = owner(client, database)
    database.accounts.update_one({"_id": cuenta["_id"]}, {"$set": {"sender": {
        "handle": "coopveraguas", "domain": "coop.org",
        "domain_status": accounts.DOMAIN_VERIFIED, "dkim_tokens": ["a", "b", "c"],
        "domain_local": "boletin", "reply_to": "socios@coop.org"}}})
    accounts.migrate_sender(database)
    mine = accounts.sender_of(fresh(database, cuenta))
    assert not {"domain", "domain_status", "dkim_tokens", "domain_local",
                "reply_to"} & set(mine)
    assert mine["domains"][0]["name"] == "coop.org"
    assert mine["reply_tos"] == ["socios@coop.org"]
    cuenta = fresh(database, cuenta)
    assert sender.sender_email(cuenta) == "boletin@coop.org"
    assert sender.reply_to(cuenta) == "socios@coop.org"
    assert len(accounts.froms_of(cuenta)) == 2
    # Una vez: correrla otra vez no cambia nada.
    antes = accounts.sender_of(fresh(database, cuenta))
    accounts.migrate_sender(database)
    assert accounts.sender_of(fresh(database, cuenta)) == antes


# --------------------------------------------------------------- permisos

def test_un_usuario_del_equipo_la_ve_y_no_la_cambia(client, database, outbox):
    from test_users import as_member
    browser, empresa, suyo = as_member(client, database, outbox=outbox,
                                       permisos=(accounts.CAMPAIGNS, accounts.SEND))
    assert suyo.get(URL).status_code == 200
    with suyo.session_transaction() as sess:
        token = sess["_csrf"]
    suyo.post(URL, data={"csrf_token": token, "action": "handle", "handle": "intruso"})
    assert "handle" not in accounts.sender_of(fresh(database, empresa))
    suyo.post(URL, data={"csrf_token": token, "action": "from_add", "name": "Intruso",
                         "domain": "shared"})
    assert not accounts.sender_of(fresh(database, empresa)).get("froms")


# ------------------------------------------------------------------ DMARC

def test_dmarc_se_pide_solo_si_falta(client, database, outbox, ses, monkeypatch):
    """DMARC lo pone el cliente, no SES (octubre de 2026). Se mira en su DNS: si
    falta, se pide el registro y va en el archivo de zona; si ya tiene uno, no
    se pide otro, porque dos se anulan; y si no se pudo saber, se enseña con el
    aviso, pero no se mete en el archivo."""
    browser, cuenta = owner(client, database)
    post(browser, action="domain", domain="coopveraguas.org")
    monkeypatch.setattr(ses_identity, "_fake", lambda: False)
    monkeypatch.setattr(ses_identity, "_dmarc_seen", {})
    respuesta = {"coopveraguas.org": ses_identity.DMARC_MISSING}
    monkeypatch.setattr(ses_identity, "_lookup_dmarc", lambda domain: respuesta[domain])

    pantalla = browser.get(URL).get_data(as_text=True)
    assert "_dmarc.coopveraguas.org" in pantalla and "v=DMARC1; p=none;" in pantalla
    assert "Falta" in pantalla
    archivo = browser.get("/campaigns/sender/records/coopveraguas.org.txt").get_data(as_text=True)
    assert '_dmarc.coopveraguas.org.\t3600\tIN\tTXT\t"v=DMARC1; p=none;"' in archivo

    respuesta["coopveraguas.org"] = ses_identity.DMARC_OK
    monkeypatch.setattr(ses_identity, "_dmarc_seen", {})
    pantalla = browser.get(URL).get_data(as_text=True)
    assert "Publicado" in pantalla and "_dmarc.coopveraguas.org" not in pantalla
    archivo = browser.get("/campaigns/sender/records/coopveraguas.org.txt").get_data(as_text=True)
    assert "_dmarc" not in archivo

    respuesta["coopveraguas.org"] = ses_identity.DMARC_UNKNOWN
    monkeypatch.setattr(ses_identity, "_dmarc_seen", {})
    pantalla = browser.get(URL).get_data(as_text=True)
    assert "Sin comprobar" in pantalla and "no agregues otro" in pantalla
    archivo = browser.get("/campaigns/sender/records/coopveraguas.org.txt").get_data(as_text=True)
    assert "_dmarc" not in archivo
