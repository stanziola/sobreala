# Iconos de redes sociales

Kits de marca oficiales de cada red, tal como se descargan de su página de
recursos. Se guardan completos, en una carpeta por red, y **no se editan**.

```
social/
├── instagram/     # kit oficial: glifo en degradado, blanco y negro
├── whatsapp/      # kit oficial: glifo, inline y apilado, en verde, blanco y negro
└── README.md
```

**Se agregan a mano.** Son marcas de terceros: no las genera ningún script ni
dependen de `colors.css`.

## Qué variante usa el sitio

Lo decide una sola tabla, `SOCIAL_ICONS` en `landing/build_site.py`, que apunta
al archivo exacto dentro de cada kit. Hoy: el **glifo blanco en SVG** de cada red.
Para cambiar de variante, cambia esa ruta y ejecuta `python landing/build_site.py`.

En el sitio, el archivo se usa como **máscara**: su transparencia define la forma
y el color lo pone el CSS con `currentColor`. Por eso da igual que el glifo sea
blanco o negro; lo que importa es que tenga fondo transparente.

## Para agregar otra red

1. Descarga su kit oficial y déjalo en `social/<red>/`.
2. Agrega la entrada en `SOCIAL_ICONS` apuntando al SVG (o PNG con fondo
   transparente) que quieras usar.
3. Añade el enlace en `landing/content.py` y en el pie de `landing/src/base.html.j2`.

Los PNG se recortan a su contenido y se dejan cuadrados al generar el sitio, así
que ningún icono sale deformado aunque el archivo venga en un lienzo ancho.

Igual que el logo y los favicons, `landing/` se despliega solo: los iconos que
usa el sitio se copian a `landing/assets/img/social/` al generar.
