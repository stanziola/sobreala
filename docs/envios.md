# Envío de campañas y lo que cuenta Amazon

Detalle que vivía en `CLAUDE.md`, movido tal cual para que ese archivo
cupiera en el límite. Lo esencial (las reglas, las convenciones y el
resumen de cada parte) sigue allí; esto es lo que hay que leer antes de
tocar esta parte.

## Envío

**Cada cliente elige de quién salen sus campañas**, en Configuración de envío →
Remitente (`/campaigns/sender`, `blueprints/campaigns/`). La cambia solo el
dueño; un usuario con permiso de enviar la ve.

**Desde octubre de 2026 hay varios de cada uno, y cada plantilla elige los
suyos** (`account.sender`, en `models/account.py`):

- **Remitentes** (`froms`): cada uno es **un nombre y una dirección**. El
  nombre es el que se ve en el buzón (vacío es el de la empresa). La dirección
  es la de la cuenta en `envios.sobreala.com` (ahí solo cambia el nombre, y
  puede haber varios con nombres distintos) o **cualquiera de un dominio
  propio verificado** (`ventas@`, `cobros@`…). Hasta 20, y uno es el
  **predeterminado**.
- **«Responder a»** (`reply_tos`): hasta 10, cada uno confirmado, y uno
  predeterminado. Sin ninguno, las respuestas van al correo del dueño.
- **Dominios propios** (`domains`): hasta 5, cada uno con su estado y sus
  registros. Únicos entre cuentas por un índice de varias claves
  (`uniq_sender_domains`).
- **La plantilla elige** en sus editores (los tres: Lienzo, HTML y
  prediseñadas) **«Sale de»** y **«Responder a»** (`designs.send_from` y
  `designs.reply_to`); sin elegir, o si lo elegido ya no existe o su dominio
  no está verificado, salen los predeterminados (`sender.remitente()` y
  `sender.reply_to()`). **Lo escrito**, que no tiene plantilla, sale con los
  predeterminados.
- **Quitar** un remitente, un «Responder a» o un dominio lo borra también de
  las plantillas que lo usaban (`designs.forget_sending()`), que vuelven al
  predeterminado. Quitar un dominio se lleva sus remitentes y los «Responder
  a» de ese dominio, y si el predeterminado era uno de ellos, pasa a serlo el
  de `envios.sobreala.com`.
- **La pantalla que pregunta antes de mandar dice de quién sale y a dónde se
  responde** esa campaña: con la elección por plantilla, ahí se comprueba.
- **Hasta octubre de 2026 había uno solo de cada uno** (`sender.domain`,
  `domain_local` y `reply_to`). `ensure_indexes()` los pasa a las listas una
  vez (`accounts.migrate_sender()`): el dominio verificado con su dirección
  queda de remitente predeterminado, porque de ahí salían sus campañas.

| Cliente | De | Responder a |
|---|---|---|
| Sin dominio propio | `Tu Empresa <usuario@envios.sobreala.com>`, con el usuario que eligió, y el nombre de cada remitente | Las direcciones que confirmó con un código, o el correo del dueño |
| Con dominios verificados | Además, `Ventas <ventas@tuempresa.com>`: las que agregue de cada dominio | Igual; una de sus propios dominios no pide código |
| Sin usuario ni remitente que pueda salir | **No sale**: `sender.blocked()` dice `sender` | — |

- **Una campaña nunca sale de `notifications@sobreala.com`**, que es solo del
  correo del sistema. `sender.sender_email()` no tiene esa salida: así una
  lista mala de un cliente no puede llevarse a spam los códigos de
  confirmación.
- **`SENDING_DOMAIN`** (por omisión `envios.sobreala.com`) es el subdominio de
  quien no tiene dominio propio. Lo comparten todos ellos, y con él su
  reputación ante Gmail; los protegen la demostración o el pago que abren cada
  cuenta, y la pausa automática (abajo). Hubo además una
  habilitación a mano antes del primer envío, y se quitó en octubre de 2026
  (ver «Abrir la cuenta» en `docs/cuenta.md`).
- **El usuario es único entre cuentas**, y cada dominio también: lo garantizan
  dos índices únicos parciales, sobre `sender.handle` y sobre
  `sender.domains.name` (de varias claves: ninguna otra cuenta repite uno de la
  lista). Los reservados (`info`, `soporte`, `notifications`…) no se pueden
  elegir.
