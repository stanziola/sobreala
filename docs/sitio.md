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
| `#planes` | Interruptor y tarjetas, y la tabla | `src/sections/planes.html.j2` |
| `#como-funciona` | Funciones (Features), los tutoriales, la tira de plantillas y el dominio personalizado | `src/sections/como-funciona.html.j2` |
| `#preguntas` | Seis preguntas frecuentes, sin botón en la barra | `src/partials/faq.html.j2` |

**Contacto es el pie** (`id="contacto"` en `base.html.j2`): WhatsApp, correo e
Instagram. Hubo una sección «Hablemos de tu lista» antes de las preguntas, y se
quitó en octubre de 2026 porque repetía el pie; `/contact/` y `/#contacto`
aterrizan ahí. Con ella se fue el `id` repetido que había entre las dos.

**En octubre de 2026 salieron dos secciones más:**
- **«Qué significa cada fila»**, el glosario de debajo de la tabla de Planes;
- **«Nosotros»**, con su columna «Empresa» del pie, que solo lo enlazaba.

**Las preguntas frecuentes se quitaron y volvieron ese mismo mes, más cortas:**
seis en vez de once (`HOME["faq"]`), entre Cómo funciona y el pie, cada una en
un `details` que se abre sin JavaScript y con la primera abierta. Cada respuesta
se revisó contra `docs/`: las de antes decían que el dominio «lo configuramos
contigo», cuando el cliente lo conecta solo, y que se podía bajar de plan en
cualquier momento, cuando con un plan vigente solo se mejora. Son: cómo empiezo,
si necesito dominio, cómo se paga, los correos que no uso, cambiar de plan y la
permanencia.

`/about/` sigue respondiendo y lleva al inicio.

- **Cada sección conserva sus textos en su diccionario de `content.py`**
  (`PRICING`, `HOW`), y `index.html.j2` la incluye con
  `{% with page = … %}`, así que dentro nada cambió de nombre. `CONTACT_PAGE`
  y `ABOUT` solo guardan el título de su página de paso. El `hero` de
  cada una es ahora la cabeza de su sección, con su `h2`: hay un solo `h1`.
- **La barra lleva Inicio, Planes y Cómo funciona.**
- **Las cabezas llevan solo su título** (octubre de 2026): «Planes», sin la
  etiqueta «Precios» ni la entradilla; «Funciones», que reemplazó a «Cómo
  funciona / De tu base de datos…» y a «Features» con las suyas; y «¿Aún no
  sabes por dónde empezar?», sin la etiqueta «Cómo funciona». El botón de la
  barra sigue diciendo «Cómo funciona». `HOW["hero"]["title"]` («Cómo
  funciona») y `PRICING["hero"]["title"]` solo siguen ahí para el enlace de su
  página de paso.
- **Los botones de la barra solo desplazan** (`/#planes`, con la `/` para que
  sirvan también desde las legales). La barra fija no tapa el título:
  `scroll-margin-top` en `.page-part` y en las secciones con `id`. **El botón de
  la sección que se está leyendo se marca** con un `IntersectionObserver` en
  `nav.js`, mirando una franja justo debajo de la barra.
- **Las direcciones de antes siguen respondiendo**: `/pricing/`,
  `/how-it-works/`, `/about/` y `/contact/` son páginas de paso
  (`src/redirect.html.j2`, tabla `REDIRECTS` de `build_site.py`) con
  `noindex`, que mandan a su ancla (`/about/`, al inicio) y conservan el `#`
  que traigan, así
  `/how-it-works/#templates` sigue abriendo su tutorial. El panel ya enlaza
  directo a `/#planes`. `sitemap.xml` y las tarjetas para compartir son solo de
  `/` y las legales.
- **La página carga cinco guiones**: `trouble.js`, `stories.js`,
  `carousel.js`, `plans.js` y `tutorial.js`. Las pestañas de los tutoriales
  usan `contacts`, `templates`, `campaigns`, `stats` y `settings`, que no
  chocan con las anclas de las secciones.

