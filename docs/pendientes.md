# Pendientes

Lo que falta hacer o decidir, juntado en un solo lugar (20 de octubre de 2026).
Antes estaba regado entre `CLAUDE.md`, `docs/api.md` y los reportes de cada
tarea, que se pierden al cerrar la conversación.

**Cómo se usa:** cada punto dice qué es, por qué importa y quién lo hace
(**tú**, en una consola, o **Claude**, cuando se lo pidas). Marca la casilla o
di el punto, y lo hecho se borra de aquí y queda explicado en su `docs/`.

Los tutoriales del sitio no están aquí a propósito: se rehacen al final, cuando
el panel esté casi terminado.

---

## 1. Ahora (esta semana)

- [ ] **Ver que salga lo de hoy en Railway.** *Tú.*
  Railway tuvo una falla general el 20 de octubre de 2026, desde las 12:03 de
  Panamá: pausó la construcción de versiones nuevas en todas las cuentas. Los
  commits de la API y de la letra nueva quedaron en cola y se publican solos al
  reanudarse. Comprobar después que el despliegue terminó bien y que GitHub
  enseña la marca de Railway en el último commit.

- [ ] **La marca de Cloudflare en GitHub.** *Tú.*
  Si tampoco aparece, no es por la falla de Railway (es otra empresa). Mirar en
  Cloudflare → Pages → el proyecto → Deployments si está el de hoy, y en GitHub
  → Settings → Applications que la app de Cloudflare tenga acceso al
  repositorio.

- [ ] **Crear el servicio `worker` en Railway**, cuando Railway vuelva. *Tú, con
  Claude guiando.*
  Es el proceso en segundo plano: manda las campañas programadas a su hora,
  sigue por tandas una campaña grande y entrega los avisos a los sistemas de los
  clientes (webhooks). Sin él, el panel funciona, pero lo programado no sale,
  una campaña grande solo manda su primera tanda y los avisos no llegan.
  Los pasos están en `docs/api.md`, «Lo que tienes que hacer tú»: un servicio
  nuevo del mismo repositorio, Start Command `python backend/worker.py`, sin
  dominio público, todas las variables del web por referencia (sobre todo
  `SECRET_KEY`) y `RAILWAY_DEPLOYMENT_DRAINING_SECONDS=30`.

- [ ] **Bot Fight Mode apagado en Cloudflare.** *Tú.*
  Encendido, las llamadas a la API desde el servidor de un cliente reciben un
  desafío en vez de JSON, y en el plan gratis no se le puede hacer una excepción
  para `/api/`.

- [ ] **Comprobar el primer despliegue con la API.** *Tú, con Claude.*
  - que gunicorn arranque con hilos (`--worker-class gthread`, en el
    `Procfile`; en Windows no se pudo probar);
  - que Railway ponga la IP real al final de `X-Forwarded-For` (la lista de IP
    permitidas de cada llave depende de eso);
  - que `FLASK_ENV` diga `production` (si no, la galleta de sesión no exige
    HTTPS);
  - y, con el worker creado, que `/health` diga que late y que su llave
    coincide (`worker_key: ok`).

---

## 2. Antes de la primera campaña real de un cliente

- [ ] **Pedirle al cliente sus datos de facturación (RUC).** *Claude.*
  El panel no los guarda en ningún sitio, y una factura en Panamá los necesita.

- [ ] **Sacar la importación CSV de la petición.** *Claude.*
  Hoy corre mientras la página espera; con más de unas 5,000 filas se corta.
  Ahora que existe el worker, es el sitio natural para hacerla.

- [ ] **Pedir la producción de SES.** *Tú, con el texto que redacta Claude.*
  La cuenta sigue en sandbox (21 de octubre de 2026): solo entrega a direcciones
  verificadas. Va después de crear el worker. Lo que se le diga a Amazon tiene
  que estar funcionando: bajas, supresiones, la pausa automática y la
  declaración del origen de cada contacto.

