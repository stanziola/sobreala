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
| `#inicio` | La presentación: el título y dos botones | `src/pages/index.html.j2` |
| `#api` | El bloque grande de la API | `src/sections/destacadas.html.j2` |
| `#lienzo` | El bloque grande del lienzo, sin botón en la barra | `src/sections/destacadas.html.j2` |
| `#planes` | Interruptor y tarjetas, y la tabla | `src/sections/planes.html.j2` |
| `#funciones` | El carrusel de Funciones, con el dominio personalizado al final | `src/sections/funciones.html.j2` |
| `#plantillas` | Las dos tiras de plantillas de muestra | `src/sections/plantillas.html.j2` |
| `#preguntas` | Seis preguntas frecuentes, sin botón en la barra | `src/partials/faq.html.j2` |

**El orden es el de octubre de 2026**, como se pidió: la API y el lienzo justo
después de la presentación, como lo principal. Hasta entonces era la portada
con «¿Sigues enviando correos masivos…?» y «Haz crecer tu negocio», Planes y
«Cómo funciona» (Funciones, los tutoriales, la tira y el dominio). Lo que salió,
en «Lo que salió de la portada», más abajo.

**Contacto es el pie** (`id="contacto"` en `base.html.j2`): WhatsApp, correo e
Instagram. Hubo una sección «Hablemos de tu lista» antes de las preguntas, y se
quitó en octubre de 2026 porque repetía el pie; `/contact/` y `/#contacto`
aterrizan ahí. Con ella se fue el `id` repetido que había entre las dos.

**En octubre de 2026 salieron dos secciones más:**
- **«Qué significa cada fila»**, el glosario de debajo de la tabla de Planes;
- **«Nosotros»**, con su columna «Empresa» del pie, que solo lo enlazaba.

**Las preguntas frecuentes se quitaron y volvieron ese mismo mes, más cortas:**
seis en vez de once (`HOME["faq"]`), entre Plantillas y el pie, cada una en
un `details` que se abre sin JavaScript y con la primera abierta. Cada respuesta
se revisó contra `docs/`: las de antes decían que el dominio «lo configuramos
contigo», cuando el cliente lo conecta solo, y que se podía bajar de plan en
cualquier momento, cuando con un plan vigente solo se mejora. Son: cómo empiezo,
si necesito dominio, cómo se paga, los correos que no uso, cambiar de plan y la
permanencia.

`/about/` sigue respondiendo y lleva al inicio.

- **Cada sección conserva sus textos en su diccionario de `content.py`**:
  Planes los de `PRICING`, que `index.html.j2` incluye con
  `{% with page = … %}`; los bloques grandes, Funciones y Plantillas, los de
  `HOME` (`highlights`, `features` y `steps`). `CONTACT_PAGE`
  y `ABOUT` solo guardan el título de su página de paso. El `hero` de
  cada una es ahora la cabeza de su sección, con su `h2`: hay un solo `h1`.
- **La barra lleva Inicio, API, Planes, Funciones y Plantillas** (octubre de
  2026; antes Inicio, Planes y Cómo funciona). El lienzo y las preguntas no
  llevan botón. El pie baja también a Funciones y Plantillas.
- **Las cabezas llevan solo su título** (octubre de 2026): «Planes», sin la
  etiqueta «Precios» ni la entradilla; «Funciones», que reemplazó a «Cómo
  funciona / De tu base de datos…» y a «Features» con las suyas; y
  «Plantillas», con la pregunta de antes («¿Aún no sabes por dónde
  empezar?») de entradilla. `HOW` («Cómo funciona») y `PRICING["hero"]["title"]`
  solo siguen ahí para su página de paso.
- **Los botones de la barra solo desplazan** (`/#planes`, con la `/` para que
  sirvan también desde las legales). La barra fija no tapa el título:
  `scroll-margin-top` en `.page-part` y en las secciones con `id`. **El botón de
  la sección que se está leyendo se marca** con un `IntersectionObserver` en
  `nav.js`, mirando una franja justo debajo de la barra.
- **Las direcciones de antes siguen respondiendo**: `/pricing/`,
  `/how-it-works/`, `/about/` y `/contact/` son páginas de paso
  (`src/redirect.html.j2`, tabla `REDIRECTS` de `build_site.py`) con
  `noindex`, que mandan a su ancla (`/about/`, al inicio) y conservan el `#`
  que traigan. `/how-it-works/` lleva a `#funciones` desde que «Cómo
  funciona» salió (octubre de 2026). El panel ya enlaza
  directo a `/#planes`. `sitemap.xml` y las tarjetas para compartir son solo de
  `/` y las legales.
- **La página carga dos guiones**: `carousel.js` (Funciones) y `plans.js`.
  `trouble.js` y `stories.js` se borraron con sus secciones, y `tutorial.js`
  se quedó en `assets/js/` sin cargarse, para cuando vuelvan los tutoriales.

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
palabra**; las tarjetas (`.plan`, `.faq__item`) **suben** con un retraso entre ellas; y los precios de los
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