- **Cada dominio propio lo conecta el cliente solo.** El panel crea su identidad
  en SES por la API v2 (`services/ses_identity.py`, con Easy DKIM), le enseña
  los tres CNAME para su DNS (también como archivo de zona para **importarlos
  de una vez en el proveedor de DNS que lo permita**, Cloudflare, Route 53 y
  otros, `/campaigns/sender/records/<dominio>.txt`; desde octubre de 2026 ni el
  botón ni el archivo dan por hecho Cloudflare, que no todos usan. Cada CNAME
  lleva al final el comentario `cf_tags=cf-proxied:false`, que los demás no
  leen y que a Cloudflare le dice que entren sin proxy), y consulta si ya está
  verificado al abrir la pantalla (cada uno que falte) y con «Comprobar
  ahora»: no hay proceso que lo mire solo. Quitarlo borra la identidad de SES, y eliminar la
  cuenta borra la de todos. Los de correo gratis (gmail.com y compañía) no se
  pueden conectar, porque nadie puede ponerles registros. **Con su propio MAIL
  FROM** (octubre de 2026): `envios.<dominio>`, con un MX y un SPF más (cinco
  registros en total), que es lo que Gmail enseña en «enviado por»; sin él
  decía `us-east-2.amazonses.com`. Mientras falten esos dos se envía igual con
  el de Amazon (`USE_DEFAULT_VALUE`), porque DKIM ya alinea DMARC; Remitente
  dice «Enviado por: listo / esperando los registros». A un dominio conectado
  antes se le pide al abrir esa pantalla (`ses_identity.mail_from()`). El de
  `envios.sobreala.com` se pone a mano: `docs/ses.md`, paso 6b. **Y DMARC**
  (octubre de 2026): Amazon lo marca como recomendación de impacto alto y Gmail
  y Yahoo lo piden a quien envía en cantidad, pero no lo puede poner SES.
  Remitente lo consulta en el DNS del dominio (`ses_identity.dmarc_state()`, un
  minuto en memoria) y dice «Publicado», «Falta» o «Sin comprobar»; si falta,
  enseña el TXT de `_dmarc.<dominio>` con `v=DMARC1; p=none;` (solo observa) y
  lo mete en el archivo de zona. **Si ya tiene uno no se pide otro**, y si no se
  pudo saber se enseña con el aviso pero no va en el archivo: dos registros
  DMARC se anulan. BIMI (el logo en la bandeja) no se pide: necesita DMARC
  estricto y un certificado de marca.
- **Cada «Responder a» se confirma con un código** a esa dirección
  (`tokens.REPLY_TO`, el mismo mecanismo que cambiar el correo de la cuenta),
  para que nadie ponga la de un tercero y le lleguen las respuestas de toda una
  lista; las de un dominio propio verificado no lo piden. Espera uno a la vez
  (`reply_to_pending`), y hasta que entra, las respuestas siguen yendo a donde
  iban. El primero que se confirma queda de predeterminado.
- La ficha del administrador lo enseña todo, de solo lectura.

Los de `envios.sobreala.com` comparten reputación, y las defensas automáticas
son su protección:

| Métrica de una cuenta | Acción automática |
|---|---|
| Rebotes permanentes > 3 %, desde 100 enviados | Pausa de envío y aviso (AWS revisa a 5 %) |
| Quejas > 0.1 %, desde 1,000 enviados | Pausa de envío y aviso (AWS revisa a 0.1 %) |
| Primera campaña | Tope reducido las primeras 48h, sin importar el plan |

### La pausa automática (octubre de 2026)

`services/reputation.py`. **Amazon mide la cuenta entera de Sobreala**: con 5 %
de rebotes la pone en revisión, y con eso se para el envío de todos. El panel
mide a cada cliente por su lado y lo pausa antes.

- **Qué cuenta:** los últimos 30 días de esa cuenta. Enviados son los eventos
  `sent`; rebotes y quejas, las supresiones que puso el aviso de SES
  (`source="ses"`, `hard_bounce` o `complaint`), así que cuentan personas, y un
  rebote pasajero (buzón lleno) no pausa a nadie.
- **El volumen mínimo** es para que un envío chico no se pause por una sola
  persona: con veinte correos, un rebote ya es un 5 %. Por eso las quejas
  empiezan a contar desde 1,000 y no desde 100: una sola persona que pulsa «es
  spam» en un envío de 500 sería un 0.2 %. Se decidió en octubre de 2026 en vez
  del 0.05 % que estaba escrito, que pausaba por una queja en 2,000.
