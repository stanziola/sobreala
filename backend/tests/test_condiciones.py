"""Las condiciones del masivo (octubre de 2026, `services/audience.py`).

Lo que se fija aquí: que cada operador compara como su tipo sobre Mongo de
verdad (los números como números aunque se guarden como texto, las fechas por
su orden, el texto sin importar mayúsculas y sin que un punto sea un comodín);
que un valor vacío, que falta o mal escrito no cumple nunca, ni siquiera
«distinto de»; que una lista se mira por sus filas, por alguna fila o por la
suma de un dato; que una condición que no vale no se guarda, y una que dejó de
valer frena la campaña en vez de agrandarla; que la cuenta en vivo pide el
permiso de enviar; y que la API valida igual que el panel.
"""

from __future__ import annotations

from bson import ObjectId

from test_api_contactos import llave
from test_campaigns import catch, csrf, ready, send_it
from test_users import as_member

from blueprints.campaigns import routes as campaign_routes
from models import account as accounts
from models import campaign as campaigns
from models import campaign_run as runs
from models import contact as contacts
from services import audience, background, fields, sender

DEFINITIONS = [
    {"key": "MONTO", "label": "Monto", "type": "number"},
    {"key": "CIUDAD", "label": "Ciudad", "type": "text"},
    {"key": "VENCE", "label": "Vence", "type": "date"},
    {"key": "ACTIVO", "label": "Activo", "type": "yesno"},
    {"key": "TRANSACCIONES", "label": "Transacciones", "type": "list",
     "items": [{"key": "FECHA", "label": "Fecha", "type": "date"},
               {"key": "MONTO", "label": "Monto", "type": "number"},
               {"key": "TIPO", "label": "Tipo", "type": "text"}]},
]


def sembrar(database, gente: dict) -> ObjectId:
    """Contactos escritos directo en la base, cada uno con sus columnas."""
    cuenta = ObjectId()
    database.contacts.insert_many([
        {"account_id": cuenta, "email": email, "email_normalized": email,
         "fields": valores} for email, valores in gente.items()])
    # Uno de otra cuenta que cumple todo: no tiene que salir nunca.
    database.contacts.insert_one({"account_id": ObjectId(), "email": "ajeno@x.com",
                                  "email_normalized": "ajeno@x.com",
                                  "fields": {"MONTO": "999999", "CIUDAD": "Santiago"}})
    return cuenta


def quienes(database, cuenta, reglas, match="all") -> list[str]:
    """A quién elige esa condición: las direcciones, en orden."""
    limpias, problemas = audience.parse({"match": match, "rules": reglas}, DEFINITIONS)
    assert problemas == [], problemas
    consulta = audience.query(limpias, DEFINITIONS)
    return sorted(one["email"] for one in database.contacts.find(
        {"account_id": cuenta, **consulta}))


def regla(field, op, value="", **extra):
    return {"field": field, "op": op, "value": value, **extra}


# ------------------------------------------------------------ cada tipo

def test_los_numeros_se_comparan_como_numeros(database):
    cuenta = sembrar(database, {
        "cincuenta@x.com": {"MONTO": "50"},
        "cien@x.com": {"MONTO": "100"},
        "mil@x.com": {"MONTO": "1234.5"},
        "decimal@x.com": {"MONTO": "0.3"},
        "vacio@x.com": {"MONTO": ""},
        "falta@x.com": {},
        "malo@x.com": {"MONTO": "abc"},
    })
    # Como texto, «1234.5» sería menor que «50».
    assert quienes(database, cuenta, [regla("MONTO", "gt", "100")]) == ["mil@x.com"]
    assert quienes(database, cuenta, [regla("MONTO", "gte", "100")]) == [
        "cien@x.com", "mil@x.com"]
    # Lo vacío, lo que falta y lo mal escrito no son «menos que 100».
    assert quienes(database, cuenta, [regla("MONTO", "lt", "100")]) == [
        "cincuenta@x.com", "decimal@x.com"]
    assert quienes(database, cuenta, [regla("MONTO", "lte", "50")]) == [
        "cincuenta@x.com", "decimal@x.com"]
    # El valor de la regla se lee como el de un contacto: con comas o con B/.
    assert quienes(database, cuenta, [regla("MONTO", "eq", "B/.1,234.50")]) == ["mil@x.com"]
    assert quienes(database, cuenta, [regla("MONTO", "eq", ".3")]) == ["decimal@x.com"]
    # Ni «distinto de» deja entrar a quien no tiene un número.
    assert quienes(database, cuenta, [regla("MONTO", "ne", "100")]) == [
        "cincuenta@x.com", "decimal@x.com", "mil@x.com"]


