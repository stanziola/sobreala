"""Los avisos de Amazon SES: quién puede mandarlos y a dónde va cada uno.

Lo que se fija aquí es lo que no puede fallar en silencio. Que la dirección no
exista para quien no tiene el secreto. Que la confirmación de la suscripción no
sirva para hacer que el servidor abra cualquier dirección. Que un rebote anule
la dirección **en la cuenta a la que pertenece y en ninguna otra**. Y que las
cifras de un envío cuenten personas y no eventos.

Los avisos son de mentira, pero tienen la forma exacta de los de Amazon, y
desde octubre de 2026 van firmados como los firma Amazon: con una clave de
prueba cuyo certificado se sirve en lugar del de SNS (`services/sns.py`).
"""

from __future__ import annotations

import base64
import json
from datetime import datetime, timedelta, timezone

import pytest
from bson import ObjectId
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID

from blueprints.webhooks import routes as webhook
from config import Config
from models import event as events
from models import mail_log
from models import suppression as suppressions
from services import sns
from test_admin import make_admin
from test_campaigns import catch, make, ready, send_it

SECRET = "un-secreto-largo-de-prueba"
TOPIC = "arn:aws:sns:us-east-2:123456789012:sobreala-ses-events"


CERT_URL = ("https://sns.us-east-2.amazonaws.com/"
            "SimpleNotificationService-0000000000000000000000.pem")


