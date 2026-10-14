# Envío de campañas y lo que cuenta Amazon

Detalle que vivía en `CLAUDE.md`, movido tal cual para que ese archivo
cupiera en el límite. Lo esencial (las reglas, las convenciones y el
resumen de cada parte) sigue allí; esto es lo que hay que leer antes de
tocar esta parte.

## Envío

**Cada cliente elige de quién salen sus campañas**, en Enviar correos →
Remitente (`/campaigns/sender`, `blueprints/campaigns/`), y vale para todas sus
campañas. La cambia solo el dueño; un usuario con permiso de enviar la ve.

| Cliente | De | Responder a |
|---|---|---|
| Sin dominio propio | `Tu Empresa <usuario@envios.sobreala.com>`, con el usuario que eligió | La dirección que confirmó con un código, o el correo del dueño |
| Con su dominio verificado | `Tu Empresa <boletin@tuempresa.com>`, la que elija de su dominio | Igual; una de su propio dominio no pide código |
| Sin usuario elegido | **No sale**: `sender.blocked()` dice `sender` | — |

- **Una campaña nunca sale de `notifications@sobreala.com`**, que es solo del
  correo del sistema. `sender.sender_email()` no tiene esa salida: así una
  lista mala de un cliente no puede llevarse a spam los códigos de
  confirmación.
- **`SENDING_DOMAIN`** (por omisión `envios.sobreala.com`) es el subdominio de
  quien no tiene dominio propio. Lo comparten todos ellos, y con él su
  reputación ante Gmail; los protegen la demostración o el pago que abren cada
  cuenta, y la pausa automática, que todavía no existe. Hubo además una
  habilitación a mano antes del primer envío, y se quitó en octubre de 2026
  (ver «Abrir la cuenta» en `docs/cuenta.md`).
- **El usuario es único entre cuentas**, y el dominio también: lo garantizan dos
  índices únicos parciales sobre `sender.handle` y `sender.domain`. Los
  reservados (`info`, `soporte`, `notifications`…) no se pueden elegir.
- **El dominio propio lo conecta el cliente solo.** El panel crea su identidad
  en SES por la API v2 (`services/ses_identity.py`, con Easy DKIM), le enseña
  los tres CNAME para su DNS (también como archivo de zona para **importarlos
  en Cloudflare de una vez**, `/campaigns/sender/records.txt`, sin proxy con
  `cf_tags=cf-proxied:false`), y consulta si ya está verificada al abrir la
  pantalla y con «Comprobar ahora»: no hay proceso que lo mire solo. Quitarlo
  borra la identidad de SES. Los de correo gratis (gmail.com y compañía) no se
  pueden conectar, porque nadie puede ponerles registros. Sin MAIL FROM propio
  todavía: DKIM ya alinea DMARC.
- **El «Responder a» se confirma con un código** a esa dirección
  (`tokens.REPLY_TO`, el mismo mecanismo que cambiar el correo de la cuenta),
  para que nadie ponga la de un tercero y le lleguen las respuestas de toda una
  lista. Hasta que entra, las respuestas siguen yendo a la de antes.
- La ficha del administrador lo enseña, de solo lectura.

Los de `envios.sobreala.com` comparten reputación, y las defensas automáticas
son su protección:

| Métrica de una cuenta | Acción automática |
|---|---|
| Rebotes > 3% | Pausa de envío y aviso (AWS actúa a 5%) |
| Quejas > 0.05% | Pausa de envío (Gmail y Yahoo actúan a 0.1%) |
| Primera campaña | Tope reducido las primeras 48h, sin importar el plan |

Usar **tenants de SES** para aislar reputación y supresión por cliente.

Requisitos de remitente masivo que aplican a Sobreala (no a sus clientes), al
pasar de 5,000 correos diarios sumando todos: DMARC publicado en
`sobreala.com`, SPF y DKIM, baja de un clic procesada en menos de 2 días, y
tasa de quejas agregada bajo 0.1%.

## Flujo de campaña

```
1. Armar la plantilla en el lienzo  ó  cargar el ZIP de uno
2. Escribir asunto y contenido
3. Elegir la lista destinataria
4. Vista previa + enviar correo de prueba a su propia dirección
5. Enviar ahora  ó  programar fecha y hora
```

Los envíos programados, las importaciones grandes y la reanudación de campañas
pausadas corren en un **proceso en segundo plano**, no dentro del request.