### Los dos bloques grandes: la API y el lienzo (octubre de 2026)

**Debajo de la presentación van la API y el lienzo, uno después del otro, como
lo principal** (`src/sections/destacadas.html.j2`, textos en
`HOME["highlights"]`). Cada uno a lo ancho, con su etiqueta, su título, una
entradilla, cuatro puntos con su ganchito, un botón y su dibujo; el dibujo
cambia de lado de uno al otro (`.highlight--flip`) y en el teléfono va arriba.
La API en blanco y el lienzo en gris.
- **La API** lleva la etiqueta «Desde el plan Negocio», que es la regla del
  producto (ver «La API desde Negocio» en `docs/api.md`), y el botón «Ver la
  documentación» a `/api/`. Su dibujo es **una tarjeta de código en HTML**, no
  una imagen: la llamada de verdad a `POST /api/v1/emails`, la del ejemplo de
  `backend/api_spec.py` recortada, y su respuesta 201. Es oscura en los dos
  temas, como un editor, y larga se desliza de lado dentro de la tarjeta.
- **El lienzo** lleva su dibujo (`feature-editor.svg.j2`, con sus palabras en
  `HOME["highlights"]["canvas"]`): fue también una de las Funciones, y salió de
  ahí por estar arriba. Su botón es
  como el de la presentación: sin sesión, «Solicitar demo» a crear la cuenta, y
  con sesión `nav.js` lo cambia según en qué punto está la empresa; **quien ya
  puede usar el lienzo (la demostración o un plan) va a él**
  (`/templates/create`). Al administrador se le esconde.
- **Sin cifras ni promesas**: los puntos cuentan lo que el producto ya hace
  (ver `docs/plantillas.md` y `docs/api.md`).

### Lo que salió de la portada (octubre de 2026)

- **«¿Sigues enviando correos masivos desde Gmail o Outlook?»**, cuatro puntos
  con su ilustración que se recorrían solos, con `trouble.js` y los dibujos
  `art-{manual,spam,privacy,tracking}.svg.j2`.
- **«Haz crecer tu negocio»**, cuatro casos (comercios, empresas, cooperativas
  y colegios) con una foto de Pexels cada uno, con `stories.js` y
  `assets/img/usos/`.
- **Los tutoriales** de «Cómo funciona», que vuelven cuando se rehagan (ver más
  abajo); y con ellos el nombre «Cómo funciona», que dejó su sitio en la barra.
- **Tres funciones**: etiquetas (lo cuenta la base de datos), el envío
  programado y los usuarios de la cuenta. Siguen en el producto.

Todo eso está en la historia de git, y los textos de cómo funcionaba, en la
versión de este documento de antes de ese cambio.

**Plantillas (`#plantillas`) es la tira de plantillas que corre sola**
(septiembre de 2026), en su propia sección desde octubre de 2026: antes iba
dentro de «Cómo funciona», debajo de los tutoriales. Lleva el título
«Plantillas», con «¿Aún no sabes por dónde empezar? Prueba nuestras plantillas
personalizadas.» de entradilla, y las plantillas de `SAMPLES`.
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

**Los tutoriales salieron de la portada en octubre de 2026** y vuelven cuando
se rehagan, al final del panel. Lo suyo sigue entero (`TUTORIALS`,
`tutorials.py`, sus capturas, `tutorial.js` y su CSS), y
`test_tutorials.py` lo sigue comprobando; lo de abajo es cómo eran.

**Los tutoriales de «Cómo funciona» eran capturas del panel que se recorren
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

**Funciones son seis dibujos sencillos** (octubre de 2026), en un carrusel
que aprieta: el abierto ocupa su sitio y los otros cinco quedan en listones.
Debajo, el texto del que esté abierto, y debajo de él una barra por función con
las flechas a la derecha. En el código sigue siendo `features`.
- **Son, en este orden**: Campos personalizados, Base de datos,
  Resultados de cada campaña, Actividad de tus clientes (quién abrió y quién
  pulsó), «Bajas, rebotes y quejas, solos» y Dominio personalizado.
- **Fueron cinco, después diez y ahora seis**: en octubre de 2026 entraron
  etiquetas, campos, rebotes y quejas, y usuarios; ese mismo mes salieron
  etiquetas (lo cuenta la base de datos), el envío programado y los usuarios,
  anular la suscripción y los rebotes se juntaron en uno, el dominio
  personalizado, que era una sección, pasó a ser la última, y **el lienzo
  salió**, porque tiene su bloque grande arriba.

**Cada dibujo cuenta una sola cosa:**

