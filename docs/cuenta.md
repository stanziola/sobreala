# La cuenta: registro, entrada, usuarios y avisos

Detalle que vivía en `CLAUDE.md`, movido tal cual para que ese archivo
cupiera en el límite. Lo esencial (las reglas, las convenciones y el
resumen de cada parte) sigue allí; esto es lo que hay que leer antes de
tocar esta parte.

### `accounts`
Cuenta de una empresa cliente. Guarda plan, cuota del mes, saldo acumulado,
estado y configuración de remitente.

Estados: `registered` → `active` → `suspended`

| Estado | Qué significa |
|---|---|
| `registered` | Se registró. Hasta que se abre (con la demostración o con un pago) solo ve su bienvenida y Configuración, y **puede comprar un plan**. |
| `active` | Pagó. Su plan corre hasta `plan_until`. |
| `suspended` | Nada. Corte automático por rebotes/quejas, o manual. |

**Hubo un cuarto, `approved`, y se quitó.** Era una aprobación comercial a mano
sin la cual no se podía comprar. Esperar a que alguien te apruebe para poder
pagar no protegía nada que valiera esa espera; la mirada que sí importa —de
dónde salió esa lista— pasó a hacerse justo antes del primer envío, y desde
octubre de 2026 en la demostración. Ver «Abrir la cuenta», más abajo.

**Abierta o cerrada no es un estado**, es otro hecho (`opened_at`), como
confirmar el correo: una cuenta `registered` puede estar abierta por la demo y
sin plan todavía.

**Estar activa es el efecto de un pago cobrado, no una decisión.** `activate_plan()`
es el único sitio que escribe `active`, y lo llaman tanto la vuelta de PayPal
como el plan que el administrador pone a mano para quien pagó por Yappy o por
transferencia. Lo que el administrador sí decide es **suspender y levantar la
suspensión**, desde `/admin/accounts/<id>` y con un motivo que queda escrito en
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
| Un administrador de Sobreala | Ninguno de estos permisos: no tiene clientes a los que escribirle |

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

### Abrir la cuenta: la demostración o el pago

**Una cuenta nueva nace cerrada** (octubre de 2026). Cualquiera puede
registrarse con solo confirmar un correo, y las imágenes viven en la base: unas
200 cuentas falsas, con sus 20 fotos cada una, llenarían los 512 MB de Atlas.
Cerrada, solo usa su bienvenida y Configuración, y puede comprar un plan.
- **El menú de los dos sitios enseña el Dashboard** (hasta octubre de 2026,
  cuatro filas: Estadísticas, Enviar correos, Contactos y Plantillas), y cada
  pantalla de su árbol la
  devuelve a `/welcome?para=<permiso>`. Lo decide `needs()`, por donde ya
  pasaban todas, así que una pantalla nueva hereda la puerta. Hasta octubre de
  2026 la bienvenida decía arriba a cuál quería entrar («Para entrar a
  Contactos, contrata un plan o pide la demostración», `GATE_NAMES`); se quitó
  porque la bienvenida ya ofrece las dos formas de abrirla, y el `?para=` quedó
  sin leer.
- **Hubo en su lugar una sola fila, «Tu demostración»**, con su migaja `new`
  en el sitio, y se quitó (octubre de 2026): escondía lo que trae Sobreala, y
  las cuatro filas ya llevan a la demostración. La migaja de una cuenta
  cerrada es `1`, como la de cualquiera sin plan.
- **En Configuración → Cuenta sale un aviso amarillo** (`.notice--pending`)
  mientras falte enviar un documento, o haya uno rechazado, con el enlace al
  formulario (`/verification`). Ya no depende de que la cuenta esté abierta: se
  va al enviarlos (ver «El registro y las verificaciones»).

**Se abre por uno de dos caminos, y son independientes** (`accounts.is_open()`):

| Camino | Quién la abre | Qué tiene después |
|---|---|---|
| La demostración | El administrador, con «Abrir la cuenta» en la ficha y un motivo (`opened_by`, `admin_events`) | Lo del Básico sin vencimiento: 1,000 contactos, 1 etiqueta, 1 columna, 20 imágenes y campañas armadas. **Envía solo a sus direcciones de prueba**, hasta 50 correos (ver abajo). Para enviar a su lista, contrata |
| El pago | `activate_plan()`, sola y sin `opened_by` | Todo lo de su plan desde el primer momento, envío incluido |

### La demostración que envía (octubre de 2026)

Hasta ese mes la demostración no enviaba nada, así que no enseñaba lo mejor
(quién abrió, quién pulsó). Ahora envía **como el «sandbox» de Amazon**:

- **Direcciones de prueba**: una sección de Configuración que solo existe en la
  demostración (`accounts.in_demo()`: abierta, sin plan). Hasta
  `DEMO_ADDRESSES` (5), en `accounts.test_addresses`.
- **Cada una se confirma desde su propio buzón**: le llega un enlace
  (`tokens.TEST_ADDRESS`, de un solo uso, con hash y 3 días; regla 6) que dice
  de quién viene y que si no sabe de qué se trata no haga nada. Abrirlo
  (`/test-address/<testigo>`, sin sesión) la confirma y **la agrega a
  Contactos**, para que las campañas de prueba la encuentren. Se mandan hasta
  10 enlaces por hora.
- **Al enviar** (`sender.blocked()` y `run()`), en la demostración no se pide
  plan: se pide al menos una dirección confirmada (`demo_addresses`) y que le
  queden correos (`demo_used`). Campañas e individuales salen **solo** a las
  confirmadas; el resto de la lista se salta sin gastar nada. **Hasta
  `DEMO_SENDS` (50) correos en total** (`demo_sent`), con la marca de agua y la
  baja de siempre. Masivo lo dice arriba, con cuántas tiene y cuántos le
  quedan.
- Con un plan pagado nada de esto aplica, y la sección desaparece.

- **La demostración se pide desde la bienvenida** (`POST /welcome/demo`), **una
  sola vez** (octubre de 2026). Pregunta **«¿A qué se dedica tu negocio?»** y
  **«¿Para qué usarás Sobreala?»** (`demo_business`, `demo_purpose`, de 10 a 500
  caracteres), **cuántos contactos tiene** (`demo_contacts`: menos de 500, 500 a
  2,000, 2,000 a 10,000, más de 10,000) y **cómo los consiguió** (`demo_source`:
  clientes o socios, alumnos, formulario, eventos, otra; **con «Otra forma» se
  dice cuál**, de 3 a 200 caracteres, en `demo_source_other`: una casilla que
  con JavaScript sale solo al elegirla, octubre de 2026), y un **sitio web
  opcional** (`demo_website`, de hasta 200 caracteres, con `https://` si no lo
  trae). Los dos selectos dicen qué plan le conviene y si la lista es de fiar, que
  es lo primero que revisa Amazon. Se le escribe al teléfono personal del
  registro. Solo el dueño y con el correo confirmado.
