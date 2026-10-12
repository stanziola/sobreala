"""Los países del selector de teléfono: su bandera, su nombre y su prefijo.

Panamá va primero y es el que viene elegido, porque es de donde son casi todos;
los demás, por orden alfabético. La bandera no es una imagen: son las dos
letras del código ISO escritas como «indicadores regionales», que el sistema
dibuja como bandera. Windows no las dibuja, y para eso va la fuente
TwemojiCountryFlags en static/fonts (ver su LICENSE).

El prefijo es el del país. Los del plan de numeración de Norteamérica (Estados
Unidos, Canadá, buena parte del Caribe) comparten el +1, y el número que se
escribe lleva su código de área.
"""

from __future__ import annotations

import re

DEFAULT = "PA"

# (código ISO, nombre, prefijo sin «+»)
_ALL = [
    ("AF", "Afganistán", "93"), ("AL", "Albania", "355"), ("DE", "Alemania", "49"),
    ("AD", "Andorra", "376"), ("AO", "Angola", "244"), ("AI", "Anguila", "1"),
    ("AG", "Antigua y Barbuda", "1"), ("SA", "Arabia Saudita", "966"),
    ("DZ", "Argelia", "213"), ("AR", "Argentina", "54"), ("AM", "Armenia", "374"),
    ("AW", "Aruba", "297"), ("AU", "Australia", "61"), ("AT", "Austria", "43"),
    ("AZ", "Azerbaiyán", "994"), ("BS", "Bahamas", "1"), ("BD", "Bangladés", "880"),
    ("BB", "Barbados", "1"), ("BH", "Baréin", "973"), ("BE", "Bélgica", "32"),
    ("BZ", "Belice", "501"), ("BJ", "Benín", "229"), ("BM", "Bermudas", "1"),
    ("BY", "Bielorrusia", "375"), ("BO", "Bolivia", "591"),
    ("BA", "Bosnia y Herzegovina", "387"), ("BW", "Botsuana", "267"),
    ("BR", "Brasil", "55"), ("BN", "Brunéi", "673"), ("BG", "Bulgaria", "359"),
    ("BF", "Burkina Faso", "226"), ("BI", "Burundi", "257"), ("BT", "Bután", "975"),
    ("CV", "Cabo Verde", "238"), ("KH", "Camboya", "855"), ("CM", "Camerún", "237"),
    ("CA", "Canadá", "1"), ("BQ", "Caribe Neerlandés", "599"), ("QA", "Catar", "974"),
    ("TD", "Chad", "235"), ("CZ", "Chequia", "420"), ("CL", "Chile", "56"),
    ("CN", "China", "86"), ("CY", "Chipre", "357"), ("CO", "Colombia", "57"),
    ("KM", "Comoras", "269"), ("CG", "Congo", "242"), ("KP", "Corea del Norte", "850"),
    ("KR", "Corea del Sur", "82"), ("CI", "Costa de Marfil", "225"),
    ("CR", "Costa Rica", "506"), ("HR", "Croacia", "385"), ("CU", "Cuba", "53"),
    ("CW", "Curazao", "599"), ("DK", "Dinamarca", "45"), ("DM", "Dominica", "1"),
    ("EC", "Ecuador", "593"), ("EG", "Egipto", "20"), ("SV", "El Salvador", "503"),
    ("AE", "Emiratos Árabes Unidos", "971"), ("ER", "Eritrea", "291"),
    ("SK", "Eslovaquia", "421"), ("SI", "Eslovenia", "386"), ("ES", "España", "34"),
    ("US", "Estados Unidos", "1"), ("EE", "Estonia", "372"), ("SZ", "Esuatini", "268"),
    ("ET", "Etiopía", "251"), ("PH", "Filipinas", "63"), ("FI", "Finlandia", "358"),
    ("FJ", "Fiyi", "679"), ("FR", "Francia", "33"), ("GA", "Gabón", "241"),
    ("GM", "Gambia", "220"), ("GE", "Georgia", "995"), ("GH", "Ghana", "233"),
    ("GI", "Gibraltar", "350"), ("GD", "Granada", "1"), ("GR", "Grecia", "30"),
    ("GL", "Groenlandia", "299"), ("GP", "Guadalupe", "590"), ("GU", "Guam", "1"),
    ("GT", "Guatemala", "502"), ("GF", "Guayana Francesa", "594"),
    ("GN", "Guinea", "224"), ("GQ", "Guinea Ecuatorial", "240"),
    ("GW", "Guinea-Bisáu", "245"), ("GY", "Guyana", "592"), ("HT", "Haití", "509"),
    ("HN", "Honduras", "504"), ("HK", "Hong Kong", "852"), ("HU", "Hungría", "36"),
    ("IN", "India", "91"), ("ID", "Indonesia", "62"), ("IQ", "Irak", "964"),
    ("IR", "Irán", "98"), ("IE", "Irlanda", "353"), ("IS", "Islandia", "354"),
    ("KY", "Islas Caimán", "1"), ("CK", "Islas Cook", "682"),
    ("FO", "Islas Feroe", "298"), ("FK", "Islas Malvinas", "500"),
    ("MP", "Islas Marianas del Norte", "1"), ("MH", "Islas Marshall", "692"),
    ("SB", "Islas Salomón", "677"), ("TC", "Islas Turcas y Caicos", "1"),
    ("VG", "Islas Vírgenes Británicas", "1"),
    ("VI", "Islas Vírgenes de los Estados Unidos", "1"), ("IL", "Israel", "972"),
    ("IT", "Italia", "39"), ("JM", "Jamaica", "1"), ("JP", "Japón", "81"),
    ("JO", "Jordania", "962"), ("KZ", "Kazajistán", "7"), ("KE", "Kenia", "254"),
    ("KG", "Kirguistán", "996"), ("KI", "Kiribati", "686"), ("XK", "Kosovo", "383"),
    ("KW", "Kuwait", "965"), ("LA", "Laos", "856"), ("LS", "Lesoto", "266"),
    ("LV", "Letonia", "371"), ("LB", "Líbano", "961"), ("LR", "Liberia", "231"),
    ("LY", "Libia", "218"), ("LI", "Liechtenstein", "423"), ("LT", "Lituania", "370"),
    ("LU", "Luxemburgo", "352"), ("MO", "Macao", "853"),
    ("MK", "Macedonia del Norte", "389"), ("MG", "Madagascar", "261"),
    ("MY", "Malasia", "60"), ("MW", "Malaui", "265"), ("MV", "Maldivas", "960"),
    ("ML", "Malí", "223"), ("MT", "Malta", "356"), ("MA", "Marruecos", "212"),
    ("MQ", "Martinica", "596"), ("MU", "Mauricio", "230"), ("MR", "Mauritania", "222"),
    ("YT", "Mayotte", "262"), ("MX", "México", "52"), ("FM", "Micronesia", "691"),
    ("MD", "Moldavia", "373"), ("MC", "Mónaco", "377"), ("MN", "Mongolia", "976"),
    ("ME", "Montenegro", "382"), ("MS", "Montserrat", "1"), ("MZ", "Mozambique", "258"),
    ("MM", "Myanmar", "95"), ("NA", "Namibia", "264"), ("NR", "Nauru", "674"),
    ("NP", "Nepal", "977"), ("NI", "Nicaragua", "505"), ("NE", "Níger", "227"),
    ("NG", "Nigeria", "234"), ("NO", "Noruega", "47"),
    ("NC", "Nueva Caledonia", "687"), ("NZ", "Nueva Zelanda", "64"),
    ("OM", "Omán", "968"), ("NL", "Países Bajos", "31"), ("PK", "Pakistán", "92"),
    ("PW", "Palaos", "680"), ("PS", "Palestina", "970"), ("PA", "Panamá", "507"),
    ("PG", "Papúa Nueva Guinea", "675"), ("PY", "Paraguay", "595"), ("PE", "Perú", "51"),
    ("PF", "Polinesia Francesa", "689"), ("PL", "Polonia", "48"),
    ("PT", "Portugal", "351"), ("PR", "Puerto Rico", "1"), ("GB", "Reino Unido", "44"),
    ("CF", "República Centroafricana", "236"),
    ("CD", "República Democrática del Congo", "243"),
    ("DO", "República Dominicana", "1"), ("RE", "Reunión", "262"),
    ("RW", "Ruanda", "250"), ("RO", "Rumania", "40"), ("RU", "Rusia", "7"),
    ("WS", "Samoa", "685"), ("AS", "Samoa Americana", "1"),
    ("KN", "San Cristóbal y Nieves", "1"), ("SM", "San Marino", "378"),
    ("PM", "San Pedro y Miquelón", "508"), ("VC", "San Vicente y las Granadinas", "1"),
    ("LC", "Santa Lucía", "1"), ("ST", "Santo Tomé y Príncipe", "239"),
    ("SN", "Senegal", "221"), ("RS", "Serbia", "381"), ("SC", "Seychelles", "248"),
    ("SL", "Sierra Leona", "232"), ("SG", "Singapur", "65"), ("SX", "Sint Maarten", "1"),
    ("SY", "Siria", "963"), ("SO", "Somalia", "252"), ("LK", "Sri Lanka", "94"),
    ("ZA", "Sudáfrica", "27"), ("SD", "Sudán", "249"), ("SS", "Sudán del Sur", "211"),
    ("SE", "Suecia", "46"), ("CH", "Suiza", "41"), ("SR", "Surinam", "597"),
    ("TH", "Tailandia", "66"), ("TW", "Taiwán", "886"), ("TZ", "Tanzania", "255"),
    ("TJ", "Tayikistán", "992"), ("TL", "Timor Oriental", "670"), ("TG", "Togo", "228"),
    ("TO", "Tonga", "676"), ("TT", "Trinidad y Tobago", "1"), ("TN", "Túnez", "216"),
    ("TM", "Turkmenistán", "993"), ("TR", "Turquía", "90"), ("TV", "Tuvalu", "688"),
    ("UA", "Ucrania", "380"), ("UG", "Uganda", "256"), ("UY", "Uruguay", "598"),
    ("UZ", "Uzbekistán", "998"), ("VU", "Vanuatu", "678"), ("VA", "Vaticano", "39"),
    ("VE", "Venezuela", "58"), ("VN", "Vietnam", "84"), ("YE", "Yemen", "967"),
    ("DJ", "Yibuti", "253"), ("ZM", "Zambia", "260"), ("ZW", "Zimbabue", "263"),
]