### Botones y enlaces: menos azul (octubre de 2026)

Como en el panel: **el botón principal es gris casi negro** con la letra blanca
(`--color-action`; de noche, gris claro con la letra oscura), **el de contorno
es gris**, y lo elegido (la pestaña de un tutorial, mensual o anual en Planes)
también. **Los enlaces** van del color del texto, en seminegrita, y se subrayan
al pasar el mouse. **El azul de la marca no cambia**: la cabecera, la portada y
el pie siguen azules, y los botones de la portada siguen como estaban, porque
sobre ese azul el gris no se lee.

**El menú de la cuenta tiene una fila, Dashboard** (`/dashboard`), donde antes
había cuatro (Estadísticas, Enviar correos, Contactos y Plantillas), igual que
el del panel.

**Los botones que llevan a la cuenta dicen lo que toca** (octubre de 2026): el
principal de la portada y el «Crear mi cuenta» del final de los tutoriales.
El sitio no sabe quién mira; lo sabe por la migaja del panel (`sa_in`), que
desde ahora lleva también **en qué punto está la empresa** (`company_state()`
en `backend/app.py`): `1:<plan>:<ciclo>:<estado>`. Los textos viven en
`CTA_STATES` de `content.py` y los pinta `nav.js` (`data-cta`):

| Estado | Portada | Final del tutorial |
|---|---|---|
| Sin sesión | Solicitar demo (a registrarse) · Ver planes | Crear mi cuenta |
| `closed`, cerrada | Solicitar demo (a `/welcome`) · Ver planes | Solicitar demo |
| `requested`, demostración pedida | Ver mi solicitud · Ver planes | Ver mi solicitud |
| `demo`, abierta sin plan | solo Ver planes, de principal | Ver planes |
| `paid`, con plan | Ir al Dashboard · Ver planes | Ir al Dashboard |

Una migaja de antes («1» a secas) se lee como cerrada, que es lo que se hacía.
Como el plan, cualquier script de `sobreala.com` puede leer el estado.

**El logo de la empresa, en «Mi cuenta»** (octubre de 2026), como en la barra
del panel: la migaja lleva al final el nombre de su imagen
(`1:<plan>:<ciclo>:<estado>:<logo>`, solo si tiene) y `nav.js` cambia el ícono
de persona por él, pedido a `https://app.sobreala.com/img/<nombre>`. Solo si el
nombre tiene la forma de los que genera el panel. Ese nombre ya es público: es
la dirección de una imagen.

**Con logo, en la barra va la foto con su flecha** (octubre de 2026), igual que
en el panel: `nav.js` le pone `usermenu__button--avatar` al botón y `site.css`,
desde 960 px, deja la foto y la flecha en la caja de siempre y «Mi cuenta»
(`usermenu__me-label`) para el lector de pantalla. El logo llena su círculo de
32 px. Se probó primero solo el círculo, sin caja ni flecha, y no se leía como
un desplegable. **En el teléfono**, donde la cuenta es una fila más dentro del
menú de tres líneas, se queda «Mi cuenta» al lado del círculo: una foto suelta
en una fila de texto no se entiende. **Desde 960 px la cuenta va pegada al borde
derecho**, a la misma distancia que el ala del izquierdo, como en el panel: los
enlaces quedan en medio de lo que sobra, y el hueco de las tres líneas, que
solo viven en el teléfono, se quitó. Con «Ingresar» y «Registrarse» pasa lo
mismo. El
menú del sitio no lleva la cabecera con el nombre que tiene el del panel: la
migaja no lleva el nombre de la empresa, y antes el botón decía «Mi cuenta» y
tampoco lo enseñaba.

## La portada

### Se va descubriendo al bajar (octubre de 2026)

