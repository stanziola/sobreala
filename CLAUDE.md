# Panamails

Plataforma de email marketing para negocios de Panamá. Las empresas clientes
suben sus contactos, arman campañas (ofertas, recordatorios, eventos) y las
envían desde un panel web. Las piezas las arma cada cliente en el editor, o sube
su propio HTML: el diseño como servicio aparte se dejó de ofrecer.

Mercado principal: Santiago de Veraguas y el interior. Cliente típico:
cooperativas de ahorro y crédito, colegios privados, gremios, universidades y
PyMEs — organizaciones que ya tienen una lista de correos armada por otra razón.

**Estado.** Están la marca (`brand/`), el sitio público (`landing/`, siete
páginas estáticas generadas con Jinja2), la cuenta entera —registro, código,
doble factor, dispositivos, configuración—, **contactos** con su importador y
sus supresiones, **plantillas** —las cuatro prediseñadas y la validación del
HTML subido—, el **panel de administración** con la habilitación de envío, el
**cobro de un plan con PayPal** y el **envío de campañas**, con su enlace de
baja, y **el aviso de Amazon** que cuenta qué pasó con cada correo después de
salir. Faltan la pausa automática por rebotes y quejas, y el proceso en segundo
plano.

---

## Stack

| Componente | Tecnología | Dónde corre |
|---|---|---|
| Backend | Flask (Python) | Railway |
| Base de datos | MongoDB Atlas (PyMongo) | AWS us-east-1 |
| Envío de correo | **Amazon SES** (API HTTPS, no SMTP) | AWS |
| Landing | HTML/CSS/JS estático | Cloudflare Pages |
| DNS, WAF, rate limiting | Cloudflare (modo proxied, SSL Full strict) | — |
| Imágenes de correos | En la propia base, servidas por el panel | Railway |
| Pagos | PayPal, y tarjeta por Paguélofácil (falta la afiliación). Yappy, anunciado | — |

**No usar Brevo ni SMTP propio.** Brevo prohíbe en sus términos enviar en nombre
de terceros y sus tarifas dan margen negativo. El SMTP propio o de una cuenta
empresarial tiene límites de ~2,000 correos/día y quema la reputación del
dominio. Ver `docs/decisiones.md`.

---

## Estructura del repositorio

```
panamails/
├── CLAUDE.md
├── README.md
├── .env.example
├── docs/
│   ├── pricing.md          # planes, precios y reglas de negocio
│   ├── pricing-interno.md  # costos, márgenes, competencia (FUERA de git)
│   ├── arquitectura.md
│   ├── decisiones.md
│   └── ses.md              # conectar SES con el panel, y la entrega a la UTP
├── brand/
│   ├── colors.css          # variables de color, fuente única de verdad
│   ├── layout.json         # posición del ala (logo y favicon) y encuadre del favicon
│   ├── build_logo.py       # genera logo/, favicon/ y preview/ desde esos dos
│   ├── logo/               # logo.svg, logo-transparent.svg, logo.png (generados)
│   │   └── reference/      # PNG original del logo, referencia visual maestra
│   ├── favicon/            # favicon.svg, .ico y PNG 16/32/180 (generados)
│   ├── preview/            # colores.html: editor de color y posición (generado)
│   ├── social/             # iconos de redes (Instagram, etc.), agregados a mano
│   └── fonts/
├── requirements.txt        # dependencias de Python; en la raíz porque Railway
│                           # las busca aquí para reconocer el proyecto
├── Procfile                # cómo arranca en Railway
├── .python-version         # 3.12
├── landing/                # → Cloudflare Pages (sitio público, ver landing/README.md)
│   ├── build_site.py       # genera las páginas; único punto de entrada.
│   │                       # --check avisa si lo publicado quedó viejo
│   ├── content.py          # todos los textos del sitio, en español
│   ├── src/                # plantillas Jinja2 (base, parciales, páginas) y site.css
│   ├── assets/             # css, js, fonts, img (fonts, img y css/site.css son generados)
│   ├── index.html          # GENERADO
│   ├── como-funciona/      # GENERADO
│   ├── planes/             # GENERADO (precios leídos de docs/pricing.md al construir)
│   ├── nosotros/           # GENERADO
│   ├── contacto/           # GENERADO
│   ├── privacidad/         # GENERADO
│   └── terminos/           # GENERADO
└── backend/                # → Railway
    ├── wsgi.py
    ├── config.py
    ├── requirements.txt    # apunta al de la raíz, que es el de verdad
    ├── blueprints/
    │   ├── auth/           # registro, confirmación, login, configuración. HECHO
    │   ├── contacts/       # importación, etiquetas, supresiones. HECHO
    │   ├── designs/        # plantillas: las prediseñadas y el HTML subido. HECHO
    │   ├── admin/          # aprobar cuentas, ficha de cliente y piezas. HECHO
    │   ├── campaigns/      # crear, programar, enviar por tandas. HECHO
    │   ├── unsubscribe/    # la baja, sin sesión. HECHO
    │   ├── analytics/      # bajarse Estadísticas en CSV y en PDF. HECHO
    │   ├── billing/        # planes, cuota, acumulado
    │   └── webhooks/       # SNS de SES. HECHO. PayPal y Yappy, no
    ├── models/
    ├── make_admin.py       # da el rol de administrador al primero, a mano
    ├── build_assets.py     # genera panel.css y _wing.svg; --check avisa si
    │                       # quedaron viejos
    ├── services/
    │   ├── mailer.py       # correo del sistema: file | smtp | ses
    │   ├── notices.py      # los avisos de la cuenta: plan, habilitación,
    │   │                   # suspensión, y el aviso de pago para el admin
    │   ├── security.py     # contraseñas, CSRF, límite de intentos
    │   ├── totp.py         # autenticación de múltiples factores
    │   ├── importer.py     # CSV en streaming, upsert por lotes
    │   ├── plans.py        # precios, etiquetas y quién sube HTML, de docs/pricing.md
    │   ├── html_check.py   # revisa el HTML que sube un cliente
    │   ├── paypal.py       # crear y cobrar la orden, con urllib
    │   ├── sender.py       # arma y entrega cada correo de una campaña
    │   ├── unsubscribe.py  # el enlace de baja, firmado, uno por destinatario
    │   ├── render.py       # arma el correo: la pieza más la baja, la marca
    │   │                   # de agua y la dirección postal
    │   ├── imaging.py      # achica y reconoce las imágenes de las piezas
    │   ├── ses.py
    │   ├── ses_events.py   # a dónde va cada aviso de SES: evento, supresión
    │   │                   # o la fila de mail_log
    │   └── payments/
    ├── email_templates/    # plantillas prediseñadas del producto, una por
    │                       # archivo, con sus campos declarados arriba
    ├── templates/          # Jinja: panel del cliente y admin
    ├── static/
    └── tests/
```

Un solo repositorio. `landing/` se despliega a Cloudflare Pages y `backend/` a
Railway; cada plataforma apunta a su carpeta.

**Todo lo que dice GENERADO se escribe con un comando, nunca a mano.** Editar
`landing/src/` o `_panel.src.css` y no regenerar no rompe nada y llega al
despliegue en silencio: ya pasó una vez. Por eso `python landing/build_site.py
--check` y `python backend/build_assets.py --check` comparan sin escribir, y
`backend/tests/test_generated.py` los llama, así que un `pytest` falla cuando
algo quedó viejo y dice qué comando correr.

El panel de administración es un **blueprint con verificación de rol**, no una
aplicación aparte: comparte modelos y servicios con el resto.

---

## Convenciones

- **Código en inglés**: variables, funciones, colecciones y campos de Mongo
  (`contacts`, `send_campaign`, `bounce_rate`, `suppression_reason`).
- **Interfaz en español**: todo lo que ve el cliente — panel, correos del
  sistema, mensajes de error, plantillas. Los textos de interfaz van en un solo
  archivo de traducciones, no dispersos en las plantillas.
- Comentarios en inglés.
- **En la interfaz no se usan guiones largos.** Un inciso va entre paréntesis,
  con comas o con dos puntos. En el texto que lee un cliente —el panel, el sitio
  y los correos— esa raya se lee como escrita por una máquina. En los
  comentarios del código y en este documento da igual.
- Implementaciones mínimas y directas. No agregar funcionalidad que no se pidió.
- **No cambiar nada que no se haya pedido.** Si al hacer una tarea aparece algo
  más —un texto flojo, una regla que se salta en silencio, algo que se podría
  endurecer— **se dice y se espera**, no se arregla de paso. La única excepción
  es lo estrictamente necesario para que lo pedido funcione o para que las
  pruebas pasen, y eso va nombrado en el reporte. Renombrar de paso, reordenar,
  «ya que estoy» y «aprovecho y mejoro esto» no entran.
- **Los commits se hacen aquí, pero solo cuando se piden.** Terminar un bloque
  no es una orden de subir nada: el reporte sigue siendo el resumen enumerado
  con su asunto sugerido, y ahí se espera. Cuando se pide subirlo, primero se
  pregunta si va con ese asunto o con uno escrito a mano, y después `git add`,
  `git commit` y `git push`. Un plan aprobado tampoco es una orden de subir:
  aprobar un plan es decir «hazlo», no «publícalo».
- **En el repositorio no aparece Claude.** Ningún commit lleva `Co-Authored-By`,
  ni enlace de sesión, ni una línea de «generado con»: el autor es el de
  `git config` y el mensaje dice qué cambió y nada más. Si algún día eso no se
  pudiera cumplir, entonces no se commitea.
- **Los permisos viven en `.claude/settings.json` del proyecto**, no en el del
  usuario, para que esto valga en Panamails y no en sus otros repositorios. Van
  sin preguntar: `status`, `log`, `diff`, `show`, `add`, `commit`, `push`,
  `branch`, `remote` y `fetch`. Quedan negados a propósito, y los hace una
  persona a mano: `reset --hard`, `push --force`, `rebase`, `clean`,
  `filter-branch` y borrar el `reflog`.
- **Lo que existe en los dos sitios se cambia en los dos.** La barra de arriba,
  su menú y todo lo que se repita entre `panamails.com` (`landing/src/`) y
  `panel.panamails.com` (`backend/templates/`) son **dos plantillas distintas
  que tienen que decir lo mismo**. Al tocar una, se abre la otra en el mismo
  cambio y se comprueban las dos en el navegador, con sesión y sin ella. Ya
  mordió dos veces: la fila de Plantillas se puso solo en el panel, y salir
  preguntaba en un sitio y no en el otro.

---

## Modelo de datos

### `accounts`
Cuenta de una empresa cliente. Guarda plan, cuota del mes, saldo acumulado,
estado y configuración de remitente.

Estados: `registered` → `active` → `suspended`

| Estado | Qué significa |
|---|---|
| `registered` | Se registró. Explora, importa contactos y **puede comprar un plan**. |
| `active` | Pagó. Su plan corre hasta `plan_until`. |
| `suspended` | Nada. Corte automático por rebotes/quejas, o manual. |

**Hubo un cuarto, `approved`, y se quitó.** Era una aprobación comercial a mano
sin la cual no se podía comprar. Esperar a que alguien te apruebe para poder
pagar no protegía nada que valiera esa espera; la mirada que sí importa —de
dónde salió esa lista— se hace ahora justo antes del primer envío, que es donde
puede hacer daño. Ver «La habilitación para enviar», más abajo.

**Estar activa es el efecto de un pago cobrado, no una decisión.** `activate_plan()`
es el único sitio que escribe `active`, y lo llaman tanto la vuelta de PayPal
como el plan que el administrador pone a mano para quien pagó por Yappy o por
transferencia. Lo que el administrador sí decide es **suspender y levantar la
suspensión**, desde `/admin/cuentas/<id>` y con un motivo que queda escrito en
`admin_events`. `suspended` no es decorativo: una cuenta suspendida no abre
sesión, y al suspenderla se le cierran las que tuviera abiertas.

### Los usuarios de la cuenta

**Una empresa puede darle entrada a alguien de su equipo**, con sus permisos:
ver estadísticas, ver campañas, enviar correos, modificar contactos y crear o
editar plantillas.

**Un usuario es su propio documento de `accounts`**, con `owner_id` apuntando a
la empresa y `permissions` con lo que puede. Se hizo así y no con una colección
aparte porque el inicio de sesión, la contraseña, la autenticación de múltiples
factores, los dispositivos y los avisos ya funcionan por documento de cuenta:
nada de eso hubo que escribirlo dos veces.

**Lo que ve y toca sigue siendo de la empresa.** `current_workspace()` devuelve
la cuenta dueña y es lo que reciben los tres blueprints en su `signed_in()`, así
que las consultas siguen preguntando por un solo `account_id` y no cambió
ninguna. `current_account()` sigue diciendo **quién** es: su correo, su
contraseña y su segundo factor son suyos, no de la empresa.

