# Contactos, supresiones e importación

Detalle que vivía en `CLAUDE.md`, movido tal cual para que ese archivo
cupiera en el límite. Lo esencial (las reglas, las convenciones y el
resumen de cada parte) sigue allí; esto es lo que hay que leer antes de
tocar esta parte.

### `contacts`
**Un solo documento por dirección de correo por cuenta.** Índice único sobre
`{account_id, email_normalized}`. Normalización: sin espacios, minúsculas.

Las "listas" son un arreglo de **etiquetas** en el mismo documento, no
colecciones separadas. Esto garantiza que un contacto en varias listas:
cuente una sola vez contra el límite, reciba un solo correo, y consuma un solo
correo de la cuota.

**Cuántas etiquetas caben lo dice el plan**, leído de `docs/pricing.md` como los
precios: 1 · 2 · 4, y **1 sin plan**, como el Básico. No se copia el
número al backend por la misma razón que no se copian los precios. Una
consecuencia que conviene tener presente: con una sola etiqueta no se puede
segmentar, así que el Básico tampoco; si algún día estorba, es cambiar una fila
del documento.

**Las etiquetas se crean antes de usarse**, en `/contacts/tags`, y viven
en `contact_tags` del documento de la cuenta. Los formularios de agregar e
importar solo enseñan casillas con las que existen, y el servidor descarta lo
que llegue y no esté en ese registro. Dos razones: escribirlas en cada
formulario dejaba «Socios» y «socios» como dos etiquetas distintas, y una recién
creada no aparecía en ningún lado hasta tener un contacto dentro, porque la
lista se sacaba preguntándole a los contactos.

**Cada cuenta define sus propias columnas**, además del correo y el nombre:
ciudad, número de socio, monto, fecha de vencimiento. Viven en
`contact_fields` del documento de la cuenta —nombre, clave, tipo y respaldo— y
sus valores en `fields` del contacto, así que escribir un correo personalizado
no agrega ni una consulta. Cuántas caben lo dice `docs/pricing.md`, como las
etiquetas: 1 · 5 · 10, y 1 sin plan.

Cuatro tipos —texto, número, fecha y sí/no— y cada uno se gana el sitio
haciendo dos cosas: decidir qué se acepta al importar, y cómo se escribe al
enviar. **El valor se guarda normalizado y siempre como texto**: una fecha como
`2026-03-15` y un «1,234.50» como `1234.5`, para que el archivo de cada cliente
pueda venir como venga y el correo salga parejo. Lo que no es de su tipo no se
escribe: guardar «el martes» en una columna de fecha es guardar algo que
después no se puede enseñar.

**Son obligatorias, y no hay texto de respaldo.** Un contacto **nuevo** solo
entra con todas llenas —sin ellas no podría recibir nada, así que entrar sería
entrar de peso muerto— y al que le falte una **no se le manda ningún correo**
hasta que la tenga. Tapar el hueco con un respaldo era lo contrario de
enseñarlo.

Eso muerde el día que se crea una columna nueva: deja incompleta a toda la
lista. Por eso se ve en los cuatro sitios donde se cuenta gente —la tabla marca
«Incompleto», el contador lo dice, la pantalla de crearla avisa a cuántos va a
dejar fuera, y las cifras de envío ya no los cuentan—. Lo hace una condición en
la consulta común (`models/contact.py`) que **solo encienden los caminos de
envío**: la lista sí los enseña, porque para completarlos hay que verlos.

**Se crean desde la lista de contactos**, que es donde se está cuando hace falta
guardar un dato más, y con el plan lleno ese botón sale apagado —y la ruta lo
comprueba igual—. `/contacts/columns` es para lo que ya existe: **cambiar el
tipo**, que no se deja si algún valor no encaja en el nuevo, y borrar. El nombre
no se cambia: es lo que las piezas ya tienen escrito dentro. Borrar una borra lo
que los contactos tenían escrito en ella; los contactos se quedan.

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

**Exportar pregunta antes.** El GET de `/contacts/export` no descarga nada:
dice cuántos van a salir y con qué filtro, y el POST es el que escribe el
archivo. El filtro viaja en campos escondidos, así que lo que baja es lo que esa
pantalla acaba de decir y no lo que quedó en la dirección de otra.

