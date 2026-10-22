# Plantillas: el lienzo, las de antes y sus imágenes

Detalle que vivía en `CLAUDE.md`, movido tal cual para que ese archivo
cupiera en el límite. Lo esencial (las reglas, las convenciones y el
resumen de cada parte) sigue allí; esto es lo que hay que leer antes de
tocar esta parte.

### `designs`
Las piezas de un cliente. Se llaman «diseños» y no «templates» porque en este
repositorio `templates/` ya son las plantillas Jinja del panel; para el cliente
la pantalla dice **Plantillas**, que es su palabra.

**`source` dice de dónde salió cada una**, y hay tres:

| `source` | Qué guarda | Quién puede |
|---|---|---|
| `canvas` | El lienzo en JSON, con sus coordenadas (ver «El lienzo») | Todos |
| `upload` | El HTML entero, tal como llegó | Ya no se crean: las que hay se editan |
| `builtin` | De qué prediseñada salió y **qué escribió en cada casilla** | Ya no se crean: las que hay se editan |

De una prediseñada llena **no se guarda el correo armado**. Guardar el resultado
la dejaría imposible de volver a editar, y además el archivo de la plantilla
puede mejorar: al reabrirla se arma otra vez con lo que ese archivo diga hoy. Los
archivos de las prediseñadas viajan con el repositorio, en `email_templates/`,
iguales para todos y sin nada que aprobar.

**El HTML propio ya no se sube** (septiembre de 2026). Fue de Negocio en
adelante, con la fila «Subir tu propio HTML» de `docs/pricing.md`, y se quitó de
todos lados: del panel, de los planes y del sitio. Las plantillas se arman en el
lienzo, y **lo que se carga es el ZIP de un lienzo** (ver «Bajarse la pieza»),
que se abre en el editor tal como estaba. Un `.html` suelto, o un ZIP sin
lienzo, se rechaza en todos los planes. **Las piezas HTML que ya existían se
quedan**, como las prediseñadas: siguen en su lista, se envían y se editan como
código con cualquier plan.

**Cada vez que se guarda una, se valida** con `services/html_check.py`, que lee
el documento con un parser y no con expresiones regulares —`&lt;script&gt;` es
texto y `<script>` no—. Fuera: `<script>`, `<iframe>`, `<object>`, `<form>`,
atributos de evento, hojas de estilo de otro sitio, imágenes que no van por
`https://` (las del propio panel entran aunque vayan por http, que es como corre
en desarrollo), y **cualquier pieza de más de 102 KB**. Lo que se guarda es el
archivo entero y tal como llegó.

**Las imágenes `https://` de otro sitio sí entran**: es lo que traía un HTML
hecho con una IA o bajado de internet. Pero dependen de ese sitio, así que el editor
de HTML las enseña en **«Imágenes de esta plantilla»** (`html_images()`), cada
una con su estado: de la cuenta, de otra cuenta (sale rota el día que esa la
borre), de otro sitio, borrada (sale rota) o dentro del archivo (`data:`, que
Gmail no muestra). **«Cambiar»** sube una foto por la ruta
de siempre del lienzo (con su revisión, su achique y el tope del plan) y cambia esa
dirección en el código; se guarda con Guardar. **El panel no va a buscar la
imagen de fuera**: la sube quien la tiene.

**Nadie aprueba una pieza a mano.** Lo que puede hacer daño lo rechaza el
validador al guardarla, y eso es mecánico, no un juicio. La mirada de una persona
ocurre una sola vez por cuenta, en la demostración que la abre, y es sobre la
empresa y su lista, no sobre el archivo. Tener las dos serían dos revisiones
manuales para la misma decisión. Hubo una pantalla en administración,
**Plantillas subidas** (`/admin/templates`), que listaba el HTML que subieron
los clientes cuando se podía y dejaba bajarlo como texto. Se quitó en octubre de
2026: solo enseñaba piezas viejas. Esas piezas siguen editándose y enviándose
como siempre.

**El HTML de un cliente se dibuja solo para él, y solo en un marco aislado.**
Es lo que deja editarlo viendo cómo queda (`/templates/html/<id>`): el código a
un lado, la vista previa al otro, y un botón por columna que escribe su marca
donde está el cursor. El marco va con `sandbox` y sin ningún permiso —origen
opaco, sin scripts, sin ver la galleta— y la respuesta lleva la cabecera de
seguridad de un correo, no la del panel. Antes de dibujarse pasa el validador:
lo que no se podría guardar tampoco se enseña, y en su lugar sale por qué. Con
JavaScript se refresca sola al dejar de escribir, pulsando por su cuenta el
botón de ver cómo queda; un marco llenado desde el panel heredaría la cabecera
del panel y no dejaría pasar los estilos del correo. **En el panel del
administrador sigue sin dibujarse**: allí se baja como `text/plain`.

**La lista de plantillas son tarjetas con el correo dentro.** Cada una enseña la
pieza armada como correo, achicada en un marco aislado (`sandbox`, sin permisos,
con `loading="lazy"`), y debajo el nombre, de qué clase es, cuándo se tocó y
Editar, Duplicar, Borrar y «Mover a…». Lo sirve **`GET /templates/<id>/preview`**, que arma
las tres clases de pieza con lo que ya existía (`html_preview()`,
`canvas_email()` y `preview()`) y lleva la cabecera de correo; la pieza de otra
cuenta responde 404. Una tabla de nombres obligaba a abrir cada una para
acordarse de cuál era. **Duplicar copia las imágenes por nombre**, así que
borrar una pieza solo borra las imágenes que ninguna otra nombra.

**Mis plantillas es sus carpetas y, debajo, las sueltas** («Sin carpeta»), y su
único botón es «Nueva carpeta» (octubre de 2026). Hasta entonces tenía arriba
dos caminos, Crear plantilla y Cargar plantilla (ZIP), y dos notas: el dato de
cada persona, con las columnas de la cuenta, y el tope de 102 KB. Se quitaron
a pedido: **crear y cargar viven en el Lienzo**, y las dos notas ya estaban
dentro del editor (los botones de las marcas y la revisión de peso). **Cargar
plantilla (ZIP)** es un botón del Lienzo que abre la misma bandeja de antes;
sin JavaScript lleva a `/templates/upload`, que es la misma ruta, y al cargar se
va directo al editor del lienzo nuevo. Cada lista enseña hasta 50 tarjetas,
como antes, y se lee sin el HTML ni el lienzo de cada pieza (`designs.LISTED`).

