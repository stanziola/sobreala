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

`services/notices.py` es el único sitio que los compone, y son doce:

| Correo | Cuándo sale | ¿Se puede apagar? |
|---|---|---|
| Contrataste el plan X | Al cobrar PayPal, y al ponerle el plan a mano | Sí, «Pagos y plan» |
| Renovaste el plan X | Igual, cuando el plan pagado es el que ya corría (ya no se puede pagar así) | Sí, «Pagos y plan» |
| Tu plan vence en 7 días | Al entrar al panel, si falta una semana o menos. Sin botón: se vuelve a contratar al vencer | Sí, «Estado de tu plan» |
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
