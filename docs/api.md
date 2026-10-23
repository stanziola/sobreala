# La API pública y el proceso en segundo plano

Octubre de 2026. Lo que hay que leer antes de tocar la API (`backend/blueprints/api/`),
la rama «API» del Dashboard (`blueprints/developers/`), el proceso en segundo
plano (`backend/worker.py`) o los webhooks. La
documentación para los clientes es otra: `sobreala.com/api/`, que sale de
`backend/api_spec.py`.

## Lo que tienes que hacer tú (una vez)

1. **El servicio `worker` en Railway.** Un servicio nuevo **del mismo
   repositorio**:
   - Start Command: `python backend/worker.py`.
   - **Sin dominio público** (Settings → Networking: nada).
   - Variables: **todas las del web, por referencia** (en Railway, «Add
     Reference» a cada variable del servicio web). La que no puede faltar es
     `SECRET_KEY`: el worker firma los enlaces de baja y los avisos con ella, y
     si no es la misma **no manda nada** (Administración → Clientes lo dice, y
     `/health` también: `worker_key: mismatch`).
   - `RAILWAY_DEPLOYMENT_DRAINING_SECONDS=30`, para que al desplegar le dé
     tiempo de terminar el correo en curso.
   - Opcionales: `SES_MAX_PER_SECOND` y `SES_MAX_PER_DAY`, que solo bajan lo
     que Amazon le da a la cuenta (`docs/envios.md`, «El ritmo de envío»), y
     `WORKER_TICK_SECONDS` (5).
2. **Cloudflare: Bot Fight Mode apagado.** En el plan gratis no se le puede
   hacer una excepción para `/api/`, y encendido, las llamadas de un servidor
   reciben un desafío en vez de JSON.
3. **Comprobar en el primer despliegue** que Railway pone la IP real al final de
   `X-Forwarded-For` (la lista de IP de cada llave depende de eso) y que
   gunicorn arranca con hilos (`--worker-class gthread`, en el `Procfile`): en
   Windows no se puede probar.

Mientras el worker no exista, **lo programado no sale**, los avisos a su
sistema no se entregan, y una campaña mandada desde el panel o la API sale solo
en su primera tanda.

## La puerta (`blueprints/api/core.py`)

- **La API es desde el plan Negocio** (octubre de 2026), en la tabla de planes y
  en el producto: lo dice la fila «Acceso a la API» de `docs/pricing.md`, que
  leen el sitio y `plans.has_api()`. Se mira el plan **vigente**
  (`accounts.current_plan()`), así que un Básico, la demostración y un plan
  vencido quedan fuera:
  - la puerta responde **403 `plan_without_api`**, después de comprobar que la
    cuenta está abierta. Sus claves no se borran: vuelven a abrir al mejorar;
  - la rama API del Dashboard (`developers.keep_out()`) enseña en cada pantalla
    solo «La API es desde el plan Negocio», con «Ver planes» y la
    documentación, y no procesa ningún formulario. Quien bajó de plan lee que
    sus claves siguen guardadas;
  - los webhooks de esa cuenta no se anotan (`webhooks.emit()`): se quedan
    guardados y callados.
- **Solo `Authorization: Bearer <llave>`.** Bajo `/api/` la sesión es una vacía
  que no se lee ni se guarda (`PanelSessions` en `app.py`), y la puerta deja
  `current_account()` en None: una galleta del navegador no cuela nada. Sin
  galletas no hace falta CSRF, y sin CORS ninguna página llama a la API.
- **Una llave en la dirección se revoca sola** y se le avisa al dueño: ya quedó
  escrita en el registro de gunicorn y en el de Cloudflare.
- **Denegado por omisión**: cada ruta se declara con `api_route(regla,
  scope=…)`. `tests/test_api_docs.py` compara esa lista con `api_spec.py` en los
  dos sentidos, y que cada `fail("código")` esté en su tabla de errores.
- **Llave mala, vencida o revocada: el mismo 401.** 20 fallos en 10 minutos por
  IP (por bloque /64 en IPv6) dan 429, solo a lo que falla.
- **La IP** es la de la conexión tras `ProxyFix`, y `CF-Connecting-IP` cuenta
  solo si la conexión viene de un rango de Cloudflare (`services/api_auth.py`,
  copiados con fecha: revisarlos de vez en cuando).
- **JSON estricto**: un campo desconocido es 422, cada valor con su tipo (un
  `{"$ne": ""}` donde va un texto nunca llega a Mongo), NaN e Infinity no son
  JSON, ids de 24 hex (otro formato, 404).
