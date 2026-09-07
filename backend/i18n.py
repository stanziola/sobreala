"""Every line of Spanish the client sees, in one file.

Project convention: code and database fields in English, interface in Spanish,
and the interface strings gathered here instead of scattered through the
templates, so they can be reworded without touching any markup.
"""

from __future__ import annotations

TEXTS = {
    # --- shared ------------------------------------------------------------
    "brand": "Panamails",
    "nav_panel": "Panel",
    "nav_logout": "Cerrar sesión",
    "back_to_site": "Volver al sitio",

    # --- registration ------------------------------------------------------
    "register_title": "Crea tu cuenta",
    "register_lead": "Con tu cuenta puedes preparar tus contactos y armar campañas. "
                     "Para enviar de verdad hablamos antes contigo.",
    "register_company": "Nombre de tu negocio u organización",
    "register_contact": "Tu nombre",
    "register_email": "Correo electrónico",
    "register_phone": "Teléfono (opcional)",
    "register_password": "Contraseña",
    "register_password_hint": "Al menos 10 caracteres.",
    "register_submit": "Crear cuenta",
    "register_have_account": "¿Ya tienes cuenta?",
    "register_login_link": "Entra aquí",

    # --- "check your inbox" ------------------------------------------------
    "sent_title": "Revisa tu correo",
    "sent_lead": "Te enviamos un enlace para confirmar tu dirección. "
                 "Vence en {hours} horas.",
    "sent_hint": "Si no lo ves, mira en la carpeta de spam.",
    "sent_resend": "Enviar otro enlace",

    # --- confirmation ------------------------------------------------------
    "confirm_ok_title": "Listo, tu correo quedó confirmado",
    "confirm_ok_lead": "Ya puedes entrar a tu cuenta.",
    "confirm_already_title": "Este correo ya estaba confirmado",
    "confirm_already_lead": "No hace falta que hagas nada más.",
    "confirm_expired_title": "El enlace venció",
    "confirm_expired_lead": "Los enlaces de confirmación duran {hours} horas. "
                            "Pide uno nuevo y te lo enviamos al momento.",
    "confirm_unknown_title": "Este enlace no sirve",
    "confirm_unknown_lead": "Puede que ya lo hayas usado o que se haya copiado "
                            "incompleto. Pide uno nuevo desde aquí.",
    "confirm_go_login": "Entrar",

    # --- resend ------------------------------------------------------------
    "resend_title": "Enviar otro enlace de confirmación",
    "resend_lead": "Escribe tu correo y te mandamos uno nuevo.",
    "resend_submit": "Enviar enlace",

    # --- login -------------------------------------------------------------
    "login_title": "Entra a tu cuenta",
    "login_email": "Correo electrónico",
    "login_password": "Contraseña",
    "login_submit": "Entrar",
    "login_no_account": "¿Todavía no tienes cuenta?",
    "login_register_link": "Créala aquí",

    # --- panel -------------------------------------------------------------
    "panel_title": "Tu panel",
    "panel_greeting": "Hola, {name}",
    "panel_building": "Estamos construyendo el panel. Por ahora solo puedes "
                      "entrar y salir; pronto podrás subir tus contactos.",
    "panel_unconfirmed": "Todavía no confirmas tu correo. Revisa tu bandeja o "
                         "pide otro enlace.",
    "panel_unconfirmed_action": "Pedir otro enlace",
    "panel_status_label": "Estado de tu cuenta",
    "panel_status_registered": "Registrada. Cuando quieras enviar, escríbenos y "
                               "revisamos tu caso.",
    "panel_status_approved": "Aprobada. Ya puedes contratar un plan.",
    "panel_status_active": "Activa.",
    "panel_status_suspended": "Suspendida. Escríbenos para revisarla.",

    # --- errors ------------------------------------------------------------
    "error_required": "Completa este campo.",
    "error_email_invalid": "Ese correo no parece válido.",
    "error_password_short": "La contraseña debe tener al menos 10 caracteres.",
    "error_password_long": "Esa contraseña es demasiado larga. Usa uno más corto.",
    "error_login_failed": "El correo o la contraseña no coinciden.",
    "error_csrf": "El formulario venció. Vuelve a intentarlo.",
    "error_too_many": "Demasiados intentos. Espera unos minutos y vuelve a probar.",

    # --- error pages -------------------------------------------------------
    # Shown instead of the server's own blank error page. The technical detail
    # stays in the platform log; the visitor gets something they can act on.
    "error_db_title": "El servicio no está disponible",
    "error_db_lead": "No logramos conectar con la base de datos. Es un problema "
                     "temporal de nuestro lado: no tiene que ver con tu cuenta "
                     "ni con tu conexión, y no se perdió nada de lo que ya "
                     "tenías guardado.",
    "error_unknown_title": "Algo salió mal",
    "error_unknown_lead": "Tuvimos un problema inesperado al procesar lo que "
                          "pediste. Ya quedó anotado de nuestro lado.",
    "error_retry": "Vuelve a intentarlo en unos minutos. Si sigue pasando, "
                   "escríbenos y lo revisamos.",

    # --- emails ------------------------------------------------------------
    "mail_confirm_subject": "Confirma tu correo en Panamails",
    "mail_confirm_heading": "Confirma tu correo",
    "mail_confirm_body": "Gracias por crear tu cuenta en Panamails. Pulsa el "
                         "botón para confirmar que esta dirección es tuya.",
    "mail_confirm_button": "Confirmar mi correo",
    "mail_confirm_expiry": "El enlace vence en {hours} horas.",
    "mail_confirm_ignore": "Si no creaste ninguna cuenta, puedes ignorar este "
                           "mensaje: no se hará nada.",
    "mail_confirm_fallback": "Si el botón no funciona, copia esta dirección en "
                             "tu navegador:",

    # Sent when someone tries to register with an address that already has an
    # account. The screen must not reveal this, so the owner is told by email.
    "mail_exists_subject": "Alguien intentó crear una cuenta con tu correo",
    "mail_exists_heading": "Ya tienes una cuenta",
    "mail_exists_body": "Alguien intentó registrarse en Panamails con esta "
                        "dirección, que ya tiene una cuenta. Si fuiste tú, "
                        "simplemente entra con tu contraseña.",
    "mail_exists_button": "Entrar a mi cuenta",
    "mail_exists_ignore": "Si no fuiste tú, no tienes que hacer nada. Tu cuenta "
                          "sigue segura y nadie ha entrado.",
}


def t(key: str, **kwargs) -> str:
    text = TEXTS[key]
    return text.format(**kwargs) if kwargs else text
