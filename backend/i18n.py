"""Every line of Spanish the client sees, in one file.

Project convention: code and database fields in English, interface in Spanish,
and the interface strings gathered here instead of scattered through the
templates, so they can be reworded without touching any markup.
"""

from __future__ import annotations

TEXTS = {
    # --- shared ------------------------------------------------------------
    "brand": "Panamails",
    "nav_panel": "Estadísticas",
    "nav_logout": "Cerrar sesión",
    # Encima de salir. Lleva a la lista de las cuentas que este navegador tiene
    # abiertas a la vez, para saltar entre ellas sin escribir nada.
    "nav_switch": "Cambiar de cuenta",
    "back_to_site": "Volver al sitio",

    # --- the bar menu ------------------------------------------------------
    # Two faces of the same control: three lines before signing in, the name of
    # the company after. What hangs from it is the same list either way, minus
    # the entries that need an account.
    "menu_options": "Opciones",
    "menu_account": "Mi cuenta",
    "menu_settings": "Configuración",
    "menu_theme": "Modo oscuro",
    "menu_theme_light": "Modo claro",
    "menu_language": "Idioma",
    "menu_language_current": "Español",
    "menu_language_soon": "Inglés (pronto)",

    # --- signing out from a link -------------------------------------------
    # Salir cierra la sesión al momento desde los dos sitios. Esta pantalla ya
    # no está en ese camino: solo la recibe una petición que el navegador dijo
    # estar adelantando por su cuenta, y a esa no la mira nadie.
    "logout_title": "¿Cerrar tu sesión?",
    "logout_lead": "Vas a salir de tu cuenta en este dispositivo.",
    "logout_submit": "Sí, cerrar mi sesión",
    "logout_cancel": "No, volver al panel",

    # --- registration ------------------------------------------------------
    "register_title": "Crea tu cuenta",
    "register_lead": "Con tu cuenta puedes preparar tus contactos y armar campañas. "
                     "Para enviar de verdad hablamos antes contigo.",
    "register_company": "Nombre de tu negocio u organización",
    "register_contact": "Tu nombre",
    "register_email": "Correo electrónico",
    "register_phone": "Teléfono (opcional)",
    "register_password": "Contraseña",
    "register_submit": "Crear cuenta",
    # Partido en tres porque dos de los pedazos son enlaces. Todo el español
    # sigue aquí; la plantilla solo los une.
    "register_legal": "Al crear tu cuenta aceptas los",
    "register_legal_terms": "términos y condiciones",
    "register_legal_join": "y la",
    "register_legal_privacy": "política de privacidad",
    "register_have_account": "¿Ya tienes cuenta?",
    "register_have_account_adding": "¿Esa cuenta ya existe?",
    "register_login_link": "Entra aquí",
    "register_adding": "Vas a crear otra cuenta. La que tienes abierta sigue "
                       "abierta, y vas a poder saltar entre las dos.",

    # --- confirmation ------------------------------------------------------
    "confirm_title": "Escribe tu código",
    "confirm_lead": "Te enviamos un código de 6 dígitos a tu correo. "
                    "Vence en {minutes} minutos.",
    "confirm_lead_one": "Te enviamos un código de 6 dígitos a tu correo. "
                        "Vence en un minuto.",
    "confirm_hint": "Si no lo ves, mira en la carpeta de spam.",
    "recover_hint": "Si no lo ves, mira en la carpeta de spam. Y si no llega, "
                    "vuelve a pedirlo revisando que sea el correo de tu cuenta.",
    "confirm_code": "Código de 6 dígitos",
    "confirm_submit": "Confirmar mi correo",
    "confirm_resend": "Pedir otro código",
    "confirm_go_back": "Volver a entrar",
    "confirm_wrong_email": "¿Escribiste mal tu correo?",
    "correct_title": "Corrige tu correo",
    "correct_lead": "Si el código va a una dirección equivocada, cámbiala aquí "
                    "y te enviamos uno nuevo a la buena.",
    "correct_submit": "Cambiar y enviar el código",
    "confirm_countdown": "Vence en {time}",
    "confirm_expired": "El código venció. Pide uno nuevo y te lo enviamos al "
                       "momento.",

    # --- resend ------------------------------------------------------------
    "resend_title": "Pedir otro código",
    "resend_lead": "Escribe tu correo y te mandamos un código nuevo.",
    "resend_submit": "Enviar código",

    # --- contraseñas -------------------------------------------------------
    # Las mismas cuatro reglas que aplica password_problem() en
    # services/security.py, que es la que manda. Estas son solo su nombre.
    "password_rules_title": "Tu contraseña necesita:",
    "password_rule_length": "Al menos {min} caracteres",
    "password_rule_upper": "Una letra mayúscula",
    "password_rule_digit": "Un número",
    "password_rule_symbol": "Un símbolo, por ejemplo . - _ ! ?",
    "password_rule_met": "cumplido",
    "password_show": "Mostrar contraseña",
    "password_hide": "Ocultar contraseña",

    # --- recover -----------------------------------------------------------
    "recover_title": "Recuperar tu cuenta",
    # "Si esa dirección tiene una cuenta" no es un rodeo: es lo que deja ser
    # claro sin decir cuáles existen, que es lo que protege la regla 7 aquí.
    "recover_lead": "Escribe el correo con el que creaste tu cuenta. Si esa "
                    "dirección tiene una cuenta, te llega un código en un "
                    "minuto.",
    "recover_lead_known": "Te enviamos un código para poner una contraseña "
                          "nueva, sin necesidad de recordar la anterior.",
    "recover_to": "El código va a {email}",
    "recover_submit": "Enviarme el código",
    "recover_code_title": "Escribe tu código",
    "recover_code_submit": "Continuar",
    "recover_new_title": "Tu nueva contraseña",
    "recover_new_lead": "Al guardarla cerramos la sesión en todos los "
                        "dispositivos y te avisamos por correo.",
    "recover_new_submit": "Guardar y entrar",
    "login_forgot": "¿Olvidaste tu contraseña?",
    "password_forgot": "¿No recuerdas tu contraseña actual?",

    # --- login -------------------------------------------------------------
    # --- la bienvenida, al confirmar el registro ---------------------------
    # «Te damos la bienvenida» y no «Bienvenido»: es la fórmula que ya usa el
    # correo de bienvenida, y no le adivina el género a nadie por su nombre.
    "welcome_tab": "Tu cuenta está lista",
    "welcome_title": "{name}, te damos la bienvenida a Panamails",
    "welcome_lead": "Tu cuenta está lista. Elige el plan que más se adapte a ti "
                    "para empezar a enviar correos.",
    "welcome_plans": "Ver planes",
    "welcome_settings": "Ir a configuración",

    # --- cambiar el correo de la cuenta ------------------------------------
    "email_change_title": "Cambiar tu correo",
    "email_change_lead": "Ahora mismo tu cuenta usa {email}. Aquí te llegan los "
                         "códigos para entrar y para recuperar tu contraseña, "
                         "así que hay que comprobar la dirección nueva.",
    "email_change_new": "Correo nuevo",
    "email_change_code_hint": "Te mandamos un código ahí para comprobar que es "
                              "tuyo. Hasta que lo escribas no cambia nada.",
    "email_change_password": "Tu contraseña",
    "email_change_submit": "Mandar el código",

    "email_code_title": "Escribe el código",
    "email_code_lead": "Te enviamos un código de 6 dígitos a {email}. Cuando lo "
                       "escribas, esa pasa a ser la dirección de tu cuenta.",
    "email_code_hint": "Si no te llega, mira en el correo no deseado. El código "
                       "es de un solo uso.",
    "email_code_other": "Usar otra dirección",
    "email_code_submit": "Cambiar mi correo",
    "error_email_same": "Esa ya es la dirección de tu cuenta.",

    # Los dos mensajes: el código va a la dirección nueva y el aviso a la vieja.
    "mail_email_code_subject": "{code} es tu código para cambiar tu correo",
    "mail_email_code_heading": "Tu código para cambiar el correo",
    "mail_email_code_body": "Alguien pidió usar esta dirección para una cuenta "
                            "de Panamails. Escribe este código en la pantalla "
                            "que lo pidió:",
    "mail_email_code_expiry": "El código vence en {minutes} minutos. Si no "
                              "fuiste tú, no hagas nada: sin el código no "
                              "cambia nada.",
    "mail_email_code_expiry_one": "El código vence en un minuto. Si no fuiste "
                                  "tú, no hagas nada: sin el código no cambia "
                                  "nada.",

    "mail_email_changed_subject": "El correo de tu cuenta de Panamails cambió",
    "mail_email_changed_heading": "Tu cuenta cambió de correo",
    "mail_email_changed_body": "De ahora en adelante tu cuenta de Panamails usa "
                               "{new}. A esta dirección ya no le va a llegar "
                               "nada.",
    "mail_email_changed_write": "Si no fuiste tú, escríbenos de inmediato a "
                                "{email}: con este mensaje en la mano podemos "
                                "devolverte la cuenta.",

    "login_title": "Entra a tu cuenta",
    "login_switched": "Cerraste tu sesión. Entra con la cuenta que quieras.",
    "login_adding": "Vas a agregar otra cuenta. La que tienes abierta sigue "
                    "abierta, y vas a poder saltar entre las dos.",

    # --- las cuentas abiertas a la vez -------------------------------------
    "accounts_title": "Tus cuentas",
    "accounts_lead": "Las que tienes abiertas en este navegador. Saltar de una "
                     "a otra no pide contraseña y no cierra ninguna.",
    "accounts_here": "Estás aquí",
    "accounts_use": "Entrar aquí",
    "accounts_drop": "Cerrar esta",
    "accounts_add": "Agregar otra cuenta",
    "accounts_full": "Caben {n} a la vez. Cierra una para poder agregar otra.",
    "accounts_back": "Volver",
    "login_email": "Correo electrónico",
    "login_password": "Contraseña",
    "login_submit": "Entrar",
    "login_remember": "Mantener mi sesión iniciada 30 días",
    "login_no_account": "¿Todavía no tienes cuenta?",
    # Estando dentro de una cuenta y agregando otra, «todavía no tienes cuenta»
    # es mentira: la tiene, lo que quiere es otra.
    "login_no_account_adding": "¿Todavía no existe esa cuenta?",
    "login_register_link": "Créala aquí",

    # --- devices -----------------------------------------------------------
    "devices_title": "Tus dispositivos",
    "devices_lead": "Donde tu cuenta está abierta ahora mismo. Si ves algo que "
                    "no reconoces, ciérralo y cambia tu contraseña.",
    # Browser and system are proper nouns; the only thing translated is how
    # they are joined.
    "device_on": "{browser} en {system}",
    "device_unknown": "Dispositivo desconocido",
    "device_here": "Este dispositivo",
    "device_seen": "Última actividad: {when}",
    "device_since": "Desde {when}",
    "device_close": "Cerrar",
    "device_close_others": "Cerrar sesión en los demás dispositivos",
    "device_alone": "Es el único dispositivo con tu cuenta abierta.",
    "when_now": "hace un momento",
    "when_minute": "hace un minuto",
    "when_minutes": "hace {n} minutos",
    "when_hour": "hace una hora",
    "when_hours": "hace {n} horas",
    "when_day": "ayer",
    "when_days": "hace {n} días",

    # --- closing a session from the notice ---------------------------------
    "close_ready_title": "¿Cerrar esa sesión?",
    "close_ready_lead": "Vamos a cerrar la sesión del dispositivo que te "
                        "avisamos por correo. Los demás siguen abiertos.",
    "close_submit": "Sí, cerrar esa sesión",
    "close_done_title": "Listo, esa sesión quedó cerrada",
    "close_done_lead": "Ese dispositivo ya no puede entrar a tu cuenta. Si no "
                       "reconociste el ingreso, cambia también tu contraseña.",
    "close_unknown_title": "Ese enlace ya no sirve",
    "close_unknown_lead": "Puede que ya lo hayas usado o que haya vencido. "
                          "Desde tu panel puedes ver y cerrar tus dispositivos "
                          "cuando quieras.",
    "close_change": "Cambiar mi contraseña",

    # --- autenticación de múltiples factores --------------------------------
    "two_step_title": "Autenticación de múltiples factores",
    "two_step_off_lead": "Añade un segundo candado a tu cuenta: además de tu "
                         "contraseña, un código que genera una app en tu "
                         "teléfono y cambia cada 30 segundos.",
    "two_step_on_lead": "Está activada. Cada vez que entres te vamos a pedir el "
                        "código de tu app, en cualquier dispositivo.",
    "two_step_step_password": "Escribe tu contraseña, para saber que eres tú.",
    "two_step_step_app": "Instala una app de códigos: Google Authenticator, "
                         "Microsoft Authenticator o la que ya uses.",
    "two_step_step_code": "Escanea el código que te vamos a enseñar y escribe "
                          "los 6 dígitos que aparezcan en la app.",
    "two_step_manual": "¿No puedes escanear? Escribe esta clave en la app:",
    "two_step_code_label": "Código de tu app",
    "two_step_why_password": "Pedimos tu contraseña para que nadie active ni "
                             "desactive esto desde una sesión que dejaste "
                             "abierta.",
    "two_step_enable": "Activar la verificación",
    "two_step_continue": "Continuar",
    "two_step_choose": "Elegir",
    "two_step_confirm": "Confirmar",
    "two_step_back": "Volver atrás",
    "two_step_to_settings": "Volver a seguridad",
    "two_step_disable": "Desactivar la verificación",
    "two_step_disable_desc": "Tu cuenta vuelve a entrar solo con la "
                             "contraseña. Los códigos de respaldo dejan de "
                             "servir.",
    "two_step_confirm_disable": "Vas a desactivar la autenticación de "
                                "múltiples factores.",
    "two_step_regenerate": "Generar códigos de respaldo nuevos",
    "two_step_regenerate_desc": "Los ocho anteriores dejan de servir al "
                                "momento. Útil si perdiste el papel donde los "
                                "apuntaste.",
    "two_step_confirm_regenerate": "Vas a generar ocho códigos de respaldo "
                                   "nuevos.",
    "two_step_recovery_left": "Te quedan {n} códigos de respaldo sin usar.",
    "two_step_expired": "Pasó demasiado tiempo desde que escribiste tu "
                        "contraseña. Vuelve a empezar.",

    # La segunda pantalla: el QR y el código que prueba que la app lo guardó.
    "two_step_scan_title": "Escanea este código",
    "two_step_scan_lead": "Ábrelo con tu app de códigos. Después escribe los "
                          "seis dígitos que te muestre, para comprobar que "
                          "quedó bien.",
    "two_step_scan_note_title": "Si ya tenías Panamails en tu app",
    "two_step_scan_note": "Cada vez que activas la verificación el código es "
                          "nuevo, así que el anterior dejó de servir. Bórralo "
                          "de tu app antes de escanear este para evitar "
                          "confusiones.",

    "two_step_codes_title": "Guarda estos códigos de respaldo",
    "two_step_codes_lead": "Sirven para entrar si pierdes el teléfono. Cada uno "
                           "vale una sola vez.",
    "two_step_codes_hint": "Solo los verás ahora: guardamos únicamente una "
                           "huella suya, así que ni nosotros podemos "
                           "enseñártelos otra vez. Apúntalos en papel o en tu "
                           "gestor de contraseñas.",
    "two_step_codes_done": "Ya los guardé",

    "two_step_code_title": "Escribe el código de tu app",
    "two_step_code_lead": "Tu cuenta tiene autenticación de múltiples "
                          "factores. Abre la app en tu teléfono y escribe el "
                          "código que muestra.",
    "two_step_submit": "Entrar",
    "two_step_lost": "No tengo mi teléfono",
    "two_step_recovery_label": "Escribe uno de tus códigos de respaldo",

    "panel_two_step_link": "Autenticación de múltiples factores",
    "panel_two_step_on": "activada",
    "panel_two_step_off": "desactivada",
    "two_step_turned_off": "Listo, la autenticación de múltiples factores "
                           "quedó desactivada.",

    # --- password ----------------------------------------------------------
    "password_title": "Cambiar tu contraseña",
    "password_lead": "Al cambiarla cerramos la sesión en los demás "
                     "dispositivos y te avisamos por correo.",
    "password_current": "Contraseña actual",
    "password_new": "Nueva contraseña",
    "password_repeat": "Repite la nueva contraseña",
    "password_submit": "Guardar la nueva contraseña",
    "password_changed_ok": "Listo, tu contraseña quedó cambiada.",
    "panel_password_link": "Cambiar mi contraseña",

    # --- settings ----------------------------------------------------------
    "settings_title": "Configuración",
    "settings_section_account": "Cuenta",
    "settings_section_security": "Seguridad",
    "settings_section_notifications": "Notificaciones",
    "settings_section_payments": "Facturación",

    "settings_account_contact": "Tu nombre",
    "settings_account_company": "Empresa u organización",
    "settings_account_email": "Correo de tu cuenta",
    "settings_account_email_pending": "Sin confirmar",
    "settings_account_email_change": "Cambiar",
    "settings_account_to_billing": "Ir a facturación",
    "settings_account_email_done": "Listo, tu correo cambió. Le avisamos a la "
                                   "dirección anterior.",
    "settings_postal": "Dirección postal",
    "settings_postal_hint": "Sale al pie de tus campañas: la ley pide la "
                            "dirección física de quien envía. Un apartado "
                            "postal sirve.",
    "settings_postal_placeholder": "Calle, ciudad, provincia",
    "settings_postal_save": "Guardar",
    "settings_postal_done": "Listo, tu dirección quedó guardada.",
    "admin_postal_missing": "Todavía no la escribió",
    "settings_postal_bad": "Escribe una dirección de entre {min} y {max} "
                           "caracteres.",
    "settings_account_status": "Estado de tu cuenta",
    # La misma palabra que la etiqueta corta de la fila; la frase larga que la
    # explica sigue siendo panel_status_*, que es la que ya se enseñaba.
    "status_short_registered": "Registrada",
    "status_short_active": "Activa",
    "status_short_suspended": "Suspendida",
    "settings_account_plan": "Tu plan",
    "settings_account_no_plan": "Sin plan contratado",
    "settings_account_no_plan_hint": "Puedes preparar tus contactos y armar "
                                     "campañas sin plan. Para enviarlas de "
                                     "verdad hace falta uno.",
    "settings_account_plans": "Ver los planes",

    "settings_security_lead": "Todo lo que decide quién puede entrar a tu "
                              "cuenta.",
    "settings_password_row": "Contraseña",
    "settings_password_desc": "Si la cambias, se cierra la sesión en los "
                              "demás dispositivos.",
    "settings_password_action": "Cambiar",
    "settings_two_step_desc": "Tipo: aplicación de códigos.",
    "settings_two_step_manage": "Administrar",

    # --- los usuarios de la cuenta -----------------------------------------
    # El dueño le da entrada a alguien de su equipo, con su propio correo y su
    # propia contraseña, y le marca lo que puede hacer.
    "users_title": "Usuarios",
    "users_lead": "Personas de tu equipo que entran a esta cuenta, cada una con "
                  "su correo y su contraseña. Tú decides lo que puede hacer "
                  "cada una.",
    "users_seats": "{used} de {seats} usuarios",
    "users_seats_full": "Tu plan no permite más. Para agregar a alguien más, "
                        "sube de plan.",
    "users_more_seats": "Ver los planes",
    "users_new": "Crear usuario",
    "users_new_title": "Crear un usuario",
    "users_edit_title": "Cambiar lo que puede hacer",
    "users_form_lead": "Le llega una invitación a su correo y ahí pone su "
                       "contraseña. Tú nunca la ves.",
    "users_name": "Nombre de la persona",
    "users_email": "Su correo",
    "users_email_hint": "Tiene que ser suyo, no el de la empresa: es a donde "
                        "llega la invitación, el aviso de un ingreso nuevo y "
                        "la recuperación de su contraseña.",
    "users_email_taken": "Ese correo ya tiene una cuenta en Panamails. Usa "
                         "otro.",
    "users_permissions": "Qué puede hacer",
    "users_permissions_hint": "Sin marcar nada, solo entra y cambia su "
                              "contraseña. Enviar correos incluye ver las "
                              "campañas.",
    "users_no_permissions": "Sin permisos",
    "users_can_stats": "Ver estadísticas",
    "users_can_stats_desc": "Las cifras de los envíos y las gráficas.",
    "users_can_campaigns": "Ver campañas",
    "users_can_campaigns_desc": "Las campañas y el detalle de cada envío, sin "
                                "poder mandar.",
    "users_can_send": "Enviar correos",
    "users_can_send_desc": "Armar campañas y mandarlas.",
    "users_can_contacts": "Modificar contactos",
    "users_can_contacts_desc": "La lista, importar, etiquetas, columnas y "
                               "supresiones.",
    "users_can_designs": "Crear o editar plantillas",
    "users_can_designs_desc": "El editor y el HTML propio.",
    "users_invite": "Invitar",
    "users_save": "Guardar",
    "users_back": "Volver a Seguridad",
    "users_edit": "Permisos",
    "users_resend": "Reenviar invitación",
    "users_enable": "Activar",
    "users_disable": "Desactivar",
    "users_delete": "Borrar",
    "users_state_active": "Activo",
    "users_state_invited": "Invitación pendiente",
    "users_state_disabled": "Desactivado",
    "users_has_two_step": "Con segundo factor",
    "users_invited_ok": "Listo, le mandamos la invitación a su correo.",
    "users_saved_ok": "Listo, guardamos sus permisos.",
    "users_no_seats": "Tu plan no permite más usuarios.",

    # La pantalla donde esa persona pone su contraseña.
    "invite_title": "Pon tu contraseña",
    "invite_lead": "{company} te dio entrada a su cuenta de Panamails. Elige "
                   "una contraseña y entras.",
    "invite_password": "Tu contraseña",
    "invite_action": "Entrar",
    "invite_gone_title": "Esta invitación ya no sirve",
    "invite_gone_lead": "Se usó o se venció. Pídele a quien te invitó que te "
                        "mande otra.",
    "invite_to_login": "Ir a entrar",
    "settings_two_step_turn_on": "Activar",

    "settings_notifications_lead": "Qué correos te mandamos. Los que avisan de "
                                   "un problema de seguridad van siempre.",

    # La misma pantalla, con la otra lista: la de quien administra habla de lo
    # que hacen los clientes, no de lo que pasa en su cuenta.
    "settings_admin_notifications_lead": "Qué te avisamos de las cuentas de tus "
                                         "clientes. Los correos que avisan de "
                                         "un problema de seguridad de tu propia "
                                         "cuenta van siempre.",
    "settings_notice_admin_payment": "Alguien pagó un plan",
    "settings_notice_admin_payment_desc": "Cuando un cliente contrata o renueva. "
                                          "Dice si queda esperando que le "
                                          "habilites el envío, que es lo único "
                                          "que espera por una persona.",
    "settings_notice_admin_signup": "Se registró una cuenta nueva",
    "settings_notice_admin_signup_desc": "Cuando alguien confirma su correo y la "
                                         "cuenta queda creada de verdad. Los "
                                         "registros a medias no avisan nada.",
    "settings_notice_admin_plan_end": "A un cliente se le venció el plan",
    "settings_notice_admin_plan_end_desc": "Se mira cuando el cliente entra a su "
                                           "panel, así que de quien no vuelve a "
                                           "entrar no se entera nadie hasta que "
                                           "exista el proceso automático.",
    "settings_fixed_codes": "Códigos de confirmación y de recuperación",
    "settings_fixed_password": "Tu contraseña cambió",
    "settings_fixed_two_step": "Se activó o se desactivó la autenticación de "
                               "múltiples factores",
    "settings_fixed_tag": "Siempre activo",
    "settings_notice_new_login": "Ingreso desde un dispositivo nuevo",
    "settings_notice_new_login_desc": "Te avisamos cuando alguien entra a tu "
                                      "cuenta desde un dispositivo que no "
                                      "habías usado.",
    "settings_notice_billing": "Pagos y plan",
    "settings_notice_billing_desc": "El comprobante cuando contratas o renuevas "
                                    "un plan.",
    "settings_notice_plan_state": "Estado de tu plan",
    "settings_notice_plan_state_desc": "Cuando está por vencerse y cuando se "
                                       "venció.",
    "settings_notice_imports": "Importación de contactos",
    "settings_notice_imports_desc": "Cuando termina de subir una lista, con "
                                    "cuántos contactos entraron y cuántos no.",
    "settings_notice_campaigns": "Envíos de campañas",
    "settings_notice_campaigns_desc": "Cuando una campaña termina de enviarse, "
                                      "o cuando se pausa sola.",
    "settings_notice_monthly": "Resumen mensual",
    "settings_notice_monthly_desc": "Una vez al mes: cuánto enviaste, cuánto "
                                    "abrieron y cuánta cuota te queda.",
    "settings_notifications_save": "Guardar",
    "settings_notifications_saved": "Listo, guardamos lo que elegiste.",

    "settings_payments_lead": "Tu plan, con qué has pagado y tus facturas. "
                              "Los planes se eligen en el sitio.",
    "billing_plan_row": "Plan",
    "billing_until": "hasta el {when}",
    "billing_methods_title": "Métodos de pago",
    "billing_used": "Lo has usado",
    "billing_paypal_used": "Has pagado con la cuenta de PayPal {who}.",
    "billing_paypal_used_plain": "Has pagado con tu cuenta de PayPal.",
    "billing_invoices_title": "Facturas",
    "billing_history_title": "Historial de compras",
    "billing_download": "Descargar factura",
    "billing_invoice_pending": "Factura en camino",
    "billing_invoices_hint": "Te avisamos por correo cuando tu factura está "
                             "lista para descargar.",
    "billing_invoices_none": "Todavía no tienes pagos.",
    "settings_payments_ready": "Disponible",
    "settings_payments_paypal": "PayPal",
    "settings_payments_paypal_desc": "Para pagar con tu cuenta de PayPal.",
    "settings_payments_card": "Tarjeta de crédito o débito",
    "settings_payments_card_desc": "Visa y Mastercard, sin necesidad de tener "
                                   "cuenta de PayPal.",
    "settings_payments_yappy": "Yappy",
    "settings_payments_yappy_desc": "Para pagar desde tu banco en Panamá, sin "
                                    "tarjeta.",
    "settings_soon_tag": "Próximamente",

    # --- pagos -------------------------------------------------------------
    "pay_checkout_title": "Contratar {plan}",
    "pay_renewing": "Ya tienes este plan hasta {when}. Lo que pagues ahora se "
                    "suma al final, no reemplaza lo que te queda.",
    "pay_back_to_plans": "Ver todos los planes",
    "pay_downgrade": "Ya tienes un plan mayor que este. Bajar de plan no se "
                     "hace desde aquí: escríbenos y lo vemos contigo, porque "
                     "hay que ajustar lo que ya pagaste.",
    "pay_choose": "Contratar un plan",
    "pay_choose_lead": "El pago se hace en la página de PayPal. Al volver, tu "
                       "cuenta queda activa al momento.",
    "pay_prices": "${month} al mes · ${year} al año, con dos meses gratis.",
    # Con qué se paga. Los tres se enseñan siempre: esconder los que faltan
    # haría que quien no tiene PayPal cerrara la página creyendo que no puede
    # pagar de ninguna forma.
    "pay_method_title": "Cómo quieres pagar",
    "pay_method_use": "Usar este",
    "pay_method_soon": "Pronto",
    "pay_method_paypal": "PayPal",
    "pay_method_paypal_desc": "Se paga en la página de PayPal, con tu cuenta. "
                              "Nosotros nunca vemos tus datos.",
    "pay_method_card": "Tarjeta de crédito o débito",
    "pay_method_card_desc": "Visa y Mastercard, sin necesidad de tener cuenta "
                            "de PayPal. Se paga en la página de Paguélofácil: "
                            "nosotros nunca vemos tu tarjeta.",
    "pay_card_ending": "terminada en {last4}",
    "pay_method_yappy": "Yappy",
    "pay_method_yappy_desc": "Desde tu banco en Panamá, sin tarjeta.",
    "pay_cycle_title": "Por cuánto tiempo",

    "pay_monthly": "Pagar un mes",
    "pay_yearly": "Pagar un año",
    "pay_talk": "Escríbenos",
    "pay_current": "Tu plan",
    "pay_until": "hasta {when}",
    "pay_compare": "La comparación completa está en el sitio:",
    "pay_history": "Tus pagos",
    "pay_cycle_monthly": "Un mes",
    "pay_cycle_yearly": "Un año",
    "pay_state_created": "Sin terminar",
    "pay_state_completed": "Pagado",
    "pay_state_failed": "No se cobró",
    "pay_done": "Listo, tu plan quedó activo.",
    "pay_needs_email": "Para contratar, confirma primero tu correo: es a donde "
                       "va el comprobante y los avisos del plan.",
    "pay_suspended": "Tu cuenta está suspendida, así que no puede contratar. "
                     "Escríbenos y lo revisamos.",
    "pay_not_ready": "El pago en línea todavía no está disponible. "
                     "Escríbenos y lo resolvemos por otra vía.",
    "pay_error_estado": "Tu cuenta todavía no puede contratar un plan. Confirma tu correo, o escríbenos si está suspendida.",
    "pay_error_plan": "Ese plan no se contrata por aquí.",
    "pay_error_paypal": "No pudimos hablar con PayPal en este momento. "
                        "Vuelve a intentarlo en unos minutos.",
    "pay_error_tarjeta": "No pudimos hablar con Paguélofácil en este momento. "
                         "Si ya pagaste, en unos minutos se activa solo; si "
                         "no, vuelve a intentarlo.",
    "pay_error_cancelado": "Cancelaste el pago. No se cobró nada.",
    "pay_error_orden": "No encontramos ese pago. Si te cobraron, escríbenos "
                       "con la fecha y lo revisamos.",
    "pay_error_cobro": "El pago no se confirmó, así que no activamos nada. Si "
                       "te cobraron, escríbenos.",
    "pay_error_monto": "El monto cobrado no coincide con el del plan, así que "
                       "no activamos nada. Escríbenos y lo revisamos.",
    "settings_payments_hint": "Panamails nunca guarda los datos de tu tarjeta: "
                              "el pago se hace en la página del proveedor.",

    # --- estadísticas ------------------------------------------------------
    # La misma pantalla para el cliente y para el administrador; lo único que
    # cambia es que él elige de qué cuenta.
    "panel_title": "Estadísticas",
    # La sigue usando la ficha del administrador, para el bloque de envíos del
    # mes que todavía no tiene datos.
    "panel_soon_tag": "Próximamente",
    "panel_greeting": "Hola, {name}",
    "admin_invoices_title": "Pagos y facturas",
    "admin_invoices_none": "Esta cuenta no tiene pagos cobrados.",
    "admin_invoice_has": "Con factura",
    "admin_invoice_file": "PDF de la factura",
    "admin_invoice_upload": "Subir factura",
    "admin_invoice_replace": "Reemplazar",
    "admin_invoice_done": "Listo, la factura quedó subida.",
    "admin_invoice_bad": "Eso no es un PDF, o pesa más de {mb} MB.",
    "admin_invoice_reason_first": "Factura subida",
    "admin_invoice_reason_again": "Factura reemplazada",
    "stats_of": "Estadísticas de {name}",
    "stats_pick": "Cuenta",
    "stats_pick_hint": "Ves lo mismo que ve esa empresa en su pantalla.",
    "stats_period": "Periodo",
    "stats_period_1h": "Última hora",
    "stats_period_hoy": "Hoy",
    "stats_period_24h": "Últimas 24 horas",
    "stats_period_7d": "Últimos 7 días",
    "stats_period_30d": "Últimos 30 días",
    "stats_period_90d": "Últimos 90 días",
    "stats_week_of": "Semana del {day}",
    "stats_campaign": "Campaña",
    "stats_all_campaigns": "Todas las campañas",
    "stats_rates_title": "Cómo le fue",
    "stats_rate_of": "{n} de {of}",
    "stats_rates_note": "Se cuentan personas: quien abre tres veces cuenta una. "
                        "Las aperturas son aproximadas (algunos buzones abren "
                        "solos los correos y otros no avisan), y «entregado» "
                        "quiere decir que el servidor de la persona lo aceptó, "
                        "no que haya llegado a su bandeja.",
    "stats_engage_title": "Aperturas y clics",
    "stats_engage_lead": "Cuántas personas abrieron tus correos y cuántas "
                         "pulsaron un enlace en el periodo que elijas. Quien "
                         "abre tres veces cuenta una.",
    "stats_tag": "Etiqueta",
    "stats_all_tags": "Todas las etiquetas",
    "stats_apply": "Ver",

    "stats_sending_title": "Envíos y rebotes",
    "stats_sending_lead": "A cuántas personas les salió un correo y a cuántas "
                          "les rebotó en el periodo que elijas.",
    "stats_sent": "Enviados",
    "stats_bounce": "Rebotes",
    "stats_delivery": "Entregados",
    "stats_complaint": "Quejas",
    "stats_open": "Aperturas",
    "stats_click": "Clics",
    # Lo que se lee cuando la gráfica sale vacía. Se dibuja igual, con sus ejes,
    # porque un cuadro vacío que se explica dice más que un hueco.
    "stats_quota_title": "Correos de este mes",
    "stats_quota_of": "{used} de {allowed} correos",
    "stats_quota_none": "Sin plan contratado: no hay correos incluidos.",
    "stats_quota_plans": "Ver los planes",
    "stats_nothing": "Todavía no se ha realizado ninguna acción sobre esto. "
                     "Aquí van a aparecer tus envíos en cuanto salga la primera "
                     "campaña.",

    "panel_unconfirmed": "Todavía no confirmas tu correo. Revisa tu bandeja o "
                         "pide otro código.",
    "panel_unconfirmed_action": "Pedir otro código",
    "panel_status_label": "Estado de tu cuenta",
    "panel_status_registered": "Registrada. Ya puedes contratar un plan; antes "
                               "de tu primera campaña revisamos tu lista "
                               "contigo.",
    "panel_status_active": "Activa.",
    "panel_status_suspended": "Suspendida. Escríbenos para revisarla.",

    # --- contacts ----------------------------------------------------------
    "contacts_title": "Contactos",
    "contacts_tab_list": "Tus contactos",
    "contacts_tab_import": "Importar",
    "contacts_tab_blocked": "Supresiones",
    "contacts_counter": "{total} de {limit} contactos",
    "contacts_counter_left": "Te quedan {n}.",
    "contacts_full": "Llegaste al límite de tu plan.",
    "contacts_counter_blocked": "{n} anulados, que no cuentan y se miran en "
                                "Supresiones.",
    "contacts_counter_blocked_one": "1 anulado, que no cuenta y se mira en "
                                    "Supresiones.",
    "contacts_export": "Exportar",
    # Se pregunta antes de descargar: el archivo trae lo que se ve en la
    # tabla, y eso hay que poder comprobarlo antes y no abriéndolo después.
    "contacts_export_title": "Exportar tus contactos",
    "contacts_export_lead": "Se descarga lo que estás viendo en la tabla, con "
                            "el buscador y el filtro que tengas puestos.",
    "contacts_export_going": "Van a salir {n} contactos.",
    "contacts_export_going_one": "Va a salir 1 contacto.",
    "contacts_export_going_none": "Con este filtro no sale ninguno.",
    "contacts_export_filter_tag": "Etiqueta: {tag}",
    "contacts_export_filter_search": "Buscando: {q}",
    "contacts_export_filter_none": "Sin filtro: salen todos tus contactos.",
    "contacts_export_columns": "Columnas: correo, nombre, etiquetas, cómo se "
                               "agregó, cuándo y si está activo o anulado.",
    "contacts_export_excel": "Se abre en Excel y lo lee nuestro propio "
                             "importador, por si quieres volver a subirlo.",
    "contacts_export_confirm": "Descargar",
    "contacts_export_back": "Volver a la lista",
    "contacts_remove_blocked": "Eliminar los anulados",
    "contacts_remove_blocked_hint": "Eliminar los anulados borra esos "
                                    "contactos y deja sus supresiones donde "
                                    "están: esas direcciones siguen sin poder "
                                    "recibir nada, y si vuelven en una "
                                    "importación vuelven marcadas.",
    "contacts_added_blocked": "Lo guardamos, pero esa dirección está anulada: "
                              "no va a recibir nada.",
    "contacts_plans": "Ver los planes",
    "contacts_empty": "Todavía no tienes contactos. Sube tu lista y empezamos.",
    "contacts_empty_search": "Ningún contacto coincide con lo que buscaste.",
    "contacts_import_action": "Importar una lista",
    "contacts_search": "Buscar por correo",
    "contacts_search_action": "Buscar",
    "contacts_all_tags": "Todas las etiquetas",
    "contacts_tag_filter": "Filtrar",
    "contacts_tag_drop": "Quitar esta etiqueta de todos",
    "contacts_tag_drop_hint": "Los contactos se quedan; solo se les quita la "
                              "etiqueta.",
    "contacts_showing": "{n} de {total}",
    "contacts_newer": "Anteriores",
    "contacts_older": "Siguientes",
    "contacts_col_email": "Correo",
    "contacts_col_name": "Nombre",
    "contacts_col_tags": "Etiquetas",
    "contacts_col_added": "Agregado",
    "contacts_delete": "Eliminar",
    "contacts_remove_title": "Eliminar contactos",
    "contacts_remove_one": "Vas a eliminar 1 contacto.",
    "contacts_remove_many": "Vas a eliminar {n} contactos.",
    "contacts_remove_keeps": "Si alguno anuló su suscripción o rebotó, eso se "
                             "queda: aunque lo vuelvas a importar, no recibirá "
                             "correos.",
    "contacts_remove_confirm_one": "Sí, eliminar 1 contacto",
    "contacts_remove_confirm_many": "Sí, eliminar {n} contactos",
    "contacts_remove_cancel": "Cancelar",
    "contacts_edit": "Editar",
    "contacts_edit_title": "Editar el contacto",
    "contacts_edit_lead": "Puedes cambiar su dirección, su nombre y sus "
                          "etiquetas. Cuándo entró y por dónde no se tocan: eso "
                          "es lo que hay que enseñar si alguien reclama.",
    "contacts_edit_submit": "Guardar",
    "contacts_history_title": "Lo que no se puede cambiar",
    "contacts_history_hint": "Cuándo entró, por dónde y qué origen se declaró. "
                             "Es lo que hay que enseñar si alguien reclama que "
                             "no dio su correo, así que no se edita.",
    "contacts_blocked_tag": "Suprimido",
    "contacts_saved": "Listo, guardamos el contacto.",

    "contacts_add_title": "Agregar manualmente",
    "contacts_add_email": "Correo",
    "contacts_add_name": "Nombre (opcional)",
    "contacts_add_submit": "Agregar",

    # Las columnas que faltaban en la lista.
    "contacts_col_how": "Cómo entró",
    "contacts_col_status": "Estado",
    "contacts_how_manual": "A mano",
    "contacts_how_import": "Importado",
    "contacts_status_active": "Activo",
    "contacts_status_blocked": "Anulado",
    "contacts_status_incomplete": "Incompleto",
    "contacts_counter_incomplete": "{n} sin completar, que no reciben correos.",
    "contacts_counter_incomplete_one": "Uno sin completar, que no recibe "
                                       "correos.",

    # --- etiquetas ---------------------------------------------------------
    # Se crean aquí y después se eligen. Escribirlas en cada formulario era lo
    # que acababa dejando «Socios» y «socios» como dos etiquetas distintas.
    "contacts_tab_tags": "Etiquetas",
    "contacts_tab_fields": "Columnas",
    # --- las columnas propias del contacto ---------------------------------
    "fields_title": "Columnas",
    "fields_lead": "Lo que guardas de cada contacto además del correo y el "
                   "nombre: su ciudad, su número de socio, lo que debe. "
                   "Después lo escribes dentro del correo y a cada quien le "
                   "llega el suyo.",
    "fields_counter": "Tienes {n} de {limit} columnas.",
    "fields_counter_free": "Tienes {n} columnas, y tu plan no pone tope.",
    "fields_empty": "Todavía no has creado ninguna.",
    "fields_new": "Nueva columna",
    "fields_name": "Nombre",
    "fields_name_example": "Ciudad",
    "fields_type": "Tipo de dato",
    "fields_type_hint": "El tipo decide cómo se lee lo que venga en el "
                        "archivo y cómo se escribe en el correo. Una fecha "
                        "sale como «15 de marzo de 2026».",
    "fields_type_text": "Texto",
    "fields_type_number": "Número",
    "fields_type_date": "Fecha",
    "fields_type_yesno": "Sí o no",
    "fields_add": "Crear la columna",
    "fields_add_action": "Agregar columna",
    "fields_new_lead": "Un dato más de cada contacto. Se guarda con él y se "
                       "escribe dentro de tus correos.",
    "fields_name_hint": "Con este nombre la vas a reconocer, y de él sale la "
                        "marca que se escribe dentro de la pieza.",
    "fields_new_warning": "Ojo: tus {n} contactos se quedan sin este dato, y "
                          "mientras les falte no reciben correos. Se completan "
                          "editándolos o volviendo a importar el archivo con "
                          "esa columna.",
    "fields_new_where": "Para crear una nueva, ve a",
    "fields_type_save": "Guardar",
    "fields_col_filled": "La tienen",
    "fields_filled": "{n} de {total}",
    "fields_delete": "Borrar",
    "fields_delete_hint": "Borrar una columna borra lo que cada contacto tenía "
                          "escrito en ella. Los contactos se quedan.",
    "fields_room": "Te quedan {n} por crear.",
    "fields_room_free": "Tu plan no pone tope.",
    "fields_full": "Ya usaste todas las columnas de tu plan.",
    "fields_plans": "Ver los planes",
    "fields_saved": "Listo, la columna quedó creada.",
    "fields_col_name": "Columna",
    "fields_col_mark": "Se escribe así",
    "fields_col_type": "Tipo",
    "fields_on_contact": "Sus columnas",
    "fields_on_contact_hint": "Todas son obligatorias: un contacto sin sus "
                              "datos no recibe correos.",
    "fields_pick": "Elige una",
    "fields_yes": "Sí",
    "fields_no": "No",
    "error_field": "Ese nombre no sirve o ya lo tiene otra columna.",
    "error_field_value": "Ese dato no es del tipo de la columna.",
    "error_fields_required": "Faltan datos. Todas las columnas son "
                             "obligatorias: un contacto sin ellas no recibiría "
                             "ningún correo.",
    "error_field_type": "No cambié el tipo: {n} contactos tienen ahí un valor "
                        "que no encaja. Corrígelos primero.",
    "error_fields_full": "Marcaste más columnas de las que caben en tu plan, "
                         "que son {n}. Desmarca algunas y vuelve a intentarlo.",

    # Al importar: qué columna del archivo va a cuál.
    "import_map_title": "Qué columnas quieres guardar",
    "import_map_hint": "Estas son las columnas de tu archivo. El correo y el "
                       "nombre se reconocen solos; de las demás, elige las que "
                       "quieras guardar. Lo que no elijas no se guarda, así "
                       "que un archivo con columnas de más se puede importar "
                       "igual.",
    "import_map_skip": "No guardar esta",
    "import_map_new": "Guardarla en una columna nueva",
    "import_map_room": "Te quedan {n} columnas por crear.",

    "tags_title": "Etiquetas",
    "tags_lead": "Los grupos con los que organizas tus contactos. Créalos aquí "
                 "y después los eliges al agregar o importar.",
    "tags_new": "Nueva etiqueta",
    "tags_name": "Nombre",
    "tags_add": "Crear",
    "tags_room": "Puedes crear {n} más.",
    "tags_room_free": "Tu plan no pone tope: crea las que necesites.",
    "tags_counter": "{n} de {limit} etiquetas",
    "tags_counter_free": "{n} etiquetas, sin tope",
    "tags_full": "Llegaste al máximo de etiquetas de tu plan. Borra alguna "
                 "para crear otra, o sube de plan para tener más.",
    "tags_plans": "Ver los planes",
    "tags_empty": "Todavía no tienes ninguna. Crea la primera y podrás usarla "
                  "al agregar contactos.",
    "tags_count": "{n} contactos",
    "tags_count_one": "1 contacto",
    "tags_count_none": "Sin contactos todavía",
    "tags_delete": "Eliminar",
    "tags_delete_hint": "Borrar una etiqueta se la quita a los contactos que "
                        "la llevaban. Los contactos se quedan.",
    "tags_saved": "Listo, la etiqueta quedó creada.",
    "tags_legend": "Etiquetas",
    "tags_pick_hint": "Marca las que le correspondan. Se crean en la pantalla "
                      "de Etiquetas.",
    "tags_none_yet": "Todavía no tienes etiquetas.",
    "tags_create_first": "Crear la primera",

    # De dónde salió la lista. Se pregunta antes de escribir nada porque no se
    # puede rellenar después: una lista subida sin esto queda sin origen.
    "consent_title": "¿De dónde salió esta lista?",
    "consent_lead": "Lo guardamos con cada contacto. Es lo que hay que "
                    "enseñar si alguien reclama que no dio su correo, y no se "
                    "puede escribir después.",
    "consent_choose": "Elige una",
    "consent_own_form": "Se registraron en un formulario nuestro",
    "consent_members": "Son socios o miembros de la organización",
    "consent_customers": "Son clientes que ya nos compraron",
    "consent_event": "Los recogimos en un evento o actividad",
    "consent_other": "Otro origen",
    "consent_note": "Cuéntanos en una línea (opcional)",

    "import_title": "Importar contactos",
    "import_lead": "Un archivo CSV con una columna de correos. Si trae una "
                   "columna de nombres, también la leemos.",
    "import_file_choose": "Elegir archivo",
    "import_file_none": "Ningún archivo elegido",
    "import_file": "Tu archivo",
    "import_file_hint": "Hasta {mb} MB, y hasta {n} importaciones al día.",
    "import_submit": "Importar",
    "import_result_title": "Esto pasó con tu archivo",
    "import_read": "Filas leídas",
    "import_added": "Contactos nuevos",
    "import_updated": "Ya estaban y se actualizaron",
    "import_incomplete": "Sin todos sus datos",
    "import_incomplete_hint": "Un contacto nuevo solo entra con todas tus "
                              "columnas llenas. A los que ya estaban se les "
                              "actualizó lo que traía el archivo.",
    "import_invalid": "Filas sin un correo válido",
    "import_suppressed": "De los importados, están suprimidos",
    "import_suppressed_hint": "Se guardan igual, pero no van a recibir nada "
                             "hasta que dejen de estar suprimidos.",
    "import_stopped": "Llegaste al límite de contactos de tu plan, así que la "
                      "importación se detuvo ahí. Lo que ya había entrado se "
                      "quedó.",
    "import_history": "Tus importaciones",
    "import_history_empty": "Todavía no has importado nada.",
    "import_status_done": "Terminada",
    "import_status_stopped": "Detenida en el límite",
    "import_status_failed": "No se pudo leer",
    "import_status_running": "En curso",

    "blocked_title": "Supresiones",
    "blocked_lead": "Direcciones a las que esta cuenta no le puede volver a "
                    "escribir. Se revisan antes de cada envío, y no gastan "
                    "cuota.",
    "blocked_empty": "No hay ninguna. Es lo normal al empezar.",
    "blocked_how": "Hoy entran aquí de dos formas: cuando alguien pulsa el "
                   "botón de anular la suscripción en uno de tus correos, y "
                   "cuando agregas una dirección tú misma.",
    "blocked_bounces_soon": "Los rebotes y las quejas todavía no entran solos. "
                            "Para eso hace falta el aviso de Amazon, que se "
                            "configura una vez y avisa por cada correo que no "
                            "llegó; mientras tanto, una dirección que rebota no "
                            "se anula sola.",
    "blocked_col_email": "Correo",
    "blocked_col_reason": "Motivo",
    "blocked_col_when": "Desde",
    "blocked_reason_unsubscribe": "Pidió la baja",
    "blocked_reason_hard_bounce": "La dirección no existe",
    "blocked_reason_complaint": "La marcó como spam",
    "blocked_reason_manual": "La agregaste tú",
    "blocked_lift": "Quitar",
    "blocked_locked": "No se puede quitar",
    "blocked_locked_hint": "Un rebote o una queja son un hecho de la "
                          "dirección, no una preferencia: no dejan de ser "
                          "ciertos porque se pulse un botón. Solo se quita lo "
                          "que agregaste a mano.",
    "blocked_add_title": "Suprimir una dirección",
    "blocked_add_lead": "Para cuando alguien te escribe pidiendo que no le "
                        "mandes más. Queda fuera de todos tus envíos.",
    "blocked_add_submit": "Suprimir",
    "blocked_saved": "Listo, esa dirección quedó suprimida.",

    "menu_contacts": "Contactos",
    "menu_admin": "Administración",

    # --- plantillas --------------------------------------------------------
    # Para el cliente son «plantillas»; en el código son «designs», porque
    # `templates/` en este proyecto ya son las plantillas Jinja del panel.
    "designs_title": "Plantillas",
    "designs_lead": "Las piezas con las que sale tu correo. Créalas aquí o "
                    "carga el HTML que ya tienes.",
    "designs_create": "Crear plantilla",

    "designs_upload_button": "Cargar plantilla personalizada",
    "designs_note_columns": "Si escribes {mark} en el texto, a cada persona le "
                            "llega lo que tenga en su columna «{what}». Tus "
                            "columnas:",
    "designs_note_columns_none": "Cuando crees columnas, como Edad, y escribas "
                                 "*|EDAD|* en el texto, a cada persona le "
                                 "llegará su propia edad.",
    "designs_note_columns_link": "Crear columnas en Contactos",
    "designs_note_size": "El HTML no puede pesar más de {kb} KB: pasado eso "
                         "Gmail corta el correo, y lo primero que se pierde es "
                         "el botón para anular la suscripción.",
    "designs_kind_upload": "HTML cargado, {kb} KB",
    "designs_kind_canvas": "Hecha en el editor, {n} diapositivas",
    "designs_kind_canvas_one": "Hecha en el editor, 1 diapositiva",
    "designs_copy": "Duplicar",
    "designs_copy_name": "Copia de {name}",
    "designs_copied": "Listo, ahí tienes la copia.",
    "designs_close": "Cerrar",
    "designs_html_lead": "Cambia el código a la izquierda y mira a la derecha "
                         "cómo queda. Para poner el dato de cada persona, pulsa "
                         "una columna y se escribe donde tengas el cursor.",
    "designs_html_fresh": "Se cargó bien. Ya la puedes usar, o cambiarle lo que "
                          "quieras aquí.",
    "designs_html_code": "Código HTML",
    "designs_html_size": "Pesa {kb} KB de {max} KB.",

    # --- las prediseñadas ---------------------------------------------------
    # El nombre de cada una lo declara su archivo, en email_templates/; aquí va
    # para qué sirve, que es lo que hace falta para elegir. Una plantilla nueva
    # sin línea aquí se ofrece igual, solo que sin explicación.
    "designs_tpl_aviso": "Un aviso corto y sin imagen: un corte, un plazo, un "
                         "recordatorio de pago.",
    "designs_tpl_anuncio": "Una oferta o una novedad, con su imagen arriba y "
                           "un botón.",
    "designs_tpl_boletin": "Varias noticias en un mismo correo, de dos a "
                           "cuatro bloques.",
    "designs_tpl_convocatoria": "Una asamblea o un evento, con la fecha, la "
                                "hora y el lugar aparte.",
    "designs_edit": "Editar",

    # --- llenar una prediseñada --------------------------------------------
    "designs_fill_title": "{plantilla}",
    "designs_fill_lead": "Llena lo que quieras que diga. Puedes ver cómo "
                         "queda antes de guardarla, y volver a cambiarla "
                         "cuando quieras.",
    "designs_fill_back": "Volver a plantillas",
    "designs_fill_missing": "Falta llenar lo que está marcado.",
    "designs_optional": "opcional",
    "designs_save": "Guardar",
    "designs_name_hint_filled": "Para reconocerla después. Si lo dejas vacío "
                                "usamos el título.",
    "designs_updated": "Listo, se guardaron los cambios.",

    "designs_field_titulo": "Título",
    "designs_field_texto": "Texto",
    "designs_field_entrada": "Entrada",
    "designs_field_imagen": "Imagen",
    "designs_field_boton": "Texto del botón",
    "designs_field_enlace": "Dirección del botón",
    "designs_field_fecha": "Fecha",
    "designs_field_hora": "Hora",
    "designs_field_lugar": "Lugar",
    "designs_field_block": "Bloque {n}: {what}",

    # --- la vista previa ---------------------------------------------------
    "designs_columns_title": "Escribir un dato de cada contacto",
    "designs_columns_hint": "Pulsa una para escribirla donde tengas el cursor, "
                            "o escríbela a mano. Al enviar, a cada persona le "
                            "llega su propio dato.",
    "designs_columns_manage": "Las creas y las borras en Contactos →",
    "designs_preview_title": "Vista previa",
    "designs_preview_button": "Ver cómo queda",
    "designs_preview_empty": "Llena la plantilla y pulsa «{boton}» para verla "
                             "aquí.",
    # Las dos van inyectadas al enviar y no dentro de la pieza, así que se
    # explican aquí para que nadie las busque en el formulario.
    "designs_preview_note": "El botón de anular la suscripción se agrega solo, "
                            "en todos los planes.",
    "designs_preview_watermark": "Tu plan lleva la marca «Enviado con "
                                 "Panamails» al pie. Desaparece sola al subir "
                                 "de plan.",

    # --- las imágenes ------------------------------------------------------
    "designs_image_upload": "Subir imagen",
    "designs_image_change": "Cambiar",
    "designs_image_remove": "Quitar",
    "designs_image_none": "Sin imagen",
    "designs_image_hint": "JPG, PNG, GIF o WebP, hasta {mb} MB. La achicamos "
                          "para que el correo abra rápido.",
    "designs_image_bad": "Ese archivo no es una imagen. Sirven JPG, PNG, GIF "
                         "y WebP.",
    "designs_image_heavy": "La imagen pesa más de {mb} MB. Mándala más "
                           "pequeña.",
    # Después de achicarla; pasa con dibujos enormes llenos de detalle.
    "designs_image_big": "Esa imagen no se pudo dejar por debajo de {kb} KB. "
                         "Prueba con otra.",
    "designs_image_gif": "Ese GIF pesa demasiado. Los GIF se guardan sin "
                         "cambios para no quitarles la animación, así que "
                         "tienen que venir livianos.",
    "designs_image_limit": "Ya tienes {n} imágenes guardadas, que es el "
                           "máximo. Borra alguna plantilla que no uses para "
                           "liberar las suyas.",

    "designs_mine_title": "Tus plantillas",
    "designs_from": "Plantilla {name}",
    "designs_mine_empty": "Todavía no tienes ninguna.",
    "designs_upload_title": "Cargar plantilla personalizada",
    "designs_upload_hint": "Un archivo .html de hasta {kb} KB. Pasado ese "
                           "tamaño Gmail recorta el correo y se pierde el "
                           "botón para anular la suscripción.",
    "designs_file": "Archivo",
    "designs_name": "Nombre",
    "designs_name_hint": "Para reconocerla después. Si lo dejas vacío usamos "
                         "el nombre del archivo.",
    "designs_submit": "Cargar",
    "designs_saved": "Listo, ya la puedes usar.",
    "designs_delete": "Eliminar",
    "designs_size": "{kb} KB",
    "designs_locked": "Cargar tu propio HTML es desde el plan {plan}.",

    # Por qué no se pudo guardar. Cada regla está por una razón, y la frase la
    # dice, porque «archivo inválido» no le sirve a nadie para arreglarlo.
    "designs_bad_empty": "El archivo está vacío.",
    "designs_bad_too_big": "Pesa más de {kb} KB. Pasado eso Gmail recorta el "
                           "correo y se pierde el botón de anular la "
                           "suscripción.",
    "designs_bad_not_utf8": "El archivo no está en UTF-8. Vuelve a guardarlo "
                            "con esa codificación.",
    "designs_bad_broken": "No se pudo leer como HTML.",
    "designs_bad_tag": "Trae <{what}>, y eso ningún lector de correo lo "
                       "ejecuta: un correo que lo lleva parece un ataque.",
    "designs_bad_event": "Trae el atributo {what}. Los correos no ejecutan "
                         "código.",
    "designs_bad_href": "Trae un enlace que ejecuta código en vez de llevar a "
                        "una dirección.",
    "designs_bad_external": "Trae CSS o imágenes de otro sitio. Un archivo de "
                            "fuera puede cambiar después de aprobado, así que "
                            "aprobarlo no significaría nada.",

    # --- el lienzo de crear ---------------------------------------------------
    "canvas_title_new": "Plantilla nueva",
    "canvas_lead": "Agrega texto, botones, imágenes y rectángulos y ponlos "
                   "donde quieras. La hoja crece sola hacia abajo. Las "
                   "imágenes y los rectángulos van atrás, con el texto y los "
                   "botones encima.",
    "canvas_noscript": "El editor necesita JavaScript. Actívalo en tu "
                       "navegador para crear plantillas.",
    "canvas_narrow": "El editor se usa mejor en una computadora: en una "
                     "pantalla angosta el lienzo no cabe entero.",
    "canvas_add": "Agregar",
    "canvas_add_text": "Texto",
    "canvas_add_button": "Botón",
    "canvas_add_image": "Imagen",
    "canvas_add_shape": "Rectángulo",
    "canvas_image_hint": "JPG, PNG, GIF o WebP, hasta {mb} MB. Entra debajo de "
                         "lo último, a la mitad del ancho. Los bordes "
                         "transparentes se recortan solos.",
    "canvas_marks_hint": "Haz doble clic en un texto y pulsa una columna: se "
                         "escribe donde está el cursor.",
    "canvas_marks_need": "Primero haz doble clic en un texto, o pon el cursor "
                         "en el texto del botón.",
    "canvas_keys": "Flechas para mover (con Mayús, de a 10). Suprimir para "
                   "borrar. Ctrl+Z deshace y Ctrl+Y rehace.",
    "canvas_props_none": "Haz clic en algo para cambiarlo. Doble clic en un "
                         "texto para escribir.",
    "canvas_page_bg": "Color de la hoja",
    "canvas_shape_bg": "Color",
    "canvas_image_href": "Enlace al pulsarla (opcional)",
    "canvas_image_alt": "Descripción",
    "canvas_image_alt_hint": "Lo que se lee si la imagen no carga",
    "canvas_full_width": "Ancho completo",
    "canvas_image_tip": "Las esquinas la agrandan sin deformarla; los lados la "
                        "recortan.",
    "canvas_font": "Fuente",
    "canvas_size": "Tamaño",
    "canvas_color": "Color de la letra",
    "canvas_bold": "Negrita",
    "canvas_italic": "Cursiva",
    "canvas_align": "Alineación",
    "canvas_align_left": "Izquierda",
    "canvas_align_center": "Centro",
    "canvas_align_right": "Derecha",
    "canvas_line": "Interlineado",
    "canvas_button_text": "Texto del botón",
    "canvas_href": "Enlace",
    "canvas_button_bg": "Color del botón",
    "canvas_radius": "Forma",
    "canvas_replace": "Cambiar imagen",
    "canvas_front": "Traer al frente",
    "canvas_back": "Enviar atrás",
    "canvas_delete": "Borrar",
    "canvas_undo": "Deshacer",
    "canvas_redo": "Rehacer",
    "canvas_resize_sheet": "Arrastra para dejar más o menos espacio abajo",
    "canvas_new_text": "Escribe aquí",
    "canvas_new_button": "Ver más",
    "canvas_overlap": "Hay textos o botones encimados (en rojo). Sepáralos "
                      "para poder guardar: en el correo no se pueden encimar.",
    "canvas_link_overlap": "Una imagen con enlace tiene algo encima (en "
                          "rojo). Sepáralos o quítale el enlace: en el correo "
                          "se funden en una sola imagen y el enlace se "
                          "perdería.",
    "canvas_uploading": "Subiendo la imagen…",
    "canvas_upload_failed": "No se pudo subir la imagen. Prueba otra vez.",
    "canvas_max_items": "Caben hasta {n} elementos.",
    "canvas_name_needed": "Ponle un nombre para reconocerla después.",
    "canvas_leave": "Tienes cambios sin guardar.",
    "canvas_preview_wait": "La vista previa aparece aquí en un momento.",
    "preview_as": "Ver con",
    "preview_as_marks": "Los nombres de las columnas",
    "preview_view": "Cómo se ve",
    "preview_desk": "Computadora",
    "preview_phone": "Teléfono",

    # Por qué no se pudo guardar un lienzo.
    "canvas_meter": "Peso del correo:",
    "canvas_meter_of": "{kb} KB de {max} KB",
    "canvas_check_ok": "Listo: no tiene nada que lo mande a spam.",
    "canvas_check_title": "Para poder guardar, arregla esto:",
    "canvas_bad_broken": "El lienzo llegó dañado. Recarga la página e "
                         "inténtalo otra vez.",
    "canvas_bad_empty": "La plantilla está vacía.",
    "canvas_bad_too_many_items": "Tiene más elementos de los que caben.",
    "canvas_bad_height": "La hoja es demasiado baja o demasiado alta.",
    "canvas_bad_bounds": "Algo se sale de la hoja. Muévelo hacia dentro.",
    "canvas_bad_image": "Una imagen no es de tu cuenta o ya no existe. "
                        "Cámbiala.",
    "canvas_bad_font": "Una fuente no está entre las que funcionan en todos "
                       "los correos.",
    "canvas_bad_size": "Un texto tiene un tamaño fuera de lo permitido.",
    "canvas_bad_text_long": "Un texto es demasiado largo.",
    "canvas_bad_button_text": "Un botón no tiene texto o tiene demasiado.",
    "canvas_bad_href": "El enlace de un botón o de una imagen tiene que "
                       "empezar por https:// o mailto:.",
    "canvas_bad_overlap": "Hay textos o botones encimados. Sepáralos: en el "
                          "correo no se pueden encimar.",
    "canvas_bad_tangled": "Hay cosas acomodadas en molinillo, rodeándose "
                          "sin tocarse. Mueve alguna para que queden en filas "
                          "o columnas.",
    "canvas_bad_link_overlap": "Una imagen con enlace tiene algo encima. "
                               "Sepáralos o quítale el enlace.",
    "canvas_bad_too_big": "El correo pasa de {kb} KB. Quita algo de "
                          "texto.",

    # Lo que tiene riesgo de ir a spam. Con cualquiera, no se guarda.
    "canvas_spam_few_text": "Tiene muy poco texto ({n} caracteres). Escribe al "
                            "menos {min}: un correo casi sin texto es de lo que "
                            "más va a spam.",
    "canvas_spam_image_heavy": "Las imágenes ocupan el {pct} % del correo. Que "
                               "sean como mucho la mitad: el resto, texto.",
    "canvas_spam_too_big": "Pesa {kb} KB y el máximo es {max} KB. Pasado eso "
                           "Gmail lo corta.",
    "canvas_spam_many_links": "Tiene {n} enlaces entre botones e imágenes. "
                              "Deja {max} como mucho.",
    "canvas_spam_shortener": "Un enlace está acortado ({what}). Pon la "
                             "dirección completa: los acortadores esconden a "
                             "dónde llevan.",
    "canvas_spam_caps": "Tiene demasiadas MAYÚSCULAS. Escríbelo normal.",
    "canvas_spam_shouting": "Tiene demasiados signos de exclamación. Deja uno, "
                            "como mucho.",
    "canvas_spam_trigger": "Dice «{what}», que los filtros de spam castigan. "
                           "Dilo de otra forma.",

    "menu_designs": "Plantillas",
    # --- enviar correos ----------------------------------------------------
    "menu_send": "Enviar correos",
    "send_title": "Enviar correos",
    "send_lead": "Elige a quién le escribes y qué plantilla. Puedes mandarlo "
                 "ahora o dejarlo programado.",
    "send_new": "Nueva campaña",
    "send_submit": "Guardar la campaña",
    "send_save": "Guardar los cambios",
    "send_yours": "Campañas guardadas",
    "send_none": "Todavía no has armado ninguna.",
    "send_runs_title": "Campañas enviadas",
    "send_runs_lead": "Una línea por cada vez que salió algo, lo último "
                      "arriba.",
    "send_runs_none": "Todavía no ha salido ninguna.",
    "send_times_one": "Enviada una vez, {when}",
    "send_times": "Enviada {n} veces, la última {when}",
    "send_back": "Volver a envíos",

    "send_subject": "Asunto",
    "send_subject_hint": "Lo primero que se lee, y muchas veces lo único. "
                         "Corto y concreto.",
    "send_list": "Etiquetas",
    "send_list_hint": "Marca las etiquetas que quieras. Quien lleve más de una "
                      "recibe un solo correo. Sin marcar ninguna le escribes a "
                      "toda tu lista.",
    "send_list_none": "Todavía no tienes etiquetas, así que este correo sale a "
                      "toda tu lista.",
    "send_all_contacts": "Todos mis contactos",
    "send_howmany": "{n} contactos",
    "send_piece": "Plantilla",
    "send_no_pieces": "Todavía no tienes ninguna plantilla guardada. Arma una "
                      "primero en",
    "send_when": "Cuándo",
    "send_when_now": "Ahora mismo",
    "send_when_later": "En esta fecha y hora",
    "send_when_hint": "La hora es la de tu reloj. Mientras esté programada la "
                      "puedes cambiar o borrar.",

    "send_pick_piece": "Elige una de tus plantillas.",
    "send_pick_when": "Escribe la fecha y la hora.",
    "send_when_past": "Esa hora ya pasó. Si quieres que salga ya, elige «ahora "
                      "mismo».",
    "send_saved": "Listo, tu campaña quedó guardada.",
    "send_removed": "Campaña borrada.",
    "send_already_out": "Esa campaña ya empezó a salir, así que no se puede "
                        "cambiar ni borrar.",

    "send_now": "Enviar",
    "send_continue": "Seguir enviando",
    "send_edit": "Editar",
    "send_delete": "Borrar",
    "send_done_all": "Se envió. Ya salieron todos.",
    "send_done_some": "Va saliendo. Pulsa «seguir enviando» para la siguiente "
                      "tanda.",
    "send_done_blocked": "Todavía no se puede enviar. Mira lo que falta arriba.",

    # Por qué una cuenta todavía no puede mandar. Se enseñan arriba del todo.
    "send_blocked_plan": "Para enviar hace falta un plan contratado.",
    "send_blocked_postal": "Falta la dirección postal de tu empresa, que la ley "
                           "pide al pie de cada correo.",
    "send_blocked_postal_link": "Escribirla en Configuración",
    "send_blocked_quota": "Se acabaron los correos de tu plan este mes.",
    "send_blocked_cleared": "Falta que habilitemos el envío de tu cuenta. Es "
                            "una sola vez, miramos de dónde salió tu lista y te "
                            "avisamos por correo.",
    "send_blocked_piece": "La plantilla de esa campaña ya no existe.",

    "send_state_ready": "Lista para salir",
    "send_state_scheduled": "Programada para el {when}",
    "send_state_going": "Van {done} de {total}",
    "send_state_sent": "Enviada · {n} salieron",
    "send_state_skipped": "{n} anulados",
    "send_state_failed": "{n} fallaron",
    "send_errors_title": "Lo que no se pudo enviar:",
    "send_seen": "{delivered} entregados · {bounced} rebotes · {opened} "
                 "abiertos · {clicked} con clic",
    "send_seen_complaints": "{n} lo marcaron como spam",

    # La pantalla que pregunta antes de mandar. Dice cifras y no generalidades:
    # es lo único que separa «mandé el boletín» de «le escribí a toda la base».
    "send_confirm_title": "¿Seguro que quieres enviarla?",
    "send_confirm_lead": "Un correo que sale no se puede recoger. Mira a quién "
                         "le va a llegar antes de mandarla.",
    "send_confirm_subject": "Asunto",
    "send_confirm_list": "Etiquetas",
    "send_confirm_piece": "Plantilla",
    "send_confirm_going_none": "Ahora mismo no hay nadie en esa lista, así que "
                               "no hay a quién mandarla.",
    "send_confirm_going_one": "Un contacto",
    "send_confirm_going": "{n} contactos",
    "send_confirm_quota": "Te quedan {n} correos este mes.",
    "send_confirm_suppressed": "Quien se dio de baja no la recibe, y no gasta "
                               "cuota.",
    "send_confirm_again_one": "Esta campaña ya salió una vez. Va a salir otra "
                              "vez a toda la lista, también a quienes ya la "
                              "recibieron.",
    "send_confirm_again": "Esta campaña ya salió {n} veces. Va a salir otra "
                          "vez a toda la lista, también a quienes ya la "
                          "recibieron.",
    "send_confirm_going_on": "Esta campaña está saliendo: van {done} de "
                             "{total}. Se manda la siguiente tanda.",
    "send_confirm_yes": "Sí, enviarla",
    "send_confirm_no": "Cancelar",
    "send_details": "Detalles",
    "run_title": "Detalle del envío",
    "run_lead": "Una fila por persona a la que le salió. Cada cosa cuenta una "
                "vez: la primera apertura y el primer clic.",
    "run_sent_on": "Salió {when}",
    "run_tag": "Etiqueta",
    "run_all_tags": "Todas las etiquetas",
    "run_search": "Buscar por correo o nombre",
    "run_outcome": "Qué pasó",
    "run_outcome_all": "Todos",
    "run_outcome_entregados": "Entregados",
    "run_outcome_rebotes": "Rebotaron",
    "run_outcome_rechazados": "Rechazados",
    "run_outcome_spam": "Lo marcaron como spam",
    "run_outcome_abrieron": "Lo abrieron",
    "run_outcome_pulsaron": "Pulsaron",
    "run_outcome_sin_abrir": "No lo abrieron",
    "run_apply": "Buscar",
    "run_clear": "Quitar filtros",
    "run_email": "Correo",
    "run_name": "Nombre",
    "run_reached": "Llegó",
    "run_opened": "Abrió",
    "run_clicked": "Pulsó",
    "run_reached_sent": "Enviado",
    "run_reached_delivery": "Entregado",
    "run_reached_bounce": "Rebotó",
    "run_reached_reject": "Rechazado",
    "run_reached_complaint": "Lo marcó como spam",
    "run_gone": "Ya no está en tus contactos",
    "run_none": "Nadie coincide con ese filtro.",
    "run_empty": "Todavía no hay nada que contar de este envío.",
    "run_count": "{n} personas",
    "run_count_one": "1 persona",
    "run_page": "Página {page} de {pages}",
    "run_prev": "Anterior",
    "run_next": "Siguiente",
    "run_note": "Las aperturas son aproximadas: algunos buzones abren los "
                "correos solos y otros no avisan. «Entregado» quiere decir que "
                "el servidor de la persona lo aceptó, no que haya llegado a su "
                "bandeja.",
    "send_edit_title": "Editar la campaña",
    "send_edit_lead": "Se puede cambiar mientras no haya empezado a salir.",

    # --- darse de baja -----------------------------------------------------
    # La pantalla que abre quien recibió una campaña. No tiene cuenta ni sesión.
    "bye_title": "Dejar de recibir estos correos",
    "bye_lead": "Si confirmas, {company} no le vuelve a escribir a {email}.",
    "bye_already": "{email} ya estaba fuera de esa lista. No le llega nada.",
    "bye_submit": "Sí, darme de baja",
    "bye_done_title": "Listo",
    "bye_done": "{email} no va a recibir más correos de {company}.",
    "bye_done_gone": "Esa dirección ya no está en ninguna lista.",
    "bye_done_note": "Si algún día quieres volver, pídeselo a quien te escribía: "
                     "nosotros no te podemos volver a suscribir.",


    # --- administración ----------------------------------------------------
    "admin_title": "Administración",
    "admin_filter_pending": "Esperando habilitación",
    "admin_tab_accounts": "Cuentas",
    "admin_mail_title": "Correos del sistema",
    "admin_mail_lead": "Lo que el panel le mandó a una dirección (códigos, "
                       "avisos, bienvenidas) y qué dijo Amazon de cada uno. "
                       "Para cuando alguien dice que no le llegó.",
    "admin_mail_search": "Dirección de correo",
    "admin_mail_col_when": "Cuándo",
    "admin_mail_col_subject": "Correo",
    "admin_mail_col_result": "Qué pasó",
    "admin_mail_failed": "No salió",
    "admin_mail_outcome_delivered": "Entregado",
    "admin_mail_outcome_bounced": "Rebotó",
    "admin_mail_outcome_soft_bounced": "Rebote pasajero",
    "admin_mail_outcome_complained": "Lo marcó como spam",
    "admin_mail_outcome_rejected": "Amazon lo rechazó",
    "admin_mail_waiting": "Enviado a Amazon, sin respuesta todavía",
    "admin_mail_not_ses": "No salió por Amazon (desarrollo)",
    "admin_mail_none": "No le hemos mandado nada a {address}.",
    "admin_mail_hint": "«Entregado» quiere decir que el servidor del "
                       "destinatario lo aceptó. Si después lo mandó a correo no "
                       "deseado o a cuarentena, no se lo cuenta a nadie: eso solo "
                       "lo puede mirar quien administra ese buzón.",
    # Lo que ve el administrador cuando todavía no hay ningún cliente del que
    # sacar estadísticas.
    "admin_no_clients_title": "Todavía no hay clientes",
    "admin_no_clients_lead": "Cuando se registre la primera empresa, aquí vas a "
                             "ver lo mismo que ve ella en su pantalla.",
    "admin_open": "Ver perfil",

    "admin_accounts_lead": "Todas las cuentas. Busca por correo o por empresa.",
    "admin_all_states": "Todos los estados",
    "admin_search": "Buscar por correo o empresa",
    "admin_col_company": "Empresa",
    "admin_col_contact": "Contacto",
    "admin_col_email": "Correo",
    "admin_col_status": "Estado",
    "admin_col_plan": "Plan",
    "admin_col_created": "Se registró",
    "admin_col_login": "Última entrada",
    "admin_never": "Nunca",
    "admin_unconfirmed": "Sin confirmar",
    "admin_no_plan": "Sin plan",
    "admin_none_found": "Ninguna cuenta coincide.",

    "admin_account_lead": "Todo sobre esta cuenta.",
    "admin_back": "Volver a las cuentas",
    "admin_done": "Listo, quedó guardado.",
    "admin_need_reason": "Escribe el motivo: es lo que se lee meses después "
                         "cuando alguien pregunte por qué.",
    "admin_update_title": "Actualizar la cuenta",
    "admin_update_hint": "Ponerle el plan a mano es para quien pagó por Yappy "
                         "o por transferencia: deja la cuenta activa y con "
                         "fecha de vencimiento, igual que un pago por PayPal. "
                         "Suspender cierra además todas sus sesiones abiertas.",
    "admin_cycle": "Por cuánto tiempo",
    "admin_suspend": "Cuenta suspendida",
    "admin_suspend_hint": "Mientras lo esté no puede entrar, ni contratar, ni "
                          "enviar.",
    "admin_reason": "Motivo",
    "admin_reason_hint": "Si cambias las dos cosas, el motivo queda escrito en "
                         "las dos.",
    "admin_apply": "Actualizar",

    "admin_usage_title": "Cómo usa la plataforma",
    "admin_contacts": "Contactos",
    "admin_of_limit": "de {n} que le permite su plan",
    "admin_suppressions": "Supresiones",
    "admin_tags": "Etiquetas",
    "admin_none": "Ninguna",
    "admin_imports_title": "Sus importaciones",
    "admin_imports_empty": "No ha importado nada todavía.",
    "admin_imports_origin": "Dijo que salió de",
    "admin_privacy_note": "Se enseñan cifras y de dónde dijo que salió cada "
                          "lista, no las direcciones de sus contactos. Esas "
                          "son suyas y de quien está en ellas.",

    "admin_sending_title": "Envíos del mes",
    "admin_sending_lead": "Correos enviados, rebotes, quejas y cuota restante. "
                          "Todavía no hay envíos que medir; estas cifras se "
                          "llenan solas cuando salga la primera campaña.",
    "admin_devices_title": "Sus dispositivos",
    "admin_history_title": "Actividad",
    "admin_history_empty": "Nada todavía.",
    "admin_history_status": "Estado: de {before} a {after}",
    "admin_history_sending": "Se habilitó el envío",
    "admin_history_plan": "Plan: de {before} a {after}",

    "admin_act_login": "Entró a la cuenta",
    "admin_act_login_failed": "Intento de entrada fallido",
    "admin_act_logout": "Cerró sesión",
    "admin_act_register": "Se registró",
    "admin_act_confirm": "Confirmó su correo",
    "admin_act_password_change": "Cambió la contraseña",
    "admin_act_recover": "Recuperó la contraseña",
    "admin_act_correct_email": "Corrigió su correo",
    "admin_act_two_factor": "Autenticación de múltiples factores",
    "admin_act_session_closed": "Cerró una sesión desde el aviso por correo",
    "admin_act_import": "Importó {file}",
    "admin_act_import_counts": "{added} nuevos · {updated} actualizados · "
                               "{invalid} sin correo",
    "admin_act_payment": "Pagó el plan {plan}",
    "admin_act_payment_failed": "Intento de pago sin cobrar: {plan}",
    "admin_act_from": "desde {ip}",
    "admin_act_reason": "Motivo: {reason}",
    "admin_act_campaign": "Envió «{subject}»",
    "admin_act_campaign_counts": "{sent} salieron · {skipped} suprimidos · "
                                 "{failed} fallaron",

    # El desplegable que parte la línea de tiempo. Los nombres van por el valor
    # que viaja en la dirección, en español como el resto de los filtros.
    "admin_act_filter": "Tipo de actividad",
    "admin_act_all": "Toda la actividad",
    "admin_act_only_entradas": "Entradas",
    "admin_act_only_pagos": "Transacciones",
    "admin_act_only_correos": "Correos",
    "admin_act_only_contactos": "Contactos",
    "admin_act_only_decisiones": "Decisiones",

    "admin_designs_title": "Plantillas subidas",
    "admin_designs_lead": "El HTML que ha subido cada cliente. Lo peligroso lo "
                          "rechaza solo el validador al subirlo; esto es para "
                          "poder mirarlo cuando haga falta.",
    "admin_designs_empty": "Ningún cliente ha subido nada todavía.",
    "admin_designs_download": "Ver el archivo",

    # La única puerta que queda con una persona detrás.
    "admin_sending_gate": "Habilitación para enviar",
    "admin_sending_gate_hint": "Todos tus clientes envían desde el mismo "
                               "dominio, así que comparten una sola "
                               "reputación. Mira de dónde dijo que salió su "
                               "lista antes de habilitarla. Se hace una sola "
                               "vez por cuenta.",
    "admin_sending_clear": "Habilitar el envío",
    "admin_sending_cleared": "Habilitada para enviar",
    "admin_sending_cleared_when": "Habilitada {when}",
    "admin_sending_pending": "Todavía no puede enviar",

    "admin_two_step_needed": "Para entrar a administración activa antes la "
                             "autenticación de múltiples factores. Es la "
                             "cuenta que puede suspender y habilitar a todos "
                             "los demás.",

    # --- errors ------------------------------------------------------------
    "error_required": "Completa este campo.",
    "error_email_invalid": "Ese correo no parece válido.",
    "error_email_taken": "Ya existe una cuenta con ese correo.",
    "error_password_short": "La contraseña debe tener al menos 10 caracteres.",
    "error_password_long": "Esa contraseña es demasiado larga. Usa uno más corto.",
    "error_password_upper": "Agrégale al menos una letra mayúscula.",
    "error_password_digit": "Agrégale al menos un número.",
    "error_password_symbol": "Agrégale al menos un símbolo, por ejemplo . - _ ! ?",
    "error_login_failed": "El correo o la contraseña no coinciden.",
    "error_csrf": "El formulario venció. Vuelve a intentarlo.",
    "error_too_many": "Demasiados intentos. Espera unos minutos y vuelve a probar.",
    # One message for a wrong code, one that expired and one that never existed.
    # The three are different facts and auth_events keeps them apart, but the
    # screen may not: telling them apart would say whether the address has an
    # account. See rule 7.
    "error_code_invalid": "Ese código no es correcto o ya venció. Revísalo o "
                          "pide uno nuevo.",
    "error_code_too_many": "Demasiados intentos con ese código. Pide uno nuevo.",
    "error_code_used": "Ese código ya se usó. Si ya confirmaste tu correo, "
                       "entra normalmente.",
    "error_mail_failed": "No pudimos enviarte el código en este momento, así "
                         "que no creamos la cuenta. Vuelve a intentarlo en unos "
                         "minutos.",
    "error_password_wrong": "Esa no es tu contraseña actual.",
    "error_password_repeat": "Las dos contraseñas no coinciden.",
    "error_password_used": "Esa contraseña ya la usaste antes. Escribe una que "
                           "no hayas tenido nunca.",
    "error_import_running": "Ya tienes una importación en curso. Espera a que "
                            "termine y vuelve a intentarlo.",
    "error_import_too_many": "Llegaste a las {n} importaciones de hoy. Vuelve "
                             "mañana o escríbenos si necesitas más.",
    "error_import_unreadable": "No pudimos leer ese archivo. Revisa que sea un "
                               "CSV y que tenga una columna de correos.",
    "error_contact_email": "Ese correo no parece válido.",
    "error_contact_taken": "Ya tienes otro contacto con esa dirección.",
    "error_contacts_full": "Llegaste al límite de contactos de tu plan.",
    "error_tag": "Ese nombre está vacío, ya lo tienes, o llegaste al máximo de "
                 "etiquetas.",
    "error_suspended": "Tu cuenta está suspendida. Escríbenos a "
                       "panamails.info@gmail.com y lo revisamos.",

    # --- error pages -------------------------------------------------------
    # Shown instead of the server's own blank error page. The technical detail
    # stays in the platform log; the visitor gets something they can act on.
    "error_db_title": "El servicio no está disponible",
    "error_db_lead": "No logramos conectar con la base de datos. Es un problema "
                     "temporal de nuestro lado: no tiene que ver con tu cuenta "
                     "ni con tu conexión, y no se perdió nada de lo que ya "
                     "tenías guardado.",
    "error_upload_big_title": "Ese archivo es muy grande",
    "error_upload_big_lead": "El límite es de 5 MB por archivo. Si tu lista es "
                             "más grande, pártela en dos y sube las mitades "
                             "por separado.",
    "error_unknown_title": "Algo salió mal",
    "error_unknown_lead": "Tuvimos un problema inesperado al procesar lo que "
                          "pediste. Ya quedó anotado de nuestro lado.",
    "error_retry": "Vuelve a intentarlo en unos minutos. Si sigue pasando, "
                   "escríbenos y lo revisamos.",

    # --- emails ------------------------------------------------------------
    "mail_confirm_subject": "{code} es tu código de Panamails",
    "mail_confirm_heading": "Confirma tu correo",
    "mail_confirm_body": "Gracias por crear tu cuenta en Panamails. Escribe "
                         "este código en la página donde lo pediste:",
    "mail_confirm_expiry": "El código vence en {minutes} minutos.",
    "mail_confirm_expiry_one": "El código vence en un minuto.",
    "mail_confirm_ignore": "Si no creaste ninguna cuenta, puedes ignorar este "
                           "mensaje: no se hará nada.",

    # Sent once the code is typed and the address is verified: the account is
    # complete. Transactional, like the rest of the system mail — it describes
    # the state of an account its owner just created, it does not offer
    # anything, so rule 8 holds and it carries no unsubscribe link.
    "mail_welcome_subject": "Tu cuenta de Panamails está lista",
    # Neutral on purpose: we do not know the recipient's gender.
    "mail_welcome_heading": "Te damos la bienvenida, {name}",
    "mail_welcome_body": "Confirmaste tu correo, así que tu cuenta ya está "
                         "creada y ya puedes contratar un plan. Desde el panel "
                         "subes tus contactos, los organizas con etiquetas y "
                         "dejas tus campañas armadas.",
    "mail_welcome_button": "Entrar al panel",
    "mail_welcome_next_title": "Antes de tu primer envío",
    "mail_welcome_next": "La primera campaña la revisamos contigo: miramos de "
                         "dónde salió tu lista y hacemos una prueba antes de "
                         "que salga. Es una sola vez, y es lo que mantiene la "
                         "entregabilidad alta para todos los que envían desde "
                         "Panamails.",
    "mail_welcome_help": "Si algo no te calza, escríbenos a "
                         "panamails.info@gmail.com y lo vemos.",

    # The recovery code. Same shape as the confirmation one, and the subject
    # carries it too: on a phone it is readable from the notification.
    "mail_recover_subject": "{code} es tu código para recuperar tu cuenta",
    "mail_recover_heading": "Recupera tu cuenta",
    "mail_recover_body": "Pediste poner una contraseña nueva en Panamails. "
                         "Escribe este código en la página donde lo pediste:",
    "mail_recover_ignore": "Si no lo pediste, ignora este mensaje: tu "
                           "contraseña no cambia hasta que alguien escriba el "
                           "código, y solo tú lo tienes.",

    # Sent when a sign-in comes from a device this account has never used. The
    # only warning there is that somebody else got in, so it says what happened,
    # where, and what to do about it without needing the password.
    "mail_login_subject": "Entraron a tu cuenta desde un dispositivo nuevo",
    "mail_login_heading": "Un ingreso desde un dispositivo nuevo",
    "mail_login_body": "Alguien entró a tu cuenta de Panamails desde un "
                       "dispositivo que no habías usado antes:",
    "mail_login_ip": "Dirección IP {ip}",
    "mail_login_alert_title": "¿No fuiste tú?",
    "mail_login_alert": "Cierra esa sesión y cambia tu contraseña. No hace "
                        "falta que recuerdes la anterior.",
    "mail_login_close": "Cerrar esa sesión",
    "mail_login_change": "Cambiar mi contraseña",
    "mail_login_ignore": "Si fuiste tú, puedes ignorar este mensaje. No "
                         "volveremos a avisarte desde ese dispositivo.",

    # The only warning someone gets when another person changed their password.
    "mail_password_subject": "Tu contraseña de Panamails cambió",
    "mail_password_heading": "Tu contraseña cambió",
    "mail_password_body": "Acabamos de cambiar la contraseña de tu cuenta y "
                          "cerramos la sesión en los demás dispositivos.",
    "mail_password_ok": "Si fuiste tú, no tienes que hacer nada más.",
    "mail_password_alert_title": "¿No fuiste tú?",
    "mail_password_alert": "Escríbenos de inmediato a panamails.info@gmail.com. "
                           "Quien haya entrado conoce tu contraseña anterior, "
                           "así que conviene revisar también el correo con el "
                           "que abriste la cuenta.",
    "mail_password_button": "Entrar al panel",

    # Sent both ways, and one of the messages nobody can turn off: turning
    # two-step on with a phone that is not the owner's is how an account gets
    # taken away for good, and turning it off is the first thing anybody does
    # after getting in.
    # La invitación a entrar como usuario de una cuenta.
    "mail_invite_subject": "{company} te invitó a su cuenta de Panamails",
    "mail_invite_heading": "Te dieron entrada a {company}",
    "mail_invite_body": "Vas a poder entrar a la cuenta de {company} en "
                        "Panamails con tu propio correo. Pulsa el botón y "
                        "elige tu contraseña.",
    "mail_invite_expires": "El enlace sirve una sola vez y vence en {days} "
                           "días.",
    "mail_invite_button": "Poner mi contraseña",
    "mail_invite_foot": "Si no esperabas esto, no hagas nada: sin poner una "
                        "contraseña, la invitación no sirve.",

    "mail_two_step_on_subject": "Activaste la autenticación de múltiples factores",
    "mail_two_step_off_subject": "Desactivaste la autenticación de múltiples factores",
    "mail_two_step_on_heading": "Tu cuenta ya pide un segundo paso",
    "mail_two_step_off_heading": "Tu cuenta dejó de pedir el segundo paso",
    "mail_two_step_on_body": "Desde ahora, al entrar desde un dispositivo "
                             "nuevo te vamos a pedir el código de tu app "
                             "además de la contraseña.",
    "mail_two_step_off_body": "Desde ahora alcanza con tu contraseña para "
                              "entrar. También olvidamos los dispositivos que "
                              "habías marcado como de confianza.",
    "mail_two_step_ok": "Si fuiste tú, no tienes que hacer nada más.",
    "mail_two_step_alert_title": "¿No fuiste tú?",
    "mail_two_step_on_alert": "Alguien con tu contraseña acaba de poner su "
                              "propio teléfono como segundo paso, y con eso te "
                              "puede dejar afuera de tu cuenta. Escríbenos de "
                              "inmediato a panamails.info@gmail.com.",
    "mail_two_step_off_alert": "Quien lo hizo conoce tu contraseña. Cámbiala "
                               "ahora mismo y escríbenos a "
                               "panamails.info@gmail.com.",
    "mail_two_step_button": "Entrar a mi cuenta",

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

    # --- los avisos de la cuenta -------------------------------------------
    # El plan, la habilitación de envío y la suspensión. Los compone
    # services/notices.py sobre una sola plantilla, porque los ocho tienen la
    # misma forma y lo único que cambia es esto.
    "mail_notice_off": "Estos avisos se apagan en Configuración → "
                       "Notificaciones.",
    "mail_plan_button": "Ir a mi panel",
    "mail_plan_until": "Corre hasta el {until}. Te avisamos una semana antes de "
                       "que se venza.",
    "mail_plan_note_title": "Antes de tu primer envío",
    "mail_plan_note_text": "Miramos una sola vez de dónde salió tu lista y te "
                           "habilitamos el envío. Te avisamos por correo en "
                           "cuanto esté.",

    "mail_plan_started_subject": "Tu plan {plan} ya está activo",
    "mail_plan_started_heading": "Ya tienes el plan {plan}",
    "mail_plan_started_body": "Recibimos tu pago y tu cuenta quedó activa con "
                              "el plan {plan}.",

    "mail_plan_renewed_subject": "Renovaste tu plan {plan}",
    "mail_plan_renewed_heading": "Tu plan {plan} sigue corriendo",
    "mail_plan_renewed_body": "Recibimos tu pago. Los días que te quedaban no "
                              "se pierden: lo que acabas de pagar se suma al "
                              "final.",

    "mail_plan_expiring_subject": "Tu plan {plan} vence el {until}",
    "mail_plan_expiring_heading": "A tu plan le quedan {days} días",
    "mail_plan_expiring_body": "Tu plan {plan} vence el {until}. Si lo renuevas "
                               "antes, los días que te quedan se suman al final "
                               "y no pierdes ninguno.",
    "mail_plan_expiring_button": "Renovar mi plan",

    "mail_plan_expired_subject": "Tu plan {plan} venció",
    "mail_plan_expired_heading": "Se venció tu plan {plan}",
    "mail_plan_expired_body": "Venció el {until}, así que por ahora no puedes "
                              "enviar campañas.",
    "mail_plan_expired_kept": "No se borró nada: tus contactos, tus etiquetas y "
                              "tus plantillas siguen donde estaban y vuelven a "
                              "servir en cuanto contrates otra vez.",
    "mail_plan_expired_button": "Ver mi plan",

    "mail_cleared_subject": "Ya puedes enviar tus campañas",
    "mail_cleared_heading": "Tu cuenta quedó habilitada",
    "mail_cleared_body": "Revisamos de dónde salió tu lista y ya puedes enviar. "
                         "Es una sola vez por cuenta, así que no tienes que "
                         "volver a esperar.",
    "mail_cleared_button": "Ir a mi panel",
    "mail_cleared_note_title": "Cuida tu lista",
    "mail_cleared_note_text": "Escríbele solo a quien te dejó su correo. Todos "
                              "enviamos desde el mismo dominio, así que si los "
                              "rebotes suben se pausa el envío solo.",

    "mail_suspended_subject": "Tu cuenta de Panamails quedó suspendida",
    "mail_suspended_heading": "Suspendimos tu cuenta",
    "mail_suspended_body": "Mientras esté suspendida no se puede entrar ni "
                           "enviar. No se borró nada: tus contactos y tus "
                           "plantillas siguen ahí.",
    "mail_suspended_write": "Si crees que es un error, escríbenos a {email} y "
                            "lo revisamos.",

    "mail_reinstated_subject": "Tu cuenta está activa otra vez",
    "mail_reinstated_heading": "Levantamos la suspensión",
    "mail_reinstated_body": "Ya puedes entrar y seguir donde estabas.",
    "mail_reinstated_button": "Entrar al panel",

    # Este va a quien administra, no a un cliente.
    "mail_admin_payment_subject": "{company} contrató el plan {plan}",
    "mail_admin_payment_heading": "Un cliente pagó",
    "mail_admin_payment_body": "{company} ({email}) contrató el plan {plan}.",
    "mail_admin_payment_waiting": "Todavía no puede enviar: falta habilitarle "
                                  "el envío desde su ficha.",
    "mail_admin_payment_cleared": "Ya estaba habilitada para enviar, así que no "
                                  "hay nada pendiente.",
    "mail_admin_payment_button": "Ver la ficha",

    "mail_admin_signup_subject": "{company} se registró",
    "mail_admin_signup_heading": "Se registró {company}",
    "mail_admin_signup_body": "{name} confirmó el correo {email} y la cuenta de "
                              "{company} ya está creada. Todavía no tiene plan "
                              "ni puede enviar.",
    "mail_admin_signup_button": "Ver la ficha",

    "mail_admin_plan_end_subject": "Se le venció el plan a {company}",
    "mail_admin_plan_end_heading": "{company} se quedó sin plan",
    "mail_admin_plan_end_body": "El plan {plan} de {company} venció el {until}, "
                                "así que ya no puede enviar.",
    "mail_admin_plan_end_kept": "No se borró nada suyo: sus contactos y sus "
                                "plantillas siguen ahí, y vuelven a servir en "
                                "cuanto renueve.",
    "mail_admin_plan_end_button": "Ver la ficha",
    "mail_invoice_subject": "Ya está tu factura",
    "mail_invoice_heading": "Tu factura está lista",
    "mail_invoice_body": "La factura de tu pago del {when} ya está lista. La "
                         "descargas desde Configuración, en Facturación.",
    "mail_invoice_button": "Ir a Facturación",
}


