"""Los tutoriales de /how-it-works: el panel de verdad, paso a paso.

Cada tutorial es un recorrido por el panel. De cada paso sale una captura de la
ventana, en los dos temas, y la caja de lo que hay que pulsar para seguir, en
porcentajes de la captura. En la página, el reproductor (`assets/js/tutorial.js`)
pone un punto encima de esa caja y un globo con lo que hay que hacer, y pulsarlo
pasa a la captura siguiente, que es lo que el panel enseña después de ese clic.

Son capturas y no una réplica del panel a propósito: se ven idénticas al panel y
no se desfasan. Se rehacen con este comando cuando cambia una pantalla:

    python landing/tutorials.py            # sembrar, recorrer y escribir
    python landing/tutorials.py --check    # decir si falta algo, sin tocar nada

Usa la cuenta de demostración, el panel y el Chrome de `shots.py`. Los textos
de cada paso no viven aquí: están en `content.py` (`TUTORIALS`), con el resto
del texto del sitio.
"""

from __future__ import annotations

import base64
import json
import subprocess
import sys
import tempfile
import time
import urllib.request
from io import BytesIO
from pathlib import Path

import shots
from shots import CHROME, EMAIL, PANEL_PORT, PASSWORD, THEMES, WS

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "landing" / "assets" / "img" / "tutorial"
DATA = ROOT / "landing" / "tutorials.json"
PORT = 9445

# La ventana del panel: la de una computadora portátil corriente. Se captura al
# doble y se guarda a este tamaño, así se lee nítida sin pesar de más.
VIEW_W, VIEW_H = 1280, 800

# De dónde sale el archivo que se importa en el tutorial de contactos.
CSV = "correo,nombre,Ciudad\n" + "\n".join(
    f"{u}@ejemplo.com,{n},{c}" for u, n, c in (
        ("elena", "Elena", "Santiago"), ("jorge", "Jorge", "Las Tablas"),
        ("lucia", "Lucía", "Chitré"), ("mario", "Mario", "David"),
        ("paula", "Paula", "Santiago"))) + "\n"


# Lo que se pulsa para abrir cada sección desde el menú de la barra.
def menu_row(href: str) -> str:
    return f'.menu__panel a.menu__item[href="{href}"]'


MENU = "summary.menu__button"
# Donde empiezan los recorridos: Estadísticas con el mes a la vista, que con
# las últimas 24 horas salen ceros.
HOME = "/dashboard?period=30d"

