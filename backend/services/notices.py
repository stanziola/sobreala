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


def renewal_on(account, *, plan: str, cycle: str, when) -> bool:
    """Que la renovación automática quedó encendida: cuándo cobra la próxima y
    cómo se cancela. Con el interruptor de «Pagos y plan»."""
    if not accounts.wants(account, accounts.BILLING):
        return False
    return deliver(
        account, purpose=mail_log.RENEWAL,
        subject=t("mail_renewal_on_subject"),
        heading=t("mail_renewal_on_heading"),
        paragraphs=[t("mail_renewal_on_body", plan=plan_name(plan),
                      cycle=t("renewal_every_" + cycle),
                      amount=plans.amount(plan, cycle),
                      when=on_date(when, clock.for_account(account))),
                    t("mail_renewal_cancel")],
        button={"href": billing_url(), "label": t("mail_renewal_button")},
        foot=switch_off_hint())


def renewal_off(account) -> bool:
    """Que se canceló la renovación automática. El plan sigue hasta su fecha."""
    if not accounts.wants(account, accounts.BILLING):
        return False
    until = accounts.plan_until(account)
    return deliver(
        account, purpose=mail_log.RENEWAL,
        subject=t("mail_renewal_off_subject"),
        heading=t("mail_renewal_off_heading"),
        paragraphs=[t("mail_renewal_off_body")]
        + ([t("mail_renewal_off_until", until=on_date(until, clock.for_account(account)))]
           if until else []),
        button={"href": billing_url(), "label": t("mail_renewal_button")},
        foot=switch_off_hint())


def renewal_failed(account) -> bool:
    """Que PayPal no pudo cobrar la renovación. Sin interruptor: si no se entera,
    el plan se vence sin que lo sepa."""
    return deliver(
        account, purpose=mail_log.RENEWAL,
        subject=t("mail_renewal_failed_subject"),
        heading=t("mail_renewal_failed_heading"),
        paragraphs=[t("mail_renewal_failed_body"), t("mail_renewal_failed_what")],
        button={"href": billing_url(), "label": t("mail_renewal_button")})


def billing_url() -> str:
    return f"{Config.APP_BASE_URL}{url_for('auth.settings', section='billing')}"


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


def paused(account, *, reason: str, note: str) -> bool:
    """Que el panel pausó sus envíos solo, por rebotes o por quejas.

    Sin interruptor, como el límite: cambia lo que puede hacer. Lleva las cifras
    que lo dispararon, qué hacer con su lista y a quién escribir, porque la
    pausa solo la quita el administrador.
    """
    return deliver(
        account, purpose=mail_log.PAUSED,
        subject=t("mail_paused_subject"),
        heading=t("mail_paused_heading"),
        paragraphs=[t("mail_paused_body_" + reason, note=note),
                    t("mail_paused_fix_" + reason),
                    t("mail_paused_write", email=Config.SYSTEM_FROM_EMAIL),
                    t("mail_limited_kept")])


def test_address(account, *, to: str, link: str, days: int) -> bool:
    """El enlace que confirma una dirección de prueba de la demostración. Va a
    esa dirección, que puede no ser la de la cuenta, y sin interruptor."""
    company = account.get("company_name", "")
    return deliver(
        account, to=to, purpose=mail_log.TEST_ADDRESS,
        subject=t("mail_test_address_subject", company=company),
        heading=t("mail_test_address_heading"),
        paragraphs=[t("mail_test_address_body", company=company),
                    t("mail_test_address_ignore")],
        button={"href": link, "label": t("mail_test_address_button")},
        foot=t("mail_test_address_expiry", days=days))