### Las carpetas

Para agrupar las plantillas (octubre de 2026), con el dibujo de la carpeta de
cristal del componente «Glass Folder Cards», rehecho sin React: el panel es
Jinja con su propio CSS y JavaScript, y meter React, Tailwind y shadcn habría
sido un segundo sistema de construcción para un solo dibujo.

- **Viven en la cuenta de la empresa**, como sus etiquetas:
  `accounts.design_folders`, una lista de `{id, name, color}`, y cada plantilla
  dice la suya en `designs.folder_id`. Un solo nivel; hasta 50 (`FOLDER_LIMIT`);
  el nombre, de 1 a 40, no se repite sin mirar mayúsculas; el color es uno de
  nueve (`FOLDER_COLORS`: gris, que es el de siempre, blanco, azul, verde,
  ámbar, rojo, morado, rosa y turquesa). El blanco se pidió aparte, y en oscuro
  sigue claro: detrás del cristal ahumado se ve en la pestaña. Lo hace
  `models/design.py`.
- **El dibujo** (`designs/_folder.html` y «La carpeta de cristal» en
  `_panel.src.css`): el fondo del color de la carpeta, las plantillas en medio y
  delante un cristal esmerilado (`backdrop-filter`) con su bisagra abajo; sus
  dos formas son las rutas del componente, como `clip-path`. Se dibuja a
  340 × 272 y se achica entera con `--k`, por eso sus letras van más grandes que
  en el componente. En oscuro, el cristal es ahumado.
- **Al pasar el ratón** (o con el foco dentro) el cristal se inclina y asoman
  **las tres de cambio más reciente** (`changed_at()`, `PEEK`; fueron cuatro
  hasta que se pidieron tres, para entrar rápido a una); **pulsar una abre esa
  plantilla** en su editor, y
  **pulsar el cristal entra a la carpeta** (`/templates/folders/<id>`, con todas
  como tarjetas; la de otra cuenta da 404). Sin ratón, tocar la carpeta entra.
  El panel no deja estilos escritos en el HTML (`style-src 'self'`), así que
  dónde va cada hoja lo dice el CSS por su lugar en la lista
  (`folder__files--N`), con un desorden fijo de ocho (`folder__sheet--jN`).
- **Cada hoja es su plantilla**: el correo de verdad, achicado al ancho de la
  hoja, **sin su nombre a la vista**: las hojas son para entrar rápido a una, y
  los nombres se leen dentro de la carpeta (el nombre queda escondido para
  quien no ve la hoja). Llevó el nombre en blanco encima unas horas, y se
  quitó a pedido. Es la vista de las tarjetas (`/templates/<id>/preview`) en un
  marco aislado, que `panel.js` pide la primera vez que el ratón (o el foco)
  entra a la carpeta (`data-src`), para que la página no pida todas de golpe;
  hasta que carga, y sin JavaScript, la hoja es papel con rayas. El enlace al
  editor va encima del marco y no lo envuelve, porque un marco no puede ir
  dentro de un enlace.
- **Se arrastra, como en Windows** (`panel.js`). Las tarjetas se eligen con un
  clic (Ctrl suma, Mayús un tramo, Esc o un clic en lo vacío lo quita) y las
  elegidas se arrastran juntas; también se arrastran las hojas que asoman, para
  pasarlas a otra carpeta. Se sueltan en una carpeta (`data-drop-folder`), que
  se abre y se marca en azul; en «Sin carpeta», que con carpetas sale siempre;
  o, dentro de una carpeta, en «← Mis plantillas». Una tarjetita sigue al ratón
  con el nombre, cuántas son y adónde van, y cerca del borde la página se
  desplaza sola. Al soltar se manda el formulario escondido de la página
  (`designs/_drag_form.html`, a `POST /templates/move` con una `id` por
  plantilla) y se vuelve con «Listo, se movieron 3 plantillas.». Esc o soltar
  fuera cancelan. Va con eventos de puntero y no con el arrastre del navegador,
  para dibujar la tarjetita y la carpeta como se quiere, y **solo con ratón**:
  en el teléfono el dedo desplaza la página, y ahí, como con el teclado, está
  «Mover a…».
- **El menú ⋮**, en vertical: Abrir, Cambiar nombre, Cambiar color y Eliminar.
  Es un `<details>`, y cada opción abre su bandeja, que `panel.js` llena con la
  carpeta pulsada (`data-folder-tray`); sin JavaScript, el mismo enlace abre la
  página con la bandeja ya llena (`?carpeta=<id>&editar=…`), y ahí vuelve
  también si algo no se pudo guardar. Todo pasa por `POST /templates/folders`
  con su `action`.
- **Eliminar una carpeta nunca borra sus plantillas**: quedan sin carpeta, y la
  bandeja lo dice antes.
- **Se entra a una carpeta** arrastrando, con «Mover a…» en cada tarjeta
  (`POST /templates/move`, `designs.move_many()`, solo a una carpeta de la misma
  cuenta) o eligiéndola en la lista «Carpeta» del Lienzo al guardar. Duplicar
  deja la copia en la misma. Mover no cuenta como un cambio: no la vuelve de las
  más recientes.
- **Se vuelve a donde se estaba**: guardar una plantilla que está en una
  carpeta, duplicarla, moverla o borrarla vuelve a esa carpeta (`listed_at()`).

### De quién sale cada plantilla

**Los tres editores** (el Lienzo, el HTML de antes y las prediseñadas de antes)
llevan dos listas, **«Sale de»** y **«Responder a»** (`designs/_sending.html`,
octubre de 2026), con los remitentes que pueden salir y los «Responder a»
confirmados de la cuenta. La primera opción de cada una es el predeterminado,
que es lo que vale si no se elige. Se guardan con Guardar
(`designs.set_sending()`: `send_from` y `reply_to`), y solo se acepta lo de la
propia cuenta (`sending_choice()`). Si lo elegido se quita de Remitente, la
plantilla vuelve al predeterminado. Lo demás está en «Envío» de
`docs/envios.md`.

## El Lienzo

