# Marca Sobreala

Activos de marca: logo vectorial, favicons, foto de perfil para redes, paleta
de colores y posición.

```
brand/
├── colors.css                  # fuente de verdad de los COLORES (tema claro)
├── colors-dark.css             # los mismos nombres, valores del tema oscuro
├── layout.json                 # fuente de verdad de la POSICIÓN y el encuadre
├── build_logo.py               # genera todo lo de logo/, favicon/, perfil/ y preview/
├── logo/
│   ├── logo.svg                # composición completa: fondo + ala (viewBox 271×254)
│   ├── logo-transparent.svg    # solo el símbolo, fondo transparente (viewBox 207×123)
│   ├── logo.png                # composición completa, 1084×1016 px
│   └── reference/
│       └── logo-original.png   # PNG original (271×254), referencia visual maestra
├── favicon/
│   ├── favicon.svg             # esquinas redondeadas
│   ├── favicon.ico             # 16 + 32 + 48 px
│   ├── favicon-16x16.png
│   ├── favicon-32x32.png
│   └── favicon-180x180.png     # apple-touch-icon (cuadrado, ver abajo)
├── perfil/
│   └── perfil-1080.png         # foto de perfil para redes, 1080×1080 (ver abajo)
├── preview/
│   └── colores.html            # editor de colores y posición, en vivo
└── social/                     # iconos de redes (Instagram, etc.), se agregan a mano
    └── README.md               # convención de nombres y formato
```

Todo lo de `logo/`, `favicon/`, `perfil/` y `preview/` (salvo `reference/`) es
**generado**:
no se edita a mano, se regenera. `social/` es lo contrario: ahí van los iconos
de redes sociales, que son marcas de terceros y se agregan a mano siguiendo la
convención de `social/README.md`.

## Decidir colores y posición

```
python brand/build_logo.py --serve
```

Abre el editor en el navegador. Muestra el logo sobre un **eje de referencia**
con cuadrícula y ejes centrales, los favicons a tamaño real y la foto de perfil
recortada como la recortan las redes. Puedes:

- mover el ala en X e Y con campos, deslizadores o las flechas del teclado
  (Shift para pasos de 5), con botones de **Centrar** y **Como el original**.
  El mismo desplazamiento se aplica en el logo y en el favicon
- cambiar los tres colores, con azules de atajo
- ajustar la foto de perfil en un círculo grande: arrastrar el ala (o moverla
  con las flechas, con el círculo seleccionado), elegir su tamaño
  (`avatar_fill`) y verla a 110, 56 y 32 px, con la zona segura marcada y un
  aviso si el ala se sale de ella. **Su posición es solo suya**
  (`avatar_offset`): no mueve el logo ni el favicon
- ver los márgenes resultantes y un aviso si el logo se sale del lienzo
- pulsar **Guardar y regenerar**: escribe `colors.css` y `layout.json` y vuelve
  a generar SVG, PNG e ICO al momento

Nada se guarda hasta que pulses el botón. El servidor solo escucha en
`127.0.0.1`, es una herramienta de desarrollo y no forma parte de nada que se
despliegue. Se para con Ctrl+C.

También puedes abrir `brand/preview/colores.html` directamente como archivo, o
servirlo con cualquier otro servidor (Live Server de VS Code, por ejemplo): se
previsualiza igual, pero sin botón de guardar, porque ese servidor no sabe
regenerar nada. En su lugar te da el comando exacto para aplicar lo que
elegiste, por ejemplo:

```
python brand/build_logo.py --background "#2E5F8A" --x 4 --y -2
```

Por cualquiera de las dos vías, los valores acaban en `colors.css` y
`layout.json` y los archivos se regeneran, así que la configuración nunca se
desincroniza de los assets.

## Comandos

```
python brand/build_logo.py                      # regenerar con la config actual
python brand/build_logo.py --serve              # editor con botón Guardar
python brand/build_logo.py --serve --port 9000  # otro puerto (por defecto 8765)
python brand/build_logo.py --show               # ver la config actual
python brand/build_logo.py --help

# colores
--background HEX   --logo HEX   --shadow HEX

# posición del ala, en unidades de lienzo desde el centro; vale igual para el
# logo y para el favicon
--x N              # + hacia la derecha
--y N              # + hacia abajo
--center           # [0, 0]: centrada en los dos
--original         # exactamente donde está en el PNG de referencia

# encuadre del favicon
--favicon-fill F   --favicon-radius F   # tamaño del ala y radio de las esquinas

# la foto de perfil: tamaño del ala y su posición, que es solo suya
--avatar-fill F    --avatar-x N    --avatar-y N
```

Los valores inválidos se rechazan **antes** de escribir nada, así que un error
de tecleo no deja la configuración rota.

Requisitos: `pip install numpy pillow`.

## Colores

Definidos una sola vez en `colors.css` como variables CSS:

| Variable             | Uso                                              |
|----------------------|--------------------------------------------------|
| `--color-background` | Fondo del logo y color primario de la marca      |
| `--color-logo`       | Formas blancas del ala                           |
| `--color-shadow`     | Separaciones/sombras entre las plumas            |

En el landing y en los paneles, importar `colors.css` y usar las variables
(`var(--color-background)`, etc.) en lugar de escribir los HEX. Los códigos HEX
no están repetidos a mano en ningún otro archivo del repositorio.

`colors-dark.css` repite esos mismos nombres con los valores del tema oscuro,
dentro de `:root[data-theme="dark"]`. **Va aparte a propósito**: `build_logo.py`
solo lee `colors.css` y se queda con el último valor de cada nombre, así que una
definición oscura en ese archivo acabaría dentro del logo generado.

## Posición

`layout.json` guarda cinco valores, todos de encuadre:

| Clave                   | Qué controla                                                            |
|-------------------------|-------------------------------------------------------------------------|
| `offset`                | `[x, y]` del ala desde el centro; el mismo valor en el logo y el favicon |
| `favicon_fill`          | Proporción del lado del icono que ocupa el ancho del ala                 |
| `favicon_corner_radius` | Radio de las esquinas del favicon, como fracción del lado                |
| `avatar_fill`           | Proporción del lado de la foto de perfil que ocupa el ancho del ala      |
| `avatar_offset`         | `[x, y]` del ala en la foto de perfil, aparte de `offset`                |

El sistema de coordenadas es el del SVG: X hacia la derecha, Y hacia abajo, en
unidades del lienzo de 271×254. El favicon usa las mismas unidades, así que el
ala se mueve lo mismo en los dos.

`offset` en `[0, 0]` centra el ala en el logo y en el favicon. En
`[-9.47, -15.48]` queda **exactamente** donde está en el PNG original, que es
lo que aplica `--original`.

`logo-transparent.svg` no se ve afectado por `offset`: va recortado al ras del
ala, así que moverla dentro de un lienzo que no existe no significaría nada.

## Cómo está construido el logo

El ala es **un solo trazado cerrado** (16 nodos: 1 recta + 15 cúbicas) dibujado
dos veces:

1. En `--color-shadow`, desplazado 15.7 unidades a la izquierda y 3.85 hacia
   arriba (`transform="translate(-15.7 -3.85)"`).
2. Encima, en `--color-logo`, sin desplazar.

Las franjas negras que separan las cuatro plumas y la línea del borde superior
son las partes de la copia desplazada que el ala blanca no tapa. Esa es la
relación de capas del original y por eso las separaciones tienen su forma,
grosor y posición exactos.

Única licencia sobre el original: la copia de sombra lleva el borde superior
recto empujado 1.34 unidades hacia afuera (`SHADOW_TOP_LIFT` en
`build_logo.py`), con lo que la línea negra de arriba pasa de ~1.9 a 3.25
unidades de grosor. Ponerlo en `0` devuelve la geometría exacta del PNG.

## Uso en la web

Logo:

```html
<img src="/assets/img/logo.svg" alt="Sobreala" width="271" height="254">
```

También se puede pegar el contenido de `logo.svg` inline si hace falta
manipularlo con CSS o JS.

Favicons, en el `<head>`, con los archivos copiados a la raíz del sitio:

```html
<link rel="icon" href="/favicon.ico" sizes="32x32">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="icon" href="/favicon-32x32.png" type="image/png" sizes="32x32">
<link rel="icon" href="/favicon-16x16.png" type="image/png" sizes="16x16">
<link rel="apple-touch-icon" href="/favicon-180x180.png" sizes="180x180">
```

`landing/` se despliega solo, así que los archivos que use el landing deben
copiarse dentro de `landing/` (por ejemplo `landing/favicon.ico`,
`landing/favicon.svg`, `landing/assets/img/logo.svg`) en el paso de build o a
mano tras regenerar.

## Detalles del favicon

- **Esquinas redondeadas**: radio del 20% del lado. Poner
  `favicon_corner_radius` en `0` para dejarlo cuadrado.
- **Área de seguridad**: el ala ocupa el 84% del ancho (`favicon_fill`), el
  resto es margen para que no roce las esquinas redondeadas. Si subes el
  relleno o el radio de más, el build avisa de que el icono recorta el ala.
- **El de 180 px va cuadrado y opaco** a propósito: es el `apple-touch-icon` e
  iOS le aplica su propio redondeo, así que unas esquinas transparentes saldrían
  negras en la pantalla de inicio. Se controla con `APPLE_TOUCH_ROUNDED` en
  `build_logo.py`.
- **Tamaños pequeños**: a 16 px las separaciones negras medirían ~0.35 px y
  desaparecerían, así que solo en los rasterizados pequeños se amplía el
  desplazamiento de la sombra: ×2 a 16 px, ×1.5 a 32 px, ×1.25 a 48 px, y ×1.5
  en `favicon.svg` (los navegadores lo muestran a 16–32 px). La silueta no
  cambia. Para usar la geometría exacta en todos los tamaños, poner esos
  factores a `1.0` (`FAVICON_SHADOW_SCALE` y `FAVICON_SVG_SHADOW_SCALE`).

## La foto de perfil

`perfil/perfil-1080.png` es la que se sube a Instagram, Facebook, WhatsApp,
LinkedIn, X, TikTok y YouTube. **Es la misma para todas**:

- **1080×1080 y cuadrada.** Es lo que todas guardan tal cual, sin recortarla
  ni rehacerla. Si se sube otra proporción, cada una corta por su lado.
- **El ala sola, sobre el azul**, con los colores del favicon. Sin la palabra:
  al tamaño al que se ve una foto de perfil no se leería.
- **Opaca y sin esquinas redondeadas.** Cada red pone su propia máscara (un
  círculo casi en todas, un cuadrado en LinkedIn), y una esquina transparente
  sale negra o blanca según la aplicación.
- **Se ajusta en el editor** (`--serve`), en el panel «Foto de perfil para
  redes»: un círculo grande donde se arrastra el ala, con su tamaño
  (`avatar_fill`) y **su propia posición** (`avatar_offset`). Hasta octubre de
  2026 la posición era la del logo y el favicon; se separó para poder
  centrarla en el círculo sin moverlos a ellos.
- **El ala ocupa el 60 % del ancho** y llega al 73 % del radio del círculo con
  el que la recortan, así que queda dentro con aire. Si el ala pasa del 80 % del
  radio (`AVATAR_SAFE` en `build_logo.py`), por tamaño o por posición, el build
  avisa.
