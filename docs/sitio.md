# El sitio público (sobreala.com)

Detalle que vivía en `CLAUDE.md`, movido tal cual para que ese archivo
cupiera en el límite. Lo esencial (las reglas, las convenciones y el
resumen de cada parte) sigue allí; esto es lo que hay que leer antes de
tocar esta parte.

## Una sola página (octubre de 2026)

**Todo el sitio es `index.html`**, menos Privacidad y Términos. Las secciones
van en este orden, cada una con el ancla a la que baja su botón de la barra:

| Ancla | Qué lleva | Plantilla |
|---|---|---|
| `#inicio` | La portada, «¿Sigues enviando correos masivos…?» y «Haz crecer tu negocio» | `src/pages/index.html.j2` |
| `#planes` | Interruptor y tarjetas, la tabla y el glosario | `src/sections/planes.html.j2` |
| `#como-funciona` | Features con su lista, la tira de plantillas, los tutoriales y el envío | `src/sections/como-funciona.html.j2` |
| `#nosotros` | Quiénes somos | `src/sections/nosotros.html.j2` |
| `#preguntas` | Una sola lista: las generales y las de facturación | `src/partials/faq.html.j2` |

**Contacto es el pie** (`id="contacto"` en `base.html.j2`): WhatsApp, correo e
Instagram. Hubo una sección «Hablemos de tu lista» antes de las preguntas, y se
quitó en octubre de 2026 porque repetía el pie; `/contact/` y `/#contacto`
aterrizan ahí. Con ella se fue el `id` repetido que había entre las dos.

- **Cada sección conserva sus textos en su diccionario de `content.py`**
  (`PRICING`, `HOW`, `ABOUT`), y `index.html.j2` la incluye con
  `{% with page = … %}`, así que dentro nada cambió de nombre. `CONTACT_PAGE`
  solo guarda el título de la página de paso. El `hero` de
  cada una es ahora la cabeza de su sección, con su `h2`: hay un solo `h1`.
- **La barra lleva Inicio, Planes y Cómo funciona.** Nosotros está solo en el
  pie (octubre de 2026), y su sección sigue en la página.
- **Los botones de la barra solo desplazan** (`/#planes`, con la `/` para que
  sirvan también desde las legales). La barra fija no tapa el título:
  `scroll-margin-top` en `.page-part` y en las secciones con `id`. **El botón de
  la sección que se está leyendo se marca** con un `IntersectionObserver` en
  `nav.js`, mirando una franja justo debajo de la barra; en Nosotros y en las
  preguntas, que no tienen botón, se queda el último.
- **Las direcciones de antes siguen respondiendo**: `/pricing/`,
  `/how-it-works/`, `/about/` y `/contact/` son páginas de paso
  (`src/redirect.html.j2`, tabla `REDIRECTS` de `build_site.py`) con
  `noindex`, que mandan a su ancla y conservan el `#` que traigan, así
  `/how-it-works/#templates` sigue abriendo su tutorial. El panel ya enlaza
  directo a `/#planes`. `sitemap.xml` y las tarjetas para compartir son solo de
  `/` y las legales.
- **La página carga los cuatro guiones**: `trouble.js`, `carousel.js`,
  `plans.js` y `tutorial.js`. Las pestañas de los tutoriales usan `contacts`,
  `templates`, `campaigns`, `stats` y `settings`, que no chocan con las anclas
  de las secciones.

## La portada

**Arriba van el título y dos botones, nada más** (octubre de 2026): «Solicitar
demo» y «Ver planes». Se quitaron la frase de debajo («Envía un correo a todos
tus contactos con un solo click») y la nota de «Escríbenos y te acompañamos».
- **«Solicitar demo» lleva a crear la cuenta** (`/signup` del panel), porque la
  demostración se pide desde la bienvenida, con el WhatsApp y el RUC o la
  cédula. Con sesión, `nav.js` le cambia la dirección por `/welcome`
  (`data-signed-href`), y al administrador se le esconde, como los botones de
  los planes.
- **«Ver planes» baja a `#planes`.** Los dos viven en `CTA_PRIMARY` y
  `CTA_SECONDARY` de `content.py`.
- **La pestaña dice solo «Sobreala»** (`HOME["meta_title"]`). La tarjeta para
  compartir no cambió: dibuja el título de la portada.