La fila «Lienzo» de Plantillas, que se llamó «Crear» hasta octubre de 2026 (el
buscador la sigue encontrando por «crear»).
`/templates/create` y `/templates/canvas/<id>`, con `services/canvas.py` y
`static/js/canvas.js`. **Es una sola hoja de 600 px que crece hacia abajo**:
texto, botón, imagen y geometría se ponen donde se quiera, se mueven, cambian
de tamaño y de estilo, y se deshace y rehace. Se guarda **el lienzo en JSON con
sus coordenadas** (`source: "canvas"`, `{v: 2, h, bg, items}`), no el HTML: el
correo se arma al enviar.

**La pantalla es como la de Canva** (22 de octubre de 2026): ocupa la ventana
entera, sin la barra del panel ni el árbol del Dashboard.
- **Arriba, su propia barra**: el ala vuelve a Mis plantillas, el nombre se
  escribe ahí mismo, deshacer y rehacer, Previsualización, Descargar (PDF y
  ZIP, en un menú), Cargar, Guardar y el menú de la cuenta.
- **A la izquierda, un riel de íconos** que abre su panel y lo cierra al
  volver a pulsarlo: **Texto** (un título, un subtítulo, un texto, una lista y
  un botón, cada uno con su tamaño de partida), **Elementos** (las figuras,
  dibujadas en cuadrícula), **Subidas**, **Variables** (los `*|CAMPO|*`),
  **Revisión** (el peso y lo que falta para poder enviarse, con un punto en el
  ícono si falta algo) y **Ajustes** (la carpeta, «Sale de», «Responder a» y
  los atajos). El último abierto se recuerda en ese navegador.
- **Encima de la hoja, la barra de lo elegido**, en una fila: cambia con lo
  elegido, y lo menos usado va en «⋯».
- **La hoja, en medio, con zoom**: «Ajustar» la lleva al ancho que queda
  (hasta 125 %), y se acerca y aleja con −, +, Ctrl y la rueda o Ctrl + y
  Ctrl −. La hoja sigue midiendo 600 px: el zoom es solo la vista, y
  `canvas.js` divide entre él todo lo que llega del ratón (`unzoom()`).
- **El formulario de Guardar va aparte y vacío** (`#lienzo-guardar`), y el
  nombre, la carpeta, «Sale de» y Guardar lo nombran con `form`: el menú de la
  cuenta trae su propio formulario (cerrar sesión), y uno dentro de otro
  cerraba el de fuera antes de tiempo.
- **En el teléfono** el riel baja como una barra, el panel sube encima de él y
  la barra de lo elegido se desplaza de lado.

**Se eligen varios a la vez** con Ctrl+clic (Cmd en Mac) o Mayús+clic, o
arrastrando un recuadro sobre la hoja (con Ctrl o Mayús, se suma a lo que ya
estaba elegido), y entonces se mueven juntos, se alinean, se reparten, se duplican y se
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

**El panel Subidas** (octubre de 2026) sube varias de una vez, pone «Mi logo»
y enseña **las fotos que ya subió la cuenta** (`GET /templates/canvas/images`,
de la más nueva a la más vieja, de 30 en 30, sin los fondos fundidos ni el
logo, y solo de esa cuenta; `images` guarda ahora su ancho y su alto). Se
pulsan para ponerlas en medio de lo que se ve, o **se arrastran a donde se
quieran**; un archivo del escritorio soltado en la hoja también entra donde
cae, con el zoom descontado. **Una foto del lienzo puede pesar hasta 10 MB**
(`imaging.PHOTO_MAX`): esa ruta sube su propio tope de petición
(`request.max_content_length`, Flask 3.1) y las demás subidas siguen en 5 MB.
**Un SVG no llega al servidor**: el editor lo dibuja en un `<canvas>` y sube su
PNG, porque un SVG puede llevar código; uno mandado directo se rechaza, porque
lo que llega se reconoce por lo que trae dentro.

**Una foto se puede pegar del portapapeles**, y sube por la misma ruta que el
botón (`/templates/canvas/image`): se revisa por lo que trae dentro, se achica
y cuenta contra el tope del plan. Si el portapapeles solo trae **una dirección
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

**El alto de la hoja lo pone quien la usa, y nada más.** Se escribe en la barra
de cuando no hay nada elegido, se arrastra el borde de abajo o se pulsa
**«Ajustar al contenido»**, que la pega a lo último que haya dentro; **insertar,
mover y cambiar de tamaño no la estiran**. Antes crecía sola y agregar un
texto al final alargaba la página sin haberlo pedido. Lo escrito se limita entre
lo que hay dentro y los 4,000 px, y cuando no cabe se queda en el mínimo **y lo
dice**.

Ese botón es lo que quita el blanco del final del correo: `to_html()` cierra la
hoja con una fila de relleno del alto que sobra (`_gap_row`), así que una pieza
de 600 px con el contenido acabado en 200 mandaba 400 px en blanco justo antes
del botón de la baja. **El relleno se sigue dibujando**: quien quiera aire al
final lo tiene, y quien no, lo pega de un clic.

**Lo que se inserta entra arriba de la hoja**, que es donde se está mirando, y
de ahí se mueve a mano. Si ya hay algo justo ahí, lo siguiente baja 20 px, como
en un editor de diapositivas, y vuelve arriba al llegar al borde. Lo que no
quepa **se achica al entrar** en vez de rechazarse, y una foto conserva su
proporción. Antes buscaba un hueco libre mirando solo franjas horizontales: un
texto pequeño a media hoja invalidaba toda la banda, así que una figura (160 px)
o una foto (400) no entraban, y el aviso salía arriba del todo de la página,
fuera de la vista. Los botones de Geometría e Imagen parecían muertos.

**Las cajas de texto tienen el tamaño que se les pone** (octubre de 2026).
Antes una caja crecía sola al escribir, al soltar un tirador y al cambiar la
letra, y en el correo el texto que no cabía salía entero y empujaba lo de
abajo: el correo salía más largo que el lienzo. Ahora:

- **En el editor** lo que no cabe queda oculto (`overflow:hidden`), y mientras
  se escribe se ve desplazando dentro de la caja. Las que no caben llevan una
  raya roja al pie y el aviso «Hay textos que no caben en su caja», que se mira
  **al abrir la plantilla** (las de antes, los ZIP y las creadas por la API
  pudieron quedar así), al terminar de escribir, al soltar un tirador y al
  cambiar la letra (`checkFit()` en `canvas.js`). **«Ajustar la caja al
  texto»**, en la barra del texto, la agranda hasta que quepa (`fitText()`).