`assets/js/reveal.js` y el final de `src/site.css`. Al entrar en pantalla, los
títulos (`.hero__title` y cada `.section__title`) salen **palabra por
palabra**; las tarjetas (`.plan`, `.faq__item`,
`.story__side`) **suben** con un retraso entre ellas; y los precios de los
planes **cuentan hasta su número** (si `plans.js` los cambia a mitad, se deja de
contar). Hubo además un trazo que subrayaba la frase destacada del inicio, y
se quitó el mismo mes. **Al terminar de subir, cada tarjeta suelta sus clases
de entrada** (`reveal-rise` e `is-revealed`): con ellas puestas, su
`transform: none` le ganaba al hover y las tarjetas de los planes dejaron de
levantarse al pasar el cursor (arreglado el 16 de octubre de 2026).

**Nada queda escondido sin el script**: el CSS solo esconde lo que va a
aparecer cuando `<html>` lleva `js-reveal`, y esa clase la pone el script justo
antes de empezar a mirar. Con «reducir movimiento», o sin IntersectionObserver,
no hace nada; al imprimir, todo a la vista. Los textos no cambian
(`content.py`): el script solo envuelve sus palabras.

**Arriba van el título y dos botones, nada más** (octubre de 2026): «Solicitar
demo» y «Ver planes». Se quitaron la frase de debajo («Envía un correo a todos
tus contactos con un solo click») y la nota de «Escríbenos y te acompañamos».
- **«Solicitar demo» lleva a crear la cuenta** (`/signup` del panel), porque la
  demostración se pide desde la bienvenida, contando a qué se dedica el negocio
  y para qué usará Sobreala. Con sesión, `nav.js` le cambia la dirección por `/welcome`
  (`data-signed-href`), y al administrador se le esconde, como los botones de
  los planes.
- **«Ver planes» baja a `#planes`.** Los dos viven en `CTA_PRIMARY` y
  `CTA_SECONDARY` de `content.py`.
- **La pestaña dice solo «Sobreala»** (`HOME["meta_title"]`). La tarjeta para
  compartir no cambió: dibuja el título de la portada. Las demás páginas
  separan su nombre de la marca con una barra, «Términos y condiciones |
  Sobreala» (octubre de 2026; antes con «·»), igual que el panel
  (`base.html`).

**«¿Sigues enviando correos masivos desde Gmail o Outlook?» son cuatro puntos
que se recorren**: a un lado la lista, con el que estás viendo marcado con un
ganchito y los otros tres con el círculo vacío, y al otro su ilustración y su
párrafo. Cada círculo llevaba su número, y se quitó en octubre de 2026.
Fueron tres tarjetas sueltas en una rejilla, que se leían de un vistazo y no se
quedaban. La sección no lleva etiqueta de arriba ni entradilla: la pregunta lo
dice todo.

**Lo que abre cada punto son cuatro botones de radio**, como el carrusel de
Features, así que funciona entero sin JavaScript y las flechas del teclado lo
mueven solas. `assets/js/trouble.js` agrega una sola cosa: pasar al siguiente
solo, **cada quince segundos**, que es lo que tarda en leerse un punto entero
(unas 50 a 60 palabras); con seis no daba tiempo. Se para fuera de la pantalla y
con la pestaña escondida, y no existe con «reducir movimiento». **Si alguien lo
cambia a mano, espera tres segundos** en el punto elegido, con la barra vacía, y
sigue solo desde ahí; otro cambio antes de tiempo vuelve a empezar la espera. Lo
detecta el evento `change` de los radios, que solo salta cuando los cambia una
persona y nunca cuando los marca el guion.
- **Hasta octubre de 2026 un cambio a mano lo apagaba** para el resto de la
  visita, y el ratón encima o el foco dentro lo pausaban. Se quitaron las dos
  cosas: al pulsar, el ratón se queda encima, y no volvía a andar nunca.

**Una barrita azul al pie de la tarjeta abierta se llena en esos quince
segundos** (octubre de 2026) y, llena, pasa al siguiente.
- **La barra es el reloj.** Es una animación de CSS (`--trouble-every`, en
  `site.css`), y `trouble.js` no cuenta el tiempo: espera su `animationend` y
  abre el siguiente, así que la barra y el cambio no se pueden separar. Pausar
  es pausar la animación (`animation-play-state`), y al seguir arranca donde
  iba.
