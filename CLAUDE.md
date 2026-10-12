# Sobreala

Plataforma de email marketing para negocios de Panamá. Las empresas clientes
suben sus contactos, arman campañas (ofertas, recordatorios, eventos) y las
envían desde un panel web. Las piezas las arma cada cliente en el editor, o sube
su propio HTML: el diseño como servicio aparte se dejó de ofrecer.

Mercado principal: Santiago de Veraguas y el interior. Cliente típico:
cooperativas de ahorro y crédito, colegios privados, gremios, universidades y
PyMEs — organizaciones que ya tienen una lista de correos armada por otra razón.

**Estado.** Están la marca (`brand/`), el sitio público (`landing/`, una sola
página más las dos legales, estáticas y generadas con Jinja2), la cuenta entera —registro, código,
doble factor, dispositivos, configuración—, **contactos** con su importador y
sus supresiones, **plantillas** —el lienzo, que se baja y se carga como ZIP,
y las cargadas en HTML y las prediseñadas que quedaron de antes—, la cuenta
que se abre **con la demostración o con el pago**, el **panel de
administración**, el
**cobro de un plan con PayPal** y el **envío de campañas**, con su enlace de
baja, y **el aviso de Amazon** que cuenta qué pasó con cada correo después de
salir. Faltan la pausa automática por rebotes y quejas, y el proceso en segundo
plano.

---

## Stack

| Componente | Tecnología | Dónde corre |
|---|---|---|
| Backend | Flask (Python) | Railway |
| Base de datos | MongoDB Atlas (PyMongo) | AWS us-east-1 |
| Envío de correo | **Amazon SES** (API HTTPS, no SMTP) | AWS |
| Landing | HTML/CSS/JS estático | Cloudflare Pages |
| DNS, WAF, rate limiting | Cloudflare (modo proxied, SSL Full strict) | — |
| Imágenes de correos | En la propia base, servidas por el panel | Railway |
| Pagos | PayPal, y tarjeta por Paguélofácil (falta la afiliación). Yappy, anunciado | — |

**No usar Brevo ni SMTP propio.** Brevo prohíbe en sus términos enviar en nombre
de terceros y sus tarifas dan margen negativo. El SMTP propio o de una cuenta
empresarial tiene límites de ~2,000 correos/día y quema la reputación del
dominio. Ver `docs/decisiones.md`.

---

## Estructura del repositorio