- **En el correo** el texto va dentro de un `div` del alto de la caja con
  `overflow:hidden` (`canvas._clipped()`): lo respetan Gmail, Apple Mail,
  Outlook.com, el Outlook nuevo y Yahoo, según caniemail.com. **Outlook de
  escritorio para Windows no lo respeta**, y ahí el texto que no cabe sigue
  empujando.
- **El PDF** recorta en el mismo sitio (`canvas_pdf._text`, con un trazado de
  recorte).
- **La excepción son las cajas con variables** (`*|NOMBRE|*`, `*|PRODUCTOS|*`,
  un bloque `*|#LISTA|*`; `canvas.has_variables()`): **crecen**, en el correo y
  en el PDF, porque el largo de cada valor se sabe solo al enviar (un nombre de
  120 caracteres, una tabla de diez filas) y recortarlas cortaría datos de la
  persona. Desde el lienzo no se puede saber si una variable es una lista: las
  que llegan por la API pueden ser tablas sin ser columnas. El editor lo dice
  en esas cajas.
- La revisión antispam cuenta los 200 caracteres sobre todo el texto, también
  lo que queda oculto en una caja que no cabe.
El ancho no se toca, 600 px es lo que se lee bien en todos los buzones. Topes: **4,000 px de alto y 60 elementos**; lo que
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

- **La geometría son seis figuras**, en un menú (`<details>`, abre sin guion):
  rectángulo, línea, círculo, triángulo, estrella y flecha, cada una con su
  medida al entrar. El rectángulo y la línea salen como celda de color cuando
  llenan su grupo; **las otras cuatro no pueden**, porque Outlook de escritorio
  ignora `border-radius` y no sabe dibujar un polígono, así que se pintan en la
  imagen del grupo (`ImageDraw.polygon`) y suman a la parte de imagen que la
  revisión permite. **El editor las dibuja con el mismo recorte** (`clip-path`
  con los mismos puntos), sobre un hijo de la caja y no sobre ella: recortar la
  caja recortaría también sus tiradores.
- **La línea es fina de verdad**: su alto es su grosor, de 1 a 12 px
  (`LINE_MIN`, `LINE_MAX`), y es lo único que puede bajar de los 16 px de
  `MIN_BOX`. Solo se tira de sus puntas; el grosor se escribe en «Grosor», y
  horizontal, vertical o diagonal es girarla. Una franja invisible arriba y
  abajo deja pulsarla aunque mida 1 px. Derecha es una celda de color, con el
  interlineado fijado a su alto (`_thin()`) para que Outlook no la engorde a un
  renglón; girada, va en la imagen del grupo. Hasta septiembre de 2026 era «línea
  divisoria», un rectángulo más que nunca bajaba de 16 px: **una «línea» guardada
  con más de 12 px se lee como rectángulo**, que es como se dibujaba.
- **Las fotos y las figuras giran** con un tirador encima de la caja, como en un
  editor de diapositivas (arrastrar gira, con Mayús de 15 en 15), o escribiendo
  los grados (`rot`, hacia la derecha como en CSS). El tirador lleva dentro
  **una flecha que cierra un círculo**: un punto blanco y solo no dice qué hace.
  **El texto y los botones no giran**, porque girarlos obligaría a
  convertirlos en imagen y ahí se pierden `*|NOMBRE|*`, la lectura con las
  imágenes bloqueadas y los 200 caracteres de texto real que pide la revisión.
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

**Los tiradores de lo elegido viven en su propia capa** (`.cv-chrome`), encima
de la hoja y **fuera del elemento**. Dentro no pueden ir: cada caja tiene su
z-index, así que es su propio contexto de apilado y sus hijos no se escapan de
él, y el del giro sale 32 px por encima. Hubo un atajo —subir el elemento
elegido a la capa de arriba— y se quitó: una figura del fondo saltaba delante de
todo al tocarla, y el editor dejaba de enseñar el orden con el que sale el
correo. Por lo mismo, **la hoja tiene aire arriba**: sin él, el tirador del giro
de algo pegado al borde caía debajo de la barra de propiedades, que es de la
página y gana siempre.

**Los textos y los botones son texto de verdad**: es lo que evita que el correo
se lea como una foto (de lo que más va a spam), lo que deja funcionar `*|EDAD|*`
y lo que se sigue leyendo con las imágenes bloqueadas. Por eso **no se deja
encimar un texto sobre otro ni sobre un botón**, y **una foto con enlace no
puede tener nada encima**: fundida con otra cosa, el enlace sería de toda la
imagen. El editor los marca en rojo y el servidor no guarda.

**El modo oscuro no cambia los colores del diseño.** Outlook en el teléfono y en
la web «corrige» colores en oscuro: el texto blanco sobre una foto salía gris
oscuro y un botón negro se quedaba sin fondo. Cada color lleva una clase
(`sac-FFFFFF` la letra, `sab-000000` el fondo) y `canvas.dark_css()` escribe en
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

**Las fotos del lienzo se guardan a 1200 px** y cuentan contra el tope del plan; **las
imágenes de los grupos no** (`kind: "background"` en `images`, el nombre es de
cuando eran fondos): las hace el sistema. Se guardan en `backgrounds` y sus
colores en `shades`, en el orden de `groups()`. Al volver a guardar, las viejas
se borran si ninguna otra pieza las nombra, que es lo que pasa con una copia,
**salvo las que ya salieron en un envío**, que se quedan retiradas (ver
`images`).

**La foto se recorta sin tocar el archivo subido.** «Recortar» abre la foto
entera con un recuadro encima: lo de dentro es lo que se ve. Se guarda como
`crop` (x, y, ancho y alto, de 0 a 1) en la pieza, así que se puede cambiar
mañana, y `_paint()` recorta antes del ajuste que ya hacía. **El recuadro
guarda la proporción de la caja**, así que lo que se ve nunca sale deformado:
solo más cerca o más lejos. Antes no había manera: al tirar de una esquina
hasta el borde de la hoja, el ancho se recortaba y el alto no, la caja cambiaba
de proporción y la foto se veía estirada; ahora el alto sigue al ancho.

**La descripción de una foto es obligatoria** (`problems()` da `alt`): es lo que
se lee cuando el buzón bloquea las imágenes, que pasa en la mitad de los casos,
y lo único que queda de esa foto para quien usa un lector de pantalla. Una pieza
vieja con fotos sin descripción las pide la próxima vez que se guarde.