- [ ] **Configurar «Continuar con Apple».** *Tú, con los pasos de
  `docs/cuenta.md`.* El Services ID, la clave `.p8` y las cuatro variables
  `APPLE_*` en Railway, y registrar `sobreala.com` en el servicio de reenvío de
  correo de Apple (sin eso, a quien oculta su correo no le llega nada).

- [ ] **Respaldo de la base entera.** *Tú, en Atlas.*
  El plan gratis (M0) no tiene respaldos; Flex hace una copia diaria y M10 en
  adelante, Cloud Backup.

---

## 3. Seguridad: lo que se vio y no se tocó

Lo de esta sección se cerró el 21 de octubre de 2026 (`docs/cuenta.md`, «Lo que
se cerró de seguridad»); queda solo lo de Cloudflare.

- [ ] **HSTS también en Cloudflare** (opcional). *Tú* (SSL/TLS → Edge
  Certificates). El panel y el sitio ya lo mandan (octubre de 2026); encenderlo
  en Cloudflare lo pone además en lo que Cloudflare conteste solo. Obliga al
  navegador a usar siempre HTTPS.

---

## 4. Cómo funciona el envío

Decisiones de producto: **tú decides**, Claude las hace.

- [ ] **Una campaña que está saliendo no se puede detener ni borrar.** Y con el
  worker, una que se quedó sin cuota sigue sola el mes siguiente. Falta un botón
  «Detener».

- [ ] **La pausa automática mezcla las dos clases de correo.** Los
  transaccionales casi nunca reciben quejas y diluyen las de las campañas: un
  cliente con muchos recibos podría mandar campañas malas sin que salte. Se
  puede medir por clase.

- [ ] **Estadísticas suma los correos de la API** con las campañas, sin
  separarlos. Separarlos es un filtro.

- [ ] **Masivo enseña las 50 últimas campañas contando los individuales.** Con
  50 correos de Redactar, «Campañas guardadas» sale vacía.

- [ ] **El aviso «tu plan vence en 7 días»** solo sale cuando el cliente entra
  al panel. El worker podría mandarlo cada día aunque no entre.

---

## 5. Negocio, precios y textos legales

- [ ] **La API no aparece en los planes.** `docs/pricing.md` y la página de
  planes no la nombran. Es una fila. *Tú decides el texto.*

- [ ] **Los términos y la API.** Deberían decir qué cuenta como transaccional
  (para que nadie mande publicidad disfrazada de recibo) y que la llave es
  responsabilidad del cliente. *Tú* (Claude no toca texto legal sin ti).

- [ ] **Yappy.** Confirmar si soporta cobros recurrentes (yappy@bgeneral.com /
  800-5000), y falta su integración. *Tú.*

- [ ] **Paguélofácil.** Falta la afiliación del comercio. *Tú.*

- [ ] **Presupuestar el salto de Atlas.** Los eventos de cada correo no vencen,
  y la API adelanta el momento de llenar los 512 MB del plan gratis. *Tú.*

- [ ] **Tenants de SES por cliente**, cuando haya más clientes: Amazon llevaría
  la reputación de cada uno aparte. Detalle en `CLAUDE.md`. *Claude, cuando se
  decida.*

- [ ] **Contrato de encargo** para una cooperativa grande que pida un documento
  firmado. Se redacta cuando aparezca. *Tú.*

---

## 6. Documentación que quedó vieja

*Claude*, cuando se pida (no se corrige de paso).

- [ ] `docs/envios.md`, «Lo que todavía no hace»: dice que no reanuda sola una
  campaña, y el worker ya lo hace.
- [ ] `docs/panel.md`, «Pendiente: la pantalla de gráficas»: dice que no existen
  `events` ni `campaigns`, y existen.
- [ ] `docs/cobro.md`: dice que el proyecto no tiene proceso en segundo plano.
- [ ] `CLAUDE.md` nombra `docs/arquitectura.md` y `docs/decisiones.md`, que no
  existen: o se escriben o se quitan del árbol.
