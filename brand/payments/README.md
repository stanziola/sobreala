# Logos de métodos de pago

Kits de marca oficiales de cada proveedor de pago, tal como se descargan de su
página de recursos. Se guardan completos, en una carpeta por marca, y **no se
editan**.

```
payments/
├── paypal/        # kit oficial: horizontal y vertical, a color, negro y blanco
├── yappy/         # kit oficial: apaisado y vertical, versión "traslucid" (blanca)
└── README.md
```

**Se agregan a mano.** Son marcas de terceros: no las genera ningún script ni
dependen de `colors.css`, y se muestran tal cual, sin recolorear.

## Qué variante usa el sitio

Lo decide `PAYMENT_LOGOS` en `landing/build_site.py`, que apunta al archivo
exacto dentro de cada kit. Hoy: las **versiones blancas horizontales**, que son
las que se leen sobre el azul oscuro del pie. Para cambiar a color, cambia esa
ruta y ejecuta `python landing/build_site.py`.

Los PNG se recortan a su contenido y se reducen a 112 px de alto al generar el
sitio (se muestran a 28 px), para no servir archivos de tamaño de imprenta.

## Si falta un archivo

El generador avisa y el pie muestra una línea de texto con los medios de pago en
vez de los logos, así que el sitio nunca queda a medias.

## Para agregar otro medio de pago

1. Descarga su kit oficial y déjalo en `payments/<marca>/`.
2. Agrega la entrada en `PAYMENT_LOGOS` apuntando a la versión blanca horizontal.
3. Regenera. El pie los muestra en el orden de esa tabla.