**Al subir una foto se recortan sus bordes transparentes** (`imaging.trim()`): un
logo exportado con aire alrededor ocupaba una caja más grande que lo que se ve.
Entra **debajo de lo último, a la mitad del ancho**, para poder moverla y poner
otra al lado. **Las esquinas la agrandan sin deformarla y los lados la
recortan**, así que la caja siempre abraza la foto; la proporción se guarda en
`r`. «Ancho completo» la estira a 600 con su proporción. Lleva **enlace**
opcional y **descripción**, que va en el `alt`: es lo que se lee con las imágenes
bloqueadas.

**Una foto puede tomar forma, redondear sus esquinas y llevar borde** (octubre
de 2026): `mask` (cualquier figura menos el rectángulo y la línea), `radius`
(hasta 300) y `border` con `border_color` (hasta 20 px); **las figuras también
llevan borde**, y hay ocho nuevas (rombo, pentágono, hexágono, octágono,
corazón, cruz, globo de diálogo y flecha doble, en `POLYGONS`). **Todo eso se
pinta en la imagen del grupo** con Pillow (`_shaped()`, dibujado al cuádruple y
achicado para que la orilla salga suave), así que se ve igual en Gmail, Apple
Mail y Outlook de escritorio: `border-radius` y los bordes con esquinas son lo
que Outlook no dibuja. Por eso **una figura con borde deja de ser celda de
color** y pasa a imagen. El borde va por dentro de la caja, en el correo, en el
PDF (que recorta la foto con `clipPath` y traza el borde metido la mitad de su
grosor) y en el editor, que dibuja las figuras y el borde con los mismos puntos
que el correo (`shape_points()`, en `#canvas-shapes`).

**El formato va por palabras** (22 de octubre de 2026; antes era por caja
entera, porque se temía que no llegara igual a Outlook, y sí llega: un `<span>`
con su estilo y un `<a>` con el suyo los dibujan todos). La fuente, el tamaño y
la alineación siguen siendo de la caja. **Negrita, cursiva, subrayado, color y
enlace** se ponen a lo seleccionado mientras se escribe (con la barra o con
Ctrl+B, I, U y K), y sin nada seleccionado, al texto entero.
- **El modelo**: el texto gana `runs`, tramos `{text, b, i, u, color, href}`.
  La caja (`bold`, `italic`, `color`) es la base y cada tramo dice solo en qué
  cambia; `_runs()` quita lo repetido y une los seguidos iguales, y sin ningún
  formato no se guardan. **`text` lo arma el servidor** con los tramos, así que
  las variables, el conteo de 200 caracteres, la búsqueda y la API de antes no
  cambian. Hasta 200 tramos.
- **El enlace** lleva escritos su color y su `text-decoration`: sin ellos Gmail
  lo pinta de azul y lo subraya. **El subrayado del enlace es opcional**: viene
  puesto al crearlo y se quita en su cuadro. Su dirección pasa por la misma
  regla `HREF` que la de un botón (`https://` o `mailto:`, y lo demás no se
  guarda ni como borrador), **cuenta en «más de 8 enlaces» y en los
  acortadores** (`links_of()`), y sus clics se miden como los de un botón.
- **El color de un tramo** se protege del modo oscuro como el de la caja
  (`dark_css()`).
- **El PDF** parte los renglones por palabras con su letra, pinta el subrayado
  como una raya y deja el enlace clicable (`_rich()` de `canvas_pdf.py`).
- **En el editor** la caja se escribe con `span` por tramo, se vuelve a leer al
  escribir (`readRuns()`), y dar formato parte los tramos por posición de
  letra (`formatRange()`), no con `execCommand`, que cada navegador hace a su
  modo. Pulsar la barra mientras se escribe no termina de escribir.

**Un texto puede ir con viñetas** (`list`, que solo se escribe cuando está
puesto): cada renglón es un punto, y un renglón vacío, un hueco. **Hay cuatro
tipos** (octubre de 2026): `dot` •, `check` ✓, `star` ★ y `circle` ○ (`BULLETS`);
un `true` de antes es el punto. En el PDF el punto va con la letra del texto y
los otros tres con ZapfDingbats, que sí los tiene. En el correo es
una tabla con una columna para la viñeta (su entidad, del ancho de la letra × 1.2,
`dot_px()`) y otra para el texto, una fila por renglón: `<ul>` Outlook lo dibuja
con márgenes propios. Va siempre a la izquierda, así que la alineación se
esconde. En el editor cada renglón es un bloque con su viñeta y sangría
francesa; mientras se escribe va plano con la misma sangría, así que se parte
igual. El PDF dibuja lo mismo.

**Los atajos del teclado viven detrás de un botón**, en su propia ventana
(`<dialog>`, la misma que abre `panel.js` para la bandeja de cargar) y en dos
columnas: en la columna angosta del editor no se leían. Salen de una sola lista,
`i18n.CANVAS_KEYS`.

**La vista previa también es una ventana**, y no la columna de al lado: allí se
veía dos veces lo mismo y le quitaba ancho al lienzo. Su botón dice
**«Previsualización»**, que es lo mismo que dice en las prediseñadas y en el
editor de HTML: los tres leen la misma cadena. **Solo se refresca mientras está
abierta**, y al abrirla; cerrada no se le pide nada al servidor. La barra de
peso y la revisión antispam se quedan fuera, a la vista: son las que no dejan
guardar.

### Bajarse la pieza: PDF y HTML

**Dos botones al lado de Previsualización.** Ninguno pasa por el correo de
nadie: las marcas `*|NOMBRE|*` se quedan escritas, porque lo que se baja es la
plantilla.

**El PDF baja lo que se está viendo**, por POST (`/templates/canvas/pdf`), como
la vista previa: también de una pieza que todavía no se ha guardado.

**«Descargar ZIP» baja la plantilla guardada, para pasársela a otra persona**
(`GET /templates/canvas/<id>/html`). Trae dos cosas:

- **El lienzo**: `lienzo.json`, el lienzo guardado tal cual y con su nombre, y
  sus fotos originales en `fotos/`, que el lienzo nombra por su ruta
  (`fotos/1.jpg`): el nombre de verdad es la dirección de la imagen en esta
  cuenta, y en otra no significa nada. Es lo que se vuelve a cargar y se sigue
  editando como si nada.