def test_el_texto_sin_mayusculas_y_sin_comodines(database):
    cuenta = sembrar(database, {
        "santiago@x.com": {"CIUDAD": "Santiago"},
        "veraguas@x.com": {"CIUDAD": "santiago de Veraguas"},
        "panama@x.com": {"CIUDAD": "Panamá"},
        "punto@x.com": {"CIUDAD": "axb"},
        "vacio@x.com": {"CIUDAD": ""},
        "falta@x.com": {},
    })
    assert quienes(database, cuenta, [regla("CIUDAD", "eq", "SANTIAGO")]) == ["santiago@x.com"]
    assert quienes(database, cuenta, [regla("CIUDAD", "ne", "santiago")]) == [
        "panama@x.com", "punto@x.com", "veraguas@x.com"]
    assert quienes(database, cuenta, [regla("CIUDAD", "contains", "TIAGO")]) == [
        "santiago@x.com", "veraguas@x.com"]
    assert quienes(database, cuenta, [regla("CIUDAD", "not_contains", "tiago")]) == [
        "panama@x.com", "punto@x.com"]
    assert quienes(database, cuenta, [regla("CIUDAD", "starts", "san")]) == [
        "santiago@x.com", "veraguas@x.com"]
    # Un punto es un punto, no «cualquier letra»; y lo demás tampoco es código.
    assert quienes(database, cuenta, [regla("CIUDAD", "eq", "a.b")]) == []
    assert quienes(database, cuenta, [regla("CIUDAD", "contains", ".*")]) == []
    assert quienes(database, cuenta, [regla("CIUDAD", "contains", "(")]) == []


def test_las_fechas_por_su_orden(database):
    cuenta = sembrar(database, {
        "octubre@x.com": {"VENCE": "2026-10-01"},
        "diciembre@x.com": {"VENCE": "2026-12-31"},
        "vacio@x.com": {"VENCE": ""},
        "falta@x.com": {},
        "mala@x.com": {"VENCE": "pronto"},
    })
    assert quienes(database, cuenta, [regla("VENCE", "before", "2026-11-01")]) == [
        "octubre@x.com"]
    assert quienes(database, cuenta, [regla("VENCE", "after", "01/11/2026")]) == [
        "diciembre@x.com"]
    assert quienes(database, cuenta, [regla("VENCE", "on", "01/10/2026")]) == ["octubre@x.com"]


def test_si_o_no_sin_valor(database):
    cuenta = sembrar(database, {"si@x.com": {"ACTIVO": "si"}, "no@x.com": {"ACTIVO": "no"},
                                "vacio@x.com": {"ACTIVO": ""}, "falta@x.com": {}})
    assert quienes(database, cuenta, [regla("ACTIVO", "yes")]) == ["si@x.com"]
    assert quienes(database, cuenta, [regla("ACTIVO", "no", "lo que sea")]) == ["no@x.com"]


def filas(*pares):
    return [{"FECHA": fecha, "MONTO": monto, "id": f"a{n:05x}"}
            for n, (fecha, monto) in enumerate(pares)]