**«¿Sigues enviando correos masivos desde Gmail o Outlook?» son cuatro puntos
que se recorren**: a un lado la lista, con el que estás viendo marcado con un
ganchito y los otros tres con su número, y al otro su ilustración y su párrafo.
Fueron tres tarjetas sueltas en una rejilla, que se leían de un vistazo y no se
quedaban. La sección no lleva etiqueta de arriba ni entradilla: la pregunta lo
dice todo.

**Lo que abre cada punto son cuatro botones de radio**, como el carrusel de
Features, así que funciona entero sin JavaScript y las flechas del teclado lo
mueven solas. `assets/js/trouble.js` agrega una sola cosa: pasar al siguiente
solo, **cada quince segundos**, que es lo que tarda en leerse un punto entero
(unas 50 a 60 palabras); con seis no daba tiempo. Se para con el ratón encima o
el foco dentro, fuera de la pantalla y con la pestaña escondida, y no existe con
«reducir movimiento». **Si alguien lo cambia a mano, deja de pasar solo** para el
resto de la visita, a diferencia de Features, donde se pidió que volviera a
andar al quitar el ratón: lo detecta el evento `change` de los radios, que solo
salta cuando los cambia una persona y nunca cuando los marca el guion. **No hay
cuenta atrás**: hubo una barra bajo el punto abierto y se quitó.

**El estado del punto abierto viaja a sus hijos en variables** (`--card`,
`--mark-bg`, `--tick`…), de modo que una sola lista de cuatro selectores pinta a
la vez la tarjeta, el círculo, el número y el ganchito. Sin eso harían falta una
lista por declaración.

**Con el ratón encima, los otros tres se asoman**, para que se vea que también
se abren: la tarjeta sin su sombra y el círculo con el borde de acento. Es menos
que el abierto (sombra, círculo lleno y ganchito), y al abierto no le cambia
nada, porque sus reglas nombran su id y ganan. Va bajo `@media (hover: hover)`:
en el teléfono no hay hover y se quedaría pegado al tocar.

**Nada salta de alto.** Las cuatro ilustraciones comparten una celda de rejilla
y los cuatro párrafos otra, así que el bloque mide siempre lo que el más largo;
el que no toca se esconde con `visibility` y no con `display`, para que siga
contando en esa medida y quede fuera del lector de pantalla. El precio es un
hueco bajo el párrafo corto, y es a propósito. En el teléfono la ilustración va
arriba y la lista debajo.

**Las cuatro ilustraciones son SVG**, en
`src/partials/art-{manual,spam,privacy,tracking}.svg.j2`, que la plantilla
incluye por el nombre que trae cada punto en `art`, y **siguen el encuadre de
cuatro imágenes de referencia** (renders 3D que se dieron para esto): alguien
trabajando en su portátil con el reloj detrás, los sobres que van a la bandeja o
a la papelera, el sobre con candado entre seis personas, y el tablero de cifras.
Hubo una primera versión plana en los colores de la marca y se rehízo: no se
parecía.

**Las dos primeras están medidas sobre su referencia, no dibujadas a ojo**
(septiembre de 2026). A ojo salían con las proporciones aproximadas y la
perspectiva mezclada, y cada arreglo las dejaba más simples. Ahora las siluetas
de lo orgánico (la persona, la taza, las hojas, la silla) salen de separar cada
parte de la imagen por su color; las costuras del jersey, los mechones, los
dedos y la oreja son sus rayas finas; y lo geométrico (los dos portátiles, el
reloj, el tablero, la bandeja, la papelera, cada sobre) sale de esquinas leídas
sobre una rejilla puesta encima o de rectas ajustadas a sus bordes. **La prueba
es ponerlas al 50 % encima de la referencia**: coinciden, sin imagen doble. Las
herramientas que calcan y las imágenes no están en el repositorio; lo que queda
son los dos SVG, que se editan a mano como los otros dos.

**Las personas van sin rostro**, como un usuario por defecto. La de la primera
escena está en la pose de su referencia, de tres cuartos y tecleando, con la
oreja, la sombra de la barbilla en el cuello, el cuello redondo y las costuras
del jersey, el puño del que sale la mano y los dedos. Hubo una versión de frente
y detrás del portátil, de cuando la pose dibujada a ojo nunca dejó de verse
rara. **Los portátiles tienen la perspectiva de su referencia**: en la primera,
la tapa de espaldas con su canto claro y la base asomando bajo la mano; en la
segunda, de tres cuartos, con la base en perspectiva, su canto, el teclado y el
panel táctil. Los hubo de frente y simétricos, que era la manera de no mezclar
perspectivas a ojo; medidos, ya no hay mezcla.
**No llevan una sola palabra dentro** (las referencias traían «Inbox», «Spam»
y cifras) ni el puntero que tenía el tablero.

