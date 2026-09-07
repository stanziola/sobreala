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
    "name": "Panamails",
    "domain": "panamails.com",
    "base_url": "https://panamails.com",
    "locale": "es",
    "tagline": "Convierte tu lista de correos en ventas.",
}

# Contact. The WhatsApp link carries a prefilled message so the conversation
# starts with context instead of a blank "hola".
CONTACT = {
    "whatsapp_number": "50768935742",
    "whatsapp_display": "+507 6893-5742",
    "whatsapp_message": "Hola, me interesa Panamails para mi negocio.",
    "email": "panamails.info@gmail.com",
    # Prefilled like the WhatsApp message, so the conversation starts with context.
    "email_subject": "Consulta sobre Panamails",
    "email_body": "Hola, me interesa Panamails para mi negocio.",
    "email_copy_label": "Copiar",
    "email_copied_label": "Copiado",
    "instagram_user": "pana.mails",
    "instagram_url": "https://instagram.com/pana.mails",
}

NAV = [
    {"label": "Inicio", "url": "/"},
    {"label": "Cómo funciona", "url": "/como-funciona/"},
    {"label": "Precios", "url": "/precios/"},
    {"label": "Nosotros", "url": "/nosotros/"},
]

CTA_PRIMARY = {"label": "Contáctanos por WhatsApp", "kind": "whatsapp"}
CTA_SECONDARY = {"label": "Ver planes y precios", "url": "/precios/"}

# --------------------------------------------------------------------------- home

