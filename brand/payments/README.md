# Logos de métodos de pago

Kits de marca oficiales de cada proveedor de pago, tal como se descargan de su
página de recursos. Se guardan completos, en una carpeta por marca, y **no se
editan**.

```
payments/
├── paypal/        # kit oficial: horizontal y vertical, a color, negro y blanco
├── yappy/         # kit oficial: apaisado y vertical, a color y "traslucid" (blanca)
├── visa/          # Visa Brand Mark digital 2025: azul, negro y blanco
├── mastercard/    # el símbolo de Mastercard, a color
└── README.md
```

**Se agregan a mano.** Son marcas de terceros: no las genera ningún script ni
dependen de `colors.css`, y se muestran tal cual, sin recolorear.

## Qué variante usa el sitio

Lo decide `PAYMENT_LOGOS` en `landing/build_site.py`, que apunta al archivo
exacto dentro de cada kit. Hoy: **las versiones a color** (Yappy apaisado,
PayPal horizontal, Visa azul y el símbolo de Mastercard), directo sobre el azul
del pie, que es lo que se decidió aunque PayPal, Visa y Yappy tengan poco
contraste ahí. El panel usa los mismos cuatro en la pantalla de pago: los copia
`backend/build_assets.py` (`PAYMENT_LOGOS` de ese archivo). Para cambiar de
variante, cambia la ruta y ejecuta los dos generadores.

**El margen de respeto se recorta en las copias**, no en el kit: los SVG de Visa
y Mastercard traen su espacio libre dentro del archivo, y a 22 o 28 px de alto
el dibujo quedaba diminuto. El viewBox justo alrededor del dibujo vive en
`viewbox.json`, y lo aplican los dos generadores al copiar.

Los PNG se recortan a su contenido y se reducen a 112 px de alto al generar el
sitio (se muestran a 28 px), para no servir archivos de tamaño de imprenta.

## Si falta un archivo

El generador avisa y el pie muestra una línea de texto con los medios de pago en
vez de los logos, así que el sitio nunca queda a medias.

## Para agregar otro medio de pago

1. Descarga su kit oficial y déjalo en `payments/<marca>/`.
2. Agrega la entrada en `PAYMENT_LOGOS` apuntando a la versión a color.
3. Regenera. El pie los muestra en el orden de esa tabla.
