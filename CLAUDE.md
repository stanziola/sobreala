# Panamails

Plataforma de email marketing para negocios de Panamá. Las empresas clientes
suben sus contactos, arman campañas (ofertas, recordatorios, eventos) y las
envían desde un panel web. Panamails también les ofrece el diseño de las piezas
HTML como servicio.

Mercado principal: Santiago de Veraguas y el interior. Cliente típico:
cooperativas de ahorro y crédito, colegios privados, gremios, universidades y
PyMEs — organizaciones que ya tienen una lista de correos armada por otra razón.

**Estado.** Están la marca (`brand/`), el sitio público (`landing/`, siete
páginas estáticas generadas con Jinja2), la cuenta entera —registro, código,
doble factor, dispositivos, configuración—, **contactos** con su importador y
sus supresiones, **plantillas** con la validación del HTML subido, el **panel de
administración** con la habilitación de envío, y el **cobro de un plan con
PayPal**. Faltan campañas, analítica y el webhook de rebotes.

---

## Stack

| Componente | Tecnología | Dónde corre |
|---|---|---|
| Backend | Flask (Python) | Railway |
| Base de datos | MongoDB Atlas (PyMongo) | AWS us-east-1 |
| Envío de correo | **Amazon SES** (API HTTPS, no SMTP) | AWS |
| Landing | HTML/CSS/JS estático | Cloudflare Pages |
| DNS, WAF, rate limiting | Cloudflare (modo proxied, SSL Full strict) | — |
| Imágenes de correos | Cloudflare R2 | — |
| Pagos | Yappy y PayPal (tarjeta vía PayPal) | — |

**No usar Brevo ni SMTP propio.** Brevo prohíbe en sus términos enviar en nombre
de terceros y sus tarifas dan margen negativo. El SMTP propio o de una cuenta
empresarial tiene límites de ~2,000 correos/día y quema la reputación del
dominio. Ver `docs/decisiones.md`.

---

## Estructura del repositorio

