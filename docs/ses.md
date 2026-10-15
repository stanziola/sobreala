# Amazon SES: saber qué pasó con cada correo

Qué hay que hacer en Amazon y en Cloudflare para que el panel se entere de lo
que pasa con cada correo después de salir: si se entregó, si rebotó, si lo
abrieron, si pulsaron un enlace o si alguien lo marcó como spam. Y qué hacer
cuando no le llega a una dirección institucional, como las de la UTP.

El código ya está: recibe el aviso en `POST /webhooks/ses/<secreto>`, lo guarda
y anula sola la dirección que rebota o se queja. Lo que falta es conectar
Amazon con esa dirección, y eso se hace a mano, una vez, en este orden.

---

## Lo que se puede saber, y lo que no

| Pregunta | ¿Se sabe? |
|---|---|
| ¿Salió de Amazon? | Sí |
| ¿El servidor del destinatario lo aceptó? | Sí: «entregado» |
| ¿Rebotó, y por qué? | Sí, con el motivo que dio el otro servidor |
| ¿Lo abrieron? ¿Pulsaron un enlace? | Sí, solo en campañas |
| ¿Lo marcaron como spam? | Solo si la persona pulsa «es spam», y solo en Outlook.com, Hotmail y Yahoo |
| **¿Cayó en la carpeta de spam?** | **No. Nadie lo sabe desde fuera** |

«Entregado» quiere decir que el servidor del otro lado **lo aceptó**. Si después
lo puso en la bandeja, en correo no deseado o en cuarentena, no se lo cuenta a
nadie. Lo que sí se ve es la sombra: si a un dominio le llegan cien correos y no
se abre ninguno, van a parar a spam.

Las aperturas tampoco son exactas: Apple Mail las abre todas solo (cuenta de
más) y quien no carga imágenes no avisa (cuenta de menos). Sirven para comparar
un envío con otro, no como cifra absoluta.

---

## 1. El secreto, y desplegar

Va primero porque Amazon, al crear la suscripción del paso 3, llama a la
dirección del panel y espera respuesta.

1. Generar una cadena larga al azar:

   ```
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

2. En Railway, en las variables del servicio, crear `SES_WEBHOOK_SECRET` con
   ese valor.
3. Desplegar.

Sin esa variable, la dirección del aviso responde 404 a todo. Es a propósito.

## 2. El tema de SNS

SNS es el buzón por el que Amazon manda los avisos.

1. Consola de AWS, **arriba a la derecha, región Ohio (us-east-2)**: es donde
   está verificada la identidad de SES. Un tema en otra región no se puede
   elegir desde SES.
2. **SNS → Temas → Crear tema.**
3. Tipo **Estándar** (no FIFO). Nombre: `sobreala-ses-events`.
4. Lo demás como viene. **Crear tema.**
5. Copiar el **ARN** que aparece arriba. Tiene esta forma:
   `arn:aws:sns:us-east-2:123456789012:sobreala-ses-events`.

## 3. La suscripción al panel

1. En el tema recién creado: **Crear suscripción.**
2. Protocolo: **HTTPS**.
3. Punto de enlace:
   `https://app.sobreala.com/webhooks/ses/<el secreto del paso 1>`
4. **«Habilitar la entrega de mensajes sin procesar» se deja apagado.** El panel
   espera el sobre de SNS, con el aviso dentro.
5. **Crear suscripción.**

El panel confirma la suscripción solo, en unos segundos. Al recargar, el estado
tiene que decir **Confirmada**.

**Si se queda en «Pendiente de confirmación»**, casi siempre es Cloudflare: el
panel va detrás de su WAF, y una petición de un servidor de Amazon sin navegador
puede parecerle un bot. Mirar en Cloudflare → Seguridad → Eventos si hay un
bloqueo o un desafío sobre `/webhooks/ses/`. Si lo hay, crear una regla que
**omita** el modo de lucha contra bots y las reglas administradas solo para la
ruta que empieza por `/webhooks/`, y en la consola de SNS pulsar **Solicitar
confirmación** otra vez.

## 4. Los dos conjuntos de configuración

Un conjunto de configuración le dice a SES qué avisar y a dónde. Son dos porque
a un código de confirmación no se le mide nada.

**SES → Configuración → Conjuntos de configuración → Crear conjunto.**

### `sobreala-campaigns`

1. Nombre: `sobreala-campaigns`. Lo demás como viene. **Crear.**
2. Dentro, pestaña **Destinos de eventos → Agregar destino.**
3. Tipos de evento: **Entregas, Rebotes, Quejas, Rechazos, Aperturas y Clics.**
   Sin «Envíos» (eso ya lo anota el panel al mandar) ni «Errores de
   representación» ni «Retrasos en la entrega».