- **El guion pone dos clases en el bloque:** `is-playing`, con el paso
  automático encendido, e `is-paused`, cuando se detiene un momento.
- **Tras un cambio a mano**, `trouble.js` la deja en pausa tres segundos: el
  punto nuevo estrena su animación, así que se ve vacía.
- **Solo se dibuja mientras el paso automático corre:** sin guion o con
  «reducir movimiento» no lleva a ninguna parte.
- **Hubo otra en septiembre de 2026 y se quitó.** Corría aparte de un
  `setInterval` del guion: con el ratón encima el cambio se pausaba y ella
  seguía llenándose.
- La tarjeta deja abajo siempre el mismo sitio, para no dar un salto cuando la
  barra se va.

**El estado del punto abierto viaja a sus hijos en variables** (`--card`,
`--mark-bg`, `--tick`, `--bar`…), de modo que una sola lista de cuatro
selectores pinta a la vez la tarjeta, el círculo, el ganchito y la barra. Sin
eso harían falta una lista por declaración.

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
Comunícate con tu equipo, Convoca a tus socios y Mantén a todos informados, para
comercios, empresas, cooperativas y colegios, que son el cliente típico. **La
florista va primera**, como se pidió. El texto de los socios perdió «cada uno
con su nombre y su monto», que contaba una función donde no tocaba, y el de los
colegios dejó «el correo de cada familia» por «toda la comunidad educativa».
- **Sigue la referencia que se dio**, el carrusel de casos de Mailchimp:
  - la foto ocupa unos 2/3 de la tarjeta, con el rótulo y el título encima, abajo
    a la izquierda, sobre un degradado oscuro que los deja leer en cualquier
    foto;
  - al lado va un panel con la descripción, y en el teléfono el panel queda
    debajo;
  - abajo hay una barra por caso, y la del abierto es más larga.
  Fue antes una rejilla de cuatro tarjetas pequeñas con el encabezado «Ejemplos /
  Lo que puedes enviar con Sobreala».
- **El panel lleva solo la descripción.** La referencia trae cifras, el nombre
  de un cliente y un enlace a su caso, y aquí serían inventados.
- **Funciona como «¿Sigues enviando…?»**: lo que abre cada caso son botones de
  radio, y las barras son sus etiquetas, así que va sin JavaScript y con las
  flechas del teclado. `assets/js/stories.js` agrega las flechas y el paso
  automático:
  - **la barra del abierto es el reloj**, como en «¿Sigues enviando…?»: el azul
    la llena en 8 s (`--stories-every`) y, llena, pasa al siguiente;
  - se para fuera de la pantalla y con la pestaña escondida, y la barra se
    queda donde iba;
  - **si alguien pulsa una barra o una flecha, espera un segundo** con la barra
    del caso nuevo gris, y después el azul empieza a llenarla otra vez; otro
    cambio antes de tiempo vuelve a empezar la espera;
  - con «reducir movimiento», no existe.
  Hasta octubre de 2026 un cambio a mano lo apagaba, con la barra azul y llena,
  y el ratón encima o el foco dentro lo pausaban. Se quitaron, como en
  «¿Sigues enviando…?».
- **La barra del abierto mide 64 px**, para que se vea llenarse (eran 46).
  Mientras corre es gris y la llena el azul; parada (sin guion o con «reducir
  movimiento») queda azul y llena. Antes era gris oscuro.
- **Las flechas van a los lados de las barras** (octubre de 2026), todo
  centrado bajo la tarjeta y en todos los anchos. Son círculos de 40 px como los
  de Features, solo las dibuja el guion (`is-ready`) y dan la vuelta al final.
  Lo que dicen a un lector de pantalla está en `HOME["uses"]` (`back` y
  `next`).
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