# Los recorridos. De cada paso:
#   id      su nombre, que es la clave de su texto en content.py
#   go      a dónde ir antes de capturar (si no, se sigue donde se quedó)
#   prep    qué hacer antes de capturar (dejar algo escrito, pasar el ratón)
#   hover   dónde dejar el ratón en la captura
#   target  lo que hay que pulsar para seguir; sin él, es el último paso
#   act     qué pasa al pulsarlo: "click" (el de siempre), "file" (elegir el
#           CSV), "none" (nada cambia en pantalla: el globo explica y se sigue)
#           o un guion propio
TOURS: tuple[tuple[str, list[dict]], ...] = (
    ("contacts", [
        {"id": "menu", "go": HOME, "target": MENU},
        {"id": "entrar", "target": menu_row("/contacts")},
        {"id": "etiquetas", "target": 'a.settings__tab[href="/contacts/tags"]'},
        {"id": "nueva",
         "prep": "document.getElementById('etiqueta').value='Socios'",
         "target": "#etiqueta ~ button[type=submit]"},
        {"id": "importar", "target": 'a.settings__tab[href="/contacts/import"]'},
        {"id": "archivo", "target": 'label[for="archivo"]', "act": "file"},
        {"id": "columnas", "target": "[data-map-rows] select",
         "act": "(function(){var s=document.querySelector('[data-map-rows] select');"
                "for(var i=0;i<s.options.length;i++){if(s.options[i].text==='Ciudad')"
                "{s.selectedIndex=i;}}s.dispatchEvent(new Event('change',{bubbles:true}));})()"},
        {"id": "origen", "target": "#source",
         "act": "(function(){var s=document.getElementById('source');"
                "s.selectedIndex=1;s.dispatchEvent(new Event('change'));"
                "var t=document.querySelector('input[name=tags][value=Socios]');"
                "if(t)t.checked=true;})()"},
        {"id": "subir", "target": 'form[enctype] > button[type="submit"]'},
        {"id": "resultado", "focus": ".notice"},
    ]),
    ("templates", [
        {"id": "menu", "go": HOME, "target": MENU},
        {"id": "entrar", "target": menu_row("/templates")},
        {"id": "crear", "target": 'a[href="/templates/create"]'},
        {"id": "texto", "target": 'button[data-add="text"]'},
        {"id": "escribir", "target": ".cv-item--text", "act": "none"},
        {"id": "armada", "go": "/templates/canvas/{design}",
         "target": ".cv-item--text"},
        {"id": "vista", "target": 'button[data-open-dialog="vista-previa"]',
         "wait": 3},
        {"id": "cerrar", "target": "#vista-previa .drawer__close"},
        {"id": "guardar", "target": '.editor__actions button.btn[type="submit"]',
         "wait": 3.5},
        {"id": "listo"},
    ]),
    ("campaigns", [
        {"id": "menu", "go": HOME, "target": MENU},
        {"id": "entrar", "target": menu_row("/campaigns")},
        {"id": "asunto", "target": "#asunto",
         "act": "document.getElementById('asunto').value='Boletín de octubre'"},
        {"id": "etiquetas", "target": 'label:has(> input[name="lista"])'},
        {"id": "plantilla", "target": "#pieza",
         "act": "(function(){var s=document.getElementById('pieza');"
                "s.selectedIndex=1;})()"},
        {"id": "cuando", "target": 'input[name="cuando"][value="ahora"]'},
        {"id": "guardar", "target": 'form:has(#asunto) button[type="submit"]'},
        {"id": "mandar", "target": 'a[href$="/send"]'},
        {"id": "pregunta"},
    ]),
    ("stats", [
        {"id": "periodo", "go": "/dashboard", "target": "#periodo",
         "act": "(function(){var s=document.getElementById('periodo');"
                "s.value='30d';s.form.submit();})()"},
        {"id": "cifras", "target": ".rates", "act": "none"},
        {"id": "grafica", "hover": ".chart .chart__col:nth-last-child(2)",
         "target": ".chart", "act": "none"},
        {"id": "bajar", "target": 'a[href*="/analytics/"], a[href*="csv"]',
         "act": "none"},
        {"id": "mejores", "target": 'a[href*="/campaigns/sent/"]'},
        {"id": "detalles"},
    ]),
    ("settings", [
        {"id": "menu", "go": HOME, "target": MENU},
        {"id": "entrar", "target": menu_row("/settings")},
        {"id": "direccion", "target": "#direccion-campo", "act": "none"},
        {"id": "seguridad", "target": 'a.settings__tab[href="/settings/security"]'},
        {"id": "dos_pasos", "target": 'a[href="/account/two-factor"]', "act": "none"},
        {"id": "usuarios", "target": 'a[href="/settings/users/new"]',
         "act": "none"},
        {"id": "facturacion", "target": 'a.settings__tab[href="/settings/billing"]'},
        {"id": "plan"},
    ]),
)


def image_name(tour: str, index: int) -> str:
    return f"{tour}-{index + 1}"


# ------------------------------------------------------------ la demostración

def seed() -> dict:
    """La cuenta de `shots.py`, con lo que los recorridos necesitan de más:
    sitio para una etiqueta nueva, que es lo primero que se enseña a crear."""
    demo = shots.seed()
    from datetime import timedelta

    from pymongo import MongoClient

    from models import account as accounts
    from models import event as events

    db = MongoClient()[shots.DB]
    who = accounts.by_email(db, EMAIL)["_id"]
    # Empresa: cuatro etiquetas, y la demostración trae tres.
    accounts.activate_plan(db, who, "empresa", events.now() + timedelta(days=300))
    # Sin la campaña programada: la que se guarda en el recorrido es la única
    # de la lista, que es la que se manda. Sus envíos se quedan en el historial.
    db.campaigns.delete_many({"account_id": who})
    # En el último envío, las primeras personas son contactos de verdad: en su
    # «Detalles» salen con su nombre y sus etiquetas.
    last = db.campaign_runs.find_one({"account_id": who}, sort=[("started_at", -1)])
    people = [c["email_normalized"] for c in db.contacts.find({"account_id": who})]
    # Desde la décima: las primeras rebotaron, y el ejemplo es uno que llegó.
    for n, email in enumerate(people, start=10):
        db.events.update_many({"run_id": last["_id"],
                               "email_normalized": f"persona{n}@ejemplo.com"},
                              {"$set": {"email_normalized": email}})
    return demo