4. Destino: **Amazon SNS**, y elegir `sobreala-ses-events`.
5. Nombre del destino: `panel`. **Siguiente** y **Agregar destino.**

### `sobreala-system`

Igual, con nombre `sobreala-system`, y en el paso 3 **sin Aperturas ni Clics**:
solo Entregas, Rebotes, Quejas y Rechazos. Mismo tema.

## 5. Los nombres, en Railway

| Variable | Valor |
|---|---|
| `SES_CONFIGURATION_SET` | `sobreala-campaigns` |
| `SES_TRANSACTIONAL_CONFIGURATION_SET` | `sobreala-system` |
| `SES_TOPIC_ARN` | El ARN del paso 2 |

Desplegar. Desde aquí cada correo sale con su conjunto, y los avisos empiezan a
llegar.

`SES_TOPIC_ARN` es opcional, pero con ella el panel descarta cualquier aviso que
no venga de ese tema.

## 6. Comprobar DKIM

DKIM es la firma que prueba que el correo lo mandó quien dice. Sin ella,
Microsoft y Gmail desconfían, y desde fuera no se puede ver si está bien.

1. **SES → Identidades → sobreala.com**, pestaña **Autenticación**.
2. «Configuración de DKIM» tiene que decir **Correcto** (Successful).
3. Si dice otra cosa: SES enseña tres registros CNAME que acaban en
   `._domainkey.sobreala.com`. Tienen que estar en Cloudflare → DNS **con la
   nube gris (solo DNS)**. Con la nube naranja Cloudflare los esconde detrás de
   su proxy y la firma no se puede comprobar.

## 6b. El subdominio de las campañas, y los dominios de los clientes

**`envios.sobreala.com` es otra identidad**, aparte de `sobreala.com`: de ahí
salen las campañas de quien no tiene dominio propio, y separarla es lo que
impide que su reputación toque la de los códigos de confirmación.

1. **SES → Identidades → Crear identidad → Dominio**: `envios.sobreala.com`,
   Easy DKIM, RSA 2048.
2. Sus tres CNAME en Cloudflare, **en gris**, igual que los de `sobreala.com`.
3. Esperar a que diga **Verificada**. `SENDING_DOMAIN` ya vale eso por omisión:
   no hace falta ponerla en Railway.
4. **Su propio MAIL FROM** (octubre de 2026). Sin él, Gmail enseña «enviado
   por: us-east-2.amazonses.com» debajo del remitente; con él, el dominio de
   Sobreala. No es tema legal: es el dominio del sobre, adonde vuelven los
   rebotes.
   - En la identidad `envios.sobreala.com`, **MAIL FROM personalizado →
     Editar**: dominio `mail.envios.sobreala.com`, y en «Comportamiento si falla
     el MX», **usar el MAIL FROM predeterminado** (así nunca se rechaza un
     envío por esto).
   - En Cloudflare, los dos registros que enseña Amazon, **en gris**:
     - MX `mail.envios` → `feedback-smtp.us-east-2.amazonses.com`, prioridad 10;
     - TXT `mail.envios` → `v=spf1 include:amazonses.com ~all`.

     La región es la de la cuenta, la de `AWS_REGION`.
   - Cuando diga **Correcto**, mandarse una campaña de prueba a Gmail: en
     «Mostrar original», «enviado por» tiene que decir
     `mail.envios.sobreala.com`.

**Los dominios de los clientes no se crean a mano.** El panel los crea, los
consulta y los borra por la API v2 (`services/ses_identity.py`), y desde
octubre de 2026 **les pone su MAIL FROM**, `envios.<dominio>`: el cliente ve
cinco registros en vez de tres (los tres CNAME, un MX y un TXT), y a un
dominio conectado antes se le pide al abrir Remitente. Para eso el usuario de
IAM necesita, además de enviar:

```json
{
  "Effect": "Allow",
  "Action": ["ses:CreateEmailIdentity", "ses:GetEmailIdentity",
             "ses:DeleteEmailIdentity",
             "ses:PutEmailIdentityMailFromAttributes"],
  "Resource": "arn:aws:ses:us-east-2:TU_CUENTA:identity/*"
}
```

**El último permiso va antes de desplegar**: sin él, conectar un dominio da
error (la identidad se crea y el MAIL FROM no).

## 7. Los informes de DMARC

Con `_dmarc.sobreala.com` en `v=DMARC1; p=none;` y nada más, la política está
publicada, pero nadie recibe los informes de quién manda correo en nombre del
dominio y si pasa las comprobaciones.

La forma más sencilla, sin montar nada:

1. Cloudflare → **Seguridad del correo → Administración de DMARC** → Habilitar.
2. Cloudflare agrega su dirección `rua=` al registro y enseña los informes en
   esa misma pantalla, por remitente.

Se deja en `p=none` hasta ver unas semanas de informes limpios. Subirlo a
`quarantine` antes de mirarlos puede tirar correo legítimo que salga por otro
lado (Cloudflare, por ejemplo).

## 8. Salir del sandbox

Mientras la cuenta esté en sandbox, **SES solo entrega a direcciones
verificadas**: un código a cualquier otra dirección ni siquiera sale, y en el
panel se ve como «No salió» con el error `Email address is not verified`. Eso
por sí solo explica que no le llegue a nadie de la UTP.

**SES → Panel de la cuenta → Solicitar acceso a producción.** Lo que se le
prometa a Amazon ahí (bajas, supresiones y umbrales) tiene que estar
funcionando.

---

## Probarlo de punta a punta

SES tiene direcciones de prueba que responden siempre lo mismo, sirven en
sandbox y no cuentan contra la reputación:

| Dirección | Qué responde |
|---|---|
| `success@simulator.amazonses.com` | Entregado |
| `bounce@simulator.amazonses.com` | Rebote permanente |
| `complaint@simulator.amazonses.com` | Entregado y después queja |

1. Importar las tres como contactos de una cuenta de prueba y mandarles una
   campaña.
2. En unos segundos, en Enviados (`/campaigns/sent`), la fila tiene que decir 2
   entregados, 1 rebote y 1 queja.
3. En Contactos → Supresiones, `bounce@` sale como rebote y `complaint@` como
   queja.
4. Para el correo del sistema: registrarse con `bounce@simulator.amazonses.com`
   y buscar esa dirección en **Administración → Correos del sistema**. Tiene que
   decir «Rebotó», con el motivo.

Si nada cambia, mirar el registro de Railway: cada aviso deja una línea que
empieza por `[ses]`. Sin ninguna línea, el aviso no está llegando (pasos 2 a 5).

---

## Cuando no le llega a una dirección institucional

Buscar la dirección en **Administración → Correos del sistema** y leer la
última fila:

| Dice | Qué pasó | Qué hacer |
|---|---|---|
| **No salió** | Amazon no lo aceptó | El error lo dice. Si es `not verified`, es el sandbox (paso 8) |
| **Enviado a Amazon, sin respuesta todavía** | El aviso no está llegando | Configuración: pasos 2 a 5 |
| **Rebotó** | El otro servidor lo rechazó | El motivo lo dice. `550 5.7.x` suele ser una política del dominio: escribirle a sistemas |
| **Entregado** | El otro servidor lo aceptó | Está en correo no deseado o en cuarentena. Escribirle a sistemas |

La UTP usa **Microsoft 365** (su MX es `utp-ac-pa.mail.protection.outlook.com`).
Microsoft **pone en cuarentena sin rebotar**, así que un correo que el panel ve
«Entregado» puede no estar en ninguna carpeta que la persona pueda ver. Solo lo
puede mirar su equipo de sistemas. Antes de escribirles, que DKIM esté
**Correcto** (paso 6): es lo primero que van a revisar.

### El mensaje para sistemas

> Asunto: Correos de sobreala.com retenidos en Microsoft 365
>
> Buenos días,
>
> Soy <tu nombre>, de Sobreala (sobreala.com), una plataforma panameña de
> correo. Personas de la UTP se registran en nuestro servicio con su correo
> institucional y no reciben el código de confirmación. Nuestro proveedor
> (Amazon SES) confirma que su servidor aceptó el mensaje, así que sospechamos
> que queda en cuarentena o en correo no deseado.
>
> ¿Podrían revisarlo en su lado?
>
> 1. En el **seguimiento de mensajes** (Exchange admin center → Mail flow →
>    Message trace), buscar correos del remitente `notifications@sobreala.com`
>    a `<dirección de la persona>` el `<fecha>` cerca de las `<hora>`.
> 2. Si aparecen en **cuarentena** (Microsoft Defender → Email & collaboration →
>    Review → Quarantine), el motivo que indique.
> 3. Si es posible, agregar el dominio `sobreala.com` a los remitentes
>    permitidos (Tenant Allow/Block List).
>
> Nuestros datos de envío, por si les sirven: los correos salen por Amazon SES
> (región us-east-2), firmados con DKIM para `sobreala.com`, con SPF en
> `mail.sobreala.com` y DMARC publicado.
>
> Quedo atento, y gracias.

Revisar antes de mandarlo que el remitente sea el que está en `SYSTEM_FROM_EMAIL`
de Railway, y poner la dirección, la fecha y la hora de la fila de «Correos del
sistema».