```
sobreala/
├── CLAUDE.md
├── README.md
├── .env.example
├── docs/
│   ├── pricing.md          # planes, precios y reglas de negocio
│   ├── pricing-interno.md  # costos, márgenes, competencia (FUERA de git)
│   ├── arquitectura.md
│   ├── decisiones.md
│   ├── ses.md              # conectar SES con el panel, y la entrega a la UTP
│   └── cuenta.md, contactos.md, plantillas.md, envios.md, panel.md, cobro.md,
│       sitio.md            # el detalle de cada parte (ver «Cada parte, en corto»)
├── brand/
│   ├── colors.css          # variables de color, fuente única de verdad
│   ├── layout.json         # posición del ala (logo, favicon y perfil) y su encuadre
│   ├── build_logo.py       # genera logo/, favicon/, perfil/ y preview/ desde esos dos
│   ├── logo/               # logo.svg, logo-transparent.svg, logo.png (generados)
│   │   └── reference/      # PNG original del logo, referencia visual maestra
│   ├── favicon/            # favicon.svg, .ico y PNG 16/32/180 (generados)
│   ├── perfil/             # perfil-1080.png: la foto de perfil para redes (generada)
│   ├── preview/            # colores.html: editor de color y posición (generado)
│   ├── social/             # iconos de redes (Instagram, etc.), agregados a mano
│   └── fonts/
├── requirements.txt        # dependencias de Python; en la raíz porque Railway
│                           # las busca aquí para reconocer el proyecto
├── Procfile                # cómo arranca en Railway
├── .python-version         # 3.12
├── landing/                # → Cloudflare Pages (sitio público, ver landing/README.md)
│   ├── build_site.py       # genera las páginas; único punto de entrada.
│   │                       # --check avisa si lo publicado quedó viejo
│   ├── content.py          # todos los textos del sitio, en español
│   ├── shots.py            # la cuenta de demostración, el panel y Chrome que
│   │                       # usan tutorials.py y samples.py
│   ├── tutorials.py        # las capturas de los tutoriales y tutorials.json
│   │                       # (GENERADO); --check avisa si falta alguna
│   ├── samples.py          # las miniaturas de las plantillas de muestra de la
│   │                       # portada; --check avisa si falta alguna
│   ├── src/                # plantillas Jinja2 (base, parciales, secciones de la
│   │                       # página única, páginas legales y de paso) y site.css
│   ├── assets/             # css, js, fonts, img (fonts, img y css/site.css son
│   │                       # generados; img/usos, las fotos, van a mano)
│   ├── index.html          # GENERADO: la página única (precios leídos de
│   │                       # docs/pricing.md al construir)
│   ├── privacy/, terms/    # GENERADO: las dos legales
│   └── pricing/, how-it-works/, about/, contact/
│                           # GENERADO: páginas de paso a su sección
└── backend/                # → Railway
    ├── wsgi.py
    ├── config.py
    ├── requirements.txt    # apunta al de la raíz, que es el de verdad
    ├── blueprints/
    │   ├── auth/           # registro, confirmación, login, configuración. HECHO
    │   ├── contacts/       # importación, etiquetas, supresiones. HECHO
    │   ├── designs/        # plantillas: el lienzo y las de antes. HECHO
    │   ├── admin/          # aprobar cuentas, ficha de cliente y piezas. HECHO
    │   ├── campaigns/      # crear, programar, enviar por tandas. HECHO
    │   ├── unsubscribe/    # la baja, sin sesión. HECHO
    │   ├── analytics/      # bajarse Estadísticas en CSV y en PDF. HECHO
    │   ├── billing/        # planes, cuota, acumulado
    │   └── webhooks/       # SNS de SES. HECHO. PayPal y Yappy, no
    ├── models/
    ├── make_admin.py       # da el rol de administrador al primero, a mano
    ├── build_assets.py     # genera panel.css y _wing.svg; --check avisa si
    │                       # quedaron viejos
    ├── services/
    │   ├── mailer.py       # correo del sistema: file | smtp | ses
    │   ├── notices.py      # los avisos de la cuenta: plan, cuenta abierta,
    │   │                   # suspensión, y los avisos para el admin
    │   ├── security.py     # contraseñas, CSRF, límite de intentos
    │   ├── totp.py         # autenticación de múltiples factores
    │   ├── importer.py     # CSV en streaming, upsert por lotes
    │   ├── plans.py        # precios, etiquetas y quién sube HTML, de docs/pricing.md
    │   ├── html_check.py   # revisa el HTML de las piezas cargadas antes
    │   ├── paypal.py       # crear y cobrar la orden, con urllib
    │   ├── sender.py       # arma y entrega cada correo de una campaña
    │   ├── unsubscribe.py  # el enlace de baja, firmado, uno por destinatario
    │   ├── render.py       # arma el correo: la pieza más la baja, la marca
    │   │                   # de agua y la dirección postal
    │   ├── imaging.py      # achica y reconoce las imágenes de las piezas
    │   ├── ses.py
    │   ├── canvas_pdf.py   # la pieza del lienzo, bajada como PDF
    │   ├── ses_events.py   # a dónde va cada aviso de SES: evento, supresión
    │   │                   # o la fila de mail_log
    │   └── payments/
    ├── email_templates/    # plantillas prediseñadas del producto, una por
    │                       # archivo, con sus campos declarados arriba
    ├── sample_templates/   # los ZIP de lienzo de la tira de la portada, uno
    │                       # por plantilla de SAMPLES (landing/content.py)
    ├── templates/          # Jinja: panel del cliente y admin
    ├── static/
    └── tests/
```