# ------------------------------------------------------------------ capturar

def shrink(raw: bytes) -> bytes:
    from PIL import Image

    with Image.open(BytesIO(raw)) as shot:
        cut = shot.resize((VIEW_W, VIEW_H), Image.LANCZOS)
        buffer = BytesIO()
        cut.convert("RGB").save(buffer, format="WEBP", quality=80, method=6)
        return buffer.getvalue()


def box_of(ws, selector: str) -> dict | None:
    """La caja de lo que hay que pulsar, ya a la vista, en píxeles de la
    ventana."""
    return json.loads(ws.js(
        "JSON.stringify((function(){var e=document.querySelector(%s);"
        "if(!e)return null;var b=e.getBoundingClientRect();"
        "if(b.top<70||b.bottom>innerHeight-50){"
        "e.scrollIntoView({block:'center',inline:'nearest'});"
        "b=e.getBoundingClientRect();}"
        "return {x:b.left,y:b.top,w:b.width,h:b.height}})())" % json.dumps(selector)))


def click(ws, box: dict) -> None:
    x, y = box["x"] + box["w"] / 2, box["y"] + box["h"] / 2
    ws.call("Input.dispatchMouseEvent", type="mouseMoved", x=x, y=y)
    for kind, buttons in (("mousePressed", 1), ("mouseReleased", 0)):
        ws.call("Input.dispatchMouseEvent", type=kind, x=x, y=y, button="left",
                buttons=buttons, clickCount=1)


def choose_file(ws, csv_path: Path) -> None:
    doc = ws.call("DOM.getDocument", depth=-1)
    node = ws.call("DOM.querySelector", nodeId=doc["root"]["nodeId"],
                   selector="#archivo")["nodeId"]
    ws.call("DOM.setFileInputFiles", nodeId=node, files=[str(csv_path)])
    ws.js("document.getElementById('archivo').dispatchEvent("
          "new Event('change', {bubbles: true}))")


def goto(ws, url: str) -> None:
    """Ir a otra dirección aunque la página pregunte antes de salir.

    El lienzo pregunta si se sale sin guardar, y esa pregunta deja el guion de
    la página parado: la navegación se pide en diferido y la pregunta se
    acepta, si la hubo."""
    ws.js("setTimeout(function(){location.href=%s}, 0)" % json.dumps(url))
    time.sleep(0.8)
    try:
        ws.call("Page.handleJavaScriptDialog", accept=True)
    except RuntimeError:
        pass  # no preguntó
    time.sleep(2.5)


def walk(ws, tour: str, steps: list[dict], csv_path: Path, demo: dict):
    """Un recorrido entero: por cada paso, sus dos capturas y su punto."""
    base = f"http://127.0.0.1:{PANEL_PORT}"
    images, spots = {}, []
    for index, step in enumerate(steps):
        if step.get("go"):
            goto(ws, base + step["go"].format(**demo))
        if step.get("prep"):
            ws.js(step["prep"])
            time.sleep(0.4)
        box = None
        if step.get("target"):
            box = box_of(ws, step["target"])
            if box is None:
                raise RuntimeError(f"{tour}/{step['id']}: no está {step['target']}")
        elif step.get("focus"):
            box_of(ws, step["focus"])
        time.sleep(0.5)
        # El ratón fuera de todo, salvo que el paso quiera enseñar un cuadrito.
        if step.get("hover"):
            hovered = box_of(ws, step["hover"])
            if box is not None:
                box = box_of(ws, step["target"])
            if hovered:
                ws.call("Input.dispatchMouseEvent", type="mouseMoved",
                        x=hovered["x"] + hovered["w"] / 2,
                        y=hovered["y"] + hovered["h"] / 2)
        else:
            ws.call("Input.dispatchMouseEvent", type="mouseMoved", x=2, y=VIEW_H - 2)
        time.sleep(0.6)
        name = image_name(tour, index)
        images[name] = {}
        for theme in THEMES:
            ws.js("document.documentElement.dataset.theme=%s" % json.dumps(theme))
            time.sleep(0.8)
            raw = base64.b64decode(ws.call("Page.captureScreenshot", format="png")["data"])
            images[name][theme] = shrink(raw)
        spot = None
        if box is not None:
            spot = [round(max(0.0, box["x"]) / VIEW_W * 100, 2),
                    round(max(0.0, box["y"]) / VIEW_H * 100, 2),
                    round(min(box["w"], VIEW_W - max(0, box["x"])) / VIEW_W * 100, 2),
                    round(min(box["h"], VIEW_H - max(0, box["y"])) / VIEW_H * 100, 2)]
        spots.append({"id": step["id"], "image": name, "spot": spot})
        # Seguir: lo que pasa al pulsarlo.
        act = step.get("act", "click")
        if box is None or act == "none":
            continue
        if act == "click":
            click(ws, box)
        elif act == "file":
            choose_file(ws, csv_path)
        else:
            ws.js(act)
        time.sleep(step.get("wait", 2.5))
    return images, spots