| Quién | Qué puede |
|---|---|
| El dueño | Todo, siempre. No lleva permisos escritos: lo que decide es no tener `owner_id` |
| Un usuario | Lo que el dueño le marcó (`accounts.can()`), y **su** Seguridad |
| Un administrador de Panamails | Ninguno de estos permisos: no tiene clientes a los que escribirle |

- **Mandar arrastra ver**: `SEND` implica `CAMPAIGNS`, porque un usuario que
  manda y no ve lo que mandó no tiene sentido (`clean_permissions()`).
- **Se comprueba en la ruta**, con `needs()` en el `before_request` de cada
  blueprint y en las cuatro rutas que escriben o mandan campañas. El menú
  esconde lo que no puede, pero esconder una fila no es un permiso. Quien abre
  algo que no le toca cae en la primera pantalla que sí puede, y si no puede
  ninguna, en su Seguridad.
- **Del dueño y solo del dueño**: Configuración → Cuenta, Notificaciones,
  Facturación, contratar un plan, la dirección postal y los usuarios mismos
  (`owner_only()`).
- **Cuántos caben lo dice el plan**, leído de `docs/pricing.md` como los precios
  (`plans.users()`), y **el dueño cuenta**: Básico 1, Negocio 2, Empresa 3, y 1
  sin plan. Una invitación sin aceptar ocupa sitio, porque si no se podrían
  mandar veinte. Si un cambio de plan deja más usuarios de los que caben, nadie
  pierde la entrada: no se puede crear otro y la pantalla lo dice.
- **El alta es por invitación**: el dueño escribe nombre, correo y permisos, y
  a esa persona le llega un enlace de un solo uso que vence en siete días
  (`tokens.INVITE`) para poner **su** contraseña. El dueño nunca conoce la
  contraseña de nadie, y reenviarla deja sin valor la anterior. Al aceptarla el
  correo queda confirmado: el enlace llegó a esa dirección, que es lo que
  probaría un código.
- **El correo es propio de cada persona, no el de la empresa.** Es a donde va
  la invitación, el aviso de un dispositivo nuevo y la recuperación de su
  contraseña, y es lo que hace que `auth_events` diga quién hizo qué. El índice
  único de correos lo garantiza: una dirección con cuenta no se puede invitar.
- **Desactivar y borrar le cierran las sesiones** en el momento: quitarle la
  entrada y dejarlo dentro no es quitarle la entrada. Una empresa suspendida
  deja fuera también a su equipo (`member_may_enter()`).
- **La tabla de administración no lista usuarios**, como no lista
  administradores: el cliente es la empresa, y su ficha ya dice quiénes entran.

### La habilitación para enviar

`sending_cleared_at` en la cuenta, y `sending_cleared_by` con quién la puso. **Es
la única puerta que queda con una persona detrás.** Todos los clientes envían
desde el mismo dominio, así que comparten una sola reputación: una lista comprada
la quema para todos. Se mira una vez —de dónde dijo que salió cada lista, y la
pieza que va a mandar— y después la cuenta queda habilitada.

Registrarse, importar y pagar **no la necesitan**: nada de eso le llega a nadie.
La portada de `/admin` lista lo que espera, que son las cuentas con plan y sin
habilitar. Todavía no hay campañas, así que nada consulta `can_send()` hoy; el
blueprint de campañas, cuando exista, lee ese booleano antes de mandar nada.

**`role` está en todas las cuentas** y vale `client` o `admin`; un campo que a
veces está y a veces no es difícil de leer y fácil de equivocar en una consulta.
Lo que decide quién manda es la comparación exacta contra `admin`, así que un
valor mal escrito no es administrador. Al primero se lo pone `make_admin.py` a
mano, porque nadie puede aprobarse a sí mismo el primer día. Las rutas de `/admin`
responden **404** a quien no lo tiene —un 403 le confirmaría a un curioso que la
dirección existe— y exigen doble factor: es la cuenta que puede aprobar,
suspender y leer las cifras de todos los clientes.

**Una cuenta de administrador solo administra.** No tiene panel de envíos, ni
contactos, ni plantillas, ni puede comprar un plan: no tiene a quién escribirle,
así que esas pantallas le saldrían vacías. De Configuración le quedan dos:
**Seguridad** —contraseña, múltiples factores y dispositivos—, que es lo que hay que
cuidar en la cuenta que puede suspender y habilitar a todas las demás, y
**Notificaciones**, que es la misma pantalla con otra lista: qué le avisamos de
las cuentas de sus clientes. Las filas se esconden del menú
**y las rutas la devuelven a `/admin`**: esconder un botón no es un permiso.

**Un registro que no se confirma se borra a las 24 horas.** `create()` escribe
`purge_at` y `confirm_email()` lo quita, así que Mongo barre solo lo que quedó a
medias: una dirección escrita mal no queda ocupada para siempre, y nadie puede
reservar el correo de un tercero registrándolo y no confirmando nunca. El
intento sigue en `auth_events`, que no tiene TTL.

**La cuota del mes vive en `sent_counts`**, una clave por mes y un contador
dentro. Un contador por mes y no uno solo que haya que poner a cero: el mes que
viene empieza en cero porque es otra clave, sin que nadie pase a barrer, y lo del
mes pasado queda para responder cuánto envió alguien en marzo. Lo compara
`accounts.quota_left()` contra lo que dice `docs/pricing.md` para ese plan; sin
plan es cero, que no es lo mismo que «no se sabe».

**El correo de la cuenta se puede cambiar, con dos pruebas.** La contraseña,
como para cambiarla o para tocar los dos pasos; y un **código a la dirección
nueva**, que es lo que prueba que existe y que es suya. Hasta que ese código
entra, la dirección nueva vive en `pending_email` y **la cuenta sigue entrando y
recibiendo por la de siempre**: un cambio a medias dejaría a alguien sin ninguna
de las dos. Al terminar se avisa a la **dirección vieja**, y ese aviso no tiene
interruptor ni lleva enlaces dentro: quien lo recibe ya no controla esa cuenta, y
es lo único que le queda para reclamar.

Corregir el correo (`/confirmar/corregir`) es otra cosa y es de antes: sirve
mientras la cuenta no está confirmada, cuando todavía no hay nada que proteger.
Y si una cuenta sin confirmar cambia su correo por aquí, **queda confirmada**:
el código acaba de probar exactamente lo que probaría confirmar, y pedir dos
veces la misma prueba no protege de nada.

**Ninguna contraseña se puede repetir.** `password_history` guarda el hash de
cada una que la cuenta usó, y cambiarla las compara todas: si alguien conoció
una, volver a ponerla devolvería la cuenta al mismo estado.

**Autenticación de múltiples factores, opcional para cada cuenta.** Se llamó
«verificación en dos pasos» hasta septiembre de 2026; es el mismo segundo
factor, una app de códigos. `two_factor` guarda
el secreto de la app de códigos —TOTP: el servidor tiene que calcular los mismos
dígitos que el teléfono, así que ese sí va tal cual y no como hash—, el último
intervalo usado, para que un código no sirva dos veces, y los **hashes** de ocho
códigos de respaldo de un solo uso. Activarla y desactivarla piden la
contraseña: sin eso, quien encuentre una sesión abierta se queda con la cuenta.
Las dos cosas se avisan por correo.

**Las dos pantallas van en dos pasos, y la contraseña siempre va primero.** Para
activarla: la contraseña, y solo después el QR; entre las dos, una marca en la
sesión con diez minutos de vida, para que la del QR no se pueda abrir sola. Para
administrarla: primero se elige entre generar códigos nuevos o desactivar, y
después se confirma con la contraseña, para que se confirme una decisión y no un
botón cualquiera.

**Con dos pasos activados el código se pide siempre**, en cualquier dispositivo
y todas las veces. Hubo una opción de no volver a preguntar durante 30 días y se
quitó: un dispositivo que deja de preguntar un mes es un segundo candado abierto
un mes, y quien quiere esa comodidad lo que quiere es no tener dos pasos.

Los campos donde se pide la contraseña para probar quién eres —cambiarla, y
activar o desactivar los dos pasos— nacen de **solo lectura** y se liberan al
primer clic. El gestor de contraseñas del navegador no rellena lo que no se
puede escribir, y así no contesta él por quien acaba de sentarse frente a una
sesión ajena. Sin JavaScript el campo funciona como siempre.

**`notifications` guarda qué correos quiere recibir la cuenta**, una clave por
aviso. Lo que no esté escrito vale «sí»: una cuenta que nunca abrió la pantalla
recibe todo. En una cuenta de cliente están los avisos de su actividad
—`new_login`, `billing`, `plan_state`, `imports`, `campaigns`, `monthly`— y en
una de administrador **otros tres**, que son de lo que hacen los clientes:
`admin_payment`, `admin_signup` y `admin_plan_end`. Lo decide
`accounts.notices_for()`, y una cuenta es lo uno o lo otro, así que las dos
listas no se mezclan nunca en el mismo documento. Los de seguridad **no tienen clave y no se
pueden apagar**: el código de confirmación, el de recuperación, la contraseña
cambiada y el doble factor activado o desactivado son los que enteran a alguien
de que otro está entrando a su cuenta, y `set_notifications()` descarta
cualquier campo del formulario que no sea uno de los seis de arriba.

**`billing` y `plan_state` están separados a propósito.** El primero es
papeleo —el comprobante de lo que se cobró— y el segundo es lo que explica
por qué algo dejó de funcionar. Son dos cosas que se quieren apagar por
razones distintas, y juntarlas obligaba a elegir entre las dos.

**`plan_notices` guarda para qué fecha de vencimiento ya se avisó**, no un
sí o un no. Es lo que hace que renovar devuelva el aviso para el ciclo
siguiente sin que nadie tenga que limpiar nada: al cambiar `plan_until`, la
marca deja de coincidir sola.

### `sessions`
Un documento por dispositivo con sesión abierta: de la galleta solo se guarda su
hash, y el documento lleva IP, navegador, cuándo entró y cuándo se le vio por
última vez. Es lo que permite enseñar los dispositivos conectados y cerrar uno
sin tocar los demás. TTL sobre `expires_at`.

**Entrar desde un dispositivo que la cuenta nunca usó manda un aviso por
correo**, con un enlace de un solo uso para cerrar esa sesión sin necesidad de
recordar la contraseña. Solo al entrar, no al confirmar el registro ni al
recuperar la clave, que ya avisan por su cuenta.

### `contacts`
**Un solo documento por dirección de correo por cuenta.** Índice único sobre
`{account_id, email_normalized}`. Normalización: sin espacios, minúsculas.

Las "listas" son un arreglo de **etiquetas** en el mismo documento, no
colecciones separadas. Esto garantiza que un contacto en varias listas:
cuente una sola vez contra el límite, reciba un solo correo, y consuma un solo
correo de la cuota.

**Cuántas etiquetas caben lo dice el plan**, leído de `docs/pricing.md` como los
precios: 1 · 2 · 4, y **1 sin plan**, como el Básico. No se copia el
número al backend por la misma razón que no se copian los precios. Una
consecuencia que conviene tener presente: con una sola etiqueta no se puede
segmentar, así que el Básico tampoco; si algún día estorba, es cambiar una fila
del documento.

**Las etiquetas se crean antes de usarse**, en `/contactos/etiquetas`, y viven
en `contact_tags` del documento de la cuenta. Los formularios de agregar e
importar solo enseñan casillas con las que existen, y el servidor descarta lo
que llegue y no esté en ese registro. Dos razones: escribirlas en cada
formulario dejaba «Socios» y «socios» como dos etiquetas distintas, y una recién
creada no aparecía en ningún lado hasta tener un contacto dentro, porque la
lista se sacaba preguntándole a los contactos.

**Cada cuenta define sus propias columnas**, además del correo y el nombre:
ciudad, número de socio, monto, fecha de vencimiento. Viven en
`contact_fields` del documento de la cuenta —nombre, clave, tipo y respaldo— y
sus valores en `fields` del contacto, así que escribir un correo personalizado
no agrega ni una consulta. Cuántas caben lo dice `docs/pricing.md`, como las
etiquetas: 1 · 5 · 10, y 1 sin plan.

Cuatro tipos —texto, número, fecha y sí/no— y cada uno se gana el sitio
haciendo dos cosas: decidir qué se acepta al importar, y cómo se escribe al
enviar. **El valor se guarda normalizado y siempre como texto**: una fecha como
`2026-03-15` y un «1,234.50» como `1234.5`, para que el archivo de cada cliente
pueda venir como venga y el correo salga parejo. Lo que no es de su tipo no se
escribe: guardar «el martes» en una columna de fecha es guardar algo que
después no se puede enseñar.

**Son obligatorias, y no hay texto de respaldo.** Un contacto **nuevo** solo
entra con todas llenas —sin ellas no podría recibir nada, así que entrar sería
entrar de peso muerto— y al que le falte una **no se le manda ningún correo**
hasta que la tenga. Tapar el hueco con un respaldo era lo contrario de
enseñarlo.

