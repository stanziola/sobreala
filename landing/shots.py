"""Las capturas del panel que enseña la portada.

El sitio dice lo que hace Sobreala; estas capturas lo enseñan. Salen del panel
de verdad, no de un dibujo: se siembra una cuenta de demostración en una base
aparte, se arranca el panel contra ella, se abre en un Chrome sin cabeza y se
recorta la zona que importa de cada pantalla.

**Los datos son inventados y se nota**: la empresa se llama «Tu empresa», los
contactos son nombres de pila en `@ejemplo.com` y los asuntos son corrientes.
Nada de esto puede leerse como un cliente de verdad.

Mismo trato que `brand/build_logo.py`: fuentes de verdad → comando → archivos
generados que no se tocan a mano.

    python landing/shots.py            # sembrar, capturar y escribir los webp
    python landing/shots.py --check    # decir si faltan, sin tocar nada

Hace falta Chrome instalado y MongoDB corriendo. **Se corre a mano cuando una
pantalla del panel cambie**: si no, el sitio enseña algo que ya no existe.
"""

from __future__ import annotations

import base64
import json
import os
import socket
import struct
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
OUT = ROOT / "landing" / "assets" / "img" / "panel"

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PORT = 9444              # el de las capturas, para no chocar con otro Chrome
PANEL_PORT = 5099        # el panel de las capturas, aparte del de desarrollo
DB = "sobreala_shots"

EMAIL = "hola@ejemplo.com"
PASSWORD = "Contrasena-Larga1"

# Dos juegos, uno por tema: la portada enseña el del tema que tenga puesto quien
# mira, así que la sección puede seguir al tema como el resto de la página. Cada
# uno va en su carpeta, con los mismos cinco nombres dentro.
THEMES = ("light", "dark")

# El bloque del carrusel es 16:9. A este ancho una captura se lee nítida en el
# panel abierto (unos 900 px) sin pasar de 120 KB en webp.
WIDE, TALL = 1400, 788

# Lo que se captura. De cada una: el archivo (`name`), la dirección (`url`, y
# sin ella la pone el guion más abajo), desde dónde recorta (`from`) y, si hace
# falta, en qué pulsar antes (`pick`), qué dejar escrito (`fill`) y en qué ancho
# de ventana (`width`). Los tres últimos son para que ninguna salga vacía: un
# formulario en blanco, un lienzo sin nada elegido o una tarjeta sola en medio
# de una pantalla enorme enseñan el producto apagado.
SHOTS = (
    {"name": "contactos", "url": "/contactos", "from": ".table-wrap"},
    {"name": "lienzo", "from": ".editor", "pick": ".cv-item--text"},
    {"name": "envios", "url": "/envios", "from": ".compose",
     "fill": "(function(){var f=document.getElementById('asunto');"
             "f.value='Boletín de septiembre';"
             "var t=document.querySelectorAll('[name=lista]');"
             "if(t[1])t[1].checked=true;"
             "var r=document.querySelector('[name=cuando][value=ahora]');"
             "if(r)r.checked=true;})()"},
    {"name": "estadisticas", "url": "/panel?periodo=30d", "from": ".rates"},
    # La última, y sin sesión: al enlace de baja lo abre quien recibió el
    # correo, no el cliente, así que arriba no va su menú de cuenta.
    {"name": "baja", "from": ".card", "width": 820, "guest": True},
)


# --------------------------------------------------------------- el navegador

