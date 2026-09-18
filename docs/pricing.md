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
| Etiquetas | 1 | 2 | 4 | Ilimitadas |
| Columnas propias del contacto | 1 | 5 | 10 | Ilimitadas |
| Crear plantillas en el editor | ✅ | ✅ | ✅ | ✅ |
| Subir tu propio HTML | — | ✅ | ✅ | ✅ |
| **Correos sin marca de agua** | — | ✅ | ✅ | ✅ |
| Diseño personalizado de tu correo | — | 1 | 3 | 5 |
| Analytics completo | ✅ | ✅ | ✅ | ✅ |
| Exportar CSV y PDF | ✅ | ✅ | ✅ | ✅ |
| Usuarios | 1 | 2 | 3 | 5 |
| Soporte | Email 48h | Email 24h | WhatsApp, mismo día | WhatsApp prioritario |
| Sesión de arranque dedicada | — | — | — | ✅ |

**Corporativo se publica sin precio visible**: *"A la medida — contáctanos"*.
Los $300 son referencia interna, no una promesa pública.

**Los precios son finales e incluyen el ITBMS cuando corresponde.** El mismo
precio para todos: a un cliente de fuera de Panamá se le factura como
exportación de servicios, sin ITBMS, así que cambia el desglose de su factura y
no lo que paga.

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

### Diseño personalizado de tu correo (Negocio en adelante)

- Se diseña **una vez** con la marca, colores, logo y tipografía del cliente; él
  la reutiliza cada mes cambiando textos e imágenes.
- Hasta **2 rondas de cambios**, entrega en **3 días hábiles**.
- El cliente entrega textos, imágenes y logo.
- **No acumulable** de un mes al siguiente.

### Marca de agua (solo Básico)

- Los correos enviados desde el plan **Básico** llevan una firma discreta al pie:
  *"Enviado con Panamails"*, con enlace al sitio.
- **A partir de Negocio los correos salen sin ninguna marca.**
- La firma va separada del enlace de baja: el enlace de baja de un click es
  obligatorio en **todos** los planes y nunca se quita.
- Doble función: incentivo de upgrade, y publicidad gratuita en cada correo que
  envía un cliente de entrada.

### Sesión de arranque dedicada (Corporativo)

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

### Columnas propias del contacto

Además del correo y el nombre, cada cuenta define **sus** columnas —ciudad,
número de socio, monto, fecha de vencimiento— y las usa dentro del correo para
que cada persona reciba su propio texto. Cuántas caben lo dice la fila de
arriba.

El límite es de empaquetado, no de costo: una columna más no cuesta lo que
cuesta un correo más. Está para que los planes se distingan entre sí.

| Regla | Efecto |
|---|---|
| Se crean antes de usarse | Como las etiquetas: el importador solo llena columnas que ya existen |
| El archivo no manda | Un CSV con quince columnas se acepta; el cliente marca cuáles importa, y son esas las que cuentan contra el límite |
| Cada una tiene un valor por defecto | Un contacto sin ese dato no deja un hueco en medio de la frase |

**Argumento comercial**: *"Escríbele a cada quien por su nombre, con su monto y
su fecha, sin armar un correo por persona."*

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
| Imágenes de correos | Mientras exista la pieza que las usa |

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

Vive en `docs/pricing-interno.md`, fuera de git: costos, márgenes por plan,
precios de la competencia y distribución esperada de prospectos. No debe viajar
con el repositorio.