- **Con la solicitud hecha el formulario ya no sale**: queda un aviso verde con
  su gancho que dice «Tu solicitud ha sido recibida» y qué pasa ahora: «La
  revisamos pronto. Cuando la aprobemos, te llegará un correo a {correo} para que
  empieces» (la espera se quitó a principios de octubre de 2026 y volvió el 20,
  porque sin ella no se sabía qué esperar; el teléfono no), y un segundo
  envío no guarda nada ni vuelve a avisar. Antes se podía pedir otra vez, con un
  tope de tres al día (`DEMO_PER_ACCOUNT`, ya quitado). Corregir una solicitud
  enviada no se ofrece. A quien administra le llega «{empresa} pidió una
  demostración» (`admin_demo`, con interruptor), con el teléfono y las respuestas
  (también lo que escribió en «Otra forma»), y la cuenta sale en el filtro «Piden demostración» de Cuentas. La ficha enseña
  las respuestas, con el sitio como enlace.
- **Configuración → Cuenta, con menos texto** (octubre de 2026): el correo se
  llama «Correo» a secas; la dirección postal y los teléfonos van sin frase
  debajo; y **no hay fila de estado**, que solo podía decir «Registrada» o
  «Activa» (una suspendida no entra, y la limitada la dice el aviso de arriba).
  El estado lo sigue viendo el administrador en la ficha y en Cuentas. En
  Seguridad, Usuarios va sin frase, y cambiar la contraseña dice «Si la cambias,
  se cierra la sesión en los demás dispositivos.»
- **Hasta octubre de 2026 se pedían aquí el WhatsApp y el RUC o la cédula.** El
  WhatsApp era el mismo número del registro, y la identificación pasó al
  registro. Con ellos se fue el texto de la bienvenida que contaba las dos
  formas de empezar y lo que se hace en la demostración.
- **En la llamada se abre la cuenta al empezar** y, juntos, se recorre el
  panel, se mira de dónde sale su lista, se importa y se arma su primera
  plantilla. Al abrirla le llega «Tu cuenta de Sobreala está abierta», que no
  se puede apagar.
- **El pago ya no pide la identificación** (octubre de 2026). Hasta entonces
  el checkout pedía el RUC o la cédula si no estaba. Ahora la identificación es
  solo el documento que se verifica, y las cuentas de antes conservan el
  número que ya habían escrito (`tax_id`), que la ficha enseña si existe. **El
  aviso de operación no se exige**: dejaría fuera a cooperativas, gremios,
  asociaciones y negocios pequeños; es uno de los documentos que sirven para
  verificar la dirección.
- **No hubo nada que migrar**: `is_open()` cuenta también `plan` y
  `sending_cleared_at`, así que las cuentas que ya habían pagado o se habían
  habilitado siguen abiertas. Las registradas sin plan quedaron cerradas hasta
  que alguien las abra.

### El registro y las verificaciones (octubre de 2026)

**El registro pide lo que después se verifica**, además de empresa, nombre,
correo y contraseña:
- **el teléfono personal**, obligatorio: es al que se le escribe por la
  demostración (`phone`);
- **los de la empresa**, opcionales y hasta tres (`company_phones`), con
  «Agregar otro número»;
- **la dirección**, por partes (ver abajo), la misma que sale al pie de las
  campañas;
- **la casilla de los términos**, obligatoria, y **la de las novedades**,
  opcional (ver abajo).

**Los nombres tienen que ser nombres** (octubre de 2026: se aceptaban «.» y
«123»). El de la empresa, de 2 a 80 caracteres, con al menos dos letras o
números y alguna letra; admite los signos de una razón social (`& . , ' - ( )
/ +`). El de la persona, de 2 a 60, solo letras y `' - .`, con al menos dos
letras (`accounts.clean_company_name()` y `clean_person_name()`). Valen en los
dos registros y al invitar a un usuario. Los de las cuentas que ya existían no
se revisan.

**La dirección va por partes** (octubre de 2026; antes era una línea suelta):
dirección (línea 1, de 5 a 200 caracteres), línea 2 opcional (apartamento,
oficina), ciudad, provincia o estado (con las de Panamá como sugerencias en un
`datalist`, `i18n.PANAMA_REGIONS`), código postal opcional y país
(`templates/_address.html`, `accounts.clean_address()`). Se guarda en
`accounts.address` y **también armada en `postal_address`**
(`compose_postal()`), que es lo que leen el pie de las campañas,
`sender.blocked()` y la ficha. Al armarla **no se repite nada**: si la ciudad ya
nombra la provincia («Santiago de Veraguas» y «Veraguas») la provincia no se
escribe. Las cuentas de antes tienen solo `postal_address`, y se leen como su
línea 1 (`address_of()`): siguen enviando igual, y «Editar» les pide lo que
falta. Guardar una dirección cuyo texto armado cambió reinicia su
verificación, como siempre.

**Los términos se aceptan con una casilla** (octubre de 2026; antes era una
frase debajo del botón). Sin marcarla no hay cuenta, y se guardan
`terms_accepted_at` y `terms_version`, que es la fecha de los términos vigentes:
`accounts.TERMS_VERSION`, copia de `TERMS_UPDATED` de `landing/content.py`
(una prueba compara las dos). **Las novedades de Sobreala** son la otra casilla:
va desmarcada, se guarda en `news_opt_in` (con su fecha) y se cambia en
Configuración → Notificaciones → Novedades de Sobreala. **Va aparte de
`notifications`**, donde lo no escrito vale «sí»: aquí vale «no»
(`wants_news()`). La ficha del administrador enseña las dos.

**La identificación personal no se escribe en ningún sitio**: es solo el
documento (la foto o el PDF de la cédula o el pasaporte), que se envía después
de registrarse. Hasta octubre de 2026 también se escribía su número (`tax_id`).

