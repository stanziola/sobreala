# Iconos de redes sociales

Carpeta para los iconos de redes y contacto que se usan en el landing, los
correos y los paneles: Instagram, Facebook, WhatsApp, LinkedIn, TikTok,
YouTube, X, correo, teléfono.

**Se agregan a mano.** No los genera `build_logo.py` ni dependen de
`colors.css`; son marcas de terceros y se usan sus versiones oficiales.

## Convención

| Archivo               | Formato                              |
|-----------------------|--------------------------------------|
| `instagram.svg`       | vector oficial, monocromo, sin fondo |
| `facebook.svg`        | ídem                                 |
| `whatsapp.svg`        | ídem                                 |
| `linkedin.svg`        | ídem                                 |
| `tiktok.svg`          | ídem                                 |
| `youtube.svg`         | ídem                                 |
| `x.svg`               | ídem                                 |
| `email.svg`           | ídem                                 |

- Un archivo por red, en minúsculas, sin espacios. Vale `.svg` o `.png`; el
  generador del sitio (`landing/build_site.py`) toma el que encuentre, con
  preferencia por el SVG. Un PNG debe llevar fondo transparente y medir 512 px
  o más.
- SVG cuadrado (`viewBox="0 0 24 24"`) con `fill="currentColor"`, para que el
  color lo ponga el CSS con `var(--color-...)` de `colors.css`. Si la red exige
  su color de marca, ese color va dentro del propio SVG, no en `colors.css`.
- Si además hace falta un PNG (por ejemplo para correos, donde el SVG no
  siempre se muestra), va al lado con el mismo nombre: `instagram.png`, a 64×64.

## Uso en la web

```html
<a href="https://instagram.com/..." aria-label="Instagram">
  <img src="/assets/img/social/instagram.svg" alt="" width="24" height="24">
</a>
```

Inline, cuando se quiera colorear con CSS:

```html
<a href="..." class="social" aria-label="Instagram">
  <!-- contenido de instagram.svg pegado aquí -->
</a>
```

```css
.social { color: var(--color-logo); }
.social:hover { color: var(--color-background); }
```

Igual que el logo y los favicons, `landing/` se despliega solo: los iconos que
use el landing se copian dentro de `landing/` en el paso de build o a mano.
