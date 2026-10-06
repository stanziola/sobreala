# Backend de Sobreala

Aplicación Flask con el panel del cliente. Por ahora solo cubre cuentas:
registro, confirmación del correo, entrar y salir.

## Levantarlo

```
pip install -r requirements.txt
cp .env.example .env          # y completar MONGODB_URI y SECRET_KEY
python backend/build_assets.py
python backend/wsgi.py
```

La lista de dependencias vive en la **raíz** del repositorio, no aquí: es donde
Railpack, el constructor de Railway, la busca para reconocer el proyecto como
Python. `backend/requirements.txt` apunta a ella, así que ese comando también
sigue funcionando. `.python-version` fija Python 3.12 para que el despliegue no
cambie de versión por su cuenta.

Queda en `http://127.0.0.1:5000/`.

## Rutas

| Ruta | Qué hace |
|---|---|
| `/signup` | Crear cuenta y recibir el código de confirmación |
| `/confirm` | Escribir el código de 6 dígitos; vale una sola vez y entra a la cuenta |
| `/resend-confirmation` | Pide otro código |
| `/login` · `/logout` | Sesión |
| `/dashboard` | Panel vacío, con aviso si el correo no está confirmado |

## Correo

`MAIL_BACKEND` decide cómo se envía:

| Valor | Cuándo |
|---|---|
| `file` | Desarrollo. Guarda el mensaje en `backend/.mail_outbox/` y escribe el código en la consola. No manda nada |
| `smtp` | Puente. Un servidor SMTP corriente, por ejemplo Gmail con contraseña de aplicación |
| `ses` | Producción. Amazon SES por su API |

**Sobre `smtp`.** `CLAUDE.md` descarta SMTP para las **campañas**, que son envíos
masivos en nombre de terceros. Unos pocos correos de confirmación son otra cosa,
y sirve como puente mientras SES sale del modo de pruebas. Dos avisos:

- `MAIL_SMTP_FROM` tiene que ser el mismo buzón que autentica. Enviar como
  `notifications@mail.sobreala.com` a través de Gmail falla SPF y DKIM y cae en spam.
  El código pone ese buzón como remitente y deja la dirección de la marca en
  `Responder a`.
- Gmail limita alrededor de 500 destinatarios al día y puede bloquear una cuenta
  que empiece a parecer un emisor masivo.

**Los correos del sistema son transaccionales**: no llevan enlace de baja ni
marca de agua. Esas reglas son para las campañas de los clientes.

### Probar el envío: `check_mail.py`

```
python backend/check_mail.py luis@ejemplo.com
```

Manda un mensaje por el backend configurado, dice con qué ajustes lo intentó y,
si falla, escribe la respuesta del proveedor tal cual. Es lo que convierte «no
llega el correo» en algo accionable: SES contesta cosas como `MessageRejected:
Email address is not verified`, que dice exactamente qué falta. El intento queda
en `mail_log` con `purpose: "check"`.

### Configurar Amazon SES

Railway **no deja salir tráfico SMTP**: la conexión muere con `Network is
unreachable` antes de abandonar el servidor. Por eso el correo del sistema tiene
que salir por una API HTTPS, y la elegida en `CLAUDE.md` es SES.

Lo que hay que montar en la cuenta de AWS y en Cloudflare, comprobable después
desde cualquier parte con `nslookup`. **Todavía no está**: la cuenta de AWS de
Sobreala es nueva y su SES empieza en sandbox.

| Registro | Valor | Para qué |
|---|---|---|
| identidad SES | `sobreala.com`, verificada en **us-east-2** | Cubre también sus subdominios |
| `mail.sobreala.com` MX | `feedback-smtp.us-east-2.amazonses.com` | MAIL FROM propio: los rebotes vuelven a SES |
| `mail.sobreala.com` TXT | `v=spf1 include:amazonses.com ~all` | SPF del sobre, alineado con el dominio |
| `_dmarc.sobreala.com` TXT | `v=DMARC1; p=none;` | DMARC observando |
| `sobreala.com` MX | Cloudflare Email Routing | Correo entrante del dominio |

**La región es `us-east-2`, no `us-east-1`.** SES es por región y la identidad
solo existe en la que se verificó; con la región equivocada, el envío falla con
«identity not verified» aunque todo lo demás esté bien.

El remitente es `notifications@sobreala.com`, del dominio raíz, **no**
`notifications@mail.sobreala.com`: ese subdominio es el MAIL FROM y su MX apunta al
endpoint de rebotes de SES, así que una respuesta enviada ahí no llegaría a
nadie. Conviene crear en **Cloudflare Email Routing** una regla que lleve
`notifications@sobreala.com` a un buzón real, para que responder al correo sirva de
algo.

Falta:

1. Un usuario **IAM** solo para esto, con permiso de `ses:SendEmail` y
   `ses:SendRawEmail` **restringido a esa identidad**. De ahí salen las claves.
2. **Pedir acceso de producción** en SES. Tarda ~24 h. Mientras tanto la cuenta
   está en *sandbox*: solo se puede enviar a direcciones verificadas una por una,
   así que un registro con cualquier otra dirección va a fallar — limpiamente, y
   deshaciendo la cuenta, que es lo que hace la aplicación cuando el correo no
   sale.