- **El HTML**, con sus imágenes fundidas en `imagenes/`, que el HTML nombra por
  su ruta: al abrirlo en una computadora se ve entero, y sirve fuera de
  Sobreala. En el panel ya no se carga.

El HTML es lo mismo que sale al enviar (`sender.Piece`) y va **sin nuestro pie**
(`render.email_from_body(bare=True)`): la baja, la dirección y la marca de agua
se ponen al enviar, y dentro saldrían dos veces. Hasta septiembre de 2026
llevaba las fotos dentro (`data:`) y el pie: una sola foto ya pasaba de los
102 KB, y no se podía volver a cargar. Después las llevó enlazadas al panel de
quien lo bajó, y se quitó porque la otra cuenta dependía de esa. Como las imágenes fundidas
solo existen al guardar, **sin guardar, o con cambios sin guardar, el editor no
baja nada y lo dice**. Una pieza vieja por diapositivas se rehace antes, como
antes del primer correo.

**Cargar el ZIP crea un lienzo nuevo en la cuenta que lo carga** y abre el
editor (`canvas_from_pack()`, con `imaging.unpack()`), en **todos los planes y
sin plan**, porque el lienzo es de todos. Sus fotos entran **a esa cuenta**, por
la misma revisión y el mismo achique que una foto del lienzo, **contando contra
su tope**, y solo las que el lienzo nombra. Después el lienzo pasa **exactamente
lo que pasa Guardar**, porque del JSON no se fía nada: `canvas_refused()` (las
reglas para armar el correo y la revisión antispam) y `canvas_fused()` (funde
las imágenes y mira los 102 KB), que son las mismas dos funciones que usa el
editor. Si algo falla no queda nada guardado. Queda con el nombre del
formulario o con el que trae el lienzo. **Cada cuenta es dueña de las suyas**:
si dos usan la misma foto, cada una guarda su copia (unos 120 KB), y ninguna
depende de la otra. El ZIP se lee en memoria y con topes contados en lo que
sale y no en lo que dice su índice (5 MB por foto, 20 MB entre todas y 512 KB el
lienzo), porque un ZIP pequeño puede inflarse a gigas.

**Las plantillas de muestra de la portada son ZIP de lienzo en el código**
(`backend/sample_templates/<slug>.zip`), iguales para todos.
- **Por qué en el código y no subidas desde administración:** el sitio es
  estático, y lo que enseña tiene que existir al construirlo.
- **Qué pasa al pulsar una:** `GET /templates/sample/<slug>` la carga con el
  mismo `canvas_from_pack()` de «Cargar plantilla», con la misma revisión y sus
  fotos contando contra el tope, y abre su lienzo.
  - Cada pulsación es otra copia.
  - Un nombre que no sea un ZIP de la carpeta da 404.
  - A una precarga del navegador no se le crea nada.
- **Sin sesión**, lleva a entrar recordando el nombre (`WANTED_SAMPLE`, como el
  plan) y sigue hasta ella.
- **Agregar una** es dejar su ZIP en la carpeta, su fila en `SAMPLES` y correr
  `python landing/samples.py`, que hace su miniatura. Una prueba comprueba que
  las dos listas coinciden y otra que cada una tiene su miniatura.
- **Hoy son diecisiete** (octubre de 2026), en dos grupos (`group` en
  `SAMPLES`):
  - **trece de promociones**: joyería, panadería, ventas, restaurante, hoteles,
    perfumería, reclutamiento, clínica, alquiler de autos, tecnología,
    gimnasio, construcción y bienes raíces;
  - **cuatro para la API**: factura, bienvenida, confirmación de pedido y
    estado de cuenta. Llevan las marcas que llena el sistema del comercio
    (`*|NOMBRE|*`, `*|NUMERO|*`, `*|TOTAL|*`…) y sus tablas (`*|PRODUCTOS|*`,
    `*|TRANSACCIONES|*`), cada una en un texto propio y no en lista, y un
    rectángulo «Tu logo» para cambiar por «Mi logo».
  Cada una tiene su paleta, su letra y su composición, para que no se vean
  hechas en serie. Antes hubo cuatro hechas a mano (restaurante, perfumería,
  reclutamiento y bienes raíces, cada una de su alto) y, antes, ocho de relleno.
- **Las reglas de una muestra**, además de pasar la revisión como cualquier
  lienzo:
  - **800 de alto, todas**: la miniatura es el 3:4 de arriba a 600 de ancho, y
    así enseña la plantilla entera;
  - **dos fotos como mucho**: cada foto cuenta contra el tope de quien la abre
    (20 en el Básico);
  - los enlaces van a `tunegocio.com`, nunca a un negocio real, y ninguna foto
    lleva una marca comercial a la vista.
  `test_samples.py` comprueba las dos primeras.
- **Las fotos son de Unsplash**, con su licencia (uso comercial, sin pedir
  permiso ni nombrar al autor; se nombra igual). Las dos de la joyería son del
  Cleveland Museum of Art, de dominio público.

  | Muestra | Autor | Foto |
  |---|---|---|
  | jewelry | @clevelandart | https://unsplash.com/photos/octagonal-pendant-with-large-faceted-amethyst-and-diamond-accents-FR5gYrT4dfk |
  | jewelry | @clevelandart | https://unsplash.com/photos/beaded-necklace-with-gold-and-teal-accents-vpEiDfZVoGo |
  | bakery | @picoftasty | https://unsplash.com/photos/breads-on-wicker-basket-Ehtxtp9Ykvo |
  | bakery | @isszvicky25 | https://unsplash.com/photos/a-croissant-sitting-on-top-of-a-cork-coaster-a4xoMVKzbak |
  | sales | @pilipeichenko | https://unsplash.com/photos/hand-holding-colorful-shopping-bags-against-a-white-background-mS_QzcElEAo |
  | restaurant | @focusedonyou | https://unsplash.com/photos/cooked-food-on-white-ceramic-plate-Y-CSSwcS5co |
  | restaurant | @nimanaseri | https://unsplash.com/photos/a-person-pouring-sauce-on-a-plate-of-food-AqAyU5YAAyQ |
  | hotel | @i_story_pictures | https://unsplash.com/photos/brown-wooden-lounge-chairs-near-body-of-water-during-daytime-oyxsG2Lh_uA |
  | perfume | @siora18 | https://unsplash.com/photos/glass-perfume-bottle-LkT5-JCePUY |
  | perfume | @scentspiracy | https://unsplash.com/photos/clear-glass-bottle-on-white-table-iDDGJt3veps |
  | hiring | @silverkblack | https://unsplash.com/photos/man-with-arms-crossed-in-front-of-chalkboard-E4jeiHp2QHo |
  | clinic | @silverkblack | https://unsplash.com/photos/doctor-wearing-a-stethoscope-sits-at-a-desk-JJEOuvnY1Tw |
  | car-rental | @bbestamis | https://unsplash.com/photos/white-sedan-on-gray-asphalt-road-during-daytime-73XAgT8DOpo |
  | tech | @aditya_sethia_97 | https://unsplash.com/photos/a-computer-desk-with-a-monitor-and-keyboard-GVYVTY9XOFg |
  | gym | @johnarano | https://unsplash.com/photos/woman-doing-weight-lifting-h4i9G-de7Po |
  | construction | @josholalde | https://unsplash.com/photos/construction-worker-in-hard-hat-on-building-frame-X1P1_EDNnok |
  | real-estate | @webaliser | https://unsplash.com/photos/white-and-brown-concrete-building-under-blue-sky-during-daytime-_TPTXZd9mOo |
  | real-estate | @spacejoy | https://unsplash.com/photos/a-living-room-filled-with-furniture-and-a-large-window-x3mSC1WnWhc |

