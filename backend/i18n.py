"""Every line of Spanish the client sees, in one file.

Project convention: code and database fields in English, interface in Spanish,
and the interface strings gathered here instead of scattered through the
templates, so they can be reworded without touching any markup.
"""

from __future__ import annotations

TEXTS = {
    # --- shared ------------------------------------------------------------
    "brand": "Sobreala",
    "nav_panel": "Estadísticas",
    "nav_logout": "Cerrar sesión",
    # Encima de salir. Lleva a la lista de las cuentas que este navegador tiene
    # abiertas a la vez, para saltar entre ellas sin escribir nada.
    "nav_switch": "Cambiar de cuenta",
    "back_to_site": "Volver al sitio",
    # Los avisos que bajan desde arriba (octubre de 2026). El de «guardado»
    # dice qué se guardó y vive con su pantalla; este es el de cuando no cambió
    # nada, igual para todas.
    "saved_none": "No se realizaron cambios.",
    "toast_close": "Cerrar el aviso",

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

    # --- the Dashboard (octubre de 2026) -------------------------------------
    # One row of the menu for everything a client works with, and its tree.
    "menu_dashboard": "Dashboard",
    "dash_title": "Dashboard",
    "dash_sections": "Secciones",
    "dash_stats": "Estadísticas",
    "dash_stats_summary": "Resumen",
    "dash_stats_opens": "Aperturas y clics",
    "dash_stats_campaigns": "Campañas",
    "dash_stats_timing": "Cuándo abren",
    "dash_stats_growth": "Lista",
    "dash_stats_quota": "Cuota",
    "dash_mail": "Correos",
    "dash_send": "Enviar",
    "dash_compose": "Redactar",
    "dash_bulk": "Masivo",
    "dash_templates": "Plantillas",
    "dash_templates_mine": "Mis plantillas",
    "dash_templates_new": "Lienzo",
    "dash_send_settings": "Configuración de envío",
    # La de la cuenta, su propia rama a la izquierda (octubre de 2026).
    "dash_settings": "Configuración",
    "dash_sent": "Enviados",
    "dash_sender": "Remitente",
    "dash_contacts": "Contactos",
    "dash_contacts_list": "Lista",
    "dash_contacts_suppressions": "Supresiones",

    # --- signing out from a link -------------------------------------------
    # Salir cierra la sesión al momento desde los dos sitios. Esta pantalla ya
    # no está en ese camino: solo la recibe una petición que el navegador dijo
    # estar adelantando por su cuenta, y a esa no la mira nadie.
    "logout_title": "¿Cerrar tu sesión?",
    "logout_lead": "Vas a salir de tu cuenta en este dispositivo.",
    "logout_submit": "Sí, cerrar mi sesión",
    "logout_cancel": "No, seguir en Sobreala",

    # --- registration ------------------------------------------------------
    "register_title": "Crea tu cuenta",
    "register_company": "Nombre de tu negocio u organización",
    "register_contact": "Tu nombre",
    "register_email": "Correo electrónico",
    "register_phone": "Tu teléfono",
    "register_phone_hint": "Es al que te escribimos para agendar tu demostración.",
    "register_company_phones": "Teléfonos de tu empresa (opcional)",
    "register_address": "Dirección",
    "register_address_hint": "La de tu negocio. Sale al pie de tus campañas, "
                             "porque la ley la pide, y la verificamos con un "
                             "documento.",
    # El selector del país de un teléfono, y el botón de agregar otro.
    "phone_country": "País",
    "phone_add": "Agregar otro número",
    "register_password": "Contraseña",
    "register_submit": "Crear cuenta",
    # Partido en tres porque dos de los pedazos son enlaces. Todo el español
    # sigue aquí; la plantilla solo los une.
    "register_legal": "Al crear tu cuenta aceptas los",
    "register_legal_terms": "términos y condiciones",
    "register_legal_join": "y la",
    "register_legal_privacy": "política de privacidad",
    # El mismo pie al registrarse y al crear otra cuenta desde una abierta.
    "register_have_account": "¿Ya tienes una cuenta?",
    "register_login_link": "Iniciar sesión",

    # --- confirmation ------------------------------------------------------
    "confirm_title": "Escribe tu código",
    "confirm_lead": "Te enviamos un código de 6 dígitos a tu correo. "
                    "Vence en {minutes} minutos.",
    "confirm_lead_one": "Te enviamos un código de 6 dígitos a tu correo. "
                        "Vence en un minuto.",
    "confirm_hint": "Si no lo ves, mira en la carpeta de spam.",
    "confirm_code": "Código de 6 dígitos",
    "confirm_submit": "Confirmar mi correo",
    # Un botón y no una pantalla: el código sale a la dirección que ya se
    # escribió, sin preguntarla otra vez. Lo usan confirmar y recuperar.
    "confirm_resend": "Pedir otro código",
    "code_resent": "Te enviamos un código nuevo.",
    "code_resend_failed": "No pudimos enviarte el código. Vuelve a intentarlo "
                          "en unos minutos.",
    "confirm_go_back": "Volver a entrar",
    "confirm_countdown": "Vence en {time}",
    "confirm_expired": "El código venció. Pide uno nuevo y te lo enviamos al "
                       "momento.",

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
    "welcome_tab": "Te damos la bienvenida",
    "welcome_title": "{name}, te damos la bienvenida a Sobreala",
    "welcome_lead": "Tu cuenta está lista. Elige el plan que más se adapte a ti "
                    "para empezar a enviar correos.",
    "welcome_plans": "Ver planes",
    "welcome_settings": "Ir a configuración",
    # La misma pantalla con la cuenta todavía cerrada: los dos caminos que la
    # abren, la demostración y contratar, sin empujar hacia ninguno.
    # Lo que se pregunta al pedirla (octubre de 2026). Antes había aquí un
    # párrafo con las dos formas de empezar y la lista de lo que se hace en la
    # demostración, y se pedían el WhatsApp y el RUC o la cédula.
    "welcome_demo_business": "¿A qué se dedica tu negocio?",
    "welcome_demo_purpose": "¿Para qué usarás Sobreala?",
    "welcome_demo_ask": "Pedir la demostración",
    "welcome_demo_done_title": "Tu solicitud ha sido recibida",
    "welcome_demo_contacts": "¿Cuántos contactos tienes?",
    "welcome_demo_choose": "Elige una opción",
    "welcome_demo_contacts_lt500": "Menos de 500",
    "welcome_demo_contacts_500_2k": "De 500 a 2,000",
    "welcome_demo_contacts_2k_10k": "De 2,000 a 10,000",
    "welcome_demo_contacts_gt10k": "Más de 10,000",
    "welcome_demo_source": "¿Cómo conseguiste esos contactos?",
    "welcome_demo_source_customers": "Son mis clientes o socios",
    "welcome_demo_source_students": "Son alumnos o familias de la matrícula",
    "welcome_demo_source_form": "Se inscribieron en un formulario",
    "welcome_demo_source_events": "Los recogí en eventos",
    "welcome_demo_source_other": "Otra forma",
    "welcome_demo_website": "Sitio web (opcional)",
    "welcome_demo_website_ph": "minegocio.com",
    "welcome_demo_website_label": "Sitio web",
    "welcome_buy_lead": "¿Ya sabes qué plan quieres? Al contratarlo empiezas "
                        "enseguida, sin esperar la demostración.",
    "demo_needs_email": "Para pedirla, confirma primero tu correo: es a donde te "
                        "avisamos cuando tu cuenta esté abierta.",
    "demo_too_many": "Ya nos avisaste varias veces hoy. Te vamos a escribir; si "
                     "es urgente, escríbenos a info@sobreala.com.",
    # El RUC o la cédula, que se pide al abrir la cuenta por cualquiera de los
    # dos caminos: al pedir la demostración y al pagar.
    # Se llamó «RUC o cédula» hasta octubre de 2026.
    "tax_id_label": "Identificación personal",

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
    "mail_reply_code_subject": "{code} es tu código para confirmar esta dirección",
    "mail_reply_code_heading": "Confirma esta dirección de respuesta",
    "mail_reply_code_body": "{company} quiere que las respuestas a sus campañas "
                            "de Sobreala lleguen a esta dirección. Escribe este "
                            "código en la pantalla que lo pidió:",
    "mail_email_code_heading": "Tu código para cambiar el correo",
    "mail_email_code_body": "Alguien pidió usar esta dirección para una cuenta "
                            "de Sobreala. Escribe este código en la pantalla "
                            "que lo pidió:",
    "mail_email_code_expiry": "El código vence en {minutes} minutos. Si no "
                              "fuiste tú, no hagas nada: sin el código no "
                              "cambia nada.",
    "mail_email_code_expiry_one": "El código vence en un minuto. Si no fuiste "
                                  "tú, no hagas nada: sin el código no cambia "
                                  "nada.",

    "mail_email_changed_subject": "El correo de tu cuenta de Sobreala cambió",
    "mail_email_changed_heading": "Tu cuenta cambió de correo",
    "mail_email_changed_body": "De ahora en adelante tu cuenta de Sobreala usa "
                               "{new}. A esta dirección ya no le va a llegar "
                               "nada.",
    "mail_email_changed_write": "Si no fuiste tú, escríbenos de inmediato a "
                                "{email}: con este mensaje en la mano podemos "
                                "devolverte la cuenta.",

    "login_title": "Entra a tu cuenta",
    "login_adding_title": "Agregar una cuenta",
    "login_switched": "Cerraste tu sesión. Entra con la cuenta que quieras.",
    "login_already_open": "Esa cuenta ya está abierta en este navegador.",

    # --- las cuentas abiertas a la vez -------------------------------------
    "accounts_title": "Tus cuentas",
    "accounts_here": "Estás aquí",
    "accounts_use": "Entrar aquí",
    "accounts_drop": "Cerrar esta",
    "accounts_add": "Agregar otra cuenta",
    "accounts_full": "Caben {n} a la vez. Cierra una para poder agregar otra.",
    "accounts_back": "Volver",
    "login_email": "Correo electrónico",
    "login_password": "Contraseña",
    "login_submit": "Entrar",
    # Entrar y registrarse con Google (octubre de 2026) y con GitHub (el mismo
    # mes): los mismos textos para los dos, con el nombre de cada uno.
    "provider_google": "Google",
    "provider_github": "GitHub",
    "oauth_button": "Continuar con {provider}",
    "oauth_or": "o",
    "oauth_cancelled": "No se completó la entrada con {provider}. Vuelve a intentarlo.",
    "oauth_error": "No pudimos hablar con {provider} en este momento. Vuelve a "
                   "intentarlo en unos minutos.",
    "oauth_unverified": "Tu cuenta de {provider} no tiene el correo verificado. "
                        "Entra con tu correo y tu contraseña.",
    "oauth_other": "Ese correo ya está conectado a otra cuenta de {provider}. Entra "
                   "con esa, o con tu correo y tu contraseña.",
    "oauth_signup_title": "Completa tu cuenta",
    "oauth_signup_lead": "Entraste con {provider} como {email}. Faltan estos datos "
                         "para crear tu cuenta.",
    "oauth_on_desc": "Entras con tu cuenta de {provider}.",
    "oauth_off_desc": "Conéctalo para entrar también con tu cuenta de {provider}.",
    "oauth_on": "Conectado",
    "oauth_off": "Sin conectar",
    "oauth_disconnect": "Desconectar",
    "oauth_done_off": "Listo, desconectaste {provider}. Entras con tu correo y tu "
                      "contraseña.",
    "oauth_needs_password": "Para desconectar {provider}, crea primero una "
                            "contraseña con «¿Olvidaste tu contraseña?».",
    # Corto, para que quepa al lado de «¿Olvidaste tu contraseña?».
    "login_remember": "Recordarme 30 días",
    "login_no_account": "¿Todavía no tienes cuenta?",
    # Estando dentro de una cuenta y agregando otra, «todavía no tienes cuenta»
    # es mentira: la tiene, lo que quiere es otra.
    "login_no_account_adding": "¿Te gustaría crear otra cuenta?",
    "login_register_link": "Créala aquí",

    # Entrar y registrarse a dos columnas (octubre de 2026): el saludo, los
    # ejemplos dentro de los campos y, a la izquierda, las funciones que rotan.
    "login_hello": "Hola de nuevo",
    "login_register_short": "Regístrate",
    "login_email_placeholder": "tu@empresa.com",
    "login_password_placeholder": "Tu contraseña",
    "auth_or_email": "o con tu correo",
    "auth_tour_label": "Lo que puedes hacer con Sobreala",
    "auth_tour_pick": "Ver «{name}»",
    "auth_feature_contacts_title": "Tu lista, en orden",
    "auth_feature_contacts_text": "Importa tu archivo CSV y organízala con etiquetas.",
    "auth_feature_editor_title": "Arma tu correo",
    "auth_feature_editor_text": "Textos, botones e imágenes donde quieras.",
    "auth_feature_schedule_title": "Ahora o cuando quieras",
    "auth_feature_schedule_text": "Envía de inmediato o programa el día y la hora.",
    "auth_feature_results_title": "Mira cómo le fue",
    "auth_feature_results_text": "Aperturas, clics, rebotes y bajas de cada envío.",

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
    "close_unknown_lead": "Puede que ya lo hayas usado o que haya vencido. En "
                          "Configuración → Seguridad puedes ver y cerrar tus "
                          "dispositivos cuando quieras.",
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
    "two_step_scan_note_title": "Si ya tenías Sobreala en tu app",
    "two_step_scan_note": "Cada vez que activas la verificación el código es "
                          "nuevo, así que el anterior dejó de servir. Bórralo "
                          "de tu app antes de escanear este para evitar "
                          "confusiones.",

    "two_step_codes_title": "Guarda estos códigos de respaldo",
    "two_step_codes_lead": "Sirven para entrar si pierdes el teléfono. Cada uno "
                           "vale una sola vez.",
    "two_step_codes_hint": "Solo los verás ahora: guardamos únicamente su hash, así "
                           "que ni nosotros podemos enseñártelos otra vez. Apúntalos "
                           "en papel o en tu gestor de contraseñas.",
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
    "password_lead": "Si la cambias, se cierra la sesión en los demás "
                     "dispositivos.",
    "password_current": "Contraseña actual",
    "password_new": "Nueva contraseña",
    "password_repeat": "Repite la nueva contraseña",
    "password_submit": "Guardar la nueva contraseña",
    "password_changed_ok": "Listo, tu contraseña quedó cambiada.",
    "panel_password_link": "Cambiar mi contraseña",

    # --- settings ----------------------------------------------------------
    # La búsqueda de la barra (octubre de 2026).
    "search_label": "Buscar",
    "search_title": "Buscar",
    "search_placeholder": "Buscar",
    "search_suggestions": "Sugerencias",
    "search_none": "Nada coincide con «{q}».",
    "search_nothing": "Nada coincide.",
    "search_kind_campaign": "Campaña",
    "search_kind_run": "Envío",
    "search_kind_design": "Plantilla",
    "search_kind_tag": "Etiqueta",
    "search_page_import": "Importar contactos",
    "search_page_add_contact": "Agregar un contacto",
    "search_page_tags": "Etiquetas",
    "search_page_fields": "Columnas propias",
    "search_page_admin_stats": "Estadísticas de un cliente",
    "search_page_admin_accounts": "Cuentas",
    "search_page_admin_clients": "Clientes",
    "search_page_admin_events": "Eventos",
    "search_page_admin_mail": "Correos del sistema",
    "settings_title": "Configuración",
    "settings_section_account": "Cuenta",
    "settings_section_security": "Seguridad",
    "settings_section_notifications": "Notificaciones",
    "settings_section_payments": "Facturación",
    "settings_section_test": "Direcciones de prueba",
    # Las subsecciones de cada sección (octubre de 2026): `settings_part_<sección>_<parte>`.
    "settings_part_account_profile": "Perfil",
    "settings_part_account_contact": "Dirección y teléfonos",
    "settings_part_account_verification": "Verificación",
    "settings_part_account_plan": "Tu plan",
    "settings_part_account_delete": "Eliminar la cuenta",
    # Eliminar la cuenta y sus datos (octubre de 2026).
    "erase_row": "Eliminar la cuenta",
    "erase_row_desc": "Borra tu cuenta, tus contactos, campañas, plantillas y cifras. No se puede deshacer.",
    "erase_open": "Eliminar…",
    "erase_title": "Eliminar la cuenta",
    "erase_lead": "Esto borra tu cuenta de Sobreala y todo lo que tiene. No se puede deshacer, y nadie (tampoco nosotros) la puede recuperar.",
    "erase_gone_title": "Se borra",
    "erase_gone": [
        "Tus contactos, sus etiquetas y sus columnas.",
        "Tus campañas, tus envíos y sus cifras.",
        "Tus plantillas y sus imágenes, y los archivos que enviaste.",
        "Los usuarios de tu empresa y todas las sesiones abiertas.",
        "Tu dominio propio, que se quita de Amazon; la renovación automática, que se cancela en PayPal, y las cuentas de PayPal guardadas.",
    ],
    "erase_kept_title": "Se queda",
    "erase_kept": [
        "Las bajas y supresiones, para que nadie le vuelva a escribir a quien pidió no recibir correos.",
        "Tus pagos y facturas, porque la ley pide guardarlos.",
        "El registro de accesos y de los correos que te enviamos, por seguridad.",
    ],
    "erase_no_refund": "Si tienes un plan vigente, lo que queda de él no se reembolsa.",
    "erase_export": "¿Quieres llevarte tu lista antes? Descarga tus contactos.",
    "erase_company": "Escribe el nombre de tu empresa: {company}",
    "erase_password": "Tu contraseña",
    "erase_app_code": "El código de tu app",
    "erase_email_code": "El código que te enviamos",
    "erase_send_code": "Enviarme el código",
    "erase_code_sent": "Te enviamos un código a tu correo. Vence en unos minutos.",
    "erase_code_hint": "Entraste con Google o GitHub y no tienes contraseña: te mandamos un código a tu correo.",
    "erase_submit": "Eliminar mi cuenta para siempre",
    "erase_cancel": "Cancelar",
    "erase_error_company": "El nombre no coincide con el de tu empresa.",
    "erase_error_password": "La contraseña no es correcta.",
    "erase_error_code": "El código no es correcto o ya venció.",
    "erase_reason_self": "La eliminó su dueño desde Configuración",
    "login_deleted": "Tu cuenta y sus datos se eliminaron. Gracias por haber usado Sobreala.",
    "admin_erase_title": "Eliminar esta cuenta",
    "admin_erase_hint": "Borra la cuenta, sus usuarios y sus datos, igual que si lo hiciera el cliente: se quedan las supresiones, los pagos y las facturas, y la bitácora. No se puede deshacer.",
    "admin_erase_company": "Escribe el nombre de la empresa: {company}",
    "admin_erase_reason": "Motivo (queda en el registro)",
    "admin_erase_submit": "Eliminar la cuenta y sus datos",
    "admin_erase_error": "Escribe el nombre de la empresa tal cual y un motivo.",
    "admin_erased": "Listo, la cuenta y sus datos se eliminaron.",
    "settings_part_security_two_step": "Autenticación de múltiples factores",
    "settings_part_security_password": "Contraseña",
    "settings_part_security_users": "Usuarios",
    "settings_part_security_sessions": "Sesiones",
    "settings_part_notifications_plan": "Plan y facturación",
    "settings_part_notifications_security": "Seguridad",
    "settings_part_notifications_clients": "Clientes",
    "settings_part_billing_plan": "Tu plan",
    "settings_part_billing_methods": "Métodos de pago",
    "settings_part_billing_auto_renewal": "Renovación automática",
    "settings_part_billing_history": "Historial de compras",
    "settings_part_test_addresses": "Direcciones de prueba",
    "settings_verify_lead": "Verificamos tu identificación y tu dirección una sola "
                            "vez, con un documento de cada una. Los mira una "
                            "persona de Sobreala y el archivo se borra al decidir.",
    "test_lead": "En la demostración puedes enviar campañas y correos de verdad, pero "
                 "solo a estas direcciones: hasta {n}, y {total} correos en total. "
                 "Así ves quién lo abrió y quién hizo clic, como con tu lista. Cada "
                 "una se confirma con un enlace que le llega a ese buzón.",
    "test_left": "Te quedan {left} de {total} correos de prueba.",
    "test_sent": "Listo, le mandamos el enlace de confirmación. Cuando lo abra, "
                 "ya le puedes enviar.",
    "test_error_email": "Esa no es una dirección de correo.",
    "test_error_wait": "Mandaste muchos enlaces seguidos. Espera un rato.",
    "test_error_full": "Ya tienes esa dirección, o ya tienes las {n}.",
    "test_confirmed": "Confirmada: recibe tus correos de prueba.",
    "test_waiting": "Le mandamos el enlace; falta que lo abra.",
    "test_state_on": "Confirmada",
    "test_state_waiting": "Sin confirmar",
    "test_remove": "Quitar",
    "test_add_label": "Una dirección de prueba",
    "test_add": "Agregar",
    "test_address_consent": "Dirección de prueba de la demostración, confirmada "
                            "desde su buzón.",
    "test_page_title": "Dirección de prueba",
    "test_page_ok": "Listo: {email} va a recibir los correos de prueba de "
                    "{company} en Sobreala.",
    "test_page_bad": "Este enlace ya se usó o venció. Pide uno nuevo desde "
                     "Configuración.",

    # El logo de la empresa (octubre de 2026).
    "settings_logo": "Logo de la empresa",
    "settings_logo_hint": "Se ve arriba como foto de perfil, en un círculo (uno "
                          "cuadrado se ve mejor), y lo puedes poner entero en tus "
                          "plantillas y correos. PNG, JPG o WebP de hasta 5 MB.",
    "settings_logo_pick": "Elegir imagen",
    "settings_logo_none_chosen": "Ninguna elegida",
    "settings_logo_upload": "Subir logo",
    "settings_logo_change": "Cambiar logo",
    "settings_logo_remove": "Quitar logo",
    "settings_logo_saved": "Listo, guardamos tu logo.",
    "settings_logo_removed": "Listo, quitamos tu logo.",
    "settings_logo_error_required": "Elige una imagen para subir.",
    "settings_logo_error_heavy": "Esa imagen pesa más de 5 MB. Prueba con una más liviana.",
    "settings_logo_error_kind": "Esa imagen no se pudo leer. Sube un PNG, un JPG o un WebP.",
    "settings_account_contact": "Tu nombre",
    "settings_account_company": "Empresa u organización",
    "settings_account_email": "Correo",
    "settings_account_email_pending": "Sin confirmar",
    "settings_account_email_change": "Cambiar",
    "settings_account_to_billing": "Ir a facturación",
    "settings_account_email_done": "Listo, tu correo cambió. Le avisamos a la "
                                   "dirección anterior.",
    "settings_postal": "Dirección postal",
    "settings_postal_placeholder": "Calle, ciudad, provincia",
    "settings_postal_save": "Guardar",
    "settings_postal_done": "Listo, tu dirección quedó guardada.",
    "admin_postal_missing": "Todavía no la escribió",
    "settings_postal_bad": "Escribe una dirección de entre {min} y {max} "
                           "caracteres.",
    # La palabra corta del estado, que enseña el administrador en la ficha y en
    # Cuentas; la frase larga que la explica es panel_status_*. El cliente ya no
    # la ve (octubre de 2026): solo podía decir «Registrada» o «Activa».
    "status_short_registered": "Registrada",
    "status_short_active": "Activa",
    "status_short_suspended": "Suspendida",
    "settings_account_plan": "Tu plan",
    "settings_account_no_plan": "Sin plan contratado",
    "settings_account_no_plan_hint": "Puedes preparar tus contactos y armar "
                                     "campañas sin plan. Para enviarlas de "
                                     "verdad hace falta uno.",
    "settings_account_closed_hint": "Tu cuenta se abre con la demostración o "
                                    "al contratar un plan.",
    # El aviso amarillo de arriba de Cuenta, mientras falte verificar algo.
    "settings_pending_title": "Pendiente de verificación:",
    "settings_pending_text": "necesitamos un documento de tu identificación y "
                             "otro de tu dirección.",
    "settings_pending_link": "Enviar los documentos",
    # La cuenta limitada por el administrador: entra, pero no envía.
    "settings_limited_title": "Tu cuenta está limitada.",
    "settings_limited_verification": "Para enviar necesitamos verificar tu "
                                     "identificación y tu dirección.",
    "settings_limited_link": "Enviar los documentos",
    # La pausa automática por rebotes o quejas: tampoco envía.
    "settings_paused_title": "Tus envíos están en pausa.",
    "settings_limited_bounces": "Demasiados de tus correos rebotaron porque esas "
                                "direcciones no existen. Te escribimos con el "
                                "detalle, y lo revisamos contigo antes de volver "
                                "a enviar.",
    "settings_limited_complaints": "Varias personas marcaron tus correos como "
                                   "spam. Te escribimos con el detalle, y lo "
                                   "revisamos contigo antes de volver a enviar.",
    # Las filas de Cuenta se ven como texto y se cambian con «Editar».
    "settings_edit": "Editar",
    "settings_cancel": "Cancelar",
    "settings_postal_missing": "Falta",
    # Los teléfonos y la identificación, que se cambian aquí.
    "settings_phones": "Teléfonos",
    "settings_phones_done": "Listo, tus teléfonos quedaron guardados.",
    # Las verificaciones: la identificación y la dirección, cada una con su
    # documento, que mira una persona de Sobreala.
    "verification_title": "Verifica tu cuenta",
    "verification_lead": "Para enviar campañas necesitamos comprobar quién está "
                         "detrás de la cuenta. Sube un documento de cada cosa y "
                         "los revisamos. Una vez revisados los borramos.",
    "verify_title": "Verificaciones",
    "verify_name_identity": "Identificación personal",
    "verify_name_address": "Dirección",
    "verify_hint_identity": "Foto o PDF de tu cédula o pasaporte.",
    "verify_hint_address": "Un recibo de luz, agua o teléfono, tu aviso de "
                           "operación, o un documento legal que certifique tu "
                           "dirección si tu empresa no está constituida.",
    "verify_what_identity": "identificación personal",
    "verify_what_address": "dirección",
    "verify_status_missing": "Falta el documento",
    "verify_status_review": "En revisión",
    "verify_status_verified": "Verificada",
    "verify_status_rejected": "Rechazada",
    "verify_rejected_reason": "Motivo: {reason}. Sube otro documento.",
    "verify_send": "Enviar documentos",
    "verify_sent": "Recibimos tus documentos. Te avisamos cuando los revisemos.",
    "verify_nothing_due": "Ya enviaste todo lo que hacía falta.",
    "verify_back": "Volver a Configuración",
    "verify_bad": "Tiene que ser un PDF, JPG o PNG de hasta {mb} MB.",
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
    "users_email_taken": "Ese correo ya tiene una cuenta en Sobreala. Usa "
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
    "users_can_designs_desc": "El editor de plantillas.",
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
    "invite_lead": "{company} te dio entrada a su cuenta de Sobreala. Elige "
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
                                          "Pagar le abre la cuenta y le deja "
                                          "enviar, así que no queda nada "
                                          "pendiente.",
    "settings_notice_admin_signup": "Se registró una cuenta nueva",
    "settings_notice_admin_signup_desc": "Cuando alguien confirma su correo y la "
                                         "cuenta queda creada de verdad. Los "
                                         "registros a medias no avisan nada.",
    "settings_notice_admin_demo": "Alguien pidió una demostración",
    "settings_notice_admin_demo_desc": "Cuando una cuenta la pide desde su "
                                       "bienvenida, con su WhatsApp y su RUC o "
                                       "cédula. Es la que espera que la abras.",
    "settings_notice_admin_plan_end": "A un cliente se le venció el plan",
    "settings_notice_admin_plan_end_desc": "Se mira cuando el cliente entra a su "
                                           "cuenta, así que de quien no vuelve a "
                                           "entrar no se entera nadie hasta que "
                                           "exista el proceso automático.",
    "settings_notice_admin_pause": "Sobreala pausó a un cliente",
    "settings_notice_admin_pause_desc": "Por rebotes o quejas por encima del "
                                        "umbral. La pausa solo la quitas tú, "
                                        "desde su ficha.",
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
    "billing_until": "vence el {when}",
    "billing_methods_title": "Métodos de pago",
    "billing_paypal_used": "Has pagado con la cuenta de PayPal {who}.",
    "billing_paypal_used_plain": "Has pagado con tu cuenta de PayPal.",
    "billing_invoices_title": "Facturas",
    "billing_history_title": "Historial de compras",
    "billing_download": "Descargar factura",
    "billing_invoice_pending": "Factura en camino",
    "billing_invoices_hint": "Te avisamos por correo cuando tu factura está "
                             "lista para descargar.",
    "billing_invoices_none": "Todavía no tienes pagos.",
    # Solo se enseña lo guardado (octubre de 2026).
    "methods_none": "No tienes métodos de pago guardados.",
    "methods_add": "Agregar método de pago",
    "methods_add_this": "Agregar",
    "methods_dialog_title": "Agregar un método de pago",
    "methods_dialog_close": "Cerrar",
    "methods_unavailable": "No disponible",
    "methods_paypal_remove": "Eliminar",
    "methods_paypal_saved": "Listo, guardamos tu cuenta de PayPal.",
    "methods_paypal_removed": "Listo, quitamos tu cuenta de PayPal.",

    # --- pagos -------------------------------------------------------------
    "pay_checkout_title": "Obtener Plan {plan}",
    # El resumen de lo que se va a pagar.
    "pay_summary_plan": "Plan {plan}, {cycle}",
    "pay_summary_cycle_monthly": "un mes",
    "pay_summary_cycle_yearly": "un año",
    "pay_summary_credit": "Descuento por los correos sin usar",
    "pay_summary_credit_detail": "{unused} de {emails} correos de este mes",
    "pay_summary_credit_months": "{unused} de {emails} correos de este mes, y "
                                 "{months} meses que te quedaban",
    "pay_summary_total": "Total a pagar ahora",
    "pay_summary_tax": "ITBMS ({rate}%)",
    "pay_summary_switch_yearly": "Prefiero pagar un año: {amount}",
    "pay_summary_switch_monthly": "Prefiero pagar un mes: {amount}",
    "pay_summary_upgrade": "Al mejorar, tu plan nuevo empieza hoy con su mes "
                           "completo, y los correos que no usaste se descuentan.",
    "pay_button": "Pagar {amount}",
    "pay_yearly_only": "Tienes un plan anual: se mejora a otro plan anual.",
    # El recibo, al volver de un pago cobrado.
    "receipt_title": "Tu pago se completó",
    "receipt_number": "Número de pago",
    "receipt_plan": "Plan",
    "receipt_method": "Método de pago",
    "receipt_when": "Fecha y hora",
    "receipt_total": "Total pagado",
    "receipt_button": "Ir a mi cuenta",
    "pay_running": "Ya tienes este plan hasta el {when}. Cuando venza lo "
                   "vuelves a contratar aquí.",
    "pay_running_undated": "Ya tienes este plan. Cuando venza lo vuelves a "
                           "contratar aquí.",
    "pay_back_to_plans": "Ver todos los planes",
    "pay_downgrade": "Ya tienes un plan mayor que este. Bajar de plan no se "
                     "hace desde aquí: escríbenos y lo vemos contigo, porque "
                     "hay que ajustar lo que ya pagaste.",
    "pay_choose": "Contratar un plan",
    "pay_choose_lead": "El pago se hace en la página de PayPal. Al volver, tu "
                       "cuenta queda activa al momento.",
    "pay_prices": "${month} al mes · ${year} al año, con {off}% de descuento.",
    # Con qué se paga. Los tres se enseñan siempre: esconder los que faltan
    # haría que quien no tiene PayPal cerrara la página creyendo que no puede
    # pagar de ninguna forma.
    "pay_method_title": "Cómo quieres pagar",
    "pay_method_soon": "Pronto",
    "pay_other_method": "Utilizar otra cuenta o método de pago",
    # Las columnas del historial de compras.
    "billing_col_date": "Fecha",
    "billing_col_plan": "Plan",
    "billing_col_cycle": "Periodo",
    "billing_col_method": "Método",
    "billing_col_amount": "Monto",
    "billing_col_invoice": "Factura",
    "pay_method_paypal": "PayPal",
    "pay_method_card": "Tarjeta de crédito o débito",
    "pay_card_ending": "terminada en {last4}",
    "pay_method_yappy": "Yappy",
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
    "pay_error_status": "Tu cuenta todavía no puede contratar un plan. Confirma tu correo, o escríbenos si está suspendida.",
    "pay_error_plan": "Ese plan no se contrata por aquí.",
    "pay_error_paypal": "No pudimos hablar con PayPal en este momento. "
                        "Vuelve a intentarlo en unos minutos.",
    "pay_error_card": "No pudimos hablar con Paguélofácil en este momento. "
                         "Si ya pagaste, en unos minutos se activa solo; si "
                         "no, vuelve a intentarlo.",
    "pay_error_cancelled": "Cancelaste el pago. No se cobró nada.",
    "pay_error_order": "No encontramos ese pago. Si te cobraron, escríbenos "
                       "con la fecha y lo revisamos.",
    "pay_error_capture": "El pago no se confirmó, así que no activamos nada. Si "
                       "te cobraron, escríbenos.",
    "pay_error_amount": "El monto cobrado no coincide con el del plan, así que "
                       "no activamos nada. Escríbenos y lo revisamos.",
    "settings_payments_hint": "Sobreala nunca guarda tus datos de pago.",

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
    "stats_period_today": "Hoy",
    "stats_period_24h": "Últimas 24 horas",
    "stats_period_7d": "Últimos 7 días",
    "stats_period_30d": "Últimos 30 días",
    "stats_period_90d": "Últimos 90 días",
    "stats_week_of": "Semana del {day}",
    "stats_campaign": "Campaña",
    "stats_all_campaigns": "Todas las campañas",
    "stats_rates_title": "Cómo le fue",
    "stats_rate_of": "{n} de {of}",
    # La pastilla del cambio. «Mejor» y «peor» y no «subió» y «bajó»: más
    # rebotes es peor aunque la flecha apunte arriba.
    "stats_change_up": "{pct} % más que en el periodo anterior",
    "stats_change_down": "{pct} % menos que en el periodo anterior",
    "stats_change_note": "Las pastillas comparan con {antes}. Verde es que "
                         "mejoró y rojo que empeoró, así que más rebotes, más "
                         "quejas o más bajas van en rojo aunque la flecha "
                         "suba. Donde antes no hubo envíos no hay con qué "
                         "comparar y no sale pastilla.",
    # Contra qué compara cada periodo: el mismo tramo, justo antes.
    "stats_before_1h": "la hora anterior",
    "stats_before_today": "ayer hasta esta misma hora",
    "stats_before_24h": "las 24 horas anteriores",
    "stats_before_7d": "los 7 días anteriores",
    "stats_before_30d": "los 30 días anteriores",
    "stats_before_90d": "los 90 días anteriores",
    "stats_rates_note": "Se cuentan personas: quien abre tres veces cuenta una. "
                        "Las aperturas son aproximadas (algunos buzones abren "
                        "solos los correos y otros no avisan), y «entregado» "
                        "quiere decir que el servidor de la persona lo aceptó, "
                        "no que haya llegado a su bandeja.",
    "stats_engage_title": "Aperturas y clics",
    "stats_engage_lead": "Cuántas personas abrieron tus correos y cuántas hicieron "
                         "clic en un enlace en el periodo que elijas. Quien abre tres "
                         "veces cuenta una.",
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
    "stats_leave": "Bajas",
    "stats_leaves_off": "Las bajas no se cuentan con un filtro puesto: el "
                        "enlace de baja sabe quién se fue, no de qué campaña. "
                        "Quita el filtro de etiqueta o de campaña para verlas.",

    # Tus mejores campañas.
    "stats_best_title": "Tus mejores campañas",
    "stats_best_lead": "Los envíos del periodo, del que más abrieron al que "
                       "menos. Pulsa uno para ver a quién le llegó.",
    "stats_best_subject": "Asunto",
    "stats_best_when": "Cuándo salió",
    "stats_best_sent": "Salieron",
    "stats_best_open": "Aperturas",
    "stats_best_click": "Clics",
    "stats_best_none": "En este periodo no salió ninguna campaña.",

    # Bajarse lo que enseña la pantalla.
    "export_title": "Estadísticas de Sobreala",
    "export_account": "Cuenta",
    "export_compared": "Comparado con",
    "export_made": "Generado",
    "export_figure": "Cifra",
    "export_value": "Valor",
    "export_of": "De cuántos",
    "export_change": "Cambio",
    "export_slot": "Tramo",
    "export_csv": "Bajar CSV",
    "export_pdf": "Bajar PDF",

    # Enlaces más pulsados.
    "stats_links_title": "Enlaces con más clics",
    "stats_links_lead": "Cuántas personas hicieron clic en cada enlace en el periodo. "
                        "Quien hace clic en el mismo tres veces cuenta una.",
    "stats_links_who": "Personas",
    "stats_links_none": "Todavía no hay clics con su enlace anotado. Se "
                        "empieza a guardar desde ahora: los clics de antes no "
                        "traían la dirección.",

    # Cuándo abren tus correos.
    "stats_when_title": "Cuándo abren tus correos",
    "stats_when_lead": "De los últimos 90 días, sin importar el periodo que "
                       "elijas arriba: es para decidir cuándo mandar, y con "
                       "una hora de datos eso no se puede decir.",
    "stats_when_days": "Por día de la semana",
    "stats_when_hours": "Por hora del día",
    "stats_when_best": "Tu lista abre más los {day} y alrededor de las {hour}.",
    "stats_when_few": "Con pocos envíos esto todavía no dice gran cosa: se "
                      "afina solo a medida que mandes más.",
    "stats_when_none": "Todavía no hay aperturas en los últimos 90 días.",

    # Crecimiento de la lista.
    "stats_growth_title": "Crecimiento de la lista",
    "stats_growth_lead": "Cuántos contactos entraron y a cuántos se dejó de "
                         "escribir cada mes, en los últimos doce.",
    "stats_added": "Entraron",
    "stats_left": "Se fueron",
    "stats_growth_note": "Las bajas incluyen los rebotes duros y las quejas, no solo "
                         "a quien hizo clic en el enlace de baja. Y borrar un "
                         "contacto a mano no queda anotado, así que esto son altas y "
                         "bajas, no el total de cada mes.",
    "stats_growth_none": "Todavía no hay altas ni bajas que enseñar.",
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
    "panel_status_registered": "Registrada: todavía sin plan.",
    "panel_status_active": "Activa.",
    "panel_status_suspended": "Suspendida. Escríbenos para revisarla.",

    # --- contacts ----------------------------------------------------------
    "contacts_title": "Contactos",
    "contacts_tab_list": "Tus contactos",
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
    # Por la API (octubre de 2026).
    "contacts_how_api": "Por la API",
    "contacts_status_active": "Activo",
    "contacts_status_blocked": "Anulado",
    "contacts_status_incomplete": "Incompleto",
    "contacts_status_invalid": "Dirección inválida",
    "contacts_invalid_why": "Su dominio no recibe correo. No se le envía nada y "
                            "no gasta correos de tu plan.",
    "contacts_invalid_notice": "Tienes {n} contactos con una dirección inválida "
                               "(su dominio no recibe correo).",
    "contacts_invalid_see": "Verlas",
    "contacts_invalid_lead": "Estas {n} direcciones son de un dominio que no "
                             "recibe correo: cualquier envío rebotaría. No "
                             "sabemos si un buzón existe en un dominio bueno; "
                             "eso solo lo dice el rebote, que las anula solo.",
    "contacts_invalid_delete": "Borrar las {n}",
    "contacts_invalid_back": "Volver a todos",
    "contacts_undeliverable": "{domain} no recibe correo, así que esa dirección "
                              "rebotaría. Revisa cómo está escrita.",
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
    "fields_name_hint": "Con este nombre la vas a reconocer, y de él sale la variable "
                        "que se escribe dentro de la pieza.",
    "fields_new_warning": "Ojo: tus {n} contactos se quedan sin este dato, y "
                          "mientras les falte no reciben correos. Se completan "
                          "editándolos o volviendo a importar el archivo con "
                          "esa columna.",
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
    # La revisión de direcciones (services/address_check.py).
    "import_undeliverable": "De un dominio que no recibe correo",
    "import_undeliverable_hint": "Entraron marcadas como inválidas: al enviar se "
                                 "saltan y no gastan correos de tu plan. Lo mejor "
                                 "es borrarlas.",
    "import_typos": "Parecen mal escritas",
    "import_typos_hint": "Entraron como están; revísalas por si les falta o les "
                         "sobra una letra:",
    "import_typo_maybe": "¿{better}?",
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
    "blocked_empty": "No hay ninguna. Es lo normal al empezar.",
    "blocked_col_email": "Correo",
    "blocked_col_reason": "Motivo",
    "blocked_col_when": "Desde",
    "blocked_reason_unsubscribe": "Baja",
    "blocked_reason_hard_bounce": "Rebote",
    "blocked_reason_complaint": "Queja",
    "blocked_reason_manual": "Manual",

    "menu_admin": "Administración",

    # --- plantillas --------------------------------------------------------
    # Para el cliente son «plantillas»; en el código son «designs», porque
    # `templates/` en este proyecto ya son las plantillas Jinja del panel.
    "designs_title": "Plantillas",
    # Cargar el ZIP de un lienzo vive en el Lienzo (octubre de 2026): cargarlo
    # es abrir un lienzo.
    "designs_upload_button": "Cargar plantilla (ZIP)",
    "designs_kind_upload": "HTML cargado, {kb} KB",
    # Las diapositivas se quitaron en septiembre de 2026: ahora es una hoja.
    "designs_kind_sheet": "Hecha en el editor",
    "designs_copy": "Duplicar",
    "designs_copy_name": "Copia de {name}",
    "designs_copied": "Listo, ahí tienes la copia.",
    "designs_close": "Cerrar",
    "designs_html_lead": "Cambia el código a la izquierda y mira a la derecha "
                         "cómo queda. Para poner el dato de cada persona, pulsa "
                         "una columna y se escribe donde tengas el cursor.",
    "designs_html_code": "Código HTML",
    # Las imágenes del HTML y de dónde sale cada una.
    "designs_pictures_title": "Imágenes de esta plantilla",
    "designs_pictures_warn": "{n} no son de tu cuenta. Cámbialas por una tuya "
                             "para que la plantilla no dependa de nadie.",
    "designs_pictures_warn_one": "Una no es de tu cuenta. Cámbiala por una tuya "
                                 "para que la plantilla no dependa de nadie.",
    "designs_picture_ok": "De tu cuenta.",
    "designs_picture_outside": "De otro sitio: se ve mientras ese sitio la "
                               "publique.",
    "designs_picture_other": "De otra cuenta: sale rota el día que esa cuenta "
                             "la borre.",
    "designs_picture_gone": "Ya no existe: sale rota.",
    "designs_picture_inside": "Dentro del archivo: Gmail no la muestra y pesa.",
    "designs_picture_change": "Cambiar",
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
    "designs_preview_button": "Previsualización",
    "designs_preview_empty": "Llena la plantilla y pulsa «{boton}» para verla "
                             "aquí.",
    # Las dos van inyectadas al enviar y no dentro de la pieza, así que se
    # explican aquí para que nadie las busque en el formulario.
    "designs_preview_note": "El botón de anular la suscripción se agrega solo, "
                            "en todos los planes.",
    "designs_preview_watermark": "Tu plan lleva la marca «Enviado con "
                                 "Sobreala» al pie. Desaparece sola al subir "
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
    "designs_upload_title": "Cargar plantilla",
    "designs_upload_hint": "El ZIP que baja el editor con «Descargar ZIP», de "
                           "esta cuenta o de otra. Se abre en el editor tal "
                           "como estaba, para seguir trabajándola, y sus fotos "
                           "entran a tu cuenta.",
    # El ZIP que baja el editor: el lienzo con sus fotos, y el HTML aparte.
    "designs_only_zip": "Solo se cargan los ZIP que baja el editor. Las "
                        "plantillas se arman en el editor: el HTML propio ya "
                        "no se carga.",
    "designs_zip_broken": "No se pudo abrir el ZIP. Vuelve a bajarlo del "
                          "editor.",
    "designs_zip_no_canvas": "Ese ZIP no trae una plantilla del editor. Bájala "
                             "otra vez con «Descargar ZIP».",
    "designs_zip_canvas_bad": "La plantilla del ZIP no se pudo leer. Bájala otra "
                              "vez del editor.",
    "designs_zip_too_many": "El ZIP trae más de {n} fotos.",
    "designs_zip_heavy": "Las fotos del ZIP pesan demasiado: cada una "
                         "puede pesar hasta {mb} MB.",
    "designs_zip_missing": "La plantilla nombra {what} y el ZIP no la trae.",
    "designs_zip_limit": "Trae {n} fotos y te caben {free} de {limit}. Borra "
                         "alguna plantilla que ya no uses.",
    "designs_file": "Archivo",
    "designs_name": "Nombre",
    "designs_name_hint": "Para reconocerla después. Si lo dejas vacío, se "
                         "queda con el que traía.",
    "designs_submit": "Cargar",
    "designs_saved": "Listo, ya la puedes usar.",
    "designs_delete": "Eliminar",

    # Las carpetas de Mis plantillas (octubre de 2026).
    "folders_title": "Carpetas",
    "folders_loose": "Sin carpeta",
    "folders_new": "Nueva carpeta",
    "folders_name": "Nombre",
    "folders_color": "Color",
    "folders_save": "Guardar",
    "folders_cancel": "Cancelar",
    "folders_count_none": "Vacía",
    "folders_count_one": "1 plantilla",
    "folders_count": "{n} plantillas",
    "folders_open_aria": "Abrir la carpeta {name}, {count}",
    "folders_peek_aria": "Las más recientes de {name}",
    "folders_menu_aria": "Opciones de {name}",
    "folders_open": "Abrir",
    "folders_rename": "Cambiar nombre",
    "folders_recolor": "Cambiar color",
    "folders_delete": "Eliminar",
    "folders_new_title": "Nueva carpeta",
    "folders_rename_title": "Cambiar el nombre de",
    "folders_recolor_title": "Cambiar el color de",
    "folders_delete_title": "Eliminar",
    "folders_delete_lead": "Sus plantillas no se borran: quedan en Mis "
                           "plantillas, sin carpeta.",
    "folders_delete_confirm": "Eliminar la carpeta",
    "folders_back": "Mis plantillas",
    "folders_empty": "Esta carpeta está vacía. Para llenarla, usa «Mover a…» "
                     "en una plantilla, o elígela al guardar en el Lienzo.",
    "folders_done_new": "Listo, ya tienes la carpeta.",
    "folders_done_name": "Listo, se cambió el nombre.",
    "folders_done_color": "Listo, se cambió el color.",
    "folders_done_deleted": "Listo, se eliminó la carpeta. Sus plantillas "
                            "quedaron sin carpeta.",
    "folders_done_moved": "Listo, se movió la plantilla.",
    "folders_done_moved_many": "Listo, se movieron {n} plantillas.",
    # Arrastrar plantillas hasta una carpeta (octubre de 2026): lo que dice la
    # tarjetita que sigue al ratón.
    "folders_drag_move_to": "Mover a «{name}»",
    "folders_drag_out": "Sacar de la carpeta",
    "folders_loose_empty": "Todas tus plantillas están en carpetas.",
    "folders_error_taken": "Ya tienes una carpeta con ese nombre.",
    "folders_error_full": "Ya tienes {n} carpetas, que es el máximo.",
    "folders_error_color": "Elige uno de los colores.",
    "folders_move": "Mover a…",
    "folders_move_none": "Sin carpeta",
    "folders_color_gray": "Gris",
    "folders_color_white": "Blanco",
    "folders_color_blue": "Azul",
    "folders_color_green": "Verde",
    "folders_color_amber": "Ámbar",
    "folders_color_red": "Rojo",
    "folders_color_purple": "Morado",
    "folders_color_pink": "Rosa",
    "folders_color_teal": "Turquesa",
    # La lista del Lienzo, junto al nombre.
    "canvas_folder": "Carpeta",
    # De quién sale cada plantilla y a dónde se responde (octubre de 2026).
    "designs_send_from": "Sale de",
    "designs_reply_to": "Responder a",
    "designs_send_default": "El predeterminado: {what}",
    "designs_sending_hint": "Si no eliges otros, sale del remitente "
                            "predeterminado y las respuestas llegan a la "
                            "dirección predeterminada.",
    "designs_sending_link": "Ver Remitente",
    "designs_size": "{kb} KB",

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
    # Las imágenes de otro sitio sí entran si van por https://: lo que no entra
    # es una hoja de estilos de fuera, ni una imagen por http://.
    "designs_bad_external": "Trae una hoja de estilos de otro sitio, o una "
                            "imagen que no va por https://. Un estilo de fuera "
                            "puede cambiar después sin que nadie lo vea.",

    # --- el lienzo de crear ---------------------------------------------------
    "canvas_title_new": "Plantilla nueva",
    "canvas_lead": "Agrega texto, botones, imágenes y figuras y ponlos donde "
                   "quieras. El alto de la hoja lo pones tú: escríbelo arriba "
                   "o arrastra su borde de abajo. Las imágenes y las figuras "
                   "van atrás, con el texto y los botones encima.",
    "canvas_noscript": "El editor necesita JavaScript. Actívalo en tu "
                       "navegador para crear plantillas.",
    "canvas_narrow": "El editor se usa mejor en una computadora: en una "
                     "pantalla angosta el lienzo no cabe entero.",
    "canvas_add": "Agregar",
    "canvas_add_text": "Texto",
    "canvas_add_button": "Botón",
    "canvas_add_image": "Imagen",
    "canvas_add_logo": "Mi logo",
    "canvas_logo_none": "Tu empresa todavía no tiene logo. Súbelo en Configuración, en Cuenta.",
    "canvas_add_shape": "Geometría",
    "canvas_image_hint": "JPG, PNG, GIF o WebP, hasta {mb} MB. Entra debajo de "
                         "lo último, a la mitad del ancho. Los bordes "
                         "transparentes se recortan solos.",
    "canvas_marks_hint": "Haz doble clic en un texto y pulsa una columna: se "
                         "escribe donde está el cursor.",
    "canvas_marks_need": "Primero haz doble clic en un texto, o pon el cursor "
                         "en el texto del botón.",
    "canvas_keys": "Atajos del teclado",
    "canvas_props_none": "Haz clic en algo para cambiarlo. Doble clic en un "
                         "texto para escribir. Con Mayús pulsas varios, y "
                         "arrastrando sobre la hoja los encierras.",
    "canvas_rights": "Sube solo imágenes de las que tengas derechos: respondes "
                     "por ellas. También puedes pegar una con Ctrl+V.",
    "canvas_page_bg": "Color de la hoja",
    "canvas_sheet_h": "Alto de la hoja",
    "canvas_sheet_least": "La hoja no puede quedar por debajo de lo que tiene "
                          "dentro: se quedó en {px} px.",
    "canvas_fit_content": "Ajustar al contenido",
    "canvas_pdf": "Descargar PDF",
    "canvas_html": "Descargar ZIP",
    "canvas_html_save_first": "Guárdala antes de bajarla: el ZIP es la "
                              "plantilla guardada, lista para cargarla en esta "
                              "cuenta o en otra y seguir trabajándola.",
    "canvas_shape_bg": "Color",
    "canvas_shape_kind": "Figura",
    "canvas_shape_rect": "Rectángulo",
    # «Línea» y no «Línea divisoria»: se gira, así que también es vertical o
    # diagonal.
    "canvas_shape_line": "Línea",
    "canvas_line_width": "Grosor",
    "canvas_shape_ellipse": "Círculo",
    "canvas_shape_triangle": "Triángulo",
    "canvas_shape_star": "Estrella",
    "canvas_shape_arrow": "Flecha",
    "canvas_rot": "Giro",
    "canvas_rot_zero": "Enderezar",
    "canvas_shape_tip": "Esta figura viaja como imagen: el correo no sabe "
                        "dibujarla, y eso suma a la parte del correo que es "
                        "imagen. El rectángulo y la línea no.",
    "canvas_rot_drag": "Arrastra para girar (con Mayús, de 15 en 15)",
    "canvas_text_cut": "Un texto no cabe en la hoja y se ve cortado aquí. En "
                       "el correo sale entero y empuja lo de abajo: hazla más "
                       "alta o acorta el texto.",
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
    "canvas_list": "Viñetas",
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
    "canvas_crop": "Recortar",
    "canvas_uncrop": "Quitar el recorte",
    "canvas_crop_how": "Arrastra el recuadro para elegir qué parte se ve, y "
                       "sus esquinas para acercar o alejar. Pulsa Esc o fuera "
                       "de la foto cuando termines.",
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

    # Varios elegidos a la vez: moverlos juntos, alinearlos y agruparlos.
    "canvas_many": "{n} elementos elegidos",
    "canvas_group": "Agrupar",
    "canvas_ungroup": "Desagrupar",
    "canvas_group_hint": "Agrupar es para moverlos juntos. No cambia cómo se "
                         "arma el correo: eso lo deciden las cajas que se "
                         "enciman.",
    # Cortas a propósito: van en fila debajo de «Alinear», y con el nombre
    # largo la barra se llenaba de botones que no cabían.
    "canvas_align_many": "Alinear",
    "canvas_align_l": "Izquierda",
    "canvas_align_cx": "Centro",
    "canvas_align_r": "Derecha",
    "canvas_align_t": "Arriba",
    "canvas_align_cy": "Medio",
    "canvas_align_b": "Abajo",
    "canvas_spread_x": "Repartir ancho",
    "canvas_spread_y": "Repartir alto",
    "canvas_duplicate": "Duplicar",
    "canvas_copied": "Copiado. Pégalo con Ctrl+V, aquí o en otra plantilla.",
    "canvas_paste_url": "Eso es la dirección de una imagen, no la imagen. "
                        "Descárgala y súbela con el botón de imagen.",
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
    "canvas_bad_alt": "A una imagen le falta la descripción. Es lo que se lee "
                      "cuando el buzón bloquea las imágenes, así que sin ella "
                      "no se guarda.",
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
    "canvas_bad_line": "El grosor de una línea tiene que ir de 1 a 12 px.",
    "canvas_bad_too_big": "El correo pasa de {kb} KB. Quita algo de "
                          "texto.",

    # Lo que tiene riesgo de ir a spam. Con cualquiera, no se guarda.
    "canvas_spam_few_text": "Tiene muy poco texto ({n} caracteres). Escribe al "
                            "menos {min}: un correo casi sin texto es de lo que "
                            "más va a spam.",
    "canvas_spam_image_heavy": "Las imágenes ocupan el {pct} % del correo. Que "
                               "sean como mucho el {max} %: el resto, texto.",
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

    # La ventana de requisitos: todo lo que se mira antes de guardar, con lo que
    # se cumple y lo que no. Cada frase dice la regla y, si hay cifra, cómo va.
    "canvas_rules_button": "Requisitos para guardar",
    "canvas_rules_title": "Requisitos para guardar",
    "canvas_rules_lead": "Todo lo que se revisa antes de guardar. Se actualiza "
                         "mientras trabajas.",
    "canvas_rules_count": "Cumple {ok} de {n}.",
    "canvas_rules_wait": "Revisando…",
    "canvas_rules_build": "Para armar el correo",
    "canvas_rules_spam": "Para no ir a spam",
    "canvas_rule_yes": "Cumple:",
    "canvas_rule_no": "No cumple:",
    "canvas_rule_name": "Tiene nombre.",
    "canvas_rule_empty": "Tiene al menos un elemento.",
    "canvas_rule_height": "La hoja mide entre {min} y {max} px (ahora {h} px).",
    "canvas_rule_too_many_items": "Tiene como mucho {max} elementos (ahora {n}).",
    "canvas_rule_bounds": "Nada se sale de la hoja.",
    "canvas_rule_image": "Todas las imágenes son de tu cuenta.",
    "canvas_rule_alt": "Cada imagen tiene su descripción.",
    "canvas_rule_href": "Los enlaces empiezan por https:// o mailto:.",
    "canvas_rule_font": "Las fuentes son de las que funcionan en todos los "
                        "correos.",
    "canvas_rule_size": "La letra mide entre {min} y {max} px.",
    "canvas_rule_text_long": "Cada texto tiene como mucho {max} caracteres.",
    "canvas_rule_button_text": "Cada botón tiene texto, de hasta {max} "
                               "caracteres.",
    "canvas_rule_line": "Las líneas miden de {min} a {max} px de grosor.",
    "canvas_rule_overlap": "No hay textos ni botones encimados.",
    "canvas_rule_tangled": "Nada queda en molinillo, rodeándose sin tocarse.",
    "canvas_rule_link_overlap": "Ninguna imagen con enlace tiene algo encima.",
    "canvas_rule_few_text": "Al menos {min} caracteres de texto (tiene {n}).",
    "canvas_rule_image_heavy": "Las imágenes ocupan como mucho el {max} % del "
                               "correo (ahora el {pct} %).",
    "canvas_rule_too_big": "Pesa como mucho {max} KB (ahora {kb} KB).",
    "canvas_rule_many_links": "Como mucho {max} enlaces entre botones e "
                              "imágenes (tiene {n}).",
    "canvas_rule_shortener": "Ningún enlace acortado (bit.ly y parecidos).",
    "canvas_rule_caps": "Menos del {max} % de las letras en mayúscula.",
    "canvas_rule_shouting": "Sin signos repetidos (!! o ¡¡) ni más de tres "
                            "exclamaciones.",
    "canvas_rule_trigger": "Sin palabras que castigan los filtros («gratis», "
                           "«urgente», «haz clic aquí»…).",
    "canvas_rule_found": "Tiene «{what}».",

    "menu_designs": "Plantillas",
    # --- enviar correos ----------------------------------------------------
    "send_title": "Masivo",
    "send_lead": "Elige a quién le escribes y cómo lo armas: con una plantilla o "
                 "escrito. Puedes mandarlo ahora o dejarlo programado.",
    "send_new": "Nueva campaña",
    # El correo individual (octubre de 2026).
    "single_title": "Redactar",
    "single_lead": "Un correo a una persona, con un archivo si hace falta. Sabrás si "
                   "le llegó, si lo abrió, si hizo clic en un enlace y si bajó el "
                   "archivo.",
    "single_to": "Para",
    "single_to_hint": "Cualquier dirección, esté o no en tus contactos. Si no "
                      "está, no se agrega.",
    "single_body": "Mensaje",
    "single_file": "Archivo (opcional)",
    "single_file_hint": "Uno, de hasta {mb} MB: PDF, JPG, PNG, Word o Excel. Va "
                        "como un botón para bajarlo, así sabes si lo bajó; lo "
                        "guardamos {days} días.",
    "single_file_big": "El archivo pasa de {mb} MB.",
    "single_file_kind": "Ese tipo de archivo no se puede adjuntar. Usa PDF, JPG, "
                        "PNG, Word o Excel.",
    "single_send": "Enviar",
    "single_bad_address": "Esa no es una dirección de correo.",
    "single_undeliverable": "{domain} no recibe correo, así que esa dirección "
                            "rebotaría. Revisa cómo está escrita.",
    "single_typo": "¿Quisiste decir {better}?",
    "single_typo_use": "Usar {better}",
    "single_typo_keep": "Mandar a la que escribí",
    # La página del enlace de descarga, que abre quien recibió el correo.
    "download_title": "Bajar el archivo",
    "download_lead": "{company} te mandó este archivo.",
    "download_lead_plain": "Te mandaron este archivo.",
    "download_submit": "Descargar",
    # La página baja el archivo sola (octubre de 2026).
    "download_started": "Tu descarga empezó",
    "download_close": "Ya puedes cerrar esta pestaña.",
    "download_again": "Descargar otra vez",
    "bare_by": "Enviado por",
    "bare_privacy": "Privacidad",
    "download_gone_title": "Este archivo ya no está",
    "download_gone_lead": "Los archivos se guardan {days} días. Si todavía lo "
                          "necesitas, pídeselo de nuevo a quien te lo mandó.",
    "single_suppressed": "Esa persona se dio de baja o su correo rebotó. No se le "
                         "puede escribir.",
    "single_body_long": "El mensaje pasa de {n} caracteres.",
    "single_blocked": "Todavía no puedes enviar. Mira lo que falta en Enviar "
                      "correos.",
    "single_failed": "No se pudo enviar tu correo. Vuelve a intentarlo, y si sigue "
                     "fallando, escríbenos.",
    "single_row": "Individual · {to}",
    "send_submit": "Guardar la campaña",
    "send_save": "Guardar los cambios",
    "send_yours": "Campañas guardadas",
    "send_none": "Todavía no has armado ninguna.",
    "send_runs_none": "Todavía no ha salido ninguna.",
    "send_times_one": "Enviada una vez, {when}",
    "send_times": "Enviada {n} veces, la última {when}",
    "send_back": "Volver a envíos",

    # Enviados (octubre de 2026): todo lo que salió, en una tabla.
    "sent_title": "Enviados",
    "sent_back": "Volver a Enviados",
    "sent_col_subject": "Asunto",
    "sent_col_when": "Fecha",
    "sent_col_delivered": "Entregados",
    "sent_col_opened": "Abiertos",
    "sent_col_clicked": "Clics",
    "sent_col_bounced": "Rebotes",
    "sent_col_complaints": "Quejas",
    "sent_kind_bulk": "Campaña",
    "sent_kind_single": "Individual",
    "sent_waiting": "Esperando lo que cuente Amazon.",
    "sent_downloaded": "Descargó el archivo",
    "sent_not_downloaded": "No ha bajado el archivo",

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
    # Escribir o Plantilla (octubre de 2026), en Redactar y en Masivo.
    "send_mode": "Cómo lo armas",
    "send_mode_write": "Escribir",
    "send_mode_template": "Plantilla",
    "send_logo": "Poner mi logo arriba",
    "send_written_name": "Texto escrito",
    "send_written_hint": "Sale con el enlace de baja y la dirección postal, como "
                         "toda campaña.",
    "single_template_missing": "Esta plantilla usa {what}, y esa dirección no "
                               "tiene esos datos en Contactos. Agrégala con sus "
                               "datos o elige Escribir.",
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
    "send_done_some": "Va saliendo: el resto sale solo, por tandas.",
    "send_done_blocked": "Todavía no se puede enviar. Mira lo que falta arriba.",

    # Por qué una cuenta todavía no puede mandar. Se enseñan arriba del todo.
    "send_blocked_plan": "Para enviar hace falta un plan contratado.",
    "send_blocked_postal": "Falta la dirección postal de tu empresa, que la ley "
                           "pide al pie de cada correo.",
    "send_blocked_postal_link": "Escribirla en Configuración",
    "send_blocked_quota": "Se acabaron los correos de tu plan este mes.",
    "send_blocked_sender": "Falta elegir desde qué dirección salen tus campañas.",
    "send_blocked_sender_link": "Elegirla en Remitente",
    "send_blocked_limited": "Tu cuenta está limitada: necesitamos verificar tu "
                            "identificación y tu dirección.",
    "send_blocked_limited_link": "Enviar los documentos",
    # La demostración envía solo a sus direcciones de prueba (octubre de 2026).
    "send_blocked_demo_addresses": "En la demostración solo envías a tus "
                                   "direcciones de prueba, y todavía no tienes "
                                   "ninguna confirmada.",
    "send_blocked_demo_link": "Agregarlas en Configuración",
    "send_blocked_demo_used": "Ya usaste los correos de prueba de la "
                              "demostración. Para seguir, contrata un plan.",
    "send_demo_notice": "Estás en la demostración: tus envíos salen solo a tus "
                        "direcciones de prueba confirmadas ({n}), y te quedan "
                        "{left} de {total} correos.",
    "send_demo_link": "Ver tus direcciones de prueba",
    "single_demo_only": "En la demostración solo puedes escribirle a tus "
                        "direcciones de prueba confirmadas.",
    "send_blocked_paused": "Tus envíos están en pausa: rebotaron o se marcaron "
                           "como spam demasiados de tus correos. Te escribimos "
                           "con el detalle.",
    # Remitente: de quién salen las campañas y a dónde vuelven las respuestas.
    "sender_title": "Remitente",
    "sender_back": "Volver a Enviar correos",
    "sender_lead": "Desde qué direcciones salen tus campañas y a dónde llegan "
                   "las respuestas. Cada plantilla elige las suyas; la que no "
                   "elige, y lo que escribes sin plantilla, usan las "
                   "predeterminadas.",
    "sender_change": "Cambiar remitente",
    "sender_owner_only": "Solo el dueño de la cuenta puede cambiar el remitente.",
    "sender_now": "Lo predeterminado",
    # Arriba de Masivo: son los de una plantilla que no elige otros.
    "sender_now_default": "Lo predeterminado:",
    "sender_now_from": "Sale de: {name} <{email}>",
    "sender_now_none": "Sale de: todavía no elegiste una dirección",
    "sender_now_reply": "Responde a: {email}",
    "sender_none": "Sin elegir",
    "sender_save": "Guardar",
    "sender_edit": "Editar",
    "sender_default": "Predeterminado",
    "sender_make_default": "Hacer predeterminado",
    # Los remitentes (octubre de 2026: varios, cada uno con su nombre).
    "sender_froms": "Remitentes",
    "sender_froms_lead": "Quién firma tus campañas: el nombre que se ve en el "
                         "buzón y la dirección de la que salen, que es la tuya "
                         "en {domain} o una de tus dominios verificados.",
    "sender_froms_none": "Todavía no tienes ninguno. Elige abajo tu dirección de "
                         "envío.",
    "sender_from_waiting": "No sale mientras su dominio no esté verificado.",
    "sender_from_remove": "Quitar",
    "sender_from_add": "Agregar un remitente",
    "sender_from_add_button": "Agregar",
    "sender_from_name": "Nombre",
    "sender_from_name_hint": "El que se ve en el buzón. Si lo dejas vacío, el "
                             "de tu empresa: {name}.",
    "sender_from_address": "Dirección",
    "sender_from_domain": "Dominio de la dirección",
    "sender_from_local_hint": "En tus dominios, escribe la parte de antes de la "
                              "@: boletin, cobros o la que quieras. En {domain} "
                              "la dirección es siempre la tuya.",
    "sender_from_full": "Ya tienes {n} remitentes, que es el máximo.",
    "sender_from_taken": "Ya tienes un remitente con ese nombre y esa dirección.",
    "sender_from_domain_bad": "Esa dirección no se puede usar: elige la tuya en "
                              "{domain} o un dominio verificado.",
    "sender_handle_title": "Tu dirección en {domain}",
    "sender_handle": "Tu dirección de envío",
    "sender_handle_hint": "La parte de antes de la @. Es la de tus remitentes en "
                          "{domain}, y ninguna otra cuenta la puede usar.",
    "sender_handle_bad": "Usa de {min} a {max} letras, números, puntos o guiones, "
                         "sin espacios ni tildes. Algunos nombres están reservados.",
    "sender_handle_taken": "Esa dirección ya la usa otra cuenta. Prueba con otra.",
    "sender_reply": "Responder a",
    "sender_reply_hint": "A dónde llegan las respuestas de tus contactos. Cada "
                         "dirección se confirma con un código que le mandamos; "
                         "las de tus dominios verificados no lo necesitan. Sin "
                         "ninguna, llegan a {email}.",
    "sender_reply_owner": "El correo con el que entras. Las respuestas llegan "
                          "aquí mientras no agregues otra dirección.",
    "sender_reply_remove": "Quitar",
    "sender_reply_add": "Agregar",
    "sender_reply_placeholder": "socios@tuempresa.com",
    "sender_reply_full": "Ya tienes {n} direcciones, que es el máximo.",
    "sender_reply_same": "Esa dirección ya está en la lista.",
    "sender_reply_waiting": "Esperando el código que mandamos a {email}.",
    "sender_reply_code_link": "Escribir el código",
    "sender_code_title": "Confirma la dirección de respuesta",
    "sender_code_lead": "Te mandamos un código de seis dígitos a {email}. "
                        "Escríbelo aquí.",
    "sender_code_submit": "Confirmar",
    "sender_code_other": "Usar otra dirección",
    "sender_domain": "Tus dominios",
    "sender_domain_lead": "Si tu empresa tiene sus dominios (por ejemplo "
                          "tuempresa.com), conéctalos y tus remitentes podrán "
                          "salir de direcciones tuyas, con tu propia reputación. "
                          "Es opcional, y puedes tener hasta {n}.",
    "sender_domain_field": "Tu dominio",
    "sender_domain_another": "Otro dominio",
    "sender_domain_connect": "Conectar",
    "sender_domain_none": "Sin dominio conectado.",
    "sender_domain_bad": "Ese dominio no se puede usar. Escríbelo como "
                         "tuempresa.com. Los de correo gratis, como gmail.com, "
                         "no se pueden conectar.",
    "sender_domain_taken": "Ese dominio ya está conectado en otra cuenta.",
    "sender_domain_mine": "Ese dominio ya está en tu lista.",
    "sender_domain_full": "Ya tienes {n} dominios, que es el máximo.",
    "sender_domain_failed": "No pudimos hablar con Amazon en este momento. "
                            "Prueba otra vez en unos minutos.",
    "sender_status_pending": "Pendiente",
    "sender_status_verified": "Verificado",
    "sender_status_failed": "No se encontraron los registros",
    "sender_records_lead": "Agrega estos cinco registros en el DNS de tu dominio, "
                           "donde lo compraste o donde lo administras:",
    "sender_records_type": "Tipo",
    "sender_records_name": "Nombre",
    "sender_records_value": "Valor",
    "sender_records_hint": "Amazon los comprueba solo. Suele tardar unos minutos, "
                           "y puede llegar a 72 horas.",
    "sender_records_download": "Descargar los registros DNS",
    "sender_records_download_hint": "Si tu proveedor de DNS permite importar un "
                                    "archivo de zona (Cloudflare, Route 53 y otros), "
                                    "súbelo y entran todos a la vez. Si no, cópialos "
                                    "uno por uno de la tabla.",
    "sender_records_priority": "prioridad {n}",
    # El MAIL FROM (octubre de 2026): el dominio que Gmail enseña en «enviado
    # por». Sin sus registros dice el de Amazon, y se envía igual.
    "sender_mail_from": "Enviado por",
    "sender_mail_from_hint": "Lo que Gmail enseña debajo de tu nombre: {domain}. "
                             "Mientras falten sus registros dice el de Amazon, y "
                             "tus correos salen igual.",
    "sender_mail_from_verified": "Listo",
    "sender_mail_from_pending": "Esperando los registros",
    "sender_mail_from_failed": "No se encontraron los registros",
    "sender_mail_from_lead": "Para que Gmail diga tu dominio y no el de Amazon, "
                             "agrega estos dos registros en su DNS:",
    "sender_check": "Comprobar ahora",
    "sender_remove": "Quitar dominio",
    "sender_local_bad": "Escribe solo la parte de antes de la @, sin espacios.",
    "sender_done_handle": "Guardamos tu dirección de envío.",
    "sender_done_reply": "Listo, agregamos esa dirección.",
    "sender_done_reply_removed": "Quitamos esa dirección. Las plantillas que la "
                                 "usaban responden a la predeterminada.",
    "sender_done_reply_default": "Listo, ahora las respuestas llegan a esa "
                                 "dirección.",
    "sender_done_from_added": "Listo, agregamos el remitente.",
    "sender_done_from_saved": "Listo, guardamos el remitente.",
    "sender_done_from_removed": "Quitamos el remitente. Las plantillas que salían "
                                "de él salen del predeterminado.",
    "sender_done_from_default": "Listo, ese es ahora el remitente predeterminado.",
    "sender_done_domain": "Dominio agregado. Ahora pon los registros en su DNS.",
    "sender_done_check": "Comprobamos tu dominio con Amazon.",
    "sender_done_removed": "Quitamos el dominio, con sus remitentes. Las "
                           "plantillas que salían de ahí salen del "
                           "predeterminado.",
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
    "send_confirm_from": "Sale de",
    "send_confirm_reply": "Responder a",
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
    "run_outcome": "Resultado",
    "run_outcome_all": "Todos",
    "run_outcome_entregados": "Entregados",
    "run_outcome_rebotes": "Rebotaron",
    "run_outcome_rechazados": "Rechazados",
    "run_outcome_spam": "Lo marcaron como spam",
    "run_outcome_abrieron": "Lo abrieron",
    "run_outcome_pulsaron": "Hicieron clic",
    "run_outcome_sin_abrir": "No lo abrieron",
    "run_apply": "Buscar",
    "run_clear": "Quitar filtros",
    "run_email": "Correo",
    "run_name": "Nombre",
    "run_reached": "Llegó",
    "run_opened": "Abrió",
    "run_clicked": "Hizo clic",
    "run_downloaded": "Bajó el archivo",
    "run_reached_sent": "Enviado",
    "run_reached_delivery": "Entregado",
    "run_reached_bounce": "Rebotó",
    "run_reached_reject": "Rechazado",
    "run_reached_complaint": "Lo marcó como spam",
    "run_gone": "Ya no está en tus contactos",
    # El correo individual a una dirección que no está en Contactos.
    "run_not_contact": "No está en tus contactos",
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
    "admin_filter_demo": "Piden demostración",
    "admin_tab_accounts": "Cuentas",
    # Clientes: vigilar cómo envía cada uno (octubre de 2026).
    "admin_tab_clients": "Clientes",
    "admin_clients_lead": "Para vigilar cómo envía cada cliente. Las cifras son "
                          "de los últimos {days} días; para hacer algo con una "
                          "cuenta, ábrela desde aquí o desde Cuentas.",
    "admin_health_title": "Tu cuenta de Amazon",
    "admin_health_day": "Últimas 24 horas",
    "admin_health_month": "Últimos {days} días",
    "admin_health_sent": "correos de campaña enviados",
    "admin_health_bounces": "Rebotes",
    "admin_health_complaints": "Quejas",
    "admin_health_of": "{n} en total. Amazon revisa la cuenta desde {limit}.",
    "admin_health_note": "Amazon mide la cuenta entera de Sobreala, sumando a "
                         "todos los clientes: si pasa sus umbrales, se para el "
                         "envío de todos. Solo cuentan los rebotes permanentes, y "
                         "los correos del sistema no entran aquí.",
    "admin_clients_title": "Por cliente",
    "admin_clients_all_plans": "Todos los planes",
    "admin_clients_col_sent": "Enviados",
    "admin_clients_col_delivered": "Entregados",
    "admin_clients_col_bounces": "Rebotes",
    "admin_clients_col_complaints": "Quejas",
    "admin_clients_col_opens": "Aperturas",
    "admin_clients_col_contacts": "Contactos",
    "admin_clients_col_last": "Último envío",
    "admin_clients_state_paused": "En pausa",
    "admin_clients_state_limited": "Limitada",
    "admin_clients_state_near": "Cerca del límite",
    "admin_clients_state_ok": "Bien",
    "admin_clients_few": "Todavía no envió lo suficiente para que esta cifra "
                         "diga algo.",
    "admin_clients_note": "En ámbar, cerca del umbral de la pausa automática; en "
                          "rojo, pasado. Los rebotes cuentan desde {bounce_min} "
                          "enviados y las quejas desde {complaint_min}: antes, la "
                          "cifra sale en gris. Las aperturas son sobre los "
                          "entregados.",
    # Eventos: lo que está pasando, y se actualiza solo (octubre de 2026).
    "admin_tab_events": "Eventos",
    "admin_events_lead": "Lo que está pasando: lo que cuenta Amazon de cada "
                         "correo y lo que pasa en las cuentas. Del destinatario "
                         "se ve solo el dominio.",
    "admin_events_type": "Qué mirar",
    "admin_events_filter_attention": "Lo que pide atención",
    "admin_events_filter_mail": "Correos",
    "admin_events_filter_accounts": "Cuentas",
    "admin_events_filter_all": "Todo",
    "admin_events_all_companies": "Todas las empresas",
    "admin_events_live": "Se actualiza sola cada 5 segundos mientras la tienes "
                         "abierta.",
    "admin_events_refresh": "Actualizar",
    "admin_events_col_when": "Cuándo",
    "admin_events_col_what": "Evento",
    "admin_events_col_detail": "Detalle",
    "admin_events_none": "No pasó nada de esto en los últimos {days} días.",
    "activity_kind_delivery": "Entregado",
    "activity_bounce_hard": "Rebote permanente",
    "activity_bounce_soft": "Rebote pasajero",
    "activity_kind_complaint": "Queja",
    "activity_kind_reject": "Rechazado",
    "activity_kind_open": "Abierto",
    "activity_kind_click": "Clic",
    "activity_kind_download": "Bajó el archivo",
    "activity_kind_signup": "Registro",
    "activity_kind_demo": "Pidió la demostración",
    "activity_kind_payment": "Pago",
    "activity_kind_pause": "Pausa automática",
    "activity_kind_limit": "Cuenta limitada",
    "activity_kind_unlimit": "Se quitó el límite",
    "activity_payment_detail": "{plan}, {amount}",
    "activity_to": "a {domain}",
    "admin_mail_title": "Correos del sistema",
    "admin_mail_lead": "Lo que Sobreala le envió a una dirección (códigos, avisos, "
                       "bienvenidas) y qué dijo Amazon de cada uno. Para cuando "
                       "alguien dice que no le llegó.",
    "admin_mail_search": "Dirección de correo",
    "admin_mail_col_when": "Cuándo",
    "admin_mail_col_subject": "Correo",
    "admin_mail_col_result": "Estado",
    "admin_mail_failed": "Fallido",
    "admin_mail_outcome_delivered": "Entregado",
    "admin_mail_outcome_bounced": "Rebotó",
    "admin_mail_outcome_soft_bounced": "Rebote pasajero",
    "admin_mail_outcome_complained": "Lo marcó como spam",
    "admin_mail_outcome_rejected": "Amazon lo rechazó",
    "admin_mail_waiting": "Enviado a Amazon, sin respuesta todavía",
    "admin_mail_not_ses": "No se envió por Amazon (desarrollo)",
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
    "admin_history_open": "Se abrió la cuenta",
    # La habilitación ya no se toma (octubre de 2026). Queda para leer las
    # decisiones de antes.
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
    "admin_act_only_logins": "Entradas",
    "admin_act_only_payments": "Transacciones",
    "admin_act_only_emails": "Correos",
    "admin_act_only_imports": "Contactos",
    "admin_act_only_decisions": "Decisiones",

    # La única puerta con una persona detrás; la otra forma de pasarla es pagar.
    "admin_demo_title": "Demostración",
    "admin_demo_asked": "La pidió {when}.",
    "admin_demo_whatsapp": "Escribirle al {phone}",
    "admin_demo_not_asked": "Todavía no la pide. Si paga un plan, la cuenta se "
                            "abre sola.",
    "admin_demo_opened_when": "Abierta {when}",
    "admin_demo_opened_paid": "Abierta al pagar",
    "admin_demo_opened": "Abierta",
    "admin_demo_closed": "Cerrada",
    "admin_demo_open": "Abrir la cuenta",
    "admin_phone_missing": "No lo dejó",
    "admin_company_phones": "De la empresa",

    # Las verificaciones de la ficha: ver el documento, y verificarlo o
    # rechazarlo. Las dos cosas lo borran.
    "admin_verify_when": "Desde {when}.",
    "admin_verify_see": "Ver documento",
    "admin_verify_reason": "Motivo (obligatorio para rechazar)",
    "admin_verify_ok": "Verificar",
    "admin_verify_no": "Rechazar",
    "admin_verify_reason_ok": "Documento revisado y correcto.",
    "admin_verify_notify": "Enviar correo al cliente",
    "admin_verify_notify_hint": "Le cuenta qué quedó verificado y qué se rechazó. "
                                "Verificar y rechazar solo anotan el resultado.",
    "admin_verify_notified": "Le enviamos el correo al cliente.",
    "admin_notify_reason": "Se le mandó el resultado de sus verificaciones.",
    "admin_limit_note_rejected": "Documento rechazado.",
    "admin_history_notify": "Se le avisó el resultado de las verificaciones",
    "admin_filter_review": "Por verificar",
    "admin_history_verify": "{what}: {status}",
    "admin_history_limit": "Se limitó la cuenta",
    "admin_history_unlimit": "Se quitó el límite",

    # Limitar: entra y prepara, pero no envía. No es suspender.
    "admin_limit_title": "Limitar la cuenta",
    "admin_limit_hint": "Una cuenta limitada entra, prepara todo y puede pagar, "
                        "pero no envía. Le llega un correo con el motivo y el "
                        "enlace a sus documentos.",
    "admin_limit_reason": "Motivo",
    "admin_limit_reason_verification": "Falta verificar la identificación y la "
                                       "dirección",
    # La pausa automática (services/reputation.py): no sale en el selector.
    "admin_limit_reason_bounces": "Pausa automática por rebotes",
    "admin_limit_reason_complaints": "Pausa automática por quejas",
    "pause_note_bounces": "Rebotes: {rate} ({n} de {sent} enviados en {days} "
                          "días)",
    "pause_note_complaints": "Quejas: {rate} ({n} de {sent} enviados en {days} "
                             "días)",
    "pause_auto_reason": "Pausa automática. {note}",
    "admin_limit_note": "Nota para el registro (opcional)",
    "admin_limit_do": "Limitar la cuenta",
    "admin_limit_now": "Limitada {when}: {reason}.",
    "admin_limit_note_was": "Nota: {note}",
    "admin_limit_lift": "Quitar el límite",
    "admin_limit_lifted": "Se quitó el límite.",
    "admin_limit_lifted_auto": "Se quitó solo al quedar verificadas la "
                               "identificación y la dirección.",

    "admin_two_step_needed": "Para entrar a administración activa antes la "
                             "autenticación de múltiples factores. Es la "
                             "cuenta que puede abrir y suspender las cuentas "
                             "de todos los demás.",

    # --- errors ------------------------------------------------------------
    "error_required": "Completa este campo.",
    "error_phone": "Ese número no parece válido. Revisa el país y los dígitos.",
    "error_demo_answer": "Cuéntanos un poco más: entre {min} y {max} caracteres.",
    "error_demo_choose": "Elige una opción.",
    "error_demo_website": "Escribe una dirección válida, como minegocio.com.",
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
                       "info@sobreala.com y lo revisamos.",

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
    # El pie de todos los correos del sistema (octubre de 2026): quién y dónde,
    # las redes y la ayuda.
    "mail_footer_name": "Sobreala",
    "mail_footer_address": "Santiago de Veraguas, Panamá",
    "mail_footer_help": "Ayuda",
    "mail_footer_privacy": "Privacidad",
    "mail_confirm_subject": "{code} es tu código de Sobreala",
    "mail_confirm_heading": "Confirma tu correo",
    "mail_confirm_body": "Gracias por crear tu cuenta en Sobreala. Escribe "
                         "este código en la página donde lo pediste:",
    "mail_confirm_expiry": "El código vence en {minutes} minutos.",
    "mail_confirm_expiry_one": "El código vence en un minuto.",
    "mail_confirm_ignore": "Si no creaste ninguna cuenta, puedes ignorar este "
                           "mensaje: no se hará nada.",

    # Sent once the code is typed and the address is verified: the account is
    # complete. Transactional, like the rest of the system mail — it describes
    # the state of an account its owner just created, it does not offer
    # anything, so rule 8 holds and it carries no unsubscribe link.
    "mail_welcome_subject": "Tu cuenta de Sobreala está creada",
    # Neutral on purpose: we do not know the recipient's gender.
    "mail_welcome_heading": "Te damos la bienvenida, {name}",
    "mail_welcome_body": "Confirmaste tu correo, así que tu cuenta ya está "
                         "creada. Para empezar hay dos caminos: pides una "
                         "demostración y te escribimos por WhatsApp para "
                         "agendarla, o contratas un plan y empiezas enseguida.",
    "mail_welcome_button": "Pedir la demostración",
    "mail_welcome_next_title": "Qué incluye la demostración",
    "mail_welcome_next": "Abrimos tu cuenta y, juntos, recorremos Sobreala, vemos de "
                         "dónde sale tu lista, la importamos y armamos tu primera "
                         "plantilla. Desde ahí tienes lo del plan Básico para "
                         "preparar todo.",
    "mail_welcome_help": "Si algo no te calza, escríbenos a "
                         "info@sobreala.com y lo vemos.",

    # The recovery code. Same shape as the confirmation one, and the subject
    # carries it too: on a phone it is readable from the notification.
    "mail_recover_subject": "{code} es tu código para recuperar tu cuenta",
    "mail_recover_heading": "Recupera tu cuenta",
    "mail_recover_body": "Pediste poner una contraseña nueva en Sobreala. "
                         "Escribe este código en la página donde lo pediste:",
    "mail_recover_ignore": "Si no lo pediste, ignora este mensaje: tu "
                           "contraseña no cambia hasta que alguien escriba el "
                           "código, y solo tú lo tienes.",

    # Sent when a sign-in comes from a device this account has never used. The
    # only warning there is that somebody else got in, so it says what happened,
    # where, and what to do about it without needing the password.
    "mail_login_subject": "Entraron a tu cuenta desde un dispositivo nuevo",
    "mail_login_heading": "Un ingreso desde un dispositivo nuevo",
    "mail_login_body": "Alguien entró a tu cuenta de Sobreala desde un "
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
    "mail_password_subject": "Tu contraseña de Sobreala cambió",
    "mail_password_heading": "Tu contraseña cambió",
    "mail_password_body": "Acabamos de cambiar la contraseña de tu cuenta y "
                          "cerramos la sesión en los demás dispositivos.",
    "mail_password_ok": "Si fuiste tú, no tienes que hacer nada más.",
    "mail_password_alert_title": "¿No fuiste tú?",
    "mail_password_alert": "Escríbenos de inmediato a info@sobreala.com. "
                           "Quien haya entrado conoce tu contraseña anterior, "
                           "así que conviene revisar también el correo con el "
                           "que abriste la cuenta.",
    "mail_password_button": "Entrar a Sobreala",

    # Sent both ways, and one of the messages nobody can turn off: turning
    # two-step on with a phone that is not the owner's is how an account gets
    # taken away for good, and turning it off is the first thing anybody does
    # after getting in.
    # La invitación a entrar como usuario de una cuenta.
    "mail_invite_subject": "{company} te invitó a su cuenta de Sobreala",
    "mail_invite_heading": "Te dieron entrada a {company}",
    "mail_invite_body": "Vas a poder entrar a la cuenta de {company} en "
                        "Sobreala con tu propio correo. Pulsa el botón y "
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
                              "inmediato a info@sobreala.com.",
    "mail_two_step_off_alert": "Quien lo hizo conoce tu contraseña. Cámbiala "
                               "ahora mismo y escríbenos a "
                               "info@sobreala.com.",
    "mail_two_step_button": "Entrar a mi cuenta",

    # Sent when someone tries to register with an address that already has an
    # account. The screen must not reveal this, so the owner is told by email.
    "mail_exists_subject": "Alguien intentó crear una cuenta con tu correo",
    "mail_exists_heading": "Ya tienes una cuenta",
    "mail_exists_body": "Alguien intentó registrarse en Sobreala con esta "
                        "dirección, que ya tiene una cuenta. Si fuiste tú, "
                        "simplemente entra con tu contraseña.",
    "mail_exists_button": "Entrar a mi cuenta",
    "mail_exists_ignore": "Si no fuiste tú, no tienes que hacer nada. Tu cuenta "
                          "sigue segura y nadie ha entrado.",

    # --- los avisos de la cuenta -------------------------------------------
    # El plan, la cuenta abierta y la suspensión. Los compone
    # services/notices.py sobre una sola plantilla, porque los ocho tienen la
    # misma forma y lo único que cambia es esto.
    "mail_notice_off": "Estos avisos se apagan en Configuración → "
                       "Notificaciones.",
    "mail_plan_button": "Ir a mi cuenta",
    "mail_plan_until": "Corre hasta el {until}. Te avisamos una semana antes de "
                       "que se venza.",
    "mail_plan_charged": "Pagaste ${amount}.",
    "mail_plan_charged_credit": "Pagaste ${amount}, con ${credit} de descuento por "
                                "los correos que no usaste de tu plan anterior.",

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
    "mail_plan_expiring_body": "Tu plan {plan} vence el {until}. Cuando venza "
                               "lo vuelves a contratar desde Planes, y hasta "
                               "entonces sigue funcionando igual.",

    "mail_plan_expired_subject": "Tu plan {plan} venció",
    "mail_plan_expired_heading": "Se venció tu plan {plan}",
    "mail_plan_expired_body": "Venció el {until}, así que por ahora no puedes "
                              "enviar campañas.",
    "mail_plan_expired_kept": "No se borró nada: tus contactos, tus etiquetas y "
                              "tus plantillas siguen donde estaban y vuelven a "
                              "servir en cuanto contrates otra vez.",
    "mail_plan_expired_button": "Ver mi plan",

    "mail_opened_subject": "Tu cuenta de Sobreala está abierta",
    "mail_opened_heading": "Ya puedes empezar",
    "mail_opened_body": "Abrimos tu cuenta: ya puedes subir tus contactos y "
                        "armar tus plantillas y campañas, con lo del plan "
                        "Básico, y mandarlas a tus direcciones de prueba "
                        "(Configuración, Direcciones de prueba) para ver quién "
                        "las abre. Para enviarlas a tu lista, eliges tu plan.",
    "mail_opened_button": "Ir a mis contactos",

    "mail_suspended_subject": "Tu cuenta de Sobreala quedó suspendida",
    "mail_suspended_heading": "Suspendimos tu cuenta",
    "mail_suspended_body": "Mientras esté suspendida no se puede entrar ni "
                           "enviar. No se borró nada: tus contactos y tus "
                           "plantillas siguen ahí.",
    "mail_suspended_write": "Si crees que es un error, escríbenos a {email} y "
                            "lo revisamos.",

    "mail_reinstated_subject": "Tu cuenta está activa otra vez",
    "mail_reinstated_heading": "Levantamos la suspensión",
    "mail_reinstated_body": "Ya puedes entrar y seguir donde estabas.",
    "mail_reinstated_button": "Entrar a Sobreala",

    # La cuenta quedó limitada: entra y prepara, pero no envía.
    "mail_limited_subject": "Necesitamos verificar tu cuenta de Sobreala",
    "mail_limited_heading": "Tu cuenta está limitada",
    "mail_limited_body_verification": "Para seguir enviando necesitamos "
                                      "verificar tu identificación y tu "
                                      "dirección. Sube los documentos desde "
                                      "Configuración y los revisamos.",
    "mail_limited_kept": "Mientras tanto puedes entrar y preparar todo: tus "
                         "contactos, tus plantillas y tus campañas siguen ahí.",
    "mail_limited_button": "Subir los documentos",

    # La pausa automática por rebotes o quejas (services/reputation.py).
    "mail_test_address_subject": "Confirma tu dirección de prueba para {company}",
    "mail_test_address_heading": "¿Recibes los correos de prueba?",
    "mail_test_address_body": "{company} está probando Sobreala y quiere "
                               "mandarte sus correos de prueba. Confirma que "
                               "esta dirección es tuya y que los aceptas.",
    "mail_test_address_ignore": "Si no sabes de qué se trata, no hagas nada: no "
                                "te va a llegar ninguno.",
    "mail_test_address_button": "Confirmar mi dirección",
    "mail_test_address_expiry": "El enlace vence en {days} días.",
    "mail_paused_subject": "Pausamos los envíos de tu cuenta de Sobreala",
    "mail_paused_heading": "Tus envíos están en pausa",
    "mail_paused_body_bounces": "Demasiados de tus correos rebotaron porque esas "
                                "direcciones no existen. {note}. Con tantos "
                                "rebotes, los proveedores de correo empiezan a "
                                "desconfiar de todo lo que envías, así que "
                                "pausamos tus envíos antes de que eso pase.",
    "mail_paused_body_complaints": "Varias personas marcaron tus correos como "
                                   "spam. {note}. Si sigue pasando, los "
                                   "proveedores de correo mandan a spam todo lo "
                                   "que envías, así que pausamos tus envíos "
                                   "antes de que eso pase.",
    "mail_paused_fix_bounces": "Lo más común es una lista vieja o copiada de otro "
                               "sistema. A las direcciones que rebotaron ya no se "
                               "les va a enviar nada; revisa de dónde salió el "
                               "resto antes de volver a enviar.",
    "mail_paused_fix_complaints": "Lo más común es escribirle a gente que no "
                                  "pidió tus correos o que no te reconoce. "
                                  "Revisa de dónde salió tu lista, y que cada "
                                  "correo diga claramente quién eres.",
    "mail_paused_write": "Para volver a enviar, escríbenos a {email} y lo "
                         "revisamos contigo.",

    # La renovación automática con PayPal.
    # Facturación y el pago: la renovación automática con PayPal.
    "pay_renew_label": "Renovar solo {every} con PayPal",
    "pay_renew_hint": "PayPal cobra tu plan al vencer, sin que tengas que "
                      "volver. Lo cancelas cuando quieras desde Facturación o "
                      "desde tu cuenta de PayPal.",
    "renewal_title": "Renovación automática",
    "renewal_unavailable_soon": "La renovación automática todavía no está "
                                "disponible. Por ahora, cada periodo se paga desde "
                                "aquí.",
    "renewal_unavailable_plan": "Se activa cuando tienes un plan vigente: paga un "
                                "periodo y vuelve aquí.",
    "renewal_desc": "PayPal cobra tu plan solo cada mes o cada año. Lo cancelas "
                    "cuando quieras.",
    "renewal_status_on": "Activa",
    "renewal_status_suspended": "PayPal no pudo cobrar",
    "renewal_next": "Próximo cobro: {when}",
    "renewal_activate": "Activar con PayPal",
    "renewal_cancel": "Cancelar renovación",
    "renewal_done_on": "Listo, tu plan se renovará solo con PayPal.",
    "renewal_done_off": "Listo, cancelaste la renovación automática. Tu plan "
                        "sigue hasta su fecha.",
    "renewal_every_monthly": "cada mes",
    "renewal_every_yearly": "cada año",
    "mail_renewal_on_subject": "Activaste la renovación automática",
    "mail_renewal_on_heading": "Tu plan se renovará solo",
    "mail_renewal_on_body": "Tu plan {plan} se renueva {cycle} con PayPal, por "
                            "$ {amount}. El primer cobro es el {when}.",
    "mail_renewal_cancel": "La cancelas cuando quieras desde Facturación, o "
                           "desde tu cuenta de PayPal.",
    "mail_renewal_button": "Ir a Facturación",
    "mail_renewal_off_subject": "Cancelaste la renovación automática",
    "mail_renewal_off_heading": "Tu plan ya no se renueva solo",
    "mail_renewal_off_body": "No volveremos a cobrarte con PayPal. Lo que ya "
                             "pagaste sigue funcionando.",
    "mail_renewal_off_until": "Tu plan sigue hasta el {until}.",
    "mail_renewal_failed_subject": "No pudimos cobrar tu renovación",
    "mail_renewal_failed_heading": "PayPal no pudo cobrar tu plan",
    "mail_renewal_failed_body": "Intentamos renovar tu plan y PayPal no pudo "
                                "hacer el cobro.",
    "mail_renewal_failed_what": "Revisa tu método de pago en PayPal. Tu plan "
                                "sigue hasta su fecha; si no se cobra, vence.",
    # El resultado de las verificaciones, que manda el administrador cuando
    # quiere. Una línea por cosa y un cierre según cómo quedó.
    "mail_result_subject": "El resultado de la verificación de tu cuenta",
    "mail_result_heading": "Revisamos tus documentos",
    "mail_result_verified": "{what}: verificada.",
    "mail_result_rejected": "{what}: no pudimos verificarla. Motivo: {reason}",
    "mail_result_pending": "{what}: todavía no la revisamos.",
    "mail_result_again": "Envía otra vez lo que no pudimos verificar. Hasta que "
                         "esté verificado no puedes enviar campañas.",
    "mail_result_done": "Tu cuenta quedó verificada. Ya puedes enviar campañas, "
                        "si tienes un plan.",
    "mail_result_waiting": "Te avisamos cuando terminemos.",
    "mail_result_button": "Enviar los documentos",

    # Este va a quien administra, no a un cliente.
    "mail_admin_payment_subject": "{company} contrató el plan {plan}",
    "mail_admin_payment_heading": "Un cliente pagó",
    "mail_admin_payment_body": "{company} ({email}) contrató el plan {plan}.",
    "mail_admin_payment_button": "Ver la ficha",

    "mail_admin_signup_subject": "{company} se registró",
    "mail_admin_erased_subject": "{company} eliminó su cuenta",
    "mail_admin_erased_heading": "{company} eliminó su cuenta",
    "mail_admin_erased_body": "{company} ({email}) eliminó su cuenta y sus datos desde Configuración. Se quedaron sus supresiones, pagos y facturas.",
    "mail_erase_code_subject": "Tu código para eliminar la cuenta",
    "mail_erase_code_heading": "Tu código para eliminar la cuenta",
    "mail_erase_code_body": "Alguien con tu sesión abierta pidió eliminar tu cuenta de Sobreala. Si fuiste tú, escribe este código. Si no, no hagas nada: sin el código no se borra nada.",
    "mail_erased_subject": "Tu cuenta de Sobreala se eliminó",
    "mail_erased_heading": "Tu cuenta se eliminó",
    "mail_erased_body": "La cuenta de {company} y sus datos se eliminaron de Sobreala. Si no fuiste tú, escríbenos respondiendo este correo.",
    "mail_admin_signup_heading": "Se registró {company}",
    "mail_admin_signup_body": "{name} confirmó el correo {email} y la cuenta de "
                              "{company} ya está creada. Todavía no tiene plan "
                              "ni puede enviar.",
    "mail_admin_signup_button": "Ver la ficha",

    "mail_admin_demo_subject": "{company} pidió una demostración",
    "mail_admin_demo_heading": "{company} quiere una demostración",
    "mail_admin_demo_body": "{name} ({email}) la pidió desde su bienvenida.",
    "mail_admin_demo_data": "Teléfono: {phone}.",
    "mail_admin_demo_business": "A qué se dedica: {answer}",
    "mail_admin_demo_purpose": "Para qué usará Sobreala: {answer}",
    "mail_admin_demo_contacts": "Contactos: {answer}",
    "mail_admin_demo_source": "Cómo los consiguió: {answer}",
    "mail_admin_demo_website": "Sitio web: {answer}",
    "mail_admin_demo_button": "Ver la ficha",

    "mail_admin_plan_end_subject": "Se le venció el plan a {company}",
    "mail_admin_plan_end_heading": "{company} se quedó sin plan",
    "mail_admin_plan_end_body": "El plan {plan} de {company} venció el {until}, "
                                "así que ya no puede enviar.",
    "mail_admin_plan_end_kept": "No se borró nada suyo: sus contactos y sus "
                                "plantillas siguen ahí, y vuelven a servir en "
                                "cuanto renueve.",
    "mail_admin_plan_end_button": "Ver la ficha",
    "mail_admin_pause_subject": "Pausamos los envíos de {company}",
    "mail_admin_pause_heading": "{company} quedó en pausa",
    "mail_admin_pause_body_bounces": "Sobreala pausó los envíos de {company} por "
                                     "rebotes. {note}.",
    "mail_admin_pause_body_complaints": "Sobreala pausó los envíos de {company} por "
                                        "quejas. {note}.",
    "mail_admin_pause_lift": "Ya le llegó un correo con el detalle. Cuando haya "
                             "revisado su lista, quita la pausa desde su ficha, "
                             "en «Limitar la cuenta».",
    "mail_admin_pause_button": "Ver la ficha",
    "mail_invoice_subject": "Ya está tu factura",
    "mail_invoice_heading": "Tu factura está lista",
    "mail_invoice_body": "La factura de tu pago del {when} ya está lista. La "
                         "descargas desde Configuración, en Facturación.",
    "mail_invoice_button": "Ir a Facturación",

    # --- la API (octubre de 2026) ------------------------------------------
    "dash_api": "API",
    "dash_api_keys": "Claves de API",
    "dash_api_log": "Logs",
    "dash_api_docs": "Documentación",

    "api_keys_title": "Claves de API",
    "api_keys_lead": "Con una clave de API, el sistema de tu negocio (tu tienda en "
                     "línea, tu programa de socios) se conecta con Sobreala sin que "
                     "entres a tu cuenta: carga contactos, usa tus plantillas y tus "
                     "remitentes, y envía correos. Cada clave tiene sus permisos, y "
                     "la puedes revocar cuando quieras.",
    "api_keys_docs": "Cómo se usa: la documentación",
    "api_keys_new": "Crear una clave",
    "api_keys_none": "Todavía no tienes ninguna clave de API.",
    "api_keys_full": "Ya tienes {n} claves activas, que es el máximo. Revoca una que "
                     "no uses para crear otra.",
    "api_keys_active": "{n} de {limit} activas",
    "api_keys_col_name": "Nombre",
    "api_keys_col_key": "Clave",
    "api_keys_col_scopes": "Permisos",
    "api_keys_col_used": "Último uso",
    "api_keys_col_expires": "Vence",
    "api_keys_mode_live": "producción",
    "api_keys_mode_test": "prueba",
    "api_keys_never_used": "Sin usar",
    "api_keys_used": "{when} · {ip}",
    "api_keys_expires_never": "Nunca",
    "api_keys_revoked": "Revocada",
    "api_keys_expired": "Vencida",
    "api_keys_ips_some": "Solo desde {n} IP o rangos",
    "api_keys_revoke": "Revocar",
    "api_keys_done_revoked": "Listo, la clave quedó revocada: lo que la use ya no "
                             "entra.",
    "api_keys_new_title": "Crear una clave de API",
    "api_keys_new_lead": "La clave se enseña una sola vez, al crearla. Va en el "
                         "servidor de tu sistema, nunca en una página web, en una "
                         "aplicación que se descarga ni en un repositorio.",
    "api_keys_name": "Nombre",
    "api_keys_name_hint": "Para reconocerla después: «Tienda en línea», «Sistema "
                          "de socios».",
    "api_keys_mode": "Modo",
    "api_keys_mode_live_title": "Producción",
    "api_keys_mode_live_desc": "Hace lo que le permitas. Los correos se envían de "
                               "verdad y gastan cuota.",
    "api_keys_mode_test_title": "Prueba",
    "api_keys_mode_test_desc": "Para que un programador haga pruebas: solo lee, y los "
                               "envíos se simulan (no se envía nada ni se gasta "
                               "cuota). Si se filtra, no puede editar ni enviar nada.",
    "api_keys_scopes": "Permisos",
    "api_keys_preset_send": "Solo enviar correos",
    "api_keys_preset_read": "Solo leer",
    "api_keys_preset_all": "Todo",
    "api_keys_preset_custom": "A mi medida",
    "api_keys_scope_required": "Marca al menos un permiso.",
    "api_keys_test_scope_note": "Una clave de prueba solo se queda con los permisos "
                                "de lectura y los de envío, que con ella se simulan.",
    "api_keys_days": "Vence",
    "api_keys_days_0": "Nunca",
    "api_keys_days_30": "En 30 días",
    "api_keys_days_90": "En 90 días",
    "api_keys_days_365": "En un año",
    "api_keys_ips": "Solo desde estas IP (opcional)",
    "api_keys_ips_hint": "Una por línea, o un rango como 203.0.113.0/24. Vacío "
                         "deja entrar desde donde sea. Hasta 10.",
    "api_keys_ips_bad": "Esto no es una IP ni un rango: {what}.",
    "api_keys_ips_full": "Caben hasta {n} IP o rangos.",
    "api_keys_proof_title": "Confirma que eres tú",
    "api_keys_proof_lead": "Una clave de API abre tu cuenta sin contraseña, así que "
                           "antes de crearla te pedimos la tuya. Después, por 10 "
                           "minutos, no te la volvemos a pedir.",
    "api_keys_password": "Tu contraseña",
    "api_keys_email_code": "El código que te llegó al correo",
    "api_keys_send_code": "Enviarme un código",
    "api_keys_code_hint": "Entraste con Google o GitHub y no tienes contraseña: te "
                          "mandamos un código a tu correo.",
    "api_keys_code_sent": "Listo, te mandamos el código.",
    "api_keys_app_code": "El código de tu app de autenticación",
    "api_keys_create": "Crear la clave",
    "api_keys_cancel": "Cancelar",
    "api_keys_created_title": "Tu clave nueva",
    "api_keys_created_lead": "Cópiala ahora: es la única vez que la vas a ver. "
                             "Nosotros guardamos solo su hash y no la podemos volver "
                             "a enseñar. Si la pierdes, crea otra y revoca esta.",
    "api_keys_created_label": "La clave «{name}»",
    "api_keys_created_where": "Va en la cabecera Authorization de cada petición, "
                              "desde el servidor de tu sistema. Nunca en una página "
                              "web, en una aplicación que se descarga ni en un "
                              "repositorio.",
    "api_keys_created_try": "Para probarla, desde una terminal:",
    "api_keys_created_done": "Ya la guardé",
    "api_keys_revoke_title": "¿Revocar «{name}»?",
    "api_keys_revoke_lead": "Lo que use esta clave deja de entrar desde ya, y no se "
                            "puede deshacer. Si la necesitas otra vez, crea una "
                            "nueva.",
    "api_keys_revoke_yes": "Sí, revocarla",
    "api_key_revoked_by_owner": "La revocó el dueño de la cuenta.",
    "api_key_exposed_reason": "Llegó en la dirección de una petición, donde queda "
                              "escrita en registros ajenos.",

    "api_scope_contacts_read": "Ver contactos",
    "api_scope_contacts_read_desc": "Contactos, etiquetas, columnas y supresiones.",
    "api_scope_contacts_write": "Editar contactos",
    "api_scope_contacts_write_desc": "Crear, editar y borrar contactos, sus listas, "
                                     "etiquetas y columnas.",
    "api_scope_templates_read": "Ver plantillas",
    "api_scope_templates_read_desc": "Plantillas, carpetas y cómo queda cada correo.",
    "api_scope_templates_write": "Editar plantillas",
    "api_scope_templates_write_desc": "Crear, editar y borrar plantillas, carpetas e "
                                      "imágenes.",
    "api_scope_emails_send": "Enviar correos",
    "api_scope_emails_send_desc": "Enviar un correo a una persona y ver los que se "
                                  "enviaron por la API.",
    "api_scope_campaigns_read": "Ver campañas",
    "api_scope_campaigns_read_desc": "Campañas, sus envíos y a quién.",
    "api_scope_campaigns_write": "Editar campañas",
    "api_scope_campaigns_write_desc": "Crear, editar y borrar campañas.",
    "api_scope_campaigns_send": "Enviar campañas",
    "api_scope_campaigns_send_desc": "Enviar y programar campañas.",
    "api_scope_stats_read": "Ver estadísticas",
    "api_scope_stats_read_desc": "Las cifras y los eventos de tus correos.",

    "api_log_title": "Logs de la API",
    "api_log_lead": "Las peticiones que fallaron en los últimos {days} días, para ver "
                    "por qué algo no entró. Lo que salió bien se ve en el último uso "
                    "de cada clave.",
    "api_log_none": "Nada falló en estos días.",
    "api_log_all": "Todas las claves",
    "api_log_show": "Ver",
    "api_log_key": "Clave",
    "api_log_col_when": "Cuándo",
    "api_log_col_key": "Clave",
    "api_log_col_request": "Petición",
    "api_log_col_result": "Resultado",
    "api_log_col_from": "Desde",

    "admin_api_title": "API",
    "admin_api_none": "No tiene claves de API.",
    "admin_api_revoke": "Revocar",
    "admin_api_reason": "Motivo",
    "admin_api_done": "Listo, la clave quedó revocada y el cliente recibió un correo.",

    "mail_api_code_subject": "Tu código para la API",
    "mail_api_code_heading": "Tu código para la API",
    "mail_api_code_body": "Alguien con tu sesión abierta pidió crear una clave de API "
                          "o un webhook. Si fuiste tú, escribe este código. Si no, no "
                          "hagas nada: sin el código no se crea nada.",
    "mail_api_key_subject": "Se creó una clave de API en tu cuenta",
    "mail_api_key_heading": "Se creó una clave de API",
    "mail_api_key_body": "Se creó la clave «{name}» ({mode}) desde la IP {ip}.",
    "mail_api_key_scopes": "Puede: {scopes}.",
    "mail_api_key_not_you": "Si no fuiste tú, revócala ahora y cambia tu contraseña: "
                            "con esa clave se puede usar tu cuenta sin iniciar "
                            "sesión.",
    "mail_api_key_button": "Ver mis claves de API",
    "mail_api_revoked_subject": "Se revocó una clave de API",
    "mail_api_revoked_heading": "Se revocó una clave de API",
    "mail_api_revoked_body": "La clave «{name}» quedó revocada: lo que la usaba ya no "
                             "entra.",
    "mail_api_exposed_subject": "Revocamos una clave de API",
    "mail_api_exposed_heading": "Revocamos una de tus claves de API",
    "mail_api_exposed_body": "La clave «{name}» llegó escrita en la URL de una "
                             "petición. Ahí queda guardada en los logs de los "
                             "servidores por donde pasa, así que la revocamos para "
                             "que nadie más la use.",
    "mail_api_exposed_fix": "Crea una nueva y mándala en la cabecera "
                            "Authorization, como dice la documentación.",

    "api_error_unauthorized": "Falta la clave de API, o no es válida. Va en la "
                              "cabecera Authorization: Bearer y tu clave.",
    "api_error_key_in_url": "La clave de API no va en la URL: va en la cabecera "
                            "Authorization. Si era una clave válida, la revocamos, "
                            "porque en la URL queda escrita en logs ajenos.",
    "api_error_ip_not_allowed": "Esta clave no se puede usar desde esta IP.",
    "api_error_account_suspended": "La cuenta está suspendida.",
    "api_error_account_closed": "La cuenta todavía no está abierta: le falta la "
                                "demostración o un plan.",
    "api_error_test_key_cannot": "Una clave de prueba solo puede leer y simular "
                                 "envíos.",
    "api_error_missing_scope": "Esta clave no tiene el permiso {scope}.",
    "api_error_rate_limited": "Demasiadas peticiones. Espera los segundos que dice "
                              "Retry-After y vuelve a intentar.",
    "api_error_not_found": "No existe, o no es de esta cuenta.",
    "api_error_method_not_allowed": "Esta dirección no acepta ese método.",
    "api_error_too_large": "La petición es demasiado grande.",
    "api_error_unavailable": "El servicio no está disponible en este momento. "
                             "Intenta de nuevo en unos segundos.",
    "api_error_internal_error": "Algo falló de nuestro lado. Si se repite, "
                                "escríbenos con el request_id.",
    "api_error_unsupported_media_type": "El cuerpo va en JSON, con Content-Type: "
                                        "application/json.",
    "api_error_bad_json": "El cuerpo no es un objeto JSON válido.",
    "api_error_validation_failed": "Hay campos que no están bien: los dice fields.",
    "api_error_bad_cursor": "El cursor no es válido: usa el next_cursor de la "
                            "respuesta anterior.",
    "api_error_bad_idempotency_key": "Idempotency-Key tiene que ser texto de hasta "
                                     "100 caracteres, sin espacios.",
    "api_error_idempotency_mismatch": "Esa Idempotency-Key ya se usó con otro "
                                      "cuerpo.",
    "api_error_idempotency_busy": "Hay otra petición con esa Idempotency-Key en "
                                  "curso. Espera y vuelve a intentar.",

    "api_field_unknown": "Este campo no existe.",
    "api_field_required": "Falta este campo.",
    "api_field_text": "Tiene que ser texto.",
    "api_field_long": "Tiene más de {n} caracteres.",
    "api_field_bool": "Tiene que ser true o false.",
    "api_field_int": "Tiene que ser un número entero de {low} a {high}.",
    "api_field_strings": "Tiene que ser una lista de textos, de hasta {n}.",
    "api_field_id": "No es un id válido.",
    "api_field_when": "Tiene que ser fecha y hora ISO 8601 con su zona, como "
                      "2026-10-20T15:00:00-05:00.",

    # --- la API: contactos (octubre de 2026) ----------------------------------
    "api_contacts_rows": "Van de 1 a {n} contactos por carga.",
    "api_contacts_consent": "Falta de dónde salieron: source es uno de {sources}, "
                            "y note (opcional) hasta 300 caracteres.",
    "api_contacts_email": "Ese correo no parece válido.",
    "api_contacts_unknown_tags": "Estas etiquetas no existen: {what}. Créalas antes "
                                 "con POST /tags.",
    "api_contacts_field_bad_fields": "fields tiene que ser un objeto con la clave de "
                                     "cada columna.",
    "api_contacts_field_unknown_field": "La columna {what} no existe. Créala antes "
                                        "con POST /fields.",
    "api_contacts_field_bad_value": "El valor de {what} no es de su tipo.",
    "api_contacts_missing": "Le faltan columnas: {what}. Todas son obligatorias.",
    "api_fields_type": "type es uno de {types}.",
    "api_limit_tags": "etiquetas",
    "api_limit_fields": "columnas",
    "api_suppressions_reason": "reason es uno de {reasons}.",
    "api_error_busy": "Hay otra operación como esta en curso en tu cuenta (una "
                      "carga de contactos, o guardar o bajar una plantilla). "
                      "Intenta en unos segundos.",
    "api_error_unknown_tag": "Hay etiquetas que no existen: las dice tags. Créalas "
                             "antes con POST /tags.",
    "api_error_email_taken": "Esa dirección ya la tiene otro contacto de la cuenta.",
    "api_error_tag_exists": "Esa etiqueta ya existe.",
    "api_error_limit_reached": "Llegaste al tope de {what} de tu plan: {n}.",
    "api_error_field_exists": "Ese nombre ya lo tiene otra columna, o es el de un "
                              "dato que todo contacto ya trae (Nombre, Correo).",
    "api_error_field_values": "{n} contactos tienen en esa columna algo que no es de "
                              "ese tipo. Corrígelos antes de cambiarlo.",

    # --- las listas dentro de un contacto y el id de su sistema (octubre de 2026)
    "contacts_external": "Id en tu sistema",
    "contacts_external_hint": "Opcional: su número de socio o de cliente. Con él "
                              "tu sistema lo encuentra por la API aunque cambie "
                              "el correo. Letras, números y . _ : @ -, hasta 64.",
    "contacts_external_bad": "Solo letras, números y . _ : @ -, hasta 64.",
    "contacts_external_taken": "Ese id ya lo tiene otro contacto.",
    "contacts_rows_hint": "Hasta {n} filas: si llega una más, se va la más vieja. "
                          "En una plantilla, {mark} arma la tabla.",
    "contacts_rows_none": "Todavía no tiene filas.",
    "contacts_rows_full": "Ya tiene {n} filas: al agregar otra se borra la más "
                          "vieja.",
    "contacts_rows_count": "{n} filas",
    "contacts_row_save": "Guardar la fila",
    "contacts_row_delete": "Borrar",
    "contacts_row_delete_ask": "¿Borrar esta fila? No se puede deshacer.",
    "contacts_row_delete_yes": "Sí, borrarla",
    "contacts_row_add_title": "Agregar una fila",
    "contacts_row_add": "Agregar la fila",
    "contacts_row_empty": "Escribe al menos un dato de la fila.",
    "contacts_rows_big": "La lista pasa del tamaño que cabe en un contacto: borra "
                         "filas viejas o acorta lo escrito.",
    "fields_type_list": "Lista",
    "fields_list_items": "Los datos de cada fila (solo para una lista)",
    "fields_list_items_hint": "Por ejemplo, para las transacciones de un socio: "
                              "Fecha, Descripción y Monto. De 1 a {n}.",
    "fields_list_item_name": "Nombre del dato {n}",
    "fields_list_item_type": "Tipo del dato {n}",
    "fields_list_item_example_0": "Fecha",
    "fields_list_item_example_1": "Descripción",
    "fields_list_item_example_2": "Monto",
    "fields_list_items_bad": "Una lista necesita de 1 a {n} datos, cada uno con su "
                             "nombre y sin repetir.",
    "fields_lists_full": "Ya tienes {n} listas, que es lo que cabe.",
    "fields_list_item_remove": "Quitar",
    "fields_list_item_remove_ask": "¿Quitar «{name}»? Se borra lo escrito en ese "
                                   "dato en todas las filas de todos tus contactos.",
    "fields_list_item_remove_yes": "Sí, quitarlo",
    "fields_list_item_new": "Dato nuevo",
    "fields_list_item_add": "Agregar dato",

    # --- la API: las listas de un contacto y el id de su sistema (octubre de 2026)
    "api_contacts_field_bad_list": "Una lista no está bien ({what}): cada fila "
                                   "lleva al menos uno de sus datos y cada valor "
                                   "de su tipo, sin pasar de las filas ni del "
                                   "tamaño que caben.",
    "api_lists_rows_bad": "Las filas no están bien ({what}): caben {n}, cada una "
                          "con al menos uno de sus datos y cada valor de su tipo.",
    "api_lists_too_big": "La lista pasaría del tamaño que cabe en un contacto: "
                         "borra filas viejas o acorta lo escrito.",
    "api_fields_items": "Una lista lleva de 1 a {n} datos, cada uno con label (su "
                        "nombre, sin repetir) y type ({types}).",
    "api_fields_add_or_remove": "Va uno de los dos: add para agregar un dato, o "
                                "remove con la clave del que se quita.",
    "api_fields_remove": "Ese dato no es de esta lista, o es el único que le queda.",
    "api_limit_lists": "listas",
    "api_error_external_id_taken": "Ese id de tu sistema ya lo tiene otro "
                                   "contacto de la cuenta.",

    # --- la API: plantillas, carpetas y fotos (octubre de 2026)
    "api_field_ref": "No existe, o no es de esta cuenta.",
    "api_field_one_line": "Va en una sola línea, sin caracteres de control.",
    "api_templates_send_from": "Tiene que ser el id de uno de tus remitentes listos "
                               "(GET /senders), o null para el predeterminado.",
    "api_templates_reply_to": "Tiene que ser uno de tus «Responder a» confirmados "
                              "(GET /senders), o null para el predeterminado.",
    "api_templates_source": "source es uno de {sources}.",
    "api_templates_not_canvas": "Solo una plantilla del lienzo tiene lienzo.",
    "api_templates_ids": "ids es una lista de 1 a {n} ids de plantillas.",
    "api_emails_type": "type es uno de {types}.",
    "api_folders_taken": "Ya tienes una carpeta con ese nombre.",
    "api_folders_color": "color es uno de {colors}.",
    "api_limit_templates": "plantillas",
    "api_limit_folders": "carpetas",
    "api_limit_images": "imágenes",
    "api_data_shape": "data es un objeto, con cada variable por su nombre.",
    "api_data_keys": "data lleva hasta {n} variables.",
    "api_data_size": "data pasa de {kb} KB.",
    "api_data_key": "Cada clave de data va en mayúsculas, números y _ (hasta 24), "
                    "como en la plantilla. CORREO no: es la dirección a la que va.",
    "api_data_value": "Cada valor de data es texto o un número de hasta {chars} "
                      "caracteres, en una sola línea, o una lista de filas.",
    "api_data_rows": "Una lista de data lleva hasta {rows} filas.",
    "api_data_row": "Cada fila de una lista es un objeto de 1 a {cells} datos, con "
                    "claves como las de data y valores de texto o número de hasta "
                    "{cell_chars} caracteres, en una sola línea.",

    # --- la API: los correos transaccionales y promocionales (octubre de 2026)
    "api_emails_one_body": "Va template_id (una plantilla tuya) o text (lo que "
                           "dice el correo), uno de los dos.",
    "api_emails_logo": "logo va solo con text: una plantilla ya trae lo suyo.",
    "api_emails_status": "status es uno de {statuses}.",
    "api_error_cannot_send": "Hoy esta cuenta no puede enviar: los motivos van en "
                             "blocked.",
    "api_error_not_a_contact": "Un promocional va solo a un contacto de tu cuenta. "
                               "Agrégalo antes con POST /contacts, o mándale un "
                               "transaccional.",
    "api_error_contact_incomplete": "A ese contacto le faltan columnas (van en "
                                    "missing): sin ellas no recibe promocionales.",
    "api_error_suppressed": "A esa dirección ya no se le escribe: se dio de baja, "
                            "no existe o marcó un correo como spam.",
    "api_error_undeliverable": "El dominio de esa dirección no recibe correo.",
    "api_error_demo_address": "En la demostración solo se envía a tus direcciones "
                              "de prueba confirmadas.",
    "api_error_missing_data": "La plantilla o el asunto usan variables sin dato (van "
                              "en missing): mándalas en data.",
    "api_error_bad_subject": "El asunto lleno trae un salto de línea, de un dato "
                             "del contacto: corrígelo y vuelve a enviar.",
    "api_error_throttled": "Amazon pidió esperar un momento. No se envió ni se gastó "
                           "cuota: reintenta tras Retry-After.",
    "api_error_delivery_failed": "No se pudo entregar a Amazon. No se gastó cuota: "
                                 "el detalle va en email.",

    # --- API → Correos en el panel (octubre de 2026)
    "dash_api_emails": "Correos",
    "api_emails_title": "Correos de la API",
    "api_emails_lead": "Lo que tu sistema envió por la API en los últimos {days} "
                       "días, y el estado de cada uno. Las campañas siguen en "
                       "Enviados.",
    "api_emails_col_when": "Cuándo",
    "api_emails_col_to": "Para",
    "api_emails_col_subject": "Asunto",
    "api_emails_col_kind": "Tipo",
    "api_emails_col_outcome": "Estado",
    "api_emails_from": "de {address}",
    "api_emails_kind_transactional": "Transaccional",
    "api_emails_kind_promotional": "Promocional",
    "api_emails_outcome_pending": "Sin confirmar",
    "api_emails_outcome_sent": "Enviado",
    "api_emails_outcome_failed": "Fallido",
    "api_emails_outcome_delivery": "Entregado",
    "api_emails_outcome_open": "Abierto",
    "api_emails_outcome_click": "Clic",
    "api_emails_outcome_bounce": "Rebotó",
    "api_emails_outcome_complaint": "Marcado como spam",
    "api_emails_newest": "Los más nuevos",
    "api_emails_older": "Más viejos",
    "api_emails_none": "Tu sistema todavía no ha mandado correos por la API.",

    "admin_api_sent": "Este mes mandó por la API {transactional} transaccionales y "
                      "{promotional} promocionales.",

    # --- el proceso en segundo plano (octubre de 2026)
    "send_state_scheduled_auto": "Programada para el {when}: sale sola",
    "send_state_going_auto": "El resto sale solo, por tandas.",
    "send_state_waiting": "No pudo salir. {why} Se vuelve a intentar sola.",
    "send_done_busy": "Esa campaña ya está saliendo.",
    "send_blocked_busy": "Ya está saliendo.",

    "send_blocked_suspended": "La cuenta está suspendida.",

    # --- la API: las campañas (octubre de 2026)
    "api_campaigns_past": "Esa hora ya pasó: para mandarla ya, usa send.",
    "api_error_campaign_sending": "Esa campaña está saliendo ahora: no se cambia, no "
                                  "se borra ni se reprograma hasta que termine.",

    "admin_worker_up": "El proceso en segundo plano está dando vueltas: lo "
                       "programado sale solo.",
    "admin_worker_down": "El proceso en segundo plano no da señales desde hace más "
                         "de un minuto: lo programado no está saliendo.",
    "admin_worker_never": "El proceso en segundo plano nunca ha arrancado: lo "
                          "programado no sale. Ver docs/api.md.",
    "admin_worker_key_mismatch": "Su SECRET_KEY no es la del web, y así no manda "
                                 "nada.",
    "admin_worker_key_unknown": "Todavía no comprobó su SECRET_KEY.",

    # --- los avisos a su sistema, webhooks (octubre de 2026)
    "dash_api_webhooks": "Webhooks",
    "webhooks_title": "Webhooks",
    "webhooks_lead": "Cuando pasa algo con tus correos (se entregó, rebotó, alguien "
                     "se dio de baja, terminó una campaña), te lo enviamos a tu "
                     "servidor, firmado, sin que tengas que preguntar.",
    "webhooks_done_deleted": "Se borró el webhook.",
    "webhooks_new": "Agregar un webhook",
    "webhooks_full": "Ya tienes {n} webhooks, que es el máximo.",
    "webhooks_col_url": "URL del endpoint",
    "webhooks_col_events": "Eventos",
    "webhooks_col_last": "La última vez",
    "webhooks_on": "Activo",
    "webhooks_off": "Inactivo",
    "webhooks_events_n": "{n} eventos",
    "webhooks_failing": "Fallando desde {when}",
    "webhooks_last": "Respondió {status}, {when}",
    "webhooks_never": "Todavía no se ha mandado nada.",
    "webhooks_open": "Abrir",
    "webhooks_none": "Todavía no tienes webhooks.",
    "webhooks_new_title": "Agregar un webhook",
    "webhooks_edit_title": "Editar el webhook",
    "webhooks_new_lead": "Tu servidor recibe un POST en JSON por cada evento, con la "
                         "firma en la cabecera Sobreala-Signature. Tiene que "
                         "responder un 2xx en menos de 5 segundos.",
    "webhooks_url": "URL del endpoint",
    "webhooks_url_hint": "https://, con un nombre (no una IP) y sin puerto. No puede "
                         "ser una dirección de una red interna.",
    "webhooks_url_url": "Tiene que ser una URL https:// completa, sin usuario ni "
                        "contraseña, de hasta 500 caracteres.",
    "webhooks_url_port": "Va sin puerto: solo el 443 de https.",
    "webhooks_url_ip": "Va con un nombre, no con una IP.",
    "webhooks_url_host": "Ese nombre no es de internet.",
    "webhooks_description": "Para qué es (opcional)",
    "webhooks_events": "Qué eventos",
    "webhooks_events_required": "Elige al menos un evento.",
    "webhooks_event_email_delivered": "Un correo llegó al buzón.",
    "webhooks_event_email_bounced": "Un correo rebotó (con permanent si la dirección "
                                    "no existe).",
    "webhooks_event_email_complained": "Alguien marcó un correo como spam.",
    "webhooks_event_email_rejected": "Amazon no lo mandó (traía un virus, por ejemplo).",
    "webhooks_event_email_opened": "Alguien abrió un correo (la primera vez).",
    "webhooks_event_email_clicked": "Alguien hizo clic en un enlace (nunca en un "
                                    "transaccional).",
    "webhooks_event_email_downloaded": "Alguien bajó el archivo de un correo individual.",
    "webhooks_event_contact_unsubscribed": "Un contacto se dio de baja.",
    "webhooks_event_campaign_finished": "Una campaña terminó de salir, con sus cifras.",
    "webhooks_save": "Guardar",
    "webhooks_create": "Agregar el webhook",
    "webhooks_secret_title": "El secreto de firma del webhook",
    "webhooks_created_lead": "Listo: los eventos van a {host}. Este es su secreto de "
                             "firma, con el que tu servidor comprueba que cada evento "
                             "es nuestro.",
    "webhooks_rotated_lead": "Este es el secreto de firma nuevo de {host}. El de "
                             "antes ya no sirve: cámbialo en tu servidor.",
    "webhooks_secret_label": "Secreto de firma",
    "webhooks_secret_where": "Se ve solo ahora. Guárdalo en tu servidor, nunca en una "
                             "página web ni en un repositorio. Si lo pierdes, cámbialo "
                             "por otro.",
    "webhooks_how_verify": "Cómo comprobar la firma",
    "webhooks_done_saved": "Se guardó el webhook.",
    "webhooks_done_on": "El webhook está activo.",
    "webhooks_done_off": "El webhook está inactivo: no se envía nada.",
    "webhooks_test_ok": "Tu servidor respondió {status} en {ms} ms.",
    "webhooks_test_bad": "Falló: respondió {status} ({error}) en {ms} ms.",
    "webhooks_test_many": "Ya mandaste varios de prueba en la última hora. Espera un "
                          "poco.",
    "webhooks_switched_off": "Lo desactivamos porque tu servidor llevaba 72 horas sin "
                             "responder bien. Arréglalo y actívalo otra vez.",
    "webhooks_test": "Enviar uno de prueba",
    "webhooks_turn_off": "Desactivar",
    "webhooks_turn_on": "Activar",
    "webhooks_edit": "Editar",
    "webhooks_rotate": "Cambiar el secreto de firma",
    "webhooks_delete": "Borrar",
    "webhooks_deliveries": "Las últimas entregas",
    "webhooks_col_event": "Evento",
    "webhooks_col_result": "Estado",
    "webhooks_col_attempts": "Intentos",
    "webhooks_status_pending": "Por entregar",
    "webhooks_status_delivered": "Entregado",
    "webhooks_status_failed": "Fallido",
    "webhooks_no_deliveries": "Todavía no se ha enviado nada a este webhook.",
    "webhooks_ask_secret_title": "Cambiar el secreto de firma de {host}",
    "webhooks_ask_secret_lead": "El de ahora deja de servir en ese momento: los "
                                "eventos que lleguen con la firma vieja tu servidor "
                                "los va a rechazar hasta que pongas el nuevo.",
    "webhooks_ask_secret_yes": "Cambiar el secreto de firma",
    "webhooks_ask_delete_title": "Borrar el webhook a {host}",
    "webhooks_ask_delete_lead": "No se le manda nada más, y se borran sus entregas "
                                "pendientes. No se puede deshacer.",
    "webhooks_ask_delete_yes": "Sí, borrarlo",
    "mail_webhook_added_subject": "Se agregó un webhook a tu cuenta",
    "mail_webhook_added_heading": "Tus datos van a un servidor nuevo",
    "mail_webhook_added_body": "Desde ahora, lo que pasa con tus correos se manda a "
                               "{host}. Se agregó desde la IP {ip}.",
    "mail_webhook_button": "Ver mis webhooks",
    "mail_webhook_off_subject": "Desactivamos uno de tus webhooks",
    "mail_webhook_off_heading": "Tu servidor no responde",
    "mail_webhook_off_body": "Los eventos de tus correos se enviaban a {host}, que "
                             "lleva 72 horas sin responder bien, así que desactivamos "
                             "el webhook.",
    "mail_webhook_off_fix": "Cuando tu servidor esté listo, actívalo otra vez en "
                            "Dashboard → API → Webhooks.",

    "admin_api_hooks": "Envía sus webhooks a:",

    # --- la API: envíos, estadísticas y eventos (octubre de 2026)
    "api_stats_tz": "tz es el nombre de una zona, como America/Panama.",
    "api_stats_period": "period es uno de {periods}.",
    "api_stats_outcome": "outcome es uno de {outcomes}.",
    "api_stats_kind": "type es uno de {kinds}.",
    "api_stats_offset": "offset es un número entero desde 0.",

    # --- el registro (octubre de 2026): nombres, teléfonos de Panamá, la
    # dirección por partes, los términos y las novedades
    "error_company_name": "Escribe el nombre de tu negocio: de 2 a 80 caracteres, con "
                          "letras. Puede llevar números y signos como & . , -",
    "error_person_name": "Escribe un nombre de persona: de 2 a 60 caracteres, solo "
                         "letras.",
    "error_phone_pa_mobile": "Tu teléfono personal tiene que ser un celular de Panamá: 8 "
                             "dígitos que empiezan con 6.",
    "error_phone_pa_number": "Un número de Panamá tiene 8 dígitos si es celular (empieza "
                             "con 6) o 7 si es fijo.",
    "address_title": "Dirección de tu negocio",
    "address_line1": "Dirección",
    "address_line1_hint": "Calle o avenida, número, barriada o lugar.",
    "address_line2": "Dirección, línea 2 (opcional)",
    "address_line2_hint": "Apartamento, oficina, piso o edificio.",
    "address_city": "Ciudad",
    "address_region": "Provincia o estado",
    "address_postal_code": "Código postal (opcional)",
    "address_country": "País",
    "address_line1_bad": "Escribe la calle o el lugar: de 5 a 200 caracteres.",
    "address_line2_bad": "La línea 2 lleva hasta 100 caracteres.",
    "address_city_bad": "Escribe la ciudad.",
    "address_region_bad": "Escribe la provincia o el estado.",
    "address_postal_code_bad": "El código postal lleva hasta 10 letras, números o guiones.",
    "address_country_bad": "Elige un país de la lista.",
    "address_bad": "Revisa la dirección: falta algo o no está bien escrito.",
    "register_terms_accept": "Acepto los",
    "register_news": "Quiero recibir novedades y comunicados de Sobreala. Los puedes "
                     "dejar de recibir cuando quieras.",
    "error_terms_required": "Para crear tu cuenta, acepta los términos y condiciones y la "
                            "política de privacidad.",
    "settings_part_notifications_news": "Novedades de Sobreala",
    "settings_news": "Novedades y comunicados",
    "settings_news_desc": "Mejoras, funciones nuevas y comunicados de Sobreala. Nunca "
                          "publicidad de otras empresas.",
    "admin_terms": "Términos",
    "admin_terms_accepted": "Aceptó la versión del {version}, el {when}",
    "admin_terms_none": "Se registró antes de la casilla",
    "admin_news": "Novedades de Sobreala",
    "admin_news_yes": "Sí, desde el {when}",
    "admin_news_no": "No",

    # --- Google y GitHub (octubre de 2026): solo entran a la cuenta conectada
    # a ellos, y se conectan desde Seguridad
    "join_or": " o ",
    "oauth_has_password": "Ya tienes una cuenta con {email} que entra con contraseña. "
                          "Entra con ella y, si quieres, conecta {provider} en "
                          "Configuración → Seguridad.",
    "oauth_has_other": "Esa cuenta entra con {other}. Usa ese botón para entrar.",
    "oauth_has_account": "Ya hay una cuenta con {email}. Entra con tu contraseña, o "
                         "recupérala con «¿Olvidaste tu contraseña?».",
    "oauth_connect": "Conectar",
    "oauth_done_on": "Listo, conectaste {provider}. Desde ahora también entras con él.",
    "oauth_taken": "Esa cuenta de {provider} ya está conectada a otra cuenta de Sobreala.",
    "oauth_lost": "No se conectó {provider}: la sesión cambió a mitad de camino. Vuelve "
                  "a intentarlo.",
    "erase_replaced": "Registro sin confirmar, reemplazado al registrarse con {provider}",
    "connect_title": "Conectar {provider}",
    "connect_lead": "Después podrás entrar a esta cuenta con tu cuenta de {provider}. Te "
                    "llevamos a {provider} para que elijas cuál.",
    "connect_proof_lead": "Conectar {provider} abre tu cuenta por otra puerta, así que "
                          "antes te pedimos tu contraseña. Después, por 10 minutos, no te "
                          "la volvemos a pedir.",
    "connect_submit": "Continuar a {provider}",
    "mail_connect_code_subject": "Tu código para conectar {provider}",
    "mail_connect_code_heading": "Tu código para conectar {provider}",
    "mail_connect_code_body": "Alguien con tu sesión abierta pidió conectar {provider} a tu "
                              "cuenta de Sobreala. Si fuiste tú, escribe este código. Si "
                              "no, no hagas nada: sin el código no se conecta nada.",
    "mail_connected_subject": "Se conectó {provider} a tu cuenta",
    "mail_connected_heading": "Se conectó {provider} a tu cuenta",
    "mail_connected_body": "Desde ahora se puede entrar a tu cuenta de Sobreala con una "
                           "cuenta de {provider}. Se conectó desde la IP {ip}.",
    "mail_connected_not_you": "Si no fuiste tú, desconéctalo en Configuración → Seguridad "
                              "y cambia tu contraseña.",
    "mail_connected_button": "Ver mi seguridad",
    "mail_exists_body_provider": "Alguien intentó registrarse en Sobreala con esta "
                                 "dirección, que ya tiene una cuenta. Si fuiste tú, entra "
                                 "con {provider}.",

    "oauth_signup_replaces": "Ese correo tenía un registro con contraseña que nadie "
                             "confirmó. Al crear tu cuenta con {provider}, ese registro "
                             "se borra.",

    # --- las cuentas eliminadas en administración (octubre de 2026)
    "activity_kind_erased": "Cuenta eliminada",
    "admin_erased_name": "{company} (eliminada)",
    "admin_erased_title": "{company} (eliminada)",
    "admin_erased_lead": "La cuenta ya no existe. Esto es lo que se guarda de ella: su "
                         "ficha mínima, quién la eliminó y por qué, y los pagos, que se "
                         "quedan por ley.",
    "admin_erased_when": "Eliminada",
    "admin_erased_by": "Quién la eliminó",
    "admin_erased_by_self": "El propio cliente",
    "admin_erased_by_admin": "Administración ({email})",
    "admin_erased_reason": "Motivo",
    "admin_erased_owner": "Dueño",
    "admin_erased_plan": "Plan",
    "admin_erased_since": "Cliente desde",
    "admin_erased_counts": "Lo que se borró",
    "admin_erased_outside": "No se pudo soltar afuera: {what}",
    "admin_erased_payments": "Pagos que se quedan",
    "admin_erased_no_payments": "No tenía pagos.",
    "admin_erased_back": "Volver a Eventos",

    # --- la demostración (octubre de 2026): «Otra forma» dice cuál, y el aviso
    # dice qué pasa ahora
    "welcome_demo_source_other_label": "¿Cuál?",
    "welcome_demo_source_other_hint": "Si elegiste «Otra forma», cuéntanos cómo los "
                                      "conseguiste.",
    "error_demo_other": "Cuéntanos cómo los conseguiste: de {min} a {max} caracteres.",
    "welcome_demo_done_wait": "La revisamos pronto. Cuando la aprobemos, te llegará un "
                              "correo a {email} para que empieces.",
}


