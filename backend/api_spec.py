"""La descripción de la API pública, en datos (octubre de 2026).

Es **una sola descripción para dos cosas**: la API la sirve como OpenAPI 3.1 en
`/api/v1/openapi.json`, y `landing/build_site.py` la lee al construir el sitio
y escribe con ella `sobreala.com/api/`. Por eso aquí no hay Flask ni Mongo, solo
datos y la función que los vuelve OpenAPI.

`tests/test_api_docs.py` compara cada ruta de aquí (método, ruta y permiso) con
las que de verdad responde la API, en los dos sentidos: una ruta sin describir,
o descrita y que no existe, hace fallar las pruebas. Los textos son de la
interfaz: en español y sin rayas largas.
"""

from __future__ import annotations

from typing import Any

TITLE = "API de Sobreala"
VERSION = "1"
BASE_URL = "https://app.sobreala.com/api/v1"

# El permiso de cada ruta, con los nombres que usa `blueprints/api/core.py`.
ANY = "any"
PUBLIC = "public"

SCOPES = [
    ("contacts:read", "Ver contactos", "Contactos, etiquetas, columnas y supresiones."),
    ("contacts:write", "Cambiar contactos",
     "Crear, cambiar y borrar contactos, sus listas, etiquetas y columnas."),
    ("templates:read", "Ver plantillas", "Plantillas, carpetas y cómo queda cada correo."),
    ("templates:write", "Cambiar plantillas",
     "Crear, cambiar y borrar plantillas, carpetas y fotos."),
    ("emails:send", "Enviar correos",
     "Mandar un correo a una persona y ver los que mandó la API."),
    ("campaigns:read", "Ver campañas", "Campañas, lo que salió y a quién."),
    ("campaigns:write", "Cambiar campañas", "Crear, cambiar y borrar campañas."),
    ("campaigns:send", "Mandar campañas", "Enviar y programar campañas."),
    ("stats:read", "Ver estadísticas", "Las cifras y los eventos de tus correos."),
]

# Los códigos de error: el código, su estado HTTP y qué quiere decir. La frase
# que viaja en `message` está en `i18n.py` (`api_error_*`).
ERRORS = [
    ("unauthorized", 401, "Falta la llave, o no es válida, está vencida o se revocó."),
    ("key_in_url", 400, "La llave llegó en la dirección. Se rechaza y, si era buena, "
                        "se revoca: ahí queda escrita en registros ajenos."),
    ("ip_not_allowed", 403, "La llave tiene una lista de IP y esta no está."),
    ("account_suspended", 403, "La cuenta está suspendida."),
    ("account_closed", 403, "La cuenta todavía no se abrió (falta la demostración o "
                            "un plan)."),
    ("test_key_cannot", 403, "Una llave de prueba no puede hacer esto: solo lee y "
                             "simula envíos."),
    ("missing_scope", 403, "La llave no tiene el permiso que pide esta ruta."),
    ("rate_limited", 429, "Demasiadas peticiones. Espera lo que dice Retry-After."),
    ("not_found", 404, "No existe, o no es de esta cuenta. Las dos cosas responden "
                       "igual."),
    ("method_not_allowed", 405, "La ruta no acepta ese método."),
    ("too_large", 413, "La petición pasa del tamaño permitido."),
    ("unsupported_media_type", 415, "El cuerpo no es JSON (o multipart donde se "
                                    "sube un archivo)."),
    ("bad_json", 400, "El cuerpo no es un objeto JSON válido."),
    ("validation_failed", 422, "Hay campos que no están bien; `fields` dice cuáles y "
                               "por qué."),
    ("bad_cursor", 400, "El cursor no salió de una respuesta anterior."),
    ("bad_idempotency_key", 400, "La Idempotency-Key no tiene la forma pedida."),
    ("idempotency_mismatch", 422, "Esa Idempotency-Key ya se usó con otro cuerpo."),
    ("idempotency_busy", 409, "La primera petición con esa Idempotency-Key sigue en "
                              "curso."),
    ("busy", 409, "Ya hay una carga de contactos en curso en la cuenta (por la API "
                  "o una importación del panel). Reintenta en unos segundos."),
    ("unknown_tag", 422, "Hay etiquetas que no existen; `tags` dice cuáles. Se crean "
                         "antes con `POST /tags`."),
    ("email_taken", 409, "Esa dirección ya la tiene otro contacto de la cuenta."),
    ("external_id_taken", 409, "Ese id de tu sistema ya lo tiene otro contacto de la "
                               "cuenta."),
    ("tag_exists", 409, "Esa etiqueta ya existe."),
    ("limit_reached", 409, "Se llegó al tope de tu plan (etiquetas, columnas, "
                           "plantillas, carpetas o fotos)."),
    ("field_exists", 409, "Ya hay una columna con esa clave, o es Nombre o Correo, "
                          "que todo contacto ya trae."),
    ("field_values", 409, "Hay contactos con valores que no encajan en el tipo nuevo; "
                          "`contacts` dice cuántos."),
    ("unavailable", 503, "No disponible por un momento; reintenta tras Retry-After."),
    ("internal_error", 500, "Algo falló de nuestro lado. Escríbenos con el "
                            "request_id."),
]

