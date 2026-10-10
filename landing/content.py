"""All the copy of the public site, in one place.

Everything a non-developer might want to reword lives here: headlines, section
text, cards, steps, FAQ, footer links and contact details. The templates only
lay it out.

Prices are NOT here. They are read from docs/pricing.md at build time by
build_site.py, so the site can never drift from that document.

Language rule of the project: code and keys in English, everything the visitor
reads in Spanish.
"""

from __future__ import annotations

# --------------------------------------------------------------------------- site

SITE = {
    "name": "Sobreala",
    "domain": "sobreala.com",
    "base_url": "https://sobreala.com",
    "locale": "es",
    "tagline": "Administra tu base de correos y envía de manera organizada.",
}

# Contact. The WhatsApp link carries a prefilled message so the conversation
# starts with context instead of a blank "hola".
CONTACT = {
    "whatsapp_number": "50760807972",
    "whatsapp_display": "+507 6080-7972",
    "whatsapp_message": "Hola, me interesa Sobreala para mi negocio.",
    "email": "info@sobreala.com",
    # Prefilled like the WhatsApp message, so the conversation starts with context.
    "email_subject": "Consulta sobre Sobreala",
    "email_body": "Hola, me interesa Sobreala para mi negocio.",
    "email_copy_label": "Copiar",
    "email_copied_label": "Copiado",
    "instagram_user": "sobreala",
    "instagram_url": "https://instagram.com/sobreala",
}

NAV = [
    {"label": "Inicio", "url": "/#inicio"},
    {"label": "Planes", "url": "/#planes"},
    {"label": "Cómo funciona", "url": "/#como-funciona"},
    {"label": "Nosotros", "url": "/#nosotros"},
]

# The panel is a different service on a different host: Railway, not Cloudflare
# Pages. These two buttons are the only way in from the public site.
PANEL = {
    "base_url": "https://app.sobreala.com",
    "login_label": "Ingresar",
    "register_label": "Registrarse",
    # Se enseña en lugar de los dos anteriores cuando el panel dejó su migaja.
    "account_label": "Mi cuenta",
    # El menú de la barra. Sin sesión solo se ven el modo y el idioma; con
    # sesión aparecen además las tres que necesitan una cuenta.
    "options_label": "Opciones",
    "send_label": "Enviar correos",
    "contacts_label": "Contactos",
    "designs_label": "Plantillas",
    "settings_label": "Configuración",
    "panel_label": "Estadísticas",
    # La de una cuenta que todavía no se abrió (ni demostración ni pago), en
    # lugar de las cuatro de cliente. La misma fila que el menú del panel.
    "demo_label": "Tu demostración",
    # Solo la ve quien tiene el rol, y quien lo decide es la galleta que deja
    # el panel: este sitio es estático y no sabe quién mira.
    "admin_label": "Administración",
    "switch_label": "Cambiar de cuenta",
    "logout_label": "Cerrar sesión",
    "theme_dark": "Modo oscuro",
    "theme_light": "Modo claro",
    "language_label": "Idioma",
    "language_current": "Español",
    "language_soon": "Inglés (pronto)",
}

# Lo que dicen los botones de /pricing cuando ya hay un plan contratado. El
# sitio es estático y no lo sabe al construirse: los textos viajan en el
# marcado y nav.js elige uno según la migaja que deja el panel. El plan que ya
# se tiene no se renueva antes de que venza: dice lo mismo que los de abajo,
# salvo en anual para quien lo tiene mensual, que es pasarlo a anual. Quien
# tiene un anual solo mejora a otro anual.
PLAN_BUTTONS = {
    "start": "Obtener Plan {name}",
    "upgrade": "Mejorar a {name}",
    "to_yearly": "Pasar a anual",
    "covered": "Ya tienes todas las ventajas",
    "yearly_only": "Solo en anual",
}

CTA_PRIMARY = {"label": "Contáctanos por WhatsApp", "kind": "whatsapp"}
CTA_SECONDARY = {"label": "Ver los planes", "url": "/#planes"}

# --------------------------------------------------------------------------- home