Eso muerde el día que se crea una columna nueva: deja incompleta a toda la
lista. Por eso se ve en los cuatro sitios donde se cuenta gente —la tabla marca
«Incompleto», el contador lo dice, la pantalla de crearla avisa a cuántos va a
dejar fuera, y las cifras de envío ya no los cuentan—. Lo hace una condición en
la consulta común (`models/contact.py`) que **solo encienden los caminos de
envío**: la lista sí los enseña, porque para completarlos hay que verlos.

**Se crean desde la lista de contactos**, que es donde se está cuando hace falta
guardar un dato más, y con el plan lleno ese botón sale apagado —y la ruta lo
comprueba igual—. `/contactos/columnas` es para lo que ya existe: **cambiar el
tipo**, que no se deja si algún valor no encaja en el nuevo, y borrar. El nombre
no se cambia: es lo que las piezas ya tienen escrito dentro. Borrar una borra lo
que los contactos tenían escrito en ella; los contactos se quedan.

**`added_by` dice por dónde entró cada contacto**, `manual` o `import`. Los que
existían antes de que el campo existiera no lo tienen y la pantalla enseña una
raya: no se puede saber hacia atrás, y una raya es mejor que inventarlo.

**Cada contacto guarda de dónde salió**: `consent` con el origen que se declaró
al importar, la nota y la fecha. Se pregunta antes de escribir nada porque no se
puede rellenar hacia atrás, y es lo que hay que enseñar cuando alguien reclame
que no dio su correo.

**Si está suprimido no se marca en el contacto.** La supresión vive en su propia
colección y se consulta en lote con `$in`; así las dos no pueden separarse, y un
contacto borrado y vuelto a importar reaparece suprimido. La columna «Estado» de
la lista sale de esa consulta, no de un campo guardado.

**Exportar pregunta antes.** El GET de `/contactos/exportar` no descarga nada:
dice cuántos van a salir y con qué filtro, y el POST es el que escribe el
archivo. El filtro viaja en campos escondidos, así que lo que baja es lo que esa
pantalla acaba de decir y no lo que quedó en la dirección de otra.

**El límite de contactos sale del plan** (`PLAN_CONTACTS` en
`models/account.py`, copiado de `docs/pricing.md`). Una cuenta **sin plan** tiene
`CONTACTS_FREE_LIMIT`, hoy 500: alcanza para probar con una lista de verdad y
deja que el Básico, con 1,000, valga la pena.

### `suppressions`
Correos que una cuenta no puede volver a contactar. **Colección aparte; el
cliente no la puede borrar.** Índice sobre `{account_id, email}` — nunca global:
una baja en una cuenta no afecta a las demás.

| `reason` | ¿Se puede levantar? |
|---|---|
| `unsubscribe` | Solo si la persona se resuscribe por el formulario, con doble opt-in |
| `hard_bounce` | Nunca |
| `complaint` | Nunca |
| `manual` | Sí, por el cliente desde el panel |

Guardar siempre fecha y origen.

### `imports`
Un documento por archivo subido: nombre, etiquetas, el origen declarado, en qué
fila va y cuántas entraron, se actualizaron o no eran direcciones. Es lo que
hace comprobables los límites —diez al día, una a la vez— y lo que responde qué
pasó con un archivo de hace meses.

**Hoy la importación corre dentro del request**, no en un proceso aparte. Es a
propósito: con un tope de 500 filas tarda menos que abrir la página. El
documento existe para que mudarla sea mover el trabajo y no rehacer los datos.
**Hay que mudarla antes del primer cliente con más de unas 5,000 filas**, que es
donde el request se acerca al tiempo máximo de Railway.

### `admin_events`
Un documento por decisión de un administrador: qué cambió, de qué a qué, sobre
qué cuenta, cuándo y **por qué**. El motivo no es opcional; la pantalla no deja
aplicar un cambio sin él, porque meses después esa frase es la única respuesta
honesta a «por qué me suspendieron». Sin TTL, como `auth_events`.

### `payments`
Un documento por **intento** de pago, escrito antes de mandar a nadie a PayPal:
la cuenta, el plan, si fue mensual o anual, el monto que se pidió cobrar, la
moneda, el identificador de la orden, el estado y las fechas. Se escribe antes y
no al volver porque si alguien paga y el navegador se cierra en el camino de
vuelta, ese intento tiene que existir para poder reconciliarlo.

**De la tarjeta no hay nada, y no puede haberlo**: el pago entero ocurre en el
checkout de PayPal. Es la regla 9.

Pasar de `created` a `completed` es una **escritura condicional**, y es la única
que decide si se alarga un plan: recargar la página de vuelta entra otra vez y
se va con las manos vacías en lugar de regalar otro periodo. Al cobrar se guarda
también `payer_email`, la cuenta de PayPal que pagó. **Se guarda y no se
enseña**: es para cuando haya cobros recurrentes.

### `invoices`
**El PDF de la factura de cada pago cobrado**, que se emite a mano y se sube
desde la ficha de la cuenta en administración («Pagos y facturas»). Uno por
pago: subir otro lo reemplaza, y queda en `admin_events`. Solo entra lo que
empieza como un PDF, hasta 2 MB. Lo baja solo la cuenta dueña, desde
Facturación, **siempre como archivo** y nunca dentro de una página del panel. La
primera vez que se sube se le avisa al cliente, con el interruptor de «Pagos y
plan».

### `designs`
Las piezas de un cliente. Se llaman «diseños» y no «templates» porque en este
repositorio `templates/` ya son las plantillas Jinja del panel; para el cliente
la pantalla dice **Plantillas**, que es su palabra.

**`source` dice de dónde salió cada una**, y hay dos:

| `source` | Qué guarda | Quién puede |
|---|---|---|
| `upload` | El HTML entero, tal como llegó | Negocio en adelante |
| `builtin` | De qué prediseñada salió y **qué escribió en cada casilla** | Todos |

De una prediseñada llena **no se guarda el correo armado**. Guardar el resultado
la dejaría imposible de volver a editar, y además el archivo de la plantilla
puede mejorar: al reabrirla se arma otra vez con lo que ese archivo diga hoy. Los
archivos de las prediseñadas viajan con el repositorio, en `email_templates/`,
iguales para todos y sin nada que aprobar.

**Subir HTML propio es de Negocio en adelante**, y eso lo dice la fila «Subir tu
propio HTML» de `docs/pricing.md`, no una lista copiada al backend. El servidor
lo comprueba además de esconder el formulario: esconder un botón no es un
permiso.

**Cada subida se valida al entrar** con `services/html_check.py`, que lee el
documento con un parser y no con expresiones regulares —`&lt;script&gt;` es
texto y `<script>` no—. Fuera: `<script>`, `<iframe>`, `<object>`, `<form>`,
atributos de evento, CSS o imágenes de otro sitio, y **cualquier pieza de más de
102 KB**. Lo que se guarda es el archivo entero y tal como llegó.

**Nadie aprueba una pieza a mano.** Lo que puede hacer daño lo rechaza el
validador al subirla, y eso es mecánico, no un juicio. La mirada de una persona
ocurre una sola vez por cuenta, en la habilitación para enviar, y es sobre la
cuenta y su lista, no sobre el archivo. Tener las dos serían dos revisiones
manuales para la misma decisión. `/admin/plantillas` lista lo que han subido los
clientes, para poder abrir una cuando haga falta; las prediseñadas llenas no
salen ahí, porque son nuestras plantillas con el texto de alguien dentro y no hay
ningún archivo ajeno que mirar.

**El HTML de un cliente se dibuja solo para él, y solo en un marco aislado.**
Es lo que deja editarlo viendo cómo queda (`/plantillas/html/<id>`): el código a
un lado, la vista previa al otro, y un botón por columna que escribe su marca
donde está el cursor. El marco va con `sandbox` y sin ningún permiso —origen
opaco, sin scripts, sin ver la galleta— y la respuesta lleva la cabecera de
seguridad de un correo, no la del panel. Antes de dibujarse pasa el validador:
lo que no se podría guardar tampoco se enseña, y en su lugar sale por qué. Con
JavaScript se refresca sola al dejar de escribir, pulsando por su cuenta el
botón de ver cómo queda; un marco llenado desde el panel heredaría la cabecera
del panel y no dejaría pasar los estilos del correo. **En el panel del
administrador sigue sin dibujarse**: allí se baja como `text/plain`.

**La pantalla de Plantillas tiene dos caminos arriba**: Crear plantilla (el
lienzo, de todos los planes) y Cargar plantilla personalizada, que con un plan
que no lo permite sale apagado —y la ruta lo comprueba igual—. Cargar abre una
bandeja con el formulario; sin JavaScript el botón lleva a `/plantillas/cargar`,
que es la misma ruta. Al cargar se va directo al editor. Debajo, dos notas —el
dato de cada persona, con las columnas de esa cuenta, y el tope de 102 KB— y la
lista de todas sus piezas, con Editar, Duplicar y Borrar. **Duplicar copia las
imágenes por nombre**, así que borrar una pieza solo borra las imágenes que
ninguna otra nombra.

## El lienzo de «Crear plantilla»

`/plantillas/crear` y `/plantillas/lienzo/<id>`, con `services/canvas.py` y
`static/js/canvas.js`. **Es una sola hoja de 600 px que crece hacia abajo**:
texto, botón, imagen y geometría se ponen donde se quiera, se mueven, cambian
de tamaño y de estilo, y se deshace y rehace. Se guarda **el lienzo en JSON con
sus coordenadas** (`source: "canvas"`, `{v: 2, h, bg, items}`), no el HTML: el
correo se arma al enviar.

**Se eligen varios a la vez** con Mayús+clic o arrastrando un recuadro sobre la
hoja, y entonces se mueven juntos, se alinean, se reparten, se duplican y se
borran de una vez. **Agrupar** escribe `g` en cada elemento y viaja con la
pieza, así que tocar uno vuelve a elegir el grupo entero al reabrirla. Es lo
único de todo esto que **no cambia cómo se arma el correo**: las celdas las
siguen decidiendo las cajas que se enciman, así que dos cosas agrupadas pero
separadas caen en celdas distintas. `groups()` y `to_html()` ignoran `g`.

**Se copia y se pega** con Ctrl+C, Ctrl+X, Ctrl+V y Ctrl+D. Lo copiado va al
portapapeles **como texto nuestro**, así que se pega también en otra plantilla o
en otra pestaña; si el navegador no deja escribirlo, queda en una variable y
sirve dentro de esa página. Lo pegado entra por `parse()` como todo lo demás: el
servidor no se fía de ello más que de lo que escribe el editor.

**Una foto se puede pegar del portapapeles**, y sube por la misma ruta que el
botón (`/plantillas/lienzo/imagen`): se revisa por lo que trae dentro, se achica
y cuenta contra el tope de 20. Si el portapapeles solo trae **una dirección
web**, se pide descargarla y subirla: **el servidor nunca va a buscar una
imagen a otro sitio**, que sería dejarlo pidiendo cualquier cosa a cualquier
dirección. De los derechos de autor no hay detección posible: lo que hay es la
línea que lo dice al subir, los términos §7 y que cada imagen queda en `images`
con su cuenta y su fecha, que es lo que permite retirarla si alguien reclama.

**Hubo diapositivas y se quitaron** (septiembre de 2026). `canvas.read()`
convierte lo guardado así: las apila en una hoja, y el color de cada una pasa a
ser un rectángulo del ancho entero. Se abre ya convertida, queda guardada en la
forma nueva al volver a guardarla, y **el envío la rehace una vez antes del
primer correo** (`designs.upgrade_canvas()`), porque sus imágenes guardadas eran
de otra forma.

**La hoja crece sola** cuando algo pasa del borde de abajo (un texto que se
alarga, algo arrastrado más abajo) y nunca queda más baja que lo que tiene
dentro; arrastrar el borde de abajo deja más o menos aire. **El alto también se
escribe**, en la barra de cuando no hay nada elegido: crecer sola cubre el caso
de siempre, pero no el de querer una medida exacta, y el tirador solo no se
encontraba. Lo escrito se limita entre lo que hay dentro y los 4,000 px, y
cuando no cabe se queda en el mínimo **y lo dice**. Sin tamaños listos, que esos
sí sobran. El ancho no se toca, 600 px es lo que se lee bien en todos los
buzones. Topes: **4,000 px de alto y 60 elementos**; lo que
de verdad limita es la barra de peso.

**Ningún lector de correo respeta posiciones libres** —Gmail las borra y Outlook
dibuja con el motor de Word—, así que `to_html()` traduce las coordenadas a una
**cuadrícula de tablas con medidas fijas**. Primero junta en **grupos**
(`groups()`) lo que se toca o se encima, y lo que se encima con la caja de un
grupo; después reparte los grupos en franjas y columnas una y otra vez hasta que
cada uno queda solo, con los huecos medidos alrededor. Es un corte en
guillotina; el único arreglo que no lo admite es un molinillo, y ese no se deja
guardar.