### HTML subido por el cliente

Ya no se sube (septiembre de 2026): ver `designs`, más arriba. Las que se
cargaron antes se siguen editando y enviando.

### `campaigns`
**Un documento por campaña, no por envío**: el asunto, la pieza, la lista, la
hora y **hasta dónde llegó**. Estados: `scheduled` → `sending` → `sent`.

**Una campaña se guarda y se manda las veces que haga falta.** Un boletín
mensual se arma una vez y sale doce; un recordatorio de asamblea, cada año.
`restart()` devuelve los contadores a cero y la deja esperando otra vez, con el
estado dentro de la consulta que escribe para que dos clics no arranquen dos
envíos. **Sale a la lista entera otra vez**, también a quien ya la recibió —que
es lo que se le pide a un boletín—, los suprimidos se siguen saltando por la
regla 1, y gasta cuota otra vez porque son correos que salen.

**A qué etiquetas sale vive en `tags`**, y vacío es toda la lista. Las
campañas de antes llevaban una sola en un campo suelto; `campaigns.tags_of()`
lee las dos formas, así que no hubo nada que migrar, y guardar una campaña vieja
la pasa al campo nuevo.

**La posición es lo que hace que esto se pueda cortar.** El envío sale por tandas
—cien destinatarios por vuelta— porque corre dentro de la petición y no hay
proceso en segundo plano: cada tanda anota dónde quedó, así que cortar a la
mitad no le manda a nadie dos veces, y la pantalla ofrece seguir. El día que
exista ese proceso, llama a `sender.run()` en bucle y no cambia nada más. Es
también lo que va a permitir pausar por cuota y retomar.

**Editar y borrar solo mientras no esté saliendo**, y el estado va dentro de la
consulta que escribe: entre mirar y guardar hay sitio para que el envío
arranque. Que le haya pasado la hora no la cierra —nadie la despertó—, así que
sigue esperando con su botón de mandar. Y una que ya salió tampoco queda
cerrada: es la campaña guardada, y corregirle el asunto para la próxima vez es
justo para lo que se guarda. Lo que ya salió no cambia con ella, porque vive
aparte.

**Lo programado no sale solo.** No hay quién lo despierte: cuando pasa su hora, la
pantalla la enseña como lista para salir.

### `campaign_runs`
Un documento **cada vez que una campaña sale**: la cuenta, la campaña, el asunto
y la lista copiados, cuándo empezó y terminó, cuántos salieron, se saltaron y
fallaron, y los errores. Lo escribe `campaigns.finish()`, que es por donde pasa
toda vuelta que termina.

Aparte y no en un arreglo dentro de la campaña por tres razones: **no hay
tope** —treinta envíos son treinta líneas—, el documento de la campaña no crece
sin límite, y el asunto copiado hace que el historial siga contando la verdad
aunque después se corrija o se borre la campaña. **Borrar una campaña no borra
sus envíos**: lo que salió, salió.

Es lo que dibuja «Campañas enviadas» en `/campaigns` y las líneas de correo de la
Actividad de una ficha, que por eso son una por envío y no una por campaña.

**Su `_id` nace al arrancar, no al terminar.** `campaigns.start()` lo genera y
lo deja en `run_id` de la campaña, cada correo sale etiquetado con él, y
`finish()` escribe la línea con ese mismo id. Hace falta así porque los avisos
de SES llegan mientras el envío todavía sale, y tienen que poder decir a qué
envío pertenecen.

### `events`
Un registro por evento de SES (enviado, entregado, rebote, queja, apertura,
clic), con su cuenta, su campaña y cuándo pasó. Es lo que más crece: ~3 eventos
por correo, ~200 bytes cada uno.
**Retención: 12 meses en detalle, después solo totales por campaña.**

**La llenan dos sitios**: el envío de campañas, con un `sent` por correo que
sale, y el aviso de SES (ver «Lo que cuenta Amazon»), con lo demás. **Un evento
por envío, persona y tipo** (`events.record()`, con `$setOnInsert`): quien abre
el mismo correo mil veces deja una apertura, la primera, y un clic en dos
enlaces del mismo correo es un clic. Así las cifras no se inflan y la colección
no crece con cada reapertura. Cada evento
lleva el `run_id` del envío y la dirección normalizada, que es lo que permite
contar **personas y no eventos**: quien abre tres veces cuenta una. Lo hace
`events.counts_by_run()`, una consulta para toda la lista de «Campañas
enviadas». `models/event.py` lee también la serie por tramo de tiempo y los
totales del periodo que dibuja Estadísticas.

