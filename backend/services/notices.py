"""Los avisos de la cuenta: el plan, la cuenta abierta y la suspensión.

Aquí se compone y se manda todo lo que le llega a un cliente **por algo que le
pasó a su cuenta** y no por su propia seguridad. Los de seguridad —el código de
confirmación, la contraseña cambiada, el doble factor— viven en el blueprint de
la cuenta y no se pueden apagar; estos sí, según lo que diga su pantalla de
Notificaciones.

Todos comparten un solo par de plantillas, `email/notice.html` y `.txt`,
porque todos tienen la misma forma: un titular, unos párrafos, y a veces un
botón, un recuadro o un código de seis dígitos. Lo que cambia es el texto, y el texto está en
`i18n.py` como todo lo que lee un cliente.

**Ninguno puede romper lo que estaba pasando.** Un correo que no sale no puede
hacer que un pago cobrado parezca fallido, así que el envío va envuelto y lo
único que deja es una línea en el registro. `mail_log` guarda el intento con su
error, como con cualquier otro correo del sistema.

Y como todos los del sistema, son transaccionales: **sin enlace de baja y sin
marca de agua**, que es la regla 8 de CLAUDE.md.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from flask import render_template, url_for

from config import Config
from i18n import on_date, t  # noqa: F401  (on_date se reexporta)
from services import clock
from models import account as accounts
from models import mail_log
from services import mailer, plans

# Con cuántos días de anticipación se avisa de un vencimiento.
WARN_DAYS = 7
# Y hasta cuándo tiene sentido avisar de uno que ya pasó. Sin esto, una cuenta
# de prueba de hace medio año recibiría un aviso de algo viejísimo la primera
# vez que alguien entre.
STALE_DAYS = 30

def plan_name(plan: str | None) -> str:
    return plans.PLANS.get(plan or "", {}).get("name", "")


def panel_url() -> str:
    return f"{Config.APP_BASE_URL}{url_for('auth.panel')}"


def deliver(account: dict[str, Any], *, purpose: str, subject: str,
            heading: str, paragraphs: list[str], button: dict | None = None,
            note: dict | None = None, foot: str = "", code: str = "",
            to: str = "") -> bool:
    """Mandar uno. True si salió.

    No deja escapar nada: quien llama acaba de cobrar un pago o de suspender una
    cuenta, y eso ya pasó aunque el correo no salga.

    `to` existe para el único caso en que el mensaje no va a la dirección de la
    cuenta: el código que prueba una dirección nueva, que tiene que llegar
    justamente a esa y no a la de siempre.
    """
    content = {"heading": heading, "paragraphs": paragraphs,
               "button": button, "note": note, "foot": foot, "code": code}
    try:
        mailer.send(
            to=to or account["email"], subject=subject,
            html=render_template("email/notice.html", **content),
            text=render_template("email/notice.txt", **content),
            purpose=purpose, account_id=account["_id"])
        return True
    except Exception as exc:  # noqa: BLE001 - reported, not handled
        print(f"  [avisos] no se pudo enviar {purpose} a "
              f"{to or account.get('email')}: {type(exc).__name__}: "
              f"{str(exc)[:160]}", flush=True)
        return False


def switch_off_hint() -> str:
    """La línea que dice dónde se apagan estos avisos.

    Solo la llevan los que se pueden apagar. Ponerla en uno que no se apaga
    sería mandar a alguien a buscar un interruptor que no existe.
    """
    return t("mail_notice_off")


# ------------------------------------------------------------------ el plan

def paid(account, *, plan: str, until, renewed: bool, charged: str = "",
         credit: str = "") -> bool:
    """El comprobante de que su plan quedó activo.

    Renovar y contratar no dicen lo mismo: al renovar lo importante es que los
    días que quedaban no se pierden, y al contratar, que ya tiene el plan. Dice
    lo que se cobró, y en una mejora, el descuento por los correos sin usar.
    """
    if not accounts.wants(account, accounts.BILLING):
        return False

    name = plan_name(plan)
    which = "renewed" if renewed else "started"
    paragraphs = [t(f"mail_plan_{which}_body", plan=name),
                  t("mail_plan_until", until=on_date(until, clock.for_account(account)))]
    if charged:
        paragraphs.append(
            t("mail_plan_charged_credit", amount=charged, credit=credit)
            if credit and credit != "0.00" else t("mail_plan_charged", amount=charged))
    return deliver(
        account, purpose=mail_log.PLAN_PAID,
        subject=t(f"mail_plan_{which}_subject", plan=name),
        heading=t(f"mail_plan_{which}_heading", plan=name),
        paragraphs=paragraphs,
        button={"href": panel_url(), "label": t("mail_plan_button")},
        foot=switch_off_hint())


def invited(member, *, company: str, link: str, days: int) -> bool:
    """La invitación a entrar como usuario de una cuenta.

    Va a la dirección de esa persona y lleva un enlace de un solo uso para que
    ponga **su** contraseña: el dueño no conoce la contraseña de nadie. No tiene
    interruptor: es el único correo que esa cuenta va a recibir si nunca lo
    abre, y sin él la invitación no existe.
    """
    return deliver(
        member, purpose=mail_log.INVITE,
        subject=t("mail_invite_subject", company=company),
        heading=t("mail_invite_heading", company=company),
        paragraphs=[t("mail_invite_body", company=company),
                    t("mail_invite_expires", days=days)],
        button={"href": link, "label": t("mail_invite_button")},
        foot=t("mail_invite_foot"))


def invoice_ready(account, *, paid_at) -> bool:
    """Ya está la factura de un pago. Es papeleo de un cobro, así que va con el
    interruptor de «Pagos y plan»."""
    if not accounts.wants(account, accounts.BILLING):
        return False
    when = on_date(paid_at, clock.for_account(account)) if paid_at else ""
    return deliver(
        account, purpose=mail_log.INVOICE,
        subject=t("mail_invoice_subject"),
        heading=t("mail_invoice_heading"),
        paragraphs=[t("mail_invoice_body", when=when)],
        button={"href": f"{Config.APP_BASE_URL}"
                        f"{url_for('auth.settings', section='billing')}",
                "label": t("mail_invoice_button")},
        foot=switch_off_hint())


def expiring(account, *, plan: str, until, days: int) -> bool:
    if not accounts.wants(account, accounts.PLAN_STATE):
        return False
    name = plan_name(plan)
    return deliver(
        account, purpose=mail_log.PLAN_EXPIRING,
        subject=t("mail_plan_expiring_subject", plan=name,
                  until=on_date(until, clock.for_account(account))),
        heading=t("mail_plan_expiring_heading", days=days),
        # Sin botón: el mismo plan no se paga antes de que venza.
        paragraphs=[t("mail_plan_expiring_body", plan=name,
                      until=on_date(until, clock.for_account(account)))],
        foot=switch_off_hint())


def expired(account, *, plan: str, until) -> bool:
    if not accounts.wants(account, accounts.PLAN_STATE):
        return False
    name = plan_name(plan)
    return deliver(
        account, purpose=mail_log.PLAN_EXPIRED,
        subject=t("mail_plan_expired_subject", plan=name),
        heading=t("mail_plan_expired_heading", plan=name),
        paragraphs=[t("mail_plan_expired_body", until=on_date(until, clock.for_account(account))),
                    t("mail_plan_expired_kept")],
        button={"href": f"{Config.APP_BASE_URL}"
                        f"{url_for('auth.checkout', plan=plan)}",
                "label": t("mail_plan_expired_button")},
        foot=switch_off_hint())


def plan_watch(db, account) -> None:
    """Mirar si a esta cuenta hay que avisarle algo de su plan.

    **Se hace cuando entra al panel, y no hay dónde más hacerlo hoy**: no existe
    un proceso en segundo plano que pueda darse cuenta a las tres de la mañana.
    Tiene el límite que se ve: solo le llega a quien entra, que es justamente
    quien menos lo necesita. El día que exista ese proceso, es mover esta misma
    llamada.

    Se manda una sola vez: queda escrito **para qué fecha de vencimiento** se
    avisó, así que renovar —que cambia esa fecha— deja el aviso disponible otra
    vez para el ciclo siguiente, sin ningún campo que limpiar a mano.
    """
    plan = accounts.plan_of(account)
    until = accounts.plan_until(account)
    if not plan or not until or accounts.is_suspended(account):
        return

    now = accounts.now()
    marks = account.get("plan_notices") or {}

    if until <= now:
        if now - until > timedelta(days=STALE_DAYS):
            return
        if marks.get(accounts.EXPIRED) != until:
            # Dos avisos del mismo vencimiento: al cliente y a quien administra.
            # La marca se escribe cuando los dos salieron, así que un correo
            # que falló se vuelve a intentar y ninguno se manda dos veces.
            done = True
            if accounts.wants(account, accounts.PLAN_STATE):
                done = expired(account, plan=plan, until=until)
            done = plan_end_to_admins(db, account, plan=plan,
                                      until=until) and done
            if done:
                accounts.mark_plan_notice(db, account["_id"],
                                          accounts.EXPIRED, until)
        return

    left = until - now
    if left <= timedelta(days=WARN_DAYS) and marks.get(accounts.EXPIRING) != until:
        # Redondeado hacia arriba: a quien le quedan unas horas se le dice que
        # le queda un día, no cero.
        days = max(1, -(-left.days * 86400 + left.seconds) // 86400)
        if expiring(account, plan=plan, until=until, days=days):
            accounts.mark_plan_notice(db, account["_id"], accounts.EXPIRING,
                                      until)


# ------------------------------------------------------ cambiar el correo

def email_change_code(account, *, code: str, to: str, minutes: int) -> bool:
    """El código que prueba que la dirección nueva existe y es suya.

    Va a la dirección **nueva**, que es de lo que se trata. Se manda aunque el
    dueño de la cuenta no vuelva a escribir: si nadie lo usa, no pasa nada y la
    cuenta se queda donde estaba.
    """
    return deliver(
        account, to=to, purpose=mail_log.EMAIL_CHANGE_CODE,
        subject=t("mail_email_code_subject", code=code),
        heading=t("mail_email_code_heading"),
        paragraphs=[t("mail_email_code_body")],
        code=code,
        foot=t("mail_email_code_expiry_one") if minutes == 1
        else t("mail_email_code_expiry", minutes=minutes))


def reply_to_code(account, *, code: str, to: str, minutes: int) -> bool:
    """El código que prueba que el «Responder a» es de quien lo escribió.

    Va a esa dirección, como el de cambiar el correo, y sin interruptor: si
    nadie lo usa, el «Responder a» se queda como estaba.
    """
    return deliver(
        account, to=to, purpose=mail_log.REPLY_TO_CODE,
        subject=t("mail_reply_code_subject", code=code),
        heading=t("mail_reply_code_heading"),
        paragraphs=[t("mail_reply_code_body", company=account.get("company_name", ""))],
        code=code,
        foot=t("mail_email_code_expiry_one") if minutes == 1
        else t("mail_email_code_expiry", minutes=minutes))


def email_changed(account, *, old: str, new: str) -> bool:
    """El aviso a la dirección **vieja** de que la cuenta se mudó.

    Es la alarma, y por eso no tiene interruptor: si alguien entró a una sesión
    abierta y se llevó la cuenta a su buzón, este mensaje es lo único que entera
    al dueño mientras todavía puede reclamar.

    No lleva ningún enlace que sirva para entrar ni para deshacerlo: quien lo
    recibe ya no controla esa cuenta, y un enlace en ese correo sería una puerta
    en la dirección equivocada. Lleva a dónde escribir.
    """
    return deliver(
        account, to=old, purpose=mail_log.EMAIL_CHANGED,
        subject=t("mail_email_changed_subject"),
        heading=t("mail_email_changed_heading"),
        paragraphs=[t("mail_email_changed_body", new=new),
                    t("mail_email_changed_write",
                      email=Config.SYSTEM_FROM_EMAIL)])


# --------------------------------------------------- el estado de la cuenta

def opened(account) -> bool:
    """Que su cuenta quedó abierta después de la demostración. No se puede
    apagar: pasa una vez y es la respuesta a la única espera que le pedimos.

    El botón va a Contactos y no a Estadísticas, que sin un solo envío es un
    cuadro vacío: lo primero que se hace con la cuenta abierta es subir la
    lista.
    """
    return deliver(
        account, purpose=mail_log.OPENED,
        subject=t("mail_opened_subject"),
        heading=t("mail_opened_heading"),
        paragraphs=[t("mail_opened_body")],
        button={"href": f"{Config.APP_BASE_URL}{url_for('contacts.index')}",
                "label": t("mail_opened_button")})


def suspended(account) -> bool:
    """Que la cuenta quedó suspendida.

    **No lleva el motivo que escribió el administrador.** Ese motivo se redacta
    para el registro interno y puede ser corto y duro; aquí va lo que la persona
    necesita: qué significa, que no se borró nada y a dónde escribir.

    Tampoco se puede apagar, y no por castigo: quien está suspendido no puede
    entrar a cambiar sus preferencias, así que un interruptor no le serviría.
    """
    return deliver(
        account, purpose=mail_log.SUSPENDED,
        subject=t("mail_suspended_subject"),
        heading=t("mail_suspended_heading"),
        paragraphs=[t("mail_suspended_body"),
                    t("mail_suspended_write", email=Config.SYSTEM_FROM_EMAIL)])


def limited(account, *, reason: str) -> bool:
    """Que la cuenta quedó limitada: entra y prepara, pero no envía.

    Sin interruptor, como la suspensión: cambia lo que puede hacer. Lleva el
    motivo de la lista (no la nota del administrador, que es para el registro)
    y el enlace a donde se arregla.
    """
    return deliver(
        account, purpose=mail_log.LIMITED,
        subject=t("mail_limited_subject"),
        heading=t("mail_limited_heading"),
        paragraphs=[t("mail_limited_body_" + reason), t("mail_limited_kept")],
        button={"href": verifications_url(), "label": t("mail_limited_button")})


def doc_rejected(account, *, kind: str, reason: str) -> bool:
    """Que un documento de verificación no sirvió, con el motivo, para que suba
    otro. Sin interruptor: si no se entera, no puede arreglarlo."""
    return deliver(
        account, purpose=mail_log.DOC_REJECTED,
        subject=t("mail_doc_rejected_subject"),
        heading=t("mail_doc_rejected_heading", what=t("verify_what_" + kind)),
        paragraphs=[t("mail_doc_rejected_body", reason=reason),
                    t("mail_doc_rejected_again")],
        button={"href": verifications_url(),
                "label": t("mail_doc_rejected_button")})


def verifications_url() -> str:
    return (f"{Config.APP_BASE_URL}"
            f"{url_for('auth.settings', section='account')}#verificaciones")


def reinstated(account) -> bool:
    return deliver(
        account, purpose=mail_log.REINSTATED,
        subject=t("mail_reinstated_subject"),
        heading=t("mail_reinstated_heading"),
        paragraphs=[t("mail_reinstated_body")],
        button={"href": panel_url(), "label": t("mail_reinstated_button")})


# ------------------------------------------------------------- para nosotros

def admins_who_want(db, notice: str):
    """Las cuentas de administrador que todavía quieren ese aviso.

    Se buscan por su índice de rol. **Estos también tienen interruptor**, en su
    propia Configuración: son avisos de lo que hacen los clientes, y con varios
    clientes activos son varios correos al día. El que no está escrito vale
    «sí», como en las cuentas de los clientes.
    """
    return [admin for admin in db.accounts.find({"role": accounts.ADMIN})
            if accounts.wants(admin, notice)]


def about(client) -> str:
    """Cómo se nombra a un cliente en estos avisos."""
    return client.get("company_name") or client.get("email", "")


def file_of(client) -> str:
    return (f"{Config.APP_BASE_URL}"
            f"{url_for('admin.account_page', raw=str(client['_id']))}")


def signup_to_admins(db, client) -> bool:
    """Avisarle a quien administra que se registró una cuenta nueva.

    Al confirmar el correo y no al escribir el formulario: hasta ese momento no
    hay cuenta que dure —lo que no se confirma se borra a las 24 horas— y
    avisar de cada intento sería avisar de cada dirección escrita mal.
    """
    todos = admins_who_want(db, accounts.ADMIN_SIGNUP)
    ok = True
    for admin in todos:
        ok = deliver(
            admin, purpose=mail_log.ADMIN_SIGNUP,
            subject=t("mail_admin_signup_subject", company=about(client)),
            heading=t("mail_admin_signup_heading", company=about(client)),
            paragraphs=[t("mail_admin_signup_body", company=about(client),
                          email=client.get("email", ""),
                          name=client.get("contact_name", ""))],
            button={"href": file_of(client),
                    "label": t("mail_admin_signup_button")},
            foot=switch_off_hint()) and ok
    return ok


def demo_to_admins(db, client) -> bool:
    """Avisarle a quien administra que una cuenta pidió la demostración.

    Lleva lo que hace falta para escribirle y preparar la llamada: el teléfono
    personal, la identificación y las dos respuestas (a qué se dedica y para qué
    usará Sobreala). Sin esto, enterarse de que alguien espera obliga a entrar a
    mirar.
    """
    todos = admins_who_want(db, accounts.ADMIN_DEMO)
    ok = True
    for admin in todos:
        ok = deliver(
            admin, purpose=mail_log.ADMIN_DEMO,
            subject=t("mail_admin_demo_subject", company=about(client)),
            heading=t("mail_admin_demo_heading", company=about(client)),
            paragraphs=[t("mail_admin_demo_body", company=about(client),
                          name=client.get("contact_name", ""),
                          email=client.get("email", "")),
                        t("mail_admin_demo_data",
                          phone=client.get("phone", ""),
                          tax_id=accounts.tax_id_of(client)),
                        t("mail_admin_demo_business",
                          answer=client.get("demo_business", "")),
                        t("mail_admin_demo_purpose",
                          answer=client.get("demo_purpose", ""))],
            button={"href": file_of(client),
                    "label": t("mail_admin_demo_button")},
            foot=switch_off_hint()) and ok
    return ok


def plan_end_to_admins(db, client, *, plan: str, until) -> bool:
    """Avisarle a quien administra que a un cliente se le venció el plan.

    Con el mismo límite que el aviso al cliente y por la misma razón: **esto se
    mira cuando el cliente entra al panel**, así que de quien no vuelve a
    entrar no se entera nadie. El día que exista el proceso en segundo plano,
    es la misma llamada en otro sitio.
    """
    todos = admins_who_want(db, accounts.ADMIN_PLAN_END)
    ok = True
    for admin in todos:
        ok = deliver(
            admin, purpose=mail_log.ADMIN_PLAN_END,
            subject=t("mail_admin_plan_end_subject", company=about(client)),
            heading=t("mail_admin_plan_end_heading", company=about(client)),
            paragraphs=[t("mail_admin_plan_end_body", company=about(client),
                          plan=plan_name(plan), until=on_date(until, clock.for_account(admin))),
                        t("mail_admin_plan_end_kept")],
            button={"href": file_of(client),
                    "label": t("mail_admin_plan_end_button")},
            foot=switch_off_hint()) and ok
    return ok


def payment_to_admins(db, client, *, plan: str) -> int:
    """Avisarle a quien administra que alguien pagó un plan.

    Va a todas las cuentas con el rol que lo quieran. Ya no hay nada que hacer
    después: pagar abre la cuenta y deja enviar, sin esperar a nadie. Es para
    enterarse sin tener que entrar a mirar.
    """
    ficha = file_of(client)
    company = about(client)
    sent = 0
    for admin in admins_who_want(db, accounts.ADMIN_PAYMENT):
        if deliver(
                admin, purpose=mail_log.ADMIN_PAYMENT,
                subject=t("mail_admin_payment_subject", company=company,
                          plan=plan_name(plan)),
                heading=t("mail_admin_payment_heading", company=company),
                paragraphs=[t("mail_admin_payment_body", company=company,
                              email=client.get("email", ""),
                              plan=plan_name(plan))],
                button={"href": ficha, "label": t("mail_admin_payment_button")},
                foot=switch_off_hint()):
            sent += 1
    return sent
