"""La cuenta de demostración, el panel y el Chrome de las capturas del sitio.

Lo comparten `tutorials.py`, que recorre el panel paso a paso, y `samples.py`,
que abre Chrome para las miniaturas de las muestras: la cuenta sembrada en una
base aparte, el panel arrancado contra ella y lo justo para hablar con un Chrome
sin cabeza.

**Los datos son inventados y se nota**: la empresa se llama «Tu empresa», los
contactos son nombres de pila en `@ejemplo.com` y los asuntos son corrientes.
Nada de esto puede leerse como un cliente de verdad.

Hasta octubre de 2026 también hacía las cinco capturas del panel que enseñaba
Features en la portada (`landing/assets/img/panel/`). Features pasó a dibujos
sencillos (`landing/src/partials/feature-*.svg.j2`) y las capturas se quitaron.
"""

from __future__ import annotations

import base64
import json
import os
import socket
import struct
import subprocess
import sys
import time
import urllib.request
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PANEL_PORT = 5099        # el panel de las capturas, aparte del de desarrollo
DB = "sobreala_shots"

EMAIL = "hola@ejemplo.com"
PASSWORD = "Contrasena-Larga1"

# Los dos temas del panel. Los tutoriales se capturan en los dos, cada juego en
# su carpeta, y la página enseña el del tema que tenga puesto quien mira.
THEMES = ("light", "dark")


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
    accounts.set_address(db, who, {"line1": "Apartado 0816-00001", "line2": "",
                                   "city": "Santiago", "region": "Veraguas",
                                   "postal_code": "", "country": "PA"})
    # De quién salen sus campañas: sin usuario, Enviar correos diría que falta.
    accounts.set_handle(db, who, "tuempresa")
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
    baja = f"/unsubscribe/{unsubscribe.sign(quien['_id'])}"
    return {"design": str(diseno), "baja": baja}


# ------------------------------------------------------------------- el panel

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
