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

- [ ] **Comprobar la firma del aviso de Amazon (SNS).** *Claude.*
  Hoy lo autoriza solo un secreto en la dirección (fue una decisión,
  `docs/envios.md`). Con los avisos a los sistemas de los clientes pesa más:
  quien tuviera ese secreto podría inventarles eventos. Pide agregar la
  dependencia `cryptography`. Recomendado antes de que un cliente encienda sus
  avisos.

- [ ] **Respaldo de la base entera.** *Tú, en Atlas.*
  El plan gratis (M0) no tiene respaldos; Flex hace una copia diaria y M10 en
  adelante, Cloud Backup.

---

## 3. Seguridad: lo que se vio y no se tocó

Ninguno es urgente con pocos clientes, pero conviene cerrarlos antes de crecer.
Todos los arregla **Claude** cuando se le pida.

- [ ] **La contraseña del segundo factor no está atada a la cuenta.**
  `password_proved()` (`blueprints/auth/routes.py`) guarda solo una hora en la
  sesión. Con varias cuentas abiertas en el mismo navegador, probar la
  contraseña de una sirve para encender el segundo factor en otra. La API ya lo
  hace bien (la prueba lleva la cuenta); es copiar eso.

- [ ] **El panel cree la IP que dice cualquiera.** `client_ip()` lee
  `CF-Connecting-IP` venga de donde venga, así que quien le hable directo a
  Railway se salta los límites de intentos de entrar y registrarse. La API ya
  solo la cree si viene de Cloudflare (`services/api_auth.py`); el panel es una
  línea.

- [ ] **Eliminar la cuenta no comprueba que el código se gastó.** Dos
  peticiones a la vez podrían usar el mismo código (`delete_account`, no mira
  lo que devuelve `tokens.spend()`).

- [ ] **Un nombre con salto de línea rompe el asunto de una campaña.** Si un
  contacto tiene un salto de línea en el nombre y el asunto lleva `*|NOMBRE|*`,
  falla al armarse. La API ya rechaza esos caracteres; el importador y la ficha
  no.

- [ ] **Un número inválido en el lienzo da error 500.** Un JSON del lienzo con
  `NaN` o `Infinity` revienta en vez de decir qué está mal. La API ya los
  rechaza; el editor del panel no.

- [ ] **Sin HSTS.** *Tú, en Cloudflare* (SSL/TLS → Edge Certificates). Obliga al
  navegador a usar siempre HTTPS.

- [ ] **Cosas que pueden llenar la base.** Redactar guarda archivos de hasta
  5 MB dentro de la base, y el panel no tiene tope de plantillas (la API sí,
  300). Con uso normal no pasa nada; con abuso, llenan los 512 MB de Atlas.

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