- **Cuándo se mira:** el aviso de SES llama a `check()` después de cada rebote
  permanente o queja nueva. No hay proceso que lo mire solo, y no hace falta: lo
  que mueve la cifra es justo ese aviso.
- **Qué hace:** es un límite más (`accounts.pause()`, motivos `bounces` y
  `complaints`): entra, prepara y paga, pero no envía (`sender.blocked()` dice
  `paused`). Una campaña a medias para en la tanda siguiente. La nota del límite
  guarda las cifras que lo dispararon, y queda en `admin_events` sin
  administrador. Pisa un límite de verificación, pero no otra pausa: los rebotes
  siguen llegando de a uno y solo el primero que pasa el umbral pausa y avisa.
- **Avisa** al cliente (`notices.paused()`, sin interruptor: qué pasó, con sus
  cifras, qué revisar y a quién escribir) y a quien administra
  (`notices.pause_to_admins()`, con su interruptor «El panel pausó a un
  cliente»).
- **Solo la quita el administrador**, desde la ficha («Quitar el límite»), con
  su nota. Aprobar la verificación no la levanta: eso solo quita el límite de
  verificación.

Los **tenants de SES** (reputación y supresión aisladas por cliente ante
Amazon) quedaron para más adelante: ver «Pendientes de decisión» en `CLAUDE.md`.

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

Los envíos programados y el resto de una campaña que empezó a salir los manda
el **proceso en segundo plano** (`backend/worker.py`, octubre de 2026; ver
`docs/api.md`). La importación CSV todavía corre dentro de la petición.

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

**Hasta dónde llegó es lo que hace que esto se pueda cortar.** El envío sale por
tandas de cien: la primera dentro de la petición que pulsa Enviar, y las demás
desde el proceso en segundo plano, que llama a `sender.run()` en bucle con su
**turno** (`lease_by`): avanzar y cerrar solo escriben si el turno sigue siendo
suyo, y si `start()` dice que otro la arrancó primero no se manda nada. Desde
octubre de 2026 la lista se recorre **por `_id`** (`cursor_id`, el último que se
procesó) y no por posición, así borrar contactos a mitad de camino no salta a
nadie; y antes de cada tanda se mira quién ya tiene su `sent` de este envío. La
cuota se **aparta antes** de mandar y lo que no salió vuelve. Una que no puede
salir (sin cuota, en pausa) anota por qué en `waiting` y se reintenta sola a los
15 minutos.

**Editar y borrar solo mientras no esté saliendo**, y el estado va dentro de la
consulta que escribe: entre mirar y guardar hay sitio para que el envío
arranque. Que le haya pasado la hora no la cierra —nadie la despertó—, así que
sigue esperando con su botón de mandar. Y una que ya salió tampoco queda
cerrada: es la campaña guardada, y corregirle el asunto para la próxima vez es
justo para lo que se guarda. Lo que ya salió no cambia con ella, porque vive
aparte.

**Lo programado sale solo** (octubre de 2026): guardar con fecha pone
`auto_send`, y el proceso en segundo plano la manda a su hora. «Ahora mismo»
sigue pidiendo Enviar y su pantalla que pregunta. Una que ya salió y se edita con
otra fecha no se rearma sola: se vuelve a mandar con Enviar o con `schedule` por
la API. Al desplegar el worker, las de antes con fecha futura pasaron a salir
solas y las que ya habían pasado su hora no (`campaigns.migrate_auto_send`).

### Las condiciones (octubre de 2026)

**Además de sus etiquetas, una campaña puede salir solo a quien cumpla unas
condiciones sobre sus columnas**: un monto mayor que 100, una ciudad que empieza
con «San», un vencimiento antes del 1 de noviembre, un sí; y de una lista (las
transacciones de un socio), cuántas filas tiene, si alguna fila cumple algo con
uno de sus datos o la suma de un dato numérico. Se cumplen **todas** o
**alguna**, hasta 10, y van en `campaigns.filters` (`match` y `rules`) con su
frase en `filters_text`. Etiquetas y condiciones van juntas: «quien lleve alguna
de estas etiquetas **y** cumpla las condiciones».

**Todo pasa por `services/audience.py`**: `parse()` valida contra las columnas
de la cuenta (la clave existe, el operador es de su tipo, el valor pasa por
`fields.parse` y cada parte de la regla llega con su tipo), `query()` arma la
consulta que se suma al `$and` de `contact._matching()`, y `describe()` escribe
la frase. Las usan el panel, la cuenta en vivo, el envío por tandas, el proceso
en segundo plano y la API, así que no pueden contar distinto.