Cada grupo sale de una de cuatro formas, y eso es lo que arregló cómo llegaba a
Gmail y a Outlook en el teléfono:

| Grupo | Cómo sale |
|---|---|
| Un texto o un botón solo | Su celda |
| Un rectángulo sin girar, con o sin texto encima, que llena el grupo | **Una celda de color**, sin imagen |
| Fotos o rectángulos sin nada encima | **Una imagen de verdad (`<img>`)**, fundida al doble |
| Fotos con texto o botones encima | **Un fondo de esa zona**, con el texto dentro |

- **La geometría son dos figuras: rectángulo y círculo** (un óvalo si la caja
  no es cuadrada). El rectángulo sale como celda de color cuando llena su
  grupo; **el círculo no puede**, porque Outlook de escritorio ignora
  `border-radius` y lo dibujaría cuadrado, así que se pinta en la imagen del
  grupo. Eso tiene un costo que conviene saber: un círculo viaja como imagen y
  suma a la mitad de superficie que la revisión permite. Una línea no hace
  falta: es un rectángulo delgado.
- **Las fotos y las figuras giran** (`rot`, en grados y hacia la derecha, como
  en CSS); **el texto y los botones no**, porque girarlos obligaría a
  convertirlos en imagen y ahí se pierden `*|NOMBRE|*`, la lectura con las
  imágenes bloqueadas y los 300 caracteres de texto real que pide la revisión.
  Para el efecto de siempre queda **una figura girada detrás del texto
  derecho**. El giro se hornea en la imagen del grupo (`_paint()` gira con
  Pillow al revés que CSS, que cuenta al contrario).
- **La caja que se arrastra no cambia al girar; la huella sí** (`bounds()`), y
  es la huella la que decide qué se encima con qué, qué se sale de la hoja y
  cuánta superficie es imagen. Por eso **girar junta cosas**: lo que toque esa
  huella cae en el mismo grupo y sale como una sola imagen, que es justo lo que
  hace que una foto torcida sobre una banda de color salga bien.
- **Una foto es un `<img>` y no un fondo.** Antes cada foto era el fondo de su
  diapositiva: en Gmail del teléfono el fondo se escalaba por su cuenta y la
  foto salía corrida respecto al texto. Un `<img>` en su celda baja con lo de
  arriba si algo crece.
- **El fondo del texto sobre una foto mide exactamente su celda**, a una
  resolución y no al doble, para que ningún lector tenga que escalarlo. Debajo
  lleva **el color promedio de la foto** (`shades`), que es lo que se ve si no
  carga: el texto blanco se sigue leyendo. Para Outlook de escritorio va en VML,
  solo en esa zona.
- **El botón lleva su versión VML** (`v:roundrect`) para Outlook de escritorio,
  que es lo único que dibuja con sus esquinas, su color y su letra; los demás
  leen el enlace. Dentro de un fondo VML no, que Outlook dibuja mal un VML dentro
  de otro. **La letra del texto se repite en un `<span>`**, porque dentro de un
  fondo VML Outlook ignora la de la celda.

**Los textos y los botones son texto de verdad**: es lo que evita que el correo
se lea como una foto (de lo que más va a spam), lo que deja funcionar `*|EDAD|*`
y lo que se sigue leyendo con las imágenes bloqueadas. Por eso **no se deja
encimar un texto sobre otro ni sobre un botón**, y **una foto con enlace no
puede tener nada encima**: fundida con otra cosa, el enlace sería de toda la
imagen. El editor los marca en rojo y el servidor no guarda.

**El modo oscuro no cambia los colores del diseño.** Outlook en el teléfono y en
la web «corrige» colores en oscuro: el texto blanco sobre una foto salía gris
oscuro y un botón negro se quedaba sin fondo. Cada color lleva una clase
(`pmc-FFFFFF` la letra, `pmb-000000` el fondo) y `canvas.dark_css()` escribe en
la cabecera una regla por color con `[data-ogsc]` y `[data-ogsb]`, que es lo que
Outlook respeta. El sobre (`email_templates/_wrap.html`) dice además
`color-scheme: light`, para el iPhone. Gmail en oscuro invierte todo y eso no se
puede evitar.

**El sobre tampoco deja que el teléfono agrande la letra**
(`-webkit-text-size-adjust:100%`): el texto crecía y se salía de su sitio. **Sin
`viewport` ni `x-apple-disable-message-reformatting`, a propósito**: el correo
mide 600 fijos, y con ellas el teléfono dejaría de achicarlo y saldría cortado.

**El servidor no se fía del JSON**: `parse()` lo rehace con solo lo que conoce y
`problems()` exige fuentes de la lista (`FONTS`: las ocho de siempre más
Palatino, Garamond, Lucida Sans y Century Gothic, cada una con un respaldo
dentro de las ocho, porque en Android no están). **No se importan fuentes**:
Gmail y Outlook ignoran `@font-face`, así que la letra subida se vería en el
editor y en Apple Mail, y en los demás caería a otra de medidas distintas que
se sale de su celda; para la letra de la marca queda un titular como imagen con
su texto alternativo. Además exige letra de 14 a 72 px, colores `#RRGGBB`,
enlaces `https://` o `mailto:`, **la huella de cada cosa dentro de la hoja** e
imágenes de esa cuenta. El texto se guarda como texto y sale
escapado. La vista previa usa el mismo `to_html()` que el envío, con las
imágenes dentro de la respuesta para no guardar nada por mirar.

**Las fotos del lienzo se guardan a 1200 px** y cuentan contra el tope de 20; **las
imágenes de los grupos no** (`kind: "background"` en `images`, el nombre es de
cuando eran fondos): las hace el sistema. Se guardan en `backgrounds` y sus
colores en `shades`, en el orden de `groups()`. Al volver a guardar, las viejas
se borran si ninguna otra pieza las nombra, que es lo que pasa con una copia.

**La foto se recorta sin tocar el archivo subido.** «Recortar» abre la foto
entera con un recuadro encima: lo de dentro es lo que se ve. Se guarda como
`crop` (x, y, ancho y alto, de 0 a 1) en la pieza, así que se puede cambiar
mañana, y `_paint()` recorta antes del ajuste que ya hacía. **El recuadro
guarda la proporción de la caja**, así que lo que se ve nunca sale deformado:
solo más cerca o más lejos. Antes no había manera: al tirar de una esquina
hasta el borde de la hoja, el ancho se recortaba y el alto no, la caja cambiaba
de proporción y la foto se veía estirada; ahora el alto sigue al ancho.

**Al subir una foto se recortan sus bordes transparentes** (`imaging.trim()`): un
logo exportado con aire alrededor ocupaba una caja más grande que lo que se ve.
Entra **debajo de lo último, a la mitad del ancho**, para poder moverla y poner
otra al lado. **Las esquinas la agrandan sin deformarla y los lados la
recortan**, así que la caja siempre abraza la foto; la proporción se guarda en
`r`. «Ancho completo» la estira a 600 con su proporción. Lleva **enlace**
opcional y **descripción**, que va en el `alt`: es lo que se lee con las imágenes
bloqueadas.

El formato va **por caja de texto entera**: una caja es toda de la misma fuente,
tamaño y color. Formato por palabra complica que llegue igual a Outlook.

**Los atajos del teclado viven detrás de un botón** («Atajos del teclado», un
`<details>`, así que abre sin JavaScript) y salen de una sola lista,
`i18n.CANVAS_KEYS`: antes eran una línea suelta que no cabía y que se quedaba
vieja cada vez que se agregaba uno.

**La vista previa se ve con un contacto de verdad o con las pastillas**, y como
en una computadora o como en un teléfono (el correo achicado a 375 px, que es lo
que hace Gmail). El contacto se busca con la cuenta en la consulta: el de otra
no encuentra nada. Las dos cosas están también en el editor de HTML
(`templates/designs/_preview_tools.html`).

### Solo se guarda lo que tiene pinta de llegar a la bandeja

`canvas.review()` es una revisión **que bloquea**: con cualquier motivo en la
lista, el servidor no guarda y el botón de Guardar no se deja pulsar. Mira lo que
más manda a spam:

| Regla | Límite |
|---|---|
| Texto de verdad | Al menos 300 caracteres |
| Imágenes | Como mucho la mitad de la superficie (encimadas cuentan una vez; un rectángulo de color no cuenta) |
| Peso del correo armado | Debajo de los 102 KB, donde Gmail lo corta |
| Enlaces de botones e imágenes | Como mucho 8 |
| Acortadores (bit.ly y compañía) | Ninguno |
| Mayúsculas | Menos del 30 % de las letras |
| Signos repetidos (`!!`, `??`) | Ninguno |
| Palabras gancho («gratis», «ganaste», «haz clic aquí»…) | Ninguna |

No es una garantía: la bandeja la deciden la reputación del dominio y lo que
hace cada destinatario, no el correo. Es quitar lo que se sabe que resta.

**La misma revisión corre mientras se trabaja**, en `POST
/plantillas/lienzo/revisar`, que devuelve la lista y **el peso del correo tal
como sale** —con el pie de la baja y las imágenes—. El editor lo dibuja como una
barra de cuánto queda antes de los 102 KB, en ámbar pasado el 70 % y en rojo
pasado el 90 %.

## Las plantillas prediseñadas

**Ya no se ofrecen.** Las piezas que alguien armó con ellas siguen en su lista y
se editan con el formulario de siempre (`/plantillas/pieza/<id>`); empezar una
nueva ya no se puede. Lo de abajo describe cómo funcionan esas piezas.

Cuatro, en `backend/email_templates/`, en el HTML que entienden los lectores de
correo —tablas y estilos en línea—:

| Plantilla | Para qué | Qué llena el cliente |
|---|---|---|
| **Aviso** | Un corte, un plazo, un recordatorio de pago. Sin imagen. | Título, texto y un botón opcional |
| **Anuncio** | Una oferta o una novedad | Título, imagen, texto, botón |
| **Boletín** | Varias noticias en un correo | Título y de dos a cuatro bloques |
| **Convocatoria** | Una asamblea o un evento | Título, imagen, fecha, hora, lugar, texto, botón |

**Cada archivo declara arriba sus campos y su nombre**, así que la pantalla
dibuja su formulario sola y no hay una lista de campos escrita aparte que un día
diga otra cosa que el archivo. Agregar la quinta es dejar caer un archivo; lo
único que se escribe fuera es la línea que explica para qué sirve, en `i18n.py`,
y sin ella se ofrece igual. Las que empiezan por guion bajo no se pueden elegir:
son el sobre.

### Escribir el dato de cada quien

Dentro de una pieza, `*|CIUDAD|*` se cambia por lo que dice ese contacto al
armarle **su** correo, en `services/sender.py`. El asunto también, que es lo
primero que se lee. Lo hace `services/fields.py` y no Jinja: **el HTML de un
cliente no puede pasar nunca por el motor de plantillas del panel**, que sería
dejar que un archivo subido ejecute código en el servidor. Por eso la marca es
esa y no `{{ }}`; además no choca con las llaves del CSS de nadie.

El valor va **escapado** dentro del correo —lo escribió otro y el HTML de
alrededor es nuestro— y sin escapar en el asunto, que es texto. Una marca que
nombra una columna borrada se queda en blanco: dejarla a la vista sería mandar
`*|CIUDAD|*` a mil personas.

**`*|NOMBRE|*` y `*|CORREO|*` existen siempre**, en todas las cuentas: son el
nombre y la dirección que trae todo contacto (`fields.BUILT_IN`). Por eso
ninguna columna propia puede llamarse así. A una persona sin nombre le llega
ese hueco en blanco: «Hola ,». Conviene escribirla donde un hueco no estorbe.

La vista previa dibuja cada marca con **el nombre de su columna** —«Ciudad»—,
que enseña dónde va cada dato sin inventarse un valor que después no se parezca
al de nadie. **Va en una pastilla celeste** (`fields.preview_fill()`), para que
se vea de un vistazo qué cambia en cada correo; dentro de un atributo, como un
enlace, va el nombre solo, sin pastilla, que la rompería. La pastilla es solo de
la vista previa: lo que sale lleva el dato tal cual.

**`services/render.py` es el único sitio que arma un correo**, y la vista previa
llama ahí, así que lo que alguien ve antes de mandar es de verdad lo que se
manda. Pone, por este orden: lo que escribió el cliente **escapado** —un
`<script>` en el título sale como texto—, el botón de anular la suscripción, la
dirección postal **de la cuenta** si ya la escribió, y la marca de agua solo si
el plan la lleva. Las tres van fuera de la pieza, que es lo que hacen las reglas 3 y 4
ciertas: el cliente no las puede quitar editando lo suyo, y la marca desaparece
sola al subir de plan porque nadie la copió a ningún sitio.