**Los teléfonos llevan su país.** Un `<select>` con **solo la bandera y el
prefijo** («🇵🇦 +507»; el nombre del país va en el `title` de cada opción y lo
lee un lector de pantalla), Panamá primero y elegido, de `services/countries.py`
(unos 240). La bandera son las dos letras del código ISO como indicadores
regionales; Windows no las dibuja, y para eso va la fuente
`static/fonts/TwemojiCountryFlags.woff2` (MIT, con los dibujos de Twemoji en
CC-BY 4.0; ver su LICENSE), solo para esos caracteres. Se guardan con su
prefijo, `+50760000000` (`clean_phone(número, país)`); el 0 de marcar dentro del
país se quita, menos en Italia (`templates/_phone.html`).

**Los de Panamá tienen sus reglas** (octubre de 2026; se aceptaban de 4 a 14
dígitos): **el personal es un celular**, 8 dígitos que empiezan con 6, y los de
la empresa pueden ser también un fijo, 7 dígitos que empiezan con 2 a 5 o 7 a
9. Vale si se eligió Panamá o si se escribió +507 (`accounts.check_phone()`,
que devuelve el número y, si no vale, la clave de la frase que dice por qué).
Los de los demás países siguen con la regla de antes.

**Teléfonos y dirección se ven como texto y se cambian con «Editar»**
(Configuración → Cuenta, solo el dueño): cada fila enseña su valor, y «Editar»
abre su formulario (`?editar=phones` o `?editar=address`) con Guardar y
Cancelar. Funciona sin JavaScript. Hasta octubre de 2026 eran campos con
«Guardar» siempre a la vista.

**Se verifican dos cosas, a mano**: la identificación personal y la dirección
(`accounts.verifications.{identity,address}`).
- **El cliente envía los dos documentos en un formulario aparte**
  (`/verification`, solo el dueño), al que lo llevan el aviso amarillo de
  Configuración, el de la cuenta limitada y Masivo. Hasta octubre de
  2026 se subían dentro de Configuración → Cuenta.
  - la identificación, con la foto o el PDF de su cédula o pasaporte;
  - la dirección, con un recibo de luz, agua o teléfono, el aviso de
    operación, o un documento legal que la certifique si la empresa no está
    constituida.
- **Pide los dos de una vez, en un solo envío**, y si uno no sirve no se guarda
  ninguno. **Después no se ven ni se cambian desde la cuenta**: la pantalla
  solo dice «Recibimos tus documentos». Solo vuelve a pedirse el que se rechaza,
  con su motivo.
- **PDF, JPG o PNG de hasta 5 MB**, reconocidos por cómo empiezan
  (`models/verification_doc.py`, colección `verification_docs`, uno por cuenta
  y clase). Enviarlos deja la verificación **en revisión**.
- **El administrador los mira en la ficha**: baja cada uno como archivo, nunca
  dibujado dentro del panel, y lo **verifica** o lo **rechaza** con un motivo.
  **Las dos cosas borran el archivo**: de la cédula de alguien o de su recibo
  solo hace falta el resultado. Queda en `admin_events` (`verify`).
- **Verificar y rechazar no mandan correo.** El administrador lo manda cuando
  quiere con **«Enviar correo al cliente»** (`notify`), que cuenta qué quedó
  verificado y qué se rechazó con su motivo; con un rechazo pide volver a
  enviar ese documento, y con los dos verificados lo confirma.
- **Rechazar limita la cuenta sola** (si no lo estaba): sin el documento no se
  puede comprobar quién envía. El límite se levanta al verificar los dos.
- **Cambiar el dato después reabre la verificación**: editar la dirección la
  devuelve a «falta el documento» y borra el que esperaba, porque lo que se
  miró era el de antes.
- **Cuentas tiene un filtro «Por verificar»**: las que tienen un documento en
  revisión.

### Limitar una cuenta (octubre de 2026)

**Limitar no es suspender.** Una cuenta limitada entra, prepara todo y puede
pagar; lo único que no puede es enviar: `sender.blocked()` dice `limited`, y
Masivo lo explica con el enlace al formulario de documentos.
Suspender sigue cerrando la entrada.
- **Lo decide el administrador en la ficha** («Limitar la cuenta»), con un
  motivo de una lista (`accounts.LIMIT_REASONS`; hoy solo `verification`,
  «Falta verificar la identificación y la dirección») y una nota que queda en
  el registro. El motivo es lo que lee el cliente; la nota no.
- **Al cliente le llega «Necesitamos verificar tu cuenta»**, sin interruptor,
  con el enlace a sus documentos. Si solo se enterara al intentar enviar,
  podría enterarse tarde.
- **Se levanta solo** cuando el motivo es `verification` y el administrador deja
  verificadas las dos cosas, y **a mano** con «Quitar el límite». Las dos
  cosas quedan en `admin_events` (`limit`).

**Hubo una habilitación para enviar, y se quitó** (octubre de 2026).
`sending_cleared_at` era una mirada a mano antes de la primera campaña: de dónde
dijo que salió cada lista, y la pieza que iba a mandar. Con la cuenta abierta
por la demostración o por el pago era una segunda espera para la misma decisión,
y a quien acababa de pagar le pedía esperar justo cuando quería empezar. Lo que
miraba pasó a la demostración. El campo queda en las cuentas viejas, que
`is_open()` lee, y sus decisiones se siguen leyendo en la actividad de la ficha.

**Lo que se pierde con eso**: nadie mira la lista real antes del primer envío de
quien entra pagando. Lo cubre la pausa automática por rebotes y quejas (octubre
de 2026, `docs/envios.md`): una lista mala se detiene sola en cuanto sus
rebotes pasan el umbral.

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
cuidar en la cuenta que puede abrir y suspender a todas las demás, y
**Notificaciones**, que es la misma pantalla con otra lista: qué le avisamos de
las cuentas de sus clientes. Las filas se esconden del menú
**y las rutas la devuelven a `/admin`**: esconder un botón no es un permiso.

### El logo de la empresa (octubre de 2026)

**Lo sube el dueño** en Configuración → Cuenta → Perfil (`/settings/logo`): un
PNG, un JPG o un WebP de hasta 5 MB, reconocido por cómo empieza (un GIF o un
PDF no entran), sin sus bordes transparentes y achicado a 400 px. Un usuario
de la empresa lo ve y no lo cambia. **Gmail no lo enseña como foto de quien
escribe**: eso pide BIMI, con un certificado de unos USD 1,000 al año por
dominio, y en `envios.sobreala.com` saldría el de Sobreala para todos.