def t(key: str, **kwargs) -> str:
    text = TEXTS[key]
    return text.format(**kwargs) if kwargs else text


# Los atajos del lienzo, en un solo sitio: la lista de la pantalla sale de
# aquí. No van en TEXTS porque `t()` devuelve texto, no pares.
CANVAS_KEYS = (
    ("Mover lo elegido", "Flechas (con Mayús, de a 10)"),
    ("Borrar", "Suprimir o Retroceso"),
    ("Deshacer y rehacer", "Ctrl+Z y Ctrl+Y"),
    ("Copiar, cortar y pegar", "Ctrl+C, Ctrl+X y Ctrl+V"),
    ("Duplicar", "Ctrl+D"),
    ("Elegir todo", "Ctrl+A"),
    ("Elegir varios", "Mayús y clic, o arrastrar sobre la hoja"),
    ("Escribir en un texto", "Doble clic"),
    ("Pegar una foto", "Ctrl+V"),
    ("Soltar lo elegido, salir del texto o del recorte", "Esc"),
)


# Las provincias y comarcas de Panamá, que el campo «Provincia o estado» de la
# dirección sugiere (un `datalist`: se puede escribir otra, de otro país). No van
# en TEXTS porque `t()` devuelve texto, no listas.
PANAMA_REGIONS = ("Bocas del Toro", "Chiriquí", "Coclé", "Colón", "Darién", "Herrera",
                  "Los Santos", "Panamá", "Panamá Oeste", "Veraguas", "Guna Yala",
                  "Emberá-Wounaan", "Ngäbe-Buglé", "Naso Tjër Di")


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