| `art` | Lo que se ve |
|---|---|
| `contacts` | Un archivo CSV que entra a la lista: tres direcciones y «3 / 1000» |
| `fields` | El correo con «*\|NOMBRE\|*» y «*\|SALDO\|*», y el mismo como le llega a Ana |
| `editor` | Una hoja con un título elegido (con sus tiradores), una foto y un botón |
| `results` | Tres cifras grandes (entregados, aperturas y clics) y «CSV · PDF» |
| `opens` | La lista de un envío, persona por persona, con un ojo (abrió) y un puntero (pulsó), encendidos en las que sí. Cuenta lo que ya hace «Detalles» de cada envío |
| `unsubscribe` | El enlace para anular la suscripción al pie de un correo, y «Fuera de tus envíos» con una dirección por baja, otra por rebote y otra por spam, tachadas (lo que eran los dibujos `unsubscribe` y `bounces`) |
| `domain` | Los tres registros CNAME, verificados, y un correo «De: boletin@tuempresa.com» con su «Verificado»; abajo, de dónde saldría sin dominio |

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
  noche. Los `id` llevan el prefijo de su dibujo (`fc-`, `ff-`, `fe-`,
  `fr-`, `fu-` y `fd-`): un `id` repetido en una página hace que un dibujo use
  el filtro de otro.
- **Cuatro también salen en el panel** (octubre de 2026): contactos, editor
  (el del bloque del lienzo, que `build_assets.py` toma de ahí),
  resultados y quién lo vio (`opens`, desde que el de envío programado salió)
  rotan al lado de entrar y registrarse. Los convierte
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

**Lo que abre cada dibujo son seis botones de radio**, no un guion. Por eso la
sección funciona entera sin JavaScript y las flechas del teclado la mueven
solas, que es lo que se consigue gratis con un grupo de radios. Las barras de
debajo del texto son sus etiquetas, así que también se ven sin guion.
`assets/js/carousel.js` agrega dos cosas y nada más, y ninguna existe sin él
(como el interruptor de Planes): los botones de anterior y siguiente, y el paso
automático.
- **La barra de la abierta es el reloj** (octubre de 2026): el azul la llena en 8 s (`--tour-every`) y, llena, pasa a la
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
los seis a la vista. El apretujón necesita ancho para significar algo, y ahí
no lo hay. Tampoco hay barras ni flechas, y como sin barra no hay reloj, ahí no
pasa sola.

Las reglas del carrusel nombran los seis por su id (`#tour-1` … `#tour-6`), que
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

**«Dominio personalizado» es la última de Funciones** (octubre de 2026). Fue
una sección aparte al final de «Cómo funciona», con dos ventajas y una tarjeta
que comparaba las dos direcciones de salida; ese mismo mes pasó a ser una
función, con su dibujo (`feature-domain.svg.j2`). Lo que dice:
- con un dominio, se agrega desde la cuenta con tres registros DNS y, al
  verificarse, las campañas salen desde él, firmadas y con una reputación que
  depende solo de sus envíos;
- sin dominio, salen desde `envios.sobreala.com` con el nombre del negocio.
- **Dice lo que hace el panel de verdad** (ver «Remitente» en
  `docs/envios.md`): los tres CNAME con Easy DKIM y «Comprobar ahora». Nunca
  «lo configuramos contigo», que ya no era cierto. La reputación propia es la
  del dominio; las IP siguen siendo las compartidas de SES, así que no se
  habla de ellas.

**La sección sigue al tema, como el resto de la página.** Hubo una banda que se
invertía, oscura de día y blanca de noche, porque las capturas de entonces eran
siempre del panel en oscuro; con ella se fueron las variables `--color-flip*` y
las clases `.section--flip` y `.section--deep`. **Los fondos alternan de arriba
abajo** (octubre de 2026): azul (la presentación) · blanco (la API) · gris
(el lienzo) · blanco (Planes) · gris (Funciones) · blanco (Plantillas) · gris
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


## El centro de ayuda (octubre de 2026)

**`sobreala.com/ayuda/`** es una página aparte (`src/pages/ayuda.html.j2`, sus
textos en `HELP` de `content.py`, y su fila en `PAGES`, con la que entra al
sitemap). Es a donde lleva el pie de los correos del sistema: «¿Necesitas
ayuda? Visita el centro de ayuda» (antes «Ayuda» iba a las preguntas de la
portada, en gris, con los íconos de Instagram y WhatsApp al lado).

- **Las preguntas van por tema**: Cuenta y acceso, Contactos, Plantillas,
  Envíos, Pagos y API, cada una con el acordeón de las preguntas de la portada
  (`<details>`, sin guion), y arriba los temas como pastillas que bajan a su
  sección. **Cada respuesta se escribió contra `docs/`**: si algo cambia allí,
  cambia aquí.
- **Al final, cómo escribirnos**: WhatsApp y el correo, con los mismos
  enlaces del pie del sitio (`whatsapp_url()`, `mailto_url()`).
- El pie del sitio lleva «Ayuda» en Producto. El panel no tiene pie, y el menú
  de los dos sitios no la lleva (no se pidió).

