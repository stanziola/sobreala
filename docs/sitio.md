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
| `#inicio` | La portada y «¿Sigues enviando correos masivos…?» | `src/pages/index.html.j2` |
| `#planes` | Interruptor y tarjetas, la tabla, el glosario e «incluido» | `src/sections/planes.html.j2` |
| `#como-funciona` | Features, la tira de plantillas, los tutoriales, el envío y las reglas | `src/sections/como-funciona.html.j2` |
| `#nosotros` | Quiénes somos | `src/sections/nosotros.html.j2` |
| `#contacto` | WhatsApp, correo e Instagram, quién contesta | `src/sections/contacto.html.j2` |
| `#preguntas` | Una sola lista: las generales y las de facturación | `src/partials/faq.html.j2` |

- **Cada sección conserva sus textos en su diccionario de `content.py`**
  (`PRICING`, `HOW`, `ABOUT`, `CONTACT_PAGE`), y `index.html.j2` la incluye con
  `{% with page = … %}`, así que dentro nada cambió de nombre. El `hero` de
  cada una es ahora la cabeza de su sección, con su `h2`: hay un solo `h1`.
- **Los botones de la barra solo desplazan** (`/#planes`, con la `/` para que
  sirvan también desde las legales). La barra fija no tapa el título:
  `scroll-margin-top` en `.page-part` y en las secciones con `id`. **El botón de
  la sección que se está leyendo se marca** con un `IntersectionObserver` en
  `nav.js`, mirando una franja justo debajo de la barra; en Contacto y en las
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

**«¿Sigues enviando correos masivos desde Gmail o Outlook?» son cuatro puntos
que se recorren**: a un lado la lista, con el que estás viendo marcado con un
ganchito y los otros tres con su número, y al otro su ilustración y su párrafo.
Fueron tres tarjetas sueltas en una rejilla, que se leían de un vistazo y no se
quedaban. La sección no lleva etiqueta de arriba ni entradilla: la pregunta lo
dice todo.

**Lo que abre cada punto son cuatro botones de radio**, como el carrusel de
capturas, así que funciona entero sin JavaScript y las flechas del teclado lo
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

**«Features» son cinco capturas del panel de verdad**, en un carrusel que
aprieta: la abierta ocupa su sitio y las otras cuatro quedan en listones.
Debajo, el texto de la que esté abierta. La sección no lleva etiqueta de arriba,
a diferencia de las demás: el titular ya es la etiqueta.

**La abierta mide lo mismo que la captura** (1400 × 788).
- **Cómo:** su ancho es el alto de la tira (su ancho entre 3.2) por la
  proporción de la imagen, y las cerradas se reparten lo que sobra.
- **Qué se consigue:** la abierta se ve entera, y todas las capturas se dibujan
  a la misma escala, la del alto, así que abrir una solo destapa más de ella.
- **Por qué cambió:** antes crecía a 7 contra 1 y quedaba más ancha que la
  captura. `object-fit: cover` le cortaba arriba y abajo y la agrandaba al
  terminar de abrirse, y se veía como un pequeño zoom.
- **El ratón sobre una cerrada** la agranda a costa de las otras cerradas,
  nunca de la abierta.
- **Si cambia el tamaño de las capturas o la proporción de la tira**, cambia esa
  cuenta, que está en `landing/src/site.css`.

**Hay dos juegos de capturas, uno por tema**, en
`landing/assets/img/panel/light/` y `.../dark/`, con los mismos cinco nombres en
cada carpeta. Las hace `landing/shots.py`: siembra una cuenta de demostración en
una base aparte, arranca el panel contra ella, lo abre en Chrome sin cabeza y
recorta cada pantalla a 16:9. **Cada dirección se abre una sola vez y se
fotografía en los dos temas**, poniéndole `data-theme` entre foto y foto, que es
lo mismo que hace el guion de la cabecera del panel: así los dos juegos salen
idénticos salvo el color y la vuelta no tarda el doble. **Hay que volver a
correrlo cuando cambie una de esas cinco pantallas**, o la portada enseñará algo
que ya no existe.

Los datos de la demostración son neutros a propósito: «Tu empresa», nombres de
pila con `@ejemplo.com` y asuntos corrientes. Ni una cooperativa, ni un colegio,
ni nada que se lea como un cliente de verdad.

**Los listones no llevan rótulo.** Lo llevaron, de lado y con un velo oscuro
debajo para que se leyeran encima de la captura; el velo tapaba justo lo que la
sección viene a enseñar. Sin rótulo no hace falta ninguno de los dos.

**La sección sigue al tema, como el resto de la página.** Hubo una banda que se
invertía —oscura de día y blanca de noche— y estaba ahí por una sola razón: las
capturas eran siempre del panel en oscuro, así que necesitaban un fondo oscuro
al lado. Con un juego por tema esa razón desapareció, y con ella las cuatro
variables `--color-flip*` y las clases `.section--flip` y `.section--deep`, que
era la otra banda fija de la portada («Cómo funciona»). La portada queda azul ·
gris · blanco · gris · blanco, y los mismos escalones al revés en oscuro.

