# Cobrar un plan

Detalle que vivía en `CLAUDE.md`, movido tal cual para que ese archivo
cupiera en el límite. Lo esencial (las reglas, las convenciones y el
resumen de cada parte) sigue allí; esto es lo que hay que leer antes de
tocar esta parte.

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
  →  paga en Paguélofácil  →  vuelve a /settings/billing/card/return
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

Pagar mueve la cuenta a `active` y escribe `plan`, `plan_until` y `plan_cycle`
(mensual o anual; lo de antes se lee como mensual). **El mismo plan no se vuelve
a pagar mientras está vigente** (septiembre de 2026): se compra otra vez cuando
vence, y cuenta desde ese día. Lo decide
`accounts.current_plan()`, que da el plan solo mientras `plan_until` no pasó, y
lo comprueban `/checkout/<plan>`, que lo dice con la fecha y no ofrece pagar, y
el POST que crea el pago. Hasta entonces pagar antes de tiempo sumaba al final
de lo que quedaba; `renews_from()` y el correo de «Renovaste» siguen ahí por si
un pago llega así, pero ya no hay camino para crearlo. Subir a un plan mayor sí
se puede, y empieza hoy.

**Mejorar de plan lleva prorrateo** (`services/upgrade.py`, y la regla en
`docs/pricing.md`). Con un plan vigente **solo se mejora**, que es lo que hace
que el crédito nunca sobre: de un mensual, a uno mayor en cualquier ciclo o al
mismo en anual; de un anual, solo a uno mayor en anual (`upgrade.refused()`).
**El descuento son los correos sin usar** al precio al que se pagaron
(`upgrade.credit()`): en un mensual, el mes × lo que queda de su cuota; en un
anual, los meses enteros que faltan después de este más lo que queda de la
cuota de este mes, a un doceavo del año. Lo calcula `start_payment()` al crear
el intento y lo guarda en él (`price`, `credit`, `amount`, `upgrade`), y **la
vuelta de PayPal y la de tarjeta comparan contra ese `amount`**, no contra el
precio de lista. Al cobrar, la mejora empieza hoy y **el mes empieza de nuevo**:
`activate_plan(fresh_month=True)` guarda en `quota_base` cuánto iba enviado
este mes, y `used_this_month()` lo resta, tanto para la cuota como para la
barra de Estadísticas. Un correo enviado entre crear el intento y pagar no
cambia el descuento ya calculado.

**`/checkout/<plan>` es un resumen, no una elección.** Llega con el ciclo que
se eligió en Planes (`?cycle=yearly`) y enseña un desglose **que suma**: el
plan y el descuento con sus correos, **sin ITBMS**; la fila «ITBMS (7%)»; y al
final el **total a pagar ahora**, que es lo que se cobra y lleva el ITBMS
dentro, como todos los precios. El ITBMS sale del total (`plans.itbms_in()`),
el plan sin él es su precio entre 1.07 (`plans.without_itbms()`) y el descuento
es la diferencia, así las filas cuadran al centavo: Negocio, $23.36 + $1.64 =
$25.00; de Negocio a Empresa con 10,000 correos sin usar, $51.40 − $15.58 +
$2.51 = $38.33 (`upgrade.quote()`). La tasa es `plans.ITBMS`. Después, un solo
botón «Pagar $X», con los métodos de pago encima; el otro ciclo queda a un
enlace si también se puede. **Cada método son sus logos a color, sin título,
sin descripción y sin fondo propio**: PayPal; Visa y Mastercard en la tarjeta;
Yappy en el que dice «pronto» (`PAY_LOGOS` en las rutas, `_pay_logos.html`, y
los archivos los copia `build_assets.py` de `brand/payments/` a
`static/img/payments/`). El nombre del método va en el texto alternativo de sus
logos y, escondido, en su «Usar este», para que un lector de pantalla no diga
tres veces «Usar este» sin decir de qué. De noche descansan sobre la tarjeta
oscura tal cual: hubo una pastilla blanca y se quitó, sabiendo que PayPal, Visa
y Yappy, que son azules, ahí se leen poco. Debajo, una sola frase: «Sobreala
nunca guarda tus datos de pago.» Del cliente
de fuera de Panamá no se sabe el país (el panel no guarda sus datos de
facturación), así que el desglose dice ITBMS para todos y la factura, que se
hace a mano, es la que va sin él. Si el ciclo
pedido no se puede y el otro sí (quien tiene un anual y pulsó un mensual), enseña
el que sí.