# Las guías: lo que hay que leer antes de las rutas.
GUIDES: list[dict[str, Any]] = [
    {"id": "empezar", "title": "Empezar",
     "paragraphs": [
         "La API deja que el sistema de tu negocio (tu tienda en línea, tu programa "
         "de socios, tu sistema de cobros) hable con tu cuenta de Sobreala sin "
         "entrar al panel: carga y actualiza contactos, usa tus plantillas y tus "
         "remitentes, envía correos y lee lo que pasó con ellos.",
         "Todas las direcciones empiezan por **https://app.sobreala.com/api/v1**. "
         "Se habla en JSON y en UTF-8, y siempre por HTTPS.",
         "Lo primero es crear una llave en el panel: **Dashboard → API → Llaves**. "
         "Con ella, esta llamada dice de quién es la cuenta y si hoy se puede "
         "enviar:",
     ],
     "code": "curl https://app.sobreala.com/api/v1/me \\\n"
             "  -H \"Authorization: Bearer sa_live_tu_llave\""},
    {"id": "autenticacion", "title": "La llave",
     "paragraphs": [
         "Cada petición lleva la llave en la cabecera **Authorization: Bearer**. "
         "Nunca en la dirección: una llave que llega ahí se rechaza y se revoca "
         "sola, porque queda escrita en los registros de los servidores por donde "
         "pasa.",
         "**La llave va en tu servidor**, nunca en una página web, en una "
         "aplicación que se descarga ni en un repositorio. La API no acepta "
         "llamadas desde un navegador de otra página.",
         "La llave se ve una sola vez, al crearla: nosotros guardamos solo una "
         "huella de ella. Si la pierdes, crea otra y revoca la vieja. Cada llave "
         "puede vencer, y puede quedar limitada a unas IP.",
         "Crear una llave pide tu contraseña (o un código a tu correo) y el código "
         "de tu app si tienes segundo factor, y te llega un correo cada vez que se "
         "crea o se revoca una.",
     ]},
    {"id": "permisos", "title": "Permisos",
     "paragraphs": [
         "Cada llave tiene los permisos que le diste al crearla, y cada ruta dice "
         "cuál pide. `GET /me` y `GET /senders` responden a cualquier llave.",
     ],
     "scopes": True},
    {"id": "prueba", "title": "Llaves de prueba",
     "paragraphs": [
         "Una llave que empieza por **sa_test_** es para ensayar: **lee todo lo "
         "que sus permisos dejen, y los envíos se simulan**. `POST /emails` arma "
         "el correo, lo revisa y te lo devuelve armado, pero no sale nada, no se "
         "gasta cuota y no se guarda nada. Enviar o programar una campaña dice a "
         "cuántos saldría y qué la frena, sin cambiar nada.",
         "Una llave de prueba **no puede escribir**: ni crear contactos ni "
         "plantillas ni campañas. Así, si se filtra desde un servidor de pruebas, "
         "no puede tocar tu lista. Para escribir hace falta una llave de verdad "
         "(**sa_live_**).",
     ]},
    {"id": "errores", "title": "Errores",
     "paragraphs": [
         "Un error responde con su estado HTTP y un cuerpo como este. `code` es "
         "para tu programa y `message` para leerlo; `fields` aparece cuando hay "
         "campos que no están bien, y `request_id` es lo que nos dices si nos "
         "escribes.",
     ],
     "code": "{\n  \"error\": {\n    \"code\": \"validation_failed\",\n"
             "    \"message\": \"Hay campos que no están bien: los dice fields.\",\n"
             "    \"fields\": {\"subject\": \"Falta este campo.\"},\n"
             "    \"request_id\": \"req_3f9a2c1b7d4e8a60\"\n  }\n}",
     "errors": True},
    {"id": "limites", "title": "Límites",
     "paragraphs": [
         "Por cuenta, sumando todas sus llaves: **600 peticiones por minuto**. "
         "Además, por minuto: 120 correos, 30 cargas de contactos (y 5,000 filas), "
         "5 plantillas o ZIP, 20 fotos y 30 consultas de estadísticas. Pasado un "
         "límite responde 429 con la cabecera **Retry-After**, en segundos.",
         "El cuerpo de una petición llega hasta 1 MB, y hasta 6 MB el ZIP de una "
         "plantilla y una foto. Lo pesado va de uno en uno por cuenta: dos cargas "
         "de contactos a la vez no se cruzan.",
         "Los correos gastan la cuota de tu plan, como en el panel. En la "
         "demostración solo salen a tus direcciones de prueba.",
     ]},
    {"id": "paginacion", "title": "Listas largas",
     "paragraphs": [
         "Las rutas que devuelven listas aceptan **limit** (de 1 a 100, 25 si no "
         "se dice) y responden `data` y `next_cursor`. Para la página siguiente se "
         "pide la misma ruta con **cursor** igual a ese `next_cursor`; cuando "
         "viene null, no hay más.",
     ],
     "code": "{\n  \"data\": [ ... ],\n  \"next_cursor\": \"ZS1h9Xc2bm9wcXJz\"\n}"},
    {"id": "idempotencia", "title": "Reintentar sin repetir",
     "paragraphs": [
         "Si la red se corta y no sabes si un envío salió, reintenta con la misma "
         "cabecera **Idempotency-Key** (hasta 100 caracteres sin espacios, por "
         "ejemplo un id de tu pedido). La segunda vez recibes la respuesta de la "
         "primera, con la cabecera Idempotent-Replayed: true, en vez de mandarlo "
         "otra vez.",
         "La aceptan `POST /emails`, `POST /contacts`, `POST /campaigns` y enviar "
         "y programar una campaña. Se guarda 24 horas, para esa llave y esa ruta. "
         "Con otro cuerpo responde 422; mientras la primera sigue en curso, 409.",
     ]},
    {"id": "fechas", "title": "Fechas y horas",
     "paragraphs": [
         "Las fechas salen en UTC, como **2026-10-20T20:00:00Z**. Las que mandas "
         "van en ISO 8601 **con su zona**: 2026-10-20T15:00:00-05:00 son las tres "
         "de la tarde en Panamá. Una sin zona se rechaza, porque no se sabe de "
         "dónde es.",
     ]},
    {"id": "listas", "title": "Listas dentro de un contacto",
     "paragraphs": [
         "Además de columnas de un valor (la ciudad, el número de socio), un "
         "contacto puede llevar **listas**: varias filas con los mismos datos, como "
         "las transacciones de un socio (fecha, descripción y monto) o los pedidos "
         "de un cliente. Se crean como una columna de tipo `list` con sus datos, "
         "caben 2 por cuenta, y cada una guarda hasta 50 filas y 3 KB por "
         "contacto. Una lista puede ir vacía: no deja incompleto a nadie.",
         "Cada fila lleva su `id`, que se pone solo al crearla y sirve para "
         "cambiarla o borrarla sin tocar las demás. Al agregar filas, si pasan de "
         "50, se van las más viejas.",
         "En una plantilla, `*|TRANSACCIONES|*` sola escribe una tabla con todas "
         "las filas. Para armar cada fila a tu manera, lo que va entre "
         "`*|#TRANSACCIONES|*` y `*|/TRANSACCIONES|*` se repite una vez por fila, "
         "con los datos de esa fila por su clave; lo que va entre "
         "`*|^TRANSACCIONES|*` y `*|/TRANSACCIONES|*` sale solo cuando no hay "
         "filas. En el asunto, una lista no escribe nada.",
     ],
     "code": "*|#TRANSACCIONES|*\n*|FECHA|*: *|DESCRIPCION|*, B/. *|MONTO|*\n"
             "*|/TRANSACCIONES|*\n*|^TRANSACCIONES|*\n"
             "Este mes no tuviste movimientos.\n*|/TRANSACCIONES|*"},
    {"id": "lienzo", "title": "El lienzo en JSON",
     "paragraphs": [
         "Una plantilla del lienzo es una hoja de 600 px de ancho que crece hacia "
         "abajo: `h` es su alto (de 80 a 4,000), `bg` su color y `items` lo que "
         "lleva encima, hasta 60 cosas. Cada una dice qué es en `t` y dónde va en "
         "`x`, `y`, `w` y `h`, en píxeles y dentro de la hoja. El correo se arma "
         "en tablas al enviarlo, así que lo que se encima tiene que poder cortarse "
         "en franjas y columnas.",
         "**text**: `text` (hasta 2,000 caracteres, con saltos de línea y "
         "marcas), `font` (Arial, Helvetica, Verdana, Tahoma, Trebuchet MS, "
         "Georgia, Times New Roman, Courier New, Palatino, Garamond, Lucida Sans o "
         "Century Gothic), `size` (de 14 a 72), `color` (#RRGGBB), `bold`, "
         "`italic`, `align` (left, center o right), `line` (de 1 a 2.5) y `list` "
         "(con viñetas). **button**: `text` (hasta 60), `href` (https:// o "
         "mailto:), `bg`, `radius` (de 0 a 60) y la misma letra que un texto. "
         "**image**: `name` (el que devuelve `POST /images`), `alt` (obligatorio), "
         "`href`, `fit` (cover o contain), `crop` ([x, y, ancho, alto], de 0 a 1) "
         "y `rot` (grados). **shape**: `shape` (rect, line, ellipse, triangle, "
         "star o arrow), `bg`, `radius` y `rot`; una línea mide de 1 a 12 px de "
         "alto.",
         "Se guarda solo si arma bien el correo y pasa la revisión antispam, igual "
         "que en el panel: entre otras cosas, al menos 200 caracteres de texto, "
         "poca imagen, pocos enlaces y nada de acortadores. `POST /templates/check` "
         "dice cómo va cada regla sin guardar nada. Lo más cómodo es armarla en el "
         "panel y leerla después con `GET /templates/{template_id}`.",
     ],
     "code": "{\n  \"h\": 420,\n  \"bg\": \"#FFFFFF\",\n  \"items\": [\n"
             "    {\"t\": \"text\", \"x\": 40, \"y\": 40, \"w\": 520, \"h\": 120,\n"
             "     \"text\": \"Hola *|NOMBRE|*, estos son tus movimientos.\",\n"
             "     \"font\": \"Arial\", \"size\": 18, \"color\": \"#18181B\"},\n"
             "    {\"t\": \"button\", \"x\": 40, \"y\": 320, \"w\": 240, \"h\": 48,\n"
             "     \"text\": \"Ver mi cuenta\", \"href\": \"https://coopejemplo.com/cuenta\",\n"
             "     \"font\": \"Arial\", \"size\": 16, \"color\": \"#FFFFFF\", \"bg\": \"#31A9E8\"}\n"
             "  ]\n}"},
    {"id": "fuera", "title": "Lo que la API no hace",
     "paragraphs": [
         "Hay cosas que se hacen solo en el panel, porque son de una persona y no "
         "de un sistema: la contraseña y el segundo factor, los usuarios, pagar y "
         "cambiar de plan, conectar dominios y confirmar remitentes, crear llaves "
         "y avisos, y eliminar la cuenta.",
     ]},
]