**En «Cómo funciona», debajo de los tutoriales, va una tira de plantillas que
corre sola** (septiembre de 2026). Lleva el título «¿Aún no sabes por dónde
empezar?» y las plantillas de `SAMPLES`. Iba entre Features y los tutoriales,
con un botón «Ver tutorial» que bajaba a ellos. En octubre de 2026 los
tutoriales subieron por encima de la tira y el botón se quitó: llevaba hacia
atrás.
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
- **Son dos tiras desde octubre de 2026**, por el campo `group` de `SAMPLES`:
  - **las promociones** (`promo`), trece rubros, debajo del título de siempre.
    Su vuelta dura 58 s (`.samples--long`), para que corra a la misma
    velocidad que la de cuatro;
  - **«Para tu sistema»** (`api`): factura, bienvenida, confirmación de pedido
    y estado de cuenta, que manda el sistema de un comercio por la API. Corre
    en sentido contrario (`.samples--reverse`), para que no parezca la misma, y
    su entrada enlaza a `/api/`. Su miniatura sale **llena con datos de
    ejemplo** (`EXAMPLES` en `samples.py`, por `fields.fill()`): con las marcas
    a la vista se vería una plantilla vacía.
  - **Todas miden 800 de alto**, así la miniatura las enseña enteras, sin corte
    ni blanco debajo (lo comprueba `test_samples.py`).

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
- **Arriba lleva solo el título**, «Aprende a usar el panel» (octubre de 2026):
  se quitaron la etiqueta «Tutoriales» y la entradilla. «Tutoriales» sigue
  siendo lo que oye un lector de pantalla en las pestañas (`TUTORIALS["label"]`).

**«Features» son diez dibujos sencillos** (octubre de 2026), en un carrusel
que aprieta: el abierto ocupa su sitio y los otros ocho quedan en listones.
Debajo, el texto del que esté abierto, y debajo de él una barra por función con
las flechas a la derecha. Fueron cinco: ese mismo mes «Contactos sin
duplicados» se hizo más general («Administra tus contactos») y entraron
etiquetas, campos personalizados, rebotes y quejas, y usuarios de la cuenta,
todo lo que el panel ya hace. En la página se llama **«Funciones»** y
es el único título de Cómo funciona; en el código sigue siendo `features`.

**Cada dibujo cuenta una sola cosa:**

| `art` | Lo que se ve |
|---|---|
| `contacts` | Un archivo CSV que entra a la lista: tres direcciones y «3 / 1000» |
| `tags` | Dos filas con la misma dirección, cada una con su etiqueta, que se juntan en una: el contador dice «1 / 1000». Era el dibujo de contactos |
| `fields` | El correo con «*\|NOMBRE\|*» y «*\|SALDO\|*», y el mismo como le llega a Ana |
| `editor` | Una hoja con un título elegido (con sus tiradores), una foto y un botón |
| `schedule` | «Enviar ahora» y «Programar», con el segundo marcado y su fecha |
| `results` | Tres cifras grandes (entregados, aperturas y clics) y «CSV · PDF» |
| `opens` | La lista de un envío, persona por persona, con un ojo (abrió) y un puntero (pulsó), encendidos en las que sí. Cuenta lo que ya hace «Detalles» de cada envío |
| `bounces` | Un sobre con su aviso de rebote, y «Fuera de tus envíos» con una dirección por rebote y otra por spam, tachadas |
| `unsubscribe` | El enlace al pie de un correo y el «Listo, ya no recibirás estos correos» |
| `users` | Ana, la dueña, y Luis, invitado, con las casillas de lo que Luis puede hacer |

- **Sin flechas punteadas** (octubre de 2026): los dibujos no llevan conector
  entre sus partes, que quedan juntas y centradas. Donde hay una acción, la
  señal es un mouse: anular suscripción lo lleva sobre su botón.
- **«Mira quién abrió y quién pulsó» es legal en Panamá y ya está dicho**: la
  política de privacidad cuenta que se mide si un correo se abrió o se pulsó, y
  los términos (§8) piden a quien envía que avise a sus destinatarios y obtenga
  su consentimiento donde se exija (la Unión Europea, por ejemplo). Las
  aperturas son aproximadas, porque algunos buzones abren solos los correos
  (`run_note` en el panel); los clics son más fiables.
