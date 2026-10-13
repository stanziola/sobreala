# El panel del cliente y el de administración

Detalle que vivía en `CLAUDE.md`, movido tal cual para que ese archivo
cupiera en el límite. Lo esencial (las reglas, las convenciones y el
resumen de cada parte) sigue allí; esto es lo que hay que leer antes de
tocar esta parte.

## Panel del cliente

**Al entrar, se aterriza en el sitio público**, que es la portada, y desde ahí
se elige con el menú de siempre. **Administre o no**: una sola regla para el
mismo momento. Antes un cliente caía en Estadísticas y un administrador en
`/admin`, que son dos pantallas concretas, y la diferencia se notaba justo al
saltar entre cuentas abiertas —una te dejaba en un sitio y la otra en otro—. Lo
decide `landing()` en `blueprints/auth/routes.py`, y como devuelve una dirección
de otro dominio, es lo que obliga a nombrar el sitio en `form-action`. **El
«Volver» de la lista de cuentas lleva ahí también**: llevaba a las Estadísticas
de la cuenta en uso.

**Lo primero que ve una cuenta nueva es `/welcome`, no el panel.** Confirmar
el registro aterriza ahí. Antes se caía directo en Estadísticas, que sin plan
contratado y sin un solo envío es un cuadro vacío diciendo que todavía no ha
pasado nada: la peor primera pantalla posible.

**Mientras la cuenta siga cerrada** (octubre de 2026, ver «Abrir la cuenta» en
`docs/cuenta.md`), `/welcome` es la pantalla de la demostración: los dos caminos
que la abren, lo que incluye la llamada, el formulario para pedirla (a qué
se dedica el negocio y para qué usará Sobreala) y los botones de ver los planes y de Configuración.
Las cuatro pantallas de cliente, que siguen en el menú, la devuelven ahí (con
`?para=`, que ya no se lee: el aviso de a cuál quería entrar se quitó en octubre
de 2026). **Ya abierta y sin plan**, dice que la cuenta está lista y lleva esos
dos botones, como antes.

**Los enlaces no se subrayan** (octubre de 2026), en el panel ni en el sitio:
quietos van en su azul (`--color-accent-strong`) y, al pasar el mouse, los de
texto se ponen del azul de la marca (`--color-accent`). La regla es
`a:not([class]):hover`: botones, menú y pestañas llevan clase y su propio
efecto, y un botón azul con la letra azul no se leería. En el pie del sitio, que
va sobre el azul de la marca, se ponen celeste (`--color-accent-light`).

Esa dirección se queda en el historial, así que lleva dos guardas que **no son
para el día del registro**, donde no pueden darse: con un plan ya contratado
manda al panel, y a un administrador lo devuelve a `/admin`.

**`/dashboard` es la pantalla de Estadísticas.** La dirección no cambió aunque la
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
  y enlaza a Planes (`/#planes`). Es un SVG y no un ancho en `style`, que la cabecera
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
entradas, para que no puedan separarse. **`/contacts`** tiene cinco
pantallas: la lista —una fila por contacto: su correo, su nombre, **sus
columnas propias**, si está activo, anulado o incompleto, sus etiquetas y
cuándo entró—, la importación, las etiquetas, las columnas propias y las
supresiones. Agregar uno a mano tiene su propia pantalla, a la que se llega
desde un botón encima de la lista, y exportar pasa por una confirmación que dice
cuántos van a salir. **Borrar también pregunta**: el botón de cada fila, y el de
eliminar los anulados, llevan a una pantalla que dice cuántos se van y tiene el
botón rojo; el que borra es el POST. **`/templates`** tiene arriba crear y cargar, y debajo
todas las piezas de la cuenta: las del lienzo, las cargadas en HTML y las
prediseñadas que quedaron de antes. Y todo lo demás vive en **`/settings`**, con cuatro secciones:
**Cuenta** (datos, estado y plan), **Seguridad** (contraseña, autenticación de
múltiples factores, dispositivos conectados y **los usuarios de la cuenta**),
**Notificaciones** y **Facturación**
(`/settings/billing`, que no cambió de dirección porque ahí vuelve PayPal):
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
galleta `sa_tz` con la zona del navegador; la primera página de un dispositivo
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

**El modo claro u oscuro viaja entre los dos sitios en la galleta `sa_theme`**,
en `.sobreala.com`. El sitio y el panel son dos orígenes y cada uno tiene su
propio almacenamiento, así que guardarlo solo ahí dejaba el panel en claro
después de elegir oscuro en el sitio. El guion de la cabecera de los dos mira
primero la galleta; lo que alguien eligió antes de que existiera se copia a ella
la primera vez que abre cualquiera de los dos.

**El idioma está anunciado, no traducido.** El menú enseña «Español» y «Inglés
(pronto)»; el inglés se hará cuando haya a quién dárselo.