def test_una_lista_por_sus_filas_por_alguna_o_por_la_suma(database):
    cuenta = sembrar(database, {
        "cuatro@x.com": {"TRANSACCIONES": filas(*[("2026-09-0%d" % n, "100") for n in range(1, 5)])},
        "una@x.com": {"TRANSACCIONES": filas(("2026-10-15", "600"))},
        "sin_lista@x.com": {},
        "decimales@x.com": {"TRANSACCIONES": filas(("2026-08-01", "0.1"), ("2026-08-02", "0.2"))},
        "mal@x.com": {"TRANSACCIONES": [{"MONTO": "abc", "id": "b00001"},
                                        {"FECHA": "2026-07-01", "id": "b00002"}]},
        "no_es_lista@x.com": {"TRANSACCIONES": "texto"},
    })
    filas_de = {"field": "TRANSACCIONES", "measure": "rows"}
    assert quienes(database, cuenta, [{**filas_de, "op": "gt", "value": "3"}]) == ["cuatro@x.com"]
    # Sin la lista son cero filas, y eso sí es «menos de una».
    assert quienes(database, cuenta, [{**filas_de, "op": "lt", "value": "1"}]) == [
        "no_es_lista@x.com", "sin_lista@x.com"]

    alguna = {"field": "TRANSACCIONES", "measure": "any"}
    assert quienes(database, cuenta, [{**alguna, "item": "FECHA", "op": "after",
                                       "value": "2026-10-01"}]) == ["una@x.com"]
    assert quienes(database, cuenta, [{**alguna, "item": "MONTO", "op": "gt",
                                       "value": "500"}]) == ["una@x.com"]
    # Una fila con el monto mal escrito no es «menos de 1».
    assert quienes(database, cuenta, [{**alguna, "item": "MONTO", "op": "lt",
                                       "value": "1"}]) == ["decimales@x.com"]

    suma = {"field": "TRANSACCIONES", "measure": "sum", "item": "MONTO"}
    assert quienes(database, cuenta, [{**suma, "op": "gte", "value": "400"}]) == [
        "cuatro@x.com", "una@x.com"]
    # En decimal, 0.1 + 0.2 es 0.3 exacto.
    assert quienes(database, cuenta, [{**suma, "op": "eq", "value": "0.3"}]) == [
        "decimales@x.com"]


def test_todas_o_alguna(database):
    cuenta = sembrar(database, {
        "las_dos@x.com": {"MONTO": "200", "CIUDAD": "Santiago"},
        "monto@x.com": {"MONTO": "200", "CIUDAD": "Soná"},
        "ciudad@x.com": {"MONTO": "10", "CIUDAD": "Santiago"},
        "ninguna@x.com": {"MONTO": "10", "CIUDAD": "Soná"},
    })
    dos = [regla("MONTO", "gt", "100"), regla("CIUDAD", "eq", "santiago")]
    assert quienes(database, cuenta, dos) == ["las_dos@x.com"]
    assert quienes(database, cuenta, dos, match="any") == [
        "ciudad@x.com", "las_dos@x.com", "monto@x.com"]


# ------------------------------------------------------------ validar y decir

def test_lo_que_no_vale_se_dice_con_su_numero():
    def problema(reglas, match="all"):
        _, problemas = audience.parse({"match": match, "rules": reglas}, DEFINITIONS)
        return [audience.problem_text(*one) for one in problemas]

    assert problema([regla("MONTO", "gt", "1"), regla("CIUDAD", "gt", "a")]) == [
        "Condición 2: ese operador no va con esa columna."]
    assert problema([regla("NADA", "eq", "1")]) == ["Condición 1: esa columna no existe."]
    assert problema([regla("MONTO", "gt", "abc")]) == [
        "Condición 1: falta el valor, o no es del tipo de la columna."]
    assert problema([regla("MONTO", "gt", "")]) == [
        "Condición 1: falta el valor, o no es del tipo de la columna."]
    for raro in ("inf", "nan", "1e999", {"$gt": ""}, ["1"], True):
        assert problema([regla("MONTO", "gt", raro)]) == [
            "Condición 1: falta el valor, o no es del tipo de la columna."], raro
    # Un objeto donde va un texto no se convierte en texto.
    assert problema([regla({"$ne": None}, "eq", "1")]) == ["Condición 1: no se entiende."]
    assert problema([{"field": "TRANSACCIONES", "measure": "rows", "op": "gt",
                      "value": "3.5"}]) == [
        "Condición 1: la cantidad de filas es un número entero, de 0 a 50."]
    assert problema([{"field": "TRANSACCIONES", "measure": "sum", "item": "TIPO",
                      "op": "gt", "value": "1"}]) == [
        "Condición 1: solo se suman los datos de tipo número."]
    assert problema([{"field": "TRANSACCIONES", "op": "gt", "value": "1"}]) == [
        "Condición 1: de una lista se elige la cantidad de filas, alguna fila o la "
        "suma de un dato."]
    assert problema([regla("MONTO", "gt", "1")] * 11) == ["Son como mucho 10 condiciones."]
    assert problema([regla("MONTO", "gt", "1")], match="cualquiera") == [
        "Elige si se cumplen todas o alguna."]
    # Sin reglas no es un error: sale a sus etiquetas, como siempre.
    assert audience.parse({"match": "all", "rules": []}, DEFINITIONS) == (None, [])
    assert audience.parse(None, DEFINITIONS) == (None, [])
    assert audience.parse("todo", DEFINITIONS) == (None, [(-1, "audience_bad_shape")])