**La vista previa se dibuja en un marco aislado**, con `sandbox` y con su propia
cabecera de seguridad —un correo necesita justo lo que el panel prohíbe: estilos
en línea e imágenes de otro dominio—. El HTML es nuestro, pero el texto de
dentro es de otro y esa página lleva una sesión abierta. El formulario entero
entra en ese marco al pulsar el botón, así que ver cómo queda no guarda nada ni
pierde lo escrito.

### Las imágenes

**Se guardan en la propia base**, en la colección `images`, y las sirve el panel
en `/img/<nombre>`. No pueden viajar dentro del correo —pegadas dentro pesan
megas y Gmail recorta a los 102 KB, y lo que se pierde es el pie con el botón de
la baja—, así que van fuera y el correo trae su dirección.

Hubo un almacén aparte (Cloudflare R2) y se quitó: pedía dejar una tarjeta en un
servicio que se cobra por uso y no tiene tope duro de gasto. El costo real habría
sido mínimo, pero para lo que hace falta aquí no compensa depender de una factura
variable, y **esto no necesita ninguna variable de entorno ni ningún proveedor
nuevo**.

Lo que hace que guardarlas en la base salga barato es que **se achican al
entrar** (`services/imaging.py`, con Pillow): una foto de teléfono son tres o
cuatro megas y las plantillas la dibujan a 600 píxeles de ancho, así que lo
guardado son unos 120 KB. Sin ese paso habría que rechazar casi cualquier foto,
que es justo lo que dejaría la pantalla inservible para quien solo tiene la que
acaba de tomar.

- **Se acepta o se rechaza por lo que trae dentro el archivo, no por su
  nombre**: JPG, PNG, GIF y WebP, hasta 5 MB de entrada. Sale JPEG, o PNG si
  tiene transparencia. El **GIF se guarda tal cual** si viene liviano, porque
  achicarlo le quitaría la animación.
- Se le pone tope de píxeles a Pillow y se atrapa su aviso de bomba: un PNG de
  40 KB puede descomprimirse a varios gigabytes.
- **El campo de la pieza guarda el nombre del archivo, no una dirección.** La
  dirección entera se arma al dibujar el correo, en `services/render.py`. Así la
  pieza no se rompe si cambia el dominio, y **no hay forma de colar una imagen
  de fuera** escribiendo en el campo escondido del formulario: lo que se acepta
  es un nombre que tiene que existir y ser de esa cuenta.
- **Borrar la pieza borra sus imágenes**, y hay un tope de 20 por cuenta. Ese
  tope es también lo que acota lo que puede quedar huérfano: una imagen subida
  y nunca guardada en ninguna pieza no la borra nadie.

### `images`
Una imagen de una plantilla, ya achicada, con la cuenta de quien la subió y su
nombre. **El nombre es aleatorio y es la dirección**: no se usa el `_id`, que
lleva la hora dentro y va casi en orden, porque con él quien tuviera una
dirección podría recorrer las de los demás. Y lleva la extensión pegada, porque
Cloudflare mira la extensión para decidir si guarda una respuesta en su borde;
sin eso, cada apertura de cada correo llegaría hasta el servidor.

`/img/<nombre>` es **la única dirección del panel que no pide sesión, y tiene que
serlo**: quien la abre no es el cliente, es el lector de correo de cada persona
que recibió la campaña. Va en su propio blueprint (`blueprints/media/`) y no en
el de plantillas, que exige sesión y devuelve los administradores a `/admin`. La
respuesta se puede guardar un año: cambiar una imagen es subir otra, con otro
nombre, así que lo cacheado no puede quedar viejo.

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

Es lo que dibuja «Campañas enviadas» en `/envios` y las líneas de correo de la
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

### `mail_log`
Un documento por cada **correo del sistema** que se intentó enviar, con el
cuerpo completo: destinatario, asunto, backend usado, `sent` o `failed`, el
error si falló, el HTML y el texto tal como salieron. Es lo que permite
responder qué salió del servidor cuando alguien dice que no le llegó la
confirmación. No cubre campañas de clientes, que llevan su propia contabilidad.

**`outcome` es lo que Amazon dijo después**: `delivered`, `bounced`,
`soft_bounced`, `complained` o `rejected`, con el motivo en `outcome_detail`.
Se encuentra la fila por `provider_id`, el identificador que SES devolvió al
enviar. Lo enseña **Administración → Correos del sistema**, buscando por
dirección.

### `auth_events`
Un documento por cada intento de registro, entrada, reenvío, confirmación y
salida: `kind`, `outcome`, la dirección, `account_id` cuando se conoce, IP y
navegador. **La contraseña no se guarda nunca, en ninguna forma.**

Las dos son internas, solo las lee el admin, y **ninguna tiene TTL**: el
historial se conserva hasta que se decida otra cosa. `auth_events` registra la
verdad, `already_registered` incluido; la regla 7 gobierna lo que se le dice al
visitante, no lo que la plataforma sabe de su propio tráfico.

---

## Reglas que no se pueden violar

1. **Antes de enviar a cualquier dirección, verificar `suppressions`.** Los
   suprimidos se saltan y **no consumen cuota**.
2. **Borrar un contacto no borra su supresión.** Reimportarlo no lo reactiva.
3. **El enlace de baja se inyecta al enviar, no al guardar el HTML** — así el
   cliente no lo puede quitar. Es único por destinatario (con token). Va en
   todos los planes, sin excepción, más la cabecera `List-Unsubscribe`.
4. **La marca de agua "Enviado con Panamails" se inyecta al enviar, solo en el
   plan Básico**, con el ala de la marca al lado (`static/img/email-logo.png`,
   que genera `build_assets.py` desde `brand/logo/logo.png`, en PNG porque Gmail
   y Outlook no dibujan SVG). Al subir de plan desaparece sola, y Negocio y
   Empresa no llevan ninguna mención. No la exige ninguna ley: es publicidad.
5. **Los contactos no se duplican.** Toda importación es un upsert sobre
   `{account_id, email_normalized}`.
6. **De los tokens de correo solo se guarda su hash**, nunca el valor que va
   en el enlace, y valen una sola vez y con vencimiento.
7. **Entrar y recuperar la cuenta nunca revelan si una dirección tiene cuenta.**
   Las dos responden igual exista o no, para que ninguna sirva de buscador de
   clientes. **El registro sí lo dice**: esconderlo dejaba a la persona
   esperando un código que no iba a llegar. El aviso al dueño se manda igual,
   con su propio límite por dirección para que el formulario no sirva para
   llenarle el buzón a nadie.
8. **Los correos del sistema son transaccionales**: sin enlace de baja y sin
   marca de agua. Las reglas 3 y 4 son solo para campañas de clientes.
9. **Nunca guardar datos de tarjeta.** El pago se hace en el checkout hospedado
   del proveedor; la tarjeta no toca el servidor ni la base de datos.
10. **Toda escritura de contactos usa `bulkWrite`**, y las supresiones se
   consultan en lote con `$in`. Nunca una consulta por contacto.

---

## Envío

Todos los clientes envían desde un subdominio de Panamails; **no se les exige
configurar DNS** porque la mayoría no tiene dominio propio:

```
De:        Tu Empresa <tuempresa@envios.panamails.com>
Responder: tuempresa@gmail.com
```

Al cliente que sí tiene dominio, Luis le configura el DKIM durante la
activación (opcional, mejor entregabilidad).

Como todos comparten el dominio, **la reputación es una sola** y las defensas
automáticas son la única protección:

| Métrica de una cuenta | Acción automática |
|---|---|
| Rebotes > 3% | Pausa de envío y aviso (AWS actúa a 5%) |
| Quejas > 0.05% | Pausa de envío (Gmail y Yahoo actúan a 0.1%) |
| Primera campaña | Tope reducido las primeras 48h, sin importar el plan |

Usar **tenants de SES** para aislar reputación y supresión por cliente.

Requisitos de remitente masivo que aplican a Panamails (no a sus clientes), al
pasar de 5,000 correos diarios sumando todos: DMARC publicado en
`panamails.com`, SPF y DKIM, baja de un clic procesada en menos de 2 días, y
tasa de quejas agregada bajo 0.1%.

---

## Flujo de campaña

```
1. Elegir plantilla prediseñada  ó  subir HTML propio (Negocio en adelante)
2. Escribir asunto y contenido
3. Elegir la lista destinataria
4. Vista previa + enviar correo de prueba a su propia dirección
5. Enviar ahora  ó  programar fecha y hora
```

Los envíos programados, las importaciones grandes y la reanudación de campañas
pausadas corren en un **proceso en segundo plano**, no dentro del request.

### HTML subido por el cliente

Hecho, en `/plantillas` y en la colección `designs`. Ver esa sección más arriba:
qué se rechaza, quién puede subir y quién aprueba la primera.

### Límites de importación

| Límite | Valor |
|---|---|
| Importaciones por día | 10 por cuenta |
| Filas por importación | El límite de contactos del plan |
| Tamaño de archivo | 5 MB |
| Importaciones simultáneas | 1 por cuenta |

Procesar el CSV **en streaming**, nunca cargarlo entero en memoria.

**Un contacto nuevo solo entra con todas las columnas de la cuenta llenas.** El
resultado dice cuántos se quedaron fuera por venir incompletos. A los que ya
existían se les actualiza lo que traiga el archivo, columna a columna: traer la
ciudad no le borra el monto a nadie.

**El archivo no manda.** Uno de quince columnas se acepta igual: la pantalla
enseña sus títulos y el cliente marca cuáles guardar, y es **lo que marca** lo
que cuenta contra el límite del plan. Rechazar el archivo entero por traer
columnas de más dejaría fuera a cualquiera que exporte de su sistema.

Ese mapeo lo dibuja `panel.js` leyendo la primera línea en el propio navegador,
así que el archivo no se sube dos veces ni se guarda mientras alguien decide.
**Sin JavaScript la importación sigue funcionando**: el servidor casa los
títulos del archivo con las columnas que la cuenta ya tiene. Lo que se pierde es
poder crear una columna desde ahí, y eso es a propósito: crear una columna es
una decisión, no un efecto secundario de subir un archivo. El servidor vuelve a
leer la cabecera y no se fía de nada de lo que mande la pantalla.

---

## Panel del cliente

**Al entrar, se aterriza en el sitio público**, que es la portada, y desde ahí
se elige con el menú de siempre. **Administre o no**: una sola regla para el
mismo momento. Antes un cliente caía en Estadísticas y un administrador en
`/admin`, que son dos pantallas concretas, y la diferencia se notaba justo al
saltar entre cuentas abiertas —una te dejaba en un sitio y la otra en otro—. Lo
decide `landing()` en `blueprints/auth/routes.py`, y como devuelve una dirección
de otro dominio, es lo que obliga a nombrar el sitio en `form-action`.

Volver **desde dentro** del panel es otra cosa y tiene su propia función,
`inside()`: de una pantalla del panel se vuelve a otra del panel, no al sitio.

**Lo primero que ve una cuenta nueva es `/bienvenida`, no el panel.** Confirmar
el registro aterriza ahí: el nombre de la persona, que su cuenta está lista, y
dos botones —ver los planes, que están en el sitio público, e ir a
Configuración—. Antes se caía directo en Estadísticas, que sin plan contratado y
sin un solo envío es un cuadro vacío diciendo que todavía no ha pasado nada: la
peor primera pantalla posible.

Esa dirección se queda en el historial, así que lleva dos guardas que **no son
para el día del registro**, donde no pueden darse: con un plan ya contratado
manda al panel, y a un administrador lo devuelve a `/admin`.

**`/panel` es la pantalla de Estadísticas.** La dirección no cambió aunque la
pantalla se llame así: cambiarla rompería los enlaces guardados y el correo de
bienvenida a cambio de nada. **Solo enseña envíos**: los contactos, las
importaciones y el plan tienen sus propias pantallas y salieron de aquí. Tiene
cuatro partes, con filtro por periodo, por etiqueta y por **campaña**:

- **«Cómo le fue»**: enviados, y el porcentaje de entregados, rebotes,
  aperturas, clics y quejas, **en personas** (`events.people()`, la misma
  cuenta que «Campañas enviadas»). Entregados y rebotes sobre lo enviado; lo
  demás sobre lo entregado. Debajo, fijo, que las aperturas son aproximadas y
  que entregado no es la bandeja.