HOME = {
    "meta_title": "Sobreala · Email marketing para tu negocio",
    "meta_description": (
        "Email marketing sin complicaciones: sube tus contactos, escribe tu campaña "
        "y envíala por correo a toda tu lista desde un solo panel."
    ),
    "hero": {
        "title_lead": "Administra tu base de datos de correos",
        "title_accent": "y envía de manera organizada.",
        "subtitle": "Envía un correo a todos tus contactos con un solo click.",
        "note": "Escríbenos y te acompañamos en tu primera campaña.",
    },
    "problem": {
        # Sin etiqueta de arriba ni entradilla: la pregunta lo dice todo.
        "title": "¿Sigues enviando correos masivos desde Gmail o Outlook?",
        # `art` nombra el archivo de la ilustración (partials/art-<art>.svg.j2),
        # `lead` es la línea que va en el panel y `text` el párrafo que va
        # debajo de la ilustración.
        "items": [
            {
                "art": "manual",
                "title": "Hacerlo a mano cuesta horas",
                "lead": (
                    "Copiar y pegar el mismo mensaje miles de veces no es una "
                    "solución viable."
                ),
                "text": (
                    "Los envíos manuales consumen tiempo y aumentan las "
                    "posibilidades de cometer errores: contactos que reciben el "
                    "correo más de una vez, destinatarios que quedan fuera o "
                    "mensajes enviados con información incorrecta."
                ),
            },
            {
                "art": "spam",
                "title": "Evita problemas de spam",
                "lead": (
                    "Enviar correos masivos desde tu cuenta personal puede afectar "
                    "la entregabilidad."
                ),
                "text": (
                    "Gmail y Outlook tienen límites de envío y sus cuentas "
                    "convencionales no están diseñadas para campañas masivas. Los "
                    "envíos frecuentes o de gran volumen pueden aumentar el riesgo "
                    "de que tus correos terminen en spam o que alcances los límites "
                    "de tu cuenta."
                ),
            },
            {
                "art": "privacy",
                "title": "Protege la privacidad de tus contactos",
                "lead": (
                    "Tus clientes y colaboradores no deberían quedar expuestos en "
                    "un correo."
                ),
                "text": (
                    "Enviar a múltiples destinatarios desde una cuenta convencional "
                    "puede revelar las direcciones de tus contactos. Una plataforma "
                    "especializada permite gestionar tus destinatarios de forma "
                    "individual, evitando exponer tu lista de contactos "
                    "innecesariamente."
                ),
            },
            {
                "art": "tracking",
                "title": "¿Realmente llegó tu correo?",
                "lead": (
                    "Sin una herramienta de seguimiento, no sabes qué pasó después "
                    "de presionar «Enviar»."
                ),
                "text": (
                    "No puedes saber con certeza qué mensajes fueron entregados, "
                    "cuáles tuvieron interacción o qué enlaces recibieron clics. "
                    "Tampoco puedes identificar fácilmente direcciones inactivas o "
                    "que ya no existen, haciendo más difícil mantener una lista de "
                    "contactos actualizada."
                ),
            },
        ],
    },
    "features": {
        # Sin etiqueta de arriba, a diferencia de las demás secciones: el
        # titular ya es la etiqueta.
        "title": "Features",
        # Las flechas del carrusel de capturas. Solo las dibuja el guion.
        "back": "Ver la anterior",
        "next": "Ver la siguiente",
        # La ventana de ver una captura en grande, que también dibuja el guion.
        "zoom": "Captura del panel, en grande",
        "close": "Cerrar la captura",
        "intro": (
            "Estas son las pantallas con las que trabajas: tus contactos, tus "
            "plantillas, tus envíos y lo que pasó con cada correo."
        ),
        "items": [
            {
                "icon": "contacts",
                "shot": "contactos",
                "alt": (
                    "La lista de contactos del panel, con el correo de cada "
                    "persona, su nombre, sus columnas propias, su estado y sus "
                    "etiquetas."
                ),
                "title": "Contactos sin duplicados",
                "text": (
                    "Cada dirección existe una sola vez en tu cuenta. Si una persona "
                    "lleva varias etiquetas y la campaña va a más de una, recibe una "
                    "sola copia y gasta un solo envío."
                ),
            },
            {
                "icon": "campaign",
                "shot": "lienzo",
                "alt": (
                    "El editor de plantillas: un texto elegido sobre la hoja, con "
                    "su barra de fuente, tamaño y color, y el correo armándose al "
                    "lado."
                ),
                "title": "Campañas creadas en el editor",
                "text": (
                    "Diseña tus campañas directamente desde el editor, colocando "
                    "textos, botones e imágenes donde quieras. Además, puedes "
                    "importar una campaña creada por otra persona y continuar "
                    "editándola desde tu propia cuenta."
                ),
            },
            {
                "icon": "schedule",
                "shot": "envios",
                "alt": (
                    "La pantalla de enviar correos, con el asunto escrito, una "
                    "etiqueta marcada, la plantilla elegida y la opción de mandarlo "
                    "ahora o a una fecha y hora."
                ),
                "title": "Envío inmediato o programado",
                "text": (
                    "Selecciona tu lista, revisa la vista previa y envíate una prueba "
                    "antes de enviar. Luego, elige si quieres que tu campaña salga de "
                    "inmediato o en la fecha y hora que prefieras."
                ),
            },
            {
                "icon": "chart",
                "shot": "estadisticas",
                "alt": (
                    "La pantalla de estadísticas: enviados, entregados, rebotes, "
                    "aperturas y clics, cada cifra comparada con el periodo "
                    "anterior, y las gráficas de envíos y de aperturas."
                ),
                "title": "Resultados de cada campaña",
                "text": (
                    "Entregados, aperturas, clicks, rebotes y bajas, por campaña, con "
                    "exportación a CSV y PDF."
                ),
            },
            {
                "icon": "shield",
                "shot": "baja",
                "alt": (
                    "La pantalla que abre quien pulsa el enlace de baja, con el "
                    "botón de dejar de recibir estos correos."
                ),
                "title": "Cada persona puede anular su suscripción cuando quiera",
                "text": (
                    "Todos los correos llevan el botón para anular la suscripción, en "
                    "todos los planes. Quien lo usa deja de recibir al momento y tú no "
                    "tienes que hacer nada."
                ),
            },
        ],
    },
    # La tira de plantillas de muestra, donde estaban los cuatro pasos: los
    # pasos siguen enteros en los tutoriales, justo debajo, que es a donde lleva
    # el botón.
    "steps": {
        "eyebrow": "Cómo funciona",
        "title": "¿Aún no sabes por dónde empezar?",
        "intro": "Prueba nuestras plantillas personalizadas.",
        # Lo que dice cada tarjeta a un lector de pantalla, con su nombre.
        "open": "Abrir la plantilla {name} en el editor",
        "cta": {"label": "Ver tutorial", "url": "#tutorials"},
    },
    "faq": {
        "eyebrow": "Preguntas frecuentes",
        "title": "Lo que suelen preguntarnos",
        "items": [
            {
                "q": "¿Cómo empiezo?",
                "a": (
                    "Creas tu cuenta y nos pides una demostración. En ella abrimos "
                    "tu cuenta y, contigo, recorremos el panel, vemos de dónde sale "
                    "tu lista, la importamos y armamos tu primer correo. Si ya sabes "
                    "qué plan quieres, lo contratas y empiezas enseguida."
                ),
            },
            {
                "q": "¿Necesito tener un dominio propio?",
                "a": (
                    "No. Los correos salen desde un subdominio de Sobreala con el "
                    "nombre de tu negocio como remitente y tu correo para respuestas. "
                    "Si tienes dominio propio, lo configuramos contigo durante la "
                    "activación."
                ),
            },
            {
                "q": "¿Puedo subir la lista que ya tengo?",
                "a": (
                    "Sí, desde un archivo CSV. Al importar te decimos cuántos contactos "
                    "entraron y cuántos estaban dados de baja y no recibirán correos."
                ),
            },
            {
                "q": "¿Qué pasa si alguien no quiere recibir más correos?",
                "a": (
                    "Todos los correos llevan un enlace de baja de un click, en todos "
                    "los planes, y no se puede quitar. Quien se da de baja queda fuera "
                    "de tus envíos automáticamente."
                ),
            },
            {
                "q": "¿Cómo se paga?",
                "a": (
                    "Con los medios de pago que ves al pie de esta página. Los datos de "
                    "la tarjeta se manejan siempre en el sitio del proveedor de pago, "
                    "nunca en Sobreala."
                ),
            },
            {
                "q": "¿Ustedes me diseñan el correo?",
                "a": (
                    "No hace falta: la armas tú en el editor, con tu logo, tus "
                    "colores y tus fotos. Y si alguien te la prepara, te pasa el "
                    "archivo y la sigues editando tú."
                ),
            },
            {
                "q": "¿Qué pasa si no uso todos mis correos del mes?",
                "a": (
                    "Los correos que no uses pasan al mes siguiente y vencen ahí. Al "
                    "enviar se gastan primero los acumulados, para que no se pierdan."
                ),
            },
            {
                "q": "¿Puedo cambiar de plan después?",
                "a": (
                    "Sí. Puedes subir o bajar de plan según cómo crezca tu lista. Al "
                    "subir de plan, la marca de agua del plan Básico desaparece sola."
                ),
            },
            {
                "q": "¿Qué es la marca de agua del plan Básico?",
                "a": (
                    "Una línea discreta al pie del correo que dice que fue enviado con "
                    "Sobreala. Solo aparece en el plan Básico. Es distinta del enlace "
                    "de baja, que va en todos los planes."
                ),
            },
            {
                "q": "¿Hay permanencia o penalización por cancelar?",
                "a": (
                    "No hay permanencia mínima y puedes cancelar cuando quieras. El "
                    "saldo de correos acumulados se pierde al cancelar."
                ),
            },
            {
                "q": "¿El cobro es automático cada mes?",
                "a": (
                    "Depende del medio de pago que elijas. Con algunos el cobro se "
                    "renueva solo; con otros te enviamos el enlace de pago antes de cada "
                    "vencimiento. Te lo confirmamos al activar tu cuenta."
                ),
            },
        ],
    },
}

# The sample templates of the home page strip. Each slug is a ZIP in
# backend/sample_templates/ (a test checks both lists match), and clicking one
# opens it in the editor. Each card shows its picture, made from that ZIP by
# landing/samples.py.
SAMPLES = [
    {"slug": "restaurant", "name": "Restaurante"},
    {"slug": "perfume", "name": "Perfumería"},
    {"slug": "hiring", "name": "Reclutamiento"},
    {"slug": "real-estate", "name": "Bienes raíces"},
]