HOME = {
    "meta_title": "Panamails · Email marketing para tu negocio",
    "meta_description": (
        "Email marketing sin complicaciones: sube tus contactos, escribe tu campaña "
        "y envíala por correo a toda tu lista desde un solo panel."
    ),
    "hero": {
        "title_lead": "Convierte tu lista de correos",
        "title_accent": "en ventas.",
        "subtitle": (
            "Sube tus contactos, escribe tu campaña y envíala por correo a toda tu "
            "lista desde un solo panel. Sin instalar nada."
        ),
        "note": "En construcción. Escríbenos y te avisamos apenas abramos cuentas.",
    },
    "problem": {
        "eyebrow": "El problema",
        "title": "Ya tienes los correos. El problema es enviarlos.",
        "intro": (
            "Cooperativas, colegios, gremios y comercios llevan años juntando "
            "direcciones de socios, padres y clientes. Esa lista casi nunca se usa."
        ),
        "items": [
            {
                "title": "El correo personal no sirve para esto",
                "text": (
                    "Enviar a cientos de personas desde Gmail termina en spam, con "
                    "límites diarios y todos los destinatarios a la vista."
                ),
            },
            {
                "title": "Contratar cada campaña sale caro",
                "text": (
                    "Pagar por envío convierte en excepción algo que debería ser "
                    "rutina todos los meses."
                ),
            },
            {
                "title": "Hacerlo a mano cuesta horas",
                "text": (
                    "Mandar en tandas de cincuenta, copiar y pegar el mismo mensaje, "
                    "y al final no saber quién lo abrió ni quién ya no quiere recibirlo."
                ),
            },
        ],
    },
    "features": {
        "eyebrow": "La plataforma",
        "title": "Lo que estamos construyendo",
        "intro": (
            "Panamails está en desarrollo. Estas son las capacidades que estamos "
            "construyendo y cómo van a funcionar."
        ),
        "items": [
            {
                "icon": "contacts",
                "title": "Contactos sin duplicados",
                "text": (
                    "Cada dirección existe una sola vez en tu cuenta. Si una persona "
                    "está en varias listas, cuenta como una, recibe un solo correo y "
                    "consume un solo envío."
                ),
            },
            {
                "icon": "campaign",
                "title": "Campañas con plantilla o con tu HTML",
                "text": (
                    "Empiezas desde una plantilla prediseñada. Si prefieres tu propio "
                    "diseño, lo subes tal cual desde el plan Negocio."
                ),
            },
            {
                "icon": "schedule",
                "title": "Envío ahora o programado",
                "text": (
                    "Eliges la lista, revisas la vista previa, te mandas una prueba a "
                    "ti mismo y decides si sale ya o a la hora que elijas."
                ),
            },
            {
                "icon": "chart",
                "title": "Resultados de cada campaña",
                "text": (
                    "Entregados, aperturas, clics, rebotes y bajas, por campaña, con "
                    "exportación a CSV y PDF."
                ),
            },
            {
                "icon": "shield",
                "title": "Bajas y rebotes gestionados solos",
                "text": (
                    "El enlace para darse de baja va en todos los correos y en todos "
                    "los planes. Quien se da de baja o rebota no vuelve a recibir nada."
                ),
            },
            {
                "icon": "flag",
                "title": "Acompañamiento en tu primera campaña",
                "text": (
                    "Revisamos tu lista contigo, probamos el envío y sales con la "
                    "primera campaña ya enviada, no con un panel vacío."
                ),
            },
        ],
    },
    "steps": {
        "eyebrow": "Cómo funciona",
        "title": "Cuatro pasos, de la lista al resultado",
        "cta": {"label": "Ver cómo funciona en detalle", "url": "/como-funciona/"},
    },
    "faq": {
        "eyebrow": "Preguntas frecuentes",
        "title": "Lo que suelen preguntarnos",
        "items": [
            {
                "q": "¿Panamails ya está disponible?",
                "a": (
                    "Todavía no. Estamos construyendo la plataforma y abriendo cuentas "
                    "poco a poco. Si nos escribes, te avisamos apenas puedas entrar."
                ),
            },
            {
                "q": "¿Necesito tener un dominio propio?",
                "a": (
                    "No. Los correos salen desde un subdominio de Panamails con el "
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
                    "Todos los correos llevan un enlace de baja de un clic, en todos "
                    "los planes, y no se puede quitar. Quien se da de baja queda fuera "
                    "de tus envíos automáticamente."
                ),
            },
            {
                "q": "¿Cómo se paga?",
                "a": (
                    "Con los medios de pago que ves al pie de esta página. Los datos de "
                    "la tarjeta se manejan siempre en el sitio del proveedor de pago, "
                    "nunca en Panamails."
                ),
            },
            {
                "q": "¿Ustedes me diseñan el correo?",
                "a": (
                    "Sí, es un servicio aparte. Diseñamos la pieza con tu marca y la "
                    "reutilizas cada mes cambiando textos e imágenes. Los planes de "
                    "Negocio en adelante incluyen plantillas personalizadas."
                ),
            },
        ],
    },
}

