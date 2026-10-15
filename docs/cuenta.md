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
  clientes o socios, alumnos, formulario, eventos, otra), y un **sitio web
  opcional** (`demo_website`, de hasta 200 caracteres, con `https://` si no lo
  trae). Los dos selectos dicen qué plan le conviene y si la lista es de fiar, que
  es lo primero que revisa Amazon. Se le escribe al teléfono personal del
  registro. Solo el dueño y con el correo confirmado.
- **Con la solicitud hecha el formulario ya no sale**: queda un aviso verde con
  su gancho que dice solo «Tu solicitud ha sido recibida» (sin la espera ni el
  teléfono, que se quitaron en octubre de 2026), y un segundo
  envío no guarda nada ni vuelve a avisar. Antes se podía pedir otra vez, con un
  tope de tres al día (`DEMO_PER_ACCOUNT`, ya quitado). Corregir una solicitud
  enviada no se ofrece. A quien administra le llega «{empresa} pidió una
  demostración» (`admin_demo`, con interruptor), con el teléfono y las respuestas,
  y la cuenta sale en el filtro «Piden demostración» de Cuentas. La ficha enseña
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
- **la dirección** (`postal_address`, la misma que sale al pie de las
  campañas);

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
- **Google solo sale si la cuenta está conectada**, en Contraseña, con su
  «Desconectar». Quien se registró sin Google no ve la fila; se conecta solo la
  primera vez que entra con Google.
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
«Sobreala» en Changa One, la tipografía de la marca. La palabra va **dentro de
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

## Entrar y registrarse con Google (octubre de 2026)

- **Un solo botón, «Continuar con Google»**, en entrar y en el registro. Sale solo
  con `GOOGLE_CLIENT_ID` y `GOOGLE_CLIENT_SECRET`; sin ellos, las rutas dan 404.
- **OAuth 2.0 con código y PKCE, con `urllib`** (`services/google_auth.py`). El
  `state` y el verificador viven en la sesión. **Quién es lo dice Google al
  servidor**: el código se cambia por un token y con él se pide `sub`, `email`,
  `email_verified` y `name`. Un correo sin verificar no entra. Se pide `openid
  email profile` y nada más.
- **Con cuenta:** se busca por `google_sub`, y si no, por el correo verificado;
  la primera vez queda enlazada (`google_sub`) y, si estaba sin confirmar, queda
  confirmada. Un correo enlazado a **otra** cuenta de Google no entra. Después
  pasa lo mismo que tras la contraseña (`finish_sign_in()`): suspendida no
  entra, el doble factor se pide si está puesto, aviso de dispositivo nuevo y
  varias cuentas abiertas.
- **Sin cuenta:** `/signup/google` pide lo que Google no da (empresa, teléfono
  personal, los de la empresa y dirección). Nace **confirmada y sin contraseña**,
  con la bienvenida y el aviso al administrador de siempre. Si un día quiere
  contraseña, la crea con «¿Olvidaste tu contraseña?». Las pantallas que piden
  la contraseña actual (cambiar el correo, apagar el doble factor) la piden
  igual.
- **Regla 7:** entrar con Google no busca por un correo escrito, solo por el que
  Google confirma de quien está ahí.
- **Seguridad** dice «Google: Conectado» con «Desconectar», que solo se deja con
  contraseña puesta.
- **Lo que hace falta en Google Cloud:** un cliente OAuth de tipo aplicación web,
  la pantalla de consentimiento (nombre, logo, privacidad y términos) y la
  dirección de vuelta `https://app.sobreala.com/login/google/return`.
