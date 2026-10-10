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

## Quién los usa

**Solo el panel, en la pantalla de pago.** Los copia `backend/build_assets.py`,
y su `PAYMENT_LOGOS` apunta al archivo exacto dentro de cada kit. Hoy: **las
versiones a color** (Yappy apaisado, PayPal horizontal, Visa azul y el símbolo
de Mastercard). Para cambiar de variante, cambia la ruta y ejecuta ese
generador.

El sitio público los llevó en una franja del pie hasta octubre de 2026, y se
quitaron: de noche el final de la página se leía negro, azul y negro otra vez,
y de los cuatro medios solo cobraba PayPal (ver `docs/sitio.md`).

**El margen de respeto se recorta en las copias**, no en el kit: los SVG de Visa
y Mastercard traen su espacio libre dentro del archivo, y a 22 px de alto el
dibujo quedaba diminuto. El viewBox justo alrededor del dibujo vive en
`viewbox.json`, y lo aplica el generador al copiar.

El PNG de PayPal se recorta a su contenido y se reduce a 88 px de alto, cuatro
veces el que se dibuja, para no servir un archivo de tamaño de imprenta.

## Si falta un archivo

El generador lo salta sin error, pero la pantalla de pago lo sigue pidiendo
(`PAY_LOGOS` en `backend/blueprints/auth/routes.py`): en vez del dibujo sale su
nombre, el texto alternativo.

## Para agregar otro medio de pago

1. Descarga su kit oficial y déjalo en `payments/<marca>/`.
2. Agrega la entrada en `PAYMENT_LOGOS` de `backend/build_assets.py`,
   apuntando a la versión a color.
3. Agrega el archivo a su método en `PAY_LOGOS`
   (`backend/blueprints/auth/routes.py`), con su nombre bien escrito.
4. Regenera con `python backend/build_assets.py`.