# The tutorials of the "cómo funciona" page: one per section of the panel. The
# screenshots and where each dot goes are made by landing/tutorials.py; the
# words live here. Each step says what to press ("do") and what for ("why"),
# and a test checks that every step of tutorials.py has its words here.
TUTORIALS = {
    "eyebrow": "Tutoriales",
    "title": "Aprende a usar el panel, pulsando",
    "intro": (
        "Estas son las pantallas de verdad. Pulsa el punto que late y avanzas, como "
        "si estuvieras dentro de tu cuenta."
    ),
    # Lo que dice el reproductor.
    "step": "Paso {n} de {total}",
    "back": "Atrás",
    "restart": "Empezar de nuevo",
    "press": "Pulsar: {what}",
    "finish": "Terminar",
    "done_title": "¡Listo!",
    "again": "Repetir",
    "next": "Siguiente tutorial: {name}",
    "signup": {"label": "Crear mi cuenta", "url": "https://app.sobreala.com/signup"},
    "screen": "Pantalla del panel: {what}",
    "tours": [
        {
            "id": "contacts",
            "name": "Contactos",
            "lead": "Crea una etiqueta e importa tu lista desde un archivo CSV.",
            "done": (
                "Tu lista ya está dentro, con su etiqueta y su origen. Si una dirección "
                "venía repetida, quedó una sola vez."
            ),
            "steps": {
                "menu": {
                    "do": "Abre el menú con el nombre de tu empresa",
                    "why": "Desde ahí llegas a todo el panel.",
                },
                "entrar": {
                    "do": "Entra a Contactos",
                    "why": "Es tu lista: quién recibe tus correos.",
                },
                "etiquetas": {
                    "do": "Abre Etiquetas",
                    "why": (
                        "Las etiquetas son tus grupos: clientes, socios, boletín. Se "
                        "crean primero y después se eligen."
                    ),
                },
                "nueva": {
                    "do": "Escribe el nombre y pulsa Crear",
                    "why": "Aquí la llamamos «Socios».",
                },
                "importar": {
                    "do": "Ve a Importar",
                    "why": (
                        "La etiqueta ya quedó creada. Ahora sube la lista que ya "
                        "tienes, en un archivo CSV."
                    ),
                },
                "archivo": {
                    "do": "Elige tu archivo",
                    "why": (
                        "Un CSV con una columna de correos. Si trae nombres, también "
                        "los leemos."
                    ),
                },
                "columnas": {
                    "do": "Di dónde va cada columna",
                    "why": (
                        "El correo y el nombre se reconocen solos. Las demás las eliges "
                        "tú, o las dejas fuera."
                    ),
                },
                "origen": {
                    "do": "Cuéntanos de dónde salió la lista",
                    "why": (
                        "Lo guardamos con cada contacto: es lo que se enseña si alguien "
                        "reclama. Marca también su etiqueta."
                    ),
                },
                "subir": {
                    "do": "Pulsa Importar",
                    "why": "En unos segundos te decimos qué pasó con tu archivo.",
                },
                "resultado": {
                    "do": "Esto pasó con tu archivo",
                    "why": (
                        "Cuántas filas se leyeron, cuántos contactos son nuevos y "
                        "cuántos ya estaban."
                    ),
                },
            },
        },
        {
            "id": "templates",
            "name": "Plantillas",
            "lead": "Arma tu correo en el editor, míralo y guárdalo.",
            "done": (
                "Tu plantilla está guardada y lista para enviar. También puedes cargar "
                "una que alguien te pasó, con «Cargar plantilla (ZIP)»."
            ),
            "steps": {
                "menu": {
                    "do": "Abre el menú con el nombre de tu empresa",
                    "why": "Las plantillas están ahí, debajo de Contactos.",
                },
                "entrar": {
                    "do": "Entra a Plantillas",
                    "why": "Son los correos que armas para mandar.",
                },
                "crear": {
                    "do": "Pulsa Crear plantilla",
                    "why": "Se abre el editor con una hoja en blanco.",
                },
                "texto": {
                    "do": "Agrega un texto",
                    "why": (
                        "Con estos botones pones textos, botones, imágenes y figuras "
                        "en la hoja."
                    ),
                },
                "escribir": {
                    "do": "Doble clic para escribir",
                    "why": (
                        "Arrástralo a donde quieras. Arriba cambias su letra, su tamaño "
                        "y su color."
                    ),
                },
                "armada": {
                    "do": "Así se ve una ya armada: pulsa el título",
                    "why": "Al pulsar algo, la barra de arriba enseña lo que puedes cambiarle.",
                },
                "vista": {
                    "do": "Pulsa Previsualización",
                    "why": "Ves el correo tal como va a llegar, también en el teléfono.",
                },
                "cerrar": {
                    "do": "Ciérrala cuando termines de mirar",
                    "why": (
                        "El botón para anular la suscripción se agrega solo, en todos "
                        "los correos."
                    ),
                },
                "guardar": {
                    "do": "Pulsa Guardar",
                    "why": (
                        "Se puede guardar cuando la revisión de arriba está en verde: "
                        "es lo que evita que tu correo vaya a spam."
                    ),
                },
                "listo": {
                    "do": "Tu plantilla quedó guardada",
                    "why": "Aparece en tu lista, lista para usarla en un envío.",
                },
            },
        },
        {
            "id": "campaigns",
            "name": "Enviar correos",
            "lead": "Arma una campaña, elige a quién le llega y mándala.",
            "done": (
                "Al confirmar, sale. Después, en «Campañas enviadas», cada envío tiene su "
                "Detalles con lo que pasó con cada persona."
            ),
            "steps": {
                "menu": {
                    "do": "Abre el menú con el nombre de tu empresa",
                    "why": "Enviar correos está justo debajo de Estadísticas.",
                },
                "entrar": {
                    "do": "Entra a Enviar correos",
                    "why": "Aquí armas cada campaña.",
                },
                "asunto": {
                    "do": "Escribe el asunto",
                    "why": "Es lo primero que se lee, y muchas veces lo único. Corto y concreto.",
                },
                "etiquetas": {
                    "do": "Marca a quién le llega",
                    "why": (
                        "Puedes marcar varias etiquetas: quien lleve más de una recibe un "
                        "solo correo. Sin marcar ninguna, le llega a toda tu lista."
                    ),
                },
                "plantilla": {
                    "do": "Elige la plantilla",
                    "why": "Una de las que guardaste en Plantillas.",
                },
                "cuando": {
                    "do": "Elige cuándo sale",
                    "why": "Ahora mismo, o en la fecha y hora que prefieras.",
                },
                "guardar": {
                    "do": "Pulsa Guardar la campaña",
                    "why": "Queda guardada: la puedes mandar hoy y volver a usarla después.",
                },
                "mandar": {
                    "do": "Pulsa Enviar",
                    "why": "Antes de salir, el panel te pregunta.",
                },
                "pregunta": {
                    "do": "Revisa y confirma",
                    "why": (
                        "Te dice el asunto, a cuántos contactos va y cuántos correos te "
                        "quedan. Un correo que salió no se puede recoger."
                    ),
                },
            },
        },
        {
            "id": "stats",
            "name": "Estadísticas",
            "lead": "Mira cómo le fue a cada envío y bájalo en CSV o PDF.",
            "done": (
                "Cada envío deja su registro: entregados, aperturas, clics, rebotes y "
                "bajas, persona por persona."
            ),
            "steps": {
                "periodo": {
                    "do": "Elige el periodo",
                    "why": "De la última hora a los últimos 90 días. Aquí, 30 días.",
                },
                "cifras": {
                    "do": "Así le fue a tus correos",
                    "why": (
                        "Cada cifra se compara con el periodo anterior: en verde si "
                        "mejoró y en rojo si empeoró."
                    ),
                },
                "grafica": {
                    "do": "Pasa el ratón por la gráfica",
                    "why": "Cada barra dice cuántos salieron ese día y cuántos rebotaron.",
                },
                "bajar": {
                    "do": "Bájalo en CSV o en PDF",
                    "why": "Lo mismo que ves, para guardarlo o llevarlo a una reunión.",
                },
                "mejores": {
                    "do": "Abre uno de tus mejores envíos",
                    "why": "Están ordenados por aperturas. Pulsa uno para ver a quién le llegó.",
                },
                "detalles": {
                    "do": "Esto pasó con cada persona",
                    "why": (
                        "Si le llegó, cuándo lo abrió y cuándo pulsó. Puedes buscar y "
                        "filtrar por etiqueta."
                    ),
                },
            },
        },
        {
            "id": "settings",
            "name": "Configuración",
            "lead": "Tu dirección postal, tu seguridad, tu equipo y tu plan.",
            "done": (
                "Eso es todo lo que hay que dejar listo. Cuando quieras, contrata tu plan "
                "desde la página de planes."
            ),
            "steps": {
                "menu": {
                    "do": "Abre el menú con el nombre de tu empresa",
                    "why": "Configuración está al final.",
                },
                "entrar": {
                    "do": "Entra a Configuración",
                    "why": "Tu cuenta, tu seguridad, tus avisos y tu facturación.",
                },
                "direccion": {
                    "do": "Escribe tu dirección postal",
                    "why": (
                        "Sale al pie de tus correos, porque la ley la pide. Sin ella no "
                        "se envía. Un apartado postal sirve."
                    ),
                },
                "seguridad": {
                    "do": "Abre Seguridad",
                    "why": "Tu contraseña, tus dispositivos y tu equipo.",
                },
                "dos_pasos": {
                    "do": "Activa la autenticación de múltiples factores",
                    "why": (
                        "Además de tu contraseña, un código de una app en tu teléfono. "
                        "Recomendado."
                    ),
                },
                "usuarios": {
                    "do": "Dale entrada a tu equipo",
                    "why": (
                        "Cada persona con su correo y su contraseña. Tú decides lo que "
                        "puede hacer."
                    ),
                },
                "facturacion": {
                    "do": "Abre Facturación",
                    "why": "Tu plan, hasta cuándo va y lo que has pagado.",
                },
                "plan": {
                    "do": "Aquí está tu plan",
                    "why": "Con su fecha, los métodos de pago y el historial de compras.",
                },
            },
        },
    ],
}