**Cómo compara cada tipo**, porque todo se guarda como texto: las fechas como
`AAAA-MM-DD`, que ordena bien; los números con `$expr` y `$convert` a decimal,
no a double (0.1 + 0.2 da 0.3 exacto), con el valor de la regla redondeado a
las 34 cifras que caben; el texto con una expresión escapada y sin mayúsculas,
así un punto es un punto. **Un valor vacío, que falta o mal escrito no cumple
nunca**, ni «menor que» ni «distinto de»: en Mongo lo que falta es menor que
cualquier número y `$ne` lo acepta, así que cada comparación lleva su guarda.
Un contacto sin la lista tiene 0 filas y suma 0.

**Una condición que dejó de valer frena la campaña, no la agranda.** Si después
de guardarla se borra la columna, cambia su tipo o la lista pierde el dato,
`query()` lanza `Stale`: la pantalla de confirmar lo dice y no ofrece mandar,
`sender.run()` devuelve `blocked: ["filters"]`, el proceso en segundo plano la
deja esperando con ese motivo (`waiting`) y la API responde 409. Saltarla en
silencio la mandaría a más gente de la elegida.

**Una plantilla que vuelve a borrador también la frena** (octubre de 2026): si
después de elegirla se guarda en el lienzo sin cumplir las reglas,
`sender.run()` devuelve `blocked: ["draft"]` y la campaña espera, igual que con
una condición vieja; la pantalla de confirmar lo dice y no ofrece mandar.
Corregida y guardada, sale (`docs/plantillas.md`, «Solo se envía lo que…»).

**La pantalla funciona sin JavaScript**: salen las guardadas y una fila vacía,
«Agregar condición» y «Quitar» son botones del formulario que lo vuelven a
dibujar sin guardar (`rule_action`), y el operador lista todos, agrupados por
tipo; el servidor dice si uno no va con su columna. Con JavaScript cada fila
ofrece solo los de su columna, el campo del valor es de su tipo, y **«a cuántos
saldría» se pide mientras se elige** (`POST /campaigns/audience`, con CSRF, 60
por minuto y **el permiso de enviar**: con solo mirar se podría estrechar la
cuenta hasta adivinar el monto de cada contacto). Un botón escondido al
principio del formulario hace que Intro guarde, en vez de pulsar «Quitar» de la
primera fila. La cifra cuenta, como la de confirmar, a los suprimidos y a las
direcciones inválidas, que al enviar se saltan.

**La frase se copia a cada envío** (`campaign_runs.filters_text`), como el
asunto: la columna se puede borrar después y el historial tiene que seguir
leyéndose. La enseñan Masivo, confirmar, Enviados y el detalle de un envío;
Estadísticas no enseña la audiencia, y no se le agregó.

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

Es lo que dibuja Enviados (`/campaigns/sent`) y las líneas de correo de la
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
`events.counts_by_run()`, una consulta para toda la lista de Enviados.
`models/event.py` lee también la serie por tramo de tiempo y los
totales del periodo que dibuja Estadísticas.

## Correos

Desde octubre de 2026 es una rama del Dashboard (ver `docs/panel.md`):
**Correos → Enviar → Redactar, Masivo, Plantillas y Enviados**, y Remitente al
lado de Enviar. Las direcciones no cambiaron.

**Masivo** es `/campaigns`, **solo para clientes**: se marcan las
etiquetas a las que va —ninguna es toda la lista—, el asunto y **cómo se arma:
con una plantilla guardada o escrito** (octubre de 2026, `modo`), y sale ahora
o queda programada.

### Escribir o Plantilla (octubre de 2026)

Masivo y Redactar ofrecen los dos lo mismo arriba, **Escribir | Plantilla**
(`campaigns/_mode.html`; sin JavaScript se ven las dos partes y manda la
elegida). La campaña guarda `design_id`, o `body` (y `logo`) si se escribió
(`campaigns.written()`), y `sender.Piece` la arma igual en los dos casos:

- **Lo escrito** sale de `render.text_to_html()`, y con «Poner mi logo arriba»
  lleva el logo de la empresa centrado y a su medida (`sender.logo_block`,
  dentro de 180×64). El logo queda anotado como enviado (`images.mark_sent`),
  así cambiarlo después no rompe los correos que ya llegaron.