def t(key: str, **kwargs) -> str:
    text = TEXTS[key]
    return text.format(**kwargs) if kwargs else text


MONTHS = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
          "agosto", "septiembre", "octubre", "noviembre", "diciembre")


def _in_zone(when, zone=None):
    """Un momento con zona, llevado a la de quien lo va a leer.

    Una fecha sin hora ni zona (la de una columna de un contacto, por ejemplo)
    es una fecha de calendario y no se mueve: el 15 de marzo es el 15 de marzo
    en cualquier sitio.
    """
    if getattr(when, "tzinfo", None) is None:
        return when
    from services import clock
    return clock.local(when, zone)


def on_date(when, zone=None) -> str:
    """La fecha como la escribiría una persona, en la zona de quien la lee.

    A mano y no con `strftime`, que da el mes en el idioma del servidor: en
    Railway saldría «September» en una pantalla en español.
    """
    when = _in_zone(when, zone)
    return f"{when.day} de {MONTHS[when.month - 1]} de {when.year}"


def at_moment(when, zone=None) -> str:
    """La fecha y la hora, para algo que va a pasar."""
    when = _in_zone(when, zone)
    return f"{on_date(when)} a las {when:%H:%M}"


def ago(moment) -> str:
    """How long ago that was, in words.

    Rounds down and stops at days: on this screen the question is "was that me,
    this morning?", not how many seconds have passed.
    """
    if moment is None:
        return ""
    from datetime import datetime, timezone

    seconds = (datetime.now(timezone.utc) - moment).total_seconds()
    if seconds < 90:
        return t("when_now")
    minutes = int(seconds // 60)
    if minutes < 60:
        return t("when_minute") if minutes == 1 else t("when_minutes", n=minutes)
    hours = minutes // 60
    if hours < 24:
        return t("when_hour") if hours == 1 else t("when_hours", n=hours)
    days = hours // 24
    return t("when_day") if days == 1 else t("when_days", n=days)