Un solo repositorio. `landing/` se despliega a Cloudflare Pages y `backend/` a
Railway; cada plataforma apunta a su carpeta.

**Todo lo que dice GENERADO se escribe con un comando, nunca a mano.** Editar
`landing/src/` o `_panel.src.css` y no regenerar no rompe nada y llega al
despliegue en silencio: ya pasó una vez. Por eso `python landing/build_site.py
--check` y `python backend/build_assets.py --check` comparan sin escribir, y
`backend/tests/test_generated.py` los llama, así que un `pytest` falla cuando
algo quedó viejo y dice qué comando correr.

El panel de administración es un **blueprint con verificación de rol**, no una
aplicación aparte: comparte modelos y servicios con el resto.

---

## Convenciones

- **Código en inglés**: variables, funciones, colecciones y campos de Mongo
  (`contacts`, `send_campaign`, `bounce_rate`, `suppression_reason`).
- **Interfaz en español**: todo lo que ve el cliente — panel, correos del
  sistema, mensajes de error, plantillas. Los textos de interfaz van en un solo
  archivo de traducciones, no dispersos en las plantillas.
- Comentarios en inglés.
- **En la interfaz no se usan guiones largos.** Un inciso va entre paréntesis,
  con comas o con dos puntos. En el texto que lee un cliente —el panel, el sitio
  y los correos— esa raya se lee como escrita por una máquina. En los
  comentarios del código y en este documento da igual.
- Implementaciones mínimas y directas. No agregar funcionalidad que no se pidió.
- **No cambiar nada que no se haya pedido.** Si al hacer una tarea aparece algo
  más —un texto flojo, una regla que se salta en silencio, algo que se podría
  endurecer— **se dice y se espera**, no se arregla de paso. La única excepción
  es lo estrictamente necesario para que lo pedido funcione o para que las
  pruebas pasen, y eso va nombrado en el reporte. Renombrar de paso, reordenar,
  «ya que estoy» y «aprovecho y mejoro esto» no entran.
- **Los commits se hacen aquí, pero solo cuando se piden.** Terminar un bloque
  no es una orden de subir nada: el reporte sigue siendo el resumen enumerado
  con su asunto sugerido, y ahí se espera. Cuando se pide subirlo, primero se
  pregunta si va con ese asunto o con uno escrito a mano, y después `git add`,
  `git commit` y `git push`. Un plan aprobado tampoco es una orden de subir:
  aprobar un plan es decir «hazlo», no «publícalo».
- **En el repositorio no aparece Claude.** Ningún commit lleva `Co-Authored-By`,
  ni enlace de sesión, ni una línea de «generado con»: el autor es el de
  `git config` y el mensaje dice qué cambió y nada más. Si algún día eso no se
  pudiera cumplir, entonces no se commitea.
- **Los permisos viven en `.claude/settings.json` del proyecto**, no en el del
  usuario, para que esto valga en Sobreala y no en sus otros repositorios. Van
  sin preguntar: `status`, `log`, `diff`, `show`, `add`, `commit`, `push`,
  `branch`, `remote` y `fetch`. Quedan negados a propósito, y los hace una
  persona a mano: `reset --hard`, `push --force`, `rebase`, `clean`,
  `filter-branch` y borrar el `reflog`.
- **Lo que existe en los dos sitios se cambia en los dos.** La barra de arriba,
  su menú y todo lo que se repita entre `sobreala.com` (`landing/src/`) y
  `app.sobreala.com` (`backend/templates/`) son **dos plantillas distintas
  que tienen que decir lo mismo**. Al tocar una, se abre la otra en el mismo
  cambio y se comprueban las dos en el navegador, con sesión y sin ella. Ya
  mordió dos veces: la fila de Plantillas se puso solo en el panel, y salir
  preguntaba en un sitio y no en el otro.