def test_un_numero_largo_cabe_redondeado(database):
    """Un número de 40 cifras no se puede guardar exacto en un decimal de Mongo:
    se redondea en vez de romper la consulta."""
    cuenta = sembrar(database, {"grande@x.com": {"MONTO": "2" + "0" * 39}})
    assert quienes(database, cuenta, [regla("MONTO", "gt", "1" + "2" * 39)]) == [
        "grande@x.com"]


def test_la_frase_que_se_lee():
    limpias, _ = audience.parse({"match": "all", "rules": [
        regla("MONTO", "gte", "1,500"), regla("CIUDAD", "eq", "Santiago"),
        regla("VENCE", "before", "2026-11-01"), regla("ACTIVO", "yes"),
        {"field": "TRANSACCIONES", "measure": "rows", "op": "gt", "value": "3"},
        {"field": "TRANSACCIONES", "measure": "any", "item": "FECHA", "op": "after",
         "value": "2026-10-01"},
        {"field": "TRANSACCIONES", "measure": "sum", "item": "MONTO", "op": "gte",
         "value": "500"}]}, DEFINITIONS)
    assert audience.describe(limpias, DEFINITIONS) == (
        "Monto es mayor o igual que 1500 y Ciudad es igual a «Santiago» y "
        "Vence es antes del 1 de noviembre de 2026 y Activo es sí y "
        "Transacciones: la cantidad de filas es mayor que 3 y "
        "Transacciones: en alguna fila, Fecha es después del 1 de octubre de 2026 y "
        "Transacciones: la suma de Monto es mayor o igual que 500")
    limpias["match"] = "any"
    assert " o Ciudad es igual a" in audience.describe(limpias, DEFINITIONS)
    assert audience.describe(None, DEFINITIONS) == ""


def test_una_condicion_vieja_no_se_salta():
    """Si la columna se borró, cambió de tipo o la lista perdió el dato, la
    consulta no se arma: saltarla mandaría la campaña a más gente."""
    limpias, _ = audience.parse({"match": "all", "rules": [
        regla("MONTO", "gt", "100"),
        {"field": "TRANSACCIONES", "measure": "sum", "item": "MONTO", "op": "gt",
         "value": "1"}]}, DEFINITIONS)
    sin_monto = [one for one in DEFINITIONS if one["key"] != "MONTO"]
    como_texto = [{**one, "type": "text"} if one["key"] == "MONTO" else one
                  for one in DEFINITIONS]
    sin_dato = [{**one, "items": one["items"][:1]} if one["key"] == "TRANSACCIONES" else one
                for one in DEFINITIONS]
    for columnas in (sin_monto, como_texto, sin_dato):
        try:
            audience.query(limpias, columnas)
        except audience.Stale as problema:
            assert problema.field in ("MONTO", "TRANSACCIONES")
        else:
            raise AssertionError("una condición vieja se saltó")


def test_los_numeros_raros_ya_no_rompen_ni_se_leen_mal():
    assert fields.parse(".5", fields.NUMBER) == "0.5"
    assert fields.parse("B/.5", fields.NUMBER) == "5"
    assert fields.parse("$1,234.50", fields.NUMBER) == "1234.5"
    for raro in ("inf", "-inf", "nan", "1e999", "..5"):
        assert fields.parse(raro, fields.NUMBER) is None, raro


# ------------------------------------------------------------ el masivo

def con_columnas(client, database, **extra):
    """Una cuenta Empresa (diez columnas) con un monto y una lista."""
    browser, cuenta, pieza = ready(client, database, plan="empresa", howmany=0, **extra)
    assert accounts.add_field(database, cuenta["_id"], label="Monto", kind="number")
    assert accounts.add_field(database, cuenta["_id"], label="Ciudad", kind="text")
    return browser, accounts.by_id(database, cuenta["_id"]), pieza