def shoot(demo: dict) -> tuple[dict, dict]:
    work = Path(tempfile.mkdtemp(prefix="sobreala-tutorial-"))
    csv_path = work / "mis-contactos.csv"
    csv_path.write_text(CSV, encoding="utf-8")
    # PayPal con credenciales de mentira: en producción cobra, y sin ellas
    # Facturación lo enseñaría como «pronto». La tarjeta y Yappy siguen así,
    # como allá. Nada de esto llega a hablar con PayPal.
    import os
    os.environ.setdefault("PAYPAL_CLIENT_ID", "tutorial")
    os.environ.setdefault("PAYPAL_SECRET", "tutorial")
    panel = shots.start_panel(work / "panel.log")
    chrome = None
    try:
        shots.wait_for(f"http://127.0.0.1:{PANEL_PORT}/login")
        chrome = subprocess.Popen(
            [CHROME, "--headless=new", "--disable-gpu",
             f"--remote-debugging-port={PORT}", f"--user-data-dir={work / 'chrome'}",
             "--no-first-run", "--hide-scrollbars", "--force-device-scale-factor=2",
             f"--window-size={VIEW_W},{VIEW_H}",
             f"http://127.0.0.1:{PANEL_PORT}/login"],
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
                    for method in ("Runtime.enable", "Page.enable", "DOM.enable"):
                        ws.call(method)
                    break
            except Exception:
                pass
            time.sleep(0.5)
        if ws is None:
            raise RuntimeError("Chrome no abrió")
        ws.call("Emulation.setDeviceMetricsOverride", width=VIEW_W, height=VIEW_H,
                deviceScaleFactor=2, mobile=False)
        time.sleep(1.5)
        ws.js("(function(){var f=document.getElementById('email');if(!f)return;"
              "f=f.form;f.email.value=%s;f.password.value=%s;f.submit();})()"
              % (json.dumps(EMAIL), json.dumps(PASSWORD)))
        time.sleep(3)
        images, data = {}, {}
        for tour, steps in TOURS:
            print(f"  {tour}…")
            made, spots = walk(ws, tour, steps, csv_path, demo)
            images.update(made)
            data[tour] = spots
        return images, data
    finally:
        if chrome:
            chrome.terminate()
        panel.terminate()
        time.sleep(1)


# ----------------------------------------------------------------- el comando

def missing() -> list[str]:
    faltan = []
    if not DATA.exists():
        return [str(DATA.relative_to(ROOT))]
    data = json.loads(DATA.read_text(encoding="utf-8"))
    for tour, steps in TOURS:
        if [s["id"] for s in data.get(tour, [])] != [s["id"] for s in steps]:
            faltan.append(f"{tour} (los pasos cambiaron)")
        for index, _ in enumerate(steps):
            for theme in THEMES:
                path = OUT / theme / f"{image_name(tour, index)}.webp"
                if not path.exists():
                    faltan.append(str(path.relative_to(ROOT)))
    return faltan


def main() -> None:
    if "--check" in sys.argv:
        faltan = missing()
        if faltan:
            print("Faltan tutoriales:", ", ".join(faltan))
            print("Correlos con: python landing/tutorials.py")
            raise SystemExit(1)
        print("Los tutoriales estan, en los dos temas.")
        return

    print("Sembrando la cuenta de demostracion…")
    demo = seed()
    print("Recorriendo el panel…")
    images, data = shoot(demo)
    for theme in THEMES:
        folder = OUT / theme
        folder.mkdir(parents=True, exist_ok=True)
        for old in folder.glob("*.webp"):
            old.unlink()
    total = 0
    for name, themes in images.items():
        for theme, raw in themes.items():
            (OUT / theme / f"{name}.webp").write_bytes(raw)
            total += len(raw)
    DATA.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n",
                    encoding="utf-8", newline="\n")
    print(f"  {sum(len(s) for s in data.values())} pasos, {total // 1024} KB")


if __name__ == "__main__":
    main()