# Los ejemplos que se repiten: un contacto con una lista, y esa lista.
_ITEMS = [{"key": "FECHA", "label": "Fecha", "type": "date"},
          {"key": "DESCRIPCION", "label": "Descripción", "type": "text"},
          {"key": "MONTO", "label": "Monto", "type": "number"}]
_ROWS = [{"FECHA": "2026-10-01", "DESCRIPCION": "Depósito", "MONTO": "150", "id": "3fa9c1"},
         {"FECHA": "2026-10-09", "DESCRIPCION": "Pago de préstamo", "MONTO": "85.5",
          "id": "b07e42"}]
_LIST = {"key": "TRANSACCIONES", "label": "Transacciones", "items": _ITEMS, "rows": _ROWS}
_CONTACT = {
    "id": "6531f5c2a1b2c3d4e5f60801", "external_id": "1043", "email": "ana@ejemplo.com",
    "name": "Ana Pérez", "tags": ["Socios"],
    "fields": {"CIUDAD": "Santiago", "TRANSACCIONES": _ROWS},
    "status": "active", "suppression": None, "complete": True,
    "consent": {"source": "members", "note": "Lista de socios 2026",
                "recorded_at": "2026-10-01T15:20:00Z"},
    "added_by": "api", "created_at": "2026-10-01T15:20:00Z",
    "updated_at": "2026-10-12T13:05:44Z"}
_TEMPLATE = {"id": "6533b1d2a1b2c3d4e5f60901", "name": "Estado de cuenta", "source": "canvas",
             "folder_id": "6533b0aaa1b2c3d4e5f60900", "send_from": None, "reply_to": None,
             "created_at": "2026-10-02T14:00:00Z", "updated_at": "2026-10-15T16:30:00Z"}
_CANVAS = {"v": 2, "h": 420, "bg": "#FFFFFF", "items": [
    {"t": "text", "x": 40, "y": 40, "w": 520, "h": 120,
     "text": "Hola *|NOMBRE|*, estos son tus movimientos de octubre.\n*|TRANSACCIONES|*",
     "font": "Arial", "size": 18, "color": "#18181B", "bold": False, "italic": False,
     "align": "left", "line": 1.4},
    {"t": "button", "x": 40, "y": 320, "w": 240, "h": 48, "text": "Ver mi cuenta",
     "font": "Arial", "size": 16, "color": "#FFFFFF", "bold": True, "italic": False,
     "align": "center", "href": "https://coopejemplo.com/cuenta", "bg": "#31A9E8",
     "radius": 8}]}
_FOLDER = {"id": "6533b0aaa1b2c3d4e5f60900", "name": "Cobros", "color": "blue",
           "templates": 4}

