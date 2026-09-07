# Panamails

Plataforma de email marketing para negocios de Panamá. Las empresas clientes
suben sus contactos, arman campañas (ofertas, recordatorios, eventos) y las
envían desde un panel web. Panamails también les ofrece el diseño de las piezas
HTML como servicio.

Mercado principal: Santiago de Veraguas y el interior. Cliente típico:
cooperativas de ahorro y crédito, colegios privados, gremios, universidades y
PyMEs — organizaciones que ya tienen una lista de correos armada por otra razón.

**Estado: proyecto nuevo.** Existen la marca (`brand/`) y el sitio público
(`landing/`, cuatro páginas estáticas generadas con Jinja2). Todo el backend, el
panel del cliente y el panel de administración están por construir.

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
├── landing/                # → Cloudflare Pages (sitio público, ver landing/README.md)
│   ├── build_site.py       # genera las páginas; único punto de entrada
│   ├── content.py          # todos los textos del sitio, en español
│   ├── src/                # plantillas Jinja2 (base, parciales, páginas) y site.css
│   ├── assets/             # css, js, fonts, img (fonts, img y css/site.css son generados)
│   ├── index.html          # GENERADO
│   ├── como-funciona/      # GENERADO
│   ├── precios/            # GENERADO (precios leídos de docs/pricing.md al construir)
│   └── nosotros/           # GENERADO
└── backend/                # → Railway
    ├── wsgi.py
    ├── config.py
    ├── requirements.txt
    ├── blueprints/
    │   ├── auth/           # registro, confirmación de correo, login. HECHO
    │   ├── contacts/       # importación, etiquetas, supresiones
    │   ├── campaigns/      # crear, programar, enviar, pausar/retomar
    │   ├── analytics/      # métricas, exportar CSV/PDF
    │   ├── billing/        # planes, cuota, recargas, acumulado
    │   ├── webhooks/       # SNS de SES, PayPal, Yappy
    │   └── admin/          # panel de administración
    ├── models/
    ├── services/
    │   ├── mailer.py       # correo del sistema: file | smtp | ses
    │   ├── security.py     # contraseñas, CSRF, límite de intentos
    │   ├── ses.py
    │   ├── suppression.py
    │   ├── importer.py
    │   └── payments/
    ├── email_templates/    # plantillas prediseñadas del producto
    ├── templates/          # Jinja: panel del cliente y admin
    ├── static/
    └── tests/
```

Un solo repositorio. `landing/` se despliega a Cloudflare Pages y `backend/` a
Railway; cada plataforma apunta a su carpeta.

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

---

## Modelo de datos

### `accounts`
Cuenta de una empresa cliente. Guarda plan, cuota del mes, saldo acumulado,
estado y configuración de remitente.

Estados: `registered` → `approved` → `active` → `suspended`

| Estado | Puede |
|---|---|
| `registered` | Explorar el panel, importar contactos, armar campañas. **No comprar ni enviar.** |
| `approved` | Comprar un plan. Lo aprueba Luis manualmente tras contactar a la empresa. |
| `active` | Enviar. |
| `suspended` | Nada. Corte automático por rebotes/quejas, o manual. |

### `contacts`
**Un solo documento por dirección de correo por cuenta.** Índice único sobre
`{account_id, email_normalized}`. Normalización: sin espacios, minúsculas.

Las "listas" son un arreglo de **etiquetas** en el mismo documento, no
colecciones separadas. Esto garantiza que un contacto en varias listas:
cuente una sola vez contra el límite, reciba un solo correo, y consuma un solo
correo de la cuota.

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

### `campaigns`
Incluye la **posición de envío** (hasta qué destinatario se envió), necesaria
para pausar por límite de cuota y retomar desde ahí.

### `events`
Un registro por evento de SES (enviado, entregado, rebote, queja, apertura,
clic). Es lo que más crece: ~3 eventos por correo, ~200 bytes cada uno.
**Retención: 12 meses en detalle, después solo totales por campaña.**

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
7. **Las pantallas nunca revelan si una dirección ya tiene cuenta.** Registrarse
   con un correo existente responde igual que uno nuevo; al dueño se le avisa
   por correo.
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

Validación automática en cada subida — rechazar: `<script>`, `<iframe>`,
`<object>`, atributos de evento, CSS/JS externo, formularios, HTML mal formado y
**cualquier pieza de más de 102 KB** (pasado eso Gmail recorta el correo y se
pierden la baja y la marca de agua).

Aprobación manual solo la **primera** subida de cada cliente; después queda
habilitado. Todo HTML queda guardado y revisable desde el admin.

### Límites de importación

| Límite | Valor |
|---|---|
| Importaciones por día | 10 por cuenta |
| Filas por importación | El límite de contactos del plan |
| Tamaño de archivo | 5 MB |
| Importaciones simultáneas | 1 por cuenta |

Procesar el CSV **en streaming**, nunca cargarlo entero en memoria.

---

## Panel de administración

Aprobar cuentas · ver analytics de cada cliente · pausar y suspender · cambiar
plan · cargar plantillas prediseñadas · revisar rebotes por cliente · aprobar
HTML de clientes.

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
PAYPAL_CLIENT_ID
PAYPAL_SECRET
YAPPY_MERCHANT_ID
YAPPY_SECRET
```

Nunca commitear el `.env`. En Railway van como variables del servicio.

---

## Pendientes de decisión

- Confirmar con Yappy (yappy@bgeneral.com / 800-5000) si soporta cobros
  recurrentes. Si no, el recurrente va solo por PayPal y a los de Yappy se les
  envía enlace de pago antes de cada vencimiento.
- Pedir acceso a producción de SES al empezar a desarrollar, no al lanzar: las
  cuentas nuevas arrancan en sandbox (200 correos/día, solo a direcciones
  verificadas) y la aprobación tarda ~24h.
- Presupuestar el salto de MongoDB Atlas: los eventos llenan los 512 MB del
  tier gratuito en unos 7 meses con 6 Básico + 3 Negocio + 1 Empresa.