**Tienen su propia paleta**, `--art-*` en `brand/colors.css`, con los colores
medidos de esas referencias punto por punto: los azules vivos, el verde, el
morado, el ámbar, el rojo, el marino, las pieles y los pelos. No son los de la
marca, y es a propósito. **De noche son otra escena sin tocar el SVG**:
`colors-dark.css` repite solo lo que cambia. El fondo y la mesa son los de la
sección, así que no se ve recuadro y los dibujos flotan sobre la página; lo que
es tarjeta pasa a los grises de las tarjetas del sitio, y el papel baja un poco
para no deslumbrar. Hubo un azul noche y se quitó, porque teñía toda la escena.
Las personas no cambian de color. Lo que va dibujado encima del
papel (las agujas del reloj) usa `--art-navy` y no `--art-ink`, que de noche es
claro; el boli va en los azules.

Van **inline y no como archivo**, porque es lo único que puede leer las
variables de la página, y se pintan **con clases** (`.art-blue`, `.art-s-dash`…),
porque un atributo no puede leer una variable. El volumen son degradados de luz
y de sombra **en blanco y negro con transparencia**, que valen igual en los dos
temas; en las dos primeras, además, **bordes nítidos**: cada forma lleva su luz
arriba y su sombra abajo, recortadas con una máscara de ella misma movida unos
píxeles (`am-m-*`, `as-m-*`). Hubo luz y sombra calcadas de la referencia y
difuminadas, y dejaban manchas en la cara y las manos. La sombra suave de debajo
es un `feDropShadow` cuyo color sale de `--art-shadow` por una clase. **Las
siluetas largas se definen una vez y se reutilizan con `<use>`** (`am-p-*`,
`as-p-*`): el jersey salía trece veces entre relleno, luz, sombra, máscaras y
recortes, y la escena pesaba más del doble. **Los `id`
llevan el prefijo de su escena** (`am-`, `as-`, `ap-`, `at-`): las cuatro viven
en la misma página, y un `id` repetido hace que una use el degradado de otra (de
noche, el resplandor claro de la primera).

**Debajo de «¿Sigues enviando…?», «Haz crecer tu negocio»: cuatro casos, uno a
la vez, en una tarjeta grande** (octubre de 2026). Son Llega a más clientes,
Comunícate con tu equipo, Convoca a tus socios y Mantén informadas a las
familias, para comercios, empresas, cooperativas y colegios, que son el cliente
típico. **La florista va primera**, como se pidió.
- **Sigue la referencia que se dio**, el carrusel de casos de Mailchimp:
  - la foto ocupa unos 2/3 de la tarjeta, con el rótulo y el título encima, abajo
    a la izquierda, sobre un degradado oscuro que los deja leer en cualquier
    foto;
  - al lado va un panel con la descripción, y en el teléfono el panel queda
    debajo;
  - abajo hay un punto por caso, y el del abierto es más largo.
  Fue antes una rejilla de cuatro tarjetas pequeñas con el encabezado «Ejemplos /
  Lo que puedes enviar con Sobreala».
- **El panel lleva solo la descripción.** La referencia trae cifras, el nombre
  de un cliente y un enlace a su caso, y aquí serían inventados.
- **Funciona como «¿Sigues enviando…?»**: lo que abre cada caso son botones de
  radio, y los puntos son sus etiquetas, así que va sin JavaScript y con las
  flechas del teclado. `assets/js/stories.js` agrega el paso automático:
  - pasa cada 8 s;
  - se para con el ratón encima, con el foco dentro, fuera de la pantalla y con
    la pestaña escondida;
  - si alguien pulsa un punto, deja de pasar solo el resto de la visita;
  - con «reducir movimiento», no existe.
- **Las fotos son de Pexels, con su licencia**: uso comercial sin pedir permiso
  ni citar al autor. Lo que no deja es venderlas tal cual ni dar a entender que
  quien sale respalda algo, y por eso **nadie aparece como cliente ni dice
  nada**.