# Las rutas, por grupo, en el orden de la página.
GROUPS: list[dict[str, Any]] = [
    {"id": "cuenta", "title": "Tu cuenta",
     "intro": "De quién es la llave, qué puede hacer y desde qué direcciones se "
              "puede enviar.",
     "endpoints": [
         {"method": "GET", "path": "/me", "scope": ANY,
          "title": "Tu cuenta y tu llave",
          "description": "La empresa, su plan, la cuota del mes, los límites, si hoy "
                         "se puede enviar (y si no, por qué) y la llave con la que "
                         "llamas.",
          "response": {
              "account": {"id": "6531f0c2a1b2c3d4e5f60718", "company": "Cooperativa Ejemplo",
                          "plan": "negocio", "plan_until": "2026-11-17T05:00:00Z",
                          "demo": None},
              "quota": {"month": "2026-10", "allowed": 15000, "used": 1240, "left": 13760},
              "limits": {"contacts": 3000, "tags": 2, "fields": 5, "images": 50,
                         "templates": 300},
              "can_send": True, "blocked": [],
              "key": {"id": "6532a9e1f0e1d2c3b4a59687", "name": "Tienda en línea",
                      "mode": "live", "scopes": ["contacts:write", "emails:send"],
                      "prefix": "sa_live_Xq3f", "last4": "9KcA", "expires_at": None,
                      "created_at": "2026-10-17T14:02:11Z"}}},
         {"method": "GET", "path": "/senders", "scope": ANY,
          "title": "Remitentes y «Responder a»",
          "description": "Desde qué direcciones puede salir un correo (`ready` dice "
                         "si hoy puede), a dónde se responde, y tus dominios con "
                         "su estado. Se conectan y se confirman en el panel, en "
                         "Configuración de envío.",
          "response": {
              "from": [{"id": "6531f2aa0b1c2d3e4f506172", "name": "Cooperativa Ejemplo",
                        "address": "coop@envios.sobreala.com", "ready": True,
                        "shared": True, "default": True},
                       {"id": "6531f2bb0b1c2d3e4f506173", "name": "Cobros",
                        "address": "cobros@coopejemplo.com", "ready": True,
                        "shared": False, "default": False}],
              "reply_to": [{"address": "atencion@coopejemplo.com", "default": True}],
              "reply_to_default": "atencion@coopejemplo.com",
              "domains": [{"name": "coopejemplo.com", "status": "verified"}]}},
         {"method": "GET", "path": "/openapi.json", "scope": PUBLIC,
          "title": "Esta descripción, en OpenAPI",
          "description": "Todo lo de esta página en OpenAPI 3.1, para generar un "
                         "cliente o importarlo en Postman. No pide llave.",
          "response": {"openapi": "3.1.0", "info": {"title": TITLE, "version": VERSION}}},
     ]},
    {"id": "contactos", "title": "Contactos",
     "intro": "Tu lista: cada persona una sola vez por su correo, con sus "
              "etiquetas y tus columnas. Cargar es actualizar: si la dirección ya "
              "está, se le suma lo nuevo y no se duplica. Las etiquetas y las "
              "columnas se crean antes de usarse, y las columnas son obligatorias: "
              "a un contacto sin todas no se le envía nada (las listas no cuentan: "
              "pueden ir vacías). Cada contacto tiene su `id`, y puede llevar además "
              "**el id de tu sistema** (`external_id`: tu número de socio o de "
              "cliente, hasta 64 letras, números y . _ : @ -), único en la cuenta, "
              "para encontrarlo por él aunque cambie de correo.",
     "endpoints": [
         {"method": "GET", "path": "/contacts", "scope": "contacts:read",
          "title": "Listar contactos",
          "description": "De los más nuevos a los más viejos. Cada uno dice si "
                         "puede recibir (`status`: active, suppressed o invalid) y si "
                         "tiene todas sus columnas (`complete`). Sus listas vienen "
                         "enteras dentro de `fields`.",
          "test": "sí",
          "query": [
              {"name": "email", "type": "texto", "description": "Uno exacto."},
              {"name": "external_id", "type": "texto",
               "description": "El que tiene ese id de tu sistema."},
              {"name": "search", "type": "texto",
               "description": "Los que empiezan así: `ana@` o `ana@coop`."},
              {"name": "tag", "type": "texto", "description": "Los que llevan esa etiqueta."},
              {"name": "limit", "type": "entero", "description": "De 1 a 100. 25 si no se dice."},
              {"name": "cursor", "type": "texto", "description": "El `next_cursor` de la página anterior."},
          ],
          "query_example": "tag=Socios&limit=50",
          "response": {"data": [_CONTACT], "next_cursor": "ZTFfwqLLPOX2BgEA"}},
         {"method": "GET", "path": "/contacts/{contact_id}", "scope": "contacts:read",
          "title": "Un contacto", "description": "El mismo que sale en la lista.",
          "test": "sí",
          "response": _CONTACT},
         {"method": "POST", "path": "/contacts", "scope": "contacts:write",
          "title": "Cargar contactos",
          "description": "De 1 a 1,000 por vez. Los nuevos entran si caben en tu "
                         "plan y traen todas tus columnas; los que ya están se "
                         "actualizan (las etiquetas se suman, nunca se quitan, y una "
                         "lista que llega reemplaza la que tenía). A quien ya está se "
                         "le encuentra por su `external_id` si lo traes y existe (y "
                         "entonces su correo puede cambiar), y si no, por su correo. "
                         "Cada fila dice qué le pasó en `results`, en el orden en que "
                         "llegó: `added`, `updated` o `rejected` con su motivo: "
                         "bad_row, invalid_email, duplicate, bad_name, bad_tags, "
                         "unknown_tag, bad_external_id, unknown_field, bad_value, "
                         "bad_list, incomplete (con `missing`), limit, "
                         "external_id_conflict (ese correo ya es de un contacto con "
                         "otro id de tu sistema) o email_taken (el contacto de ese id "
                         "pasaría a un correo que ya es de otro). Una dirección dada "
                         "de baja se guarda pero no recibe (`warning: suppressed`), y "
                         "una de un dominio que no recibe correo entra marcada "
                         "(`warning: undeliverable`). Hasta 5,000 filas por minuto.",
          "test": "no",
          "fields": [
              {"name": "contacts", "type": "lista", "required": True,
               "description": "Cada uno con `email`, y si quieres `name`, `tags` (etiquetas "
                              "que ya existen), `external_id` y `fields` (tus columnas por "
                              "su clave; una lista va entera, con sus filas)."},
              {"name": "consent", "type": "objeto", "required": True,
               "description": "De dónde salieron: `source` es own_form (tu formulario), "
                              "members (socios), customers (clientes), event (un evento) u "
                              "other; `note`, hasta 300 caracteres. Se guarda en cada "
                              "contacto nuevo, y es lo que enseñas si alguien reclama."},
              {"name": "tags", "type": "lista de textos",
               "description": "Etiquetas para todos los de esta carga."},
          ],
          "request": {"consent": {"source": "members", "note": "Sistema de socios"},
                      "tags": ["Socios"],
                      "contacts": [{"email": "ana@ejemplo.com", "name": "Ana Pérez",
                                    "external_id": "1043",
                                    "fields": {"CIUDAD": "Santiago", "TRANSACCIONES": [
                                        {"FECHA": "2026-10-01", "DESCRIPCION": "Depósito",
                                         "MONTO": 150}]}},
                                   {"email": "luis@ejemplo", "name": "Luis"}]},
          "response": {"added": 1, "updated": 0, "rejected": 1, "results": [
              {"index": 0, "email": "ana@ejemplo.com", "result": "added"},
              {"index": 1, "email": "luis@ejemplo", "result": "rejected",
               "reason": "invalid_email"}]}},
         {"method": "PATCH", "path": "/contacts/{contact_id}", "scope": "contacts:write",
          "title": "Cambiar un contacto",
          "description": "Solo lo que mandes: `email`, `name`, `external_id` (null lo "
                         "quita), `tags` (reemplazan las que tenía) y `fields` (las "
                         "columnas se mezclan con las que tenía, y una lista que llega "
                         "reemplaza la suya). Como en el panel, queda con todas sus "
                         "columnas llenas. De dónde salió y cuándo entró no se cambian.",
          "test": "no",
          "fields": [
              {"name": "email", "type": "texto", "description": "Si ya es de otro contacto: 409."},
              {"name": "name", "type": "texto", "description": "Hasta 120 caracteres."},
              {"name": "external_id", "type": "texto o null",
               "description": "Si ya es de otro contacto: 409 `external_id_taken`."},
              {"name": "tags", "type": "lista de textos", "description": "Etiquetas que ya existen."},
              {"name": "fields", "type": "objeto",
               "description": "Tus columnas por su clave, y tus listas enteras."},
          ],
          "request": {"tags": ["Socios", "Asamblea 2026"], "fields": {"CIUDAD": "Las Palmas"}},
          "response": {**_CONTACT, "tags": ["Socios", "Asamblea 2026"],
                       "fields": {"CIUDAD": "Las Palmas", "TRANSACCIONES": _ROWS},
                       "updated_at": "2026-10-17T19:02:10Z"}},
         {"method": "DELETE", "path": "/contacts/{contact_id}", "scope": "contacts:write",
          "title": "Borrar un contacto",
          "description": "Si se había dado de baja, su supresión se queda: volver a "
                         "cargarlo no le devuelve los correos.",
          "test": "no",
          "response": {"id": "6531f5c2a1b2c3d4e5f60801", "deleted": True}},
         {"method": "GET", "path": "/tags", "scope": "contacts:read",
          "title": "Etiquetas", "description": "Las de la cuenta, con cuántos contactos "
                                               "lleva cada una, y cuántas caben en tu plan.",
          "test": "sí",
          "response": {"data": [{"name": "Socios", "contacts": 812}], "limit": 2}},
         {"method": "POST", "path": "/tags", "scope": "contacts:write",
          "title": "Crear una etiqueta",
          "description": "Sin fijarse en mayúsculas: «Socios» y «socios» son la misma.",
          "test": "no", "status": 201,
          "fields": [{"name": "name", "type": "texto", "required": True,
                      "description": "Hasta 40 caracteres."}],
          "request": {"name": "Asamblea 2026"},
          "response": {"name": "Asamblea 2026", "contacts": 0}},
         {"method": "DELETE", "path": "/tags/{name}", "scope": "contacts:write",
          "title": "Borrar una etiqueta",
          "description": "Sale de la cuenta y de los contactos que la llevaban; los "
                         "contactos se quedan. El nombre va en la dirección, "
                         "codificado (un espacio es %20).",
          "test": "no",
          "response": {"name": "Asamblea 2026", "deleted": True, "contacts": 37}},
         {"method": "GET", "path": "/fields", "scope": "contacts:read",
          "title": "Columnas",
          "description": "Tus columnas: la clave con que se nombran (`*|CIUDAD|*` en una "
                         "plantilla), el nombre, el tipo y cuántos contactos la tienen "
                         "llena. Una lista trae sus datos en `items`, y `filled` cuenta "
                         "a los que tienen al menos una fila.",
          "test": "sí",
          "response": {"data": [{"key": "CIUDAD", "label": "Ciudad", "type": "text",
                                 "filled": 790},
                                {"key": "TRANSACCIONES", "label": "Transacciones",
                                 "type": "list", "filled": 412, "items": _ITEMS}],
                       "limit": 5, "lists_max": 2}},
         {"method": "POST", "path": "/fields", "scope": "contacts:write",
          "title": "Crear una columna",
          "description": "La clave sale del nombre: «Número de socio» es NUMERO_DE_SOCIO. "
                         "Recién creada, todos tus contactos quedan incompletos hasta "
                         "que la tengan. Una lista (`type: list`) lleva sus datos en "
                         "`items`, cuenta como una columna de tu plan y no deja "
                         "incompleto a nadie.",
          "test": "no", "status": 201,
          "fields": [{"name": "label", "type": "texto", "required": True,
                      "description": "Hasta 40 caracteres."},
                     {"name": "type", "type": "texto", "required": True,
                      "description": "text, number, date, yesno o list."},
                     {"name": "items", "type": "lista",
                      "description": "Solo para una lista: de 1 a 6 datos, cada uno con "
                                     "`label` y `type` (text, number, date o yesno)."}],
          "request": {"label": "Transacciones", "type": "list", "items": [
              {"label": "Fecha", "type": "date"}, {"label": "Descripción", "type": "text"},
              {"label": "Monto", "type": "number"}]},
          "response": {"key": "TRANSACCIONES", "label": "Transacciones", "type": "list",
                       "filled": 0, "items": _ITEMS}},
         {"method": "PATCH", "path": "/fields/{key}", "scope": "contacts:write",
          "title": "Cambiar una columna",
          "description": "A una columna, el tipo, y solo si todo lo escrito encaja en el "
                         "nuevo: si no, 409 dice cuántos contactos lo impiden. A una "
                         "lista, un dato por vez: `add` lo agrega y `remove` lo quita "
                         "(y lo borra de todas las filas de todos tus contactos). El "
                         "nombre no se cambia, porque es lo que nombran tus plantillas.",
          "test": "no",
          "fields": [{"name": "type", "type": "texto",
                      "description": "A una columna: text, number, date o yesno."},
                     {"name": "add", "type": "objeto",
                      "description": "A una lista: el dato nuevo, con `label` y `type`."},
                     {"name": "remove", "type": "texto",
                      "description": "A una lista: la clave del dato que se quita. Le "
                                     "queda al menos uno."}],
          "request": {"type": "number"},
          "response": {"key": "NUMERO_DE_SOCIO", "label": "Número de socio",
                       "type": "number", "filled": 790}},
         {"method": "DELETE", "path": "/fields/{key}", "scope": "contacts:write",
          "title": "Borrar una columna",
          "description": "Y lo que los contactos tenían escrito en ella (de una lista, "
                         "todas sus filas).",
          "test": "no",
          "response": {"key": "NUMERO_DE_SOCIO", "deleted": True, "contacts": 790}},
         {"method": "GET", "path": "/suppressions", "scope": "contacts:read",
          "title": "Supresiones",
          "description": "Las direcciones a las que ya no se les escribe y por qué: "
                         "unsubscribe (se dio de baja), hard_bounce (no existe), "
                         "complaint (lo marcó como spam) o manual (de antes). Solo para "
                         "mirar: entran solas y no se quitan.",
          "test": "sí",
          "query": [{"name": "reason", "type": "texto", "description": "Solo las de ese motivo."},
                    {"name": "email", "type": "texto", "description": "Una dirección exacta."},
                    {"name": "limit", "type": "entero", "description": "De 1 a 100."},
                    {"name": "cursor", "type": "texto", "description": "Para la página siguiente."}],
          "response": {"data": [{"email": "luis@ejemplo.com", "reason": "unsubscribe",
                                 "source": "enlace del correo",
                                 "created_at": "2026-10-11T22:40:03Z"}],
                       "next_cursor": None}},
     ]},
    {"id": "filas", "title": "Las filas de una lista",
     "intro": "Las filas de una lista de un contacto, sin tocar lo demás: verlas, "
              "cambiarlas enteras, agregar al final, o cambiar y borrar una por su "
              "`id`. `{key}` es la clave de la lista (TRANSACCIONES). Cómo se crea "
              "una lista y cómo sale en un correo está en «Listas dentro de un "
              "contacto».",
     "endpoints": [
         {"method": "GET", "path": "/contacts/{contact_id}/lists/{key}",
          "scope": "contacts:read",
          "title": "Ver una lista",
          "description": "Sus datos y sus filas, de la más vieja a la más nueva.",
          "test": "sí",
          "response": _LIST},
         {"method": "PUT", "path": "/contacts/{contact_id}/lists/{key}",
          "scope": "contacts:write",
          "title": "Cambiar la lista entera",
          "description": "Las filas que mandes reemplazan a todas las que tenía, y `[]` "
                         "la vacía. Una fila que trae su `id` lo conserva.",
          "test": "no",
          "fields": [{"name": "rows", "type": "lista", "required": True,
                      "description": "Hasta 50 filas, cada una con sus datos por su "
                                     "clave y al menos uno."}],
          "request": {"rows": [{"FECHA": "2026-10-01", "DESCRIPCION": "Depósito",
                                "MONTO": 150}]},
          "response": {**_LIST, "rows": [_ROWS[0]]}},
         {"method": "POST", "path": "/contacts/{contact_id}/lists/{key}",
          "scope": "contacts:write",
          "title": "Agregar filas",
          "description": "Al final, en una sola escritura. Si la lista pasa de 50 filas "
                         "(o de `keep_last`), se van las más viejas.",
          "test": "no", "status": 201,
          "fields": [{"name": "rows", "type": "lista", "required": True,
                      "description": "Las filas nuevas."},
                     {"name": "keep_last", "type": "entero",
                      "description": "Cuántas dejar, de 1 a 50. 50 si no se dice."}],
          "request": {"rows": [{"FECHA": "2026-10-09", "DESCRIPCION": "Pago de préstamo",
                                "MONTO": 85.5}]},
          "response": _LIST},
         {"method": "PATCH", "path": "/contacts/{contact_id}/lists/{key}/{row_id}",
          "scope": "contacts:write",
          "title": "Cambiar una fila",
          "description": "Los datos que mandes, sobre los que tenía; null borra uno. La "
                         "fila se queda en su sitio y con su `id`.",
          "test": "no",
          "fields": [{"name": "MONTO", "type": "texto o número",
                      "description": "Cada dato por su clave, como en la lista."}],
          "request": {"MONTO": 90},
          "response": {**_ROWS[1], "MONTO": "90"}},
         {"method": "DELETE", "path": "/contacts/{contact_id}/lists/{key}/{row_id}",
          "scope": "contacts:write",
          "title": "Borrar una fila",
          "description": "Las demás se quedan como estaban.",
          "test": "no",
          "response": {"id": "b07e42", "deleted": True}},
     ]},
    {"id": "plantillas", "title": "Plantillas",
     "intro": "Las plantillas de tu cuenta, las mismas de Mis plantillas. Las del "
              "lienzo (`source: canvas`) se crean, se cambian y se cargan en ZIP "
              "por aquí, con las mismas reglas que al guardar en el panel; las "
              "cargadas en HTML (`upload`) y las prediseñadas de antes (`builtin`) "
              "se leen, se arman, se mueven, se duplican y se borran. Cada una "
              "puede elegir de quién sale (`send_from`, el id de un remitente de "
              "`GET /senders`) y a dónde se responde (`reply_to`); sin elegir, van "
              "los predeterminados. Caben 300 por cuenta.",
     "endpoints": [
         {"method": "GET", "path": "/templates", "scope": "templates:read",
          "title": "Listar plantillas",
          "description": "De las más nuevas a las más viejas, sin su contenido.",
          "test": "sí",
          "query": [
              {"name": "folder_id", "type": "texto",
               "description": "Las de esa carpeta, o `none` para las que no tienen."},
              {"name": "source", "type": "texto", "description": "canvas, upload o builtin."},
              {"name": "limit", "type": "entero", "description": "De 1 a 100. 25 si no se dice."},
              {"name": "cursor", "type": "texto", "description": "Para la página siguiente."},
          ],
          "query_example": "folder_id=none",
          "response": {"data": [_TEMPLATE], "next_cursor": None, "limit": 300}},
         {"method": "GET", "path": "/templates/{template_id}", "scope": "templates:read",
          "title": "Una plantilla",
          "description": "Con las marcas que nombra (`marks`), los bloques que repite "
                         "o esconden (`blocks`) y lo que tiene dentro: el `canvas` y la "
                         "dirección de cada foto en `images` si es del lienzo, el `html` "
                         "si se cargó en HTML, o `template` y `fields` si es una "
                         "prediseñada.",
          "test": "sí",
          "response": {**_TEMPLATE, "marks": ["NOMBRE", "TRANSACCIONES"], "blocks": [],
                       "canvas": _CANVAS, "images": {}}},
         {"method": "POST", "path": "/templates/{template_id}/render",
          "scope": "templates:read",
          "title": "Ver cómo sale",
          "description": "El correo armado, con los datos de un contacto (`contact_id`), "
                         "los que mandes en `data` (que mandan sobre los del contacto) o "
                         "los dos. Transaccional sale sin baja ni marca de agua; "
                         "promocional, con las dos, y el enlace de baja es de ejemplo. "
                         "`missing` dice qué marcas se quedarían en blanco. No envía ni "
                         "guarda nada.",
          "test": "sí",
          "fields": [
              {"name": "type", "type": "texto",
               "description": "transactional o promotional. promotional si no se dice."},
              {"name": "contact_id", "type": "texto", "description": "Un contacto de la cuenta."},
              {"name": "subject", "type": "texto",
               "description": "Un asunto con marcas, hasta 150 caracteres, para verlo lleno."},
              {"name": "data", "type": "objeto",
               "description": "Cada marca por su clave: texto o un número de hasta 1,000 "
                              "caracteres, o una lista de hasta 50 filas (cada una con "
                              "hasta 10 datos de hasta 200 caracteres). Hasta 50 claves y "
                              "32 KB, en una línea cada valor. CORREO no se manda: es la "
                              "dirección."},
          ],
          "request": {"type": "transactional", "contact_id": "6531f5c2a1b2c3d4e5f60801",
                      "subject": "Tu estado de cuenta, *|NOMBRE|*",
                      "data": {"SALDO": "1,250.00"}},
          "response": {"type": "transactional",
                       "subject": "Tu estado de cuenta, Ana Pérez",
                       "html": "<!doctype html><html>...</html>",
                       "text": "Hola Ana Pérez, estos son tus movimientos de octubre. ...",
                       "bytes": 18432, "marks": ["NOMBRE", "TRANSACCIONES", "SALDO"],
                       "blocks": [], "missing": []}},
         {"method": "POST", "path": "/templates/check", "scope": "templates:read",
          "title": "Revisar un lienzo",
          "description": "La revisión del editor, sin guardar: `ok` dice si se podría "
                         "guardar, `issues` lo que falta y `rules` cómo va cada regla, "
                         "en el orden de la ventana de requisitos del panel.",
          "test": "sí",
          "fields": [{"name": "canvas", "type": "objeto", "required": True,
                      "description": "El lienzo, como en «El lienzo en JSON»."},
                     {"name": "name", "type": "texto",
                      "description": "Su nombre, que es la primera regla."}],
          "request": {"name": "Estado de cuenta", "canvas": {
              "h": 420, "bg": "#FFFFFF", "items": [
                  {"t": "text", "x": 40, "y": 40, "w": 520, "h": 80,
                   "text": "Hola *|NOMBRE|*", "font": "Arial", "size": 22}]}},
          "response": {"ok": False, "bytes": 9120, "max": 104448,
                       "issues": ["Tiene muy poco texto (4 caracteres). Escribe al menos "
                                  "200: un correo casi sin texto es de lo que más va a "
                                  "spam."],
                       "rules": [{"group": "build", "ok": True, "text": "Tiene nombre."},
                                 {"group": "spam", "ok": False,
                                  "text": "Al menos 200 caracteres de texto (tiene 4)."}]}},
         {"method": "GET", "path": "/templates/{template_id}/zip",
          "scope": "templates:read",
          "title": "Bajar el ZIP",
          "description": "El mismo ZIP que baja el editor: el lienzo con sus fotos, que "
                         "se vuelve a cargar en cualquier cuenta, y el HTML con sus "
                         "imágenes. Solo de las del lienzo. Responde el archivo, no JSON. "
                         "Cuenta para el límite de 5 plantillas por minuto.",
          "test": "sí", "returns": "application/zip",
          "response": None},
         {"method": "POST", "path": "/templates", "scope": "templates:write",
          "title": "Crear una plantilla del lienzo",
          "description": "Con la misma revisión que Guardar: si algo no se cumple, 422 "
                         "dice qué en `fields.canvas`. Las fotos que nombra tienen que "
                         "ser tuyas (súbelas antes con `POST /images`). Hasta 5 por "
                         "minuto.",
          "test": "no", "status": 201,
          "fields": [
              {"name": "name", "type": "texto", "required": True,
               "description": "Hasta 80 caracteres."},
              {"name": "canvas", "type": "objeto", "required": True,
               "description": "El lienzo, como en «El lienzo en JSON»."},
              {"name": "folder_id", "type": "texto", "description": "Una carpeta tuya."},
              {"name": "send_from", "type": "texto",
               "description": "El id de un remitente listo. Sin él, el predeterminado."},
              {"name": "reply_to", "type": "texto",
               "description": "Uno de tus «Responder a». Sin él, el predeterminado."},
          ],
          "request": {"name": "Estado de cuenta", "folder_id": "6533b0aaa1b2c3d4e5f60900",
                      "canvas": {"h": 420, "bg": "#FFFFFF", "items": _CANVAS["items"]}},
          "response": {**_TEMPLATE, "marks": ["NOMBRE", "TRANSACCIONES"], "blocks": [],
                       "canvas": _CANVAS, "images": {}}},
         {"method": "POST", "path": "/templates/import", "scope": "templates:write",
          "title": "Cargar un ZIP",
          "description": "El ZIP que baja el Lienzo, de esta cuenta o de otra, en "
                         "multipart: `file`, y si quieres `name` y `folder_id`. Sus fotos "
                         "entran a tu cuenta y cuentan contra tu tope. Hasta 5 MB.",
          "test": "no", "status": 201,
          "upload": "file=@estado-de-cuenta.zip",
          "fields": [{"name": "file", "type": "archivo", "required": True,
                      "description": "El ZIP, en multipart/form-data."},
                     {"name": "name", "type": "texto",
                      "description": "Su nombre. Sin él, el que trae el ZIP."},
                     {"name": "folder_id", "type": "texto", "description": "Una carpeta tuya."}],
          "response": {**_TEMPLATE, "marks": ["NOMBRE", "TRANSACCIONES"], "blocks": [],
                       "canvas": _CANVAS, "images": {}}},
         {"method": "PATCH", "path": "/templates/{template_id}", "scope": "templates:write",
          "title": "Cambiar una plantilla",
          "description": "Solo lo que mandes: `name`, `folder_id` (null la saca de su "
                         "carpeta), `send_from` y `reply_to` (null vuelve al "
                         "predeterminado) y, en una del lienzo, `canvas` entero, con la "
                         "revisión de Guardar.",
          "test": "no",
          "fields": [
              {"name": "name", "type": "texto", "description": "Hasta 80 caracteres."},
              {"name": "folder_id", "type": "texto o null", "description": "Una carpeta tuya."},
              {"name": "send_from", "type": "texto o null", "description": "Un remitente listo."},
              {"name": "reply_to", "type": "texto o null",
               "description": "Uno de tus «Responder a»."},
              {"name": "canvas", "type": "objeto",
               "description": "Solo en una del lienzo: el lienzo entero."},
          ],
          "request": {"name": "Estado de cuenta de noviembre", "folder_id": None},
          "response": {**_TEMPLATE, "name": "Estado de cuenta de noviembre",
                       "folder_id": None, "marks": ["NOMBRE", "TRANSACCIONES"],
                       "blocks": [], "canvas": _CANVAS, "images": {}}},
         {"method": "POST", "path": "/templates/{template_id}/duplicate",
          "scope": "templates:write",
          "title": "Duplicar una plantilla",
          "description": "Queda en la misma carpeta, con el nombre que mandes o «Copia "
                         "de…».",
          "test": "no", "status": 201,
          "fields": [{"name": "name", "type": "texto", "description": "Hasta 80 caracteres."}],
          "request": {"name": "Estado de cuenta (socios nuevos)"},
          "response": {**_TEMPLATE, "id": "6533b9f0a1b2c3d4e5f60955",
                       "name": "Estado de cuenta (socios nuevos)",
                       "marks": ["NOMBRE", "TRANSACCIONES"], "blocks": [],
                       "canvas": _CANVAS, "images": {}}},
         {"method": "DELETE", "path": "/templates/{template_id}", "scope": "templates:write",
          "title": "Borrar una plantilla",
          "description": "Y las fotos que ninguna otra nombra. Una foto que ya salió en "
                         "un correo se sigue viendo un año.",
          "test": "no",
          "response": {"id": "6533b1d2a1b2c3d4e5f60901", "deleted": True}},
         {"method": "POST", "path": "/templates/move", "scope": "templates:write",
          "title": "Mover plantillas",
          "description": "Hasta 200 a una carpeta, o a ninguna con `folder_id: null`. "
                         "Las que no son tuyas no se tocan; `moved` dice cuántas sí.",
          "test": "no",
          "fields": [{"name": "ids", "type": "lista", "required": True,
                      "description": "Los ids de las plantillas."},
                     {"name": "folder_id", "type": "texto o null", "required": True,
                      "description": "La carpeta, o null."}],
          "request": {"ids": ["6533b1d2a1b2c3d4e5f60901"],
                      "folder_id": "6533b0aaa1b2c3d4e5f60900"},
          "response": {"moved": 1}},
         {"method": "POST", "path": "/images", "scope": "templates:write",
          "title": "Subir una foto",
          "description": "Una foto para un lienzo, en multipart (`file`, hasta 5 MB): "
                         "se revisa, se le quitan los bordes transparentes y se achica. "
                         "Su `name` es el que va en una imagen del lienzo. Cuenta contra "
                         "el tope de fotos de tu plan, y hasta 20 por minuto.",
          "test": "no", "status": 201,
          "upload": "file=@foto.jpg",
          "fields": [{"name": "file", "type": "archivo", "required": True,
                      "description": "JPG, PNG o GIF, en multipart/form-data."}],
          "response": {"name": "k3J9xQ2mP0aZr8VbT1cW4d.jpg",
                       "url": "https://app.sobreala.com/img/k3J9xQ2mP0aZr8VbT1cW4d.jpg",
                       "width": 1200, "height": 800}},
     ]},
    {"id": "carpetas", "title": "Carpetas",
     "intro": "Las carpetas de Mis plantillas: un solo nivel, con nombre y color. "
              "Borrar una no borra sus plantillas, que quedan sin carpeta.",
     "endpoints": [
         {"method": "GET", "path": "/folders", "scope": "templates:read",
          "title": "Listar carpetas",
          "description": "Por nombre, con cuántas plantillas tiene cada una, cuántas "
                         "caben y los colores que hay.",
          "test": "sí",
          "response": {"data": [_FOLDER], "limit": 50,
                       "colors": ["gray", "white", "blue", "green", "amber", "red",
                                  "purple", "pink", "teal"]}},
         {"method": "POST", "path": "/folders", "scope": "templates:write",
          "title": "Crear una carpeta",
          "description": "El nombre no se repite (sin fijarse en mayúsculas).",
          "test": "no", "status": 201,
          "fields": [{"name": "name", "type": "texto", "required": True,
                      "description": "Hasta 40 caracteres."},
                     {"name": "color", "type": "texto", "description": "gray si no se dice."}],
          "request": {"name": "Cobros", "color": "blue"},
          "response": {**_FOLDER, "templates": 0}},
         {"method": "PATCH", "path": "/folders/{folder_id}", "scope": "templates:write",
          "title": "Cambiar una carpeta",
          "description": "Su nombre, su color o los dos.",
          "test": "no",
          "fields": [{"name": "name", "type": "texto", "description": "Hasta 40 caracteres."},
                     {"name": "color", "type": "texto", "description": "Uno de los colores."}],
          "request": {"color": "green"},
          "response": {**_FOLDER, "color": "green"}},
         {"method": "DELETE", "path": "/folders/{folder_id}", "scope": "templates:write",
          "title": "Borrar una carpeta",
          "description": "Sus plantillas se quedan, sin carpeta.",
          "test": "no",
          "response": {"id": "6533b0aaa1b2c3d4e5f60900", "deleted": True}},
     ]},
]