- **Lo que cuentan existe en el panel:** contactos nuevos, editar, exportar e
  importar; etiquetas; columnas propias con `*|CAMPO|*`; supresiones; y los
  permisos de `models/account.py`. Rebotes y quejas los anula el aviso de SES,
  que está escrito pero todavía no conectado (ver «Antes de la primera campaña
  real» en `CLAUDE.md`).

- **Fueron cinco capturas del panel**, en un juego por tema que hacía
  `shots.py`, con una ventana para verlas en grande. Enseñaban demasiado de
  golpe, y se quitaron con su ventana: los dibujos se leen enteros en su sitio.
  `shots.py` se quedó con lo que comparten los tutoriales y las miniaturas: la
  cuenta de demostración, el panel y Chrome.
- **Son SVG dentro de la página**, en `src/partials/feature-*.svg.j2`, que la
  plantilla incluye por el `art` de cada uno. Se pintan con las clases `.art-*`
  de las ilustraciones de arriba, así que el mismo dibujo sirve de día y de
  noche. Los `id` llevan el prefijo de su dibujo (`fc-`, `ft-`, `ff-`, `fe-`,
  `fs-`, `fr-`, `fb-`, `fu-` y `fus-`), por lo mismo que los de las
  ilustraciones.
- **Cuatro también salen en el panel** (octubre de 2026): contactos, editor,
  envío y resultados rotan al lado de entrar y registrarse. Los convierte
  `backend/build_assets.py` desde estos mismos archivos y sus palabras, así que
  **cambiar uno de esos cuatro pide correr también `build_assets.py`**; su
  `--check` (y `test_generated`) lo avisa. Ver `docs/cuenta.md`.
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

**Lo que abre cada dibujo son diez botones de radio**, no un guion. Por eso la
sección funciona entera sin JavaScript y las flechas del teclado la mueven
solas, que es lo que se consigue gratis con un grupo de radios. Las barras de
debajo del texto son sus etiquetas, así que también se ven sin guion.
`assets/js/carousel.js` agrega dos cosas y nada más, y ninguna existe sin él
(como el interruptor de Planes): los botones de anterior y siguiente, y el paso
automático.
- **La barra de la abierta es el reloj** (octubre de 2026), como en «Haz crecer
  tu negocio»: el azul la llena en 8 s (`--tour-every`) y, llena, pasa a la
  siguiente (`animationend`).
- **Un cambio a mano** (una barra, un dibujo, el teclado o una flecha) espera
  un segundo con la barra de la nueva gris, y luego el azul empieza a llenarla.
- Se pausa fuera de la pantalla y con la pestaña escondida, y con «reducir
  movimiento» no existe; parada, la barra de la abierta queda azul y llena.
- **Hasta octubre de 2026 pasaba cada cuatro segundos** con un `setInterval`,
  sin barra, y el ratón encima o el foco dentro lo pausaban; elegir uno a mano
  reiniciaba la cuenta. Se igualó con las otras dos secciones.

**En el teléfono no hay apretujón**: los dos contenedores se vuelven
transparentes (`display: contents`) y cada dibujo queda encima de su texto, con
los diez a la vista. El apretujón necesita ancho para significar algo, y ahí
no lo hay. Tampoco hay barras ni flechas, y como sin barra no hay reloj, ahí no
pasa sola.

Las reglas del carrusel nombran los diez por su id (`#tour-1` … `#tour-10`), que
es lo que cuesta hacer esto sin una línea de JavaScript: si algún día son otros,
esas listas de `landing/src/site.css` crecen con ellos.

**Debajo del carrusel hubo una lista, «En todos los planes, sin excepción»**
(octubre de 2026), y se quitó ese mismo mes: rebotes y quejas fuera, sin
sorpresas al llegar al límite, acompañamiento en la primera campaña y sin
permanencia mínima.
- **Ahí se habían juntado tres bloques**: Features, «Reglas que funcionan
  solas», que cerraba Cómo funciona, y la lista «En todos los planes» del final
  de Planes. Lo que repetían lo cuentan los textos de los dibujos. La
  tabla comparativa de Planes se quedó.