def gente(database, cuenta, montos: dict, tags=None):
    for email, monto in montos.items():
        contacts.create(database, cuenta["_id"], email=email, tags=tags or [],
                        values={"MONTO": monto, "CIUDAD": "Santiago"},
                        consent=contacts.consent_of(contacts.MEMBERS))


def masivo(browser, pieza, reglas=(), *, cumplan="all", accion="", lista=""):
    datos = {"csrf_token": csrf(browser), "asunto": "Aviso", "pieza": str(pieza),
             "lista": lista, "cuando": "ahora", "cumplan": cumplan,
             "rule_field": [one[0] for one in reglas],
             "rule_op": [one[1] for one in reglas],
             "rule_value": [one[2] for one in reglas]}
    if accion:
        datos["rule_action"] = accion
    return browser.post("/campaigns", data=datos)


def test_el_masivo_sale_solo_a_quien_cumple(client, database, outbox, monkeypatch):
    salidos = catch(monkeypatch)
    browser, cuenta, pieza = con_columnas(client, database)
    gente(database, cuenta, {"poco@x.com": "50", "justo@x.com": "100",
                             "mucho@x.com": "1234.5"})

    hecha = masivo(browser, pieza, [("MONTO", "gt", "100")])
    assert hecha.status_code == 302
    suya = campaigns.for_account(database, cuenta["_id"])[0]
    assert suya["filters"] == {"match": "all", "rules": [
        {"field": "MONTO", "op": "gt", "value": "100"}]}
    assert suya["filters_text"] == "Monto es mayor que 100"

    lista = browser.get("/campaigns").get_data(as_text=True)
    assert "Todos mis contactos, si Monto es mayor que 100" in lista
    pregunta = browser.get(f"/campaigns/{suya['_id']}/send").get_data(as_text=True)
    assert "Monto es mayor que 100" in pregunta
    assert f'action="/campaigns/{suya["_id"]}/send"' in pregunta

    send_it(browser, database, cuenta["_id"])
    assert [one["To"] for one in salidos] == ["mucho@x.com"]
    salida = runs.for_account(database, cuenta["_id"])[0]
    assert salida["filters_text"] == "Monto es mayor que 100"
    enviados = browser.get("/campaigns/sent").get_data(as_text=True)
    assert "Todos mis contactos, si Monto es mayor que 100" in enviados
    detalle = browser.get(f"/campaigns/sent/{salida['_id']}").get_data(as_text=True)
    assert "si Monto es mayor que 100" in detalle


def test_editarla_conserva_y_cambia_sus_condiciones(client, database, outbox):
    browser, cuenta, pieza = con_columnas(client, database)
    masivo(browser, pieza, [("MONTO", "gte", "1,500"), ("CIUDAD", "starts", "San")],
           cumplan="any")
    suya = campaigns.for_account(database, cuenta["_id"])[0]
    pantalla = browser.get(f"/campaigns/{suya['_id']}").get_data(as_text=True)
    assert 'value="1500"' in pantalla and 'value="San"' in pantalla
    assert 'value="any" checked' in pantalla

    browser.post(f"/campaigns/{suya['_id']}", data={
        "csrf_token": csrf(browser), "asunto": "Aviso", "pieza": str(pieza), "lista": "",
        "cuando": "ahora", "cumplan": "all", "rule_field": [""], "rule_op": ["eq"],
        "rule_value": [""]})
    suya = campaigns.by_id(database, cuenta["_id"], suya["_id"])
    # Sin filas, sin condiciones: sale a sus etiquetas, como siempre.
    assert suya["filters"] is None and suya["filters_text"] == ""


def test_una_condicion_que_no_va_no_se_guarda(client, database, outbox):
    browser, cuenta, pieza = con_columnas(client, database)
    for reglas, frase in (
            ([("CIUDAD", "gt", "a")], "Condición 1: ese operador no va con esa columna."),
            ([("MONTO", "gt", "abc")],
             "Condición 1: falta el valor, o no es del tipo de la columna."),
            ([("MONTO", "gt", "1"), ("NADA", "eq", "1")],
             "Condición 2: esa columna no existe.")):
        pantalla = masivo(browser, pieza, reglas)
        assert pantalla.status_code == 200
        assert frase in pantalla.get_data(as_text=True)
    assert campaigns.count(database, cuenta["_id"]) == 0