---

## Cada parte, en corto

Lo de abajo es lo que no se puede olvidar de cada parte. **El detalle está en
`docs/`, y se lee antes de tocar esa parte**: es lo que explica por qué cada
cosa está como está, y lo que ya se probó y se quitó.

| Antes de tocar… | Leer |
|---|---|
| Registro, entrada, contraseña, doble factor, sesiones, usuarios de la cuenta, abrir la cuenta (demostración o pago), avisos, `mail_log`, `auth_events` | `docs/cuenta.md` |
| Contactos, etiquetas, columnas propias, supresiones, importación | `docs/contactos.md` |
| Plantillas: el lienzo, el ZIP, el PDF, la revisión antispam, las de antes, las imágenes | `docs/plantillas.md` |
| Remitente, campañas, envío por tandas, la baja, eventos, el aviso de SES | `docs/envios.md` |
| Estadísticas, la hora, varias cuentas abiertas, el menú, administración | `docs/panel.md` |
| Pagos, PayPal, Paguélofácil, mejoras con prorrateo, recibo, `/checkout` | `docs/cobro.md` |
| El sitio público: la página única, sus secciones, capturas y tutoriales | `docs/sitio.md` |
| Precios, límites por plan | `docs/pricing.md` (fuente de verdad) |
| Conectar SES | `docs/ses.md` |

### La cuenta (`docs/cuenta.md`)

- `accounts`: estados `registered` → `active` → `suspended`. **`activate_plan()`
  es el único que escribe `active`**, y lo llama un pago cobrado o el plan puesto
  a mano. Suspender lo decide el administrador, con motivo en `admin_events`, y
  cierra las sesiones.
- **Una cuenta nueva nace cerrada** (`accounts.is_open()`): ve su bienvenida y
  Configuración, y puede pagar. Se abre **con la demostración**, que pide desde
  `/welcome` y abre el administrador en la ficha (y queda con lo del Básico sin
  enviar), **o con el pago**, que la abre con todo, envío incluido. La puerta
  está en `needs()`. La habilitación antes del primer envío se quitó en octubre
  de 2026.
- **El registro pide teléfono personal (con su país), los de la empresa y la
  dirección**, que se cambian con «Editar». **La identificación no se escribe**:
  se envía como documento, junto con el de la dirección, en `/verification`, y
  **se verifican a mano**; el archivo se borra al decidir (`verification_docs`).
  El administrador manda el resultado con un botón, y puede **limitar** una
  cuenta (rechazar la limita sola): entra, pero no envía (`sender.blocked()`
  dice `limited`).
- `role` vale `client` o `admin` en todas las cuentas. `/admin` responde 404 a
  quien no lo es y exige doble factor; un administrador solo administra.
- **Los usuarios de una empresa son documentos de `accounts`** con `owner_id`
  y `permissions`. `current_workspace()` es la empresa y `current_account()` la
  persona. Se comprueba en la ruta con `needs()` y `owner_only()`.
- Un registro sin confirmar se borra a las 24 h (`purge_at`). Ninguna contraseña
  se repite (`password_history`). El doble factor, si está puesto, se pide
  siempre.
- `notifications`: lo no escrito vale «sí»; los avisos de seguridad no se apagan.
  Todos los avisos los compone `services/notices.py`, y ninguno puede romper lo
  que estaba pasando.
- `sessions`: un documento por dispositivo, con hash del testigo. Entrar desde
  un dispositivo nuevo avisa por correo.

### Contactos (`docs/contactos.md`)

- **Un documento por dirección y cuenta**, con índice único sobre
  `{account_id, email_normalized}`. Las listas son **etiquetas** dentro del
  documento, y se crean antes de usarse.
- Las **columnas propias** son obligatorias: a un contacto incompleto no se le
  manda nada. El valor se guarda normalizado y como texto.