- Van recortadas a 16:10, en WebP de 1280 × 800, en `assets/img/usos/` (de 55 a
  71 KB cada una), con `loading="lazy"`. Salieron de los originales de 1600 ×
  1067 de Pexels. Las de antes, de 800 de ancho, quedaban cortas para la
  tarjeta grande. Los textos, el rótulo y el `alt` de cada una están en
  `HOME["uses"]` de `content.py`.
- De dónde sale cada una:

| Archivo | Autor | En Pexels |
|---|---|---|
| `equipo.webp` | Yan Krukau | https://www.pexels.com/photo/coworkers-in-front-of-a-laptop-7691727/ |
| `clientes.webp` | Amina Filkins | https://www.pexels.com/photo/happy-asian-florist-working-in-cozy-floral-shop-5414331/ |
| `socios.webp` | Pavel Danilyuk | https://www.pexels.com/photo/a-man-speaking-in-front-of-the-people-sitting-inside-the-conference-room-8761330/ |
| `familias.webp` | Tiger Lily | https://www.pexels.com/photo/a-mother-and-her-daughter-looking-at-a-laptop-8260185/ |

**En «Cómo funciona», debajo de Features, va una tira de plantillas que corre
sola** (septiembre de 2026). Lleva el título «¿Aún no sabes por dónde
empezar?», las plantillas de `SAMPLES` y el botón «Ver tutorial», que baja a
los tutoriales, justo debajo (ver «Los tutoriales», más abajo).
- **Es solo CSS**, sin guion:
  - la lista va tres veces seguidas y cada una avanza su propio ancho, así que
    el salto no se ve;
  - **tres y no dos** porque con cuatro plantillas una lista mide 1,280 px:
    con dos, en una pantalla ancha se veía el final de la segunda, y con tres
    no se ve hasta los 2,560 px. Si las plantillas cambian, cambia esa cuenta;
  - la vuelta dura 18 s, unos 70 px por segundo, la velocidad de cuando eran
    doce;
  - las copias van escondidas del lector de pantalla y del tabulador.
- **Se para con el ratón encima o con el foco dentro**, para poder pulsar una.
- **Con «reducir movimiento» queda quieta** y se recorre de lado.
- **No agranda nada al pasar el ratón**, por lo mismo que Features.
- **Se tomó de un componente de React con Tailwind**, que el sitio no usa: el
  efecto se hizo con el CSS de siempre.
- **Cada tarjeta es la plantilla misma**, con su nombre debajo: 300 px de
  ancho (200 en el teléfono) y en 3:4, que deja leer los titulares y ver las
  fotos. La miniatura es **GENERADA**: `landing/samples.py` abre el correo
  armado que trae el ZIP en un Chrome sin cabeza, a 600 de ancho, y guarda la
  parte de arriba en `assets/img/samples/<slug>.webp`; lo que pasa de 800 se
  corta. **Hay que volver a correrlo cuando cambie un ZIP**, y
  `build_site.py` no construye si a una le falta la suya.
- **Pulsarla abre su lienzo en el panel** (ver `designs`).

**Los tutoriales de «Cómo funciona» son capturas del panel que se recorren
pulsando** (octubre de 2026), como Arcade: Contactos, Plantillas, Enviar correos,
Estadísticas y Configuración, en pestañas. Sustituyeron a los cuatro pasos. Cada
paso es la pantalla de verdad, en el tema puesto, con un anillo que late sobre
lo que hay que pulsar y un globo que dice qué hacer y para qué; pulsar el anillo
(o Enter con él enfocado) enseña lo que sale después de ese clic. Pulsar fuera
no avanza: el anillo late otra vez.
- **Por qué capturas y no una réplica en HTML:** una réplica se desfasa en
  silencio el día que cambia el panel; las capturas se rehacen con un comando.
- **Las hace `landing/tutorials.py`**, que reutiliza la demostración de
  `shots.py` y le agrega lo suyo (plan Empresa, sin campañas programadas, el
  último envío con contactos de verdad). Recorre el panel en Chrome a 1280 × 800
  haciendo cada clic de verdad, y escribe las capturas en
  `assets/img/tutorial/{light,dark}/` y dónde cae cada anillo, en porcentajes,
  en `landing/tutorials.json`. **Las dos cosas son GENERADAS. Hay que volver a
  correrlo cuando cambie una pantalla que sale en un recorrido**; `--check`
  avisa si falta alguna. Le pone a la demostración credenciales de PayPal de
  mentira para que Facturación diga «Disponible».