# --------------------------------------------------------------------------- how it works

HOW = {
    "meta_title": "Cómo funciona · Sobreala",
    "meta_description": (
        "Tutoriales del panel de Sobreala: contactos, plantillas, envíos, "
        "estadísticas y configuración, paso a paso y pulsando."
    ),
    "hero": {
        "eyebrow": "Cómo funciona",
        "title": "De tu base de datos al correo de tus clientes",
        "subtitle": (
            "Así vas a usar Sobreala, paso a paso. Sin instalar nada y sin pelear con "
            "configuraciones técnicas."
        ),
    },
    "sending": {
        "eyebrow": "El envío",
        "title": "Los correos salen con el nombre y el correo de tu empresa",
        "text": (
            "Muchos negocios no tienen dominio propio, así que no te pedimos uno. Tus "
            "correos salen desde un subdominio de Sobreala, pero quien los recibe ve "
            "el nombre de tu negocio como remitente, y si responde, la respuesta llega "
            "a tu correo de siempre."
        ),
        "example": {
            "from_label": "De",
            "from_value": "Tu Empresa <tuempresa@envios.sobreala.com>",
            "reply_label": "Responder a",
            "reply_value": "tuempresa@gmail.com",
        },
        "note": (
            "Si ya tienes dominio propio, lo configuramos contigo durante la activación "
            "para que los correos salgan desde él."
        ),
    },
    "care": {
        "eyebrow": "Lo que cuidamos por ti",
        "title": "Reglas que funcionan solas",
        "intro": (
            "Hay cosas que si se hacen mal terminan con tus correos en la carpeta de "
            "spam. Estas van incluidas y no dependen de que te acuerdes."
        ),
        "items": [
            {
                "title": "Botón de anular suscripción, siempre",
                "text": (
                    "El enlace para dejar de recibir correos se agrega en el envío, es "
                    "único para cada persona y va en todos los planes. No se puede quitar."
                ),
            },
            {
                "title": "Nadie recibe la misma campaña dos veces",
                "text": (
                    "Si una persona lleva tres de tus etiquetas y la campaña va a las "
                    "tres, recibe una sola copia y te cuesta un solo envío. Otra "
                    "campaña distinta, más adelante, sí le llega."
                ),
            },
            {
                "title": "Rebotes y quejas fuera",
                "text": (
                    "Las direcciones que rebotan o marcan tu correo como spam salen de "
                    "tus envíos de forma permanente. Reimportarlas no las reactiva."
                ),
            },
            {
                "title": "Sin sorpresas al llegar al límite",
                "text": (
                    "Te avisamos al 80% de tu cuota. Si la agotas a mitad de campaña, se "
                    "pausa en vez de fallar, y al empezar el mes o al subir de plan, sigue "
                    "desde donde se quedó."
                ),
            },
        ],
    },
}

# --------------------------------------------------------------------------- pricing