def endpoints() -> list[dict[str, Any]]:
    """Todas las rutas, cada una con el id de su grupo."""
    return [{**one, "group": group["id"]} for group in GROUPS
            for one in group["endpoints"]]


def anchor(endpoint: dict[str, Any]) -> str:
    """El ancla de una ruta en la página: `get-me`, `post-contacts`."""
    path = endpoint["path"].strip("/").replace("{", "").replace("}", "")
    return (endpoint["method"].lower() + "-" + path.replace("/", "-")
            .replace(".", "-")).rstrip("-")


def _schema(value: Any) -> dict[str, Any]:
    """Un esquema JSON sencillo sacado de un ejemplo."""
    if isinstance(value, bool):
        return {"type": "boolean"}
    if isinstance(value, int):
        return {"type": "integer"}
    if isinstance(value, float):
        return {"type": "number"}
    if isinstance(value, str):
        return {"type": "string"}
    if value is None:
        return {}
    if isinstance(value, list):
        return {"type": "array", "items": _schema(value[0]) if value else {}}
    return {"type": "object",
            "properties": {key: _schema(one) for key, one in value.items()}}


# Los tipos de la página, como los nombra OpenAPI.
OPENAPI_TYPES = {"texto": "string", "entero": "integer", "número": "number",
                 "sí o no": "boolean", "lista": "array", "lista de textos": "array",
                 "objeto": "object"}


