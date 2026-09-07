# Backend de Panamails

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
| `/registro` | Crear cuenta y recibir el enlace de confirmación |
| `/revisa-tu-correo` | Pantalla posterior al registro |
| `/confirmar/<token>` | Confirma la dirección; el enlace vale una sola vez |
| `/reenviar-confirmacion` | Pide otro enlace |
| `/entrar` · `/salir` | Sesión |
| `/panel` | Panel vacío, con aviso si el correo no está confirmado |

## Correo

`MAIL_BACKEND` decide cómo se envía:

| Valor | Cuándo |
|---|---|
| `file` | Desarrollo. Guarda el mensaje en `backend/.mail_outbox/` y escribe el enlace en la consola. No manda nada |
| `smtp` | Puente. Un servidor SMTP corriente, por ejemplo Gmail con contraseña de aplicación |
| `ses` | Producción. Amazon SES por su API |

**Sobre `smtp`.** `CLAUDE.md` descarta SMTP para las **campañas**, que son envíos
masivos en nombre de terceros. Unos pocos correos de confirmación son otra cosa,
y sirve como puente mientras SES sale del modo de pruebas. Dos avisos:

- `MAIL_SMTP_FROM` tiene que ser el mismo buzón que autentica. Enviar como
  `cuenta@mail.panamails.com` a través de Gmail falla SPF y DKIM y cae en spam.
  El código pone ese buzón como remitente y deja la dirección de la marca en
  `Responder a`.
- Gmail limita alrededor de 500 destinatarios al día y puede bloquear una cuenta
  que empiece a parecer un emisor masivo.

**Los correos del sistema son transaccionales**: no llevan enlace de baja ni
marca de agua. Esas reglas son para las campañas de los clientes.

## Comprobar que está vivo: `/salud`

```
curl https://panel.panamails.com/salud
```

Devuelve JSON y se lee desde fuera, sin entrar a ningún panel:

```json
{"app": "up", "database": "up", "indexes": true, "name": "panamails_app"}
```

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
así que no puede faltar en silencio: por eso `/salud` lo informa.

## Base de datos

`MONGODB_URI` acepta un clúster de Atlas. La contraseña va en `.env`, que está
en `.gitignore`, y la dirección del servidor debe estar en la lista de acceso de
Atlas. Railway usa direcciones que cambian, así que lo habitual ahí es permitir
cualquier origen y proteger la base con credenciales fuertes.

Los índices los define `db.py` y se crean de forma perezosa, en la primera
petición que lo consiga, no al arrancar. Los tres que importan:

- `accounts.email_normalized` **único**: impide cuentas repetidas aunque dos
  registros lleguen a la vez.
- `account_tokens.token_hash` **único**.
- `account_tokens.purge_at` **TTL**: Mongo borra el token pasado su vencimiento
  más siete días de margen. Ese margen es lo que permite responder «este enlace
  venció» en vez de «este enlace no existe».

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
  que si Atlas no responde no se escribe nada. Para eso están `/salud` y los
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
Cubren el correo normalizado, que la contraseña y el token no queden en claro,
que el enlace sirva una sola vez, que uno vencido se rechace, que reenviar
invalide el anterior, y que un correo repetido responda igual que uno nuevo.

## Desplegar en Railway

El orden importa: **primero el despliegue, después el dominio**, porque el
certificado necesita que el servicio ya exista.

1. En **railway.app**, crear un proyecto desde el repositorio de GitHub. Railway
   reconoce que es Python por el `requirements.txt` de la raíz y arranca con el
   `Procfile`. Ese archivo tiene que listar los paquetes uno por uno: una línea
   `-r backend/requirements.txt` la entiende pip pero no Railpack, y el
   despliegue falla con «could not determine how to build the app».
2. Pegar las variables de abajo en su panel. `APP_BASE_URL` se deja para el
   paso 5.
3. En **Atlas**, permitir la conexión desde cualquier origen. Los servidores de
   Railway no tienen dirección fija; la base queda protegida por sus credenciales.
4. En **Railway**, agregar el dominio `panel.panamails.com`. Te dará un destino.
5. En **Cloudflare**, crear un `CNAME` de `panel` hacia ese destino, **en gris,
   sin el proxy naranja**, para que Railway pueda emitir el certificado.
   **Con el proxy encendido antes de que el certificado exista, Cloudflare no
   puede hablar con el origen y responde 502 en todas las rutas.** Ya pasó una
   vez. Cuando el certificado esté emitido se puede encender el naranja, y
   entonces el modo SSL tiene que ser **Full (strict)**: con «Flexible»,
   Cloudflare habla HTTP con el origen y la galleta de sesión, que va marcada
   como segura, no deja iniciar sesión.
6. Poner `APP_BASE_URL=https://panel.panamails.com` y volver a desplegar.

**El paso 6 es el que más se olvida.** Sin él los correos salen con enlaces a
`127.0.0.1` y la confirmación falla justo ahí.

### Variables para el panel de Railway

`.env` no se sube, está en `.gitignore`. Estas se escriben en Railway:

```
FLASK_ENV=production
SECRET_KEY=            (una NUEVA, distinta a la de tu computadora)
MONGODB_URI=           (la de Atlas)
MONGODB_DB=panamails_app
APP_BASE_URL=https://panel.panamails.com
MAIL_BACKEND=smtp
SYSTEM_FROM_EMAIL=panamails.info@gmail.com
SYSTEM_FROM_NAME=Panamails
MAIL_SMTP_HOST=smtp.gmail.com
MAIL_SMTP_PORT=587
MAIL_SMTP_USER=        (tu correo)
MAIL_SMTP_PASSWORD=    (la contraseña de aplicación)
MAIL_SMTP_FROM=        (el mismo correo)
```

### Dos cosas que cambian solas en producción

Con `FLASK_ENV=production`, `config.py` apaga el modo de depuración, exige
`SECRET_KEY` en vez de usar la de relleno, y marca la galleta de sesión como
segura. Y `app.py` activa `ProxyFix`, sin el cual todas las visitas llegarían con
la dirección del proxy de Railway y el límite de intentos las trataría como una
sola persona.

### La base de datos

El clúster tiene `panamails` y `panamails_demo` de dos intentos anteriores, con
otro modelo de datos. Esta aplicación usa **`panamails_app`**, aparte, para no
mezclarse con ellos.

## Pendiente

Recuperar contraseña y cambio de correo, que reutilizan `models/token.py` y solo
añaden un `purpose`. Después: aprobación desde el panel de administración,
contactos, campañas y envío real.