def verification_result(account, *, results: dict) -> bool:
    """El resultado de las verificaciones, que manda el administrador cuando
    quiere. Sin interruptor: cambia lo que la cuenta puede hacer.

    Una línea por cosa (verificada, rechazada con su motivo, o todavía sin
    resultado). Con algún rechazo pide volver a enviar ese documento y dice que
    sin eso no se puede enviar; con las dos verificadas, lo confirma.
    """
    lines = []
    for kind, one in results.items():
        name = t("verify_name_" + kind)
        if one["status"] == accounts.VERIFIED:
            lines.append(t("mail_result_verified", what=name))
        elif one["status"] == accounts.REJECTED:
            lines.append(t("mail_result_rejected", what=name,
                           reason=one.get("reason", "")))
        else:
            lines.append(t("mail_result_pending", what=name))
    rejected = any(one["status"] == accounts.REJECTED for one in results.values())
    everything = all(one["status"] == accounts.VERIFIED for one in results.values())
    closing = (t("mail_result_again") if rejected
               else t("mail_result_done") if everything
               else t("mail_result_waiting"))
    button = ({"href": verifications_url(), "label": t("mail_result_button")}
              if rejected else {"href": panel_url(), "label": t("mail_reinstated_button")}
              if everything else None)
    return deliver(
        account, purpose=mail_log.VERIFICATION_RESULT,
        subject=t("mail_result_subject"),
        heading=t("mail_result_heading"),
        paragraphs=lines + [closing],
        **({"button": button} if button else {}))


def verifications_url() -> str:
    """El formulario donde se envían los documentos."""
    return f"{Config.APP_BASE_URL}{url_for('auth.verification')}"


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
    personal y las dos respuestas (a qué se dedica y para qué
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
                        t("mail_admin_demo_data", phone=client.get("phone", "")),
                        t("mail_admin_demo_business",
                          answer=client.get("demo_business", "")),
                        t("mail_admin_demo_purpose",
                          answer=client.get("demo_purpose", "")),
                        t("mail_admin_demo_contacts", answer=t(
                            "welcome_demo_contacts_" + client["demo_contacts"])
                          if client.get("demo_contacts") else "-"),
                        t("mail_admin_demo_source", answer=t(
                            "welcome_demo_source_" + client["demo_source"])
                          if client.get("demo_source") else "-")]
                       + ([t("mail_admin_demo_website", answer=client["demo_website"])]
                          if client.get("demo_website") else []),
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


def pause_to_admins(db, client, *, reason: str, note: str) -> int:
    """Avisarle a quien administra que el panel pausó a un cliente solo.

    Es lo único de estos avisos que pide hacer algo: la pausa solo la quita el
    administrador, desde la ficha, después de hablar con el cliente.
    """
    company = about(client)
    sent = 0
    for admin in admins_who_want(db, accounts.ADMIN_PAUSE):
        if deliver(
                admin, purpose=mail_log.ADMIN_PAUSE,
                subject=t("mail_admin_pause_subject", company=company),
                heading=t("mail_admin_pause_heading", company=company),
                paragraphs=[t("mail_admin_pause_body_" + reason, company=company,
                              note=note),
                            t("mail_admin_pause_lift")],
                button={"href": file_of(client) + "#limite",
                        "label": t("mail_admin_pause_button")},
                foot=switch_off_hint()):
            sent += 1
    return sent


# ------------------------------------------------------ eliminar la cuenta
#
# Octubre de 2026. El código, para quien no tiene contraseña; el aviso de que se
# eliminó, a la dirección que tenía (la cuenta ya no existe, pero el mensaje es
# lo único que le queda de que pasó); y el aviso a quien administra, que va con
# el interruptor de los registros.

def erase_code(account, code: str) -> bool:
    return deliver(account, purpose=mail_log.ERASE_CODE,
                   subject=t("mail_erase_code_subject"),
                   heading=t("mail_erase_code_heading"),
                   paragraphs=[t("mail_erase_code_body")], code=code)


def erased(account) -> bool:
    return deliver(account, purpose=mail_log.ERASED,
                   subject=t("mail_erased_subject"),
                   heading=t("mail_erased_heading"),
                   paragraphs=[t("mail_erased_body", company=about(account))])