## Enviar correos

`/campaigns`, debajo de Estadísticas y **solo para clientes**: se marcan las
etiquetas a las que va —ninguna es toda la lista—, una pieza guardada y el
asunto, y sale ahora o queda programada.

**Se le puede escribir a varias etiquetas a la vez**, y le llega a quien lleve
cualquiera de ellas. Que nadie reciba dos veces no hubo que construirlo: un
contacto es **un solo documento** con sus etiquetas dentro, así que la consulta
por varias lo devuelve una vez aunque lleve tres de las marcadas. Es la garantía
que `docs/pricing.md` promete, y hasta que esto existió era cierta solo porque
no se podía elegir más de una. Arriba, siempre, **qué le falta a la cuenta para que un envío salga
de verdad**; armar y programar se puede igual, mandar no.

La pantalla tiene **dos listas y son dos cosas distintas**: «Campañas
guardadas», que se corrigen y se vuelven a mandar, y «Campañas enviadas», una
línea por cada vez que salió algo, leída de `campaign_runs`. Una campaña
mandada seis veces es una fila arriba y seis abajo.

**Cada envío tiene su «Detalles»** (`/campaigns/sent/<id>`): una fila por
persona a la que le salió, con si le llegó (lo último que contó Amazon:
entregado, rebotó, rechazado o spam), cuándo lo abrió y cuándo pulsó por
primera vez. Se filtra por etiqueta y por **qué pasó** (entregados, rebotaron,
rechazados, spam, lo abrieron, pulsaron, no lo abrieron: `events.OUTCOMES`), se
busca por correo o nombre, y va de a 50. «Rebotó» es lo mismo que enseña la
columna: quien rebotó y después se quejó sale como spam, no en los dos. Los filtros se resuelven primero en Contactos (`contacts.emails_matching()`)
y solo después se miran los eventos de esas personas (`events.recipients()`),
para no traer una lista grande entera. Las etiquetas y el nombre son los de hoy;
quien ya no está en Contactos sale con su dirección y lo dice. Es la lista de
direcciones de **su propia** cuenta: lo que la ficha del administrador no enseña
sigue sin enseñarse.

**El formulario no lleva la ayuda de las columnas.** Escribir `*|NOMBRE|*` en el
asunto sigue funcionando, pero los botones de las marcas viven en Plantillas.

**Mandar pasa siempre por una pantalla que pregunta.** El botón de la lista es
un enlace a `GET /campaigns/<id>/send`, que no manda nada: dice el asunto, a qué
lista, **a cuántos contactos**, con qué pieza y cuánta cuota queda, y si ya
salió antes avisa de que le va a llegar otra vez a todos, también a quien ya la
recibió. El que manda es el POST. Es el mismo reparto que exportar contactos, y
aquí pesa más: un correo que salió no se puede recoger.

**Para mandar hace falta un plan con cuota del mes por gastar**, además de la
dirección postal y el remitente, y **no estar limitada** (`sender.blocked()`,
que lo mira antes de armar un solo correo; `limited` lo pone el administrador
mientras falte verificar la identificación y la dirección, ver «Limitar una
cuenta» en `docs/cuenta.md`). Hubo una segunda puerta, la habilitación de envío a mano, y se
quitó en octubre de 2026: quien paga entra con todo y envía de una vez, y la
mirada de una persona pasó a la demostración que abre la cuenta.

**`services/sender.py` es el único sitio que le escribe a un contacto de un
cliente.** Los del sistema salen por `mailer.py`, que es otro camino con otras
reglas: aquellos no llevan baja ni marca de agua (regla 8) y estos las llevan
siempre (reglas 3 y 4). Las campañas **no pasan por `mail_log`**, que es del
correo del sistema; lo suyo se cuenta en su propio documento.

### La baja, que es la regla 3

Cada destinatario recibe **su** enlace, distinto, inyectado al armar el correo y
no guardado en la pieza, para que el cliente no lo pueda quitar. Va también en la
cabecera `List-Unsubscribe`, con `List-Unsubscribe-Post`, que es lo que hace que
Gmail enseñe su propio botón de cancelar suscripción.