PRICING = {
    "meta_title": "Precios · Sobreala",
    "meta_description": (
        "Planes de Sobreala desde $15 al mes, con contactos, correos mensuales y "
        "soporte que responde. Plan anual con 20% de descuento."
    ),
    "hero": {
        "eyebrow": "Precios",
        "title": "Planes",
        "subtitle": (
            "Se ajustan a lo que necesites. Eliges por la cantidad de contactos que "
            "tengas, y cada plan te da cinco correos por contacto al mes: suficiente "
            "para escribirle a toda tu lista cinco veces."
        ),
    },
    # Public presentation of each plan. Prices, contact and email limits are read
    # from docs/pricing.md; only the positioning text lives here.
    "plans": {
        "Básico": {
            "pitch": "Para empezar con una lista pequeña.",
            "featured": False,
        },
        "Negocio": {
            "pitch": "Para quien ya envía cada mes y quiere su propio diseño.",
            "featured": True,
            "badge": "Recomendado",
        },
        "Empresa": {
            "pitch": "Para cooperativas y colegios con una lista grande.",
            "featured": False,
        },
    },
    # El interruptor de las tarjetas. Son dos botones de verdad: sin JavaScript
    # la página se queda en mensual, que es como nace, y los precios siguen ahí.
    "cycle": {
        "label": "Cómo quieres pagar",
        "monthly": "Mensual",
        "yearly": "Anual",
        # La pastilla al lado de Anual: el descuento, que es lo que se mira.
        "save": "-{off}",
        # Lo que dice la tarjeta debajo del precio, en cada ciclo: lo que se
        # cobra de verdad al contratar, que es lo que se quiere saber.
        "monthly_note": "Total a pagar ahora: {total}",
        "yearly_note": "Total a pagar ahora: {total}",
        "per_month": "/ mes",
    },
    # Con RUC hay que decir si el precio lleva impuesto, y se dice donde se
    # mira el precio y no escondido en los términos.
    "tax_note": "Precios con ITBMS incluido.",
    # El prorrateo al mejorar: lo que no se usó se descuenta.
    "upgrade_note": ("Al mejorar tu plan, los correos que no usaste se descuentan "
                     "del precio nuevo y tu mes empieza de nuevo."),
    "table": {
        "eyebrow": "Comparación",
        "title": "Todo lo que incluye cada plan",
        "scroll_hint": "Desliza para ver todos los planes",
        # Lo que lleva al lado la fila de algo que todavía se está
        # construyendo. Los números son los del plan; la función no está.
        "soon": "Pronto",
    },
    # Lo que la tabla no dice sola. Una fila que se llama «Etiquetas» y dice
    # «4» no significa nada para quien no conoce el producto, y hay una que no
    # se puede adivinar de ninguna forma: que el correo puede salir distinto
    # para cada persona en vez de ser el mismo para toda la lista.
    "glossary": {
        "eyebrow": "En detalle",
        "title": "Qué significa cada fila",
        "intro": (
            "Lo que hay detrás de los números de la tabla, para que sepas qué "
            "estás eligiendo."
        ),
        "items": [
            {
                "title": "Contactos",
                "text": (
                    "Las personas que tienes guardadas. Tienes una sola lista "
                    "y cada dirección está en ella una sola vez, aunque le "
                    "pongas varias etiquetas. Quien anula su suscripción "
                    "deja de ocupar lugar: si tu plan son 3,000 contactos, son "
                    "3,000 personas a las que puedes escribirle."
                ),
            },
            {
                "title": "Etiquetas",
                "text": (
                    "No manejas listas separadas: es una sola lista y las "
                    "etiquetas son las que la dividen. A cada contacto le "
                    "pones las que quieras (colaborador, empleado, junta "
                    "directiva, estudiante, profesor). Al enviar un correo "
                    "eliges toda la lista o las etiquetas que quieras, y quien "
                    "lleve más de una de las marcadas recibe un solo correo. "
                    "El número dice cuántas etiquetas distintas puedes crear."
                ),
            },
            {
                "title": "Columnas de datos",
                "text": (
                    "Lo que guardas de cada persona además de su correo y su "
                    "nombre: su ciudad, su número de socio, cuánto debe, "
                    "cuándo vence. Las creas tú, con el nombre que quieras, y "
                    "el número de la tabla indica cuántas columnas adicionales "
                    "puedes guardar en tu base."
                ),
            },
            {
                "title": "Crear plantillas en el editor",
                "text": (
                    "Armas tu correo como una diapositiva: pones textos, "
                    "botones e imágenes donde quieras, con tus colores y tus "
                    "fuentes. Las imágenes van de fondo y el texto encima, "
                    "que es como llega igual a Gmail, a Outlook y al "
                    "teléfono. Va en todos los planes, y cada plantilla se "
                    "guarda para usarla las veces que quieras."
                ),
            },
            {
                "title": "Exportar a CSV y PDF",
                "text": (
                    "Puedes descargar tus estadísticas y tu base de datos "
                    "como CSV y PDF, cuando quieras."
                ),
            },
            {
                "title": "Usuarios de la cuenta",
                "text": (
                    "Cuántas personas de tu empresa entran, cada una con su "
                    "correo y su contraseña, y el dueño cuenta. Él puede todo: "
                    "el plan, el pago y los datos de la cuenta. A cada persona "
                    "le marcas lo suyo: ver las cifras, subir contactos, armar "
                    "plantillas o mandar campañas."
                ),
            },
        ],
    },
    "included": {
        "title": "En todos los planes, sin excepción",
        "items": [
            "Botón para anular la suscripción en cada correo",
            "Contactos sin duplicados, aunque lleven varias etiquetas",
            "Lista de bajas y rebotes gestionada automáticamente",
            "Estadísticas de cada campaña, exportables",
            "Acompañamiento en tu primera campaña",
            "Sin permanencia mínima: cancelas cuando quieras",
        ],
    },
}

# --------------------------------------------------------------------------- about

ABOUT = {
    "meta_title": "Nosotros · Sobreala",
    "meta_description": (
        "Qué es Sobreala, para quién lo estamos construyendo y por qué una "
        "plataforma de email marketing pensada para listas que ya existen."
    ),
    "hero": {
        "eyebrow": "Nosotros",
        "title": "Quiénes somos y por qué hacemos esto",
        "subtitle": (
            "Sobreala se construye para negocios y organizaciones que ya tienen una "
            "lista de correos guardada en alguna parte y no tienen cómo usarla."
        ),
    },
    "sections": [
        {
            "title": "¿Qué es Sobreala?",
            "paragraphs": [
                (
                    "Sobreala es una plataforma de email marketing: un panel donde una "
                    "empresa sube sus contactos, arma un correo y lo envía a toda su "
                    "lista de una vez. Ofertas, recordatorios, convocatorias, boletines."
                ),
            ],
        },
        {
            "title": "¿Para quién?",
            "paragraphs": [
                (
                    "Sobre todo para organizaciones que ya juntaron una lista por otra "
                    "razón: cooperativas de ahorro y crédito con sus socios, colegios "
                    "privados con los padres, gremios con sus miembros, universidades "
                    "con sus estudiantes. También comercios y PyMEs que llevan tiempo "
                    "anotando correos de clientes."
                ),
                (
                    "Si todavía no tienes lista, eso también nos interesa: ayudarte a "
                    "construirla es parte del trabajo."
                ),
            ],
        },
        {
            "title": "¿Por qué?",
            "paragraphs": [
                (
                    "Una organización con dos mil correos guardados en una hoja de "
                    "cálculo tiene, sin saberlo, su canal más directo. No depende de un "
                    "algoritmo, no se pierde entre publicaciones y llega a quien ya "
                    "levantó la mano."
                ),
                (
                    "Lo que falta casi nunca es la lista. Es una forma sencilla de "
                    "escribirle sin terminar en spam ni pasar la tarde copiando y "
                    "pegando."
                ),
            ],
        },
        {
            "title": "¿Cómo lo hacemos?",
            "paragraphs": [
                (
                    "Tus correos no salen de un servidor de correo cualquiera ni de una "
                    "cuenta de empresa. Salen por Amazon SES, la infraestructura de "
                    "envío masivo de Amazon, a través de su API. Un servidor propio se "
                    "topa con unos 2,000 correos diarios y quema la reputación del "
                    "dominio en la primera campaña grande."
                ),
                (
                    "El dominio desde el que sales va firmado con SPF, DKIM y DMARC, "
                    "que es lo que Gmail y Outlook revisan antes de decidir si tu "
                    "correo entra a la bandeja o al spam. Tú no configuras nada de eso: "
                    "si no tienes dominio propio, envías desde un subdominio nuestro ya "
                    "autenticado."
                ),
                (
                    "Cada cuenta va aislada de las demás. Los envíos se separan por "
                    "cliente, así que los rebotes de uno no arrastran la entregabilidad "
                    "del resto, y la lista de bajas es tuya y no global: si alguien se "
                    "da de baja de un colegio, sigue recibiendo los correos de su "
                    "cooperativa."
                ),
                (
                    "Las reglas que cuidan tu reputación vienen activadas de fábrica. "
                    "Cada correo lleva su enlace de baja, los contactos no se duplican, "
                    "y quien rebota o marca tu correo como spam queda fuera de tus "
                    "envíos. Si una cuenta pasa del 3% de rebotes o del 0.05% de "
                    "quejas, su envío se pausa solo antes de que el problema crezca. "
                    "Nada de eso se configura ni se puede apagar."
                ),
            ],
        },
        {
            "title": "¿En qué punto estamos?",
            "paragraphs": [
                (
                    "Sobreala está en construcción. Este sitio presenta el proyecto y "
                    "los planes. La plataforma se está desarrollando y las primeras "
                    "cuentas se abrirán poco a poco, acompañando a cada cliente en su "
                    "primera campaña."
                ),
            ],
        },
    ],
}