- **Los textos viven en `content.TUTORIALS`**, por recorrido y por paso, y los
  pasos en `tutorials.TOURS`. `build_site.py` se niega a construir si a un paso
  le falta su texto, y `backend/tests/test_tutorials.py` lo comprueba en los dos
  sentidos.
- **Sin JavaScript se lee entero**: cada recorrido con todos sus pasos, uno
  debajo del otro, con su anillo y su globo. `assets/js/tutorial.js` lo vuelve
  reproductor: un paso a la vez, Atrás y Empezar de nuevo, la tarjeta de «Listo»
  al final, y la pestaña en la dirección (`#plantillas`), así se puede mandar el
  enlace de un tutorial.
- **El globo va junto al anillo** de 900 px en adelante, del lado que tenga
  sitio, y la página se mueve lo justo para que los dos queden bajo la barra
  fija. **En el teléfono va debajo, y la captura se agranda al doble** y se
  corre hasta dejar el anillo en medio: entera no se leía nada.
- **Con «reducir movimiento»** no late ni se funde.

**«Features» son cinco dibujos sencillos** (octubre de 2026), en un carrusel
que aprieta: el abierto ocupa su sitio y los otros cuatro quedan en listones.
Debajo, el texto del que esté abierto. La sección no lleva etiqueta de arriba,
a diferencia de las demás: el titular ya es la etiqueta.

**Cada dibujo cuenta una sola cosa:**

| `art` | Lo que se ve |
|---|---|
| `contacts` | Dos filas con la misma dirección, cada una con su etiqueta, que se juntan en una: el contador dice «1 / 1000» |
| `editor` | Una hoja con un título elegido (con sus tiradores), una foto y un botón |
| `schedule` | «Enviar ahora» y «Programar», con el segundo marcado y su fecha |
| `results` | Tres cifras grandes (entregados, aperturas y clics) y «CSV · PDF» |
| `unsubscribe` | El enlace al pie de un correo y el «Listo, ya no recibirás estos correos» |

- **Fueron cinco capturas del panel**, en un juego por tema que hacía
  `shots.py`, con una ventana para verlas en grande. Enseñaban demasiado de
  golpe, y se quitaron con su ventana: los dibujos se leen enteros en su sitio.
  `shots.py` se quedó con lo que comparten los tutoriales y las miniaturas: la
  cuenta de demostración, el panel y Chrome.
- **Son SVG dentro de la página**, en `src/partials/feature-*.svg.j2`, que la
  plantilla incluye por el `art` de cada uno. Se pintan con las clases `.art-*`
  de las ilustraciones de arriba, así que el mismo dibujo sirve de día y de
  noche. Los `id` llevan el prefijo de su dibujo (`fc-`, `fe-`, `fs-`, `fr-`,
  `fu-`), por lo mismo que los de las ilustraciones.
- **Las palabras que llevan dentro viven en `content.py`** (`words`), como todo
  el español del sitio. `alt` es lo que oye un lector de pantalla
  (`aria-label` del SVG): el listón es la etiqueta de su botón de radio, y sin
  eso no tendría nombre.
- **Cerrado se ve su centro** (`preserveAspectRatio="xMidYMid slice"`), que es
  donde cada uno tiene lo que cuenta.

**El abierto mide lo mismo que el dibujo** (16:9).
- **Cómo:** su ancho es el alto de la tira (su ancho entre 3.2) por la
  proporción del dibujo, y los cerrados se reparten lo que sobra.
- **Qué se consigue:** el abierto se ve entero, y todos se dibujan a la misma
  escala, la del alto, así que abrir uno solo destapa más de él.
- **Por qué:** cuando eran capturas crecía a 7 contra 1 y quedaba más ancho que
  la imagen. `object-fit: cover` le cortaba arriba y abajo y la agrandaba al
  terminar de abrirse, y se veía como un pequeño zoom.
- **El ratón sobre un cerrado** lo agranda a costa de los otros cerrados, nunca
  del abierto.
- **Si cambia la proporción de los dibujos o la de la tira**, cambia esa cuenta,
  que está en `landing/src/site.css`.