def _clave():
    clave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    nombre = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "sns.amazonaws.com")])
    ahora = datetime.now(timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(nombre).issuer_name(nombre)
            .public_key(clave.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(ahora - timedelta(days=1))
            .not_valid_after(ahora + timedelta(days=30))
            .sign(clave, hashes.SHA256()))
    return clave, cert.public_bytes(serialization.Encoding.PEM)


CLAVE, PEM = _clave()


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    monkeypatch.setattr(Config, "SES_WEBHOOK_SECRET", SECRET)
    monkeypatch.setattr(Config, "SES_TOPIC_ARN", "")
    # El certificado de «Amazon» es el de la clave de prueba, y solo en su URL.
    bajados: list[str] = []
    monkeypatch.setattr(sns, "_cache", {})
    monkeypatch.setattr(sns, "fetch_cert",
                        lambda url: bajados.append(url) or (PEM if url == CERT_URL else b""))
    return bajados


def firmar(envelope, *, version="2", clave=None, url=CERT_URL):
    """Firmar un aviso como lo firma SNS."""
    envelope = {"MessageId": "11111111-2222-3333-4444-555555555555",
                "Timestamp": "2026-10-21T15:00:00.000Z", **envelope,
                "SignatureVersion": version, "SigningCertURL": url}
    texto = sns.signed_text(envelope)
    algoritmo = hashes.SHA256() if version == "2" else hashes.SHA1()
    firma = (clave or CLAVE).sign(texto.encode("utf-8"), padding.PKCS1v15(), algoritmo)
    envelope["Signature"] = base64.b64encode(firma).decode("ascii")
    return envelope


def notify(client, message, *, secret=SECRET, topic=TOPIC):
    """Mandar un aviso como lo manda SNS: el evento va dentro, como texto."""
    envelope = firmar({"Type": "Notification", "TopicArn": topic,
                       "Message": json.dumps(message)})
    return client.post(f"/webhooks/ses/{secret}", data=json.dumps(envelope),
                       content_type="text/plain; charset=UTF-8")


def campaign_event(kind, *, account, campaign, run, to, **body):
    """Un evento de un conjunto de configuración, con sus etiquetas."""
    return {
        "eventType": kind,
        "mail": {
            "timestamp": "2026-09-16T12:00:00.000Z",
            "messageId": "0100abc",
            "destination": [to],
            "tags": {"account": [str(account)], "campaign": [str(campaign)],
                     "run": [str(run)],
                     "ses:configuration-set": ["sobreala-campaigns"]},
        },
        **body,
    }


def bounce(kind, to):
    return {"bounce": {"bounceType": kind, "timestamp": "2026-09-16T12:01:00.000Z",
                       "bouncedRecipients": [{
                           "emailAddress": to, "status": "5.1.1",
                           "diagnosticCode": "smtp; 550 5.1.1 user unknown"}]}}


# ------------------------------------------------------------------ la puerta

def test_un_secreto_equivocado_no_encuentra_nada(client, database):
    cuenta, campana = ObjectId(), ObjectId()
    evento = campaign_event("Delivery", account=cuenta, campaign=campana,
                            run=ObjectId(), to="ana@coop.com",
                            delivery={"recipients": ["ana@coop.com"]})

    respuesta = notify(client, evento, secret="otro")

    assert respuesta.status_code == 404
    assert database.events.count_documents({}) == 0


def test_sin_secreto_configurado_la_direccion_no_existe(client, database,
                                                       monkeypatch):
    monkeypatch.setattr(Config, "SES_WEBHOOK_SECRET", "")

    assert notify(client, {}, secret="").status_code == 404
    assert notify(client, {}, secret="lo-que-sea").status_code == 404


def test_la_confirmacion_solo_se_visita_si_es_de_amazon(client, monkeypatch):
    """Ese campo lo escribe quien manda el cuerpo: visitarlo sin mirar sería
    dejar que cualquiera haga que el servidor abra la dirección que quiera."""
    visitadas: list[str] = []

    class Respuesta:
        status = 200
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False

    monkeypatch.setattr(webhook.urllib.request, "urlopen",
                        lambda url, timeout=10: visitadas.append(url) or Respuesta())

    for url in ("https://sns.us-east-2.amazonaws.com/?Action=ConfirmSubscription",
                "https://evil.example.com/?Action=ConfirmSubscription",
                "http://sns.us-east-2.amazonaws.com/?Action=ConfirmSubscription"):
        client.post(f"/webhooks/ses/{SECRET}", data=json.dumps(firmar({
            "Type": "SubscriptionConfirmation", "TopicArn": TOPIC, "Token": "t",
            "Message": "Confirma", "SubscribeURL": url})), content_type="text/plain")

    assert visitadas == [
        "https://sns.us-east-2.amazonaws.com/?Action=ConfirmSubscription"]


def test_un_aviso_de_otro_tema_se_descarta(client, database, monkeypatch):
    monkeypatch.setattr(Config, "SES_TOPIC_ARN", TOPIC)
    evento = campaign_event("Delivery", account=ObjectId(), campaign=ObjectId(),
                            run=ObjectId(), to="ana@coop.com",
                            delivery={"recipients": ["ana@coop.com"]})

    respuesta = notify(client, evento, topic="arn:aws:sns:us-east-2:999:otro")

    assert respuesta.status_code == 200
    assert database.events.count_documents({}) == 0


def test_un_aviso_ilegible_se_contesta_200_y_no_guarda_nada(client, database):
    """SNS reintenta lo que no recibe 200, y un aviso raro no se arregla por
    insistir."""
    respuesta = client.post(f"/webhooks/ses/{SECRET}", data="esto no es json",
                            content_type="text/plain")

    assert respuesta.status_code == 200
    assert database.events.count_documents({}) == 0


def test_sin_la_firma_de_amazon_no_se_guarda_nada(client, database, configured):
    """Con solo el secreto de la dirección ya no alcanza (octubre de 2026): quien
    lo tuviera podía inventar rebotes y quejas, que además viajan a los
    webhooks de los clientes."""
    evento = bounce("Permanent", "ana@coop.com")
    sobre = {"Type": "Notification", "TopicArn": TOPIC, "Message": json.dumps(evento)}
    otra, _ = _clave()
    cambiado = firmar(sobre)
    cambiado["Message"] = cambiado["Message"].replace("ana@coop.com", "bea@coop.com")
    for malo in (sobre,                                   # sin firma
                 cambiado,                                # el mensaje cambió
                 firmar(sobre, clave=otra),               # otra clave
                 firmar(sobre, version="3"),              # versión que no existe
                 firmar(sobre, url="https://evil.example.com/cert.pem"),
                 firmar(sobre, url="http://sns.us-east-2.amazonaws.com/x.pem")):
        respuesta = client.post(f"/webhooks/ses/{SECRET}", data=json.dumps(malo),
                                content_type="text/plain")
        assert respuesta.status_code == 403
    assert database.suppressions.count_documents({}) == 0
    # El certificado solo se pidió a Amazon, nunca a la dirección del cuerpo.
    assert set(configured) <= {CERT_URL}


def test_la_firma_vieja_de_sha1_tambien_vale(client, database):
    sobre = firmar({"Type": "Notification", "TopicArn": TOPIC,
                    "Message": json.dumps({"eventType": "Nada"})}, version="1")
    respuesta = client.post(f"/webhooks/ses/{SECRET}", data=json.dumps(sobre),
                            content_type="text/plain")
    assert respuesta.status_code == 200


def test_sin_poder_bajar_el_certificado_se_pide_reintentar(client, database,
                                                          monkeypatch):
    def caida(url):
        raise sns.Unavailable("sin red")
    monkeypatch.setattr(sns, "fetch_cert", caida)
    sobre = firmar({"Type": "Notification", "TopicArn": TOPIC, "Message": "{}"})
    respuesta = client.post(f"/webhooks/ses/{SECRET}", data=json.dumps(sobre),
                            content_type="text/plain")
    assert respuesta.status_code == 500


# -------------------------------------------------------------- las campañas

def test_un_rebote_permanente_anula_en_esa_cuenta_y_en_ninguna_otra(client,
                                                                   database):
    """La misma dirección en las listas de dos clientes: el rebote de la
    campaña de uno no la anula en el otro."""
    una, otra = ObjectId(), ObjectId()
    evento = campaign_event("Bounce", account=una, campaign=ObjectId(),
                            run=ObjectId(), to="ana@coop.com",
                            **bounce("Permanent", "ana@coop.com"))

    notify(client, evento)

    assert suppressions.has(database, una, "ana@coop.com")
    assert not suppressions.has(database, otra, "ana@coop.com")
    fila = database.suppressions.find_one({"account_id": una})
    assert fila["reason"] == suppressions.HARD_BOUNCE
    assert database.events.count_documents({"kind": events.BOUNCE}) == 1


def test_un_rebote_pasajero_no_anula_a_nadie(client, database):
    cuenta = ObjectId()
    evento = campaign_event("Bounce", account=cuenta, campaign=ObjectId(),
                            run=ObjectId(), to="ana@coop.com",
                            **bounce("Transient", "ana@coop.com"))

    notify(client, evento)

    assert not suppressions.has(database, cuenta, "ana@coop.com")
    assert database.events.count_documents({"kind": events.BOUNCE}) == 1


def test_una_queja_anula_y_una_entrega_no(client, database):
    cuenta, campana, envio = ObjectId(), ObjectId(), ObjectId()
    notify(client, campaign_event(
        "Delivery", account=cuenta, campaign=campana, run=envio,
        to="bea@coop.com", delivery={"recipients": ["bea@coop.com"]}))
    notify(client, campaign_event(
        "Complaint", account=cuenta, campaign=campana, run=envio,
        to="ana@coop.com",
        complaint={"complainedRecipients": [{"emailAddress": "ana@coop.com"}]}))

    assert not suppressions.has(database, cuenta, "bea@coop.com")
    assert suppressions.has(database, cuenta, "ana@coop.com")
    fila = database.suppressions.find_one({"account_id": cuenta})
    assert fila["reason"] == suppressions.COMPLAINT


def test_las_cifras_de_un_envio_cuentan_personas_y_no_aperturas(client,
                                                                database):
    cuenta, campana, envio = ObjectId(), ObjectId(), ObjectId()
    for _ in range(3):
        notify(client, campaign_event(
            "Open", account=cuenta, campaign=campana, run=envio,
            to="Ana@Coop.com", open={"timestamp": "2026-09-16T13:00:00.000Z"}))
    notify(client, campaign_event(
        "Open", account=cuenta, campaign=campana, run=envio,
        to="bea@coop.com", open={"timestamp": "2026-09-16T13:00:00.000Z"}))

    cifras = events.counts_by_run(database, cuenta, [envio])[envio]

    assert cifras[events.OPEN] == 2
    assert cifras[events.DELIVERED] == 0


def test_cada_correo_de_campana_sale_etiquetado(client, database, outbox,
                                                monkeypatch):
    """Las etiquetas son lo único que dice de quién es un rebote."""
    salidos = catch(monkeypatch)
    browser, account, piece = ready(client, database, howmany=1)
    make(browser, piece)

    send_it(browser, database, account["_id"])

    etiquetas = salidos[0]["X-SES-MESSAGE-TAGS"]
    campana = database.campaigns.find_one({"account_id": account["_id"]})
    assert f"account={account['_id']}" in etiquetas
    assert f"campaign={campana['_id']}" in etiquetas
    assert f"run={campana['run_id']}" in etiquetas
    # Y el envío que queda en el historial es ese mismo.
    assert database.campaign_runs.find_one({"_id": campana["run_id"]})


def test_la_baja_no_la_reescribe_amazon(client, database, outbox, monkeypatch):
    salidos = catch(monkeypatch)
    browser, account, piece = ready(client, database, howmany=1)
    make(browser, piece)

    send_it(browser, database, account["_id"])

    cuerpo = salidos[0].get_body(("html",)).get_content()
    assert "ses:no-track" in cuerpo


# ------------------------------------------------------- el correo del sistema

def test_un_aviso_de_un_correo_del_sistema_marca_su_fila(client, database):
    mail_log.record(database, to="joseph@utp.ac.pa", subject="Tu código",
                    backend="ses", status=mail_log.SENT, provider_id="0100sys")

    notify(client, {
        "eventType": "Bounce",
        "mail": {"messageId": "0100sys", "destination": ["joseph@utp.ac.pa"],
                 "tags": {"ses:configuration-set": ["sobreala-system"]}},
        **bounce("Permanent", "joseph@utp.ac.pa")})

    fila = database.mail_log.find_one({"provider_id": "0100sys"})
    assert fila["outcome"] == mail_log.BOUNCED
    assert "user unknown" in fila["outcome_detail"]
    # Y no anula a nadie: la supresión es de los contactos de un cliente.
    assert database.suppressions.count_documents({}) == 0


def test_correos_del_sistema_encuentra_por_direccion_sin_ensenar_el_cuerpo(
        client, database, outbox):
    admin, _ = make_admin(client, database)
    mail_log.record(database, to="joseph@utp.ac.pa", subject="Tu código",
                    backend="ses", status=mail_log.SENT, provider_id="0100sys",
                    html="<p>El código secreto es 123456</p>",
                    text="El código secreto es 123456")
    mail_log.mark(database, "0100sys", outcome=mail_log.DELIVERED)

    pantalla = admin.get("/admin/emails?q=Joseph@UTP.ac.pa").get_data(as_text=True)

    assert "Tu código" in pantalla
    assert "Entregado" in pantalla
    assert "123456" not in pantalla


def test_el_aviso_de_clic_guarda_su_enlace(client, database):
    """SES manda la direccion dentro del aviso, y hasta ahora se tiraba."""
    cuenta, campana, envio = ObjectId(), ObjectId(), ObjectId()
    # Ayer, y no una fecha fija: con una fija, al pasar 30 días el clic se salía
    # del periodo que se cuenta abajo y la prueba fallaba sola.
    ayer = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    for enlace in ("https://coop.com/asamblea", "https://coop.com/horario"):
        notify(client, campaign_event(
            "Click", account=cuenta, campaign=campana, run=envio,
            to="ana@coop.com",
            click={"timestamp": ayer, "link": enlace,
                   "ipAddress": "190.0.0.1", "userAgent": "Mozilla"}))

    # Un solo clic, con los dos enlaces dentro: la cifra no se infla.
    guardados = list(database.events.find({"account_id": cuenta,
                                           "kind": events.CLICK}))
    assert len(guardados) == 1
    assert sorted(guardados[0]["links"]) == ["https://coop.com/asamblea",
                                             "https://coop.com/horario"]
    assert [one["n"] for one in events.top_links(database, cuenta, period="30d")] == [1, 1]