- **La supresión vive en su propia colección**, se consulta en lote con `$in` y
  no se marca en el contacto.
- La importación corre dentro del request, en streaming; hay que mudarla antes
  del primer cliente con más de unas 5,000 filas. `consent` guarda de dónde
  salió cada contacto.

### Plantillas (`docs/plantillas.md`)

- `designs.source`: `canvas` (todos), `upload` y `builtin` (ya no se crean; las
  que hay se editan y se envían).
- **El lienzo se guarda como JSON con coordenadas** y el correo se arma al
  enviar: `to_html()` lo traduce a una cuadrícula de tablas. `parse()` no se fía
  del JSON, `problems()` y `review()` deciden si se guarda.
- **Se baja y se carga como ZIP** (`canvas_from_pack()`): el lienzo con sus
  fotos y el HTML con sus imágenes. Cargarlo pasa lo mismo que Guardar.
- Las imágenes viven en la colección `images`, se achican al entrar y las sirve
  `/img/<nombre>` sin sesión. **Una que salió en un envío no se borra**: se
  retira con TTL a doce meses.
- `*|CAMPO|*` lo rellena `services/fields.py`, nunca Jinja. `services/render.py`
  es el único sitio que arma un correo.

### Envío (`docs/envios.md`)

- **Cada cliente elige su remitente**: `usuario@envios.sobreala.com` o su propio
  dominio verificado. Una campaña nunca sale de `notifications@sobreala.com`.
- **`services/sender.py` es el único sitio que le escribe a un contacto**; los
  del sistema salen por `mailer.py`. Para mandar hace falta un plan con cuota
  (`sender.blocked()`).
- Una campaña se guarda y se manda las veces que haga falta. Sale por tandas de
  cien y anota la posición; cada salida es una línea en `campaign_runs`.
- `events`: uno por envío, persona y tipo. Las cifras cuentan **personas**.
- **El aviso de SES** (`/webhooks/ses/<secreto>`) sabe de quién es cada correo
  por sus etiquetas, nunca por la dirección. Rebote permanente y queja anulan en
  esa cuenta.
- Falta la pausa automática por rebotes (> 3 %) y quejas (> 0.05 %).

### El panel (`docs/panel.md`)

- Al entrar se aterriza en el sitio público. Una cuenta nueva ve `/welcome`.
- `/dashboard` es Estadísticas, en personas y con su pastilla contra el periodo
  anterior. Lo llena `services/stats.py`, y el administrador ve la misma
  pantalla.
- **Todo se guarda en UTC y se escribe en la zona de quien mira**
  (`services/clock.py`, galleta `sa_tz`).
- Hasta cuatro cuentas abiertas en un navegador (`/switch-account`), cada una
  con su sesión de verdad. «Cerrar sesión» las cierra todas.
- La ficha de administración enseña cifras y orígenes, **nunca la lista de
  direcciones de un cliente**.

### Cobro (`docs/cobro.md`)

- Pago suelto de un mes o un año, por PayPal o tarjeta (Paguélofácil). **Decide
  la respuesta del proveedor al servidor**, nunca el navegador, y se compara el
  monto contra el intento.
- `payments` se escribe antes de mandar a pagar. Pasar a `completed` es una
  escritura condicional: cobrar dos veces no da dos periodos. Todo termina en
  `settle()`.
- Con un plan vigente solo se mejora, con prorrateo (`services/upgrade.py`). El
  mismo plan no se vuelve a pagar mientras está vigente.
- `/checkout/<plan>` es el resumen con el ITBMS dentro. Al cobrar se aterriza en
  el recibo.

### El sitio público (`docs/sitio.md`)

- **Es una sola página**: Inicio, Planes, Cómo funciona y Preguntas, en ese
  orden, y Contacto es el pie. La barra lleva las tres primeras, y solo baja a
  su sección. Privacidad y Términos son aparte.