```
panamails/
├── CLAUDE.md
├── README.md
├── .env.example
├── docs/
│   ├── pricing.md          # planes, precios y reglas de negocio
│   ├── pricing-interno.md  # costos, márgenes, competencia (FUERA de git)
│   ├── arquitectura.md
│   └── decisiones.md
├── brand/
│   ├── colors.css          # variables de color, fuente única de verdad
│   ├── layout.json         # posición del ala (logo y favicon) y encuadre del favicon
│   ├── build_logo.py       # genera logo/, favicon/ y preview/ desde esos dos
│   ├── logo/               # logo.svg, logo-transparent.svg, logo.png (generados)
│   │   └── reference/      # PNG original del logo, referencia visual maestra
│   ├── favicon/            # favicon.svg, .ico y PNG 16/32/180 (generados)
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
│   ├── src/                # plantillas Jinja2 (base, parciales, páginas) y site.css
│   ├── assets/             # css, js, fonts, img (fonts, img y css/site.css son generados)
│   ├── index.html          # GENERADO
│   ├── como-funciona/      # GENERADO
│   ├── planes/             # GENERADO (precios leídos de docs/pricing.md al construir)
│   ├── nosotros/           # GENERADO
│   ├── contacto/           # GENERADO
│   ├── privacidad/         # GENERADO
│   └── terminos/           # GENERADO
└── backend/                # → Railway
    ├── wsgi.py
    ├── config.py
    ├── requirements.txt    # apunta al de la raíz, que es el de verdad
    ├── blueprints/
    │   ├── auth/           # registro, confirmación, login, configuración. HECHO
    │   ├── contacts/       # importación, etiquetas, supresiones. HECHO
    │   ├── designs/        # plantillas: las prediseñadas y el HTML subido. HECHO
    │   ├── admin/          # aprobar cuentas, ficha de cliente y piezas. HECHO
    │   ├── campaigns/      # crear, programar, enviar, pausar/retomar
    │   ├── analytics/      # métricas, exportar CSV/PDF
    │   ├── billing/        # planes, cuota, recargas, acumulado
    │   └── webhooks/       # SNS de SES, PayPal, Yappy
    ├── models/
    ├── make_admin.py       # da el rol de administrador al primero, a mano
    ├── build_assets.py     # genera panel.css y _wing.svg; --check avisa si
    │                       # quedaron viejos
    ├── services/
    │   ├── mailer.py       # correo del sistema: file | smtp | ses
    │   ├── security.py     # contraseñas, CSRF, límite de intentos
    │   ├── totp.py         # verificación en dos pasos
    │   ├── importer.py     # CSV en streaming, upsert por lotes
    │   ├── plans.py        # precios, etiquetas y quién sube HTML, de docs/pricing.md
    │   ├── html_check.py   # revisa el HTML que sube un cliente
    │   ├── paypal.py       # crear y cobrar la orden, con urllib
    │   ├── ses.py
    │   └── payments/
    ├── email_templates/    # plantillas prediseñadas del producto
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
- Implementaciones mínimas y directas. No agregar funcionalidad que no se pidió.
- **No cambiar nada que no se haya pedido.** Si al hacer una tarea aparece algo
  más —un texto flojo, una regla que se salta en silencio, algo que se podría
  endurecer— **se dice y se espera**, no se arregla de paso. La única excepción
  es lo estrictamente necesario para que lo pedido funcione o para que las
  pruebas pasen, y eso va nombrado en el reporte. Renombrar de paso, reordenar,
  «ya que estoy» y «aprovecho y mejoro esto» no entran.
- **Lo que existe en los dos sitios se cambia en los dos.** La barra de arriba,
  su menú y todo lo que se repita entre `panamails.com` (`landing/src/`) y
  `panel.panamails.com` (`backend/templates/`) son **dos plantillas distintas
  que tienen que decir lo mismo**. Al tocar una, se abre la otra en el mismo
  cambio y se comprueban las dos en el navegador, con sesión y sin ella. Ya
  mordió dos veces: la fila de Plantillas se puso solo en el panel, y salir
  preguntaba en un sitio y no en el otro.

---

## Modelo de datos

### `accounts`
Cuenta de una empresa cliente. Guarda plan, cuota del mes, saldo acumulado,
estado y configuración de remitente.

Estados: `registered` → `active` → `suspended`

| Estado | Qué significa |
|---|---|
| `registered` | Se registró. Explora, importa contactos y **puede comprar un plan**. |
| `active` | Pagó. Su plan corre hasta `plan_until`. |
| `suspended` | Nada. Corte automático por rebotes/quejas, o manual. |

**Hubo un cuarto, `approved`, y se quitó.** Era una aprobación comercial a mano
sin la cual no se podía comprar. Esperar a que alguien te apruebe para poder
pagar no protegía nada que valiera esa espera; la mirada que sí importa —de
dónde salió esa lista— se hace ahora justo antes del primer envío, que es donde
puede hacer daño. Ver «La habilitación para enviar», más abajo.

**Estar activa es el efecto de un pago cobrado, no una decisión.** `activate_plan()`
es el único sitio que escribe `active`, y lo llaman tanto la vuelta de PayPal
como el plan que el administrador pone a mano para quien pagó por Yappy o por
transferencia. Lo que el administrador sí decide es **suspender y levantar la
suspensión**, desde `/admin/cuentas/<id>` y con un motivo que queda escrito en
`admin_events`. `suspended` no es decorativo: una cuenta suspendida no abre
sesión, y al suspenderla se le cierran las que tuviera abiertas.

### La habilitación para enviar

`sending_cleared_at` en la cuenta, y `sending_cleared_by` con quién la puso. **Es
la única puerta que queda con una persona detrás.** Todos los clientes envían
desde el mismo dominio, así que comparten una sola reputación: una lista comprada
la quema para todos. Se mira una vez —de dónde dijo que salió cada lista, y la
pieza que va a mandar— y después la cuenta queda habilitada.

Registrarse, importar y pagar **no la necesitan**: nada de eso le llega a nadie.
La portada de `/admin` lista lo que espera, que son las cuentas con plan y sin
habilitar. Todavía no hay campañas, así que nada consulta `can_send()` hoy; el
blueprint de campañas, cuando exista, lee ese booleano antes de mandar nada.

**`role` está en todas las cuentas** y vale `client` o `admin`; un campo que a
veces está y a veces no es difícil de leer y fácil de equivocar en una consulta.
Lo que decide quién manda es la comparación exacta contra `admin`, así que un
valor mal escrito no es administrador. Al primero se lo pone `make_admin.py` a
mano, porque nadie puede aprobarse a sí mismo el primer día. Las rutas de `/admin`
responden **404** a quien no lo tiene —un 403 le confirmaría a un curioso que la
dirección existe— y exigen doble factor: es la cuenta que puede aprobar,
suspender y leer las cifras de todos los clientes.

**Una cuenta de administrador solo administra.** No tiene panel de envíos, ni
contactos, ni plantillas, ni puede comprar un plan: no tiene a quién escribirle,
así que esas pantallas le saldrían vacías. De Configuración le queda **Seguridad**
—contraseña, dos pasos y dispositivos—, que es lo que hay que cuidar en la cuenta
que puede suspender y habilitar a todas las demás. Las filas se esconden del menú
**y las rutas la devuelven a `/admin`**: esconder un botón no es un permiso.

**Un registro que no se confirma se borra a las 24 horas.** `create()` escribe
`purge_at` y `confirm_email()` lo quita, así que Mongo barre solo lo que quedó a
medias: una dirección escrita mal no queda ocupada para siempre, y nadie puede
reservar el correo de un tercero registrándolo y no confirmando nunca. El
intento sigue en `auth_events`, que no tiene TTL.

**Ninguna contraseña se puede repetir.** `password_history` guarda el hash de
cada una que la cuenta usó, y cambiarla las compara todas: si alguien conoció
una, volver a ponerla devolvería la cuenta al mismo estado.

**Verificación en dos pasos, opcional para cada cliente.** `two_factor` guarda
el secreto de la app de códigos —TOTP: el servidor tiene que calcular los mismos
dígitos que el teléfono, así que ese sí va tal cual y no como hash—, el último
intervalo usado, para que un código no sirva dos veces, y los **hashes** de ocho
códigos de respaldo de un solo uso. Activarla y desactivarla piden la
contraseña: sin eso, quien encuentre una sesión abierta se queda con la cuenta.
Las dos cosas se avisan por correo.

**Las dos pantallas van en dos pasos, y la contraseña siempre va primero.** Para
activarla: la contraseña, y solo después el QR; entre las dos, una marca en la
sesión con diez minutos de vida, para que la del QR no se pueda abrir sola. Para
administrarla: primero se elige entre generar códigos nuevos o desactivar, y
después se confirma con la contraseña, para que se confirme una decisión y no un
botón cualquiera.

**Con dos pasos activados el código se pide siempre**, en cualquier dispositivo
y todas las veces. Hubo una opción de no volver a preguntar durante 30 días y se
quitó: un dispositivo que deja de preguntar un mes es un segundo candado abierto
un mes, y quien quiere esa comodidad lo que quiere es no tener dos pasos.

Los campos donde se pide la contraseña para probar quién eres —cambiarla, y
activar o desactivar los dos pasos— nacen de **solo lectura** y se liberan al
primer clic. El gestor de contraseñas del navegador no rellena lo que no se
puede escribir, y así no contesta él por quien acaba de sentarse frente a una
sesión ajena. Sin JavaScript el campo funciona como siempre.

**`notifications` guarda qué correos quiere recibir la cuenta**, una clave por
aviso. Lo que no esté escrito vale «sí»: una cuenta que nunca abrió la pantalla
recibe todo. Solo están ahí los avisos de actividad —`new_login`, `billing`,
`imports`, `campaigns`, `monthly`—. Los de seguridad **no tienen clave y no se
pueden apagar**: el código de confirmación, el de recuperación, la contraseña
cambiada y el doble factor activado o desactivado son los que enteran a alguien
de que otro está entrando a su cuenta, y `set_notifications()` descarta
cualquier campo del formulario que no sea uno de los cinco de arriba.

### `sessions`
Un documento por dispositivo con sesión abierta: de la galleta solo se guarda su
hash, y el documento lleva IP, navegador, cuándo entró y cuándo se le vio por
última vez. Es lo que permite enseñar los dispositivos conectados y cerrar uno
sin tocar los demás. TTL sobre `expires_at`.

**Entrar desde un dispositivo que la cuenta nunca usó manda un aviso por
correo**, con un enlace de un solo uso para cerrar esa sesión sin necesidad de
recordar la contraseña. Solo al entrar, no al confirmar el registro ni al
recuperar la clave, que ya avisan por su cuenta.

### `contacts`
**Un solo documento por dirección de correo por cuenta.** Índice único sobre
`{account_id, email_normalized}`. Normalización: sin espacios, minúsculas.

Las "listas" son un arreglo de **etiquetas** en el mismo documento, no
colecciones separadas. Esto garantiza que un contacto en varias listas:
cuente una sola vez contra el límite, reciba un solo correo, y consuma un solo
correo de la cuota.

**Cuántas etiquetas caben lo dice el plan**, leído de `docs/pricing.md` como los
precios: 1 · 2 · 4 · ilimitadas, y **1 sin plan**, como el Básico. No se copia el
número al backend por la misma razón que no se copian los precios. Una
consecuencia que conviene tener presente: con una sola etiqueta no se puede
segmentar, así que el Básico tampoco; si algún día estorba, es cambiar una fila
del documento.

**Las etiquetas se crean antes de usarse**, en `/contactos/etiquetas`, y viven
en `contact_tags` del documento de la cuenta. Los formularios de agregar e
importar solo enseñan casillas con las que existen, y el servidor descarta lo
que llegue y no esté en ese registro. Dos razones: escribirlas en cada
formulario dejaba «Socios» y «socios» como dos etiquetas distintas, y una recién
creada no aparecía en ningún lado hasta tener un contacto dentro, porque la
lista se sacaba preguntándole a los contactos.

**`added_by` dice por dónde entró cada contacto**, `manual` o `import`. Los que
existían antes de que el campo existiera no lo tienen y la pantalla enseña una
raya: no se puede saber hacia atrás, y una raya es mejor que inventarlo.

**Cada contacto guarda de dónde salió**: `consent` con el origen que se declaró
al importar, la nota y la fecha. Se pregunta antes de escribir nada porque no se
puede rellenar hacia atrás, y es lo que hay que enseñar cuando alguien reclame
que no dio su correo.

**Si está suprimido no se marca en el contacto.** La supresión vive en su propia
colección y se consulta en lote con `$in`; así las dos no pueden separarse, y un
contacto borrado y vuelto a importar reaparece suprimido. La columna «Estado» de
la lista sale de esa consulta, no de un campo guardado.

**Exportar pregunta antes.** El GET de `/contactos/exportar` no descarga nada:
dice cuántos van a salir y con qué filtro, y el POST es el que escribe el
archivo. El filtro viaja en campos escondidos, así que lo que baja es lo que esa
pantalla acaba de decir y no lo que quedó en la dirección de otra.

**El límite de contactos sale del plan** (`PLAN_CONTACTS` en
`models/account.py`, copiado de `docs/pricing.md`). Una cuenta **sin plan** tiene
`CONTACTS_FREE_LIMIT`, hoy 500: alcanza para probar con una lista de verdad y
deja que el Básico, con 1,000, valga la pena.

### `suppressions`
Correos que una cuenta no puede volver a contactar. **Colección aparte; el
cliente no la puede borrar.** Índice sobre `{account_id, email}` — nunca global:
una baja en una cuenta no afecta a las demás.

| `reason` | ¿Se puede levantar? |
|---|---|
| `unsubscribe` | Solo si la persona se resuscribe por el formulario, con doble opt-in |
| `hard_bounce` | Nunca |
| `complaint` | Nunca |
| `manual` | Sí, por el cliente desde el panel |

Guardar siempre fecha y origen.

### `imports`
Un documento por archivo subido: nombre, etiquetas, el origen declarado, en qué
fila va y cuántas entraron, se actualizaron o no eran direcciones. Es lo que
hace comprobables los límites —diez al día, una a la vez— y lo que responde qué
pasó con un archivo de hace meses.

**Hoy la importación corre dentro del request**, no en un proceso aparte. Es a
propósito: con un tope de 500 filas tarda menos que abrir la página. El
documento existe para que mudarla sea mover el trabajo y no rehacer los datos.
**Hay que mudarla antes del primer cliente con más de unas 5,000 filas**, que es
donde el request se acerca al tiempo máximo de Railway.

### `admin_events`
Un documento por decisión de un administrador: qué cambió, de qué a qué, sobre
qué cuenta, cuándo y **por qué**. El motivo no es opcional; la pantalla no deja
aplicar un cambio sin él, porque meses después esa frase es la única respuesta
honesta a «por qué me suspendieron». Sin TTL, como `auth_events`.

### `payments`
Un documento por **intento** de pago, escrito antes de mandar a nadie a PayPal:
la cuenta, el plan, si fue mensual o anual, el monto que se pidió cobrar, la
moneda, el identificador de la orden, el estado y las fechas. Se escribe antes y
no al volver porque si alguien paga y el navegador se cierra en el camino de
vuelta, ese intento tiene que existir para poder reconciliarlo.

**De la tarjeta no hay nada, y no puede haberlo**: el pago entero ocurre en el
checkout de PayPal. Es la regla 9.

Pasar de `created` a `completed` es una **escritura condicional**, y es la única
que decide si se alarga un plan: recargar la página de vuelta entra otra vez y
se va con las manos vacías en lugar de regalar otro periodo.

### `designs`
El HTML que sube un cliente. Se llaman «diseños» y no «templates» porque en este
repositorio `templates/` ya son las plantillas Jinja del panel; para el cliente
la pantalla dice **Plantillas**, que es su palabra. Las prediseñadas del producto
no están aquí: son archivos de `email_templates/`, iguales para todos y sin nada
que aprobar.

**Subir HTML propio es de Negocio en adelante**, y eso lo dice la fila «Subir tu
propio HTML» de `docs/pricing.md`, no una lista copiada al backend. El servidor
lo comprueba además de esconder el formulario: esconder un botón no es un
permiso.

**Cada subida se valida al entrar** con `services/html_check.py`, que lee el
documento con un parser y no con expresiones regulares —`&lt;script&gt;` es
texto y `<script>` no—. Fuera: `<script>`, `<iframe>`, `<object>`, `<form>`,
atributos de evento, CSS o imágenes de otro sitio, y **cualquier pieza de más de
102 KB**. Lo que se guarda es el archivo entero y tal como llegó.

**Nadie aprueba una pieza a mano.** Lo que puede hacer daño lo rechaza el
validador al subirla, y eso es mecánico, no un juicio. La mirada de una persona
ocurre una sola vez por cuenta, en la habilitación para enviar, y es sobre la
cuenta y su lista, no sobre el archivo. Tener las dos serían dos revisiones
manuales para la misma decisión. `/admin/plantillas` lista lo que han subido los
clientes, para poder abrir una cuando haga falta.

**El HTML de un cliente no se dibuja nunca dentro del panel**, ni en el suyo ni
en el del administrador. Se baja como `text/plain`: meterlo en una página
nuestra sería meter el documento de otro en una sesión abierta.

### `campaigns`
Incluye la **posición de envío** (hasta qué destinatario se envió), necesaria
para pausar por límite de cuota y retomar desde ahí.

### `events`
Un registro por evento de SES (enviado, entregado, rebote, queja, apertura,
clic), con su cuenta, su campaña y cuándo pasó. Es lo que más crece: ~3 eventos
por correo, ~200 bytes cada uno.
**Retención: 12 meses en detalle, después solo totales por campaña.**

**Todavía no la llena nadie**, y `models/event.py` ya la lee: la serie por tramo
de tiempo y los totales del periodo, que contra una colección que no existe
devuelven cero. Eso es lo que dibuja la pantalla de Estadísticas hoy, y el día
que el webhook de SNS entre en funcionamiento se llena sola sin tocar la
pantalla.

### `mail_log`
Un documento por cada **correo del sistema** que se intentó enviar, con el
cuerpo completo: destinatario, asunto, backend usado, `sent` o `failed`, el
error si falló, el HTML y el texto tal como salieron. Es lo que permite
responder qué salió del servidor cuando alguien dice que no le llegó la
confirmación. No cubre campañas de clientes, que llevan su propia contabilidad.

### `auth_events`
Un documento por cada intento de registro, entrada, reenvío, confirmación y
salida: `kind`, `outcome`, la dirección, `account_id` cuando se conoce, IP y
navegador. **La contraseña no se guarda nunca, en ninguna forma.**

Las dos son internas, solo las lee el admin, y **ninguna tiene TTL**: el
historial se conserva hasta que se decida otra cosa. `auth_events` registra la
verdad, `already_registered` incluido; la regla 7 gobierna lo que se le dice al
visitante, no lo que la plataforma sabe de su propio tráfico.

---

## Reglas que no se pueden violar

1. **Antes de enviar a cualquier dirección, verificar `suppressions`.** Los
   suprimidos se saltan y **no consumen cuota**.
2. **Borrar un contacto no borra su supresión.** Reimportarlo no lo reactiva.
3. **El enlace de baja se inyecta al enviar, no al guardar el HTML** — así el
   cliente no lo puede quitar. Es único por destinatario (con token). Va en
   todos los planes, sin excepción, más la cabecera `List-Unsubscribe`.
4. **La marca de agua "Enviado con Panamails" se inyecta al enviar, solo en el
   plan Básico.** Al subir de plan desaparece sola.
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

## Envío

Todos los clientes envían desde un subdominio de Panamails; **no se les exige
configurar DNS** porque la mayoría no tiene dominio propio:

```
De:        Tu Empresa <tuempresa@envios.panamails.com>
Responder: tuempresa@gmail.com
```

Al cliente que sí tiene dominio, Luis le configura el DKIM durante la
activación (opcional, mejor entregabilidad).

Como todos comparten el dominio, **la reputación es una sola** y las defensas
automáticas son la única protección:

| Métrica de una cuenta | Acción automática |
|---|---|
| Rebotes > 3% | Pausa de envío y aviso (AWS actúa a 5%) |
| Quejas > 0.05% | Pausa de envío (Gmail y Yahoo actúan a 0.1%) |
| Primera campaña | Tope reducido las primeras 48h, sin importar el plan |

Usar **tenants de SES** para aislar reputación y supresión por cliente.

Requisitos de remitente masivo que aplican a Panamails (no a sus clientes), al
pasar de 5,000 correos diarios sumando todos: DMARC publicado en
`panamails.com`, SPF y DKIM, baja de un clic procesada en menos de 2 días, y
tasa de quejas agregada bajo 0.1%.

---

## Flujo de campaña

```
1. Elegir plantilla prediseñada  ó  subir HTML propio (Negocio en adelante)
2. Escribir asunto y contenido
3. Elegir la lista destinataria
4. Vista previa + enviar correo de prueba a su propia dirección
5. Enviar ahora  ó  programar fecha y hora
```

Los envíos programados, las importaciones grandes y la reanudación de campañas
pausadas corren en un **proceso en segundo plano**, no dentro del request.

### HTML subido por el cliente

Hecho, en `/plantillas` y en la colección `designs`. Ver esa sección más arriba:
qué se rechaza, quién puede subir y quién aprueba la primera.

### Límites de importación

| Límite | Valor |
|---|---|
| Importaciones por día | 10 por cuenta |
| Filas por importación | El límite de contactos del plan |
| Tamaño de archivo | 5 MB |
| Importaciones simultáneas | 1 por cuenta |

Procesar el CSV **en streaming**, nunca cargarlo entero en memoria.

---

## Panel del cliente

**`/panel` es la pantalla de Estadísticas.** La dirección no cambió aunque la
pantalla se llame así: cambiarla rompería los enlaces guardados y el correo de
bienvenida a cambio de nada. Enseña las cifras de la cuenta —contactos activos y
anulados, etiquetas, importaciones, plan y cuota— y las **gráficas de envíos y
rebotes**, con filtro por periodo y por etiqueta.

Las gráficas leen `events`, que **todavía no llena nadie**, así que hoy salen
vacías. Se dibujan igual, con sus ejes y su leyenda, y encima la frase de que
aún no se ha hecho nada: un cuadro vacío que se explica enseña de antemano la
forma que va a tener, y un hueco no. **Son SVG generado en la plantilla, sin
JavaScript y sin librerías**: la cabecera del panel solo deja cargar guiones
propios, así que una de un CDN no cargaría, y traerse una al repositorio sería
algo que mantener y auditar para pintar rectángulos.

La llena `services/stats.py`, y **es la misma pantalla que ve el
administrador** en `/admin/` para la cuenta que elija: una plantilla y dos
entradas, para que no puedan separarse. **`/contactos`** tiene cuatro
pantallas: la lista —una fila por contacto, con sus etiquetas, por dónde entró,
cuándo y si está activo o anulado—, la importación, las etiquetas y las
supresiones. Agregar uno a mano tiene su propia pantalla, a la que se llega
desde un botón encima de la lista, y exportar pasa por una confirmación que dice
cuántos van a salir. **`/plantillas`** enseña las prediseñadas y las que ha
subido la cuenta. Y todo lo demás vive en **`/configuracion`**, con cuatro secciones:
**Cuenta** (datos, estado y plan), **Seguridad** (contraseña, dos pasos y
dispositivos conectados), **Notificaciones** y **Opciones de pago**, donde se
contrata un plan con PayPal y se ven los pagos hechos. Yappy sigue por
construir.

La barra de arriba lleva el logo, el nombre de la empresa y un desplegable con
las mismas cosas en el sitio público y en el panel, en este orden: panel,
contactos, plantillas, configuración, modo, idioma y cerrar sesión. Las
plantillas van debajo de contactos: primero a quién le escribes, después con qué.
**A un administrador el menú le enseña administración de primera y después
configuración, y nada más.** El sitio público sí le sigue enseñando las filas de
cliente, porque solo lee una galleta que dice «hay sesión» y no sabe quién es
—ponerle el rol sería publicar en el dominio padre quién es administrador—, pero
pulsarlas lo deja en `/admin`. El idioma es un desplegable dentro del desplegable, no
dos filas sueltas de algo que casi no se toca. **El panel va primero** porque es a
lo que se dedica la empresa; lo demás son ajustes, y se buscan cuando hacen
falta. Sin sesión el mismo control es un botón de tres líneas con las dos que
sirven sin cuenta.

**El idioma está anunciado, no traducido.** El menú enseña «Español» y «Inglés
(pronto)»; el inglés se hará cuando haya a quién dárselo.

**Salir cuesta un clic desde los dos sitios.** El sitio público está en otro
dominio y no lleva ningún testigo del panel, así que su «Cerrar sesión» no puede
ser un formulario: es un enlace, y un enlace es un `GET /salir`. Ese GET cierra
igual que el POST del menú del panel, y por eso no se le pide testigo.

Lo único que no obedece es una petición que el navegador **dice estar
adelantando** —`Sec-Purpose`, `Purpose` o `X-Moz` con `prefetch`—: sin eso, un
navegador que precarga enlaces sacaría a alguien de su cuenta sin que hubiera
pulsado nada. Se cierra por omisión y se calla solo ante esa cabecera; si un
intermediario se la comiera, lo que se pierde es la protección y no el salir.
`logout.html` sigue existiendo, pero solo la ve esa precarga.

Cerrar las sesiones de los **otros** dispositivos no se pregunta al salir: vive
en Configuración → Seguridad, que es su sitio.

## Panel de administración

`/admin`, con verificación de rol, y **es donde aterriza un administrador al
entrar**. Tres pantallas: **Estadísticas · Cuentas · Plantillas subidas**.

**Estadísticas** es `/admin/`, y es la misma pantalla del cliente con un selector
de cuenta encima: lo que ve él, de quien elijas. Hubo una portada antes ahí, con
el conteo por estado y las últimas decisiones; se quitó porque lo que pedía
acción cabe en un filtro de Cuentas y lo demás ya está en la ficha.

**Cuentas** es la tabla con filtro y buscador. **Nunca trae cuentas de
administrador**: no son clientes, no compran ni envían, y como un administrador
no paga nunca se quedaban en «registrada» para siempre, que es lo que hacía que
la columna de estado se leyera mal. Su filtro de estado tiene una entrada más,
**«esperando habilitación»**, que no es un estado sino la cola que pide acción:
pagaron y todavía no pueden enviar.

Arriba del todo de la ficha está lo único que espera una decisión: **habilitar el
envío**. Debajo, **un solo formulario** —plan, ciclo, suspensión y un motivo—: si
cambian dos cosas se anotan dos líneas en `admin_events` con el mismo motivo,
porque guardar una por cosa cambiada es lo que las hace legibles meses después.
Ponerle el plan a mano llama al mismo `activate_plan()` que usa PayPal, así que
deja la cuenta activa **y con fecha de vencimiento**, no con un plan que no vence
nunca. Y tiene
una **Actividad** que junta en una línea de tiempo lo que hizo la cuenta —sus
entradas, sus importaciones, sus pagos— con lo que se decidió sobre ella,
leyendo `auth_events`, `imports`, `payments` y `admin_events`.

**La ficha enseña cifras y orígenes, nunca la lista de direcciones de los
contactos de un cliente.** Cuántos tiene, cuántas supresiones, qué archivos subió
y de dónde dijo que salió cada lista: eso es operar la plataforma. Las
direcciones son suyas y de quien está en ellas, y se miran por un motivo
concreto —una baja que alguien pide, un abuso que se investiga—, no hojeando.

**Pendiente: la pantalla de gráficas.** El administrador elige un cliente y ve
lo mismo que ve él: correos enviados y rebotes contra el tiempo, con filtro por
periodo —las últimas 24 horas, por ejemplo— y por etiqueta. **No se puede hacer
todavía**: las colecciones `events` y `campaigns` no existen, así que no hay
envíos, rebotes ni aperturas guardados en ningún sitio. Se hace junto con las
campañas y el webhook de SNS, que es lo que las llena; antes de eso solo
dibujaría ceros y habría que rehacerla cuando se sepa qué forma tienen los
eventos de verdad. Sigue valiendo la regla de arriba: cifras agregadas sí, la
lista de direcciones de sus contactos no.

Pendiente además: cargar plantillas prediseñadas · revisar rebotes por cliente.

Además:

1. **Tasa de rebotes y quejas agregada en la portada** — la de Panamails, no la
   de cada cliente. Es la métrica que puede cerrar el negocio.
2. Estado de pagos y renovaciones (Yappy puede requerir cobro manual).
3. Cola de solicitudes de diseño, con estado y fecha límite de 3 días hábiles.
4. Envíos en curso, pausados y fallidos.
5. Ver el panel como el cliente, para soporte. Queda registrado.
6. Registro de actividad: aprobaciones, cambios de plan, pausas, con motivo.
7. Buscador global de direcciones, para suprimir a quien escriba pidiendo la baja.

---

## Cobrar un plan

Se contrata desde **Configuración → Opciones de pago**. Hoy es un **pago suelto**
de un mes o un año, no una suscripción: PayPal cobra una vez y el plan queda
activo por ese periodo. La renovación se avisa a mano, igual que ya estaba
previsto para Yappy. La suscripción que se renueva sola pide crear un producto y
un plan por cada uno de los nuestros en el panel de PayPal, y el webhook
funcionando; es el paso siguiente, no este.

```
Contratar  →  el servidor crea la orden  →  el navegador va a PayPal
           →  PayPal devuelve al panel   →  el servidor cobra y comprueba
           →  la cuenta queda activa con su plan