3. En Railway: `MAIL_BACKEND=ses`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`,
   `AWS_REGION=us-east-2` y `SYSTEM_FROM_EMAIL=notifications@sobreala.com`.

`curl https://app.sobreala.com/health` responde con `"mail": "ses"` cuando el
despliegue tomó las variables. Si falta una credencial, la aplicación **no
arranca** y lo dice en el registro de Railway: es preferible a descubrirlo con
el primer cliente que intente registrarse.

Falta todavía el webhook de SNS para rebotes y quejas (blueprint `webhooks/`),
que es lo que llenará `suppressions` sin intervención. Para unos pocos correos
transaccionales se revisa a mano en `mail_log`; para campañas es obligatorio.

## Comprobar que está vivo: `/health`

```
curl https://app.sobreala.com/health
```

Devuelve JSON y se lee desde fuera, sin entrar a ningún panel:

```json
{"app": "up", "mail": "ses", "database": "up", "indexes": true, "name": "sobreala_app"}
```

`mail` es el backend de correo con el que arrancó el proceso. Es la forma más
rápida de saber desde fuera si un despliegue tomó las variables nuevas, y nombra
un modo, nunca una credencial.

| Lo que ves | Lo que significa |
|---|---|
| `200` con `database: up` | Todo bien |
| `503` con `database: down` | La aplicación vive pero no alcanza Atlas. Casi siempre la lista de acceso de Atlas, que debe permitir cualquier origen porque Railway no tiene dirección fija |
| `502` y ni siquiera contesta | No llega a la aplicación. Si el 502 lo firma Cloudflare, mira el proxy del registro DNS antes que el código |

**Lo que ve el visitante cuando la base no responde.** Un 503 con una página en
español que dice que el servicio no está disponible, no el «Internal Server
Error» pelado del servidor. Las páginas que no consultan la base, como los
formularios de entrada y registro, siguen dibujándose normalmente: por eso un
Atlas inaccesible se veía antes como un sitio que carga pero revienta al enviar
cualquier formulario. El detalle técnico se queda en los registros de Railway.

`indexes` dice si los índices están creados. **La aplicación no los crea al
arrancar a propósito**: antes sí lo hacía, y una base momentáneamente inaccesible
mataba todos los procesos al importar, lo que la plataforma reportaba como un 502
pelado sin nada legible. Ahora se crean de forma perezosa, en la primera petición
que lo consiga. El índice único del correo es lo que impide cuentas duplicadas,
así que no puede faltar en silencio: por eso `/health` lo informa.

## Base de datos

`MONGODB_URI` acepta un clúster de Atlas. La contraseña va en `.env`, que está
en `.gitignore`, y la dirección del servidor debe estar en la lista de acceso de
Atlas. Railway usa direcciones que cambian, así que lo habitual ahí es permitir
cualquier origen y proteger la base con credenciales fuertes.

Los índices los define `db.py` y se crean de forma perezosa, en la primera
petición que lo consiga, no al arrancar. Los tres que importan:

- `accounts.email_normalized` **único**: impide cuentas repetidas aunque dos
  registros lleguen a la vez.
- `account_tokens` por `{account_id, purpose}`: un solo código vivo por cuenta,
  porque emitir uno borra el anterior.
- `account_tokens.purge_at` **TTL**: Mongo borra el código pasado su vencimiento
  más siete días de margen. Ese margen es lo que permite distinguir en la
  bitácora un código vencido de uno que nunca existió.

### Colecciones de registro

Dos bitácoras. Las dos son internas: solo las lee el administrador, nunca el
cliente.

| Colección | Qué guarda |
|---|---|
| `mail_log` | Un documento por cada correo del sistema que se intentó enviar, **con el cuerpo completo**. Destinatario, asunto, backend usado, `status` (`sent` o `failed`), el identificador que devolvió el proveedor, el error si falló, el HTML y el texto tal como salieron, y `purpose` (`confirm` o `exists`) |
| `auth_events` | Un documento por cada intento de registro, entrada, reenvío, confirmación y salida. `kind`, `outcome`, la dirección tal como se escribió y normalizada, `account_id` cuando se conoce, IP y navegador |

Se guarda el cuerpo del correo porque cuando alguien dice que no le llegó la
confirmación, la pregunta útil es qué salió exactamente del servidor, y hay que
poder responderla meses después.

**Ninguna de las dos tiene índice TTL**, a diferencia de `account_tokens` y
`rate_limits`. El historial se conserva hasta que se decida otra cosa: es con lo
que se investiga un abuso o un «no puedo entrar» semanas más tarde. Cada
documento de `auth_events` pesa unos 300 bytes, así que cien mil intentos son
unos 30 MB.

Tres cosas que conviene no perder de vista:

- **La contraseña no se escribe nunca en ninguna de las dos**, ni en claro, ni
  truncada, ni como hash. Hay una prueba que recorre los dos registros y falla
  si aparece.