- `/pricing/`, `/how-it-works/`, `/about/` y `/contact/` siguen existiendo como
  páginas de paso que llevan a su ancla (`REDIRECTS` en `build_site.py`).
- Los textos viven en `landing/content.py`. Los tutoriales y las miniaturas de
  las muestras se hacen con su comando; Features son dibujos en SVG, y las
  fotos de los usos van a mano, con sus autores en `docs/sitio.md`.

---

## Reglas que no se pueden violar

1. **Antes de enviar a cualquier dirección, verificar `suppressions`.** Los
   suprimidos se saltan y **no consumen cuota**.
2. **Borrar un contacto no borra su supresión.** Reimportarlo no lo reactiva.
3. **El enlace de baja se inyecta al enviar, no al guardar el HTML** — así el
   cliente no lo puede quitar. Es único por destinatario (con token). Va en
   todos los planes, sin excepción, más la cabecera `List-Unsubscribe`.
4. **La marca de agua "Enviado con Sobreala" se inyecta al enviar, solo en el
   plan Básico**, con el ala de la marca al lado (`static/img/email-logo.png`,
   que genera `build_assets.py` desde `brand/logo/logo.png`, en PNG porque Gmail
   y Outlook no dibujan SVG). Al subir de plan desaparece sola, y Negocio y
   Empresa no llevan ninguna mención. No la exige ninguna ley: es publicidad.
5. **Los contactos no se duplican.** Toda importación es un upsert sobre
   `{account_id, email_normalized}`.
6. **De los tokens de correo solo se guarda su hash**, nunca el valor que va
   en el enlace, y valen una sola vez y con vencimiento.
7. **Entrar y recuperar la cuenta nunca revelan si una dirección tiene cuenta.**
   Las dos responden igual exista o no, para que ninguna sirva de buscador de
   clientes. **El registro sí lo dice**: esconderlo dejaba a la persona
   esperando un código que no iba a llegar. El aviso al dueño se manda igual,
   con su propio límite por dirección para que el formulario no sirva para
   llenarle el buzón a nadie.
8. **Los correos del sistema son transaccionales**: sin enlace de baja y sin
   marca de agua. Las reglas 3 y 4 son solo para campañas de clientes.
9. **Nunca guardar datos de tarjeta.** El pago se hace en el checkout hospedado
   del proveedor; la tarjeta no toca el servidor ni la base de datos.
10. **Toda escritura de contactos usa `bulkWrite`**, y las supresiones se
   consultan en lote con `$in`. Nunca una consulta por contacto.

---

## Variables de entorno

```
MONGODB_URI
SECRET_KEY
AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
AWS_REGION
SES_CONFIGURATION_SET               # campañas, con aperturas y clics
SES_TRANSACTIONAL_CONFIGURATION_SET # correo del sistema, sin ellos
SES_WEBHOOK_SECRET        # va en la dirección del aviso; sin él, 404
SES_TOPIC_ARN             # opcional: descarta avisos de otro tema
SENDING_DOMAIN            # opcional: por omisión envios.sobreala.com
PAYPAL_ENV                # sandbox | live; en producción, con llaves, tiene que
                          # estar escrita: sin ella no arranca
PAYPAL_CLIENT_ID
PAYPAL_SECRET
PAYPAL_WEBHOOK_ID         # para comprobar los avisos; todavía sin usar
PAGUELOFACIL_ENV          # sandbox | live; en producción con sandbox no arranca
PAGUELOFACIL_CCLW         # el código web del comercio: crea los enlaces de pago
PAGUELOFACIL_TOKEN        # consulta las transacciones, que es lo que decide
PAGUELOFACIL_WEBHOOK_SECRET  # va en la dirección del aviso; sin él, 404
PAGUELOFACIL_CHECKOUT     # opcional: la página de pago, si no es la de siempre
YAPPY_MERCHANT_ID
YAPPY_SECRET
```

Nunca commitear el `.env`. En Railway van como variables del servicio.