- **Dónde vive:** en `images`, como las fotos de las plantillas, con
  `kind: logo`, y la cuenta guarda su nombre en `logo` (`accounts.logo_of`).
  No cuenta contra el tope de fotos, y ni la limpieza de las fotos sueltas ni
  el borrar de una plantilla lo tocan. Cambiarlo o quitarlo retira el de antes
  (`images.retire_logo`): se borra si nunca salió en un correo, y si salió,
  vence a los doce meses como cualquier imagen enviada.
- **Dónde se ve:** la barra del panel y la del sitio, que lo sabe por la
  migaja (`sa_in` lleva su nombre al final, ver `docs/sitio.md`); «Cambiar de
  cuenta»; Clientes, Cuentas y la ficha en administración; las páginas que abre
  un contacto (la baja, la confirmación de una dirección de prueba y la
  descarga, con `_sender_head.html`); arriba del PDF de Estadísticas; y en el
  lienzo, con «Mi logo» (`docs/plantillas.md`). Sin logo, todo queda como
  antes.
- **Cómo se ve: como una foto de perfil** (octubre de 2026). En todas esas
  pantallas **llena su círculo** (`object-fit: cover`), sin fondo ni borde: uno
  ancho pierde un poco de los lados, y lo transparente deja ver lo que hay
  detrás. Hasta entonces iba entero dentro de un círculo blanco con margen, y
  se veía como un botón con un borde blanco. Configuración lo enseña en el
  mismo círculo, más grande (72 px), y su texto dice que uno cuadrado se ve
  mejor. **Entero** sigue yendo donde se lee como logo y no como cara: arriba
  de un correo escrito (`docs/envios.md`), en el PDF y en el lienzo.

### Configuración, una página por sección (octubre de 2026)

El menú de Configuración lleva **un ícono por sección y no se despliega**.
**Cada sección se lee entera**, en una sola página (`WHOLE` en
`blueprints/auth/routes.py`): sus partes son subtítulos con su ancla. Hasta
octubre de 2026 Seguridad y Notificaciones se desplegaban en el menú, con una
pantalla por parte (`/settings/<sección>/<parte>`); esas direcciones siguen
valiendo y llevan a la sección y bajan a la suya (`/settings/security/sessions`
→ `/settings/security#sessions`).

| Sección | Partes |
|---|---|
| Cuenta | Perfil · Dirección y teléfonos · Verificación · Tu plan |
| Seguridad | Autenticación de múltiples factores · Contraseña · Usuarios (solo el dueño) · Sesiones |
| Notificaciones | Plan y facturación · Seguridad (un administrador: Clientes · Seguridad) |
| Facturación | Tu plan · Métodos de pago · Renovación automática · Historial de compras |
| Direcciones de prueba | (solo en la demostración) |

- Una parte que no existe, o que no le toca (Usuarios para un usuario), deja en
  la sección sin bajar a ninguna. Los avisos de siempre (`?user=invited`,
  `?updated=1`) salen en la página entera.
- **Notificaciones tiene un solo formulario y un solo «Guardar»**, con todos
  los avisos que esa cuenta puede elegir (`notices_for`), así guardar nunca
  apaga uno que no se dibujó; `set_notifications()` escribe aviso por aviso.
  Los de un administrador se dibujan todos en el orden de `ADMIN_NOTICES`:
  hasta octubre de 2026 faltaban «Alguien pidió una demostración» y «El panel
  pausó a un cliente», y guardar esa pantalla los apagaba sin que se viera.
- **Google y GitHub salen en Contraseña**, cada uno con lo que toca: el
  conectado con «Desconectar», y el que no, con **«Conectar»** (octubre de 2026;
  antes se conectaban solos la primera vez que se entraba con el mismo correo,
  y solo salía la fila del conectado). Uno apagado solo sale si está conectado,
  para poder quitarlo. Un administrador no ve «Conectar».
- El aviso de la pausa o el límite y el de los documentos pendientes salen
  arriba de toda Cuenta.

**Un registro que no se confirma se borra a las 24 horas.** `create()` escribe
`purge_at` y `confirm_email()` lo quita, así que Mongo barre solo lo que quedó a
medias: una dirección escrita mal no queda ocupada para siempre, y nadie puede
reservar el correo de un tercero registrándolo y no confirmando nunca. El
intento sigue en `auth_events`, que no tiene TTL.

**«Pedir otro código» no pregunta la dirección** (septiembre de 2026). Es un
botón, un POST que no puede mandar una precarga, y vuelve a la pantalla del
código con «Te enviamos un código nuevo.».

- **Al confirmar el registro** (`/resend-confirmation`), el código va a la
  cuenta que este navegador está confirmando (`PENDING_KEY`). Si no hay ninguna,
  va a la cuenta abierta si no está confirmada: es el botón del aviso del panel.
  Nadie escribe ninguna dirección, así que la regla 7 no está en juego, y la
  vuelta dice también si se pasó del límite o si el correo no salió.
- **Al recuperar la contraseña**, va a la que se escribió la primera vez, que
  guarda la sesión (`RESET_EMAIL`). Pasa por los mismos límites y contesta igual
  exista o no la cuenta, que es la regla 7 de siempre.
- **Si la dirección se escribió mal**, se vuelve atrás y se escribe la buena.
  Hubo una pantalla de corregirla antes de confirmar (`/confirm/corregir`) y
  se quitó: quien se registró con una dirección equivocada se registra otra vez
  con la buena, y la cuenta a medias se borra sola.

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

Si una cuenta sin confirmar cambia su correo por aquí, **queda confirmada**:
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

**La IP de ese aviso y la de Seguridad son el mismo dato**: la de la sesión
cuando se abrió, que Cloudflare le pasa al panel (`client_ip()`). Si no
coinciden, son dos ingresos distintos, y el proveedor de internet puede cambiar
la IP entre uno y otro. Cada fila de Seguridad es una sesión y no un aparato,
así que dos filas con la misma IP son dos sesiones de la misma computadora.

**Los formularios que abren una sesión se mandan una sola vez** (`data-once`,
en `panel.js`): entrar, el código de los dos pasos, registrarse y las seis
casillas. Un doble clic mientras el servidor contestaba abría dos sesiones; el
navegador se quedaba con la galleta de una y la otra seguía viva sin dueño, como
otra fila en Seguridad. En el código, la segunda vuelta decía que ya se había
usado.

## Los avisos de la cuenta

`services/notices.py` es el único sitio que los compone, y son quince:

| Correo | Cuándo sale | ¿Se puede apagar? |
|---|---|---|
| Contrataste el plan X | Al cobrar PayPal, y al ponerle el plan a mano | Sí, «Pagos y plan» |
| Renovaste el plan X | Igual, cuando el plan pagado es el que ya corría (ya no se puede pagar así) | Sí, «Pagos y plan» |
| Tu plan vence en 7 días | Al entrar al panel, si falta una semana o menos. Sin botón: se vuelve a contratar al vencer | Sí, «Estado de tu plan» |
| Tu plan venció | Al entrar al panel, si ya pasó la fecha | Sí, «Estado de tu plan» |
| Tu cuenta está abierta | Al abrirla desde la ficha, después de la demostración | No |
| Tu cuenta fue suspendida | Al suspenderla | No |
| Tu cuenta está activa otra vez | Al levantar la suspensión | No |
| Necesitamos verificar tu cuenta | Al limitarla desde la ficha, con el motivo y el enlace a sus documentos | No |
| El resultado de la verificación | Cuando el administrador pulsa «Enviar correo al cliente»: qué quedó verificado y qué se rechazó, con su motivo | No |
| Tu código para cambiar el correo | Al pedirlo, **a la dirección nueva** | No |
| Tu cuenta cambió de correo | Al terminar, **a la dirección vieja** | No |
| Alguien pagó un plan | Al cobrar | Sí, «Alguien pagó un plan» |
| Se registró una cuenta nueva | Al confirmar el correo | Sí, «Se registró una cuenta nueva» |
| Alguien pidió una demostración | Al pedirla desde la bienvenida, con su teléfono y sus respuestas | Sí, «Alguien pidió una demostración» |
| A un cliente se le venció el plan | Cuando ese cliente entra al panel | Sí, «A un cliente se le venció el plan» |

**Los cuatro últimos van a quien administra**, no a un cliente, y hablan de lo
que pasa en las cuentas de los demás.

**Los cinco del medio no llevan interruptor, y no por descuido.** El límite y
el resultado de la verificación cambian lo que la cuenta puede hacer, y sin
enterarse no lo puede arreglar. «Tu cuenta
está abierta» pasa una vez por cuenta y es la respuesta a la única espera que se
le pide a un cliente, la de la demostración. Hubo uno igual, «Ya puedes
enviar», que respondía a la habilitación, y se fue con ella. Los dos de la
suspensión son la respuesta a «¿por qué no puedo entrar?», y quien está
suspendido no puede entrar a cambiar sus preferencias, así que un interruptor
no le serviría de nada.

**El de un plan vencido tiene el límite de dónde se mira**, que es el mismo del
aviso al cliente: se detecta cuando ese cliente entra a su panel, así que de
quien no vuelve a entrar no se entera nadie. Los dos salen del mismo vistazo y
se anotan con la misma marca, así que ninguno se manda dos veces por el mismo
vencimiento.

**El correo de suspensión no lleva el motivo que escribió el administrador.**
Ese motivo se redacta para `admin_events`, puede ser corto y duro, y lo que
necesita quien lo recibe es otra cosa: qué significa, que no se borró nada y a
dónde escribir.

**Los trece comparten un solo par de plantillas**, `email/notice.html` y `.txt`,
porque todos tienen la misma forma: un titular, unos párrafos, y a veces un
botón, un recuadro o un código de seis dígitos. Los siete correos anteriores —confirmación,
bienvenida, recuperación, dispositivo nuevo…— siguen teniendo cada uno el suyo.

**Los ocho comparten el mismo aspecto** (octubre de 2026): `email/_layout.html`
es el sobre y `email/_parts.html` sus piezas (titular, párrafo, código, botón,
recuadro y nota). Arriba, **una franja azul de lado a lado** con el ala y
«sobreala» en Outfit Medium y en minúsculas, la marca escrita (Changa One hasta
octubre de 2026). La palabra va **dentro de
una imagen** (`static/img/mail/header.png`, que genera `build_assets.py`),
porque los lectores de correo no cargan fuentes propias, y **sin fondo**,
porque en modo oscuro el lector repinta la celda y no la imagen. Se dibuja a
`mailer.HEADER_SIZE`, la mitad exacta de la imagen: la primera versión puso el
ala cuadrada de `email-logo.png` a 40×24 y salió achatada. Debajo, el texto en
gris casi negro, **un botón oscuro** con la letra blanca y, tras una raya,
**el pie**: «Sobreala» y la dirección (Santiago de Veraguas, Veraguas, Panamá)
a la izquierda, Instagram y WhatsApp a la derecha, y «Ayuda · Privacidad»
debajo. Las direcciones del pie viven en `mailer.footer_links()`, y una prueba
las compara con el pie del sitio (`CONTACT` en `landing/content.py`). Las
imágenes son PNG que sirve el panel (Gmail y Outlook no dibujan SVG); los dos
íconos van en gris (`static/img/mail/`), sacados del glifo negro de cada kit de
`brand/social/`. `email-logo.png` queda para la marca de agua del Básico. Las
versiones en texto no cambiaron.

**Ninguno puede romper lo que estaba pasando.** Un correo que no sale no puede
hacer que un pago cobrado parezca fallido, así que el envío va envuelto y solo
deja una línea en el registro. Y como todos los del sistema, son
transaccionales: sin enlace de baja y sin marca de agua, que es la regla 8.

### Cómo se entera de que un plan venció

**Cuando la cuenta entra al panel, y hoy no hay dónde más.** No existe el proceso
en segundo plano que podría darse cuenta a las tres de la mañana, así que
`notices.plan_watch()` se llama al dibujar `/dashboard`.

Tiene el límite que se ve y conviene tenerlo presente: **solo le llega a quien
entra**, que es justamente quien menos lo necesita. El día que exista ese
proceso, es mover esta misma llamada; nada de esto se rehace.

Un plan que venció hace más de 30 días no dispara nada. Sin ese corte, al subir
esto las cuentas viejas de prueba habrían recibido un aviso de algo de hace
medio año la primera vez que alguien entrara.

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

## Eliminar la cuenta y sus datos (octubre de 2026)

Hasta el 16 de octubre de 2026 una cuenta se eliminaba borrando a mano su
documento de `accounts`, y todo lo demás (contactos, campañas, envíos, eventos,
plantillas, imágenes, sesiones) se quedaba en la base para siempre, sin dueño.
Ahora hay un botón, y **un solo sitio que borra**: `services/erase.py`,
`erase(db, owner_id, by=, reason=)`.

