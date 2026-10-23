# Sobreala — Planes y precios

Documento de referencia interno. Define los planes comerciales, sus límites y las
reglas de negocio asociadas.

---

## Planes

| | Básico | Negocio | Empresa |
|---|---|---|---|
| **Precio mensual** | $15 | $25 | $55 |
| **Precio anual** (20% de descuento) | $144 | $240 | $528 |
| Contactos | 1,000 | 3,000 | 10,000 |
| Correos por mes | 5,000 | 15,000 | 50,000 |
| Campañas a lista completa | 5 | 5 | 5 |
| Precio por correo | $0.0030 | $0.0017 | $0.0011 |
| Etiquetas | 1 | 2 | 4 |
| Columnas propias del contacto | 1 | 5 | 10 |
| Crear plantillas en el editor | ✅ | ✅ | ✅ |
| **Correos sin marca de agua** | — | ✅ | ✅ |
| **Acceso a la API** | — | ✅ | ✅ |
| Analytics completo | ✅ | ✅ | ✅ |
| Exportar CSV y PDF | ✅ | ✅ | ✅ |
| Usuarios | 1 | 2 | 3 |
| Imágenes guardadas | 20 | 50 | 100 |

**Los precios son finales e incluyen el ITBMS cuando corresponde.** El mismo
precio para todos: a un cliente de fuera de Panamá se le factura como
exportación de servicios, sin ITBMS, así que cambia el desglose de su factura y
no lo que paga.

### Regla de proporción

El límite de correos es siempre **5x el límite de contactos**. Cualquier plan
nuevo debe respetarla: permite 5 campañas mensuales a la lista completa.

---

## Reglas de negocio

### Suscripción

- Sin permanencia mínima. Cancelable desde el panel en cualquier momento.
- El plan anual se paga por adelantado y lleva un 20% de descuento.
- Métodos de pago: Yappy, PayPal y tarjeta vía PayPal.
- **Renovación automática, solo con PayPal** (octubre de 2026): opcional, con una
  suscripción de PayPal que cobra cada periodo hasta que se cancele. La
  tarjeta (Paguélofácil) y Yappy se pagan en cada renovación. Ver `docs/cobro.md`.
- **Pendiente de confirmar con Yappy**: si soporta cobros recurrentes. Si no, a
  los clientes de Yappy se les envía un enlace de pago antes de cada
  vencimiento.

### La API

- **Desde el plan Negocio** (octubre de 2026): la fila «Acceso a la API» de la
  tabla. La leen el sitio (la fila «API» de la comparación) y el producto
  (`plans.has_api()`): el Básico y la demostración no crean claves de API, y las
  de quien baja de plan dejan de abrir hasta que mejore. Ver `docs/api.md`.

### Mejorar de plan (prorrateo)

- Con un plan vigente **solo se mejora**: de un mensual, a uno mayor (mensual o
  anual) o al mismo en anual; de un anual, solo a uno mayor en anual. Bajar de
  plan, o volver a pagar el mismo ciclo del que se tiene, no se hace por la web:
  el mismo plan se vuelve a comprar cuando vence.
- **Los correos sin usar se descuentan** del precio nuevo: en un mensual, el
  precio del mes × lo que queda de su cuota; en un anual, los meses enteros que
  faltan más lo que queda de la cuota de este mes, al precio del año entre doce.
  Negocio sin usar nada → Empresa mensual: $55 − $25 = $30.
- El plan nuevo **empieza el día de la mejora**, con su cuota entera: lo
  enviado antes ya no cuenta.
- Con esas reglas el descuento nunca pasa del precio nuevo, así que nunca queda
  crédito sobrante que devolver.

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
3. Al empezar el mes siguiente o al subir de plan, el envío **retoma desde el
   correo donde se detuvo**.

Requiere guardar la posición de envío de cada campaña, no solo un contador global.

### Al llegar al límite de contactos

- La importación se detiene y se notifica que debe subir de plan.
- Los contactos ya cargados no se borran.

### Marca de agua (solo Básico)

- Los correos enviados desde el plan **Básico** llevan una firma discreta al pie:
  el ala de Sobreala y *"Enviado con Sobreala"*, con enlace al sitio.
- **A partir de Negocio los correos salen sin ninguna marca.**
- La firma va separada del enlace de baja: el enlace de baja de un click es
  obligatorio en **todos** los planes y nunca se quita.
- Doble función: incentivo de upgrade, y publicidad gratuita en cada correo que
  envía un cliente de entrada.

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

**Al vencer el plan** no se borra nada: la cuenta queda sin poder enviar hasta
que pague otra vez. **Al eliminar la cuenta** (Configuración → Cuenta) se borra
al momento, salvo las supresiones, los pagos y facturas, la bitácora y una ficha
mínima (`services/erase.py`). Hasta octubre de 2026 decía «se conserva todo 90
días», y no era así.

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
lote con `$in` y escritura con `bulkWrite`.

---

## Contexto de mercado

Vive en `docs/pricing-interno.md`, fuera de git: costos, márgenes por plan,
precios de la competencia y distribución esperada de prospectos. No debe viajar
con el repositorio.