# The four steps are shared by the home page and the "cómo funciona" page, so the
# wording never diverges. The detail page adds its own extra paragraph per step.
STEPS = [
    {
        "number": "1",
        "title": "Sube tus contactos",
        "short": "Importas tu lista desde un archivo CSV y la organizas con etiquetas.",
        "detail": (
            "Subes el archivo que ya tienes, en CSV, y Panamails lo procesa. Los "
            "correos repetidos se unifican solos: una dirección existe una sola vez en "
            "tu cuenta, aunque aparezca en varias listas. Al terminar te decimos "
            "cuántos entraron y cuántos estaban dados de baja de envíos anteriores. "
            "En vez de listas separadas usas etiquetas, así un mismo contacto puede ser "
            "socio y estar en la lista de la asamblea sin contar dos veces."
        ),
    },
    {
        "number": "2",
        "title": "Arma tu mensaje",
        "short": "Eliges una plantilla, escribes el asunto y el contenido, y lo previsualizas antes de enviar.",
        "detail": (
            "Partes de una plantilla prediseñada y cambias textos e imágenes, o subes "
            "tu propio HTML desde el plan Negocio. La previsualización te muestra el "
            "correo tal como va a llegar, y puedes enviarte una prueba a tu propia "
            "dirección para verla en tu bandeja antes de que la vea nadie más. Si "
            "prefieres no armarla tú, te diseñamos la pieza con tu marca y la "
            "reutilizas cada mes."
        ),
    },
    {
        "number": "3",
        "title": "Envía o programa",
        "short": "Seleccionas a quién le llega y decides si sale ahora o a la hora que elijas.",
        "detail": (
            "Eliges las etiquetas que reciben la campaña y confirmas. Puedes enviar en "
            "el momento o dejarla programada para el día y la hora exactos que te "
            "convengan. El enlace de baja se agrega a cada correo en el envío, único "
            "para cada destinatario, y quien se dio de baja o rebotó antes se salta "
            "automáticamente, sin gastar tu cuota."
        ),
    },
    {
        "number": "4",
        "title": "Mira qué pasó",
        "short": "Ves entregados, aperturas, clics, rebotes y bajas de cada campaña.",
        "detail": (
            "Cada campaña deja su registro: cuántos correos se entregaron, cuántas "
            "personas abrieron, cuántas hicieron clic, cuántos rebotaron y cuántas se "
            "dieron de baja. Puedes exportarlo a CSV o PDF para presentarlo en una "
            "junta directiva o guardarlo como respaldo."
        ),
    },
]

# --------------------------------------------------------------------------- how it works

HOW = {
    "meta_title": "Cómo funciona · Panamails",
    "meta_description": (
        "De tu lista de contactos al correo de tus clientes: los cuatro pasos para "
        "enviar una campaña con Panamails, explicados sin tecnicismos."
    ),
    "hero": {
        "eyebrow": "Cómo funciona",
        "title": "De tu lista al correo de tus clientes",
        "subtitle": (
            "Así vas a usar Panamails, paso a paso. Sin instalar nada y sin pelear con "
            "configuraciones técnicas."
        ),
    },
    "sending": {
        "eyebrow": "El envío",
        "title": "Sales con el nombre de tu negocio, sin configurar nada",
        "text": (
            "Muchos negocios no tienen dominio propio, así que no te pedimos uno. Tus "
            "correos salen desde un subdominio de Panamails, pero quien los recibe ve "
            "el nombre de tu negocio como remitente, y si responde, la respuesta llega "
            "a tu correo de siempre."
        ),
        "example": {
            "from_label": "De",
            "from_value": "Tu Empresa <tuempresa@envios.panamails.com>",
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
                "title": "Baja de un clic, siempre",
                "text": (
                    "El enlace para dejar de recibir correos se agrega en el envío, es "
                    "único para cada persona y va en todos los planes. No se puede quitar."
                ),
            },
            {
                "title": "Una persona, un correo",
                "text": (
                    "Si un contacto está en tres de tus listas y le envías a las tres, "
                    "recibe un solo correo y te cuesta un solo envío."
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
                    "pausa en vez de fallar, y al recargar sigue desde donde se quedó."
                ),
            },
        ],
    },
}

# --------------------------------------------------------------------------- pricing

