"""Los avisos de la cuenta: el plan, la habilitación de envío y la suspensión.

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
from i18n import t
from models import account as accounts
from models import mail_log
from services import mailer, plans

# Con cuántos días de anticipación se avisa de un vencimiento.
WARN_DAYS = 7
# Y hasta cuándo tiene sentido avisar de uno que ya pasó. Sin esto, una cuenta
# de prueba de hace medio año recibiría un aviso de algo viejísimo la primera
# vez que alguien entre.
STALE_DAYS = 30

MONTHS = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
          "agosto", "septiembre", "octubre", "noviembre", "diciembre")


def on_date(when) -> str:
    """La fecha como la escribiría una persona.

    A mano y no con `strftime`, que da el mes en el idioma del servidor: en
    Railway saldría «September» en un correo en español.
    """
    return f"{when.day} de {MONTHS[when.month - 1]} de {when.year}"


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

def paid(account, *, plan: str, until, renewed: bool) -> bool:
    """El comprobante de que su plan quedó activo.

    Renovar y contratar no dicen lo mismo: al renovar lo importante es que los
    días que quedaban no se pierden, y al contratar, que ya tiene el plan.
    """
    if not accounts.wants(account, accounts.BILLING):
        return False

    name = plan_name(plan)
    which = "renewed" if renewed else "started"
    paragraphs = [t(f"mail_plan_{which}_body", plan=name),
                  t("mail_plan_until", until=on_date(until))]
    note = None
    if not accounts.can_send(account):
        # Lo que nadie adivina: pagar no habilita el envío, eso es la otra
        # puerta. Mejor decirlo aquí que en el momento de intentarlo.
        note = {"title": t("mail_plan_note_title"),
                "text": t("mail_plan_note_text")}
    return deliver(
        account, purpose=mail_log.PLAN_PAID,
        subject=t(f"mail_plan_{which}_subject", plan=name),
        heading=t(f"mail_plan_{which}_heading", plan=name),
        paragraphs=paragraphs,
        button={"href": panel_url(), "label": t("mail_plan_button")},
        note=note, foot=switch_off_hint())


def expiring(account, *, plan: str, until, days: int) -> bool:
    if not accounts.wants(account, accounts.PLAN_STATE):
        return False
    name = plan_name(plan)
    return deliver(
        account, purpose=mail_log.PLAN_EXPIRING,
        subject=t("mail_plan_expiring_subject", plan=name,
                  until=on_date(until)),
        heading=t("mail_plan_expiring_heading", days=days),
        paragraphs=[t("mail_plan_expiring_body", plan=name,
                      until=on_date(until))],
        button={"href": f"{Config.APP_BASE_URL}"
                        f"{url_for('auth.checkout', plan=plan)}",
                "label": t("mail_plan_expiring_button")},
        foot=switch_off_hint())


def expired(account, *, plan: str, until) -> bool:
    if not accounts.wants(account, accounts.PLAN_STATE):
        return False
    name = plan_name(plan)
    return deliver(
        account, purpose=mail_log.PLAN_EXPIRED,
        subject=t("mail_plan_expired_subject", plan=name),
        heading=t("mail_plan_expired_heading", plan=name),
        paragraphs=[t("mail_plan_expired_body", until=on_date(until)),
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
        if marks.get(accounts.EXPIRED) != until and expired(
                account, plan=plan, until=until):
            accounts.mark_plan_notice(db, account["_id"], accounts.EXPIRED,
                                      until)
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

def sending_cleared(account) -> bool:
    """Que ya puede enviar. No se puede apagar: pasa una vez y es la respuesta
    a la única espera que le pedimos a un cliente."""
    return deliver(
        account, purpose=mail_log.SENDING_CLEARED,
        subject=t("mail_cleared_subject"),
        heading=t("mail_cleared_heading"),
        paragraphs=[t("mail_cleared_body")],
        button={"href": panel_url(), "label": t("mail_cleared_button")},
        note={"title": t("mail_cleared_note_title"),
              "text": t("mail_cleared_note_text")})


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


def reinstated(account) -> bool:
    return deliver(
        account, purpose=mail_log.REINSTATED,
        subject=t("mail_reinstated_subject"),
        heading=t("mail_reinstated_heading"),
        paragraphs=[t("mail_reinstated_body")],
        button={"href": panel_url(), "label": t("mail_reinstated_button")})


# ------------------------------------------------------------- para nosotros

def payment_to_admins(db, client, *, plan: str) -> int:
    """Avisarle a quien administra que alguien pagó y espera habilitación.

    Va a todas las cuentas con el rol, buscadas por su índice. Sin esto, para
    enterarte de que una cooperativa pagó y está esperando hay que entrar a
    mirar, y quien espera es un cliente que ya pagó.

    No pasa por Notificaciones: esa pantalla es de los clientes, y una cuenta de
    administrador no la tiene.
    """
    ficha = (f"{Config.APP_BASE_URL}"
             f"{url_for('admin.account_page', raw=str(client['_id']))}")
    company = client.get("company_name") or client.get("email", "")
    waiting = not accounts.can_send(client)
    sent = 0
    for admin in db.accounts.find({"role": accounts.ADMIN}):
        if deliver(
                admin, purpose=mail_log.ADMIN_PAYMENT,
                subject=t("mail_admin_payment_subject", company=company,
                          plan=plan_name(plan)),
                heading=t("mail_admin_payment_heading", company=company),
                paragraphs=[t("mail_admin_payment_body", company=company,
                              email=client.get("email", ""),
                              plan=plan_name(plan)),
                            t("mail_admin_payment_waiting" if waiting
                              else "mail_admin_payment_cleared")],
                button={"href": ficha, "label": t("mail_admin_payment_button")}):
            sent += 1
    return sent