---

## Antes de la primera campaña real

El correo del sistema y las campañas son dos caminos distintos. Lo de abajo no
hace falta para que alguien reciba su código de confirmación, y **sí** hace
falta antes de que salga la primera campaña de un cliente. Está aquí para que
no se descubra el día del lanzamiento.

- ~~**Dirección postal física en el pie de cada campaña.**~~ Hecho, y **es la de
  cada cliente**: la CAN-SPAM la pide en todo correo publicitario (basta un
  destinatario con Gmail o Hotmail) y es la de quien anuncia, no la de
  Sobreala. Se escribe en Configuración → Cuenta (`postal_address`, de 10 a
  200 caracteres), va inyectada al pie junto a la baja, y **sin ella no se
  envía**: `sender.blocked()` dice `postal`. El administrador la ve en la
  ficha y no la edita. Hubo una sola para todos en la variable `POSTAL_ADDRESS`,
  y se quitó. Un apartado postal cumple sin publicar un domicilio.
- ~~**Aviso de operación.**~~ Hecho: RUC y aviso están en `LEGAL_HOLDER` de
  `landing/content.py`, y `holder_line()` los escribe en la frase de apertura de
  la privacidad y de los términos. **Los precios incluyen el ITBMS**, lo dicen
  esas dos páginas, la de planes y `docs/pricing.md`, y a un cliente de fuera de
  Panamá se le factura como exportación de servicios sin que cambie lo que paga.
  Lo que falta de esto es **pedirle sus datos de facturación al cliente**: el
  panel no guarda su RUC en ningún sitio, y una factura en Panamá lo necesita.
- **Conectar el aviso de SES** siguiendo `docs/ses.md`. El código está y
  anula solo lo que rebota o se queja, pero hasta que el tema de SNS y los
  conjuntos de configuración existan no le llega nada. Es lo primero que AWS
  revisa si algo va mal.
- **La pausa automática por rebotes y quejas**, la de la tabla de «Envío». Hoy
  depende de mirar las cifras a mano.
- **Verificar `envios.sobreala.com`** como identidad aparte en SES, con su
  propio configuration set. El correo del sistema sale por `sobreala.com`
  (MAIL FROM `mail.sobreala.com`); separar los dos es lo que
  impide que la reputación de las campañas arrastre a los códigos de
  confirmación.
- **Tenants de SES por cliente**, para aislar reputación y supresión. Ya está
  decidido más arriba; el momento de montarlo es este.
- **Registro de consentimiento por contacto.** Guardar de dónde salió cada
  dirección y cuándo, en el propio documento del contacto. Hoy el importador no
  lo pide, y es exactamente lo que hay que enseñar cuando alguien reclame.
- **Pedir la producción de SES en la cuenta nueva de Sobreala**, que empieza en
  sandbox: lo que se prometa ahí sobre bajas, supresiones y umbrales tiene que
  estar funcionando de verdad cuando empiecen las campañas.
- **Contrato de encargo para clientes grandes.** El tratamiento de datos de
  terceros ya está pactado en los términos públicos (§8), que se aceptan al
  registrarse. Una cooperativa grande puede pedir además un documento firmado;
  ese addendum se redacta cuando aparezca.

## Pendientes de decisión


- Confirmar con Yappy (yappy@bgeneral.com / 800-5000) si soporta cobros
  recurrentes. Si no, el recurrente va solo por PayPal y a los de Yappy se les
  envía enlace de pago antes de cada vencimiento.
- Pedir acceso a producción de SES al empezar a desarrollar, no al lanzar: las
  cuentas nuevas arrancan en sandbox (200 correos/día, solo a direcciones
  verificadas) y la aprobación tarda ~24h.
- Presupuestar el salto de MongoDB Atlas: los eventos llenan los 512 MB del
  tier gratuito en unos 7 meses con 6 Básico + 3 Negocio + 1 Empresa.