- **Cada cifra lleva su pastilla contra el periodo anterior**, del mismo largo
  y pegado a él, **sea cual sea el periodo puesto**: las últimas 24 horas
  contra las 24 de antes, hoy contra ayer hasta la misma hora, los 90 días
  contra los 90 anteriores (`events.window(period, back=1)`, que sale de
  `slots()` y por eso corta en la zona de quien mira). La nota de abajo nombra
  el periodo elegido (`stats_before_*`): decía «los 7 días» siempre y se leía
  como si solo comparara eso. **El color dice si
  mejoró, no si subió**: más rebotes o más quejas van en rojo con la flecha
  hacia arriba (`stats.WORSE_UP`). Los enviados se comparan en cuántos y el
  resto **en su proporción exacta, sin el redondeo que se enseña**: con el
  12.5 % de rebotes redondeado a 12, un 25 % se leía como «+108 %» en vez de
  como el doble que es. Donde antes no hubo envíos no hay con qué comparar y no
  se dibuja pastilla, en vez de inventar un «+100 %».
- **Envíos y rebotes**, en barras apiladas, y **aperturas y clics**, en líneas.
  **También en personas**: quien abre tres veces el mismo envío es una
  apertura, en el tramo en que abrió por primera vez. Antes la gráfica contaba
  eventos y no cuadraba con «Cómo le fue».
- **Correos de este mes**, al final: lo gastado de la cuota del plan
  (`sent_counts` contra `docs/pricing.md`) en una barra, ámbar desde el 80 %
  (cuando se avisa) y roja al 100 %. **No dice cuándo se renueva**: todavía no
  hay renovación automática, y una fecha haría pensar que sí. Sin plan lo dice
  y enlaza a /planes. Es un SVG y no un ancho en `style`, que la cabecera
  del panel no deja.
- Cada gráfica lleva **la escala a la izquierda** (números redondos,
  `stats.nice_top()`), **el eje del tiempo abajo** y **un cuadrito por tramo**
  al pasar el ratón, tocar o enfocar con el teclado, que se abre solo con CSS.
- **Bajas**, que hasta ahora no estaban en ningún lado: salen de
  `suppressions` por fecha (`count_between()`), no de `events`. **Con un filtro
  de etiqueta o de campaña puesto no se dibujan**: el enlace de baja firma el
  contacto y no la campaña (`services/unsubscribe.py`), así que no se pueden
  atribuir, y enseñar las de toda la cuenta como si fueran las del filtro sería
  mentir. La pantalla dice por qué faltan.
- **Tus mejores campañas**: los envíos del periodo ordenados por aperturas, con
  enlace a su «Detalles». Sus cifras salen de `events.counts_by_run()`, la
  misma consulta de «Campañas enviadas», así que las dos pantallas no pueden
  decir cosas distintas.
- **Enlaces más pulsados**: qué enlace pulsó más gente. SES manda la dirección
  dentro del aviso de clic y se guarda **en el mismo evento** (`links`, con
  `$addToSet`), no en uno nuevo: el clic sigue siendo uno por envío y persona.
  Solo cuenta desde que esto existe, y la pantalla lo dice.
- **Cuándo abren tus correos**, por día de la semana y por hora, en la zona de
  quien mira: **siempre los últimos 90 días**, sin el filtro de periodo, porque
  con «la última hora» puesta no diría nada.
- **Crecimiento de la lista**: altas y bajas por mes, los últimos doce. No es el
  total de cada mes: **borrar un contacto a mano no deja rastro**, y las bajas
  cuentan todas las supresiones, no solo el enlace de baja.
- **Bajarse lo que se está viendo**, en CSV y en PDF
  (`blueprints/analytics/`, que llevaba vacío desde el primer día aunque
  `docs/pricing.md` lo promete en los tres planes). Las dos rutas llaman al
  mismo `stats.screen()` con los filtros de la dirección, así que el archivo y
  la pantalla no pueden decir cosas distintas. El CSV va con punto y coma y BOM,
  como el de contactos; el PDF lo arma `reportlab`. **Solo para el cliente**: el
  administrador mira las cifras de quien elija, y bajarse su archivo es otra
  decisión.

**Seis periodos**: la última hora (cada 5 minutos), hoy (por hora desde la
medianoche), 24 horas, 7 y 30 días (por día) y 90 días (por semana). **Los
tramos se cortan en la zona del dispositivo** (`events.slots()`): un día empieza
a medianoche de quien mira y no a la de UTC.

**El filtro por etiqueta mira los envíos y no los eventos**, que no la llevan:
un evento es de un envío (`run_id`) y el envío guarda a qué etiquetas salió.
Antes buscaba la etiqueta en el evento y no filtraba nada. **El de campaña** sale
de `campaign_runs`, así que aparecen también las borradas que tienen envíos; una
campaña de otra cuenta en la dirección no filtra por nada.

**Son SVG generado en la plantilla, sin librerías**: la cabecera del panel solo
deja cargar guiones propios. **Todo lo que es texto va fuera del SVG**, que se
estira a lo ancho; el eje es una fila de casillas del mismo ancho que las barras,
y los puntos de las líneas son líneas de largo cero con la punta redonda y trazo
que no se escala, para que no salgan ovalados. Sin datos se dibujan igual, con
la frase de que aún no ha pasado nada.

La llena `services/stats.py`, y **es la misma pantalla que ve el
administrador** en `/admin/` para la cuenta que elija: una plantilla y dos
entradas, para que no puedan separarse. **`/contactos`** tiene cinco
pantallas: la lista —una fila por contacto: su correo, su nombre, **sus
columnas propias**, si está activo, anulado o incompleto, sus etiquetas y
cuándo entró—, la importación, las etiquetas, las columnas propias y las
supresiones. Agregar uno a mano tiene su propia pantalla, a la que se llega
desde un botón encima de la lista, y exportar pasa por una confirmación que dice
cuántos van a salir. **Borrar también pregunta**: el botón de cada fila, y el de
eliminar los anulados, llevan a una pantalla que dice cuántos se van y tiene el
botón rojo; el que borra es el POST. **`/plantillas`** tiene arriba crear y cargar, y debajo
todas las piezas de la cuenta: las del lienzo, las cargadas en HTML y las
prediseñadas que quedaron de antes. Y todo lo demás vive en **`/configuracion`**, con cuatro secciones:
**Cuenta** (datos, estado y plan), **Seguridad** (contraseña, autenticación de
múltiples factores, dispositivos conectados y **los usuarios de la cuenta**),
**Notificaciones** y **Facturación**
(`/configuracion/pagos`, que no cambió de dirección porque ahí vuelve PayPal):
el plan con su fecha exacta, los métodos de pago que hay y el historial de
compras (una fila por pago cobrado). Los métodos son hoy solo la lista; ahí se
guardará el de cada cuenta el día que haya cobros recurrentes. **Las facturas están hechas pero escondidas** (`invoices.SHOWN`,
en `False`): ni se enseñan al cliente ni se suben desde administración, y
encenderlas es cambiar esa línea. No hay botón para cancelar la renovación
porque no hay cobro automático; va el día que lo haya.

**Configuración va sin frases de relleno.** Cada fila dice su nombre y, solo si
hace falta, una línea: que cambiar la contraseña cierra las demás sesiones, y
el tipo de autenticación de múltiples factores. Los avisos de seguridad, que no se pueden
apagar, salen en Notificaciones con su interruptor **encendido y bloqueado**, sin
una etiqueta que lo diga. **Los avisos de lo que todavía no existe
(importaciones, campañas y el resumen mensual) no se ofrecen**
(`accounts.PENDING`): un interruptor de algo que no manda nada es dejarlo a
medias. Sin interruptor valen «sí», así que el día que empiecen a salir llegan
solos; ofrecerlos es sacarlos de esa tupla.

### La hora de quien mira

**Todo se guarda en UTC y todo se escribe en la zona del dispositivo de quien
mira** (`services/clock.py`). El guion de la cabecera del panel escribe la
galleta `pm_tz` con la zona del navegador; la primera página de un dispositivo
nuevo todavía no la trae y sale en hora de Panamá. `on_date` y `at_moment` la
usan, las gráficas cortan sus tramos en ella, y **una hora escrita para
programar una campaña se lee en ella** —antes se tomaba como UTC, y las 3 de la
tarde de Panamá quedaban para las 10 de la mañana—. La cuenta guarda la última
zona vista en `time_zone`, que es la de los correos que le llegan sin estar
mirando. Lo relativo («hace 2 horas») no depende de la zona.

La barra de arriba lleva el logo, el nombre de la empresa y un desplegable con
las mismas cosas en el sitio público y en el panel, en este orden: panel,
enviar correos, contactos, plantillas, configuración, modo, idioma, cambiar de
cuenta y cerrar sesión. Las
plantillas van debajo de contactos: primero a quién le escribes, después con qué.
**A un administrador el menú le enseña administración de primera y después
configuración, y nada más.** El sitio público sí le sigue enseñando las filas de
cliente, porque solo lee una galleta que dice «hay sesión» y no sabe quién es
—ponerle el rol sería publicar en el dominio padre quién es administrador—, pero
pulsarlas lo deja en `/admin`. El idioma es un desplegable dentro del desplegable, no
dos filas sueltas de algo que casi no se toca. **El panel va primero** porque es a
lo que se dedica la empresa; lo demás son ajustes, y se buscan cuando hacen
falta. Sin sesión el mismo control es un botón de tres líneas con las dos que
sirven sin cuenta.

**El modo claro u oscuro viaja entre los dos sitios en la galleta `pm_theme`**,
en `.panamails.com`. El sitio y el panel son dos orígenes y cada uno tiene su
propio almacenamiento, así que guardarlo solo ahí dejaba el panel en claro
después de elegir oscuro en el sitio. El guion de la cabecera de los dos mira
primero la galleta; lo que alguien eligió antes de que existiera se copia a ella
la primera vez que abre cualquiera de los dos.

**El idioma está anunciado, no traducido.** El menú enseña «Español» y «Inglés
(pronto)»; el inglés se hará cuando haya a quién dárselo.

**Salir cuesta un clic desde los dos sitios.** El sitio público está en otro
dominio y no lleva ningún testigo del panel, así que su «Cerrar sesión» no puede
ser un formulario: es un enlace, y un enlace es un `GET /salir`. Ese GET cierra
igual que el POST del menú del panel, y por eso no se le pide testigo.

Lo único que no obedece es una petición que el navegador **dice estar
adelantando** —`Sec-Purpose`, `Purpose` o `X-Moz` con `prefetch`—: sin eso, un
navegador que precarga enlaces sacaría a alguien de su cuenta sin que hubiera
pulsado nada. Se cierra por omisión y se calla solo ante esa cabecera; si un
intermediario se la comiera, lo que se pierde es la protección y no el salir.
`logout.html` sigue existiendo, pero solo la ve esa precarga.

### Varias cuentas abiertas a la vez

**«Cambiar de cuenta», encima de salir, lleva a `/cambiar-cuenta`**: la lista de
las cuentas que este navegador tiene abiertas, para saltar de una a otra sin
escribir ninguna contraseña. Existe porque quien administra prueba con varias
—un cliente, otro cliente, el administrador— y antes eso era salir, buscar el
botón de entrar y volver, cada vez.

**Son sesiones de verdad y no un truco.** Cada una tiene su documento en
`sessions`, con su dispositivo, su última visita y su vencimiento, y sale en
Seguridad como cualquier otra; si la cierran desde otro dispositivo, desaparece
de la lista sola. Lo único que comparten es la galleta firmada, que guarda sus
testigos en `sids` además del de la activa en `sid`. **Caben cuatro**, porque eso
viaja en una galleta y porque nadie necesita más.

Tres cosas que sostienen esto:

- **Agregar una cuenta pasa por la pantalla de entrar completa**, con su
  contraseña y su segundo paso: `/entrar?agregar=1`. Aquí no se abre ninguna
  puerta que no estuviera ya abierta. La marca de «vengo a agregar» vive en la
  sesión y no en la dirección, porque el segundo paso pasa por otra pantalla.
- **Y se puede crear una cuenta nueva sin cerrar la abierta**, por el mismo
  camino: el pie de esa pantalla lleva a `/registro?agregar=1`, que se dibuja en
  vez de devolver a la portada, y al confirmar el código la cuenta nueva se suma
  a las abiertas. Ahí el pie tampoco dice «¿todavía no tienes cuenta?», que
  estando dentro de una es mentira.
- **«Olvidé la contraseña» mientras se agrega una cuenta es de la que se está
  agregando**, no de la que ya está abierta. La pantalla de recuperar, estando
  dentro, no pregunta la dirección porque ya la sabe; con la marca de agregar
  puesta sí la pregunta, porque la contraseña olvidada es la de otra. Y al
  terminar, las cuentas que ya estaban abiertas siguen abiertas.
- **En la lista nunca se dibuja un testigo.** Los formularios mandan el
  identificador de la cuenta; el testigo se queda en la galleta. Dibujarlo sería
  escribir la sesión dentro del HTML.
- **La lista se limpia sola al leerla**: lo cerrado, lo vencido y lo de una
  cuenta suspendida se caen antes de enseñarse, así que la pantalla no ofrece
  una puerta que no abre.

