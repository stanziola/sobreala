# Marca Panamails

Activos de marca: logo vectorial, favicons y paleta de colores.

```
brand/
├── colors.css                  # ÚNICA fuente de verdad de los colores
├── build_logo.py               # genera todo lo de logo/ y favicon/
├── logo/
│   ├── logo.svg                # composición completa: fondo azul + ala (viewBox 271×254)
│   ├── logo-transparent.svg    # solo el símbolo, fondo transparente (viewBox 207×123)
│   ├── logo.png                # composición completa, 1084×1016 px
│   └── reference/
│       └── logo-original.png   # PNG original (271×254), referencia visual maestra
└── favicon/
    ├── favicon.svg
    ├── favicon.ico             # 16 + 32 + 48 px
    ├── favicon-16x16.png
    ├── favicon-32x32.png
    └── favicon-180x180.png     # apple-touch-icon
```

Los archivos de `logo/` y `favicon/` (salvo `reference/`) son **generados**: no
se editan a mano, se regeneran.

## Colores

Definidos una sola vez en `colors.css` como variables CSS:

| Variable             | Valor     | Uso                                              |
|----------------------|-----------|--------------------------------------------------|
| `--color-background` | `#3C71A3` | Fondo azul del logo y color primario de la marca |
| `--color-logo`       | `#EFEEEC` | Formas blancas del ala                           |
| `--color-shadow`     | `#000000` | Separaciones/sombras negras entre las plumas     |

Para cambiar un color:

1. Editar el valor en `brand/colors.css`.
2. Regenerar los activos:

   ```
   pip install numpy pillow
   python brand/build_logo.py
   ```

`build_logo.py` lee `colors.css` y vuelve a escribir los SVG, el PNG y los
favicons con los nuevos valores. Los códigos HEX no están repetidos a mano en
ningún otro archivo del repositorio.

En el landing y en los paneles, importar `colors.css` y usar las variables
(`var(--color-background)`, etc.) en lugar de escribir los HEX.

## Cómo está construido el logo

El ala es **un solo trazado cerrado** (15 nodos: 1 recta + 14 cúbicas) dibujado
dos veces:

1. En `--color-shadow`, desplazado 15.7 unidades a la izquierda y 3.85 hacia
   arriba (`transform="translate(-15.7 -3.85)"`).
2. Encima, en `--color-logo`, sin desplazar.

Las franjas negras que separan las cuatro plumas y la línea fina del borde
superior son las partes de la copia desplazada que el ala blanca no tapa. Esa
es la relación de capas del original y por eso las separaciones tienen su forma,
grosor y posición exactos.

## Uso en la web

Logo:

```html
<!-- como imagen -->
<img src="/assets/img/logo.svg" alt="Panamails" width="271" height="254">

<!-- inline, si hace falta manipularlo con CSS/JS: pegar el contenido de logo.svg -->
```

Favicons (en el `<head>`, con los archivos copiados a la raíz del sitio):

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

## Tamaños pequeños

A 16 px las separaciones negras miden ~0.35 px y desaparecen. Por eso, solo en
los rasterizados pequeños, el generador amplía el desplazamiento de la sombra:
×2 a 16 px, ×1.5 a 32 px, ×1.25 a 48 px, y ×1.5 en `favicon.svg` (los navegadores
lo muestran a 16–32 px). La silueta no cambia. Para usar la geometría exacta en
todos los tamaños, poner esos factores a `1.0` en `build_logo.py`
(`FAVICON_SHADOW_SCALE` y `FAVICON_SVG_SHADOW_SCALE`).