**Los listones no llevan rótulo.** Lo llevaron, de lado y con un velo oscuro
debajo para que se leyeran encima de la captura; el velo tapaba justo lo que la
sección viene a enseñar. Sin rótulo no hace falta ninguno de los dos.

**Lo que abre cada dibujo son cinco botones de radio**, no un guion. Por eso la
sección funciona entera sin JavaScript y las flechas del teclado la mueven
solas, que es lo que se consigue gratis con un grupo de radios.
`assets/js/carousel.js` agrega dos cosas y nada más, y ninguna existe sin él
(como el interruptor de Planes): los botones de anterior y siguiente, y el paso
automático cada cuatro segundos. Ese paso **se detiene con el ratón encima o
con el foco dentro y vuelve a andar al quitarlo**, no corre fuera de la
pantalla ni con la pestaña escondida, y no existe con «reducir movimiento»
puesto. **Elegir uno a mano no lo apaga**: solo reinicia la cuenta, para que el
que se acaba de pulsar no se cambie medio segundo después. Lo deciden tres
interruptores y un solo `sync()`; antes cada uno llamaba a `play()` por su
cuenta y el ratón podía arrancarlo con la sección fuera de la vista.

**En el teléfono no hay apretujón**: los dos contenedores se vuelven
transparentes (`display: contents`) y cada dibujo queda encima de su texto, con
los cinco a la vista. El apretujón necesita ancho para significar algo, y ahí
no lo hay.

Las reglas del carrusel nombran los cinco por su id (`#tour-1` … `#tour-5`), que
es lo que cuesta hacer esto sin una línea de JavaScript: si algún día son otros,
esas listas de `landing/src/site.css` crecen con ellos.

**Debajo del carrusel, la lista «En todos los planes, sin excepción»** (octubre
de 2026): rebotes y quejas fuera, sin sorpresas al llegar al límite,
acompañamiento en la primera campaña y sin permanencia mínima.
- **Aquí se juntaron tres bloques**: Features, «Reglas que funcionan solas», que
  cerraba Cómo funciona, y la lista «En todos los planes» del final de Planes.
  Lo que repetían lo cuentan ahora los textos de los cinco dibujos, y lo demás
  va en esta lista. La tabla comparativa de Planes se quedó.
- Usa la caja de la lista de Planes (`.included`, en el gris casi negro de
  `--color-deep`), de dos en dos en lo ancho.
- **De paso salieron dos frases que prometían algo que no existe**: «envíate una
  prueba», porque ese envío de prueba no está hecho, y el aviso al 80 % de la
  cuota, por lo mismo.

**La sección sigue al tema, como el resto de la página.** Hubo una banda que se
invertía, oscura de día y blanca de noche, porque las capturas de entonces eran
siempre del panel en oscuro; con ella se fueron las variables `--color-flip*` y
las clases `.section--flip` y `.section--deep`. **Los fondos alternan de arriba
abajo**: azul (la portada) · gris («¿Sigues enviando…?») · blanco (los usos) ·
gris (las tarjetas de Planes) · blanco (la tabla) · gris (el glosario) · blanco
(Features) · gris (la tira) · blanco (los tutoriales) · gris (el envío) ·
blanco (Nosotros) · gris (las preguntas) · azul (el pie). En oscuro, los mismos
escalones.

**El pie es un solo azul** (octubre de 2026). Abajo, dentro del mismo azul, va
el «© Sobreala» en pequeño, con una raya fina encima (`--color-footer-edge`).
- **Se quitaron los logos de pago** (Yappy, PayPal, Visa y Mastercard), que iban
  en una franja del color de la página debajo del azul. De noche el final de la
  página se leía negro, azul y negro otra vez, y de los cuatro medios hoy solo
  cobra PayPal: prometían de más. Los medios se ven al pagar, en el panel.
- **`build_site.py` ya no los copia**: salieron `PAYMENT_LOGOS`,
  `PAYMENT_LABELS`, `icon_size()` y `crop_logos()`, y la carpeta
  `assets/img/payments/`. El kit sigue en `brand/payments/`, y el panel tiene su
  propia copia para el pago (`backend/build_assets.py`, recortada con
  `brand/payments/viewbox.json`), que no cambió.
- **«¿Cómo se paga?» ya no dice «los que ves al pie»**: dice que al contratar
  se elige con qué pagar.
