"""El remitente de las campañas: el usuario en envios.sobreala.com, el dominio
propio de cada cliente y el «Responder a» que se confirma con un código.

Lo que se fija aquí es lo que, si se afloja, se afloja con la reputación de
otros: que una campaña nunca salga de la dirección del correo del sistema, que
dos cuentas no compartan usuario ni dominio, y que nadie ponga como «Responder
a» la dirección de un tercero.
"""

from __future__ import annotations

import sys
import types

import pytest

from conftest import code_from_outbox, login, register

from config import Config
from models import account as accounts
from models import mail_log
from services import sender, ses_identity
from test_campaigns import ready

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

    def create_email_identity(self, EmailIdentity, **kwargs):  # noqa: N803
        self.calls.append(("create", EmailIdentity))
        return {"DkimAttributes": {"Tokens": ["aaa", "bbb", "ccc"]}}

    def get_email_identity(self, EmailIdentity):  # noqa: N803
        self.calls.append(("get", EmailIdentity))
        ok = EmailIdentity in self.verified
        return {"VerifiedForSendingStatus": ok,
                "DkimAttributes": {"Status": "SUCCESS" if ok else "PENDING",
                                   "Tokens": ["aaa", "bbb", "ccc"]}}

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


def test_con_usuario_sale_del_subdominio_de_envios(client, database, outbox):
    _, cuenta, _ = ready(client, database, handle=False)
    accounts.set_handle(database, cuenta["_id"], "coopveraguas")
    cuenta = fresh(database, cuenta)
    assert sender.sender_email(cuenta) == f"coopveraguas@{Config.SENDING_DOMAIN}"
    assert "sender" not in sender.blocked(cuenta)


def test_con_dominio_verificado_sale_de_su_dominio(client, database, outbox):
    _, cuenta, _ = ready(client, database)
    accounts.set_domain(database, cuenta["_id"], "coopveraguas.org", ["a", "b", "c"])
    accounts.set_domain_local(database, cuenta["_id"], "boletin")
    # Pendiente todavía: sigue el usuario de envíos.
    assert sender.sender_email(fresh(database, cuenta)).endswith("@" + Config.SENDING_DOMAIN)
    accounts.set_domain_status(database, cuenta["_id"], accounts.DOMAIN_VERIFIED)
    assert sender.sender_email(fresh(database, cuenta)) == "boletin@coopveraguas.org"


def test_el_correo_armado_lleva_el_from_y_el_reply_to(client, database, outbox):
    _, cuenta, pieza = ready(client, database)
    accounts.set_reply_to(database, cuenta["_id"], "socios@coopveraguas.org")
    cuenta = fresh(database, cuenta)
    contacto = database.contacts.find_one({"account_id": cuenta["_id"]})
    piece = sender.Piece(database.designs.find_one({"_id": pieza}))
    message = sender.build(cuenta, {"subject": "Hola", "_id": "x"}, piece, contacto)
    assert sender.sender_email(cuenta) in message["From"]
    assert message["Reply-To"] == "socios@coopveraguas.org"


# --------------------------------------------------------------- el usuario

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
    assert sender.reply_to(fresh(database, cuenta)) == "socios@coop.org"


def test_una_direccion_de_su_dominio_verificado_no_pide_codigo(client, database, outbox):
    browser, cuenta = owner(client, database)
    accounts.set_domain(database, cuenta["_id"], "coop.org", ["a", "b", "c"])
    accounts.set_domain_status(database, cuenta["_id"], accounts.DOMAIN_VERIFIED)
    accounts.set_domain_local(database, cuenta["_id"], "boletin")
    post(browser, action="reply", reply_to="socios@coop.org")
    assert sender.reply_to(fresh(database, cuenta)) == "socios@coop.org"
    assert not database.mail_log.find_one({"purpose": mail_log.REPLY_TO_CODE})


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
    mio = accounts.sender_of(fresh(database, cuenta))
    assert mio["domain"] == "coopveraguas.org"
    assert mio["dkim_tokens"] == ["aaa", "bbb", "ccc"]
    assert mio["domain_status"] == accounts.DOMAIN_PENDING
    assert ("create", "coopveraguas.org") in ses.calls

    pantalla = browser.get(URL).get_data(as_text=True)
    assert "aaa._domainkey.coopveraguas.org" in pantalla
    assert "aaa.dkim.amazonses.com" in pantalla

    ses.verified.add("coopveraguas.org")
    post(browser, action="check")
    assert accounts.sender_of(fresh(database, cuenta))["domain_status"] == accounts.DOMAIN_VERIFIED

    post(browser, action="remove")
    assert "domain" not in accounts.sender_of(fresh(database, cuenta))
    assert ("delete", "coopveraguas.org") in ses.calls


def test_el_dominio_de_otra_cuenta_no_se_toca(client, database, outbox, ses):
    browser, _ = owner(client, database)
    post(browser, action="domain", domain="coopveraguas.org")
    otra, otra_cuenta = owner(client, database, email="bea@ejemplo.com")
    pantalla = post(otra, action="domain", domain="coopveraguas.org").get_data(as_text=True)
    assert "ya está conectado en otra cuenta" in pantalla
    assert "domain" not in accounts.sender_of(fresh(database, otra_cuenta))
    # Amazon no se entera: se rechaza antes de llamarlo.
    assert ses.calls.count(("create", "coopveraguas.org")) == 1


def test_sin_amazon_el_dominio_se_recorre_de_mentira(client, database, outbox):
    assert Config.MAIL_BACKEND != "ses"
    assert len(ses_identity.create("coop.org")) == 3
    assert ses_identity.status("coop.org") == ses_identity.VERIFIED


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