- **Dónde:** Configuración → Cuenta, al final, «Eliminar la cuenta» (la parte
  `delete`). Solo el dueño: la cuenta es de la empresa, y a un usuario la ruta
  lo devuelve a Seguridad. El botón rojo lleva a `/settings/delete`, que dice
  qué se borra y qué se queda, que el plan vigente no se reembolsa, y ofrece
  bajar los contactos antes.
- **Se confirma** escribiendo el nombre de la empresa (sin fijarse en
  mayúsculas ni en espacios de más) y la contraseña; con doble factor, además
  el código de la app (gasta su ventana, como al entrar). Quien entró con
  Google, GitHub o Apple y no tiene contraseña pide un código por correo
  (`tokens.ERASE`). Con CSRF y cinco intentos cada quince minutos.
- **Se borra**, con un `delete_many` por colección (`ERASED`): `contacts`,
  `campaigns`, `campaign_runs`, `events`, `designs`, `images`, `imports`,
  `downloads`, `sessions`, `account_tokens` y `verification_docs`, del dueño y
  de los usuarios de su empresa, y al final sus documentos de `accounts`.
  Afuera, el dominio propio se suelta en Amazon, la renovación automática se
  cancela y las cuentas de PayPal guardadas se olvidan; si algo de afuera falla
  se anota y se sigue.
- **Se queda** (`KEPT`), porque lo prometen la privacidad y los términos o lo
  pide la ley: `suppressions` (nadie le vuelve a escribir a quien pidió no
  recibir), `payments` e `invoices` (obligaciones contables), y `auth_events`,
  `mail_log` y `admin_events` (la bitácora). En `admin_events` queda una línea
  `erase` con quién, cuándo y cuántos documentos y, desde octubre de 2026, **la
  ficha mínima de la cuenta** (`after.owner`: empresa, nombre y correo del
  dueño, plan y fecha de alta; y `after.member_ids`, sus usuarios), que lo
  dice la privacidad. Con ella Eventos dice de quién era cada fila de una
  cuenta que ya no existe (antes salía «·»), y administración la abre en
  `/admin/erased/<id>`.
- **Después:** se cierran las sesiones de este navegador, llega un correo a la
  dirección que tenía («Tu cuenta se eliminó»), se avisa a quien administra
  (con el interruptor de los registros) y se aterriza en entrar con un aviso
  verde. El sitio público es estático y no tiene cómo enseñar ese aviso.
- **El administrador** lo hace desde la ficha («Eliminar esta cuenta», `#eliminar`),
  escribiendo el nombre de la empresa y un motivo, con la misma `erase()`.
- **Las supresiones quedan huérfanas** a propósito: si la misma empresa vuelve
  con otra cuenta no se le aplican. Para eso habría que guardarlas por dominio
  o por RUC, y se deja para cuando se pidan los datos de facturación.
- **Corre dentro de la petición.** Con cuentas de cientos de miles de eventos
  conviene mudarlo al proceso en segundo plano, con la importación, cuando
  exista.

## Entrar y registrarse, a dos columnas (octubre de 2026)

Como la imagen de referencia que se dio: **a la izquierda**, media pantalla en
el azul de la barra; **a la derecha**, el formulario sobre blanco. Lo comparten
entrar, registrarse y sus pasos (el código del doble factor, el del correo,
recuperar la contraseña en sus tres pantallas, completar la cuenta tras Google
y aceptar una invitación), con el marco `_auth.html`, para que el flujo no
cambie de cara a la mitad.

- **Sin la barra de arriba:** `base.html` la tiene en `{% block bar %}` y
  `_auth.html` lo deja vacío. Su ala está arriba del lado izquierdo y lleva al
  sitio, como la de la barra. El modo claro u oscuro sale de lo ya elegido o
  del sistema: estas pantallas no tienen el botón para cambiarlo.
- **A la izquierda, las funciones que rotan:** Contactos, Editor, Envío y
  Resultados, una a la vez, con su dibujo en una tarjeta, un título y una línea
  (`auth_feature_*` en `i18n.py`). `panel.js` (`data-auth-tour`) cambia cada
  6 s y los puntitos eligen una; se para con el ratón encima, con el foco
  dentro o con la pestaña escondida, y con «reducir movimiento» no avanza sola.
  Sin JavaScript se queda la primera, sin puntitos. Es `sticky` y alta como la
  pantalla, así acompaña al registro, que es largo.
- **Los dibujos son los de «Funciones» del sitio**, no copias:
  `build_assets.py` convierte cuatro de `landing/src/partials/feature-*.svg.j2`,
  con sus palabras de `landing/content.py`, en `templates/_art-*.svg`
  (GENERADO), y copia a `panel.css` las reglas `.art-*` de
  `landing/src/site.css`. Cambiar un dibujo del sitio pide correr también
  `build_assets.py`, y su `--check` lo avisa.
- **Entrar:** «Hola de nuevo» (la pestaña sigue diciendo «Entra a tu cuenta») y
  debajo «¿Todavía no tienes cuenta? Regístrate»; correo y contraseña con un
  ejemplo dentro; en una fila, «Recordarme 30 días» y «¿Olvidaste tu
  contraseña?»; el botón a todo el ancho; y después de la raya con «o», los
  proveedores. Agregando otra cuenta (`?add=1`) siguen los textos de antes.
- **Registrarse:** «Crea tu cuenta» y debajo «¿Ya tienes una cuenta? Iniciar
  sesión» (antes iba al pie). **Los proveedores van arriba**, con la raya «o con
  tu correo» debajo, al revés que en entrar: el formulario es largo, y quien
  viene a usar Google no tiene que bajar hasta el final para encontrarlo.
- **Los proveedores** (`.providers`) van lado a lado y del mismo tamaño; uno solo
  ocupa todo el ancho.
- **En el teléfono** (por debajo de 900 px) la izquierda es una franja azul con
  el ala, sin las funciones, y el formulario va a todo el ancho.

## Entrar y registrarse con Google, GitHub o Apple (octubre de 2026)

**Los dos van por el mismo camino.** Google llegó primero y GitHub se sumó el
15 de octubre de 2026: las rutas son de un proveedor (`/login/<proveedor>`,
`/login/<proveedor>/return`, `/signup/<proveedor>` y
`/settings/<proveedor>/disconnect`, con `<any(google, github):proveedor>`), y
`PROVIDERS` en `blueprints/auth/routes.py` dice de cada uno su servicio, el
campo de la cuenta (`google_sub` o `github_id`) y su marca. Lo que se arregle
en uno vale para el otro. Las direcciones de Google no cambiaron. Lo de abajo
se escribió para Google y vale igual para GitHub, salvo lo que dice su propio
apartado.