**El límite de contactos sale del plan** (`PLAN_CONTACTS` en
`models/account.py`, copiado de `docs/pricing.md`). Una cuenta **sin plan** tiene
el del plan más barato, como las etiquetas, las columnas y las imágenes: 1,000.
Solo llega aquí abierta por la demostración, y lo que le falta es enviar, no
sitio (ver «Abrir la cuenta» en `docs/cuenta.md`). Hasta octubre de 2026 eran
500 (`CONTACTS_FREE_LIMIT`), para que el Básico valiera la pena; sin plan no
sale ningún correo, así que el Básico ya vale la pena solo.

### Direcciones inválidas (octubre de 2026)

`services/address_check.py` revisa lo que se puede saber gratis y sin mandar
nada:

- **Que el dominio reciba correo**: que tenga MX, o A si no tiene MX, con
  `email-validator` (que ya estaba instalado y trae dnspython). Es **una
  consulta por dominio** y no por dirección, guardada mientras el proceso vive,
  y como mucho 400 dominios distintos por importación. Lo que no se pudo
  averiguar (el DNS no contestó) cuenta como bueno. Sin `MAIL_BACKEND=ses` no
  se consulta nada, como el resto del envío.
- **Los errores de dedo** contra una lista corta de dominios comunes en Panamá
  (gmail, hotmail, outlook, yahoo, icloud, cwpanama, cableonda, utp, up…), solo
  si el largo cambia poco: así `yahoo.com.mx` no se «corrige».

Al **importar**, una dirección de un dominio que no recibe correo entra igual,
pero marcada (`invalid: {reason: "domain", at}`, `contacts.mark_invalid()`, en
lote). El resultado dice cuántas fueron, y cuántas parecen mal escritas, con las
primeras cinco y su sugerencia. Las mal escritas entran como están: la
sugerencia es solo eso. **Al enviar**, una marcada se salta como un suprimido y
no gasta cuota. **En Contactos** sale con la pastilla «Dirección inválida», un
aviso dice cuántas hay, `?estado=invalidas` las enseña solas, y «Borrar las N»
(`/contacts/invalid/delete`) las borra de una vez, sin tocar supresiones. **A
mano** no entra una de un dominio que no recibe correo.

Lo que **no** se puede saber es si un buzón concreto existe en un dominio bueno.
Preguntárselo al servidor del otro lado (el «RCPT TO» sin enviar) no sirve:
Gmail y Outlook dicen que sí a todo, y hacerlo seguido manda la IP a las listas
negras. Eso lo dice el rebote, que ya anula la dirección. Amazon tiene una
validación propia desde diciembre de 2025, pero cobra $0.01 por dirección; no se
usa.

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

### Límites de importación

| Límite | Valor |
|---|---|
| Importaciones por día | 10 por cuenta |
| Filas por importación | El límite de contactos del plan |
| Tamaño de archivo | 5 MB |
| Importaciones simultáneas | 1 por cuenta |

Procesar el CSV **en streaming**, nunca cargarlo entero en memoria.

**Un contacto nuevo solo entra con todas las columnas de la cuenta llenas.** El
resultado dice cuántos se quedaron fuera por venir incompletos. A los que ya
existían se les actualiza lo que traiga el archivo, columna a columna: traer la
ciudad no le borra el monto a nadie.

**El archivo no manda.** Uno de quince columnas se acepta igual: la pantalla
enseña sus títulos y el cliente marca cuáles guardar, y es **lo que marca** lo
que cuenta contra el límite del plan. Rechazar el archivo entero por traer
columnas de más dejaría fuera a cualquiera que exporte de su sistema.

Ese mapeo lo dibuja `panel.js` leyendo la primera línea en el propio navegador,
así que el archivo no se sube dos veces ni se guarda mientras alguien decide.
**Sin JavaScript la importación sigue funcionando**: el servidor casa los
títulos del archivo con las columnas que la cuenta ya tiene. Lo que se pierde es
poder crear una columna desde ahí, y eso es a propósito: crear una columna es
una decisión, no un efecto secundario de subir un archivo. El servidor vuelve a
leer la cabecera y no se fía de nada de lo que mande la pantalla.