- **Límites** (`rate_state`), por cuenta: 600 por minuto en total; 120 correos,
  30 cargas de contactos y 5,000 filas, 5 plantillas (crear, cambiar el lienzo,
  cargar o bajar un ZIP), 20 fotos y 30 consultas de estadísticas por minuto.
- **Idempotencia** (`models/idempotency.py`): por cuenta, llave, método, ruta y
  `Idempotency-Key`; 24 h; «en curso» vence a los 2 minutos; un 5xx o un 429 no
  se guarda. Un correo de la API además guarda su clave en el mensaje, así que
  uno que se quedó a medias no sale dos veces aunque la respuesta guardada haya
  vencido.
- **Registro** (`api_log`, 7 días): solo lo que falló con una llave buena, hasta
  1,000 por cuenta y día, nunca el cuerpo ni la llave.

## Las llaves (`models/api_key.py`)

Solo el hash, enseñada una vez en la respuesta del POST que la crea (ni en la
sesión ni en la dirección; un número de un solo uso evita que recargar cree
otra). Hasta 10 por cuenta, solo del dueño. **Crearla pide la prueba**: la
contraseña (o un código al correo, si entró con Google o GitHub) y el código de
la app si tiene segundo factor, atada a esta cuenta y esta sesión durante 10
minutos (`blueprints/developers/routes.py`: `proved()` y `prove()`). Lo mismo al
crear un aviso, cambiar su dirección o su secreto.

**Las de prueba** (`sa_test_`) solo tienen los permisos de leer y los de enviar,
y enviar se simula: `POST /emails` devuelve el correo armado y no sale ni se
guarda nada; mandar o programar una campaña dice a cuántos saldría.

## Contactos, listas y el id de su sistema

- La carga masiva (`POST /contacts`) usa el motor de importar
  (`importer.write_batch`), con un candado por cuenta (`models/lock.py`) que
  también respeta la importación CSV.
- **`external_id`**: único por cuenta (índice parcial). Una fila que lo trae y
  existe actualiza **ese** contacto por su `_id` (su correo puede cambiar); si
  no, se busca por el correo. Un correo de un contacto con otro `external_id` es
  `external_id_conflict`.
- **Listas** (`fields.LIST`): ver `docs/contactos.md`.

## Las condiciones de una campaña (`services/audience.py`)

`POST` y `PATCH /campaigns` aceptan `filters` (`match` y `rules`, hasta 10), con
la misma validación que Masivo: un 422 dice qué regla y por qué
(`filters.rules[1]`), y `null` las quita. `GET` devuelve `filters` y
`filters_text`, y `audience` ya las cuenta, también al simular con una clave de
prueba. Una condición que dejó de valer (se borró la columna o cambió su tipo)
sale en `blocked` como `filters`, y mandar responde 409 `cannot_send`. Los
envíos de `/sends` traen la frase. La guía «Condiciones de una campaña» de
`api_spec.py` explica la forma de cada regla; el detalle, en `docs/envios.md`.

## La declaración del origen

`POST /contacts` pide `consent.attested: true` (octubre de 2026): quien carga
confirma que esas personas dieron su correo y aceptaron recibir sus mensajes.
Sin él, 422. Cada contacto guarda que lo declaró esa clave, por su nombre, y
`GET` lo devuelve en `consent.by` (`{"type": "api_key", "name": …}`, o un
usuario con su correo si entró por el Dashboard), nunca los ids internos.

## Plantillas (`services/pieces.py`)

Lo que hacen el editor y la API con un lienzo vive en `services/pieces.py`,
recibiendo la cuenta a mano (sin sesión ni `g`). La API crea, cambia, carga y
baja lienzos con la revisión completa: **por la API no hay borradores**, y un
lienzo que no cumple da 422 como siempre. Las cargadas en HTML y las
prediseñadas solo se leen, se mueven, se duplican y se borran. **300 por
cuenta**, en el panel también. Un borrador guardado en el editor sale en la
lista con `draft: true` e `issues`, y no se envía: `POST /emails` y las
campañas lo rechazan con 422 (`api_template_draft`), y una campaña cuya
plantilla vuelve a borrador dice `blocked: draft` (octubre de 2026).

## Los correos de la API (`blueprints/api/emails.py`, `sender.send_one`)

**Transaccional** o **promocional**, que elige cada correo:

| | Transaccional | Promocional |
|---|---|---|
| A quién | cualquier dirección | un contacto completo de la cuenta |
| Lo frena | rebote permanente o queja en esta cuenta, dominio que no recibe | cualquier supresión, dirección inválida, columnas sin llenar |
| Baja y `List-Unsubscribe` | no | sí |
| Marca de agua | no | la del Básico |
| Clics | no se cuentan (`ses:no-track` en cada enlace) | sí |
| Cuota, pausa, demostración, dirección postal | sí | sí |

- La cuota (y la demostración) **se aparta antes** de mandar
  (`accounts.reserve_quota`, una escritura condicional) y se devuelve si no
  salió; dos a la vez no se pasan.
- El mensaje se guarda en `pending` antes de llamar a SES y pasa a `sent` o
  `failed` (`models/message.py`, 30 días). **Sin `data` ni HTML**: el asunto se
  guarda como se escribió.
- SES lo etiqueta con `campaign = run = id del mensaje`, así los avisos
  (entregas, rebotes, quejas) llegan solos, anulan en esa cuenta y cuentan para
  la pausa automática.
- Una marca sin dato no sale: 422 `missing_data` (`fields.lacking`).
- `data` no lleva controles ni saltos de línea (ni U+2028/2029/0085): el asunto
  es una cabecera.

## El proceso en segundo plano (`worker.py`, `services/background.py`)

- **Campañas**: las que tienen `auto_send` y les llegó la hora, una tanda por
  campaña y vuelta. Guardar con fecha la pone; «ahora mismo» no; Enviar en el
  panel manda la primera tanda y la deja (el resto sale solo).
- **Nadie recibe dos veces**: el turno (`lease_by`, 10 min) se toma antes de
  `start()`, y si `start()` devuelve None no se manda nada; avanzar y cerrar
  solo escriben si el turno sigue siendo suyo; la lista se recorre por `_id`
  (`cursor_id`); quien ya tiene su `sent` en este envío se salta; SIGTERM corta
  entre un correo y otro; si SES pide esperar (Throttling), la tanda para sin
  dar a nadie por fallado.
- **Una que no puede salir** (sin cuota, en pausa, suspendida) anota por qué en
  `waiting` y se reintenta a los 15 minutos; la lista de Masivo lo dice.
- **La migración** (`campaigns.migrate_auto_send`, en `ensure_indexes`): las de
  antes con fecha futura salen solas; las que ya pasaron su hora no.
- **La huella de la llave**: el web deja la suya en `worker_state`; el worker no
  manda nada si la suya no coincide.
- **Latido** en `worker_state`; lo enseñan `/health` y Clientes.

## Los webhooks (`services/webhooks.py`, `services/safe_http.py`)

- Hasta 5 destinos por cuenta, solo desde el Dashboard (API → Webhooks), con la
  prueba.
- Se anotan **una vez por evento** (`webhook_deliveries`, único por destino y
  clave) y solo si el evento es nuevo (`events.record_new`): el aviso de SES, la
  baja y el final de una campaña. Hubo `email.downloaded`, y se quitó en octubre
  de 2026 con el registro de descargas.
- **La firma**: `Sobreala-Signature: t=…,v1=HMAC-SHA256(secreto, "t.cuerpo")`.
  El secreto sale de `SECRET_KEY`, el id del destino y su `salt`; no se guarda.
  El ejemplo de Python de la documentación se prueba contra esto.
- **Sin entrar a la red interna**: https, 443, un nombre; toda IP a la que
  resuelve tiene que ser pública (desenvolviendo mapeadas, 6to4, NAT64 y Teredo,
  y el multicast aparte); se conecta a la IP comprobada con el certificado del
  nombre; 5 s en total con un reloj; sin redirecciones; 1 KB de respuesta.
- Reintentos a 1, 5 y 30 min, 2, 6, 12 y 24 h; un fallo corre los pendientes del
  mismo destino; **72 h fallando lo apaga** y avisa al dueño. Los entrega el
  worker en su propio hilo.

## Lo que no se tocó (dicho en el reporte, a la espera)

La pausa automática mezclando las dos clases. Lo demás que estaba aquí se
cerró en octubre de 2026: la prueba del segundo factor atada a la cuenta, la
IP del panel con la regla de la API, la firma de SNS, el tope de plantillas en
el panel, los saltos de línea en los nombres y NaN o Infinity en el lienzo
(`docs/cuenta.md`, «Lo que se cerró de seguridad»).
