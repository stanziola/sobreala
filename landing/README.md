# Sitio público de Sobreala

Una sola página que presenta Sobreala (Inicio, la API y el lienzo, Planes,
Funciones, Plantillas y las preguntas; Contacto es el pie), más las dos
legales. Se despliegan tal cual
en Cloudflare Pages, sin build remoto: esta carpeta es la raíz del sitio.

| Ruta | Archivo |
|------|---------|
| `/` | `index.html`, la página única |
| `/privacy/`, `/terms/` | `privacy/index.html`, `terms/index.html` |
| `/pricing/`, `/how-it-works/`, `/about/`, `/contact/` | páginas de paso que llevan a su sección (`#planes`, `#funciones`, `#inicio`, `#contacto`) |

El detalle de cómo está armada está en `docs/sitio.md`.

## Cómo se genera

```
python landing/build_site.py            # regenerar
python landing/build_site.py --serve    # regenerar y abrirlo en http://127.0.0.1:8080/
```

Mismo patrón que `brand/build_logo.py`: fuentes de verdad → generador →
archivos generados que no se editan a mano.

```
landing/
├── build_site.py        # el generador
├── content.py           # TODOS los textos, en español
├── src/
│   ├── base.html.j2     # <head>, header, footer, SEO
│   ├── partials/        # cta-band, faq, feature-icons, los dibujos de Features
│   │                    # (feature-*.svg.j2), iconos de correo y chat
│   ├── pages/           # index (la página única) y legal
│   ├── sections/        # destacadas (API y lienzo), planes, funciones y
│   │                    # plantillas: partes de index
│   ├── redirect.html.j2 # las páginas de paso de las direcciones viejas
│   └── site.css         # estilos (sin ningún HEX: usa las variables de brand/colors.css)
├── assets/
│   ├── js/nav.js        # menú móvil, cambio de tema y año del pie
│   ├── js/carousel.js   # las flechas y el paso automático del carrusel
│   ├── img/samples/     # GENERADO por samples.py: las miniaturas de las plantillas de muestra
│   ├── css/site.css     # GENERADO: colors.css + colors-dark.css + @font-face + src/site.css
│   ├── fonts/           # GENERADO: .woff2 a partir de brand/fonts/
│   └── img/             # GENERADO: logo, favicons e iconos desde brand/
├── index.html           # GENERADO: la página única
├── privacy/, terms/     # GENERADO: las legales
├── pricing/, how-it-works/, about/, contact/   # GENERADO: páginas de paso
├── favicon.ico, favicon.svg, robots.txt, sitemap.xml   # GENERADOS
└── README.md
```

De dónde sale cada cosa:

| Qué                         | Fuente de verdad                | Se edita en |
|-----------------------------|---------------------------------|-------------|
| Textos, enlaces, FAQ, contacto | `landing/content.py`         | ese archivo |
| Planes, límites y precios   | `docs/pricing.md`               | ese archivo; el build lee sus tablas |
| Colores, tema claro         | `brand/colors.css`              | ese archivo |
| Colores, tema oscuro        | `brand/colors-dark.css`         | ese archivo |
| Tipografías                 | `brand/fonts/`                  | ver `brand/fonts/README.md` |
| Logo y favicons             | `brand/logo/`, `brand/favicon/` | `python brand/build_logo.py` |
| Iconos de redes             | `brand/social/`                 | a mano, ver su README |
| Estructura y estilos        | `landing/src/`                  | esos archivos |
| Fotos de los usos           | `landing/assets/img/usos/`      | a mano, ver `docs/sitio.md` |
| Miniaturas de las muestras  | `backend/sample_templates/`     | `python landing/samples.py` |

Después de cambiar cualquiera de ellos, regenerar y commitear también lo generado.

## Features y los usos

Features (en la página, «Funciones») son nueve dibujos sencillos en SVG (`src/partials/feature-*.svg.j2`),
dentro de la página y pintados con las variables del tema; las palabras que
llevan están en `content.py`. Hasta octubre de 2026 eran capturas del panel que
hacía `shots.py`, y se quitaron. Las fotos de los usos se agregan a mano, en
WebP de 1280 × 800; quién hizo cada una y con qué licencia está en
`docs/sitio.md`.

## Precios sin duplicar

`build_site.py` parsea las tablas `## Planes` y `### Complementos` de
`docs/pricing.md`. Solo publica las filas listadas en `PUBLIC_ROWS`; costos,
márgenes, competidores y prospectos nunca salen del documento. Corporativo se
publica sin precio, como indica el propio archivo. Si cambia un precio, basta con
cambiarlo en `pricing.md` y regenerar.

## Modo oscuro

Arranca según la preferencia del sistema del visitante. El botón de la cabecera
la anula y esa elección se guarda en su navegador, así que se mantiene al navegar
y al volver. El icono muestra la acción, no el estado: un sol cuando está oscuro,
una luna cuando está claro.

Un script mínimo en el `<head>`, antes de la hoja de estilos, aplica el tema
antes del primer pintado. Sin él, quien tenga el sistema en oscuro vería un
destello blanco en cada carga.

Al pulsar, el tema nuevo se expande en círculo desde el botón. Si el navegador no
soporta esa API, o si el visitante pidió reducir animaciones, el cambio es
instantáneo.

**Los colores del tema oscuro viven en `brand/colors-dark.css`, nunca en
`colors.css`.** El generador del logo lee ese segundo archivo y se queda con el
último valor de cada variable, así que una definición oscura ahí acabaría
metida en el logo y los favicons.

Tres variables existen precisamente porque los temas las separan:

| Variable | Para qué |
|---|---|
| `--color-page` | Fondo de la página. En oscuro las tarjetas son un tono por encima |
| `--color-on-dark` | Texto sobre el azul: cabecera, hero, pie. Siempre casi blanco |
| `--color-on-accent` | Texto sobre el celeste de los botones. Siempre oscuro |

## Qué es solo visual

Los iconos del pie son PNG en negro sobre fondo transparente que el CSS pinta con
`currentColor`, así que salen blancos sobre el azul del pie y podrían ser de
cualquier color en otro fondo. El build los recorta a cuadrado antes de copiarlos,
para que ninguno salga deformado.

Los botones "Hablemos por WhatsApp" abren un chat con mensaje prellenado y
"Escribir por correo" abre el correo. No hay registro, login, panel ni pagos:
todo eso es de etapas futuras. Los enlaces legales del pie están marcados como
próximamente hasta que existan los textos.

## Comprobar

El build no valida el resultado; para eso sirve abrirlo con `--serve` y
revisarlo en el navegador. Cosas a mirar tras un cambio de estilos: que no haya
scroll horizontal en móvil, que el menú móvil abra y cierre (botón, Escape y clic
fuera), que cada página marque su enlace activo en el header, y que **todo se
revise en los dos temas**, no solo en el que tengas puesto.

Requisitos: `pip install jinja2 fonttools brotli`.