def erased_to_admins(db, client) -> int:
    sent = 0
    for admin in admins_who_want(db, accounts.ADMIN_SIGNUP):
        if deliver(admin, purpose=mail_log.ADMIN_ERASED,
                   subject=t("mail_admin_erased_subject", company=about(client)),
                   heading=t("mail_admin_erased_heading", company=about(client)),
                   paragraphs=[t("mail_admin_erased_body", company=about(client),
                                 email=client.get("email", ""))],
                   foot=switch_off_hint()):
            sent += 1
    return sent


def keys_url() -> str:
    return f"{Config.APP_BASE_URL}{url_for('developers.keys')}"


# ------------------------------------------------------------- la API
#
# Octubre de 2026. **De seguridad, sin interruptor**, como el de un dispositivo
# nuevo: una llave abre la cuenta sin contraseña, y es justo lo primero que haría
# alguien que entró sin permiso.

def api_access_code(account, code: str) -> bool:
    """El código para crear una llave o un aviso, a quien no tiene contraseña."""
    return deliver(account, purpose=mail_log.API_CODE,
                   subject=t("mail_api_code_subject"),
                   heading=t("mail_api_code_heading"),
                   paragraphs=[t("mail_api_code_body")], code=code)


def api_key_created(account, *, found, ip: str) -> bool:
    from models import api_key as api_keys

    mode = t("api_keys_mode_" + found.get("mode", api_keys.LIVE))
    return deliver(account, purpose=mail_log.API_KEY,
                   subject=t("mail_api_key_subject"),
                   heading=t("mail_api_key_heading"),
                   paragraphs=[t("mail_api_key_body", name=found.get("name", ""),
                                 mode=mode, ip=ip or "-"),
                               t("mail_api_key_scopes", scopes=", ".join(
                                   t("api_scope_" + one.replace(":", "_"))
                                   for one in found.get("scopes") or [])),
                               t("mail_api_key_not_you")],
                   button={"href": keys_url(), "label": t("mail_api_key_button")})


def api_key_revoked(account, *, name: str, reason: str = "") -> bool:
    paragraphs = [t("mail_api_revoked_body", name=name)]
    if reason:
        paragraphs.append(reason)
    return deliver(account, purpose=mail_log.API_KEY,
                   subject=t("mail_api_revoked_subject"),
                   heading=t("mail_api_revoked_heading"),
                   paragraphs=paragraphs,
                   button={"href": keys_url(), "label": t("mail_api_key_button")})


def api_key_exposed(account, *, name: str) -> bool:
    """Que se revocó sola porque llegó en la dirección de una petición, donde
    queda escrita en registros ajenos."""
    return deliver(account, purpose=mail_log.API_KEY,
                   subject=t("mail_api_exposed_subject"),
                   heading=t("mail_api_exposed_heading"),
                   paragraphs=[t("mail_api_exposed_body", name=name),
                               t("mail_api_exposed_fix")],
                   button={"href": keys_url(), "label": t("mail_api_key_button")})


# ------------------------------------------------------------ los avisos a su sistema

def webhooks_url() -> str:
    return f"{Config.APP_BASE_URL}{url_for('developers.webhooks_list')}"


def webhook_added(account, *, host: str, ip: str) -> bool:
    """Que se agregó (o cambió) un destino que manda los datos de la cuenta a
    un servidor. De seguridad: no se apaga."""
    return deliver(account, purpose=mail_log.WEBHOOK,
                   subject=t("mail_webhook_added_subject"),
                   heading=t("mail_webhook_added_heading"),
                   paragraphs=[t("mail_webhook_added_body", host=host, ip=ip or "-"),
                               t("mail_api_key_not_you")],
                   button={"href": webhooks_url(), "label": t("mail_webhook_button")})


def webhook_disabled(account, *, host: str) -> bool:
    """Que se apagó un destino porque llevaba 72 horas fallando."""
    return deliver(account, purpose=mail_log.WEBHOOK,
                   subject=t("mail_webhook_off_subject"),
                   heading=t("mail_webhook_off_heading"),
                   paragraphs=[t("mail_webhook_off_body", host=host),
                               t("mail_webhook_off_fix")],
                   button={"href": webhooks_url(), "label": t("mail_webhook_button")})