# --------------------------------------------------------------------------- contact
# Una página y no un ancla al pie: así se puede enlazar desde fuera, aparece en
# los buscadores y se puede mandar por WhatsApp sola.
CONTACT_PAGE = {
    "meta_title": "Contacto · Sobreala",
    "meta_description": "Escríbenos por WhatsApp o por correo. Respondemos el "
                        "mismo día hábil, desde Santiago de Veraguas.",
    "hero": {
        "eyebrow": "Contacto",
        "title": "Hablemos de tu lista",
        "subtitle": "Escríbenos y te decimos en dos minutos si Sobreala te "
                    "sirve. Sin compromiso y sin formularios largos.",
    },
    "ways": [
        {
            "kind": "whatsapp",
            "title": "WhatsApp",
            "detail": "Lo más rápido. Contestamos el mismo día hábil.",
        },
        {
            "kind": "email",
            "title": "Correo",
            "detail": "Para lo que necesite quedar por escrito, como una "
                      "cotización o los datos de tu organización.",
        },
        {
            "kind": "instagram",
            "title": "Instagram",
            "detail": "Ahí publicamos ejemplos de piezas y novedades.",
        },
    ],
    "who": {
        "title": "Quién contesta",
        "paragraphs": [
            "Sobreala lo lleva **Luis Stanziola**, desde Santiago de "
            "Veraguas. No hay centro de llamadas: escribes y te contesta la "
            "misma persona que va a configurar tu cuenta.",
            "Atendemos de **lunes a viernes**. Si escribes un fin de semana, "
            "te respondemos el lunes.",
        ],
    },
    "already": {
        "title": "¿Ya tienes cuenta?",
        "text": "Si es algo de tu cuenta, entra al panel: ahí están tus datos, "
                "tu plan y tus dispositivos conectados.",
    },
}

# --------------------------------------------------------------------------- legal

# Quién responde por los datos. La ley pide que sea identificable y
# contactable, no que publique su domicilio: por eso el lugar llega hasta el
# corregimiento y el contacto es el correo. `identifier` queda vacío a
# propósito mientras no exista aviso de operación; en cuanto lo haya, se
# escribe aquí y aparece solo en las dos páginas.
LEGAL_HOLDER = {
    # El nombre completo, que es el del aviso de operación: en un documento
    # legal no vale el de diario.
    "name": "Luis Alfredo Stanziola Guerra",
    "identifier": ("RUC 9-764-1273 DV 65, con aviso de operación N.° "
                   "9-764-1273-2026-574453501"),
    "place": "Santiago de Veraguas, provincia de Veraguas, Panamá",
}


def holder_line() -> str:
    """La frase de apertura de las dos páginas legales."""
    quien = f"Sobreala es el nombre comercial de {LEGAL_HOLDER['name']}"
    if LEGAL_HOLDER["identifier"]:
        quien += f", {LEGAL_HOLDER['identifier']}"
    return f"{quien}, en {LEGAL_HOLDER['place']}."

UPDATED = "15 de septiembre de 2026"
# Los términos cambiaron solos: dejaron de ofrecer el diseño como servicio.
TERMS_UPDATED = "18 de septiembre de 2026"

