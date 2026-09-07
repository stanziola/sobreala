# Sitio público de Panamails

Cuatro páginas estáticas que presentan Panamails. Se despliegan tal cual en
Cloudflare Pages, sin build remoto: esta carpeta es la raíz del sitio.

| Ruta              | Archivo                    |
|-------------------|----------------------------|
| `/`               | `index.html`               |
| `/como-funciona/` | `como-funciona/index.html` |
| `/precios/`       | `precios/index.html`       |
| `/nosotros/`      | `nosotros/index.html`      |

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
│   ├── partials/        # cta-band, faq, feature-icons, iconos de correo y chat
│   ├── pages/           # index, como-funciona, precios, nosotros
│   └── site.css         # estilos (sin ningún HEX: usa las variables de brand/colors.css)
├── assets/
│   ├── js/nav.js        # menú móvil accesible + año del pie
│   ├── css/site.css     # GENERADO: colors.css + @font-face + src/site.css
│   ├── fonts/           # GENERADO: .woff2 a partir de brand/fonts/
│   └── img/             # GENERADO: logo, favicons e iconos desde brand/
├── index.html           # GENERADO
├── como-funciona/       # GENERADO
├── precios/             # GENERADO
├── nosotros/            # GENERADO
├── favicon.ico, favicon.svg, robots.txt, sitemap.xml   # GENERADOS
└── README.md
```

De dónde sale cada cosa:

| Qué                         | Fuente de verdad                | Se edita en |
|-----------------------------|---------------------------------|-------------|
| Textos, enlaces, FAQ, contacto | `landing/content.py`         | ese archivo |
| Planes, límites y precios   | `docs/pricing.md`               | ese archivo; el build lee sus tablas |
| Colores                     | `brand/colors.css`              | ese archivo |
| Tipografías                 | `brand/fonts/`                  | ver `brand/fonts/README.md` |
| Logo y favicons             | `brand/logo/`, `brand/favicon/` | `python brand/build_logo.py` |
| Iconos de redes             | `brand/social/`                 | a mano, ver su README |
| Logos de métodos de pago    | `brand/payments/`               | a mano, ver su README |
| Estructura y estilos        | `landing/src/`                  | esos archivos |

Después de cambiar cualquiera de ellos, regenerar y commitear también lo generado.

## Precios sin duplicar

`build_site.py` parsea las tablas `## Planes` y `### Complementos` de
`docs/pricing.md`. Solo publica las filas listadas en `PUBLIC_ROWS`; costos,
márgenes, competidores y prospectos nunca salen del documento. Corporativo se
publica sin precio, como indica el propio archivo. Si cambia un precio, basta con
cambiarlo en `pricing.md` y regenerar.

## Qué es solo visual

Los iconos del pie son PNG en negro sobre fondo transparente que el CSS pinta con
`currentColor`, así que salen blancos sobre el azul del pie y podrían ser de
cualquier color en otro fondo. El build los recorta a cuadrado antes de copiarlos,
para que ninguno salga deformado.

La franja de pagos del pie muestra los logos de `brand/payments/`. Si esa carpeta
está vacía, muestra una línea de texto en su lugar.

Los botones "Hablemos por WhatsApp" abren un chat con mensaje prellenado y
"Escribir por correo" abre el correo. No hay registro, login, panel ni pagos:
todo eso es de etapas futuras. Los enlaces legales del pie están marcados como
próximamente hasta que existan los textos.

## Comprobar

El build no valida el resultado; para eso sirve abrirlo con `--serve` y
revisarlo en el navegador. Cosas a mirar tras un cambio de estilos: que no haya
scroll horizontal en móvil, que el menú móvil abra y cierre (botón, Escape y clic
fuera), y que cada página marque su enlace activo en el header.

Requisitos: `pip install jinja2 fonttools brotli`.