```

Tres cosas de ese camino que no son negociables:

1. **Lo que decide es la respuesta de PayPal al servidor**, nunca lo que traiga
   el navegador de vuelta. Ahí solo viene un identificador de orden, que no
   prueba nada. El servidor cobra la orden por su cuenta y **compara el monto y
   la moneda** contra lo que ese plan cuesta; si no cuadra, no se activa nada y
   el intento queda escrito con la diferencia.
2. **Cobrar dos veces la misma orden no da dos periodos**, por la escritura
   condicional de `payments`.
3. **Los precios salen de `docs/pricing.md`**, no copiados al backend:
   `services/plans.py` lee las mismas dos filas que lee el sitio. Cambiar una
   cifra ahí la cambia en el sitio, en el panel y en lo que se cobra.

**Quién puede pagar**: cualquiera con el **correo confirmado** y **sin suspender**,
y ninguna de las dos la decide una persona (`accounts.can_buy()`). El correo
confirmado porque es a donde va el comprobante, y cobrarle a una dirección
escrita mal deja a alguien pagando sin recibir nada. Una cuenta activa también,
porque si no el primer pago sería el último y nadie podría renovar ni cambiar de
plan. **Un administrador no**: su cuenta no tiene a quién escribirle.

Pagar mueve la cuenta a `active` y escribe `plan` y `plan_until`. Renovar el
mismo plan antes de tiempo **suma al final de lo que quedaba**; cambiar de plan
empieza hoy. Pagar **no** habilita el envío: eso es la otra puerta.

**Corporativo no se compra por la web.** `docs/pricing.md` dice que va sin precio
público, a la medida: su botón lleva a contacto. Ponerlo comprable sería poner un
precio donde el documento dice que no hay ninguno.

**El plan se elige en `/planes`, no dentro del panel.** El botón de cada plan
del sitio público lleva a `/contratar/<plan>`, que enseña lo que cuesta y tiene
el botón de pagar; sin sesión manda a entrar llevando **el nombre del plan, nunca
una dirección**, y al abrir sesión sigue hasta ahí. Configuración → Opciones de
pago ya no vende: dice desde dónde se cobra, qué plan hay contratado y qué se ha
cobrado.

**`form-action` de la cabecera tiene que permitir el checkout de PayPal.** Esa
regla gobierna también la redirección que sigue al envío de un formulario, así
que con solo `'self'` el navegador se niega a ir a PayPal: el servidor crea la
orden, responde 302, y desde fuera parece que el botón no hace nada. El destino
sale de `Config.paypal_checkout()`, según el entorno.

Sin credenciales configuradas la pantalla se dibuja igual y dice que el pago no
está disponible, en vez de romperse.

## Planes

Ver `docs/pricing.md` para la tabla completa, límites y reglas. Los costos, los
márgenes y el análisis de competencia están en `docs/pricing-interno.md`, que
está en `.gitignore` a propósito y no debe subirse.

Resumen: Básico $35 · Negocio $60 · Empresa $120 · Corporativo $300 (a la
medida, sin precio público). `docs/pricing.md` es la fuente de verdad; el sitio
público lee sus tablas al construirse, así que no hay que copiar cifras a mano. El límite de correos es siempre **5x** el de
contactos. Anual = 2 meses gratis. Los correos no usados pasan al mes siguiente
y vencen ahí; se consumen primero los acumulados.

---

## Variables de entorno

```
MONGODB_URI
SECRET_KEY
AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
AWS_REGION
SES_CONFIGURATION_SET
SENDING_DOMAIN            # envios.panamails.com
R2_ACCOUNT_ID
R2_ACCESS_KEY_ID
R2_SECRET_ACCESS_KEY
R2_BUCKET
PAYPAL_ENV                # sandbox | live; en producción con sandbox no arranca
PAYPAL_CLIENT_ID
PAYPAL_SECRET
PAYPAL_WEBHOOK_ID         # para comprobar los avisos; todavía sin usar
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