def test_agregar_y_quitar_sin_javascript_no_guardan(client, database, outbox):
    browser, cuenta, pieza = con_columnas(client, database)
    otra = masivo(browser, pieza, [("MONTO", "gt", "150")], accion="add")
    pantalla = otra.get_data(as_text=True)
    # La escrita y una vacía, con lo escrito en su sitio.
    assert pantalla.count('class="audience__row"') == 2
    assert 'value="150"' in pantalla

    quitada = masivo(browser, pieza, [("MONTO", "gt", "150"), ("CIUDAD", "eq", "Soná")],
                     accion="remove:0")
    pantalla = quitada.get_data(as_text=True)
    assert pantalla.count('class="audience__row"') == 2
    assert 'value="150"' not in pantalla and 'value="Soná"' in pantalla
    assert campaigns.count(database, cuenta["_id"]) == 0


def test_la_que_dejo_de_valer_no_sale(client, database, outbox, monkeypatch):
    salidos = catch(monkeypatch)
    browser, cuenta, pieza = con_columnas(client, database)
    gente(database, cuenta, {"mucho@x.com": "500"})
    masivo(browser, pieza, [("MONTO", "gt", "100")])
    suya = campaigns.for_account(database, cuenta["_id"])[0]
    # Se borra la columna: la condición ya no tiene qué mirar.
    accounts.remove_field(database, cuenta["_id"], "MONTO")
    contacts.drop_field(database, cuenta["_id"], "MONTO")

    pregunta = browser.get(f"/campaigns/{suya['_id']}/send").get_data(as_text=True)
    assert "Una de sus condiciones ya no vale" in pregunta
    assert f'action="/campaigns/{suya["_id"]}/send"' not in pregunta
    mandada = browser.post(f"/campaigns/{suya['_id']}/send",
                           data={"csrf_token": csrf(browser)})
    assert "done=filters" in mandada.headers["Location"]
    assert salidos == []

    # Por detrás, igual: espera y dice por qué.
    campaigns.set_auto(database, cuenta["_id"], suya["_id"], True)
    background.campaigns_tick(database, "w1")
    assert salidos == []
    assert campaigns.by_id(database, cuenta["_id"], suya["_id"])["waiting"] == ["filters"]
    assert "Una de sus condiciones ya no vale" in browser.get("/campaigns").get_data(as_text=True)
    resultado = sender.run(database, accounts.by_id(database, cuenta["_id"]),
                           campaigns.by_id(database, cuenta["_id"], suya["_id"]))
    assert resultado["blocked"] == ["filters"]


# ------------------------------------------------------------ la cuenta en vivo

def contar(browser, reglas=(), *, lista="", token=None):
    datos = {"csrf_token": csrf(browser) if token is None else token, "lista": lista,
             "cumplan": "all", "rule_field": [one[0] for one in reglas],
             "rule_op": [one[1] for one in reglas],
             "rule_value": [one[2] for one in reglas]}
    return browser.post("/campaigns/audience", data=datos)


def test_la_cuenta_en_vivo(client, database, outbox, monkeypatch):
    browser, cuenta, pieza = con_columnas(client, database, tag="Socios")
    gente(database, cuenta, {"a@x.com": "50", "b@x.com": "500"}, tags=["Socios"])
    gente(database, cuenta, {"c@x.com": "900"})

    todos = contar(browser).get_json()
    assert todos == {"count": 3, "text": "Saldría a 3 contactos."}
    assert contar(browser, [("MONTO", "gt", "100")]).get_json()["count"] == 2
    uno = contar(browser, [("MONTO", "gt", "100")], lista="Socios")
    assert uno.get_json() == {"count": 1, "text": "Saldría a 1 contacto."}
    assert uno.headers["Cache-Control"] == "no-store"
    malo = contar(browser, [("MONTO", "gt", "abc")]).get_json()
    assert "count" not in malo and malo["error"].startswith("Condición 1")

    assert contar(browser, token="inventado").status_code == 400
    monkeypatch.setattr(campaign_routes, "AUDIENCE_PER_MINUTE", (1, 60))
    database.rate_limits.delete_many({})
    assert contar(browser).status_code == 200
    assert contar(browser).status_code == 429