- **Un masivo escrito es una campaña**: lleva la baja, `List-Unsubscribe` y la
  marca de agua del Básico (reglas 3 y 4), y **no lleva archivo**: en una
  campaña a cientos, un archivo de 5 MB son cientos de descargas desde el
  panel. La pantalla que pregunta antes de mandarla dice «Texto escrito» donde
  iría la plantilla.
- **Un individual con plantilla sigue siendo individual**: sin baja ni marca
  de agua, con la dirección postal y con el botón de su archivo justo encima
  del pie, en las tres clases de pieza (`render.email()` y
  `email_from_html()` reciben `watermark` y `extra`). **Si la plantilla nombra
  columnas o el nombre** (las marcas se buscan en el correo armado y en el
  asunto, `marks_missing()`) y esa dirección no está en Contactos o no los
  tiene, no sale y se dice cuáles faltan: a quien le falta un dato no le llega
  nada. El correo sí se conoce siempre.
- Es lo que usará la API cuando exista: una plantilla ya sirve para un correo
  a una persona.

**Se le puede escribir a varias etiquetas a la vez**, y le llega a quien lleve
cualquiera de ellas. Que nadie reciba dos veces no hubo que construirlo: un
contacto es **un solo documento** con sus etiquetas dentro, así que la consulta
por varias lo devuelve una vez aunque lleve tres de las marcadas. Es la garantía
que `docs/pricing.md` promete, y hasta que esto existió era cierta solo porque
no se podía elegir más de una. Arriba, siempre, **qué le falta a la cuenta para que un envío salga
de verdad**; armar y programar se puede igual, mandar no.

Masivo tiene **«Campañas guardadas»**, que se corrigen y se vuelven a mandar.
Lo que ya salió está en **Enviados** (`/campaigns/sent`): una línea por cada
vez que salió algo, campañas e individuales, leída de `campaign_runs`. Una
campaña mandada seis veces es una fila en Masivo y seis en Enviados. **De una
campaña cada cifra va sobre los que salieron** (entregados, abiertos, clics,
rebotes y quejas, en personas: `207/210`); **de un individual, una marca** en
cada columna. Un envío del que Amazon
todavía no contó nada lo dice en vez de enseñar ceros. Las bajas no van: el
enlace de baja firma el contacto y no el envío, así que no se pueden atribuir
a uno (por eso Estadísticas las cuenta por cuenta).

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

Del remitente y el «Responder a» que eligió la plantilla, o de los
predeterminados de la cuenta: ver «Envío», arriba. Lo deciden
`sender.remitente()` (y con él `sender_email()` y `from_address()`) y
`sender.reply_to()`, que reciben la plantilla, y nada más. `build()` les pasa
la de cada correo.

Y SES sigue en modo de prueba: **solo entrega a direcciones verificadas**. Lo que
responda por cada destinatario se guarda en la campaña y la pantalla lo enseña.

### Lo que todavía no hace

Reanudar sola una campaña, y acumular los correos no usados al mes siguiente.
(Pausar sola una cuenta que pasa de los umbrales ya lo hace: ver «La pausa
automática».)

## Lo que cuenta Amazon

`POST /webhooks/ses/<secreto>`, en `blueprints/webhooks/`. SES avisa por SNS de
cada entrega, rebote, queja, rechazo, apertura y clic, y
`services/ses_events.py` decide a dónde va cada uno. Lo que hay que hacer en la
consola de Amazon y en Cloudflare está paso a paso en `docs/ses.md`.

**Lo que lo autoriza es el secreto de la dirección** (`SES_WEBHOOK_SECRET`):
uno que no cuadra, o ninguno configurado, responde 404. Con `SES_TOPIC_ARN`
puesto, un aviso de otro tema se descarta. **Y se comprueba la firma de SNS**
(octubre de 2026, `services/sns.py`): el certificado se baja solo de
`https://sns.<región>.amazonaws.com/….pem` y se guarda en memoria, se arma el
texto firmado de cada tipo y se verifica con RSA (SHA1 o SHA256, según
`SignatureVersion`). Sin firma o con una que no cuadra, 403 y nada se guarda; si
no se pudo bajar el certificado, 500 y SNS lo reintenta. Hasta entonces bastaba
el secreto, y con los webhooks a los sistemas de los clientes quien lo tuviera
podía inventarles rebotes y quejas. La dirección para
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

**Cada rebote permanente o queja nueva mira si la cuenta pasó el umbral** de la
pausa automática (`reputation.check()`, ver «La pausa automática»).

## El correo individual (octubre de 2026)

