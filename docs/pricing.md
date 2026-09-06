# Panamails — Planes y precios

Documento de referencia interno. Define los planes comerciales, sus límites y las
reglas de negocio asociadas.

---

## Planes

| | Básico | Negocio | Empresa | Corporativo |
|---|---|---|---|---|
| **Precio mensual** | $35 | $60 | $120 | $300 |
| **Precio anual** (2 meses gratis) | $350 | $600 | $1,200 | $3,000 |
| Contactos | 1,000 | 3,000 | 10,000 | 50,000 |
| Correos por mes | 5,000 | 15,000 | 50,000 | 250,000 |
| Campañas a lista completa | 5 | 5 | 5 | 5 |
| Precio por correo | $0.0070 | $0.0040 | $0.0024 | $0.0012 |
| Listas | 1 | Ilimitadas | Ilimitadas | Ilimitadas |
| Plantillas prediseñadas | ✅ | ✅ | ✅ | ✅ |
| Subir tu propio HTML | — | ✅ | ✅ | ✅ |
| **Correos sin marca de agua** | — | ✅ | ✅ | ✅ |
| Plantilla personalizada con su marca | — | 1 | 3 | 5 |
| Analytics completo | ✅ | ✅ | ✅ | ✅ |
| Exportar CSV y PDF | ✅ | ✅ | ✅ | ✅ |
| Usuarios | 1 | 2 | 3 | 5 |
| Soporte | Email 48h | Email 24h | WhatsApp, mismo día | WhatsApp prioritario |
| Onboarding guiado | — | — | — | ✅ |

**Corporativo se publica sin precio visible**: *"A la medida — contáctanos"*.
Los $300 son referencia interna, no una promesa pública.

### Complementos

| | Precio |
|---|---|
| Recarga de 1,000 correos | $15 |
| Diseño de pieza HTML adicional | $60 |

### Regla de proporción

El límite de correos es siempre **5x el límite de contactos**. Cualquier plan
nuevo debe respetarla: permite 5 campañas mensuales a la lista completa.

---

## Reglas de negocio

### Suscripción

- Sin permanencia mínima. Cancelable desde el panel en cualquier momento.
- El plan anual se paga por adelantado y equivale a 10 meses.
- Métodos de pago: Yappy, PayPal y tarjeta vía PayPal.
- **Pendiente de confirmar con Yappy**: si soporta cobros recurrentes. Si no,
  el cobro recurrente va solo por PayPal y a los clientes de Yappy se les envía
  un enlace de pago antes de cada vencimiento.

### Acumulación de correos

- Los correos no usados **pasan al mes siguiente y vencen ahí**. No se acumulan
  indefinidamente.
- Al enviar se consumen **primero los acumulados** (los más viejos), después los
  del mes corriente. Este orden es obligatorio: al revés, lo acumulado vencería
  siempre sin usarse.
- El saldo acumulado se pierde al cancelar.
- Consecuencia a considerar: la capacidad máxima real de un plan en un mes pico
  es el doble de su límite mensual.

### Al llegar al límite de correos

1. Aviso al cliente al **80%** del consumo.
2. Al **100%** la campaña **se pausa** — no falla ni se pierde.
3. Al comprar una recarga, el envío **retoma desde el correo donde se detuvo**.

Requiere guardar la posición de envío de cada campaña, no solo un contador global.

### Al llegar al límite de contactos

- La importación se detiene y se notifica que debe subir de plan.
- Los contactos ya cargados no se borran.

### Plantilla personalizada (Negocio en adelante)

- Se diseña **una vez** con la marca, colores, logo y tipografía del cliente; él
  la reutiliza cada mes cambiando textos e imágenes.
- Hasta **2 rondas de cambios**, entrega en **3 días hábiles**.
- El cliente entrega textos, imágenes y logo.
- **No acumulable** de un mes al siguiente.

### Marca de agua (solo Básico)

- Los correos enviados desde el plan **Básico** llevan una firma discreta al pie:
  *"Enviado con Panamails"*, con enlace al sitio.
- **A partir de Negocio los correos salen sin ninguna marca.**
- La firma va separada del enlace de baja: el enlace de baja de un clic es
  obligatorio en **todos** los planes y nunca se quita.
- Doble función: incentivo de upgrade, y publicidad gratuita en cada correo que
  envía un cliente de entrada.

### Onboarding (Corporativo)

- 1 sesión de hasta 2 horas, por videollamada o presencial: importación de
  contactos, configuración del dominio de envío, primera campaña y recorrido
  por el panel.

---

## Modelo de datos: reglas que afectan al negocio

### Contactos únicos

Cada correo electrónico existe **una sola vez por cuenta**. Las "listas" son
etiquetas sobre ese contacto único, no copias separadas.

| Garantía | Efecto |
|---|---|
| No se cuenta doble | Un contacto en 3 listas ocupa 1 lugar del límite |
| No recibe duplicados | Una campaña a dos listas superpuestas le llega una vez |
| No gasta doble | Ese envío consume 1 correo de la cuota, no 2 |
| La baja aplica a todo | Desuscribirse lo saca de todas las listas de esa cuenta |