**«Cerrar sesión» las cierra todas**, y eso es a propósito: en una computadora
prestada, salir tiene que significar que no queda ninguna cuenta abierta. Para
dejar solo una hay un botón por fila en esa misma pantalla. Entrar sin
«agregar» también cierra lo que el navegador tuviera abierto: una sesión viva
cuyo testigo ya nadie tiene sería una puerta suelta, y además aparecería en la
pantalla de dispositivos de su dueño.

Cerrar las sesiones de los **otros** dispositivos no se pregunta al salir: vive
en Configuración → Seguridad, que es su sitio.

## Panel de administración

`/admin`, con verificación de rol. **No es donde se aterriza al entrar** —eso es
el sitio público, para todos—: se llega desde el menú, que para esta cuenta
enseña Administración de primera fila. Sí es a donde la devuelve
`not_for_admins()` si abre una pantalla de cliente. Cuatro pantallas:
**Estadísticas · Cuentas · Plantillas subidas · Correos del sistema**.

**Correos del sistema** (`/admin/correos`) es la del «no me llegó el código»: se
escribe una dirección y sale cada correo que el panel le mandó, cuándo, cuál
era y qué dijo Amazon. Se busca por dirección y no desde una ficha porque quien
no recibe su código casi nunca llegó a tener cuenta. **No dibuja el cuerpo de
ningún correo**, que lleva códigos y enlaces de un solo uso.

**Estadísticas** es `/admin/`, y es la misma pantalla del cliente con un selector
de cuenta encima: lo que ve él, de quien elijas. Hubo una portada antes ahí, con
el conteo por estado y las últimas decisiones; se quitó porque lo que pedía
acción cabe en un filtro de Cuentas y lo demás ya está en la ficha.

**Cuentas** es la tabla con filtro y buscador. **Nunca trae cuentas de
administrador**: no son clientes, no compran ni envían, y como un administrador
no paga nunca se quedaban en «registrada» para siempre, que es lo que hacía que
la columna de estado se leyera mal. Su filtro de estado tiene una entrada más,
**«esperando habilitación»**, que no es un estado sino la cola que pide acción:
pagaron y todavía no pueden enviar.

Arriba del todo de la ficha está lo único que espera una decisión: **habilitar el
envío**. Debajo, **un solo formulario** —plan, ciclo, suspensión y un motivo—: si
cambian dos cosas se anotan dos líneas en `admin_events` con el mismo motivo,
porque guardar una por cosa cambiada es lo que las hace legibles meses después.
Ponerle el plan a mano llama al mismo `activate_plan()` que usa PayPal, así que
deja la cuenta activa **y con fecha de vencimiento**, no con un plan que no vence
nunca. Y tiene
una **Actividad** que junta en una línea de tiempo lo que hizo la cuenta —sus
entradas, sus importaciones, sus pagos, sus envíos— con lo que se decidió
sobre ella, leyendo `auth_events`, `imports`, `payments`, `campaign_runs` y
`admin_events`, con un desplegable para mirar una sola de las cinco. Los correos
son **una línea por envío**: la campaña que sale cada mes no es una cosa que
pasó una vez.

**Ese filtro vuelve a preguntar, no esconde filas.** De la mezcla se guardan las
sesenta más recientes, así que filtrar al dibujar enseñaría los pocos pagos que
sobrevivieron a ella.

**Agregar y borrar un contacto de uno en uno no queda escrito en ninguna
parte**, así que no se puede enseñar: de los contactos, la línea de tiempo
cuenta los archivos que importó.

**La ficha enseña cifras y orígenes, nunca la lista de direcciones de los
contactos de un cliente.** Cuántos tiene, cuántas supresiones, qué archivos subió
y de dónde dijo que salió cada lista: eso es operar la plataforma. Las
direcciones son suyas y de quien está en ellas, y se miran por un motivo
concreto —una baja que alguien pide, un abuso que se investiga—, no hojeando.

**Pendiente: la pantalla de gráficas.** El administrador elige un cliente y ve
lo mismo que ve él: correos enviados y rebotes contra el tiempo, con filtro por
periodo —las últimas 24 horas, por ejemplo— y por etiqueta. **No se puede hacer
todavía**: las colecciones `events` y `campaigns` no existen, así que no hay
envíos, rebotes ni aperturas guardados en ningún sitio. Se hace junto con las
campañas y el webhook de SNS, que es lo que las llena; antes de eso solo
dibujaría ceros y habría que rehacerla cuando se sepa qué forma tienen los
eventos de verdad. Sigue valiendo la regla de arriba: cifras agregadas sí, la
lista de direcciones de sus contactos no.

Pendiente además: revisar rebotes por cliente.

Además:

1. **Tasa de rebotes y quejas agregada en la portada** — la de Panamails, no la
   de cada cliente. Es la métrica que puede cerrar el negocio.
2. Estado de pagos y renovaciones (Yappy puede requerir cobro manual).
3. Envíos en curso, pausados y fallidos.
4. Ver el panel como el cliente, para soporte. Queda registrado.
5. Registro de actividad: aprobaciones, cambios de plan, pausas, con motivo.
6. Buscador global de direcciones, para suprimir a quien escriba pidiendo la baja.

---

## Los avisos de la cuenta

`services/notices.py` es el único sitio que los compone, y son doce:

| Correo | Cuándo sale | ¿Se puede apagar? |
|---|---|---|
| Contrataste el plan X | Al cobrar PayPal, y al ponerle el plan a mano | Sí, «Pagos y plan» |
| Renovaste el plan X | Igual, cuando el plan pagado es el que ya corría | Sí, «Pagos y plan» |
| Tu plan vence en 7 días | Al entrar al panel, si falta una semana o menos | Sí, «Estado de tu plan» |
| Tu plan venció | Al entrar al panel, si ya pasó la fecha | Sí, «Estado de tu plan» |
| Ya puedes enviar | Al habilitar el envío desde la ficha | No |
| Tu cuenta fue suspendida | Al suspenderla | No |
| Tu cuenta está activa otra vez | Al levantar la suspensión | No |
| Tu código para cambiar el correo | Al pedirlo, **a la dirección nueva** | No |
| Tu cuenta cambió de correo | Al terminar, **a la dirección vieja** | No |
| Alguien pagó y espera habilitación | Al cobrar | Sí, «Alguien pagó un plan» |
| Se registró una cuenta nueva | Al confirmar el correo | Sí, «Se registró una cuenta nueva» |
| A un cliente se le venció el plan | Cuando ese cliente entra al panel | Sí, «A un cliente se le venció el plan» |

**Los tres últimos van a quien administra**, no a un cliente, y hablan de lo
que pasa en las cuentas de los demás.

**Los tres del medio no llevan interruptor, y no por descuido.** «Ya puedes
enviar» pasa una vez por cuenta y es la respuesta a la única espera que se le
pide a un cliente. Los dos de la suspensión son la respuesta a «¿por qué no
puedo entrar?», y quien está suspendido no puede entrar a cambiar sus
preferencias, así que un interruptor no le serviría de nada.

**El de un plan vencido tiene el límite de dónde se mira**, que es el mismo del
aviso al cliente: se detecta cuando ese cliente entra a su panel, así que de
quien no vuelve a entrar no se entera nadie. Los dos salen del mismo vistazo y
se anotan con la misma marca, así que ninguno se manda dos veces por el mismo
vencimiento.

**El correo de suspensión no lleva el motivo que escribió el administrador.**
Ese motivo se redacta para `admin_events`, puede ser corto y duro, y lo que
necesita quien lo recibe es otra cosa: qué significa, que no se borró nada y a
dónde escribir.

**Los doce comparten un solo par de plantillas**, `email/notice.html` y `.txt`,
porque todos tienen la misma forma: un titular, unos párrafos, y a veces un
botón, un recuadro o un código de seis dígitos. Los siete correos anteriores —confirmación,
bienvenida, recuperación, dispositivo nuevo…— siguen teniendo cada uno el suyo;
podrían mudarse a este sobre, pero eso es otro cambio.

**Ninguno puede romper lo que estaba pasando.** Un correo que no sale no puede
hacer que un pago cobrado parezca fallido, así que el envío va envuelto y solo
deja una línea en el registro. Y como todos los del sistema, son
transaccionales: sin enlace de baja y sin marca de agua, que es la regla 8.

### Cómo se entera de que un plan venció

**Cuando la cuenta entra al panel, y hoy no hay dónde más.** No existe el proceso
en segundo plano que podría darse cuenta a las tres de la mañana, así que
`notices.plan_watch()` se llama al dibujar `/panel`.

Tiene el límite que se ve y conviene tenerlo presente: **solo le llega a quien
entra**, que es justamente quien menos lo necesita. El día que exista ese
proceso, es mover esta misma llamada; nada de esto se rehace.

Un plan que venció hace más de 30 días no dispara nada. Sin ese corte, al subir
esto las cuentas viejas de prueba habrían recibido un aviso de algo de hace
medio año la primera vez que alguien entrara.

## Enviar correos

`/envios`, debajo de Estadísticas y **solo para clientes**: se marcan las
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

**Cada envío tiene su «Detalles»** (`/envios/enviados/<id>`): una fila por
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
un enlace a `GET /envios/<id>/mandar`, que no manda nada: dice el asunto, a qué
lista, **a cuántos contactos**, con qué pieza y cuánta cuota queda, y si ya
salió antes avisa de que le va a llegar otra vez a todos, también a quien ya la
recibió. El que manda es el POST. Es el mismo reparto que exportar contactos, y
aquí pesa más: un correo que salió no se puede recoger.

**Para mandar hacen falta las dos puertas**: un plan con cuota del mes por gastar,
y la habilitación de envío, que es la única con una persona detrás
(`accounts.can_send()`). `services/sender.py` las mira antes de armar un solo
correo.

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

De la identidad **verificada hoy** en SES —`panamails.com`—, con el nombre de la
empresa a la vista y su dirección como responder a. Lo que dice el apartado de
arriba, `tuempresa@envios.panamails.com`, es a dónde va esto el día que ese
subdominio esté verificado: mientras no lo esté, usarlo haría fallar cada envío.
Es una sola función, `sender.from_address()`.

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

## Cobrar un plan

Se contrata desde **Configuración → Opciones de pago**. Hoy es un **pago suelto**
de un mes o un año, no una suscripción: PayPal, o Paguélofácil con tarjeta,
cobra una vez y el plan queda activo por ese periodo. La renovación se avisa a mano, igual que ya estaba
previsto para Yappy. La suscripción que se renueva sola pide crear un producto y
un plan por cada uno de los nuestros en el panel de PayPal, y el webhook
funcionando; es el paso siguiente, no este.

```
Contratar  →  el servidor crea la orden  →  el navegador va a PayPal
           →  PayPal devuelve al panel   →  el servidor cobra y comprueba
           →  la cuenta queda activa con su plan
```

Tres cosas de ese camino que no son negociables:

1. **Lo que decide es la respuesta de PayPal al servidor**, nunca lo que traiga
   el navegador de vuelta. Ahí solo viene un identificador de orden, que no
   prueba nada. El servidor cobra la orden por su cuenta y **compara el monto y
   la moneda** contra lo que ese plan cuesta; si no cuadra, no se activa nada y
   el intento queda escrito con la diferencia.
2. **Cobrar dos veces la misma orden no da dos periodos**, por la escritura
   condicional de `payments`.
3. **Los precios salen de `docs/pricing.md`**, no copiados al backend:
   `services/plans.py` lee las mismas dos filas que lee el sitio. Cambiar una
   cifra ahí la cambia en el sitio, en el panel y en lo que se cobra.

### Con qué se paga

La pantalla de contratar pregunta **dos cosas y en este orden**: con qué se paga
y por cuánto tiempo. El ciclo viaja en el botón que se pulse, así que no hace
falta un control aparte para elegirlo.

| Método | Estado |
|---|---|
| PayPal | Cobra |
| Tarjeta de crédito o débito | Cobra por **Paguélofácil**, en cuanto tenga sus credenciales |
| Yappy | Anunciado. Falta la integración |

**Los tres se enseñan siempre**, también los que faltan: esconderlos haría que
quien no tiene cuenta de PayPal cerrara la página creyendo que no puede pagar de
ninguna forma. Los que no se pueden usar ahora **no son un control que se pueda
mandar** —no tienen radio, solo «pronto»—, y la ruta solo acepta los de
`ready_methods()` (los de `payments.METHODS` con sus credenciales puestas), así
que un formulario escrito a mano con `metodo=yappy` acaba pagando por PayPal en
vez de abrir una puerta que no existe.

### La tarjeta: Paguélofácil