PRIVACY = {
    "meta_title": "Política de privacidad · Sobreala",
    "meta_description": (
        "Qué datos trata Sobreala, para qué, con quién los comparte, cuánto "
        "tiempo los guarda y cómo ejercer tus derechos bajo la Ley 81 de 2019."
    ),
    "hero": {
        "eyebrow": "Legal",
        "title": "Política de privacidad",
        "subtitle": (
            "Qué datos tratamos, para qué, con quién los compartimos y cuánto "
            "tiempo los guardamos. Escrita para que se entienda."
        ),
    },
    "updated": UPDATED,
    "sections": [
        {
            "title": "Quién responde por tus datos",
            "paragraphs": [
                holder_line() + " Escríbenos a info@sobreala.com "
                "para cualquier asunto de esta política, incluido el ejercicio "
                "de tus derechos.",
                "Esta política se rige por la Ley 81 de 2019 sobre protección de "
                "datos personales de la República de Panamá y su reglamento.",
            ],
        },
        {
            "title": "Dos papeles distintos",
            "paragraphs": [
                "Conviene separarlos desde el principio, porque las reglas "
                "cambian según el caso:",
            ],
            "items": [
                "**De los datos de tu cuenta somos responsables.** Los pediste "
                "tú, los usamos para prestarte el servicio y respondemos por "
                "ellos ante ti.",
                "**De los datos de tus contactos somos custodios.** La lista es "
                "tuya, tú decides qué se hace con ella y nosotros solo la "
                "guardamos y enviamos lo que nos pidas. Ni la usamos para otra "
                "cosa ni le ofrecemos nada nuestro a esa gente.",
            ],
        },
        {
            "title": "Qué datos tratamos",
            "items": [
                "**De tu cuenta:** nombre del negocio, nombre de contacto, "
                "correo, teléfono y el RUC o la cédula que nos das al abrirla. "
                "La contraseña no se guarda: solo un hash del que no se puede "
                "volver atrás.",
                "**De tus contactos:** las direcciones de correo y las "
                "etiquetas que subes, junto con las bajas y los rebotes de esa "
                "lista.",
                "**Técnicos:** la dirección IP y el navegador de cada intento "
                "de registro, entrada, confirmación, reenvío y salida. Sirven "
                "para detectar abuso y para responder cuando alguien no puede "
                "entrar. La contraseña nunca se anota, en ninguna forma.",
                "**Los correos que te enviamos:** guardamos el mensaje completo "
                "(destinatario, asunto y cuerpo) de cada correo del sistema. Es "
                "lo que nos permite responder qué salió exactamente del "
                "servidor cuando alguien dice que no le llegó el código.",
                "**De tus envíos:** por cada correo de campaña, si se entregó, "
                "rebotó, generó una queja, se abrió o se hizo click.",
                "**De pagos:** el plan, la fecha y el resultado del cobro. "
                "**Nunca vemos ni guardamos datos de tarjeta:** el pago ocurre "
                "en la página de PayPal o de Yappy, no en la nuestra.",
            ],
        },
        {
            "title": "Para qué los usamos",
            "items": [
                "Crear tu cuenta, confirmar que la dirección es tuya y dejarte "
                "entrar.",
                "Agendar contigo la demostración y comprobar que tu empresa "
                "existe antes de abrir tu cuenta.",
                "Enviar las campañas que tú prepares, a la lista que tú elijas.",
                "Cobrar el plan y llevar la cuenta de tu cuota.",
                "Proteger la entregabilidad de todos: como el dominio de envío "
                "es compartido, vigilamos rebotes y quejas y pausamos una "
                "cuenta cuando se pasan de los límites publicados.",
                "Atender soporte y responder reclamos.",
                "Cumplir obligaciones legales y contables.",
            ],
            "note": (
                "No vendemos datos, no los cedemos a terceros para su propio "
                "uso y no le enviamos publicidad nuestra a los contactos que "
                "suben nuestros clientes."
            ),
        },
        {
            "title": "Con qué permiso",
            "paragraphs": [
                "Tratamos los datos de tu cuenta porque hacen falta para "
                "ejecutar el contrato que aceptas al registrarte. Los datos "
                "técnicos de seguridad, por interés legítimo en proteger la "
                "plataforma. Y los datos de tus contactos, por instrucción "
                "tuya: el consentimiento de esas personas lo obtuviste tú, y "
                "así lo declaras al aceptar los términos.",
            ],
        },
        {
            "title": "Con quién se comparten",
            "paragraphs": [
                "Solo con los proveedores que hacen falta para que el servicio "
                "funcione. Todos actúan por instrucción nuestra:",
            ],
            "items": [
                "**Amazon Web Services (Amazon SES)**: envío de los correos.",
                "**MongoDB Atlas**: base de datos.",
                "**Railway**: servidor de la aplicación.",
                "**Cloudflare**: dominio, protección contra ataques y "
                "almacenamiento de las imágenes de los correos.",
                "**PayPal y Yappy**: cobro de los planes.",
            ],
            "note": (
                "Sus servidores están fuera de Panamá, principalmente en "
                "Estados Unidos, así que usar Sobreala implica una "
                "transferencia internacional de datos hacia esos proveedores. "
                "También podemos entregar información si una autoridad "
                "competente lo ordena."
            ),
        },
        {
            "title": "Cuánto tiempo los guardamos",
            "items": [
                "**Datos de la cuenta:** mientras la cuenta exista, y después "
                "lo que exijan las obligaciones contables y fiscales.",
                "**Contactos:** hasta que los borres o cierres la cuenta.",
                "**Bajas y supresiones:** de forma permanente y a propósito. Es "
                "justamente lo que impide volver a escribirle a quien pidió no "
                "recibir más correos, así que ni tú ni nosotros las borramos.",
                "**Detalle de aperturas, clicks, entregas y rebotes:** 12 meses; "
                "después quedan solo los totales por campaña.",
                "**Bitácora de accesos y de correos del sistema:** se conserva "
                "como registro de seguridad y soporte.",
            ],
        },
        {
            "title": "Tus derechos",
            "paragraphs": [
                "Puedes pedir acceso a tus datos, corregirlos, cancelarlos, "
                "oponerte a un tratamiento o llevártelos a otro servicio. "
                "Escríbenos a info@sobreala.com desde la dirección de tu "
                "cuenta y respondemos dentro de los plazos de la Ley 81 de "
                "2019. Si no quedas conforme, puedes acudir a la Autoridad "
                "Nacional de Transparencia y Acceso a la Información (ANTAI).",
                "Si llegaste aquí porque recibiste un correo de una empresa que "
                "usa Sobreala, los datos son de esa empresa y tu solicitud le "
                "corresponde a ella; escríbenos igual y la encaminamos. Si lo "
                "que quieres es dejar de recibir esos correos, el enlace de "
                "baja del propio mensaje lo hace al instante, y también podemos "
                "hacerlo nosotros a petición tuya.",
            ],
        },
        {
            "title": "Bajas",
            "paragraphs": [
                "Todas las campañas llevan un enlace de baja que inserta la "
                "plataforma al momento de enviar, más la cabecera técnica que "
                "permite darse de baja desde el propio programa de correo. "
                "Nuestros clientes no pueden quitarlo. Una baja es inmediata, "
                "no caduca y solo se revierte si la persona vuelve a "
                "suscribirse y confirma por correo.",
                "Los correos del sistema (el código de confirmación, los "
                "avisos de tu cuenta) no llevan enlace de baja porque no son "
                "publicidad: son parte del servicio que contrataste.",
            ],
        },
        {
            "title": "Cookies y almacenamiento en tu navegador",
            "items": [
                "Una **cookie de sesión** en el panel, imprescindible para "
                "mantenerte dentro de tu cuenta. No se puede leer desde "
                "JavaScript y caduca sola.",
                "Un **valor guardado en tu navegador** con el tema que "
                "elegiste, claro u oscuro. No sale de tu equipo.",
                "Una **marca de un solo dígito** que el panel deja en "
                "sobreala.com para que el sitio público sepa si dibujarte el "
                "botón «Mi cuenta». No lleva tu nombre ni tu dirección: es un "
                "uno y nada más.",
            ],
            "note": (
                "No usamos cookies de publicidad, ni de redes sociales, ni de "
                "medición de terceros."
            ),
        },
        {
            "title": "Seguridad",
            "paragraphs": [
                "Todo viaja cifrado por HTTPS. Las contraseñas se guardan solo "
                "como hash con bcrypt. De los códigos y enlaces que enviamos "
                "por correo se guarda únicamente su huella, valen una sola vez "
                "y vencen. Hay límites por dirección IP contra los intentos "
                "automatizados, y registro de cada acceso.",
                "Ningún sistema es infalible. Si ocurriera una brecha que "
                "afecte tus datos, te lo comunicaremos y lo reportaremos a la "
                "autoridad como corresponde.",
            ],
        },
        {
            "title": "Menores de edad",
            "paragraphs": [
                "Sobreala es un servicio para negocios y organizaciones. No "
                "está dirigido a menores de 18 años ni recogemos sus datos a "
                "sabiendas.",
            ],
        },
        {
            "title": "Cambios en esta política",
            "paragraphs": [
                "Si cambia algo importante lo avisaremos por correo o desde el "
                "panel. La fecha de arriba indica la versión vigente.",
            ],
        },
    ],
}

