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
    {"id": "fuera", "title": "Lo que la API no hace",
     "paragraphs": [
         "Hay cosas que se hacen solo en el panel, porque son de una persona y no "
         "de un sistema: la contraseña y el segundo factor, los usuarios, pagar y "
         "cambiar de plan, conectar dominios y confirmar remitentes, crear llaves "
         "y avisos, y eliminar la cuenta.",
     ]},
]

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
              "a un contacto sin todas no se le envía nada.",
     "endpoints": [
         {"method": "GET", "path": "/contacts", "scope": "contacts:read",
          "title": "Listar contactos",
          "description": "De los más nuevos a los más viejos. Cada uno dice si "
                         "puede recibir (`status`: active, suppressed o invalid) y si "
                         "tiene todas sus columnas (`complete`).",
          "test": "sí",
          "query": [
              {"name": "email", "type": "texto", "description": "Uno exacto."},
              {"name": "search", "type": "texto",
               "description": "Los que empiezan así: `ana@` o `ana@coop`."},
              {"name": "tag", "type": "texto", "description": "Los que llevan esa etiqueta."},
              {"name": "limit", "type": "entero", "description": "De 1 a 100. 25 si no se dice."},
              {"name": "cursor", "type": "texto", "description": "El `next_cursor` de la página anterior."},
          ],
          "query_example": "tag=Socios&limit=50",
          "response": {"data": [{
              "id": "6531f5c2a1b2c3d4e5f60801", "email": "ana@ejemplo.com",
              "name": "Ana Pérez", "tags": ["Socios"],
              "fields": {"CIUDAD": "Santiago", "NUMERO_DE_SOCIO": "1043"},
              "status": "active", "suppression": None, "complete": True,
              "consent": {"source": "members", "note": "Lista de socios 2026",
                          "recorded_at": "2026-10-01T15:20:00Z"},
              "added_by": "api", "created_at": "2026-10-01T15:20:00Z",
              "updated_at": "2026-10-12T13:05:44Z"}],
              "next_cursor": "ZTFfwqLLPOX2BgEA"}},
         {"method": "GET", "path": "/contacts/{contact_id}", "scope": "contacts:read",
          "title": "Un contacto", "description": "El mismo que sale en la lista.",
          "test": "sí",
          "response": {"id": "6531f5c2a1b2c3d4e5f60801", "email": "ana@ejemplo.com",
                       "name": "Ana Pérez", "tags": ["Socios"],
                       "fields": {"CIUDAD": "Santiago", "NUMERO_DE_SOCIO": "1043"},
                       "status": "active", "suppression": None, "complete": True,
                       "consent": {"source": "members", "note": "Lista de socios 2026",
                                   "recorded_at": "2026-10-01T15:20:00Z"},
                       "added_by": "api", "created_at": "2026-10-01T15:20:00Z",
                       "updated_at": "2026-10-12T13:05:44Z"}},
         {"method": "POST", "path": "/contacts", "scope": "contacts:write",
          "title": "Cargar contactos",
          "description": "De 1 a 1,000 por vez. Los nuevos entran si caben en tu "
                         "plan y traen todas tus columnas; los que ya están se "
                         "actualizan (las etiquetas se suman, nunca se quitan). Cada "
                         "fila dice qué le pasó en `results`, en el orden en que "
                         "llegó: `added`, `updated` o `rejected` con su motivo "
                         "(invalid_email, duplicate, unknown_tag, unknown_field, "
                         "bad_value, incomplete, limit). Una dirección dada de baja se "
                         "guarda pero no recibe (`warning: suppressed`), y una de un "
                         "dominio que no recibe correo entra marcada (`warning: "
                         "undeliverable`). Hasta 5,000 filas por minuto.",
          "test": "no",
          "fields": [
              {"name": "contacts", "type": "lista", "required": True,
               "description": "Cada uno con `email`, y si quieres `name`, `tags` (etiquetas "
                              "que ya existen) y `fields` (tus columnas por su clave)."},
              {"name": "consent", "type": "objeto", "required": True,
               "description": "De dónde salieron: `source` es own_form (tu formulario), "
                              "members (socios), customers (clientes), event (un evento) u "
                              "other; `note`, hasta 300 caracteres. Se guarda en cada "
                              "contacto nuevo, y es lo que enseñas si alguien reclama."},
              {"name": "tags", "type": "lista de textos",
               "description": "Etiquetas para todos los de esta carga."},
          ],
          "request": {"consent": {"source": "customers", "note": "Clientes de la tienda"},
                      "tags": ["Clientes"],
                      "contacts": [{"email": "ana@ejemplo.com", "name": "Ana Pérez",
                                    "fields": {"CIUDAD": "Santiago"}},
                                   {"email": "luis@ejemplo", "name": "Luis"}]},
          "response": {"added": 1, "updated": 0, "rejected": 1, "results": [
              {"index": 0, "email": "ana@ejemplo.com", "result": "added"},
              {"index": 1, "email": "luis@ejemplo", "result": "rejected",
               "reason": "invalid_email"}]}},
         {"method": "PATCH", "path": "/contacts/{contact_id}", "scope": "contacts:write",
          "title": "Cambiar un contacto",
          "description": "Solo lo que mandes: `email`, `name`, `tags` (reemplazan las que "
                         "tenía) y `fields` (se mezclan con las que tenía). Como en el "
                         "panel, queda con todas sus columnas llenas. De dónde salió y "
                         "cuándo entró no se cambian.",
          "test": "no",
          "fields": [
              {"name": "email", "type": "texto", "description": "Si ya es de otro contacto: 409."},
              {"name": "name", "type": "texto", "description": "Hasta 120 caracteres."},
              {"name": "tags", "type": "lista de textos", "description": "Etiquetas que ya existen."},
              {"name": "fields", "type": "objeto", "description": "Tus columnas por su clave."},
          ],
          "request": {"tags": ["Socios", "Asamblea 2026"], "fields": {"CIUDAD": "Las Palmas"}},
          "response": {"id": "6531f5c2a1b2c3d4e5f60801", "email": "ana@ejemplo.com",
                       "name": "Ana Pérez", "tags": ["Socios", "Asamblea 2026"],
                       "fields": {"CIUDAD": "Las Palmas", "NUMERO_DE_SOCIO": "1043"},
                       "status": "active", "suppression": None, "complete": True,
                       "consent": None, "added_by": "api",
                       "created_at": "2026-10-01T15:20:00Z",
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
                         "llena.",
          "test": "sí",
          "response": {"data": [{"key": "CIUDAD", "label": "Ciudad", "type": "text",
                                 "filled": 790}], "limit": 5}},
         {"method": "POST", "path": "/fields", "scope": "contacts:write",
          "title": "Crear una columna",
          "description": "La clave sale del nombre: «Número de socio» es NUMERO_DE_SOCIO. "
                         "Recién creada, todos tus contactos quedan incompletos hasta "
                         "que la tengan.",
          "test": "no", "status": 201,
          "fields": [{"name": "label", "type": "texto", "required": True,
                      "description": "Hasta 40 caracteres."},
                     {"name": "type", "type": "texto", "required": True,
                      "description": "text, number, date o yesno."}],
          "request": {"label": "Número de socio", "type": "text"},
          "response": {"key": "NUMERO_DE_SOCIO", "label": "Número de socio",
                       "type": "text", "filled": 0}},
         {"method": "PATCH", "path": "/fields/{key}", "scope": "contacts:write",
          "title": "Cambiar el tipo de una columna",
          "description": "Solo el tipo, y solo si todo lo escrito encaja en el nuevo: si "
                         "no, 409 dice cuántos contactos lo impiden. El nombre no se "
                         "cambia, porque es lo que nombran tus plantillas.",
          "test": "no",
          "fields": [{"name": "type", "type": "texto", "required": True,
                      "description": "text, number, date o yesno."}],
          "request": {"type": "number"},
          "response": {"key": "NUMERO_DE_SOCIO", "label": "Número de socio",
                       "type": "number", "filled": 790}},
         {"method": "DELETE", "path": "/fields/{key}", "scope": "contacts:write",
          "title": "Borrar una columna",
          "description": "Y lo que los contactos tenían escrito en ella.",
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
                    "content": {"application/json": {
                        "schema": _schema(one.get("response")),
                        "example": one.get("response")}}},
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
                               "schema": {"type": param.get("type", "string")}})
        if parameters:
            operation["parameters"] = parameters
        if one.get("request") is not None:
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