- **Dirección postal física en el pie de cada campaña.** La CAN-SPAM de Estados
  Unidos la exige en todo correo publicitario, y basta un destinatario con
  Gmail o Hotmail para caer en su ámbito. Va inyectada al enviar, junto a la
  baja y a la marca de agua, no en el HTML del cliente. Hoy no existe. Un
  apartado postal de Correos de Panamá cumple el requisito sin publicar un
  domicilio particular.
- **Aviso de operación.** Hace falta para operar y facturar en Panamá
  (panamaemprende.gob.pa). En cuanto exista se escribe en `LEGAL_HOLDER` de
  `landing/content.py` y aparece solo en las dos páginas legales.
- **Webhook de SNS para rebotes y quejas** (blueprint `webhooks/`). Es lo que
  llena `suppressions` sin intervención y lo que hace ciertas las defensas
  automáticas de la tabla de arriba. Sin él, una queja no bloquea el reenvío y
  la pausa por umbrales depende de mirar los datos a mano. Es lo primero que
  AWS revisa si algo va mal.
- **Verificar `envios.panamails.com`** como identidad aparte en SES, con su
  propio configuration set. El correo del sistema sale por `panamails.com`
  (MAIL FROM `mail.panamails.com`, ya configurado); separar los dos es lo que
  impide que la reputación de las campañas arrastre a los códigos de
  confirmación.
- **Tenants de SES por cliente**, para aislar reputación y supresión. Ya está
  decidido más arriba; el momento de montarlo es este.
- **Registro de consentimiento por contacto.** Guardar de dónde salió cada
  dirección y cuándo, en el propio documento del contacto. Hoy el importador no
  lo pide, y es exactamente lo que hay que enseñar cuando alguien reclame.
- **Revisar la solicitud de producción de SES ya enviada** (`solicitud-ses.txt`
  en la raíz): lo que se prometió ahí sobre bajas, supresiones y umbrales tiene
  que estar funcionando de verdad cuando empiecen las campañas.
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