**Visa y Mastercard sin PayPal**, porque no todo el que tiene tarjeta tiene
cuenta de PayPal. Stripe no acepta comercios de Panamá; de las pasarelas locales
se eligió Paguélofácil (`services/paguelofacil.py`), con su **enlace de pago**:
el cliente escribe la tarjeta en la página de Paguélofácil y vuelve. **La
tarjeta no toca el panel** —la regla 9 no cambia, y meter sus campos aquí
obligaría a una certificación PCI que este producto no va a tener—; de ella se
guardan solo los últimos cuatro números (`card_last4`), que la lista de pagos
enseña.

```
Contratar con Tarjeta  →  intento en payments (method card, provider paguelofacil)
  →  enlace de pago (PARM_1 = el intento, y el intento dentro de la descripción)
  →  paga en Paguélofácil  →  vuelve a /configuracion/pagos/tarjeta/volver
  →  el servidor CONSULTA la operación (Oper) con el token
  →  aprobada, capturada, por el monto del plan y de ESE intento: se activa
```

- **Lo que trae el navegador no decide nada**: «Estado=Aprobada» se escribe a
  mano. Decide `card_verdict()`, que pregunta por la operación. Se piden tres
  cosas: aprobada y capturada (`paguelofacil.paid()`), el monto del plan, y que
  su descripción lleve el id de **ese** intento, así una operación de otro pago
  no sirve.
- **El aviso automático** (`POST /webhooks/paguelofacil/<secreto>`) es para quien
  paga y cierra el navegador. Hace la misma consulta. Lo activa Paguélofácil
  cuando se le pide por correo.
- **La vuelta, el aviso y PayPal terminan en la misma `settle()`**: marca el
  pago, activa el plan y manda los dos correos. La escritura condicional de
  `payments.complete()` hace que dos de ellas no den dos periodos.
- **Solo se manda a una página de pago conocida**
  (`Config.paguelofacil_checkout()`). Es la que `form-action` deja abrir, por
  nombre y sin comodines. La de sandbox no está documentada: si resulta otra,
  se fija con `PAGUELOFACIL_CHECKOUT`.
- Sin `PAGUELOFACIL_CCLW` y `PAGUELOFACIL_TOKEN`, la tarjeta dice «pronto».

Cada intento de pago anota **con qué se eligió pagar** (`method`), así que la
lista de pagos lo dice. Lo escrito antes de esto no lo lleva y se lee como
PayPal, que era lo único que había.

**Quién puede pagar**: cualquiera con el **correo confirmado** y **sin suspender**,
y ninguna de las dos la decide una persona (`accounts.can_buy()`). El correo
confirmado porque es a donde va el comprobante, y cobrarle a una dirección
escrita mal deja a alguien pagando sin recibir nada. Una cuenta activa también,
porque si no el primer pago sería el último y nadie podría renovar ni cambiar de
plan. **Un administrador no**: su cuenta no tiene a quién escribirle.

Pagar mueve la cuenta a `active` y escribe `plan` y `plan_until`. Renovar el
mismo plan antes de tiempo **suma al final de lo que quedaba**; cambiar de plan
empieza hoy. Pagar **no** habilita el envío: eso es la otra puerta, y el
comprobante que sale lo dice para que no se descubra al intentar enviar.

Del cobro salen **dos correos**: el comprobante al cliente y un aviso a quien
administra, porque el que pagó queda esperando una habilitación que hace una
persona. Los dos van después de todo lo que decide algo: si el correo no sale,
el pago sigue cobrado y el plan activo.

**Hubo un cuarto plan, Corporativo, y se quitó** (septiembre de 2026): iba sin
precio público y a la medida. Quedan tres, todos con precio y todos comprables
por la web.

**El plan se elige en `/planes`, no dentro del panel.** El botón de cada plan
del sitio público lleva a `/contratar/<plan>`, que enseña lo que cuesta y tiene
el botón de pagar; sin sesión manda a entrar llevando **el nombre del plan, nunca
una dirección**, y al abrir sesión sigue hasta ahí. Configuración → Opciones de
pago ya no vende: dice desde dónde se cobra, qué plan hay contratado y qué se ha
cobrado.

**Las tarjetas de `/planes` tienen su interruptor de mensual y anual**, con
`landing/assets/js/plans.js`, el único guion que baja una sola página (el bloque
`scripts` de `src/base.html.j2`). En anual cada tarjeta enseña **el equivalente
mensual** —el anual entre doce— y debajo lo que se cobra de verdad, y el número
va de una cifra a otra con un contador propio. Las dos cifras salen de
`docs/pricing.md` como todo lo demás (`monthly_value`, `yearly_value`,
`yearly_monthly` en `build_site.py`), no escritas en el marcado.

**El descuento del año se anuncia como «-20%»** y tampoco está escrito a mano:
`build_site.discount()` y `plans.discount()` lo sacan de las dos filas de precio
(`1 − anual / (mensual × 12)`), cada uno para su lado. Por eso los precios son
múltiplos de cinco: con ellos el 20% da entero en las tres cifras, y la tarjeta
no enseña un «$12.80». La pastilla **solo se enciende con el anual puesto**: en
mensual queda apagada, para que nadie lea ese descuento como el precio que está
mirando.

**Al pasar el ratón por una tarjeta, esa crece y las otras dos se achican**, así
que la que se mira queda sola al frente. Va bajo `@media (hover: hover)` y de
860 px en adelante: en el teléfono no hay ratón, y con «reducir movimiento» no
se mueve nada. Para que eso funcione, `plans.js` **le quita a cada tarjeta las
clases de la entrada y su `transition-delay` al terminarla**: ese retraso se
quedaba puesto y la regla de la entrada, más específica, le ganaba al hover de la
recomendada.

Tres cosas más de ese interruptor:

- **La página nace en mensual y con todo dibujado**, así que sin JavaScript se
  leen los tres planes, sus precios y sus botones. **El interruptor sí se
  esconde sin el guion** (`.cycle` nace en `display: none` y `plans.js` le pone
  `is-ready`): un botón que no hace nada es peor que no tenerlo.
- **El botón de cada plan lleva el ciclo al panel**, con `?ciclo=anual`, y
  `/contratar/<plan>` resalta ese botón. Sin parámetro, o con uno inventado,
  queda el mes, que es lo de siempre. `nav.js` sigue mandando en el texto del
  botón: esto solo le toca la dirección.
- **Con «reducir movimiento» puesto no se anima nada**: el precio cambia de
  golpe, las tarjetas nacen puestas y no sale confeti. El confeti es nuestro,
  sin ninguna dependencia: sale del centro del interruptor y cae por **la
  pantalla entera**, en un `<canvas>` fijo que no recibe clics y que se borra
  solo cuando el último papelito sale de vista. Medía lo que el interruptor y se
  cortaba al primer salto.

**`form-action` de la cabecera tiene que permitir todo sitio al que se pueda
acabar yendo desde un formulario.** Esa regla gobierna también la redirección que
sigue al envío, así que con solo `'self'` el navegador se planta y desde fuera
parece que el botón no hace nada. Hoy hay dos destinos así: el checkout de PayPal
—`Config.paypal_checkout()`, según el entorno— y **el sitio público**, que es
donde aterriza un cliente al entrar. Costó descubrirlo una vez con los botones de
pagar; la segunda estaba avisada.

Sin credenciales configuradas la pantalla se dibuja igual y dice que el pago no
está disponible, en vez de romperse.

## Planes

Ver `docs/pricing.md` para la tabla completa, límites y reglas. Los costos, los
márgenes y el análisis de competencia están en `docs/pricing-interno.md`, que
está en `.gitignore` a propósito y no debe subirse.

Resumen: Básico $15 · Negocio $25 · Empresa $55. `docs/pricing.md` es la
fuente de verdad; el sitio
público lee sus tablas al construirse, así que no hay que copiar cifras a mano. El límite de correos es siempre **5x** el de
contactos. Anual = 20% de descuento. Los correos no usados pasan al mes siguiente
y vencen ahí; se consumen primero los acumulados.

---

## Variables de entorno

```
MONGODB_URI
SECRET_KEY
AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
AWS_REGION
SES_CONFIGURATION_SET               # campañas, con aperturas y clics
SES_TRANSACTIONAL_CONFIGURATION_SET # correo del sistema, sin ellos
SES_WEBHOOK_SECRET        # va en la dirección del aviso; sin él, 404
SES_TOPIC_ARN             # opcional: descarta avisos de otro tema
SENDING_DOMAIN            # envios.panamails.com
PAYPAL_ENV                # sandbox | live; en producción con sandbox no arranca
PAYPAL_CLIENT_ID
PAYPAL_SECRET
PAYPAL_WEBHOOK_ID         # para comprobar los avisos; todavía sin usar
PAGUELOFACIL_ENV          # sandbox | live; en producción con sandbox no arranca
PAGUELOFACIL_CCLW         # el código web del comercio: crea los enlaces de pago
PAGUELOFACIL_TOKEN        # consulta las transacciones, que es lo que decide
PAGUELOFACIL_WEBHOOK_SECRET  # va en la dirección del aviso; sin él, 404
PAGUELOFACIL_CHECKOUT     # opcional: la página de pago, si no es la de siempre
YAPPY_MERCHANT_ID
YAPPY_SECRET
```

Nunca commitear el `.env`. En Railway van como variables del servicio.

---

## Antes de la primera campaña real

El correo del sistema y las campañas son dos caminos distintos. Lo de abajo no
hace falta para que alguien reciba su código de confirmación, y **sí** hace
falta antes de que salga la primera campaña de un cliente. Está aquí para que
no se descubra el día del lanzamiento.

- ~~**Dirección postal física en el pie de cada campaña.**~~ Hecho, y **es la de
  cada cliente**: la CAN-SPAM la pide en todo correo publicitario (basta un
  destinatario con Gmail o Hotmail) y es la de quien anuncia, no la de
  Panamails. Se escribe en Configuración → Cuenta (`postal_address`, de 10 a
  200 caracteres), va inyectada al pie junto a la baja, y **sin ella no se
  envía**: `sender.blocked()` dice `postal`. El administrador la ve en la
  ficha y no la edita. Hubo una sola para todos en la variable `POSTAL_ADDRESS`,
  y se quitó. Un apartado postal cumple sin publicar un domicilio.
- ~~**Aviso de operación.**~~ Hecho: RUC y aviso están en `LEGAL_HOLDER` de
  `landing/content.py`, y `holder_line()` los escribe en la frase de apertura de
  la privacidad y de los términos. **Los precios incluyen el ITBMS**, lo dicen
  esas dos páginas, la de planes y `docs/pricing.md`, y a un cliente de fuera de
  Panamá se le factura como exportación de servicios sin que cambie lo que paga.
  Lo que falta de esto es **pedirle sus datos de facturación al cliente**: el
  panel no guarda su RUC en ningún sitio, y una factura en Panamá lo necesita.
- **Conectar el aviso de SES** siguiendo `docs/ses.md`. El código está y
  anula solo lo que rebota o se queja, pero hasta que el tema de SNS y los
  conjuntos de configuración existan no le llega nada. Es lo primero que AWS
  revisa si algo va mal.
- **La pausa automática por rebotes y quejas**, la de la tabla de «Envío». Hoy
  depende de mirar las cifras a mano.
- **Verificar `envios.panamails.com`** como identidad aparte en SES, con su
  propio configuration set. El correo del sistema sale por `panamails.com`
  (MAIL FROM `mail.panamails.com`, ya configurado); separar los dos es lo que
  impide que la reputación de las campañas arrastre a los códigos de
  confirmación.
- **Tenants de SES por cliente**, para aislar reputación y supresión. Ya está
  decidido más arriba; el momento de montarlo es este.
- **Registro de consentimiento por contacto.** Guardar de dónde salió cada
  dirección y cuándo, en el propio documento del contacto. Hoy el importador no
  lo pide, y es exactamente lo que hay que enseñar cuando alguien reclame.
- **Revisar la solicitud de producción de SES ya enviada** (`solicitud-ses.txt`
  en la raíz): lo que se prometió ahí sobre bajas, supresiones y umbrales tiene
  que estar funcionando de verdad cuando empiecen las campañas.
- **Contrato de encargo para clientes grandes.** El tratamiento de datos de
  terceros ya está pactado en los términos públicos (§8), que se aceptan al
  registrarse. Una cooperativa grande puede pedir además un documento firmado;
  ese addendum se redacta cuando aparezca.

## Pendientes de decisión


- Confirmar con Yappy (yappy@bgeneral.com / 800-5000) si soporta cobros
  recurrentes. Si no, el recurrente va solo por PayPal y a los de Yappy se les
  envía enlace de pago antes de cada vencimiento.
- Pedir acceso a producción de SES al empezar a desarrollar, no al lanzar: las
  cuentas nuevas arrancan en sandbox (200 correos/día, solo a direcciones
  verificadas) y la aprobación tarda ~24h.
- Presupuestar el salto de MongoDB Atlas: los eventos llenan los 512 MB del
  tier gratuito en unos 7 meses con 6 Básico + 3 Negocio + 1 Empresa.