class WS:
    """Lo justo de un cliente de WebSocket para hablar con Chrome por DevTools.

    Sin dependencias, como todo lo demás del repositorio.
    """

    def __init__(self, url: str):
        _, rest = url.split("://", 1)
        hostport, path = rest.split("/", 1)
        host, port = hostport.split(":")
        self.sock = socket.create_connection((host, int(port)), timeout=30)
        key = base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall(
            f"GET /{path} HTTP/1.1\r\nHost: {hostport}\r\nUpgrade: websocket\r\n"
            f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n"
            f"Sec-WebSocket-Version: 13\r\n\r\n".encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            buf += self.sock.recv(4096)
        self.rest = buf.split(b"\r\n\r\n", 1)[1]
        self.next_id = 0

    def _recv(self, n: int) -> bytes:
        while len(self.rest) < n:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise ConnectionError("el socket se cerró")
            self.rest += chunk
        out, self.rest = self.rest[:n], self.rest[n:]
        return out

    def _frame(self, payload: bytes) -> bytes:
        mask = os.urandom(4)
        head = bytearray([0x81])
        size = len(payload)
        if size < 126:
            head.append(0x80 | size)
        elif size < (1 << 16):
            head.append(0x80 | 126)
            head += struct.pack(">H", size)
        else:
            head.append(0x80 | 127)
            head += struct.pack(">Q", size)
        head += mask
        return bytes(head) + bytes(b ^ mask[i % 4] for i, b in enumerate(payload))

    def _read(self) -> str:
        first = self._recv(2)
        size = first[1] & 0x7F
        if size == 126:
            size = struct.unpack(">H", self._recv(2))[0]
        elif size == 127:
            size = struct.unpack(">Q", self._recv(8))[0]
        return self._recv(size).decode("utf-8", "replace")

    def call(self, method: str, **params):
        self.next_id += 1
        mine = self.next_id
        self.sock.sendall(self._frame(json.dumps(
            {"id": mine, "method": method, "params": params}).encode()))
        while True:
            answer = json.loads(self._read())
            if answer.get("id") == mine:
                if "error" in answer:
                    raise RuntimeError(answer["error"])
                return answer.get("result", {})

    def js(self, expression: str):
        answer = self.call("Runtime.evaluate", expression=expression,
                           returnByValue=True, awaitPromise=True)
        return (answer.get("result") or {}).get("value")


# ------------------------------------------------------------ la demostración

def seed():
    """La cuenta de demostración, con datos inventados y corrientes.

    Se borra y se vuelve a sembrar en cada pasada, para que dos capturas hechas
    con días de diferencia no enseñen cosas distintas.
    """
    sys.path.insert(0, str(BACKEND))
    os.environ["MONGODB_URI"] = "mongodb://127.0.0.1:27017"
    os.environ["MONGODB_DB"] = DB
    os.environ["SECRET_KEY"] = "capturas-de-la-portada"
    os.environ["MAIL_BACKEND"] = "file"
    os.environ["APP_BASE_URL"] = f"http://127.0.0.1:{PANEL_PORT}"

    from bson import ObjectId
    from pymongo import MongoClient

    from models import account as accounts
    from models import campaign as campaigns
    from models import campaign_run as runs
    from models import contact as contacts
    from models import design as designs
    from models import event as events
    from models import suppression as suppressions
    from services import canvas, security

    db = MongoClient()[DB]
    for name in db.list_collection_names():
        db[name].delete_many({})

    cuenta = accounts.create(db, company_name="Tu empresa", contact_name="Ana",
                             email=EMAIL, password=PASSWORD, phone="+507 6000-0000")
    who = cuenta["_id"]
    accounts.confirm_email(db, who)
    accounts.activate_plan(db, who, "negocio", events.now() + timedelta(days=300))
    accounts.clear_sending(db, who, who)
    accounts.set_postal(db, who, "Apartado 0816-00001, Santiago, Veraguas")
    db.accounts.update_one({"_id": who},
                           {"$set": {"password_hash": security.hash_password(PASSWORD)}})

    for tag in ("Clientes", "Boletín", "Nuevos"):
        accounts.add_tag(db, who, tag)
    accounts.add_field(db, who, label="Ciudad", kind="text")

    # Contactos: nombres de pila y @ejemplo.com, que no son de nadie.
    gente = [
        ("ana", "Ana", ["Clientes", "Boletín"], "Santiago"),
        ("luis", "Luis", ["Clientes"], "David"),
        ("marta", "Marta", ["Boletín", "Nuevos"], "Chitré"),
        ("pedro", "Pedro", ["Clientes", "Boletín"], "Santiago"),
        ("sofia", "Sofía", ["Nuevos"], "Penonomé"),
        ("diego", "Diego", ["Clientes"], "Santiago"),
        ("carmen", "Carmen", ["Boletín"], "Aguadulce"),
        ("rafael", "Rafael", ["Clientes", "Nuevos"], "David"),
    ]
    campo = accounts.fields_of(accounts.by_id(db, who))[0]["key"]
    for user, name, tags, city in gente:
        contacts.upsert_many(db, who, [(f"{user}@ejemplo.com", name, {campo: city})],
                             tags=tags, consent=contacts.consent_of("pantalla"))
    suppressions.add(db, who, "carmen@ejemplo.com", reason=suppressions.UNSUBSCRIBE)
    # Entraron en días distintos: siete «hace un momento» seguidos se leen
    # como lo que serían, una lista sembrada de golpe.
    for dias, (user, *_rest) in enumerate(gente):
        db.contacts.update_one(
            {"account_id": who, "email_normalized": f"{user}@ejemplo.com"},
            {"$set": {"created_at": events.now() - timedelta(days=dias * 3 + 1)}})

    # Dos piezas: una a medio armar para el lienzo y otra para la vista previa.
    pieza = canvas.blank()
    pieza["h"] = 600
    pieza["items"] = [
        {"t": "shape", "x": 0, "y": 0, "w": 600, "h": 120, "bg": "#3166A7",
         "radius": 0, "shape": "rect", "rot": 0},
        {"t": "text", "x": 40, "y": 36, "w": 520, "h": 44,
         "text": "Novedades de este mes", "font": "Arial", "size": 30,
         "color": "#FFFFFF", "bold": True, "italic": False, "align": "left",
         "line": 1.3},
        {"t": "text", "x": 40, "y": 160, "w": 520, "h": 280,
         "text": ("Hola *|NOMBRE|*, te contamos lo que viene este mes.\n\n"
                  "Abrimos el horario de la tarde, estrenamos la sala de "
                  "reuniones y dejamos listo el formulario para que apartes "
                  "tu cita sin llamar.\n\nSi necesitas algo antes, contéstanos "
                  "este correo y te escribimos de vuelta.\n\nGracias por "
                  "seguir con nosotros un mes más: lo que hacemos aquí sale "
                  "de lo que nos cuentas cada vez que escribes."),
         "font": "Arial", "size": 17, "color": "#18181B", "bold": False,
         "italic": False, "align": "left", "line": 1.6},
        {"t": "button", "x": 40, "y": 470, "w": 230, "h": 52,
         "text": "Apartar mi cita", "href": "https://ejemplo.com/citas",
         "font": "Arial", "size": 17, "color": "#FFFFFF", "bg": "#31A9E8",
         "bold": True, "italic": False, "align": "center", "radius": 10},
    ]
    doc = canvas.parse(json.dumps(pieza))
    grounds, shades = canvas.store(db, who, doc, lambda name: None)
    diseno = designs.save_canvas(db, who, name="Novedades del mes", doc=doc,
                                 backgrounds=grounds, shades=shades)
    designs.save_canvas(db, who, name="Recordatorio de pago", doc=doc,
                        backgrounds=grounds, shades=shades)

    campana = campaigns.create(db, who, subject="Novedades de este mes",
                               design_id=diseno, tags=["Boletín"],
                               scheduled_at=events.now() + timedelta(days=2))

    # Tres meses de envíos, uno cada dos días, para que las gráficas salgan
    # llenas y las pastillas comparen contra algo. Van con `insert_many` y no
    # con `events.record()`: son decenas de miles y aquí no hay nada que
    # deduplicar, los datos se inventan de una pieza.
    ahora = events.now()
    asuntos = ("Boletín de septiembre", "Recordatorio: cierre el viernes",
               "Novedades de este mes", "Horario nuevo desde el lunes")
    for salida in range(45):
        run = ObjectId()
        cuando = ahora - timedelta(days=salida * 2 + 1)
        # Lo más reciente es lo más grande: una lista que crece.
        cuantos = 210 - salida * 3
        abren = int(cuantos * (0.47 + (45 - salida) * 0.0015))
        pulsan = int(abren * 0.3)
        rebotan = max(1, int(cuantos * 0.018))
        filas = []
        for n in range(cuantos):
            quien = f"persona{n}@ejemplo.com"
            def fila(kind, at):
                return {"account_id": who, "campaign_id": None, "run_id": run,
                        "kind": kind, "email_normalized": quien, "created_at": at}
            filas.append(fila(events.SENT, cuando))
            filas.append(fila(events.BOUNCE if n < rebotan else events.DELIVERED,
                              cuando))
            if n < abren:
                filas.append(fila(events.OPEN, cuando + timedelta(hours=2 + n % 9)))
            if n < pulsan:
                filas.append(fila(events.CLICK, cuando + timedelta(hours=3 + n % 7)))
        db.events.insert_many(filas)
        db.campaign_runs.insert_one({
            "_id": run, "account_id": who, "campaign_id": campana,
            "subject": asuntos[salida % len(asuntos)], "tags": ["Boletín"],
            "sent": cuantos, "skipped": 1, "failed": 0,
            "started_at": cuando, "finished_at": cuando + timedelta(minutes=3)})

    # La cuota gastada del mes, que es la barra del final de Estadísticas.
    accounts.add_sent(db, who, 2480)

    # El enlace de baja de una persona, que es una pantalla más del producto.
    from services import unsubscribe

    quien = contacts.by_email(db, who, "ana@ejemplo.com")
    baja = f"/baja/{unsubscribe.sign(quien['_id'])}"
    return {"design": str(diseno), "baja": baja}


# ------------------------------------------------------------------- capturar

def start_panel(log: Path):
    """El panel contra la base de la demostración, en su propio puerto."""
    runner = log.parent / "serve_shots.py"
    runner.write_text(
        "import os, sys\n"
        f"sys.path.insert(0, r'{BACKEND}')\n"
        f"os.chdir(r'{BACKEND}')\n"
        "os.environ.setdefault('MONGODB_URI', 'mongodb://127.0.0.1:27017')\n"
        f"os.environ.setdefault('MONGODB_DB', '{DB}')\n"
        "os.environ.setdefault('SECRET_KEY', 'capturas-de-la-portada')\n"
        "os.environ.setdefault('MAIL_BACKEND', 'file')\n"
        f"os.environ.setdefault('APP_BASE_URL', 'http://127.0.0.1:{PANEL_PORT}')\n"
        "from app import create_app\n"
        "create_app().run(port=%d, debug=False, use_reloader=False)\n" % PANEL_PORT,
        encoding="utf-8")
    out = log.open("w", encoding="utf-8")
    return subprocess.Popen([sys.executable, str(runner)], stdout=out, stderr=out)


def wait_for(url: str, seconds: int = 30) -> None:
    for _ in range(seconds * 2):
        try:
            urllib.request.urlopen(url, timeout=2)
            return
        except Exception:
            time.sleep(0.5)
    raise RuntimeError(f"no arrancó: {url}")


def crop(raw: bytes, top: float, ratio: float) -> bytes:
    """La ventana entera, cortada a 16:9 desde donde empieza lo que importa.

    Se recorta la ventana y no la caja del elemento: una pantalla del panel se
    entiende viendo su barra, su título y lo que hay alrededor. Y se cuenta en
    píxeles del dispositivo (`ratio`), no en los del CSS: Chrome dibuja al doble
    para que la captura se lea nítida, y con los del CSS el recorte salía a la
    mitad y ampliado.
    """
    from PIL import Image

    with Image.open(BytesIO(raw)) as shot:
        wide, tall = shot.size
        cut_tall = min(tall, round(wide * TALL / WIDE))
        y = int(max(0, min(top * ratio, tall - cut_tall)))
        cut = shot.crop((0, y, wide, y + cut_tall)).resize((WIDE, TALL), Image.LANCZOS)
        buffer = BytesIO()
        cut.convert("RGB").save(buffer, format="WEBP", quality=82, method=6)
        return buffer.getvalue()


def take(ws, where: str, shot: dict) -> dict[str, bytes]:
    """Abrir una dirección una vez y capturar su ventana en los dos temas.

    Lo que dice `from` se sube arriba del todo, con un poco de aire, y de ahí
    sale el recorte: así cada captura empieza donde está lo que se quiere
    enseñar y no en el hueco de arriba de la página.

    Se abre una sola vez y se cambia el tema entre foto y foto: así los dos
    juegos salen idénticos salvo el color, y la vuelta no tarda el doble.
    """
    selector, pick, fill = shot["from"], shot.get("pick"), shot.get("fill")
    if shot.get("guest"):
        ws.call("Network.clearBrowserCookies")
    if shot.get("width"):
        # Una pantalla con poco dentro se captura en una ventana más angosta:
        # lo que enseña ocupa su sitio en vez de nadar en el vacío.
        ws.call("Emulation.setDeviceMetricsOverride", mobile=False,
                width=shot["width"], height=round(shot["width"] * TALL / WIDE),
                deviceScaleFactor=2)
    ws.js("location.href=%s" % json.dumps(where))
    time.sleep(3.5)
    if pick:
        where_is = json.loads(ws.js(
            "JSON.stringify((function(){var e=document.querySelector(%s);"
            "if(!e)return null;e.scrollIntoView({block:'center'});"
            "var b=e.getBoundingClientRect();"
            "return {x:b.left+b.width/2,y:b.top+b.height/2}})())"
            % json.dumps(pick)))
        if where_is:
            for kind, buttons in (("mousePressed", 1), ("mouseReleased", 0)):
                ws.call("Input.dispatchMouseEvent", type=kind,
                        x=where_is["x"], y=where_is["y"], button="left",
                        buttons=buttons, clickCount=1)
            time.sleep(1)
    if fill:
        ws.js(fill)
        time.sleep(0.5)
    top = ws.js(
        "(function(){var e=document.querySelector(%s);"
        "if(!e)return 0;e.scrollIntoView({block:'start'});"
        "window.scrollBy(0,-110);"
        "return Math.max(0, e.getBoundingClientRect().top - 110)})()"
        % json.dumps(selector))
    ratio = ws.js("window.devicePixelRatio || 1")
    made = {}
    for theme in THEMES:
        # Lo mismo que hace el guion de la cabecera del panel antes de pintar.
        ws.js("document.documentElement.dataset.theme=%s" % json.dumps(theme))
        time.sleep(1.2)
        raw = base64.b64decode(ws.call("Page.captureScreenshot", format="png")["data"])
        made[theme] = crop(raw, float(top or 0), float(ratio))
    if shot.get("width"):
        ws.call("Emulation.clearDeviceMetricsOverride")
    return made


def shoot(demo: dict) -> dict[str, dict[str, bytes]]:
    """Las cinco capturas, en orden, cada una en los dos temas."""
    work = Path(tempfile.mkdtemp(prefix="sobreala-shots-"))
    panel = start_panel(work / "panel.log")
    chrome = None
    try:
        wait_for(f"http://127.0.0.1:{PANEL_PORT}/entrar")
        chrome = subprocess.Popen(
            [CHROME, "--headless=new", "--disable-gpu",
             f"--remote-debugging-port={PORT}", f"--user-data-dir={work / 'chrome'}",
             "--no-first-run", "--hide-scrollbars",
             "--force-device-scale-factor=2", "--window-size=1500,1000",
             f"http://127.0.0.1:{PANEL_PORT}/entrar"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        ws = None
        for _ in range(60):
            try:
                pages = json.load(urllib.request.urlopen(
                    f"http://127.0.0.1:{PORT}/json/list"))
                page = next((p for p in pages if p["type"] == "page"
                             and p["url"].startswith("http")), None)
                if page:
                    ws = WS(page["webSocketDebuggerUrl"])
                    for method in ("Runtime.enable", "Page.enable", "DOM.enable",
                                   "Network.enable"):
                        ws.call(method)
                    break
            except Exception:
                pass
            time.sleep(0.5)
        if ws is None:
            raise RuntimeError("Chrome no abrió")

        time.sleep(1.5)
        ws.js("(function(){var f=document.getElementById('email');if(!f)return;"
              "f=f.form;f.email.value=%s;f.password.value=%s;f.submit();})()"
              % (json.dumps(EMAIL), json.dumps(PASSWORD)))
        time.sleep(3)

        sitios = {
            "lienzo": f"/plantillas/lienzo/{demo['design']}",
            "baja": demo["baja"],
        }
        made = {}
        for shot in SHOTS:
            name = shot["name"]
            url = f"http://127.0.0.1:{PANEL_PORT}" + (shot.get("url") or sitios[name])
            made[name] = take(ws, url, shot)
        return made
    finally:
        if chrome:
            chrome.terminate()
        panel.terminate()
        time.sleep(1)


# ----------------------------------------------------------------- el comando

def main() -> None:
    check = "--check" in sys.argv
    if check:
        faltan = [f"{theme}/{s['name']}" for theme in THEMES for s in SHOTS
                  if not (OUT / theme / f"{s['name']}.webp").exists()]
        if faltan:
            print("Faltan capturas:", ", ".join(faltan))
            print("Correlas con: python landing/shots.py")
            raise SystemExit(1)
        print("Las capturas del panel estan, en los dos temas.")
        return

    print("Sembrando la cuenta de demostracion…")
    demo = seed()
    print("Capturando…")
    made = shoot(demo)
    for theme in THEMES:
        (OUT / theme).mkdir(parents=True, exist_ok=True)
    for name, themes in made.items():
        for theme, data in themes.items():
            target = OUT / theme / f"{name}.webp"
            target.write_bytes(data)
            print(f"  {target.relative_to(ROOT)}  {len(data) // 1024} KB")


if __name__ == "__main__":
    main()