**Implementación**: índice único sobre `{account_id, email_normalizado}`; listas
como arreglo de etiquetas en el mismo documento. Una sola colección `contacts`.
Normalización: sin espacios, sin distinguir mayúsculas.

**Argumento comercial**: *"Tus contactos no se duplican: si una persona está en
varias de tus listas, cuenta como uno solo y recibe un solo correo."*

### Lista de supresión

Vive **aparte** de los contactos y el cliente **no la puede borrar**. Borrar un
contacto no borra su supresión; volver a subirlo no lo reactiva.

| Motivo | ¿Se puede levantar? | Cómo |
|---|---|---|
| Se desuscribió | Sí | Solo si **la persona misma** se resuscribe por el formulario, con doble opt-in |
| Rebote duro | No | Permanente |
| Marcó como spam | No | Permanente, sin excepción |
| Suprimido manualmente por el cliente | Sí | Desde el panel |

- **Alcance por cuenta, nunca global**: índice sobre `{account_id, email}`. Si
  alguien se da de baja del colegio, sigue recibiendo los correos de la
  cooperativa.
- Los correos suprimidos **no consumen cuota** — se saltan antes de enviar.
- Guardar siempre fecha y origen de cada supresión (respaldo ante reclamos).
- Al importar, informar al cliente: *"1,000 contactos importados. 12 están dados
  de baja y no recibirán correos."*

### Retención de datos

| Dato | Vida |
|---|---|
| Contactos | Permanente mientras la cuenta esté activa |
| Supresiones | Permanente, siempre |
| Eventos de envío | 12 meses en detalle; después solo totales por campaña |
| Archivo CSV subido | Se borra tras procesarlo |
| Imágenes de correos | Mientras exista la campaña (en Cloudflare R2, no en Mongo) |

**Al cancelar**: se conserva todo 90 días por si reactiva, con aviso por correo
antes del vencimiento. Después se borran contactos y eventos. Las supresiones se
conservan siempre.

### Límites técnicos de importación

Protección contra abuso, no control de costos (una importación cuesta
prácticamente cero; el límite de contactos del plan ya acota el crecimiento).

| Límite | Valor |
|---|---|
| Importaciones por día | 10 por cuenta |
| Filas por importación | El límite de contactos del plan |
| Tamaño de archivo | 5 MB |
| Importaciones simultáneas | 1 por cuenta |

Además: procesar el CSV **en streaming** (nunca cargarlo entero en memoria), como
**trabajo en segundo plano** (no dentro del request), consulta de supresiones en
lote con `$in` y escritura con `bulkWrite`. El HTML que suban va sanitizado
(sin `<script>`).

---

## Contexto de mercado

### Competencia real en Santiago de Veraguas

| Alternativa | Precio |
|---|---|
| Agencia local, campaña gestionada | $280 por campaña |
| Agencia local, autogestión | $89/mes |
| No hacer nada / WhatsApp | $0 |
| Mailchimp Essentials, 10,000 contactos | $110/mes |

La competencia relevante es la agencia local, no Mailchimp: la mayoría de los
prospectos no lo conoce. El precio se sostiene en soporte en español de alguien
local, pago por Yappy y el servicio de diseño — no en el desconocimiento.

### Distribución esperada de prospectos

| Prospecto | Contactos | Plan |
|---|---|---|
| Tienda / restaurante | 300 | Básico |
| Gimnasio / clínica dental | 600 | Básico |
| PyME establecida | 800 | Básico |
| Colegio privado | 1,200 | Negocio |
| Gremio profesional | 1,500 | Negocio |
| Cooperativa pequeña | 2,500 | Negocio |
| Concesionario / agro-distribuidora | 3,000 | Negocio |
| Cooperativa mediana | 4,000 | Empresa |
| Cooperativa grande | 8,000 | Empresa |
| Universidad regional | 10,000 | Empresa |

**Mejores prospectos**: cooperativas de ahorro y crédito, colegios privados,
gremios y universidades — son los únicos que ya tienen una lista de correos
armada por otra razón (socios, padres, miembros, estudiantes) y con obligación
de convocar.

**Obstáculo principal del mercado**: la mayoría de los negocios pequeños **no
tiene lista de correos**. Ayudarlos a construirla (formulario embebible, QR en
el mostrador, importación desde su facturación) puede ser más diferenciador que
el envío mismo.

### Costos

| Concepto | Costo |
|---|---|
| Amazon SES | $0.10 por cada 1,000 correos |
| Railway (Hobby) | $5/mes |
| MongoDB Atlas M0 | $0 (512 MB) |
| Cloudflare | $0 |
| Dominio | ~$12/año |
| **Fijo total** | **~$6/mes** |

Márgenes por plan: **99% / 98% / 96% / 92%**.

**A vigilar**: los eventos de envío llenan los 512 MB del tier gratuito de Atlas
en unos 7 meses con una cartera de 6 Básico + 3 Negocio + 1 Empresa. Presupuestar
el salto de plan de Atlas antes de que la base deje de aceptar escrituras.