- **Un solo botón por proveedor, «Continuar con Google» y «Continuar con
  GitHub»**, lado a lado, en entrar y en el registro. Cada uno sale solo con
  su par de variables (`GOOGLE_CLIENT_ID` y `GOOGLE_CLIENT_SECRET`,
  `GITHUB_CLIENT_ID` y `GITHUB_CLIENT_SECRET`); sin ellas, sus rutas dan 404.
- **OAuth 2.0 con código y PKCE, con `urllib`** (`services/google_auth.py`). El
  `state` y el verificador viven en la sesión. **Quién es lo dice Google al
  servidor**: el código se cambia por un token y con él se pide `sub`, `email`,
  `email_verified` y `name`. Un correo sin verificar no entra. Se pide `openid
  email profile` y nada más.
- **Con cuenta: solo por `google_sub`, nunca por el correo** (octubre de 2026).
  Hasta entonces, sin cuenta con ese id se buscaba por el correo verificado y
  se enlazaba sola, y así GitHub abría una cuenta de contraseña que tenía el
  mismo correo. Ahora, si el correo tiene una cuenta que no está conectada a
  ese proveedor, **no se entra ni se enlaza**, y se dice cómo entra esa cuenta
  (`how_to_enter()`, leído de lo que tiene: contraseña o los proveedores
  conectados, no de cómo nació): «Ya tienes una cuenta con … que entra con
  contraseña. Entra con ella y conecta Google en Configuración → Seguridad», o
  «Esa cuenta entra con GitHub». Después de entrar pasa lo mismo que tras la
  contraseña (`finish_sign_in()`): suspendida no entra, el doble factor se pide
  si está puesto, aviso de dispositivo nuevo y varias cuentas abiertas.
- **Un registro con contraseña sin confirmar del mismo correo se descarta**
  (`accounts.unconfirmed_signup()`): sin esto, alguien registraba el correo de
  otra persona sin confirmarlo, y cuando la dueña entraba con Google la cuenta
  quedaba enlazada y confirmada con una contraseña que conocía el otro. Solo
  uno que vence (`purge_at`) y que no es un usuario invitado (`owner_id`: una
  invitación pendiente no se toca). Se borra **al guardar el registro con el
  proveedor**, con `erase.erase()` (pudo entrar y dejar sesiones o archivos),
  y la pantalla de completar la cuenta lo avisa antes.
- **Conectar Google, GitHub o Apple** es «Conectar», en Seguridad
  (`/settings/<proveedor>/connect`): pide **la prueba de quién es**, la misma que
  crear una clave de API (la contraseña, o un código al correo sin ella, y el
  código de la app si tiene segundo factor; `check_proof()`, que vive en
  `blueprints/auth/routes.py` desde octubre de 2026 y developers importa). Lo
  que se pidió (`intent: link`, la cuenta y la sesión) va en
  `session["<proveedor>_request"]`, nunca en el `state`, y la vuelta es la de
  siempre (GitHub solo acepta esa ruta). A la vuelta se exigen **la misma cuenta
  y la misma sesión**; un id que ya es de otra cuenta no se enlaza. Llega un
  aviso de seguridad al correo, que no se apaga: «Se conectó Google a tu
  cuenta».
- **Una cuenta de Google o de GitHub entra a una sola de Sobreala**: índice
  único parcial sobre `google_sub` y sobre `github_id` (`db._provider_indexes`,
  al final de `ensure_indexes`, que mira antes si hay repetidos y, si los hay,
  lo anota y sigue).
- **Sin cuenta:** `/signup/google` pide lo que Google no da (empresa, teléfono
  personal, los de la empresa y dirección). Nace **confirmada y sin contraseña**,
  con la bienvenida y el aviso al administrador de siempre. Si un día quiere
  contraseña, la crea con «¿Olvidaste tu contraseña?». Las pantallas que piden
  la contraseña actual (cambiar el correo, apagar el doble factor) la piden
  igual.
- **Regla 7:** entrar con Google no busca por un correo escrito. Decir cómo
  entra la cuenta de un correo solo se le dice a quien Google acaba de probar
  que es dueño de ese correo (octubre de 2026): a un extraño no le revela nada.
- **Seguridad** dice «Google: Conectado» con «Desconectar», que solo se deja con
  contraseña puesta.
- **Lo que hace falta en Google Cloud:** un cliente OAuth de tipo aplicación web,
  la pantalla de consentimiento (nombre, logo, privacidad y términos) y la
  dirección de vuelta `https://app.sobreala.com/login/google/return`.

### Lo que GitHub tiene distinto

- **`services/github_auth.py`**, con `urllib` como el de Google: código con
  `state` y **PKCE (S256)**, que GitHub admite en las aplicaciones OAuth desde
  julio de 2025; el secreto se sigue mandando, desde el servidor. Se pide
  `read:user user:email` y nada más: ni repositorios.
- **Quién es:** `/user` da el identificador (que no cambia aunque cambie el
  nombre de usuario o el correo) y el nombre; `/user/emails` da los correos, y
  de ellos **vale solo el principal y verificado**. Sin él, no entra, como el
  correo sin verificar de Google. `who()` devuelve lo mismo que el de Google
  (`sub`, `email`, `email_verified`, `name`).
- **Sin cabecera `User-Agent`, la API de GitHub contesta que no a todo**: va en
  cada llamada. Y un código que no vale no da un error HTTP: da 200 con
  `error`, y eso también se trata como error.
- **El botón** lleva la marca de GitHub (`_github-mark.svg`) en el color del
  texto, así sigue el tema.
- **La privacidad** lo dice al lado de Google: qué da GitHub (el correo
  principal verificado, el nombre y el identificador) y para qué.
- **Lo que hace falta en GitHub:** Settings → Developer settings → OAuth Apps →
  New OAuth App, con el nombre «Sobreala», la página `https://sobreala.com` y la
  dirección de vuelta `https://app.sobreala.com/login/github/return`. Del
  resultado salen el Client ID y el secreto (que se genera ahí), que van en
  Railway como `GITHUB_CLIENT_ID` y `GITHUB_CLIENT_SECRET`.

### Lo que Apple tiene distinto (octubre de 2026)

- **`services/apple_auth.py`**, el tercero de `PROVIDERS` (`apple_sub`,
  `_apple-mark.svg`, «Continuar con Apple»). Sale con sus **cuatro** variables:
  `APPLE_CLIENT_ID` (el Services ID), `APPLE_TEAM_ID`, `APPLE_KEY_ID` y
  `APPLE_PRIVATE_KEY` (el `.p8` entero; si en Railway queda con «\n»
  escritos, se arreglan solos).