- **`auth_events` sabe más que la pantalla, a propósito.** Guarda
  `already_registered` y el `account_id` de un intento fallido contra una cuenta
  real. La regla 7 de `CLAUDE.md` dice qué se le cuenta al visitante, no que la
  plataforma deba ignorar su propio tráfico. Es lo que hace visible un ataque de
  fuerza bruta contra una cuenta concreta.
- **No sirven para diagnosticar una base caída.** Viven en el mismo Mongo, así
  que si Atlas no responde no se escribe nada. Para eso están `/health` y los
  registros de Railway.

## Decisiones que conviene no deshacer

- **Del token solo se guarda su hash.** Quien copie la base no puede confirmar
  cuentas ajenas con lo que hay dentro.
- **La pantalla nunca dice si un correo ya tiene cuenta.** Registrarse con una
  dirección existente responde igual que un registro nuevo; al dueño se le avisa
  por correo.
- **`bcrypt` ignora lo que pase de 72 bytes**, así que una contraseña más larga
  se rechaza en vez de truncarse en silencio.
- **Confirmar el correo es un campo, no un estado.** Los estados de
  `CLAUDE.md` describen la aprobación comercial, que es otra cosa.
- **Todo el español está en `i18n.py`.** Las plantillas no llevan texto propio.

## Pruebas

```
python -m pytest backend/tests -q
```

Usan `MONGODB_TEST_URI`, nunca el clúster real: crean y borran su propia base.
Cubren el correo normalizado, que la contraseña y el código no queden en claro,
que el código sirva una sola vez, que muera a los cinco intentos, que uno
vencido se rechace, que reenviar invalide el anterior, y que un correo repetido
responda igual que uno nuevo — también cuando el envío falla y el registro se
deshace.

## Desplegar en Railway

El orden importa: **primero el despliegue, después el dominio**, porque el
certificado necesita que el servicio ya exista.

1. En **railway.app**, crear un proyecto desde el repositorio de GitHub. Railway
   reconoce que es Python por el `requirements.txt` de la raíz y arranca con el
   `Procfile`. Ese archivo tiene que listar los paquetes uno por uno: una línea
   `-r backend/requirements.txt` la entiende pip pero no Railpack, y el
   despliegue falla con «could not determine how to build the app».
   **El `Procfile` no lleva comentarios**: Railway lee cada línea con dos
   puntos como un servicio aparte, y uno de ellos acabó creado y caído. En
   local no se usa, porque gunicorn no corre en Windows: ahí se arranca con
   `python backend/wsgi.py`.
2. Pegar las variables de abajo en su panel, **`APP_BASE_URL` incluida**: en
   producción el panel no arranca si apunta a `127.0.0.1` (`Config.check()`),
   y puede ir puesta aunque el dominio todavía no exista.
3. En **Atlas**, permitir la conexión desde cualquier origen. Los servidores de
   Railway no tienen dirección fija; la base queda protegida por sus credenciales.
4. En **Railway**, agregar el dominio `app.sobreala.com`. Te dará un destino.
5. En **Cloudflare**, crear un `CNAME` de `panel` hacia ese destino, **en gris,
   sin el proxy naranja**, para que Railway pueda emitir el certificado.
   **Con el proxy encendido antes de que el certificado exista, Cloudflare no
   puede hablar con el origen y responde 502 en todas las rutas.** Ya pasó una
   vez. Cuando el certificado esté emitido se puede encender el naranja, y
   entonces el modo SSL tiene que ser **Full (strict)**: con «Flexible»,
   Cloudflare habla HTTP con el origen y la galleta de sesión, que va marcada
   como segura, no deja iniciar sesión.

### Variables para el panel de Railway

`.env` no se sube, está en `.gitignore`. Estas se escriben en Railway:

```
FLASK_ENV=production
SECRET_KEY=            (una NUEVA, distinta a la de tu computadora)
MONGODB_URI=           (la de Atlas)
MONGODB_DB=sobreala_app
APP_BASE_URL=https://app.sobreala.com
PUBLIC_SITE_URL=https://sobreala.com
CONFIRMATION_CODE_MINUTES=30
MAIL_BACKEND=file      (hasta que SES esté verificado; después ses)
SYSTEM_FROM_EMAIL=notifications@sobreala.com
SYSTEM_FROM_NAME=Sobreala
```

Con `MAIL_BACKEND=ses` se suman `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`,
`AWS_REGION=us-east-2` y los conjuntos de configuración de `docs/ses.md`.

### Dos cosas que cambian solas en producción

Con `FLASK_ENV=production`, `config.py` apaga el modo de depuración, exige
`SECRET_KEY` en vez de usar la de relleno, y marca la galleta de sesión como
segura. Y `app.py` activa `ProxyFix`, sin el cual todas las visitas llegarían con
la dirección del proxy de Railway y el límite de intentos las trataría como una
sola persona.

### La base de datos

La aplicación usa la base **`sobreala_app`** del clúster de Atlas, y las pruebas
`sobreala_test`, que crean y borran.

## Pendiente

Recuperar contraseña y cambio de correo, que reutilizan `models/token.py` y solo
añaden un `purpose`. Después: aprobación desde el panel de administración,
contactos, campañas y envío real.