def flag(iso: str) -> str:
    """Las dos letras como indicadores regionales, que se dibujan como bandera."""
    return "".join(chr(0x1F1E6 + ord(letter) - ord("A")) for letter in iso.upper())


# Panamá primero; los demás como vienen, que ya es por orden alfabético.
COUNTRIES = ([one for one in _ALL if one[0] == DEFAULT]
             + [one for one in _ALL if one[0] != DEFAULT])
BY_ISO = {iso: (name, dial) for iso, name, dial in _ALL}

# Cuál se elige al leer un número guardado que empieza con un prefijo que
# comparten varios: el más probable para quien usa Sobreala.
SHARED_DIAL = {"1": "US", "7": "RU", "39": "IT", "262": "RE", "599": "CW"}


def options() -> list[dict[str, str]]:
    """Lo que dibuja el selector: «🇵🇦 +507», con su código ISO.

    Solo la bandera y el prefijo (octubre de 2026): con el nombre del país era
    largo. El nombre va aparte, en `name`, para el `title` de cada opción, que
    es lo que lee un lector de pantalla y lo que sale al pasar el ratón."""
    return [{"iso": iso, "name": name, "label": f"{flag(iso)} +{dial}"}
            for iso, name, dial in COUNTRIES]


def dial_of(iso: str) -> str | None:
    found = BY_ISO.get((iso or "").upper())
    return found[1] if found else None


def split(stored: str) -> tuple[str, str]:
    """Un número guardado («+50760807972») partido en país y número, para
    volver a llenar el formulario. Uno viejo sin «+» se lee como panameño."""
    text = (stored or "").strip()
    if not text.startswith("+"):
        return DEFAULT, re.sub(r"\D", "", text)
    digits = text[1:]
    # El prefijo más largo que calce: +1 no puede ganarle a +1868 si existiera.
    for size in (3, 2, 1):
        dial = digits[:size]
        if dial == dial_of(DEFAULT):
            return DEFAULT, digits[size:]
        if dial in SHARED_DIAL:
            return SHARED_DIAL[dial], digits[size:]
        match = next((iso for iso, _, code in _ALL if code == dial), None)
        if match:
            return match, digits[size:]
    return DEFAULT, digits