- **La clave secreta es un JWT ES256** firmado con la `.p8`, que vale cinco
  minutos (`client_secret()`). Por eso `cryptography` está en
  `requirements.txt`.
- **Sin PKCE: `nonce`.** Viaja al salir y vuelve dentro del `id_token`, y es
  lo que ata la vuelta a esa salida. Del token se comprueban el emisor
  (`https://appleid.apple.com`), la audiencia (el Services ID), el vencimiento
  y el `nonce`. La firma del token no se baja: llega directo del servidor de
  Apple al nuestro por HTTPS y a cambio de la clave secreta, que es lo que
  permite OpenID Connect (3.1.3.7).
- **La vuelta es un POST desde `appleid.apple.com`** (`form_post`, obligatorio
  al pedir el nombre y el correo), y en ese POST el navegador no manda la
  galleta de sesión (`SameSite=Lax`). La ruta contesta con
  `oauth-relay.html`, que lo vuelve a mandar desde nuestra página (con
  JavaScript solo, sin él con un botón), y ese segundo POST sí la lleva.
  **La primera respuesta no escribe nada en la sesión**: si lo hiciera, el
  navegador cambiaría la galleta de quien está entrando.
- **El nombre llega solo la primera vez**, en el POST (`user`) y no en el
  token: llena el registro, que se puede corregir, y no decide nada.
- **«Ocultar mi correo» se acepta**: la cuenta queda con la dirección
  `@privaterelay.appleid.com`, que es verificada. Para que le lleguen los
  códigos y los avisos, **`sobreala.com` tiene que estar registrado en el
  servicio de reenvío de Apple** (abajo).
- **Lo que hace falta en Apple Developer** (Certificates, Identifiers &
  Profiles):
  1. **Identifiers → App IDs**: uno para Sobreala con «Sign in with Apple»
     marcado (aunque no haya app de iPhone, el Services ID cuelga de él).
  2. **Identifiers → Services IDs**: uno nuevo (por ejemplo
     `com.sobreala.web`), con «Sign in with Apple» → Configure: el App ID de
     arriba, el dominio `app.sobreala.com` y la dirección de vuelta
     `https://app.sobreala.com/login/apple/return`. Su identificador es
     `APPLE_CLIENT_ID`.
  3. **Keys**: una nueva con «Sign in with Apple», asociada al App ID. Se baja
     el `.p8` **una sola vez**: su contenido es `APPLE_PRIVATE_KEY` y su Key ID,
     `APPLE_KEY_ID`. El Team ID sale arriba a la derecha de la cuenta.
  4. **Services → Sign in with Apple for Email Communication**: registrar
     `sobreala.com` y la dirección `notifications@sobreala.com`. Apple
     comprueba SPF y DKIM, que ya están (`docs/ses.md`). Sin esto, a quien
     ocultó su correo no le llega nada de Sobreala.
- **La privacidad** lo dice al lado de Google y GitHub, y la ayuda lo nombra.

## Lo que se cerró de seguridad (octubre de 2026)

Lo que estaba en `docs/pendientes.md` y lo que salió al revisarlo. Las pruebas
están en `tests/test_endurecido.py`.

- **La contraseña del segundo factor está atada a la cuenta y a la sesión**
  (`password_proved(account)`), como la prueba de las claves de API: con varias
  cuentas abiertas en un navegador, probar la contraseña de una no abría el QR
  de otra... y antes sí. El secreto que se está preparando también va con su
  cuenta (`two_factor_setup` es `{account, secret}`).
- **La IP del panel** (`client_ip()`) usa la regla de la API
  (`api_auth.caller_ip()`): `CF-Connecting-IP` solo cuenta si la conexión viene
  de Cloudflare. Antes, quien le hablaba directo a Railway escribía la IP que
  quisiera y tenía límites de intentos nuevos en cada uno.
- **Eliminar la cuenta gasta el código antes de borrar**, y si otra petición lo
  gastó primero, no borra: un código vale una vez aunque lleguen dos juntas.
- **Un salto de línea no llega a una cabecera**: los nombres de los contactos
  se guardan en una línea (`fields.single_line()`), y el asunto ya armado
  también pasa por ahí, en las campañas y en la vista de la API (un nombre
  guardado antes con el salto rompía el envío, y en una cabecera es lo que
  permite inventar otra).
- **El lienzo no revienta con números que no son números**: `NaN` e `Infinity`
  no son JSON y se rechazan al leer (también el ZIP), y un `1e999`, que sí es
  JSON y da infinito, cae al valor por omisión (`canvas._finite`). Antes era un
  error 500, o un `NaN` guardado.
- **Lo que podía llenar la base tiene tope**: 300 plantillas por cuenta también
  en el panel (`designs.LIMIT`, el mismo de la API), y 50 MB de archivos de
  Redactar guardados a la vez por cuenta (`downloads.ACCOUNT_BYTES`; se liberan
  solos a los 30 días).
- **HSTS**: el panel lo manda en toda respuesta por HTTPS (también la API), y el
  sitio público en su `_headers`, que escribe `build_site.py` junto con
  `X-Frame-Options`, `nosniff`, `Referrer-Policy`, `Permissions-Policy` y
  `frame-ancestors 'none'`. El sitio no lleva una política de scripts: tiene
  scripts en línea, y una lista mal hecha lo rompería en silencio.
- **El aviso de SES** no da error 500 con un JSON anidado sin fin.
- **`/health` es público y no dice a dónde se conecta**: con la base caída
  responde solo el tipo de error, y el mensaje entero (que nombra los
  servidores del clúster de Atlas) va al log.

## La API y la cuenta (octubre de 2026)

- **Avisos de seguridad que no se apagan**: se creó o se revocó una clave de
  API, se revocó sola porque llegó en una URL, se agregó (o cambió) un webhook
  que manda datos a un servidor, y se desactivó un webhook que llevaba 72 horas
  fallando.
  Van por `services/notices.py` con `mail_log` `api_key` y `webhook`.
- **La prueba de quién es** para crear una llave o un aviso queda atada a la
  cuenta y a la sesión (`blueprints/developers/routes.py`); sin contraseña se
  pide un código al correo (`tokens.API_ACCESS`).
- **Eliminar la cuenta** se lleva también `api_keys`, `api_log`,
  `api_idempotency`, `messages`, `webhook_endpoints` y `webhook_deliveries`.