**Entre cuentas nunca se copia nada.** Hubo `adopt_images()`, que al cargar un
HTML iba a buscar las imágenes de la otra cuenta y las copiaba; si esa ya las
había borrado, no había qué copiar. Una pieza HTML de las de antes que nombre
imágenes de otra cuenta sigue así, y «Imágenes de esta plantilla» las marca
como de otra cuenta, con su «Cambiar».

**Las imágenes que nombra una plantilla cargada no se borran**: `images_in()` lee
en su HTML las direcciones `/img/<nombre>` (`imaging.names_in()`), así que borrar
otra pieza de la cuenta no le rompe la cargada.

**El PDF se dibuja desde las coordenadas**, con `services/canvas_pdf.py` y
`reportlab`, el mismo que ya hace el PDF de Estadísticas. Por eso el texto sale
como texto y se puede copiar; una página de 600 puntos por el alto de la hoja.

- **El PDF solo lo tiene el lienzo**: es el único que guarda coordenadas. Una
  pieza de HTML de las de antes pediría un dibujante de HTML, que no hay.
- **Las fuentes caen a las catorce que trae todo PDF**: Arial, Verdana, Tahoma,
  Trebuchet, Century Gothic y Lucida a Helvetica; Georgia, Times, Palatino y
  Garamond a Times; Courier New a Courier. Miden distinto, así que **una línea
  puede partirse en otro sitio que en el correo**.
- **Ni el PDF ni el HTML llevan el pie de la baja ni la dirección postal**,
  que son del correo y no de la pieza.
- Las figuras usan **los mismos puntos** que el correo (`canvas.POLYGONS`), y
  las fotos honran su recorte y su giro. Una imagen de otra cuenta no se
  dibuja, como en el correo.

**Una imagen (PNG) no**: el servidor no tiene las fuentes del correo, así que
habría que pintarla en el navegador y serían tres sitios donde se dibuja lo
mismo. Para las capturas del sitio público ya están `landing/tutorials.py` y
`landing/samples.py`.

**El enlace de un botón nace vacío**, con `https://` como marca de agua y no
escrito dentro: escrito, quien pegaba una dirección acababa con
«https://https://coop.com». Al salir del campo, lo que no trae esquema se lo
lleva.

**La vista previa se ve con un contacto de verdad o con las pastillas**, y como
en una computadora o como en un teléfono (el correo achicado a 375 px, que es lo
que hace Gmail). El contacto se busca con la cuenta en la consulta: el de otra
no encuentra nada. Las dos cosas están también en el editor de HTML
(`templates/designs/_preview_tools.html`).

### Solo se envía lo que tiene pinta de llegar a la bandeja

`canvas.review()` es una revisión **que bloquea el envío**. Hasta octubre de
2026 bloqueaba también el guardado; desde el 22 de octubre, **Guardar siempre
guarda**: lo que no cumple (esta lista o las reglas de `problems()`) se guarda
como **borrador** (`designs.draft: true` y `draft_issues`, las frases de lo que
falta), sin imágenes fundidas, y el botón dice «Guardar borrador». Así se puede
dejar a medias sin inventar texto de relleno. **Un borrador no se envía por
ninguna puerta**: `sender.run()` lo frena con `blocked: draft` (la campaña
espera, no se termina, también la programada del worker), `send_one()` con
`template_draft`, el Masivo y Redactar no lo dejan elegir, y la API responde
422. Mis plantillas lo marca «Borrador», y su miniatura se arma como la vista
previa del editor. **Lo que ni un borrador guarda** (`canvas.hard_problems()`)
es seguridad o recursos: una imagen que no es de la cuenta, un enlace que no es
`https://` ni `mailto:`, la hoja o los elementos fuera de tope, una fuente o un
tamaño que no existen, y el tope de 300 plantillas. Por la API no hay
borradores: `POST` y `PATCH /templates` siguen estrictos. Mira lo que más manda
a spam:

| Regla | Límite |
|---|---|
| Texto de verdad | Al menos 200 caracteres |
| Imágenes | Como mucho el 60 % de la superficie (encimadas cuentan una vez; un rectángulo de color no cuenta) |
| Peso del correo armado | Debajo de los 102 KB, donde Gmail lo corta |
| Enlaces de botones e imágenes | Como mucho 8 |
| Acortadores (bit.ly y compañía) | Ninguno |
| Mayúsculas | Menos del 30 % de las letras |
| Signos repetidos (`!!`, `??`) | Ninguno |
| Palabras gancho («gratis», «ganaste», «haz clic aquí»…) | Ninguna |

No es una garantía: la bandeja la deciden la reputación del dominio y lo que
hace cada destinatario, no el correo. Es quitar lo que se sabe que resta.

**El texto y la imagen se aflojaron en septiembre de 2026**: eran 300
caracteres y la mitad del correo. 200 son un titular y un par de frases, y el
60 % es la proporción 60/40 de siempre, del lado permisivo; sigue sin pasar el
correo casi todo imagen, que es lo que de verdad castigan los filtros.