**Cada listón trae sus dos capturas y el CSS esconde la que no toca** (un par de
reglas con `:root[data-theme="dark"]`). El claro es el de por omisión porque
**sin JavaScript no hay atributo ninguno**: la elección la resuelve el guion de
la cabecera antes de pintar, leyendo la galleta, el `localStorage` y la
preferencia del sistema. **Las diez van `loading="lazy"`, también la primera**:
una escondida con `lazy` no se baja nunca, así que el juego que no se ve no
cuesta bytes, y una primera ansiosa habría arrastrado a su gemela. Está medido:
la portada pide cinco capturas, no diez.

**Lo que abre cada captura son cinco botones de radio**, no un guion. Por eso la
sección funciona entera sin JavaScript y las flechas del teclado la mueven
solas, que es lo que se consigue gratis con un grupo de radios.
`assets/js/carousel.js` agrega tres cosas y nada más, y ninguna existe sin él
(como el interruptor de Planes): los botones de anterior y siguiente, el paso
automático cada cuatro segundos y la ventana de ver una captura en grande. Ese
paso **se detiene con el ratón encima o con el foco dentro y vuelve a andar al
quitarlo**, no corre fuera de la pantalla, ni con la pestaña escondida, ni con
una captura abierta en grande, y no existe con «reducir movimiento» puesto.
**Elegir una a mano no lo apaga**: solo reinicia la cuenta, para que la que se
acaba de pulsar no se cambie medio segundo después. Lo deciden cuatro
interruptores y un solo `sync()`; antes cada uno llamaba a `play()` por su
cuenta y el ratón podía arrancarlo con la sección fuera de la vista.

**Pulsar la captura abierta la enseña en grande**, en un `<dialog>` que escribe
el guion. Una cerrada de la tira solo se abre, que es la navegación de siempre;
apilado (el teléfono) no hay abiertas ni cerradas, así que cualquiera se
agranda, y eso lo decide preguntarle al CSS si la tira está en `display:
contents` en vez de repetir en el guion el ancho del corte. La imagen se copia
del `<img>` **que se está viendo**, así que sale en el tema puesto y ya está en
la caché. Es un `<dialog>` y no un invento propio porque de ahí salen gratis el
`Escape`, el foco atrapado dentro, el fondo oscurecido y el foco de vuelta al
botón de radio de esa captura. **La X vive en el relleno del diálogo, o sea
fuera de la captura**, y ese relleno nunca baja de lo que ella mide; a los lados
se encoge en el teléfono, donde el sitio es para la captura. Pulsar el borde de
alrededor también cierra. En el teléfono el zoom no agranda gran cosa (una
captura apaisada ya ocupa el ancho): lo que da es la captura sola, sin la página
alrededor.

**En el teléfono no hay apretujón**: los dos contenedores se vuelven
transparentes (`display: contents`) y cada captura queda encima de su texto, con
las cinco a la vista. El apretujón necesita ancho para significar algo, y ahí no
lo hay.

Las reglas del carrusel nombran las cinco por su id (`#tour-1` … `#tour-5`), que
es lo que cuesta hacer esto sin una línea de JavaScript: si algún día son otras,
esas listas de `landing/src/site.css` crecen con ellas.

**Los logos de pago van a color, en una franja del color de la página**: Yappy,
PayPal, Visa y Mastercard (septiembre de 2026). La fila de abajo del pie, la de
los pagos, va de lado a lado, fuera del `shell`, y es **blanca de día y casi
negra de noche** (`--color-page`, con la letra en `--color-ink-soft`); el resto
del pie sigue azul, y una línea fina las separa (`--color-footer-edge`). Los
logos fueron un tiempo directo sobre el azul, donde PayPal, Visa y Yappy, que
son azules, apenas se leían (el PayPal oscuro daba 2:1); sobre el
blanco se leen todos, y de noche, sobre el negro, esos tres quedan con poco
contraste, y así se decidió. Antes de eso iban los dos que había, en blanco.
Qué variante del kit usa el sitio lo dice
`PAYMENT_LOGOS` en `landing/build_site.py`, con su nombre bien escrito para el
texto alternativo en `PAYMENT_LABELS`; **ningún logo lleva fondo propio**. **Visa y Mastercard
traen su margen de respeto dentro del SVG**, y a 28 px de alto el dibujo quedaba
diminuto: las copias que sirven el sitio y el panel se recortan con el viewBox
de `brand/payments/viewbox.json` (el kit no se toca). Las medidas de cada `<img>` salen del archivo generado
(`icon_size()`): escritas a ojo, y cuadradas para logos apaisados, el pie
saltaba mientras cargaba.