- **Redactar** en Correos → Enviar (`/campaigns/write`): para, asunto,
  el mensaje escrito o una plantilla (octubre de 2026, ver «Escribir o
  Plantilla») y un archivo opcional. Solo quien puede enviar.
- **Es una campaña de una persona** (`kind: single`, `to`, `contact_id` si
  está en Contactos, `body`, `download_id`), y sale ya por `sender.run()`: la
  supresión (regla 1), la cuota (cuenta uno), la dirección postal y las
  etiquetas de SES. Por eso su detalle dice si le llegó, si lo abrió y si
  pulsó, y al enviarlo se aterriza ahí. No sale en «Tus
  campañas» (no se edita ni se vuelve a mandar), sí en lo que ya salió, como
  «Individual · persona».
- **Sin baja y sin marca de agua** (octubre de 2026): no es una campaña, es un
  correo de una persona a otra. `build()` no le pone el pie de baja ni
  `List-Unsubscribe`, y `email_from_body(..., unsubscribe="", watermark=False)`
  no le pone la marca ni en el Básico. Las reglas 3 y 4 de `CLAUDE.md` lo
  dicen. **El riesgo** es que se use para mandar publicidad de uno en uno; lo
  frena la cuota, y si hiciera falta se le pone un tope por hora.
- **A cualquier dirección** (octubre de 2026), esté o no en Contactos, **y sin
  guardarla**: la que no está sale solo con su dirección (`run()` arma el
  destinatario con `to`), y el detalle dice «No está en tus contactos». Una
  dada de baja o que rebotó **en esa cuenta** no sale igual (regla 1). Hasta ese
  mes tenía que estar en Contactos.
- **El texto** lo arma `render.text_to_html()`: escapado, un párrafo por línea en
  blanco, con el mismo sobre y pie que todo (`email_from_body`).
- **El archivo**: uno, de hasta 5 MB, PDF, JPG, PNG, Word o Excel, **reconocido
  por su contenido** (`services/attachments.py`). **No va adjunto: va como un
  botón para bajarlo** (octubre de 2026): el correo no pesa, y no lo frena un
  filtro por el adjunto. **No se anota quién lo bajó**: se hizo, con el evento
  `download` en Enviados, en el detalle y en un webhook, y se quitó el 22 de
  octubre de 2026 porque con saber si abrió el correo basta. Al arrancar,
  `db._forget_downloads()` borra lo que quedó.
  - Se guarda en `downloads` (`models/download.py`), con el contenido dentro y
    **TTL de 30 días**: Atlas lo borra solo. Ocupa espacio en la base mientras
    tanto.
  - El enlace (`/d/<testigo>`, `services/downloads.py`) va firmado con la llave
    del servidor, como el de la baja, y no guarda nada por enlace.
  - **Abrir el enlace no lo baja, pero la página lo baja sola** (octubre de
    2026, `blueprints/downloads/`): es una página propia, **sin la barra ni el
    menú de Sobreala** (`_bare.html`), con el logo y el nombre de quien lo
    manda, el archivo y su tamaño, y un pie chiquito («Enviado por Sobreala ·
    Privacidad»). Un guion con su `nonce` manda el formulario al cargar y
    cambia los textos a «Tu descarga empezó. Ya puedes cerrar esta pestaña.»
    **Cerrarla sola no se puede**: el navegador solo deja cerrar una pestaña
    que abrió el mismo guion, y esta la abrió el lector de correo. Antes era un
    botón que se quedaba girando, porque una descarga no cambia de página.
  - Los escáneres de correo abren los enlaces de lo que revisan pero (casi
    todos) no ejecutan guiones, así que casi nunca se llevan el archivo. Sin
    JavaScript queda el botón «Descargar», que no gira. El POST entrega el
    archivo, y nada más.
  - Vencido o borrado, la página dice que ya no está (410). Con la firma mala,
    404.
  - Hasta octubre de 2026 iba adjunto y no se guardaba; antes de eso se probó
    guardarlo en S3 y se quitó.

## Los correos de la API (octubre de 2026)

Un correo a una persona, **transaccional** (a cualquier dirección, sin baja ni
marca de agua y sin contar clics; solo lo frenan un rebote permanente o una
queja en esa cuenta) o **promocional** (a un contacto completo y sin ninguna
supresión, con su baja y la marca de su plan). Sale por `sender.send_one()`, que
sigue siendo el único sitio que le escribe a alguien, y vive en `messages`, no en
Enviados. El detalle, en `docs/api.md`.