**Salir cuesta un clic desde los dos sitios.** El sitio público está en otro
dominio y no lleva ningún testigo del panel, así que su «Cerrar sesión» no puede
ser un formulario: es un enlace, y un enlace es un `GET /logout`. Ese GET cierra
igual que el POST del menú del panel, y por eso no se le pide testigo.

Lo único que no obedece es una petición que el navegador **dice estar
adelantando** —`Sec-Purpose`, `Purpose` o `X-Moz` con `prefetch`—: sin eso, un
navegador que precarga enlaces sacaría a alguien de su cuenta sin que hubiera
pulsado nada. Se cierra por omisión y se calla solo ante esa cabecera; si un
intermediario se la comiera, lo que se pierde es la protección y no el salir.
`logout.html` sigue existiendo, pero solo la ve esa precarga.

### Varias cuentas abiertas a la vez

**«Cambiar de cuenta», encima de salir, lleva a `/switch-account`**: la lista de
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
  contraseña y su segundo paso: `/login?add=1`, que se titula «Agregar una
  cuenta». Aquí no se abre ninguna puerta que no estuviera ya abierta. La marca
  de «vengo a agregar» vive en la sesión y no en la dirección, porque el segundo
  paso pasa por otra pantalla.
- **Una cuenta que ya está abierta no se agrega otra vez**: sale «Esa cuenta ya
  está abierta en este navegador.», antes de mirar la contraseña, y no se abre
  nada. Antes abría otra sesión y cerraba la vieja.
- **Agregar una cuenta que nunca entró desde este navegador manda el aviso de
  dispositivo nuevo**, aunque el navegador tenga otra abierta. Para esa cuenta
  es un navegador nuevo, y sin el aviso cualquiera que abriera primero una
  cuenta suya podría entrar a otra sin que su dueño se enterara.
- **Y se puede crear una cuenta nueva sin cerrar la abierta**, por el mismo
  camino: el pie de esa pantalla («¿Te gustaría crear otra cuenta?») lleva a
  `/signup?add=1`, que se dibuja en vez de devolver a la portada, y al
  confirmar el código la cuenta nueva se suma a las abiertas. Ninguna de las dos
  pantallas lleva un recuadro que lo explique.
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

**Cerrar «Este dispositivo» en Seguridad sale solo de esa cuenta**
(`forget_active()`, como «Cerrar esta» en la lista), y si quedan otras abiertas
lleva a elegir entre ellas. Antes vaciaba la galleta entera: las otras cuentas
se quedaban vivas sin su testigo y salían en su Seguridad como otro dispositivo
con la misma IP. Por lo mismo, `forget_active()` conserva la duración de la
galleta de las que quedan.

## Panel de administración

`/admin`, con verificación de rol. **No es donde se aterriza al entrar** —eso es
el sitio público, para todos—: se llega desde el menú, que para esta cuenta
enseña Administración de primera fila. Sí es a donde la devuelve
`not_for_admins()` si abre una pantalla de cliente. Cuatro pantallas:
**Estadísticas · Cuentas · Plantillas subidas · Correos del sistema**.

**Correos del sistema** (`/admin/emails`) es la del «no me llegó el código»: se
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
**«piden demostración»**, que no es un estado sino la cola que pide acción: la
pidieron y su cuenta sigue cerrada. Hasta octubre de 2026 era «esperando
habilitación», y se fue con la habilitación. Desde ese mes tiene otra,
**«Por verificar»**: las que subieron un documento que espera revisión.

Arriba del todo de la ficha está lo único que espera una decisión: **la
demostración**, con cuándo la pidió, su teléfono como enlace de WhatsApp, sus
dos respuestas y el botón «Abrir la cuenta», que pide un motivo. Junto a los
datos de contacto, sus teléfonos (y el RUC o la cédula que escribieron las
cuentas de antes). Debajo de la demostración, **las verificaciones** (ver el
documento, verificar o rechazar, y «Enviar correo al cliente») y **limitar la
cuenta** (ver `docs/cuenta.md`).
Debajo, **un solo formulario** —plan, ciclo, suspensión y un motivo—: si
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

1. **Tasa de rebotes y quejas agregada en la portada** — la de Sobreala, no la
   de cada cliente. Es la métrica que puede cerrar el negocio.
2. Estado de pagos y renovaciones (Yappy puede requerir cobro manual).
3. Envíos en curso, pausados y fallidos.
4. Ver el panel como el cliente, para soporte. Queda registrado.
5. Registro de actividad: aprobaciones, cambios de plan, pausas, con motivo.
6. Buscador global de direcciones, para suprimir a quien escriba pidiendo la baja.

### `admin_events`
Un documento por decisión de un administrador: qué cambió, de qué a qué, sobre
qué cuenta, cuándo y **por qué**. El motivo no es opcional; la pantalla no deja
aplicar un cambio sin él, porque meses después esa frase es la única respuesta
honesta a «por qué me suspendieron». Sin TTL, como `auth_events`.