PRICING = {
    "meta_title": "Precios · Panamails",
    "meta_description": (
        "Planes de Panamails desde $35 al mes, con contactos, correos mensuales y "
        "soporte que responde. Plan anual con dos meses gratis."
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
            "pitch": "Para cooperativas y colegios con listas grandes.",
            "featured": False,
        },
        "Corporativo": {
            "pitch": "Para listas muy grandes, con acompañamiento.",
            "featured": False,
            "custom_price": "A la medida",
            "custom_note": "Contáctanos",
        },
    },
    "annual_note": "En el plan anual pagas diez meses y usas doce.",
    "table": {
        "eyebrow": "Comparación",
        "title": "Todo lo que incluye cada plan",
        "scroll_hint": "Desliza para ver todos los planes",
    },
    "addons": {
        "eyebrow": "Complementos",
        "title": "Si necesitas más",
        "intro": "Se agregan cuando hacen falta, sin cambiar de plan.",
        "descriptions": {
            "Recarga de 1,000 correos": (
                "Si agotas tu cuota a mitad de mes, la campaña pausada retoma desde "
                "donde se quedó."
            ),
            "Diseño de pieza HTML adicional": (
                "Diseñamos una pieza más con tu marca, además de las que incluye tu "
                "plan. Hasta dos rondas de cambios, entrega en tres días hábiles."
            ),
        },
    },
    "included": {
        "title": "En todos los planes, sin excepción",
        "items": [
            "Enlace de baja de un clic en cada correo",
            "Contactos sin duplicados, aunque estén en varias listas",
            "Lista de bajas y rebotes gestionada automáticamente",
            "Estadísticas de cada campaña, exportables",
            "Acompañamiento en tu primera campaña",
            "Sin permanencia mínima: cancelas cuando quieras",
        ],
    },
    "faq": {
        "eyebrow": "Sobre los planes",
        "title": "Dudas de facturación",
        "items": [
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
                    "Panamails. Solo aparece en el plan Básico. Es distinta del enlace "
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

# --------------------------------------------------------------------------- about

ABOUT = {
    "meta_title": "Nosotros · Panamails",
    "meta_description": (
        "Qué es Panamails, para quién lo estamos construyendo y por qué una "
        "plataforma de email marketing pensada para listas que ya existen."
    ),
    "hero": {
        "eyebrow": "Nosotros",
        "title": "Para las listas de correo que nadie usa",
        "subtitle": (
            "Panamails se construye para negocios y organizaciones que ya tienen una "
            "lista de correos guardada en alguna parte y no tienen cómo usarla."
        ),
    },
    "sections": [
        {
            "title": "Qué es Panamails",
            "paragraphs": [
                (
                    "Panamails es una plataforma de email marketing: un panel donde una "
                    "empresa sube sus contactos, arma un correo y lo envía a toda su "
                    "lista de una vez. Ofertas, recordatorios, convocatorias, boletines."
                ),
                (
                    "También diseñamos las piezas de correo como servicio, para quien "
                    "prefiere no armarlas por su cuenta."
                ),
            ],
        },
        {
            "title": "Para quién",
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
            "title": "Por qué",
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
            "title": "Cómo lo hacemos",
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
            "title": "En qué punto estamos",
            "paragraphs": [
                (
                    "Panamails está en construcción. Este sitio presenta el proyecto y "
                    "los planes. La plataforma se está desarrollando y las primeras "
                    "cuentas se abrirán poco a poco, acompañando a cada cliente en su "
                    "primera campaña."
                ),
            ],
        },
    ],
}

# --------------------------------------------------------------------------- footer

FOOTER = {
    "description": (
        "Envía campañas de correo a toda tu lista desde un solo panel. "
        "Actualmente en construcción."
    ),
    "columns": [
        {
            "title": "Producto",
            "links": [
                {"label": "Cómo funciona", "url": "/como-funciona/"},
                {"label": "Precios", "url": "/precios/"},
            ],
        },
        {
            "title": "Empresa",
            "links": [
                {"label": "Nosotros", "url": "/nosotros/"},
                {"label": "Contacto", "url": "#contacto"},
            ],
        },
        {
            "title": "Legal",
            "links": [
                {"label": "Política de privacidad", "url": None, "soon": True},
                {"label": "Términos y condiciones", "url": None, "soon": True},
            ],
        },
    ],
    "soon_label": "Próximamente",
    "legal_note": "Panamails",
    # Payment logos live in brand/payments/. If that folder is empty the footer
    # falls back to this line, so the site is never left half-finished.
    "payments_label": "Pagos",
    "payments_fallback": "Pagos con Yappy, PayPal y tarjeta",
}