**«Requisitos para guardar»**, un botón junto a la barra, abre una ventana con
**todas** las reglas que deciden si se guarda, con ✓ o ✕ y sus cifras: las de
`problems()` (para armar el correo), las de `review()` (para no ir a spam) y el
nombre. La arma `canvas.checklist()` con lo que ya dijeron las dos, y
`BUILD_RULES` y `SPAM_RULES` fijan el orden; una prueba comprueba que ninguna
regla nueva se quede fuera de esa lista. La lista corta de encima del lienzo
sigue diciendo solo lo que falla.

**La misma revisión corre mientras se trabaja**, en `POST
/templates/canvas/check`, que devuelve la lista y **el peso del correo tal
como sale** —con el pie de la baja y las imágenes—. El editor lo dibuja como una
barra de cuánto queda antes de los 102 KB, en ámbar pasado el 70 % y en rojo
pasado el 90 %.

## Las plantillas prediseñadas

**Ya no se ofrecen.** Las piezas que alguien armó con ellas siguen en su lista y
se editan con el formulario de siempre (`/templates/piece/<id>`); empezar una
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
- **Borrar la pieza borra sus imágenes**, y **volver a guardarla borra las que
  la versión anterior nombraba y la nueva ya no** (una foto que se quitó del
  lienzo, una que se cambió con «Cambiar»): `drop_unused()` con
  `images_in()` de la versión vieja, que mira todas las plantillas de la
  cuenta, así una copia no pierde las suyas. Antes solo se borraban las
  fundidas, y las fotos quitadas se quedaban contando.
- **El tope lo dice el plan**, en la fila «Imágenes guardadas» de
  `docs/pricing.md` (`plans.image_limit()`): **20 · 50 · 100**, y sin plan lo
  del Básico. No se publica en Planes. Solo cuentan las fotos que sube el
  cliente, no las que funde el sistema ni las retiradas.
- **Las fotos sueltas se recogen al llegar al tope.** Una foto subida en el
  editor cuenta desde que se sube, aunque la plantilla no se guarde nunca, y
  eso dejaba el tope lleno después de borrar plantillas. Antes de decir «ya
  tienes el máximo», `photo_room()` quita las fotos de la cuenta que no nombra
  ninguna plantilla y tienen **más de un día** (`free_orphans()`, por
  `images.remove()`, así que una que salió en un envío se retira y no se
  borra). El día es para no quitarle a nadie la que acaba de subir y todavía
  no guarda.
- **Salvo las que ya salieron en un envío**: esas se quedan hasta doce meses
  después del último envío que las llevó. Ver `images`, abajo.

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

**Una imagen que salió en un envío no se borra con su pieza.** Un correo que ya
llegó pide sus imágenes cada vez que alguien lo abre, meses después, y antes se
quedaba sin ellas en tres casos: al borrar la plantilla, al volver a guardar un
lienzo (cada guardado funde imágenes nuevas y borraba las de antes, así que
corregir una coma después de enviar ya las rompía) y al rehacer una por
diapositivas. Ahora:

- **El envío anota lo que sale.** Cada tanda que manda algo escribe `sent_at`
  en las imágenes que nombra el correo armado (`images.mark_sent()`, desde
  `sender.run()`). Se leen del correo y no de la pieza, así valen las tres
  clases de pieza, y en cada tanda, porque la pieza puede cambiar a mitad.
- **Borrar pasa a retirar** (`images.remove()`, que es por donde pasan los tres
  casos): la que tiene `sent_at` no se borra, se le pone `expires_at` a **doce
  meses del último envío**, como el detalle de `events`, y la borra Mongo sola
  con su índice TTL. La que nunca salió se borra como siempre, así que guardar
  sin enviar no deja nada de más: solo se guardan las versiones que salieron.
- **Una retirada ya no es de nadie**: `owns()` y `count()` no la cuentan, así
  que no gasta del tope ni se puede poner en otra pieza, pero `/img/` la sigue
  sirviendo, porque la busca por nombre.
- **El logo de la empresa** (octubre de 2026, `kind: logo`) vive aquí también,
  pero no es de ninguna pieza: no cuenta contra el tope, la limpieza de las
  fotos sueltas no lo ve y `remove()` no lo toca. **«Mi logo», en el lienzo,
  pone una copia** (`/templates/canvas/logo`, que contesta lo mismo que subir
  una foto), así cambiar o quitar el logo en Configuración no le deja un hueco
  a ninguna plantilla guardada. La copia es una foto más y cuenta contra el
  tope. El botón sale solo si la empresa tiene logo.
- **Si un HTML cargado la vuelve a nombrar, deja de estar retirada**
  (`images.keep()` al cargar y al guardar un HTML): si no, esa pieza la
  perdería el día que venciera.

## Las listas en un correo (octubre de 2026)

`fields.fill()` llena una lista de un contacto (`docs/contactos.md`) o de los
datos de un correo de la API, **en una sola pasada**: lo que se pone nunca se
vuelve a leer, así una descripción que diga `*|CORREO|*` sale tal cual.

- `*|TRANSACCIONES|*` sola arma **una tabla**: el nombre de cada dato arriba y
  una fila por elemento, cada valor escrito como en una columna y escapado, los
  números a la derecha. En el asunto, una lista no escribe nada.
- `*|#TRANSACCIONES|* … *|/TRANSACCIONES|*` se repite por cada fila, con las
  marcas de la fila (y las del contacto) dentro; `*|^TRANSACCIONES|* …
  *|/TRANSACCIONES|*` sale cuando está vacía. Un bloque dentro de otro no se
  repite.
- La vista previa dibuja la tabla con dos filas de pastillas.
- `fields.marks_in()` dice qué marcas y qué bloques nombra un texto, y
  `fields.lacking()` cuáles no tienen con qué llenarse (lo usa la API: un correo
  con una marca vacía no sale).

## Las funciones del lienzo, en `services/pieces.py` (octubre de 2026)

Revisar, fundir, cargar y bajar el ZIP, subir una foto y armar el correo de un
lienzo se mudaron de `blueprints/designs/routes.py` a `services/pieces.py`, que
recibe la cuenta a mano y no mira la sesión ni `g`: lo usan el editor y la API.
La cabecera de correo de la vista previa la sigue poniendo la ruta del panel.