- Con la lista se fue su caja (`.included`).
- **Al juntarlos salieron dos frases que prometían algo que no existe**:
  «envíate una prueba», porque ese envío de prueba no está hecho, y el aviso al
  80 % de la cuota, por lo mismo.

**Al final de Cómo funciona va «Dominio personalizado»** (octubre de 2026),
donde estaba «El envío / Los correos salen con el nombre y el correo de tu
empresa». Cuenta cómo se conecta y por qué conviene, en `HOW["sending"]`:
- primero quien tiene dominio: «Si tienes un dominio, agrégalo desde el
  panel», con los tres registros DNS y, al verificarse, sus campañas salen desde
  él;
- dos ventajas (`benefits`): la reputación propia y la firma con su dominio;
- después quien no tiene: sale desde `envios.sobreala.com` con el nombre de su
  negocio, y **ese dominio lo comparten todos los que envían sin dominio
  propio, y con él su reputación** (lo dice «Remitente» en `docs/envios.md`);
- al lado, la tarjeta compara las dos direcciones: «Con tu dominio» y «Sin
  dominio».
- **Dice lo que hace el panel de verdad** (ver «Remitente» en
  `docs/envios.md`): los tres CNAME con Easy DKIM y «Comprobar ahora». Salió la
  nota de antes, «lo configuramos contigo durante la activación», que ya no era
  cierta. La reputación propia es la del dominio; las IP siguen siendo las
  compartidas de SES, así que no se habla de ellas.

**La sección sigue al tema, como el resto de la página.** Hubo una banda que se
invertía, oscura de día y blanca de noche, porque las capturas de entonces eran
siempre del panel en oscuro; con ella se fueron las variables `--color-flip*` y
las clases `.section--flip` y `.section--deep`. **Los fondos alternan de arriba
abajo**: azul (la portada) · gris («¿Sigues enviando…?») · blanco (los usos) ·
gris (las tarjetas de Planes) · blanco (la tabla) · gris (Funciones) · blanco
(los tutoriales) · gris (la tira) · blanco (el dominio personalizado) · gris
(las preguntas) · azul (el pie). En oscuro, los mismos escalones.

**El pie es un solo azul** (octubre de 2026). Abajo, dentro del mismo azul, va
el «© Sobreala» en pequeño, con una raya fina encima (`--color-footer-edge`).
Lleva tres columnas: Producto, Legal y Contacto. Debajo del logo no va ninguna
frase: «Envía campañas de correo a toda tu lista desde un solo panel.» se quitó
en octubre de 2026.
- **Se quitaron los logos de pago** (Yappy, PayPal, Visa y Mastercard), que iban
  en una franja del color de la página debajo del azul. De noche el final de la
  página se leía negro, azul y negro otra vez, y de los cuatro medios hoy solo
  cobra PayPal: prometían de más. Los medios se ven al pagar, en el panel.
- **`build_site.py` ya no los copia**: salieron `PAYMENT_LOGOS`,
  `PAYMENT_LABELS`, `icon_size()` y `crop_logos()`, y la carpeta
  `assets/img/payments/`. El kit sigue en `brand/payments/`, y el panel tiene su
  propia copia para el pago (`backend/build_assets.py`, recortada con
  `brand/payments/viewbox.json`), que no cambió.

## La página de la API (octubre de 2026)

`sobreala.com/api/` (`src/pages/api.html.j2`) sale entera de
`backend/api_spec.py`, la misma descripción que sirve `/api/v1/openapi.json`:
las guías y cada ruta con su permiso, sus campos, un `curl` y una respuesta de
ejemplo. `build_site.py` la carga por ruta al construir, así que **cambiar la API
pide regenerar el sitio** (`--check` y `test_generated.py` lo vigilan). El pie
lleva «API» en Producto. Las pruebas comparan la descripción con las rutas de
verdad y las claves de cada respuesta con su ejemplo.