def openapi() -> dict[str, Any]:
    """La descripción en OpenAPI 3.1."""
    paths: dict[str, Any] = {}
    error_schema = {"type": "object", "properties": {"error": {
        "type": "object", "properties": {
            "code": {"type": "string"}, "message": {"type": "string"},
            "fields": {"type": "object"}, "request_id": {"type": "string"}}}}}
    for one in endpoints():
        operation: dict[str, Any] = {
            "operationId": anchor(one).replace("-", "_"),
            "summary": one["title"],
            "description": one.get("description", ""),
            "tags": [one["group"]],
            "responses": {
                str(one.get("status", 200)): {
                    "description": "Bien",
                    "content": ({one["returns"]: {"schema": {"type": "string",
                                                              "format": "binary"}}}
                                if one.get("returns") else
                                {"application/json": {
                                    "schema": _schema(one.get("response")),
                                    "example": one.get("response")}})},
                "default": {"description": "Error",
                            "content": {"application/json": {"schema": error_schema}}},
            },
        }
        if one["scope"] == PUBLIC:
            operation["security"] = []
        elif one["scope"] != ANY:
            operation["x-scope"] = one["scope"]
        parameters = []
        for name in _path_names(one["path"]):
            parameters.append({"name": name, "in": "path", "required": True,
                               "schema": {"type": "string"}})
        for param in one.get("query", []):
            parameters.append({"name": param["name"], "in": "query",
                               "required": bool(param.get("required")),
                               "description": param.get("description", ""),
                               "schema": {"type": OPENAPI_TYPES.get(param.get("type"),
                                                                    "string")}})
        if parameters:
            operation["parameters"] = parameters
        if one.get("upload"):
            # Un archivo y sus campos de texto, en multipart.
            operation["requestBody"] = {"required": True, "content": {
                "multipart/form-data": {"schema": {"type": "object", "properties": {
                    field["name"]: ({"type": "string", "format": "binary"}
                                    if field["type"] == "archivo" else {"type": "string"})
                    for field in one.get("fields", [])}, "required": ["file"]}}}}
        elif one.get("request") is not None:
            operation["requestBody"] = {"required": True, "content": {
                one.get("content", "application/json"): {
                    "schema": _schema(one["request"]), "example": one["request"]}}}
        paths.setdefault(one["path"], {})[one["method"].lower()] = operation
    return {
        "openapi": "3.1.0",
        "info": {"title": TITLE, "version": VERSION,
                 "description": "La API de Sobreala. Guías y ejemplos en "
                                "https://sobreala.com/api/."},
        "servers": [{"url": BASE_URL}],
        "components": {"securitySchemes": {"llave": {"type": "http",
                                                     "scheme": "bearer"}}},
        "security": [{"llave": []}],
        "tags": [{"name": group["id"], "description": group["title"]} for group in GROUPS],
        "paths": paths,
    }


def _path_names(path: str) -> list[str]:
    import re

    return re.findall(r"\{([a-z_]+)\}", path)
