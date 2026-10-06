# Tipografías

Las dos familias del sitio, servidas desde el propio dominio. No se cargan desde
Google Fonts ni desde ningún tercero.

```
fonts/
├── changa-one/ChangaOne-Regular.ttf   # wordmark "Sobreala"
├── changa-one/OFL.txt
├── sora/Sora-VariableFont_wght.ttf    # todo lo demás (variable, todos los pesos)
└── sora/OFL.txt
```

| Familia | Dónde se usa |
|---|---|
| **Changa One** | Solo la palabra "Sobreala": header, footer y la marca escrita |
| **Sora** | Todo lo demás: títulos, cuerpo, botones, navegación, tarjetas |

## Convención

- Una carpeta por familia. Las dos licencias se llaman `OFL.txt`, así que juntas
  en la misma carpeta se pisarían.
- **La licencia se conserva siempre.** Ambas son SIL Open Font License: se pueden
  usar en un sitio comercial y alojar en el propio servidor, a condición de
  distribuir el texto de la licencia junto a la fuente.
- Se admite `.ttf`, `.otf` y `.woff2`. `landing/build_site.py` convierte a
  `.woff2` al generar el sitio, así que no hace falta convertir a mano.
- Si una familia es variable, un solo archivo cubre todos los grosores y no se
  necesita la carpeta `static` de la descarga.

## Cambiar una fuente

Deja el archivo nuevo en su carpeta, borra el viejo y ejecuta:

```
python landing/build_site.py
```

El generador detecta lo que haya, lo convierte, lo copia a
`landing/assets/fonts/` y reescribe las declaraciones `@font-face`.
