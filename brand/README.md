# Marca Panamails

Activos de marca: logo vectorial, favicons, paleta de colores y posición.

```
brand/
├── colors.css                  # fuente de verdad de los COLORES
├── layout.json                 # fuente de verdad de la POSICIÓN y el encuadre
├── build_logo.py               # genera todo lo de logo/, favicon/ y preview/
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
└── preview/
    └── colores.html            # editor de colores y posición, en vivo
```

Todo lo de `logo/`, `favicon/` y `preview/` (salvo `reference/`) es **generado**:
no se edita a mano, se regenera.

## Decidir colores y posición

```
python brand/build_logo.py --serve
```

Abre el editor en el navegador. Muestra el logo sobre un **eje de referencia**
con cuadrícula y ejes centrales, y los favicons a tamaño real. Puedes:

- mover el ala en X e Y con campos, deslizadores o las flechas del teclado
  (Shift para pasos de 5), con botones de **Centrar** y **Como el original**.
  El mismo desplazamiento se aplica en el logo y en el favicon
- cambiar los tres colores, con azules de atajo
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

## Posición

`layout.json` guarda tres valores, todos de encuadre:

| Clave                   | Qué controla                                                            |
|-------------------------|-------------------------------------------------------------------------|
| `offset`                | `[x, y]` del ala desde el centro; el mismo valor en el logo y el favicon |
| `favicon_fill`          | Proporción del lado del icono que ocupa el ancho del ala                 |
| `favicon_corner_radius` | Radio de las esquinas del favicon, como fracción del lado                |

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
<img src="/assets/img/logo.svg" alt="Panamails" width="271" height="254">
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