**Sin escribir nada al enviar**: el enlace lleva el identificador del contacto y
una firma con la llave del servidor (`services/unsubscribe.py`). Un documento por
destinatario multiplicaría la base por el tamaño de cada lista para conseguir lo
mismo.

**Abrir el enlace no da de baja a nadie**, y eso no es un descuido: los escáneres
de correo abren los enlaces de lo que revisan, y si bastara con abrirlo, la lista
de un cliente se vaciaría sola. Lo que da de baja es el POST —el mismo que manda
Gmail en su «un clic»—, y por eso ese POST **no lleva testigo**: lo que autoriza
es la firma del enlace. La baja queda con motivo `unsubscribe`, que el cliente no
puede levantar.

**La cabecera no puede ir codificada.** Una dirección no tiene espacios por donde
partirla, así que con el límite de 78 caracteres Python la parte codificándola en
RFC 2047 y el botón del buzón deja de entenderla. Por eso el mensaje se arma con
una política de líneas largas.

### De quién sale

Del remitente que eligió el cliente: ver «Envío», arriba. Lo deciden
`sender.sender_email()` y `sender.reply_to()`, y nada más.

Y SES sigue en modo de prueba: **solo entrega a direcciones verificadas**. Lo que
responda por cada destinatario se guarda en la campaña y la pantalla lo enseña.

### Lo que todavía no hace

Pausar sola una cuenta que pasa de los umbrales, reanudar sola una campaña, y
acumular los correos no usados al mes siguiente.

## Lo que cuenta Amazon

`POST /webhooks/ses/<secreto>`, en `blueprints/webhooks/`. SES avisa por SNS de
cada entrega, rebote, queja, rechazo, apertura y clic, y
`services/ses_events.py` decide a dónde va cada uno. Lo que hay que hacer en la
consola de Amazon y en Cloudflare está paso a paso en `docs/ses.md`.

**Lo que lo autoriza es el secreto de la dirección** (`SES_WEBHOOK_SECRET`):
uno que no cuadra, o ninguno configurado, responde 404. Con `SES_TOPIC_ARN`
puesto, un aviso de otro tema se descarta. **La firma de SNS no se comprueba**:
pide RSA contra un certificado descargado, y con el secreto por HTTPS y el
filtro del tema alcanza. Es una decisión, no un olvido. La dirección para
confirmar la suscripción **solo se visita si es de `sns.<región>.amazonaws.com`**,
porque ese campo lo escribe quien manda el cuerpo.

Un aviso que no se entiende se contesta **200**, o SNS lo reintentaría durante
horas. Uno que se entiende y no se pudo guardar, **500**, para que sí lo
reintente.

**De quién es un aviso lo dicen las etiquetas del correo**, nunca la dirección.
Cada correo de campaña sale con `account`, `campaign` y `run` en la cabecera
`X-SES-MESSAGE-TAGS`, y SES las devuelve dentro. La misma dirección puede estar
en las listas de tres clientes, y anularla en las tres por el rebote de una
sería anular por cuenta ajena. Lo que no trae esas etiquetas es un correo del
sistema, y va a su fila de `mail_log`.

| Aviso | De una campaña | Del sistema |
|---|---|---|
| Entrega | evento `delivery` | `delivered` |
| Rebote permanente | evento `bounce` y **se anula en esa cuenta** (`hard_bounce`) | `bounced` |
| Rebote pasajero | evento `bounce`, sin anular | `soft_bounced` |
| Queja | evento `complaint` y **se anula en esa cuenta** (`complaint`) | `complained` |
| Rechazo | evento `reject` | `rejected` |
| Apertura, clic | evento `open` o `click` | no se miden |

**Dos conjuntos de configuración**: `SES_CONFIGURATION_SET` para campañas, con
aperturas y clics, y `SES_TRANSACTIONAL_CONFIGURATION_SET` para el sistema, sin
ellos: a un código de confirmación no se le mide nada. **El enlace de baja
lleva `ses:no-track`**, para que SES no lo reescriba al contar clics: es el que
tiene que funcionar siempre.

**«Entregado» es que el otro servidor lo aceptó**, no que esté en la bandeja. Si
después lo mandó a spam o a cuarentena no se lo cuenta a nadie, y Microsoft 365
(la UTP) pone en cuarentena sin rebotar. Las pantallas lo dicen, para que nadie
lea «entregado» como «lo vio».

**La pausa automática por umbrales no está.** Se decidió esperar a tener cifras
reales antes de poner el corte.