TERMS = {
    "meta_title": "Términos y condiciones · Sobreala",
    "meta_description": (
        "Condiciones de uso de Sobreala: cuenta, planes y pagos, reglas de "
        "envío, tratamiento de los datos de tus contactos y responsabilidades."
    ),
    "hero": {
        "eyebrow": "Legal",
        "title": "Términos y condiciones",
        "subtitle": (
            "Las reglas del servicio. Las aceptas al crear tu cuenta, así que "
            "vale la pena leerlas: las de envío tienen consecuencias reales."
        ),
    },
    "updated": TERMS_UPDATED,
    "sections": [
        {
            "title": "1. Quién presta el servicio",
            "paragraphs": [
                holder_line() + " Al crear una cuenta aceptas estos términos "
                "y la política de privacidad.",
            ],
        },
        {
            "title": "2. Qué es el servicio",
            "paragraphs": [
                "Sobreala es una plataforma de email marketing: subes tus "
                "contactos, armas una campaña y la envías desde un panel.",
                "La plataforma está en construcción. Algunas funciones no "
                "existen todavía y otras pueden cambiar; los cambios "
                "importantes se avisan.",
            ],
        },
        {
            "title": "3. Tu cuenta",
            "items": [
                "Los datos que registras deben ser ciertos, y el correo debe "
                "ser uno al que tengas acceso.",
                "La contraseña es tuya y respondes por lo que ocurra con tu "
                "cuenta. Avísanos si crees que alguien más entró.",
                "Una cuenta nueva queda **registrada**: el panel se abre después "
                "de una demostración, o al contratar un plan, y para abrirlo te "
                "pedimos tu RUC o tu cédula. Es como cuidamos que la plataforma "
                "no se use para correo no solicitado.",
                "Podemos suspender una cuenta que incumpla estas reglas.",
            ],
        },
        {
            "title": "4. Planes y pagos",
            "items": [
                "Los precios, los límites de contactos y de correos, y las "
                "condiciones de cada plan son los publicados en la página de "
                "precios al momento de contratar.",
                "Los precios publicados son finales e incluyen el ITBMS "
                "cuando corresponde.",
                "El precio es el mismo desde donde sea que contrates. A un "
                "cliente de fuera de Panamá se le factura como exportación de "
                "servicios, sin ITBMS: cambia el desglose de su factura, no lo "
                "que paga.",
                "Por cada pago emitimos la factura y te la enviamos al correo "
                "de tu cuenta.",
                "El cobro se hace por PayPal desde el panel, o por Yappy "
                "coordinándolo con nosotros, y en ese caso activamos el plan a "
                "mano. La tarjeta no pasa por nuestros servidores.",
                "Los correos no usados en el mes pasan al siguiente y vencen "
                "ahí; se consumen primero los acumulados.",
                "El plan anual se paga por adelantado con un 20% de "
                "descuento.",
                "Los pagos no son reembolsables, salvo un cobro duplicado o un "
                "error nuestro, que devolvemos por el mismo medio.",
                "Si un pago no se completa, la cuenta queda sin poder enviar "
                "hasta regularizarlo. Los datos no se borran por eso.",
            ],
        },
        {
            "title": "5. Para qué NO puedes usar Sobreala",
            "paragraphs": [
                "Esta es la parte que más importa. El dominio de envío es "
                "compartido entre todos los clientes: lo que uno haga mal lo "
                "pagan los demás en forma de correos que dejan de llegar. Por "
                "eso estas reglas se aplican sin excepciones.",
            ],
            "items": [
                "**Solo puedes escribirle a quien te dio su correo** sabiendo "
                "que le ibas a escribir. Nada de listas compradas, alquiladas, "
                "intercambiadas o recogidas de internet.",
                "Nada de correo no solicitado, cadenas, ni mensajes masivos a "
                "direcciones que no son tuyas.",
                "Nada de contenido ilegal, engañoso o que suplante a otra "
                "persona o empresa, ni de asuntos y remitentes que engañen "
                "sobre quién envía o de qué trata el mensaje.",
                "No puedes quitar, ocultar ni desviar el enlace de baja: lo "
                "inserta la plataforma al enviar y no se puede editar.",
                "No puedes usar la plataforma para enviar programas dañinos ni "
                "para intentar acceder a datos de otras cuentas.",
            ],
        },
        {
            "title": "6. Envíos, límites y pausas automáticas",
            "items": [
                "Las primeras 48 horas de una cuenta nueva llevan un tope de "
                "envío reducido, sea cual sea el plan.",
                "**Si los rebotes pasan del 3% o las quejas del 0.05%, el envío "
                "se pausa automáticamente** y te avisamos. Son los umbrales con "
                "los que trabajan los proveedores de correo; por debajo de "
                "ellos todo el mundo sigue recibiendo.",
                "Podemos suspender un envío en curso si detectamos un abuso, "
                "sin aviso previo cuando haga falta para proteger a los demás "
                "clientes.",
                "Hacemos lo posible por que los correos lleguen, pero la "
                "bandeja de entrada la decide el proveedor de cada "
                "destinatario. No podemos garantizar la entrega.",
            ],
        },
        {
            "title": "7. Tu contenido",
            "paragraphs": [
                "Los textos, imágenes y listas que subes siguen siendo tuyos. "
                "Nos das permiso únicamente para guardarlos y enviarlos según "
                "tus instrucciones, mientras uses el servicio.",
                "Respondes por tener los derechos de lo que envías, incluidas "
                "las imágenes y las marcas que aparezcan en tus campañas.",
            ],
        },
        {
            "title": "8. Los datos de tus contactos",
            "paragraphs": [
                "Cuando subes una lista, esos datos personales son de las "
                "personas que están en ella y **tú eres el responsable** de "
                "haberlos obtenido bien. Sobreala actúa como **custodio**: los "
                "trata solo por instrucción tuya. En concreto:",
            ],
            "items": [
                "Garantizas que cada persona de tu lista te dio su correo y "
                "podía esperar recibir mensajes tuyos, y que puedes demostrarlo "
                "si alguien lo pregunta.",
                "Usamos tu lista únicamente para tus envíos. No la mezclamos "
                "con la de otros clientes, no la vendemos y no le ofrecemos "
                "nada nuestro.",
                "La guardamos con las medidas de seguridad descritas en la "
                "política de privacidad, y solo la ve quien necesite verla para "
                "darte soporte.",
                "Si un contacto tuyo nos pide acceder, corregir o borrar sus "
                "datos, te lo encaminamos a ti, que eres quien decide. Si lo "
                "que pide es dejar de recibir correos, lo aplicamos de "
                "inmediato: esa baja no la puedes revertir.",
                "Al cerrar tu cuenta borramos la lista, salvo las supresiones, "
                "que se conservan para que nadie vuelva a escribirle a quien "
                "pidió no ser contactado.",
                "Si contratamos un proveedor nuevo que trate esos datos, se le "
                "exigen las mismas obligaciones. Los actuales están nombrados "
                "en la política de privacidad.",
            ],
        },
        {
            "title": "9. Disponibilidad",
            "paragraphs": [
                "El servicio se presta tal como está. Hacemos lo razonable por "
                "mantenerlo disponible, pero puede haber cortes, mantenimientos "
                "y fallas de proveedores. No prometemos un porcentaje de "
                "disponibilidad ni operación ininterrumpida.",
            ],
        },
        {
            "title": "10. Responsabilidad",
            "paragraphs": [
                "Respondemos por lo que hagamos mal, hasta el monto que nos "
                "hayas pagado en los tres meses anteriores al hecho. No "
                "respondemos por lucro cesante, pérdida de oportunidades ni "
                "daños indirectos, ni por el contenido que tú envíes o por "
                "cómo obtuviste tu lista.",
            ],
        },
        {
            "title": "11. Cierre de la cuenta",
            "items": [
                "Puedes cerrarla cuando quieras escribiéndonos.",
                "Podemos cerrarla si incumples estas reglas, si el pago no se "
                "regulariza o si el uso pone en riesgo la entregabilidad de la "
                "plataforma.",
                "Tras el cierre puedes pedir una copia de tus contactos durante "
                "30 días. Después se borran, salvo las supresiones y lo que "
                "debamos conservar por ley.",
            ],
        },
        {
            "title": "12. Cambios",
            "paragraphs": [
                "Podemos actualizar estos términos. Si el cambio es importante "
                "lo avisaremos por correo o desde el panel antes de que entre "
                "en vigor. Seguir usando el servicio después es aceptarlo.",
            ],
        },
        {
            "title": "13. Ley aplicable",
            "paragraphs": [
                "Estos términos se rigen por las leyes de la República de "
                "Panamá, incluidas la Ley 81 de 2019 de protección de datos "
                "personales y la Ley 51 de 2008 de comercio electrónico. "
                "Cualquier disputa se somete a los tribunales de la ciudad de "
                "Panamá, sin perjuicio de intentar antes una solución "
                "conversada.",
            ],
        },
        {
            "title": "14. Contacto",
            "paragraphs": [
                "info@sobreala.com, o el WhatsApp que aparece en el pie "
                "de esta página.",
            ],
        },
    ],
}


# --------------------------------------------------------------------------- footer

FOOTER = {
    "description": "Envía campañas de correo a toda tu lista desde un solo panel.",
    "columns": [
        {
            "title": "Producto",
            "links": [
                {"label": "Planes", "url": "/#planes"},
                {"label": "Cómo funciona", "url": "/#como-funciona"},
            ],
        },
        {
            "title": "Empresa",
            "links": [
                {"label": "Nosotros", "url": "/#nosotros"},
                {"label": "Contacto", "url": "/#contacto"},
            ],
        },
        {
            "title": "Legal",
            "links": [
                {"label": "Política de privacidad", "url": "/privacy/"},
                {"label": "Términos y condiciones", "url": "/terms/"},
            ],
        },
    ],
    "soon_label": "Próximamente",
    "legal_note": "Sobreala",
    # Payment logos live in brand/payments/. If that folder is empty the footer
    # falls back to this line, so the site is never left half-finished.
    "payments_label": "Pagos",
    "payments_fallback": "Pagos con Yappy, PayPal y tarjeta",
}