**Al volver de un pago cobrado se aterriza en su recibo**
(`/settings/billing/receipt/<id>`, solo del dueño y solo cobrado): el número
de pago, el plan y el ciclo, el método, la fecha y hora y, de cifras, **solo el
total pagado**: ni el ITBMS ni el descuento, que en el resumen va sin ITBMS y
serían dos cifras distintas para lo mismo. El círculo de arriba gira como si
cargara, se cierra y dibuja el ganchito, y se queda quieto, **en verde**
(`--color-success`, más claro de noche); es solo CSS, y con «reducir
movimiento» sale ya terminado. Recargar la vuelta vuelve a enseñar el mismo recibo, sin cobrar ni
alargar nada. El comprobante por correo dice lo cobrado y el descuento, este
con su ITBMS dentro. Pagar **no** habilita el envío: eso es la otra puerta, y el
comprobante que sale lo dice para que no se descubra al intentar enviar.

Del cobro salen **dos correos**: el comprobante al cliente y un aviso a quien
administra, porque el que pagó queda esperando una habilitación que hace una
persona. Los dos van después de todo lo que decide algo: si el correo no sale,
el pago sigue cobrado y el plan activo.

**Hubo un cuarto plan, Corporativo, y se quitó** (septiembre de 2026): iba sin
precio público y a la medida. Quedan tres, todos con precio y todos comprables
por la web.

**El plan se elige en Planes (`/#planes`), no dentro del panel.** El botón de cada plan
del sitio público lleva a `/checkout/<plan>`, que enseña lo que cuesta y tiene
el botón de pagar; sin sesión manda a entrar llevando **el nombre del plan, nunca
una dirección**, y al abrir sesión sigue hasta ahí. Configuración → Opciones de
pago ya no vende: dice desde dónde se cobra, qué plan hay contratado y qué se ha
cobrado.

**Las tarjetas de Planes tienen su interruptor de mensual y anual**, con
`landing/assets/js/plans.js`, que solo baja la página única (el bloque
`scripts` de `src/base.html.j2`). En anual cada tarjeta enseña **el equivalente
mensual** —el anual entre doce— y debajo **«Total a pagar ahora»** con lo que
se cobra de verdad (el mes en mensual, el año en anual), y el número va de una
cifra a otra con un contador propio. Las dos cifras salen de
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

Cuatro cosas más de esas tarjetas:

- **La página nace en mensual y con todo dibujado**, así que sin JavaScript se
  leen los tres planes, sus precios y sus botones. **El interruptor sí se
  esconde sin el guion** (`.cycle` nace en `display: none` y `plans.js` le pone
  `is-ready`): un botón que no hace nada es peor que no tenerlo.
- **El botón de cada plan dice «Obtener Plan X»**, y **con un plan vigente
  siguen la regla de mejorar** según el interruptor (`nav.js`, leyendo la migaja
  `sa_in`, que lleva el plan y su ciclo, `1:negocio:monthly`, solo mientras está
  vigente; `plans.js` avisa con el evento `sa:cycle` cada vez que cambia el
  ciclo): los de abajo y el propio dicen «Ya tienes todas las ventajas»,
  apagados; el propio en anual, si se tiene mensual, «Pasar a anual»; los de
  arriba, «Mejorar a X», salvo en mensual para quien tiene un anual, que dicen
  «Solo en anual», apagados. Debajo de las tarjetas, con el ITBMS, una nota dice
  que al mejorar se descuentan los correos sin usar y el mes empieza de nuevo.
- **El botón de cada plan lleva el ciclo al panel**, con `?cycle=yearly`, y
  `/checkout/<plan>` resalta ese botón. Sin parámetro, o con uno inventado,
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