def test_la_cuenta_en_vivo_pide_el_permiso_de_enviar(client, database, outbox):
    """Un usuario que solo mira las campañas no puede estrechar la cuenta hasta
    adivinar el monto de cada contacto."""
    _, _, suyo = as_member(client, database, permisos=("campaigns",), outbox=outbox)
    respuesta = contar(suyo, token=csrf(suyo, "/campaigns"))
    assert respuesta.status_code == 403
    assert "count" not in respuesta.get_json()


# ------------------------------------------------------------ el tipo de una columna

def test_cambiar_el_tipo_reescribe_lo_guardado(client, database, outbox):
    """Al pasar a número, «1,234.50» queda 1234.5: si no, se escribía bien en el
    correo pero una condición no lo comparaba como número."""
    browser, cuenta, _ = ready(client, database, plan="empresa", howmany=0)
    accounts.add_field(database, cuenta["_id"], label="Saldo", kind="text")
    for email, valor in (("a@x.com", "1,234.50"), ("b@x.com", "B/.5"), ("c@x.com", "7")):
        contacts.create(database, cuenta["_id"], email=email, values={"SALDO": valor},
                        consent=contacts.consent_of(contacts.MEMBERS))
    browser.post("/contacts/columns/type", data={
        "csrf_token": csrf(browser, "/contacts/columns"), "columna": "SALDO",
        "type": "number"})
    assert accounts.field_by_key(accounts.by_id(database, cuenta["_id"]),
                                 "SALDO")["type"] == "number"
    guardado = {one["email"]: one["fields"]["SALDO"]
                for one in database.contacts.find({"account_id": cuenta["_id"]})}
    assert guardado == {"a@x.com": "1234.5", "b@x.com": "5", "c@x.com": "7"}


# ------------------------------------------------------------ la API

TODO = ("campaigns:read", "campaigns:write", "campaigns:send")


def test_la_api_valida_igual_y_cuenta_con_las_condiciones(client, database, outbox,
                                                        monkeypatch):
    salidos = catch(monkeypatch)
    _, cuenta, _ = con_columnas(client, database)
    gente(database, cuenta, {"poco@x.com": "50", "mucho@x.com": "500"})
    auth, _ = llave(database, cuenta, scopes=TODO)
    filtros = {"match": "all", "rules": [{"field": "MONTO", "op": "gt", "value": 100}]}
    hecha = client.post("/api/v1/campaigns", headers=auth, json={
        "subject": "Aviso", "text": "Hola", "filters": filtros})
    assert hecha.status_code == 201
    datos = hecha.get_json()
    assert datos["filters"] == {"match": "all", "rules": [
        {"field": "MONTO", "op": "gt", "value": "100"}]}
    assert datos["filters_text"] == "Monto es mayor que 100"
    url = f"/api/v1/campaigns/{datos['id']}"
    assert client.get(url, headers=auth).get_json()["audience"] == 1

    mala = client.patch(url, headers=auth, json={"filters": {"rules": [
        {"field": "MONTO", "op": "gt", "value": "1"},
        {"field": "CIUDAD", "op": "gt", "value": "a"}]}})
    assert mala.status_code == 422
    assert mala.get_json()["error"]["fields"] == {
        "filters.rules[1]": "Condición 2: ese operador no va con esa columna."}
    demasiadas = client.patch(url, headers=auth, json={"filters": {"rules": [
        {"field": "MONTO", "op": "gt", "value": "1"}] * 11}})
    assert demasiadas.get_json()["error"]["fields"] == {
        "filters": "Son como mucho 10 condiciones."}

    # Una condición vieja no deja mandar, y lo dice.
    accounts.remove_field(database, cuenta["_id"], "MONTO")
    vieja = client.post(f"{url}/send", headers=auth)
    assert vieja.status_code == 409
    assert [one["code"] for one in vieja.get_json()["error"]["blocked"]] == ["filters"]
    assert client.get(url, headers=auth).get_json()["audience"] == 0

    # `null` las quita, y sale a todos.
    sin = client.patch(url, headers=auth, json={"filters": None}).get_json()
    assert sin["filters"] is None and sin["filters_text"] is None
    assert client.post(f"{url}/send", headers=auth).status_code == 202
    background.campaigns_tick(database, "w1")
    assert sorted(one["To"] for one in salidos) == ["mucho@x.com", "poco@x.com"]
    envio = client.get("/api/v1/sends", headers=auth).get_json()["data"][0]
    assert envio["filters_text"] is None
