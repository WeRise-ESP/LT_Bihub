"""
Dashboard Low Ticket — BiHub
Análisis del embudo de leads por fuente, país y estado.
Fuente de datos: contactos de HubSpot filtrados por la propiedad `pgm`
(prefijos P_ / CE_ / C_). Fecha del lead = createdate del contacto.
El estado del lead sale de `lt_lead_status` (embudo propio de Low Ticket).
Ventas = pipeline "Pipeline de ventas" hasta el corte y "WooCommerce Orders"
a partir de él (ver FECHA_CORTE_WOO).
Colores oficiales FC Barcelona.
"""
import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
import os
import re
import time
try:
    from zoneinfo import ZoneInfo
    TZ_CUENTA = ZoneInfo("Europe/Madrid")   # zona horaria de la cuenta de HubSpot
except Exception:
    TZ_CUENTA = timezone.utc

load_dotenv()

try:
    TOKEN = st.secrets["HUBSPOT_TOKEN"]
except Exception:
    TOKEN = os.getenv("HUBSPOT_TOKEN", "")

try:
    ACCOUNT_NAME = st.secrets["ACCOUNT_NAME"]
except Exception:
    ACCOUNT_NAME = os.getenv("ACCOUNT_NAME", "BiHub")

if not TOKEN:
    st.error("❌ HUBSPOT_TOKEN no encontrado. Configúralo en Streamlit Cloud → Settings → Secrets.")
    st.stop()


def _sanea_estado(key, opciones, multi=False):
    """
    Evita el crash 'value not in options' al navegar entre páginas: si el valor
    guardado en session_state de un widget con `key` ya no está en sus opciones
    actuales (porque dependen de datos filtrados / del origen), se descarta antes
    de instanciar el widget.
    """
    if key not in st.session_state:
        return
    if multi:
        st.session_state[key] = [v for v in st.session_state[key] if v in opciones]
    elif st.session_state[key] not in opciones:
        del st.session_state[key]

# ── Paleta oficial Barça ───────────────────────────────────────────────────────
BARCA = {
    "blue":         "#004D98",
    "blue_deep":    "#003B7A",
    "blue_ink":     "#001A40",
    "garnet":       "#A50044",
    "garnet_deep":  "#850036",
    "gold":         "#EDBB00",
    "yellow":       "#FFED02",
    "white":        "#FFFFFF",
    "paper":        "#FAFAFA",
    "bone":         "#F4F2EE",
    "line":         "#E5E5E5",
    "line2":        "#D9D9D9",
    "ink100":       "#111111",
    "ink80":        "#2A2A2A",
    "ink60":        "#555555",
    "ink40":        "#8A8A8A",
    "ink20":        "#BFBFBF",
}

# Estados del embudo Low Ticket (propiedad `lt_lead_status` de HubSpot).
COLOR_ESTADOS = {
    "Negocio ganado":                 BARCA["gold"],
    "Negocio abierto":                BARCA["garnet"],
    "Conversación iniciada":          BARCA["blue"],
    "Primera respuesta automatizada": BARCA["yellow"],
    "Nuevo":                          BARCA["blue_deep"],
    "Sin estado":                     BARCA["line2"],
}

COLOR_FUENTES = [
    BARCA["blue_ink"], BARCA["blue_deep"], BARCA["blue"],
    BARCA["garnet_deep"], BARCA["garnet"],
    BARCA["gold"], BARCA["yellow"],
    BARCA["ink60"], BARCA["ink40"], BARCA["ink20"],
]

st.set_page_config(
    page_title=f"Low Ticket Dashboard — {ACCOUNT_NAME}",
    page_icon="🔵",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(f"""
<style>
  [data-testid="stAppViewContainer"] {{ background:{BARCA['paper']}; }}
  [data-testid="stSidebar"] {{ background:{BARCA['blue_ink']} !important; }}
  [data-testid="stSidebar"] label,
  [data-testid="stSidebar"] p,
  [data-testid="stSidebar"] small {{ color:{BARCA['white']} !important; }}
  .stButton>button {{
      background:{BARCA['garnet']} !important;
      color:{BARCA['white']} !important;
      border:none !important; font-weight:700;
  }}
  .stButton>button:hover {{ background:{BARCA['garnet_deep']} !important; }}
  h1,h2,h3 {{ color:{BARCA['blue_ink']}; }}
  hr {{ border-color:{BARCA['line']}; }}

  /* ── Multiselect en sidebar — fuerza fondo blanco ── */
  [data-testid="stSidebar"] .stMultiSelect [data-baseweb="select"] {{
      background:#ffffff !important;
  }}
  [data-testid="stSidebar"] .stMultiSelect [data-baseweb="select"] * {{
      background:#ffffff !important;
      color:#003366 !important;
  }}
  [data-testid="stSidebar"] .stMultiSelect div[class*="ValueContainer"],
  [data-testid="stSidebar"] .stMultiSelect div[class*="container"],
  [data-testid="stSidebar"] .stMultiSelect div[class*="control"] {{
      background:#ffffff !important;
      color:#003366 !important;
  }}
  /* Tags (chips) seleccionados */
  [data-testid="stSidebar"] [data-baseweb="tag"] {{
      background:{BARCA['blue']} !important;
      color:#ffffff !important;
  }}
  [data-testid="stSidebar"] [data-baseweb="tag"] span,
  [data-testid="stSidebar"] [data-baseweb="tag"] * {{
      color:#ffffff !important;
      background:transparent !important;
  }}
  /* ── Multiselect área principal ── */
  [data-testid="stAppViewContainer"] .stMultiSelect [data-baseweb="select"],
  [data-testid="stAppViewContainer"] .stMultiSelect [data-baseweb="select"] > div {{
      background:#ffffff !important;
      border-color:#cccccc !important;
  }}
  [data-testid="stAppViewContainer"] .stMultiSelect [data-baseweb="select"] * {{
      color:#003366 !important;
      background:#ffffff !important;
  }}
  [data-testid="stAppViewContainer"] [data-baseweb="tag"] {{
      background:{BARCA['blue']} !important;
  }}
  [data-testid="stAppViewContainer"] [data-baseweb="tag"] * {{
      color:#ffffff !important;
      background:transparent !important;
  }}
  /* ── Selectbox área principal (mismo estilo que multiselect) ── */
  [data-testid="stAppViewContainer"] .stSelectbox [data-baseweb="select"],
  [data-testid="stAppViewContainer"] .stSelectbox [data-baseweb="select"] > div {{
      background:#ffffff !important;
      border-color:#cccccc !important;
  }}
  [data-testid="stAppViewContainer"] .stSelectbox [data-baseweb="select"] * {{
      color:#003366 !important;
      background:#ffffff !important;
  }}
  /* Dropdown lista de opciones (global — afecta sidebar y main) */
  [data-baseweb="popover"] [data-baseweb="menu"],
  [data-baseweb="popover"] ul {{
      background:#ffffff !important;
  }}
  [data-baseweb="popover"] [role="option"] {{
      color:#003366 !important;
      background:#ffffff !important;
  }}
  [data-baseweb="popover"] [role="option"]:hover {{
      background:#e8edf2 !important;
  }}

  /* ── Date picker input en sidebar ── */
  [data-testid="stSidebar"] [data-testid="stDateInput"] input {{
      background:{BARCA['white']} !important;
      color:{BARCA['blue_ink']} !important;
      border:1px solid {BARCA['line']} !important;
      border-radius:6px !important;
  }}
  /* ── Calendario flotante (portal, fuera del sidebar) ── */
  [data-baseweb="calendar"],
  [data-baseweb="calendar"] [data-baseweb="month"],
  [data-baseweb="popover"] [data-baseweb="calendar"] {{
      background:#ffffff !important;
  }}
  [data-baseweb="popover"] {{
      background:#ffffff !important;
  }}
  [data-baseweb="calendar"] div,
  [data-baseweb="calendar"] span,
  [data-baseweb="calendar"] button {{
      color:#003366 !important;
      background:transparent !important;
  }}
  [data-baseweb="calendar"] [aria-selected="true"] div {{
      background:{BARCA['blue']} !important;
      border-radius:50% !important;
      color:#ffffff !important;
  }}
  [data-baseweb="calendar"] button:hover div {{
      background:{BARCA['line']} !important;
      border-radius:50% !important;
  }}
  /* Header mes/año */
  [data-baseweb="calendar"] select,
  [data-baseweb="calendar"] [data-baseweb="select"] * {{
      color:#003366 !important;
      background:#ffffff !important;
  }}
</style>
""", unsafe_allow_html=True)

HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
BASE = "https://api.hubapi.com"

# Session reutiliza conexiones TCP — elimina el handshake por cada request
_SESSION = requests.Session()
_SESSION.headers.update(HEADERS)


def hs_post(url: str, payload: dict, max_retries: int = 5) -> dict:
    """
    POST a la API de HubSpot con reintentos ante rate limit (429) y errores
    transitorios (5xx), respetando Retry-After. Lanza excepción si falla de
    forma persistente — así el resultado erróneo NO se cachea (st.cache_data
    no cachea excepciones) y un rerun puede volver a intentarlo.
    """
    last = None
    for attempt in range(max_retries):
        try:
            r = _SESSION.post(url, json=payload, timeout=30)
        except Exception as e:               # error de red / timeout
            last = e
            if attempt == max_retries - 1:
                raise
            time.sleep(min(1.5 * (attempt + 1), 10))
            continue
        if r.status_code == 200:
            return r.json()
        if r.status_code == 429 or r.status_code >= 500:
            wait = r.headers.get("Retry-After")
            wait = float(wait) if wait else 1.5 * (attempt + 1)
            time.sleep(min(wait, 10))
            last = r
            continue
        r.raise_for_status()                 # 4xx no recuperable
    raise RuntimeError(
        f"HubSpot POST {url} falló tras {max_retries} intentos "
        f"(último status {getattr(last, 'status_code', last)})"
    )

# Filtro de contactos por la propiedad `pgm`.
# Solo se traen contactos cuyo valor de pgm empieza por uno de estos prefijos.
PGM_PREFIXES = ("P_", "CE_", "C_")

# Etiquetas legibles del "tipo de programa" (derivado del prefijo de pgm).
TIPO_PROGRAMA = {
    "CE_": "Certificado",
    "P_":  "Programa",
    "C_":  "Curso",
}

# Mínimo histórico para la opción "todos": 2024-01-01
MIN_DATE = "2024-01-01"

# Columnas del dataframe de leads (para devolver un df vacío CON esquema).
LEAD_COLS = [
    "email", "fecha", "mes", "pgm", "tipo_programa", "pais",
    "lead_status", "lead_activado", "intentos", "curso",
    "fuente", "origen_fuente", "programa", "mercado",
    # Origen / campaña (análisis de leads)
    "fuente_original", "fuente_reciente",
    "camp_original", "camp_reciente",
    "orig_d1", "orig_d2", "rec_d1", "rec_d2",
    "fecha_fuente_reciente",
    "record_source", "record_d1", "record_d2", "record_d3",
]

# Etiquetas EXACTAS de HubSpot (en español) para la Fuente original de tráfico
# (hs_analytics_source). Se respeta el nombre tal cual aparece en HubSpot.
FUENTES_ES = {
    "ORGANIC_SEARCH":  "Búsqueda orgánica",
    "PAID_SEARCH":     "Búsqueda de pago",
    "EMAIL_MARKETING": "Marketing por email",
    "SOCIAL_MEDIA":    "Tráfico orgánico de redes sociales",
    "REFERRALS":       "Referencias",
    "OTHER_CAMPAIGNS": "Otras campañas",
    "DIRECT_TRAFFIC":  "Tráfico directo",
    "OFFLINE":         "Fuentes sin conexión",
    "PAID_SOCIAL":     "Redes sociales de pago",
    "AI_REFERRALS":    "Referencias de la IA",
}
# Etiqueta de HubSpot cuando el contacto no tiene fuente asignada.
FUENTE_SIN_ASIGNAR = "Sin asignar"

# Normalización de `lt_lead_status`. HubSpot guarda las etiquetas tal cual las
# ve el comercial (con mayúsculas inconsistentes), así que se normaliza en
# minúsculas y se devuelve siempre la etiqueta canónica del embudo.
LEAD_STATUS_NORM = {
    "nuevo": "Nuevo", "new": "Nuevo",
    "primera respuesta automatizada": "Primera respuesta automatizada",
    "conversación iniciada": "Conversación iniciada",
    "conversacion iniciada": "Conversación iniciada",
    "negocio abierto": "Negocio abierto",
    "negocio ganado": "Negocio ganado",
}

# Orden del embudo, de la etapa más avanzada a la menos avanzada (es el orden
# en que se apilan las barras y se ordenan las leyendas).
ESTADOS_ORDEN = [
    "Negocio ganado", "Negocio abierto", "Conversación iniciada",
    "Primera respuesta automatizada", "Nuevo", "Sin estado",
]

# Low Ticket no tiene estados de descarte (No válido / Ilocalizado / No interés
# solo existen en el embudo de High Ticket). El eje equivalente aquí es si el
# lead llegó a activarse: cualquier estado por encima de "Nuevo" implica que
# hubo interacción.
STATUS_ACTIVADO = {
    "Primera respuesta automatizada", "Conversación iniciada",
    "Negocio abierto", "Negocio ganado",
}


def clasif_activado(lead_status: str) -> str:
    return "Activado" if lead_status in STATUS_ACTIVADO else "Sin actividad"

CONTACT_PROPS = [
    "email",
    "pais_de_residencia", "ip_country", "country", "billing_country",
    "pais_de_la_ip_capabilia",
    # Estado del embudo Low Ticket. `hs_lead_status` se trae también porque
    # algunos contactos LT vienen del equipo comercial y solo lo tienen ahí.
    "lt_lead_status", "hs_lead_status", "num_contacted_notes",
    "curso", "url_curso_de_interes",
    "hs_analytics_source", "hs_analytics_source_data_1", "hs_analytics_source_data_2",
    "hs_latest_source", "hs_latest_source_data_1", "hs_latest_source_data_2",
    "hs_latest_source_timestamp",
    "hs_object_source_label",
    "hs_object_source_detail_1", "hs_object_source_detail_2", "hs_object_source_detail_3",
    "mail_programa_interes",
    "pgm", "createdate",
]

# ── Clasificación de mercado ───────────────────────────────────────────────────
_ESPAÑA_COUNTRIES = {
    "spain","españa","espana","espanya","andorra","es","ad",
    "cataluña","catalunya","barcelona","madrid",
}
_LATAM_COUNTRIES = {
    "argentina","bolivia","brasil","brazil","chile","colombia","costa rica",
    "cuba","dominican republic","república dominicana","ecuador","el salvador",
    "guatemala","honduras","mexico","méxico","nicaragua","panama","panamá",
    "paraguay","peru","perú","puerto rico","uruguay","venezuela",
    "ar","bo","br","cl","co","cr","cu","do","ec","sv","gt","hn","mx",
    "ni","pa","py","pe","pr","uy","ve",
}
_EUROPA_COUNTRIES = {
    # Nombres
    "albania","andorra","armenia","austria","azerbaijan","belarus","belgium",
    "bosnia and herzegovina","bulgaria","croatia","cyprus","czech republic",
    "czechia","denmark","estonia","finland","france","georgia","germany",
    "greece","hungary","iceland","ireland","italy","kazakhstan","kosovo",
    "latvia","liechtenstein","lithuania","luxembourg","malta","moldova",
    "monaco","montenegro","netherlands","north macedonia","norway","poland",
    "portugal","romania","russia","san marino","serbia","slovakia","slovenia",
    "sweden","switzerland","turkey","ukraine","united kingdom","vatican",
    "bélgica","bélgium","alemania","francia","italia","países bajos","holanda",
    "suiza","suecia","noruega","dinamarca","finlandia","austria","grecia",
    "polonia","portugal","rumania","turquía","turquia","ucrania",
    "reino unido","rusia","república checa","república checa",
    # ISO 2
    "al","am","at","az","by","be","ba","bg","hr","cy","cz","dk","ee","fi",
    "fr","ge","de","gr","hu","is","ie","it","kz","xk","lv","li","lt","lu",
    "mt","md","mc","me","nl","mk","no","pl","pt","ro","ru","sm","rs","sk",
    "si","se","ch","tr","ua","gb","va",
}
_MIDDLE_EAST_COUNTRIES = {
    "bahrain","egypt","iran","iraq","israel","jordan","kuwait","lebanon",
    "oman","palestine","qatar","saudi arabia","syria","united arab emirates",
    "uae","yemen","bahrein","egipto","irán","irak","israel","jordania",
    "kuwait","líbano","libano","omán","oman","palestina","qatar","catar",
    "arabia saudita","arabia saudi","siria","emiratos árabes unidos","yemen",
    "bh","eg","ir","iq","il","jo","kw","lb","om","ps","qa","sa","sy","ae","ye",
}
_AFRICA_COUNTRIES = {
    "algeria","angola","benin","botswana","burkina faso","burundi","cameroon",
    "cape verde","central african republic","chad","comoros","congo",
    "democratic republic of the congo","djibouti","egypt","equatorial guinea",
    "eritrea","eswatini","ethiopia","gabon","gambia","ghana","guinea",
    "guinea-bissau","ivory coast","kenya","lesotho","liberia","libya",
    "madagascar","malawi","mali","mauritania","mauritius","morocco","mozambique",
    "namibia","niger","nigeria","rwanda","sao tome and principe","senegal",
    "seychelles","sierra leone","somalia","south africa","south sudan","sudan",
    "tanzania","togo","tunisia","uganda","zambia","zimbabwe",
    "argelia","camerún","kenia","marruecos","nigeria","sudáfrica","sudafrica",
    "túnez","tunez","etiopía","etiopia","ghana","senegal","angola","mozambique",
    "dz","ao","bj","bw","bf","bi","cm","cv","cf","td","km","cg","cd","dj",
    "gq","er","sz","et","ga","gm","gh","gn","gw","ci","ke","ls","lr","ly",
    "mg","mw","ml","mr","mu","ma","mz","na","ne","ng","rw","st","sn","sc",
    "sl","so","za","ss","sd","tz","tg","tn","ug","zm","zw",
}
_NORTH_AMERICA_COUNTRIES = {
    "united states","usa","us","united states of america","canada","ca",
    "estados unidos","canadá","canada",
}
_ASIA_COUNTRIES = {
    "afghanistan","bangladesh","bhutan","brunei","cambodia","china","india",
    "indonesia","japan","laos","malaysia","maldives","mongolia","myanmar",
    "nepal","north korea","pakistan","philippines","singapore","south korea",
    "sri lanka","taiwan","tajikistan","thailand","timor-leste","turkmenistan",
    "uzbekistan","vietnam","afganistán","bangladesh","china","india",
    "indonesia","japón","japon","malasia","pakistan","filipinas","singapur",
    "corea del sur","tailandia","vietnam",
    "af","bd","bt","bn","kh","cn","in","id","jp","la","my","mv","mn","mm",
    "np","kp","pk","ph","sg","kr","lk","tw","tj","th","tl","tm","uz","vn",
}
_OCEANIA_COUNTRIES = {
    "australia","fiji","kiribati","marshall islands","micronesia","nauru",
    "new zealand","palau","papua new guinea","samoa","solomon islands","tonga",
    "tuvalu","vanuatu","nueva zelanda","nueva zelandia",
    "au","fj","ki","mh","fm","nr","nz","pw","pg","ws","sb","to","tv","vu",
}
_JUNK_PAIS = {"seleccione su país...", "selecciona tu país", "other", "otros"}

def resolve_mercado(pais: str) -> str:
    p = pais.lower().strip()
    if not p or p == "sin datos" or p in _JUNK_PAIS:
        return "Sin datos"
    if p in _ESPAÑA_COUNTRIES:
        return "España"
    if p in _LATAM_COUNTRIES:
        return "Latam"
    if p in _EUROPA_COUNTRIES:
        return "Europa"
    if p in _MIDDLE_EAST_COUNTRIES:
        return "Middle East"
    if p in _AFRICA_COUNTRIES:
        return "África"
    if p in _NORTH_AMERICA_COUNTRIES:
        return "Norte América"
    if p in _ASIA_COUNTRIES:
        return "Asia"
    if p in _OCEANIA_COUNTRIES:
        return "Oceanía"
    return "Otro"


# ── Data helpers ──────────────────────────────────────────────────────────────

def resolve_pais(cp):
    for f in ["pais_de_residencia", "ip_country", "pais_de_la_ip_capabilia",
              "country", "billing_country"]:
        v = (cp.get(f) or "").strip()
        if v:
            return v.title()
    return "Sin datos"


def tipo_programa(pgm_val: str) -> str:
    """Deriva el tipo de programa a partir del prefijo de la propiedad pgm."""
    v = (pgm_val or "").strip().upper()
    for pfx, label in TIPO_PROGRAMA.items():
        if v.startswith(pfx):
            return label
    return "Otro"


def pgm_base(pgm_val: str) -> str:
    """
    Código base del programa a partir de pgm, quitando el sufijo de idioma
    final (p. ej. PG_003_EN y PG_003_ES → PG_003). Así se agrupan las
    variantes de idioma / nombres distintos del MISMO programa.
    """
    v = (pgm_val or "").strip().upper()
    if not v:
        return ""
    parts = v.split("_")
    if len(parts) >= 3 and len(parts[-1]) == 2 and parts[-1].isalpha():
        return "_".join(parts[:-1])
    return v


def resolve_fuente(cp):
    raw_o = (cp.get("hs_analytics_source") or "").strip()
    raw_r = (cp.get("hs_latest_source") or "").strip()
    if raw_o:
        return FUENTES_ES.get(raw_o, raw_o.replace("_", " ").title()), "Original"
    if raw_r:
        return FUENTES_ES.get(raw_r, raw_r.replace("_", " ").title()), "Más reciente"
    return FUENTE_SIN_ASIGNAR, "—"


def norm_status(raw):
    if not raw:
        return "Sin estado"
    return LEAD_STATUS_NORM.get(raw.lower().strip(), raw.strip().capitalize())


# Estados de `hs_lead_status` (embudo High Ticket) que se pueden mapear al
# embudo Low Ticket cuando el contacto no tiene `lt_lead_status`. Los estados
# de descarte de HT no tienen equivalente y se dejan en "Nuevo".
_HS_A_LT = {
    "matriculado":           "Negocio ganado",
    "negocio cerrado":       "Negocio abierto",
    "contactado":            "Conversación iniciada",
    "intentando contactar":  "Primera respuesta automatizada",
}


def resolve_lead_status(cp) -> str:
    """
    Estado del lead en el embudo Low Ticket. Fuente principal: `lt_lead_status`.
    Si está vacía se intenta traducir `hs_lead_status`, porque una parte de los
    leads LT los trabaja el equipo comercial sobre el embudo antiguo.
    """
    raw_lt = (cp.get("lt_lead_status") or "").strip()
    if raw_lt:
        return norm_status(raw_lt)
    raw_hs = (cp.get("hs_lead_status") or "").strip().lower()
    if raw_hs in _HS_A_LT:
        return _HS_A_LT[raw_hs]
    return "Sin estado"


def label_fuente(raw: str) -> str:
    """Etiqueta HubSpot (ES) de una fuente de tráfico; 'Sin asignar' si vacía."""
    raw = (raw or "").strip()
    if not raw:
        return FUENTE_SIN_ASIGNAR
    return FUENTES_ES.get(raw, raw.replace("_", " ").title())


def nombre_campana(src_raw: str, d1: str, d2: str) -> str:
    """
    Nombre de la campaña según la fuente:
    - PAID_SEARCH (Google): la campaña está en el drill-down 1.
    - PAID_SOCIAL (Meta):  el drill-down 1 es la plataforma; la campaña está en el 2.
    - Otras: se prefiere el valor que parezca un código de campaña.
    """
    src = (src_raw or "").upper()
    d1 = (d1 or "").strip()
    d2 = (d2 or "").strip()
    if src == "PAID_SOCIAL":
        return d2 or d1 or "Sin campaña"
    if src == "PAID_SEARCH":
        return d1 or d2 or "Sin campaña"
    for v in (d2, d1):
        if v and ("fcb" in v.lower() or "_" in v or "/" in v):
            return v
    return d1 or d2 or "Sin campaña"


# ── Fetching de contactos por propiedad pgm (con caché) ───────────────────────

def _rango_ms_cuenta(fi_date: str, ff_date: str):
    """Convierte [fi_date, ff_date] (YYYY-MM-DD) a epoch ms en la zona de la
    cuenta (Europe/Madrid): inicio 00:00:00 y fin 23:59:59. HubSpot interpreta
    los filtros de fecha en la zona de la cuenta, así que hay que mandar ms."""
    lo = int(datetime.fromisoformat(fi_date).replace(
        hour=0, minute=0, second=0, microsecond=0, tzinfo=TZ_CUENTA).timestamp() * 1000)
    hi = int(datetime.fromisoformat(ff_date).replace(
        hour=23, minute=59, second=59, microsecond=0, tzinfo=TZ_CUENTA).timestamp() * 1000)
    return str(lo), str(hi)


_MESES_ES = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
             "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
             "noviembre": 11, "diciembre": 12}


def edad_desde_texto(dob) -> float:
    """
    Edad a partir de date_of_birth (texto libre: '17.05.1980', '04/08/2003',
    '21 de mayo de 1997', '1980-05-17'…). Devuelve None si no se puede calcular.
    """
    s = str(dob or "").strip().lower()
    if not s:
        return None
    hoy = datetime.now(TZ_CUENTA).date()
    d = None
    for fmt in ("%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            d = datetime.strptime(s, fmt).date()
            break
        except Exception:
            pass
    if d is None:  # '21 de mayo de 1997'
        m = re.search(r"(\d{1,2})\s*de\s*([a-záéíóúñ]+)\s*(?:de\s*)?(\d{4})", s)
        if m and m.group(2) in _MESES_ES:
            try:
                d = date(int(m.group(3)), _MESES_ES[m.group(2)], int(m.group(1)))
            except Exception:
                d = None
    if d is None:  # último recurso: año de 4 cifras → edad aproximada
        m = re.search(r"(19\d{2}|20\d{2})", s)
        if m:
            e = hoy.year - int(m.group(1))
            return e if 10 <= e <= 100 else None
        return None
    e = hoy.year - d.year - ((hoy.month, hoy.day) < (d.month, d.day))
    return e if 10 <= e <= 100 else None


def _fecha_cuenta(iso: str) -> str:
    """Convierte un createdate ISO (UTC) a fecha YYYY-MM-DD en la zona de la
    cuenta (Europe/Madrid), para que coincida con el rango filtrado."""
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.astimezone(TZ_CUENTA).strftime("%Y-%m-%d")
    except Exception:
        return iso[:10]


def _pgm_month_windows(fi_date: str, ff_date: str, days: int = 10):
    """
    Ventanas de `days` días [ini_ms, fin_ms] que cubren [fi_date, ff_date].
    Los límites se interpretan en la zona horaria de la cuenta (Europe/Madrid),
    igual que el filtro de "Fecha de creación" en la UI de HubSpot, para que los
    totales cuadren. Se trocea para (a) paralelizar la paginación y (b) no
    superar el límite de 10.000 resultados de la Search API en rangos amplios.
    """
    fi_dt = datetime.fromisoformat(fi_date).replace(
        hour=0, minute=0, second=0, microsecond=0, tzinfo=TZ_CUENTA)
    ff_dt = datetime.fromisoformat(ff_date).replace(
        hour=23, minute=59, second=59, microsecond=0, tzinfo=TZ_CUENTA)
    fi_ms = int(fi_dt.timestamp() * 1000)
    ff_ms = int(ff_dt.timestamp() * 1000)

    span = timedelta(days=days)
    wins = []
    cur = fi_dt
    for _ in range(5000):  # tope de seguridad
        nxt = cur + span
        w0 = max(int(cur.timestamp() * 1000), fi_ms)
        w1 = min(int(nxt.timestamp() * 1000) - 1, ff_ms)
        if w0 <= w1:
            wins.append((w0, w1))
        if int(nxt.timestamp() * 1000) > ff_ms:
            break
        cur = nxt
    return wins


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_data(fecha_inicio: str, fecha_fin: str) -> pd.DataFrame:
    """
    Contactos cuya propiedad `pgm` empieza por P_ / CE_ / C_ y cuyo
    createdate cae en el período seleccionado. Una fila por contacto.
    """
    fi_date = fecha_inicio if fecha_inicio != "todos" else MIN_DATE
    ff_date = (fecha_fin if fecha_fin != "todos"
               else datetime.now(timezone.utc).strftime("%Y-%m-%d"))

    def _search_window(w0: int, w1: int) -> dict:
        """Devuelve {clave: props} para una ventana de createdate [w0, w1] ms."""
        out: dict = {}
        base = [
            {"propertyName": "createdate", "operator": "GTE", "value": str(w0)},
            {"propertyName": "createdate", "operator": "LTE", "value": str(w1)},
        ]
        # Un filterGroup por prefijo (OR entre grupos, AND dentro de cada grupo)
        groups = [
            {"filters": [{"propertyName": "pgm", "operator": "CONTAINS_TOKEN",
                          "value": f"{pfx}*"}] + base}
            for pfx in PGM_PREFIXES
        ]
        after = None
        while True:
            payload = {
                "filterGroups": groups,
                "properties":   CONTACT_PROPS,
                "sorts": [{"propertyName": "createdate", "direction": "ASCENDING"}],
                "limit": 100,
            }
            if after:
                payload["after"] = after
            # hs_post reintenta ante 429/5xx; si falla de verdad, propaga la
            # excepción (no se cachea un resultado vacío por un rate limit).
            data = hs_post(f"{BASE}/crm/v3/objects/contacts/search", payload)
            for c in data.get("results", []):
                cp = c["properties"]
                # Verificación EXACTA del prefijo (CONTAINS_TOKEN tokeniza por '_')
                if not (cp.get("pgm") or "").strip().upper().startswith(PGM_PREFIXES):
                    continue
                key = (cp.get("email") or "").lower().strip() or c["id"]
                out.setdefault(key, cp)
            pg = data.get("paging", {})
            if "next" not in pg:
                break
            after = pg["next"]["after"]
        return out

    windows = _pgm_month_windows(fi_date, ff_date)
    seen: dict = {}
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = [ex.submit(_search_window, w0, w1) for w0, w1 in windows]
        for f in futs:
            for k, v in f.result().items():
                seen.setdefault(k, v)

    # Vacío legítimo (sin contactos en el período): DataFrame CON columnas
    # para que las secciones que hacen df["..."] no lancen KeyError.
    if not seen:
        return pd.DataFrame(columns=LEAD_COLS)

    rows = []
    for cp in seen.values():
        fuente, origen = resolve_fuente(cp)
        fecha_str = _fecha_cuenta(cp.get("createdate"))
        _pais = resolve_pais(cp)
        pgm_val = (cp.get("pgm") or "").strip()
        _estado = resolve_lead_status(cp)
        _o_d1 = (cp.get("hs_analytics_source_data_1") or "").strip()
        _o_d2 = (cp.get("hs_analytics_source_data_2") or "").strip()
        _r_d1 = (cp.get("hs_latest_source_data_1") or "").strip()
        _r_d2 = (cp.get("hs_latest_source_data_2") or "").strip()
        rows.append({
            "email":            (cp.get("email") or "").lower().strip(),
            "fecha":            fecha_str,
            "mes":              fecha_str[:7],
            "pgm":              pgm_val,
            "tipo_programa":    tipo_programa(pgm_val),
            "pais":             _pais,
            "lead_status":      _estado,
            "lead_activado":    clasif_activado(_estado),
            "intentos":         int(cp.get("num_contacted_notes") or 0),
            "curso":            (cp.get("curso") or "").strip(),
            "fuente":           fuente,
            "origen_fuente":    origen,
            "programa":         (cp.get("mail_programa_interes") or "Sin programa").strip() or "Sin programa",
            "mercado":          resolve_mercado(_pais),
            # ── Origen / campaña ──────────────────────────────────────────────
            "fuente_original":  label_fuente(cp.get("hs_analytics_source")),
            "fuente_reciente":  label_fuente(cp.get("hs_latest_source")),
            "camp_original":    nombre_campana(cp.get("hs_analytics_source"), _o_d1, _o_d2),
            "camp_reciente":    nombre_campana(cp.get("hs_latest_source"), _r_d1, _r_d2),
            "orig_d1":          _o_d1,
            "orig_d2":          _o_d2,
            "rec_d1":           _r_d1,
            "rec_d2":           _r_d2,
            "fecha_fuente_reciente": _fecha_cuenta(cp.get("hs_latest_source_timestamp")),
            "record_source":    (cp.get("hs_object_source_label") or "").strip(),
            "record_d1":        (cp.get("hs_object_source_detail_1") or "").strip(),
            "record_d2":        (cp.get("hs_object_source_detail_2") or "").strip(),
            "record_d3":        (cp.get("hs_object_source_detail_3") or "").strip(),
        })
    return pd.DataFrame(rows)


# ── Pipelines de venta Low Ticket ──────────────────────────────────────────────
# La operativa de venta migró de "Pipeline de ventas" (el histórico, id `default`)
# a "WooCommerce Orders" en mayo de 2026: el pipeline antiguo deja de registrar
# cierres en abril de 2026 y Woo arranca en mayo. Para no contar dos veces el
# mismo pedido durante el solape se aplica un CORTE DURO por fecha de cierre:
#   closedate <  FECHA_CORTE_WOO  →  solo Pipeline de ventas
#   closedate >= FECHA_CORTE_WOO  →  solo WooCommerce Orders
# Si el corte real cambia, basta con mover esta constante.
FECHA_CORTE_WOO = "2026-05-01"

PIPELINE_VENTAS = "default"        # "Pipeline de ventas" (histórico)
PIPELINE_WOO    = "3708462309"     # "WooCommerce Orders" (actual)

# Etapas de cada pipeline que cuentan como venta ganada / perdida.
VENTAS_GANADO   = {"closedwon": "Cierre ganado"}
VENTAS_PERDIDO  = {"closedlost": "Cierre perdido"}
WOO_GANADO      = {"5146661068": "Completado"}
WOO_PERDIDO     = {
    "5177881842": "Cancelado",
    "5177881844": "Fallido",
    "5177881843": "Reembolsado",
    "5177881838": "Carrito abandonado",
}

# Low Ticket no tiene una propiedad de "motivo de cierre perdido" equivalente a
# `motivos_de_cierre_perdido_rst` de RST. El motivo de pérdida se deriva de la
# etapa en la que murió el pedido, que es la información que sí existe.
MOTIVOS_CIERRE_ORDEN = [
    "Cancelado", "Fallido", "Reembolsado", "Carrito abandonado",
    "Cierre perdido",
]


def _pipeline_stages(fi_date: str, ff_date: str):
    """
    Combinaciones (pipeline, etapa_id, etiqueta_etapa, motivo) a consultar para
    el rango pedido, aplicando el corte entre el pipeline histórico y Woo.
    Devuelve solo los pipelines que pueden aportar cierres en el rango, para no
    lanzar búsquedas inútiles.
    """
    combos = []
    # El pipeline histórico solo aporta cierres ANTERIORES al corte.
    if fi_date < FECHA_CORTE_WOO:
        for sid, lbl in VENTAS_GANADO.items():
            combos.append((PIPELINE_VENTAS, sid, "Cierre ganado", lbl))
        for sid, lbl in VENTAS_PERDIDO.items():
            combos.append((PIPELINE_VENTAS, sid, "Cierre perdido", lbl))
    # Woo solo aporta cierres DESDE el corte.
    if ff_date >= FECHA_CORTE_WOO:
        for sid, lbl in WOO_GANADO.items():
            combos.append((PIPELINE_WOO, sid, "Cierre ganado", lbl))
        for sid, lbl in WOO_PERDIDO.items():
            combos.append((PIPELINE_WOO, sid, "Cierre perdido", lbl))
    return combos


def _fuera_del_corte(pipeline_id: str, fecha_cierre: str) -> bool:
    """True si ese cierre cae en el lado del corte que NO le corresponde."""
    if not fecha_cierre:
        return False
    if pipeline_id == PIPELINE_VENTAS:
        return fecha_cierre >= FECHA_CORTE_WOO
    return fecha_cierre < FECHA_CORTE_WOO


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_negocios_cerrados(fecha_inicio: str = "todos",
                            fecha_fin: str = "todos") -> pd.DataFrame:
    """
    Deals cerrados (ganado + perdido) de los pipelines de venta Low Ticket con
    closedate en el período. Enriquece cada deal con la fuente de tráfico del
    contacto asociado. El "motivo" de los perdidos es la etapa en la que murió
    el pedido (Cancelado / Fallido / Reembolsado / Carrito abandonado), porque
    Low Ticket no tiene propiedad de motivo de cierre perdido.
    """
    fi_date = fecha_inicio if fecha_inicio != "todos" else MIN_DATE
    ff_date = fecha_fin     if fecha_fin     != "todos" else "2099-12-31"
    lo_ms, hi_ms = _rango_ms_cuenta(fi_date, ff_date)

    # 1. Recoger los deals cerrados del período con sus propiedades base
    deal_map = {}   # deal_id → {etapa, motivos, fecha_cierre}
    for pipeline_id, stage_id, etapa, motivo in _pipeline_stages(fi_date, ff_date):
        after = None
        while True:
            filters = [
                {"propertyName": "pipeline",  "operator": "EQ", "value": pipeline_id},
                {"propertyName": "dealstage", "operator": "EQ", "value": stage_id},
            ]
            if fecha_inicio != "todos":
                filters.append({"propertyName": "closedate", "operator": "GTE", "value": lo_ms})
                filters.append({"propertyName": "closedate", "operator": "LTE", "value": hi_ms})
            payload = {
                "filterGroups": [{"filters": filters}],
                "properties": ["dealname", "closedate", "createdate",
                               "curso", "id_curso", "amount"],
                "limit": 100,
            }
            if after:
                payload["after"] = after
            data = hs_post(f"{BASE}/crm/v3/objects/deals/search", payload)

            for d in data.get("results", []):
                p = d["properties"]
                fecha_cierre = _fecha_cuenta(p.get("closedate") or p.get("createdate"))
                # Corte histórico/Woo: descarta el cierre que cae en el lado que
                # no le toca para no duplicar pedidos durante el solape.
                if _fuera_del_corte(pipeline_id, fecha_cierre):
                    continue
                try:
                    _imp = float(p.get("amount") or 0)
                except Exception:
                    _imp = 0.0
                deal_map[d["id"]] = {
                    "etapa":        etapa,
                    "motivos":      [motivo],
                    "fecha_cierre": fecha_cierre,
                    "mes":          fecha_cierre[:7] if fecha_cierre else "",
                    "importe":      _imp,
                    "curso":        (p.get("curso") or "").strip(),
                }

            pg = data.get("paging", {})
            if not pg or "next" not in pg:
                break
            after = pg["next"]["after"]

    if not deal_map:
        return pd.DataFrame()

    # 2. Obtener contacto asociado a cada deal (batch associations en paralelo)
    deal_ids = list(deal_map.keys())

    def _assoc_batch(batch):
        res = {}
        try:
            data = hs_post(f"{BASE}/crm/v4/associations/deals/contacts/batch/read",
                           {"inputs": [{"id": did} for did in batch]})
            for item in data.get("results", []):
                did = str(item.get("from", {}).get("id", ""))
                tos = item.get("to", [])
                if tos:
                    res[did] = str(tos[0]["toObjectId"])
        except Exception:
            pass
        return res

    deal_to_contact = {}
    _assoc_batches = [deal_ids[i:i + 100] for i in range(0, len(deal_ids), 100)]
    with ThreadPoolExecutor(max_workers=8) as ex:
        for res in ex.map(_assoc_batch, _assoc_batches):
            deal_to_contact.update(res)

    # 3. Batch read fuente de tráfico y país de los contactos (en paralelo)
    contact_ids = list(set(deal_to_contact.values()))

    def _contact_batch(batch):
        res = {}
        try:
            data = hs_post(
                f"{BASE}/crm/v3/objects/contacts/batch/read",
                {"inputs": [{"id": c} for c in batch],
                 "properties": [
                     "hs_analytics_source", "hs_analytics_source_data_1", "hs_analytics_source_data_2",
                     "hs_latest_source", "hs_latest_source_data_1", "hs_latest_source_data_2",
                     "pais_de_residencia", "ip_country", "country",
                     "billing_country", "pais_de_la_ip_capabilia",
                     "createdate", "pgm",
                     # En Low Ticket el nivel de estudios se recoge en la
                     # propiedad de cursos online, no en la de EPs y másters.
                     "date_of_birth", "nivel_de_estudios",
                 ]},
            )
            for c in data.get("results", []):
                cp = c["properties"]
                fuente, _ = resolve_fuente(cp)
                res[str(c["id"])] = {
                    "fuente":         fuente,
                    "pais":           resolve_pais(cp),
                    "contacto_creado": _fecha_cuenta(cp.get("createdate")),
                    "tipo_programa":  tipo_programa(cp.get("pgm")),
                    "pgm":            (cp.get("pgm") or "").strip(),
                    "camp_original":  nombre_campana(cp.get("hs_analytics_source"),
                                                     cp.get("hs_analytics_source_data_1"),
                                                     cp.get("hs_analytics_source_data_2")),
                    "camp_reciente":  nombre_campana(cp.get("hs_latest_source"),
                                                     cp.get("hs_latest_source_data_1"),
                                                     cp.get("hs_latest_source_data_2")),
                    "edad":           edad_desde_texto(cp.get("date_of_birth")),
                    "nivel_estudios": (cp.get("nivel_de_estudios") or "").strip(),
                }
        except Exception:
            pass
        return res

    contact_data = {}
    _c_batches = [contact_ids[i:i + 100] for i in range(0, len(contact_ids), 100)]
    with ThreadPoolExecutor(max_workers=8) as ex:
        for res in ex.map(_contact_batch, _c_batches):
            contact_data.update(res)

    # 4. Construir dataframe expandiendo motivos múltiples
    _DEFAULT = {"fuente": "Sin datos", "pais": "Sin datos",
                "contacto_creado": "", "tipo_programa": "Otro", "pgm": "",
                "camp_original": "Sin campaña", "camp_reciente": "Sin campaña",
                "edad": None, "nivel_estudios": ""}
    rows = []
    for did, info in deal_map.items():
        cid  = deal_to_contact.get(did, "")
        data = contact_data.get(cid, _DEFAULT)
        # Días entre creación del contacto y cierre del negocio
        dias = None
        if data.get("contacto_creado") and info["fecha_cierre"]:
            try:
                dias = (date.fromisoformat(info["fecha_cierre"])
                        - date.fromisoformat(data["contacto_creado"])).days
            except Exception:
                dias = None
        for motivo in info["motivos"]:
            rows.append({
                "deal_id":       did,
                "etapa":         info["etapa"],
                "motivo":        motivo,
                "fuente":        data["fuente"],
                "pais":          data["pais"],
                "tipo_programa": data["tipo_programa"],
                "pgm":           data.get("pgm", ""),
                "camp_original": data.get("camp_original", "Sin campaña"),
                "camp_reciente": data.get("camp_reciente", "Sin campaña"),
                "edad":          data.get("edad"),
                "nivel_estudios": data.get("nivel_estudios", ""),
                "curso":         info.get("curso", ""),
                "importe":       info.get("importe", 0.0),
                "contacto_creado": data["contacto_creado"],
                "fecha_cierre":  info["fecha_cierre"],
                "dias_cierre":   dias,
                "mes":           info["mes"],
            })

    return pd.DataFrame(rows)


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_ganados_por_programa(fecha_inicio: str, fecha_fin: str) -> pd.DataFrame:
    """
    Deals ganados de los pipelines de venta Low Ticket en el período,
    enriquecidos con mail_programa_interes y país del contacto asociado.
    Respeta el corte histórico/WooCommerce (ver FECHA_CORTE_WOO).
    """
    # 1. Recoger todos los deals ganados con closedate en el rango
    deal_map = {}
    fi_date = fecha_inicio if fecha_inicio != "todos" else MIN_DATE
    ff_date = fecha_fin if fecha_fin != "todos" else "2099-12-31"
    lo_ms, hi_ms = _rango_ms_cuenta(fi_date, ff_date)

    _ganados = [(p, s, e, m) for p, s, e, m in _pipeline_stages(fi_date, ff_date)
                if e == "Cierre ganado"]

    for pipeline_id, stage_id, _etapa, _motivo in _ganados:
        after = None
        while True:
            filters = [
                {"propertyName": "pipeline",  "operator": "EQ", "value": pipeline_id},
                {"propertyName": "dealstage", "operator": "EQ", "value": stage_id},
            ]
            if fecha_inicio != "todos":
                filters.append({"propertyName": "closedate", "operator": "GTE", "value": lo_ms})
                filters.append({"propertyName": "closedate", "operator": "LTE", "value": hi_ms})

            payload = {
                "filterGroups": [{"filters": filters}],
                "properties": ["dealname", "closedate", "curso", "nombre_programa", "id_curso"],
                "limit": 100,
            }
            if after:
                payload["after"] = after
            data = hs_post(f"{BASE}/crm/v3/objects/deals/search", payload)

            for d in data.get("results", []):
                p = d["properties"]
                fecha_c = _fecha_cuenta(p.get("closedate"))
                if _fuera_del_corte(pipeline_id, fecha_c):
                    continue
                deal_map[d["id"]] = {
                    "fecha_cierre":    fecha_c,
                    "mes":             fecha_c[:7] if fecha_c else "",
                    "deal_nombre_prog": (p.get("nombre_programa") or "").strip(),
                    "deal_curso":       (p.get("curso") or "").strip(),
                }

            pg = data.get("paging", {})
            if not pg or "next" not in pg:
                break
            after = pg["next"]["after"]

    if not deal_map:
        return pd.DataFrame()

    # 2. Batch associations deal → contacto
    deal_ids = list(deal_map.keys())
    deal_to_contact = {}
    for i in range(0, len(deal_ids), 100):
        batch = deal_ids[i:i + 100]
        try:
            r = _SESSION.post(
                f"{BASE}/crm/v4/associations/deals/contacts/batch/read",
                json={"inputs": [{"id": did} for did in batch]},
                timeout=30,
            )
            if r.status_code == 200:
                for item in r.json().get("results", []):
                    did = str(item.get("from", {}).get("id", ""))
                    tos = item.get("to", [])
                    if tos:
                        deal_to_contact[did] = str(tos[0]["toObjectId"])
        except Exception:
            pass

    # 3. Batch read mail_programa_interes y país del contacto
    contact_ids = list(set(deal_to_contact.values()))
    contact_data = {}
    for i in range(0, len(contact_ids), 100):
        batch = contact_ids[i:i + 100]
        try:
            r = _SESSION.post(
                f"{BASE}/crm/v3/objects/contacts/batch/read",
                json={"inputs": [{"id": c} for c in batch],
                      "properties": [
                          "mail_programa_interes", "pgm", "curso",
                          "pais_de_residencia", "ip_country", "country",
                          "billing_country", "pais_de_la_ip_capabilia",
                          "hs_analytics_source", "hs_latest_source",
                      ]},
                timeout=30,
            )
            if r.status_code == 200:
                for c in r.json().get("results", []):
                    cp = c["properties"]
                    fuente, _ = resolve_fuente(cp)
                    # En Low Ticket el nombre del producto suele venir en
                    # `curso`; `mail_programa_interes` es residual.
                    _prog = ((cp.get("mail_programa_interes") or "").strip()
                             or (cp.get("curso") or "").strip()
                             or "Sin programa")
                    contact_data[str(c["id"])] = {
                        "programa_contacto": _prog,
                        "pais":              resolve_pais(cp),
                        "fuente":            fuente,
                        "pgm":               (cp.get("pgm") or "").strip(),
                    }
        except Exception:
            pass

    # 4. Construir DataFrame
    rows = []
    for did, info in deal_map.items():
        cid = deal_to_contact.get(did, "")
        cd  = contact_data.get(cid, {
            "programa_contacto": "Sin programa",
            "pais": "Sin datos",
            "fuente": "Sin datos",
            "pgm": "",
        })
        # El nombre del programa viene del contacto (mail_programa_interes o
        # curso). Fallback: nombre_programa y luego curso del propio negocio.
        programa = cd["programa_contacto"]
        if programa == "Sin programa":
            programa = (info["deal_nombre_prog"] or info["deal_curso"]
                        or "Sin programa")

        rows.append({
            "deal_id":      did,
            "programa":     programa,
            "pgm":          cd.get("pgm", ""),
            "pais":         cd["pais"],
            "mercado":      resolve_mercado(cd["pais"]),
            "fuente":       cd["fuente"],
            "fecha_cierre": info["fecha_cierre"],
            "mes":          info["mes"],
        })

    return pd.DataFrame(rows)


# ── Helpers de gráficos ───────────────────────────────────────────────────────

def barca_layout(fig, height=340):
    fig.update_layout(
        height=height,
        paper_bgcolor=BARCA["white"],
        plot_bgcolor=BARCA["white"],
        font_color=BARCA["ink80"],
        title_font=dict(size=14, color=BARCA["blue_ink"]),
        margin=dict(t=44, b=12, l=12, r=12),
        legend=dict(font=dict(size=10)),
    )
    fig.update_xaxes(gridcolor=BARCA["line"], linecolor=BARCA["line2"])
    fig.update_yaxes(gridcolor=BARCA["line"], linecolor=BARCA["line2"])
    return fig


def kpi_card(col, label, value, color=BARCA["blue"]):
    with col:
        st.markdown(f"""
        <div style="background:{BARCA['white']};
                    border-left:5px solid {color};
                    border-radius:8px;padding:18px 20px;
                    box-shadow:0 1px 4px rgba(0,0,0,.08)">
            <div style="font-size:11px;color:{BARCA['ink60']};font-weight:700;
                        text-transform:uppercase;letter-spacing:.7px;
                        margin-bottom:6px">{label}</div>
            <div style="font-size:34px;font-weight:800;
                        color:{color};line-height:1">{value}</div>
        </div>""", unsafe_allow_html=True)


def chart_donut(df, col, title, color_map=None):
    counts = df[col].value_counts().reset_index()
    counts.columns = [col, "Total"]
    fig = px.pie(counts, names=col, values="Total", title=title,
                 hole=0.55, color=col,
                 color_discrete_map=color_map or {})
    fig.update_traces(textposition="outside", textinfo="percent+label",
                      marker=dict(line=dict(color=BARCA["white"], width=2)))
    return barca_layout(fig, 320)


def conclusiones(df, df_mat, df_deals_periodo):
    """
    df               → leads del período (por createdate del contacto)
    df_mat           → ventas del período (negocios de Cierre ganado)
    df_deals_periodo → deals cerrados del período (por closedate)
    """
    total = len(df)
    if total == 0:
        return

    # Embudo Low Ticket: cada etapa incluye a las que vienen detrás, porque un
    # lead que abrió negocio necesariamente pasó por conversación iniciada.
    _resp     = df[df["lead_status"] == "Primera respuesta automatizada"]
    _conv     = df[df["lead_status"] == "Conversación iniciada"]
    _abierto  = df[df["lead_status"] == "Negocio abierto"]
    _ganado   = df[df["lead_status"] == "Negocio ganado"]
    inactivos = df[df["lead_activado"] == "Sin actividad"]

    n_resp    = len(_resp) + len(_conv) + len(_abierto) + len(_ganado)
    n_conv    = len(_conv) + len(_abierto) + len(_ganado)
    n_abierto = len(_abierto) + len(_ganado)

    # Ventas y pérdidas vienen de los pipelines, no del estado del contacto
    n_mat        = len(df_mat)
    tasa_inactiv = len(inactivos) / total * 100
    tasa_mat     = n_mat / total * 100 if total else 0

    perdidos = (df_deals_periodo[df_deals_periodo["etapa"] == "Cierre perdido"]
                if not df_deals_periodo.empty else pd.DataFrame())
    ganados  = (df_deals_periodo[df_deals_periodo["etapa"] == "Cierre ganado"]
                if not df_deals_periodo.empty else pd.DataFrame())
    n_perdidos = perdidos["deal_id"].nunique() if not perdidos.empty else 0
    n_ganados  = ganados["deal_id"].nunique()  if not ganados.empty  else 0

    st.markdown(f"""<hr style="border:1px solid {BARCA['line']};margin:32px 0 24px">""",
                unsafe_allow_html=True)
    st.markdown("## 🔍 Análisis y Conclusiones")

    # ── Resumen ejecutivo + Embudo ─────────────────────────────────────────────
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 📌 Resumen ejecutivo")
        st.markdown(f"""
- **Leads nuevos en el período:** {total}
- **Ventas (Cierre ganado) en el período:** **{n_mat}** (por fecha de cierre)
- **Tasa de conversión leads → venta:** **{tasa_mat:.1f}%**
- **Leads sin actividad** (siguen en 'Nuevo' o sin estado): **{tasa_inactiv:.1f}%** ({len(inactivos)})
- **Cierre ganado:** {n_ganados} negocios · **Cierre perdido:** {n_perdidos} negocios (por fecha de cierre)
""")

    with col2:
        # Embudo de `lt_lead_status`: cada etapa acumula las posteriores.
        # La etapa final usa df_mat (negocios ganados), que es la fuente buena.
        funnel_df = pd.DataFrame({
            "Etapa": [
                f"Leads nuevos ({total})",
                f"Primera respuesta ({n_resp})",
                f"Conversación iniciada ({n_conv})",
                f"Negocio abierto ({n_abierto})",
                f"Venta ganada ({n_mat})",
            ],
            "Cantidad": [total, n_resp, n_conv, n_abierto, n_mat],
        })
        fig = px.funnel(funnel_df, x="Cantidad", y="Etapa",
                        title="Embudo Low Ticket del período",
                        color_discrete_sequence=[BARCA["blue"], BARCA["blue_deep"],
                                                  BARCA["yellow"], BARCA["garnet"],
                                                  BARCA["gold"]])
        barca_layout(fig, 300)
        st.plotly_chart(fig, use_container_width=True)

    # ── Fuentes con más leads que nunca se activan ────────────────────────────
    st.markdown("### ⚠️ Fuentes con más leads sin activar")
    st.caption("Un lead 'sin activar' se quedó en **Nuevo** (o sin estado): nunca llegó "
               "ni a la primera respuesta automatizada.")
    if len(inactivos) > 0:
        mq = inactivos.groupby("fuente").size().reset_index(name="Sin_actividad")
        tf = df.groupby("fuente").size().reset_index(name="Total")
        merge = mq.merge(tf, on="fuente")
        merge["Tasa %"] = (merge["Sin_actividad"] / merge["Total"] * 100).round(1)
        merge = merge.sort_values("Tasa %", ascending=False)

        col1, col2 = st.columns([2, 1])
        with col1:
            fig = px.bar(merge, x="fuente", y="Tasa %",
                         color="Tasa %", text="Tasa %",
                         title="% de leads sin activar por fuente",
                         color_continuous_scale=[BARCA["blue"], BARCA["gold"],
                                                  BARCA["garnet"]])
            fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
            fig.update_layout(coloraxis_showscale=False)
            barca_layout(fig, 320)
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            st.dataframe(
                merge[["fuente", "Total", "Sin_actividad", "Tasa %"]]
                .rename(columns={"fuente": "Fuente", "Sin_actividad": "Sin actividad"}),
                hide_index=True, use_container_width=True
            )

        st.markdown("#### 💡 Acciones recomendadas")
        acciones = {
            "Redes sociales de pago":            "Volumen alto y barato, pero mucha inercia. Revisar la secuencia automatizada de bienvenida y el tiempo hasta el primer mensaje.",
            "Búsqueda de pago":                  "Auditar palabras clave negativas y revisar que la landing del curso deje claro el precio antes del formulario.",
            "Tráfico orgánico de redes sociales": "Intención baja. Reforzar el lead magnet y la automatización de primer contacto.",
            "Otras campañas":                    "Identificar qué campañas generan este tráfico. Revisar UTMs y pausar las que no activan.",
            "Tráfico directo":                   "Alta variabilidad. Mejorar el tracking para identificar el origen real de estos leads.",
            "Búsqueda orgánica":                 "Revisar qué páginas atraen leads que no arrancan. Ajustar el copy y el CTA del curso.",
            "Fuentes sin conexión":              "Definir criterios mínimos antes de registrar el lead en el CRM.",
            "Referencias":                       "Comunicar mejor el perfil de alumno ideal a los referidores.",
        }
        for _, row in merge.head(5).iterrows():
            fuente = row["fuente"]
            tasa = row["Tasa %"]
            if tasa > 5:
                accion = acciones.get(fuente, "Revisar la fuente y la automatización de primer contacto.")
                border = BARCA["garnet"] if tasa > 25 else BARCA["gold"]
                bg = "#FFF5F7" if tasa > 25 else "#FFFDE7"
                badge = "🔴 ALTA" if tasa > 25 else "🟡 MEDIA"
                st.markdown(f"""
<div style="background:{bg};border-left:4px solid {border};
            padding:12px 16px;border-radius:6px;margin:6px 0">
  <span style="font-weight:700;color:{BARCA['blue_ink']}">{badge} · {fuente}</span>
  <span style="color:{BARCA['ink60']};font-size:13px;margin-left:8px">
    {tasa:.1f}% sin activar · {int(row['Sin_actividad'])} de {int(row['Total'])} contactos
  </span><br>
  <span style="color:{BARCA['ink60']};font-size:13px">→ {accion}</span>
</div>""", unsafe_allow_html=True)

    # ── Países con más leads sin activar ──────────────────────────────────────
    st.markdown("### 🌍 Países con más leads sin activar")
    if len(inactivos) > 0:
        mq_p  = inactivos.groupby("pais").size().reset_index(name="Sin actividad")
        tot_p = df.groupby("pais").size().reset_index(name="Total leads")
        mp    = mq_p.merge(tot_p, on="pais")
        mp["Activados"] = mp["Total leads"] - mp["Sin actividad"]
        mp["Tasa %"]    = (mp["Sin actividad"] / mp["Total leads"] * 100).round(1)
        mp_min5 = mp[mp["Total leads"] >= 5].sort_values("Tasa %", ascending=False)
        mp_top  = mp_min5.head(10)

        col_g, col_t = st.columns([3, 2])
        with col_g:
            fig = px.bar(mp_top, x="pais", y="Tasa %", text="Tasa %",
                         color="Tasa %",
                         title="Top 10 países — % sin activar (mín. 5 leads)",
                         color_continuous_scale=[BARCA["blue"], BARCA["gold"], BARCA["garnet"]])
            fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
            fig.update_layout(coloraxis_showscale=False)
            barca_layout(fig, 340)
            st.plotly_chart(fig, use_container_width=True)

        with col_t:
            tabla_pais = (mp_min5[["pais", "Total leads", "Sin actividad", "Activados", "Tasa %"]]
                          .rename(columns={"pais": "País"})
                          .reset_index(drop=True))
            # Colorear la columna Tasa % por severidad
            st.dataframe(
                tabla_pais.style.background_gradient(
                    subset=["Tasa %"],
                    cmap="RdYlGn_r",
                    vmin=0, vmax=100,
                ).format({"Tasa %": "{:.1f}%"}),
                use_container_width=True,
                hide_index=True,
                height=min(500, len(tabla_pais) * 36 + 40),
            )

    # ── Tabla pivote: Contactos por País × Fuente de tráfico ──────────────────
    st.markdown("### 🗺️ Contactos por País y Fuente de tráfico")
    if not df.empty:
        _mercados_pivot = ["España", "Latam", "Europa", "Middle East", "África",
                           "Norte América", "Asia", "Oceanía", "Otro"]
        _mercado_pivot_sel = st.multiselect(
            "Filtrar por mercado (solo esta tabla)",
            options=_mercados_pivot,
            key="pivot_mercado_filter",
            placeholder="Todos los mercados",
        )
        df_pivot = df[df["mercado"].isin(_mercado_pivot_sel)] if _mercado_pivot_sel else df

        pivot = (df_pivot.groupby(["pais", "fuente"])
                 .size()
                 .reset_index(name="Contactos")
                 .pivot(index="pais", columns="fuente", values="Contactos")
                 .fillna(0)
                 .astype(int))
        pivot.insert(0, "Total", pivot.sum(axis=1))
        pivot = pivot.sort_values("Total", ascending=False)
        pivot.index.name = "País"

        st.dataframe(
            pivot.style.background_gradient(
                subset=pivot.columns.tolist(),
                cmap="Blues",
                vmin=0,
            ).format("{:,}"),
            use_container_width=True,
            height=min(600, len(pivot) * 36 + 60),
        )
        st.download_button(
            "⬇️ Descargar tabla País × Fuente",
            data=pivot.reset_index().to_csv(index=False, encoding="utf-8-sig"),
            file_name="pais_fuente_trafico.csv",
            mime="text/csv",
            key="dl_pivot",
        )

    # ── Ventas del período: desglose por fuente y país ────────────────────────
    if n_mat > 0:
        st.markdown("### 🎓 Fuente y país de las ventas del período")
        col1, col2 = st.columns(2)
        with col1:
            mat_f = df_mat.groupby("fuente").size().reset_index(name="Ventas")
            fig = px.bar(mat_f.sort_values("Ventas", ascending=True),
                         x="Ventas", y="fuente", orientation="h",
                         text_auto=True, title="Ventas por fuente",
                         color_discrete_sequence=[BARCA["gold"]])
            fig.update_layout(yaxis=dict(categoryorder="total ascending"))
            barca_layout(fig, 300)
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            mat_p = (df_mat.groupby("pais").size().reset_index(name="Ventas")
                     .sort_values("Ventas", ascending=False).head(10))
            fig = px.bar(mat_p.sort_values("Ventas", ascending=True),
                         x="Ventas", y="pais", orientation="h",
                         text_auto=True, title="Ventas por país (Top 10)",
                         color_discrete_sequence=[BARCA["gold"]])
            fig.update_layout(yaxis=dict(categoryorder="total ascending"))
            barca_layout(fig, 300)
            st.plotly_chart(fig, use_container_width=True)

    # ── Avance del embudo por fuente ──────────────────────────────────────────
    st.markdown("### 🪜 Avance del embudo por fuente de tráfico")
    st.caption("Hasta dónde llega cada fuente en el embudo Low Ticket. "
               "La columna **% Activados** es la que mejor discrimina la calidad "
               "de la fuente: qué parte de sus leads sale del estado 'Nuevo'.")

    tot_fuente = df.groupby("fuente").size().reset_index(name="Total leads")
    act_fuente = (df[df["lead_activado"] == "Activado"]
                  .groupby("fuente").size().reset_index(name="Activados"))
    tabla_emb = tot_fuente.merge(act_fuente, on="fuente", how="left").fillna(0)
    tabla_emb["Activados"] = tabla_emb["Activados"].astype(int)
    tabla_emb["% Activados"] = (tabla_emb["Activados"]
                                / tabla_emb["Total leads"] * 100).round(1)
    tabla_emb = tabla_emb.sort_values("Total leads", ascending=False).rename(
        columns={"fuente": "Fuente de tráfico"})

    col_g, col_t = st.columns([3, 2])
    with col_g:
        emb_por_fuente = (df.groupby(["fuente", "lead_status"])
                          .size().reset_index(name="Total"))
        orden_fuentes = (emb_por_fuente.groupby("fuente")["Total"]
                         .sum().sort_values(ascending=False).index.tolist())
        fig = px.bar(emb_por_fuente, x="fuente", y="Total",
                     color="lead_status", barmode="stack",
                     text_auto=True,
                     title="Estado del embudo por fuente",
                     category_orders={"fuente": orden_fuentes,
                                      "lead_status": ESTADOS_ORDEN},
                     color_discrete_map=COLOR_ESTADOS)
        fig.update_layout(legend=dict(orientation="h", y=-0.45, title="Estado"))
        barca_layout(fig, 380)
        st.plotly_chart(fig, use_container_width=True)

    with col_t:
        _c = BARCA["blue_ink"]
        st.markdown(f"<div style='font-size:13px;font-weight:700;"
                    f"color:{_c};margin-bottom:8px'>Resumen por fuente</div>",
                    unsafe_allow_html=True)
        st.dataframe(
            tabla_emb[["Fuente de tráfico", "Total leads", "Activados", "% Activados"]]
            .style.background_gradient(subset=["% Activados"],
                                       cmap="Greens", vmin=0, vmax=100)
            .format({"% Activados": "{:.1f}%"}),
            use_container_width=True,
            hide_index=True,
            height=min(420, len(tabla_emb) * 36 + 40),
        )


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,{BARCA['blue_ink']} 0%,
                {BARCA['blue_deep']} 60%,{BARCA['blue']} 100%);
                padding:28px 36px;border-radius:12px;
                margin-bottom:28px;
                border-bottom:4px solid {BARCA['garnet']}">
        <div style="display:flex;align-items:center;gap:12px">
            <div>
                <h1 style="color:{BARCA['white']};margin:0;font-size:26px;
                           font-weight:800;letter-spacing:-.3px">
                    Dashboard Low Ticket — {ACCOUNT_NAME}
                </h1>
                <p style="color:{BARCA['line']};margin:5px 0 0;font-size:14px">
                    Embudo y conversión de leads · Contactos por programa (pgm: P_/CE_/C_) · HubSpot CRM
                </p>
            </div>
        </div>
    </div>""", unsafe_allow_html=True)

    # ── Sidebar — navegación de páginas ──────────────────────────────────────────
    with st.sidebar:
        st.markdown(f"<h2 style='color:{BARCA['gold']};margin-bottom:8px'>📄 Página</h2>",
                    unsafe_allow_html=True)
        pagina = st.radio(
            "Navegación",
            ["📊 Dashboard general", "🎓 Conversión por Programa",
             "🧲 Análisis de Leads"],
            label_visibility="collapsed",
        )
        st.markdown("---")

    # ── Sidebar — bloque 1: fecha y fuente (antes de cargar datos) ───────────────
    with st.sidebar:
        st.markdown(f"<h2 style='color:{BARCA['gold']};margin-bottom:16px'>⚙️ Filtros</h2>",
                    unsafe_allow_html=True)

        modo = st.radio("Modo de fecha", ["Período predefinido", "Rango personalizado"])

        if modo == "Período predefinido":
            hoy = date.today()
            ayer = hoy - timedelta(1)
            _fin_mes_ant = hoy.replace(day=1) - timedelta(1)      # último día del mes anterior
            _ini_mes_ant = _fin_mes_ant.replace(day=1)            # primer día del mes anterior
            periodo = st.selectbox("Período", [
                "Este mes", "Mes anterior",
                "Últimos 7 días", "Últimos 14 días", "Últimos 30 días",
                "Últimos 60 días", "Últimos 90 días",
                "Hoy", "Ayer",
                "Abril 2026", "Mayo 2026",
                "2026 completo", "2025 completo",
                "Todos (desde 2024)",
            ], index=0)
            mapa = {
                "Este mes":        (hoy.replace(day=1),   hoy),
                "Mes anterior":    (_ini_mes_ant,         _fin_mes_ant),
                "Hoy":             (hoy,                  hoy),
                "Ayer":            (ayer,                 ayer),
                "Últimos 7 días":  (hoy - timedelta(7),   hoy),
                "Últimos 14 días": (hoy - timedelta(14),  hoy),
                "Últimos 30 días": (hoy - timedelta(30),  hoy),
                "Últimos 60 días": (hoy - timedelta(60),  hoy),
                "Últimos 90 días": (hoy - timedelta(90),  hoy),
                "Abril 2026":      (date(2026, 4, 1),  date(2026, 4, 30)),
                "Mayo 2026":       (date(2026, 5, 1),  date(2026, 5, 31)),
                "2026 completo":   (date(2026, 1, 1),  date(2026, 12, 31)),
                "2025 completo":   (date(2025, 1, 1),  date(2025, 12, 31)),
            }
            if periodo == "Todos (desde 2024)":
                fi, ff = "todos", "todos"
            else:
                fi, ff = mapa.get(periodo, (hoy - timedelta(7), hoy))
        else:
            fi = st.date_input("Desde", value=date(2026, 1, 1))
            ff = st.date_input("Hasta",  value=date.today())

        st.markdown("---")
        filtro_fuente = st.multiselect(
            "Fuente de tráfico",
            options=list(FUENTES_ES.values()) + [FUENTE_SIN_ASIGNAR],
        )
        filtro_tipo = st.multiselect("Tipo de programa",
                                     options=list(TIPO_PROGRAMA.values()))
        filtro_valido = st.multiselect("Actividad del lead",
                                       options=["Activado", "Sin actividad"])

        st.markdown("---")
        if st.button("🔄 Actualizar datos", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

        st.markdown(f"<small style='color:{BARCA['ink20']}'>Contactos: caché 30 min · "
                    f"Métricas: caché 10 min · Fuente: HubSpot CRM (pgm: P_/CE_/C_)</small>",
                    unsafe_allow_html=True)

    # ── Carga (los 3 fetches corren en paralelo) ───────────────────────────────
    if fi == "todos":
        st.info("⏳ Cargando todos los contactos con pgm (P_/CE_/C_) desde 2024. "
                "La primera carga puede tardar ~1 min (luego queda en caché 30 min).", icon="ℹ️")
    with st.spinner("Cargando datos de HubSpot..."):
        with ThreadPoolExecutor(max_workers=4) as _ex:
            _fut_data  = _ex.submit(fetch_data,                  str(fi), str(ff))
            _fut_deals = _ex.submit(fetch_negocios_cerrados,    str(fi), str(ff))
            _fut_prog  = _ex.submit(fetch_ganados_por_programa,  str(fi), str(ff))
        df              = _fut_data.result()
        df_deals        = _fut_deals.result()
        df_ganados_prog = _fut_prog.result()

    if df.empty and df_deals.empty:
        st.warning("No hay datos para el período seleccionado.")
        return

    # Filtrar deals cerrados por closedate del período
    if fi == "todos" or df_deals.empty:
        df_deals_periodo = df_deals
    else:
        df_deals_periodo = df_deals[
            (df_deals["fecha_cierre"] >= str(fi)) &
            (df_deals["fecha_cierre"] <= str(ff))
        ]

    # Ventas = negocios de "Cierre ganado" (por fecha de cierre), 1 fila por deal.
    # Así "ventas" cuadra siempre con "Cierre ganado" en todo el dashboard.
    if not df_deals_periodo.empty:
        df_mat = (df_deals_periodo[df_deals_periodo["etapa"] == "Cierre ganado"]
                  .drop_duplicates("deal_id").copy())
    else:
        df_mat = pd.DataFrame(columns=df_deals_periodo.columns)

    # ── Sidebar — bloque 2: mercado y países dinámicos ────────────────────────
    with st.sidebar:
        _MERCADOS_OPTS = ["España", "Latam", "Europa", "Middle East", "África",
                          "Norte América", "Asia", "Oceanía", "Otro", "Sin datos"]
        filtro_mercado = st.multiselect("Mercado", options=_MERCADOS_OPTS)

        # Combinar países de leads, ventas y deals para la lista completa
        paises_all = set()
        for _d, _col in [(df, "pais"), (df_mat, "pais"), (df_deals_periodo, "pais")]:
            if not _d.empty and _col in _d.columns:
                paises_all.update(_d[_col].dropna().unique())
        paises_opts = sorted([p for p in paises_all if p not in ("Sin datos", "")])
        if "Sin datos" in paises_all:
            paises_opts.append("Sin datos")
        filtro_pais = st.multiselect("País", options=paises_opts)

    # Añadir columna mercado a los tres datasets (siempre fresca)
    for _frame in [df, df_mat, df_deals_periodo]:
        if not _frame.empty and "pais" in _frame.columns:
            _frame["mercado"] = _frame["pais"].apply(resolve_mercado)

    # ── Aplicar filtros a los TRES datasets ───────────────────────────────────
    def _apply(frame, fuente=True, pais=True, tipo=False, valido=False):
        if frame.empty:
            return frame
        if fuente and filtro_fuente and "fuente" in frame.columns:
            frame = frame[frame["fuente"].isin(filtro_fuente)]
        if filtro_mercado and "mercado" in frame.columns:
            frame = frame[frame["mercado"].isin(filtro_mercado)]
        if pais and filtro_pais and "pais" in frame.columns:
            frame = frame[frame["pais"].isin(filtro_pais)]
        if tipo and filtro_tipo and "tipo_programa" in frame.columns:
            frame = frame[frame["tipo_programa"].isin(filtro_tipo)]
        if valido and filtro_valido and "lead_activado" in frame.columns:
            frame = frame[frame["lead_activado"].isin(filtro_valido)]
        return frame

    df              = _apply(df,              fuente=True, pais=True, tipo=True, valido=True)
    df_mat          = _apply(df_mat,          fuente=True, pais=True, tipo=True, valido=True)
    df_deals_periodo = _apply(df_deals_periodo, fuente=True, pais=True, tipo=False, valido=False)

    total         = len(df)
    n_mat         = df_mat["deal_id"].nunique() if "deal_id" in df_mat.columns else 0
    n_perdidos    = (df_deals_periodo[df_deals_periodo["etapa"] == "Cierre perdido"]["deal_id"].nunique()
                     if not df_deals_periodo.empty else 0)
    n_conversac   = (df["lead_status"].isin(
        ["Conversación iniciada", "Negocio abierto", "Negocio ganado"])).sum()
    n_inactivo    = (df["lead_activado"] == "Sin actividad").sum()

    periodo_txt = "Todos (desde 2024)" if fi == "todos" else \
                  f"{fi.strftime('%d/%m/%Y')} → {ff.strftime('%d/%m/%Y')}"

    # ══════════════════════════════════════════════════════════════════════════
    # PÁGINA: Conversión por Programa (return anticipado)
    # ══════════════════════════════════════════════════════════════════════════
    if pagina == "🎓 Conversión por Programa":
        _render_conversion_page(df, df_ganados_prog, fi, ff)
        return

    if pagina == "🧲 Análisis de Leads":
        _render_leads_analysis_page(df, periodo_txt, fi, ff, df_deals_periodo)
        return

    # ══════════════════════════════════════════════════════════════════════════
    # PÁGINA: Dashboard general (resto de main)
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown(
        f"<span style='color:{BARCA['ink60']};font-size:13px'>"
        f"📅 <b>{periodo_txt}</b> · "
        f"<b>{total}</b> leads nuevos · <b>{n_mat}</b> cierres ganados en el período · "
        f"{df['pais'].nunique()} países</span>",
        unsafe_allow_html=True
    )
    st.markdown("<br>", unsafe_allow_html=True)

    # ── KPIs ──────────────────────────────────────────────────────────────────
    c1, c2, c3, c4, c5 = st.columns(5)
    kpi_card(c1, "Leads nuevos",      total,       BARCA["blue"])
    kpi_card(c2, "Ventas",            n_mat,       BARCA["gold"])
    kpi_card(c3, "Negocios Perdidos", n_perdidos,  BARCA["garnet"])
    kpi_card(c4, "En conversación",   n_conversac, BARCA["blue_deep"])
    kpi_card(c5, "Sin actividad",
             f"{n_inactivo} ({n_inactivo/total*100:.0f}%)" if total else "0",
             BARCA["garnet_deep"])

    st.markdown(
        f"<div style='font-size:12px;color:{BARCA['ink40']};margin-top:6px'>"
        f"ℹ️ <b>Leads nuevos</b>: contacto creado en el período (createdate) · "
        f"<b>Ventas</b> = negocios <b>Cierre ganado</b> y <b>Negocios Perdidos</b> = "
        f"<b>Cierre perdido</b> de los pipelines de venta Low Ticket, por <b>fecha de "
        f"cierre</b> del negocio (no por la fecha del contacto) · "
        f"<b>En conversación</b> y <b>Sin actividad</b> salen de <b>lt_lead_status</b></div>",
        unsafe_allow_html=True
    )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Distribución general ───────────────────────────────────────────────────
    st.markdown("### Distribución general")
    col1, col2, col3 = st.columns([1.2, 1.2, 1.6])

    with col1:
        st.plotly_chart(
            chart_donut(df, "lead_status", "Por Estado de Lead", COLOR_ESTADOS),
            use_container_width=True
        )
    with col2:
        fuente_counts = df["fuente"].value_counts().reset_index()
        fuente_counts.columns = ["fuente", "Total"]
        fig = px.pie(fuente_counts, names="fuente", values="Total",
                     title="Por Fuente de Tráfico", hole=0.55,
                     color_discrete_sequence=COLOR_FUENTES)
        fig.update_traces(textposition="outside", textinfo="percent+label",
                          marker=dict(line=dict(color=BARCA["white"], width=2)))
        barca_layout(fig, 320)
        st.plotly_chart(fig, use_container_width=True)
    with col3:
        pais_top = (df.groupby("pais").size().reset_index(name="Total")
                    .sort_values("Total", ascending=False).head(12))
        fig = px.bar(pais_top, x="Total", y="pais", orientation="h",
                     text_auto=True, title="Top 12 países",
                     color="Total",
                     color_continuous_scale=[BARCA["line2"], BARCA["blue_deep"],
                                              BARCA["blue_ink"]])
        fig.update_layout(coloraxis_showscale=False,
                          yaxis=dict(categoryorder="total ascending"))
        barca_layout(fig, 340)
        st.plotly_chart(fig, use_container_width=True)

    # ── Por tipo de programa ─────────────────────────────────────────────────────
    st.markdown("### Distribución por tipo de programa")
    _TIPO_ORDEN = list(TIPO_PROGRAMA.values()) + ["Otro"]
    col1, col2 = st.columns(2)
    with col1:
        tipo_counts = df["tipo_programa"].value_counts().reset_index()
        tipo_counts.columns = ["tipo_programa", "Total"]
        fig = px.bar(tipo_counts, x="tipo_programa", y="Total", text_auto=True,
                     title="Contactos por tipo de programa",
                     color="tipo_programa",
                     color_discrete_sequence=[BARCA["blue"], BARCA["garnet"], BARCA["gold"]],
                     category_orders={"tipo_programa": _TIPO_ORDEN})
        fig.update_layout(showlegend=False, xaxis_title="")
        barca_layout(fig, 300)
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        grp_tipo = df.groupby(["tipo_programa", "lead_status"]).size().reset_index(name="Total")
        fig = px.bar(grp_tipo, x="tipo_programa", y="Total", color="lead_status",
                     barmode="stack", title="Estado de lead por tipo de programa",
                     color_discrete_map=COLOR_ESTADOS,
                     category_orders={"lead_status": ESTADOS_ORDEN,
                                      "tipo_programa": _TIPO_ORDEN})
        fig.update_layout(legend=dict(orientation="h", y=-0.45, font_size=10),
                          xaxis_title="")
        barca_layout(fig, 300)
        st.plotly_chart(fig, use_container_width=True)

    # ── Activación de leads (Activado / Sin actividad) ───────────────────────────
    st.markdown("### Activación de leads")
    st.caption("Activado = el lead superó el estado 'Nuevo' en `lt_lead_status` "
               "(primera respuesta, conversación, negocio abierto o ganado). "
               "Sin actividad = sigue en 'Nuevo' o no tiene estado.")
    _COLOR_VALIDO = {"Activado": BARCA["blue"], "Sin actividad": BARCA["garnet"]}
    _n_valido    = int((df["lead_activado"] == "Activado").sum())
    _n_no_valido = int((df["lead_activado"] == "Sin actividad").sum())
    _pct_valido  = _n_valido / total * 100 if total else 0

    cva, cvb, cvc = st.columns(3)
    kpi_card(cva, "Leads activados",   _n_valido,             BARCA["blue"])
    kpi_card(cvb, "Sin actividad",     _n_no_valido,          BARCA["garnet"])
    kpi_card(cvc, "% Activados",       f"{_pct_valido:.0f}%", BARCA["gold"])

    st.markdown("<br>", unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        vc = df["lead_activado"].value_counts().reset_index()
        vc.columns = ["lead_activado", "Total"]
        fig = px.pie(vc, names="lead_activado", values="Total",
                     title="Activado vs Sin actividad", hole=0.55,
                     color="lead_activado", color_discrete_map=_COLOR_VALIDO)
        fig.update_traces(textposition="outside", textinfo="percent+label",
                          marker=dict(line=dict(color=BARCA["white"], width=2)))
        barca_layout(fig, 320)
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        grp_v = df.groupby(["fuente", "lead_activado"]).size().reset_index(name="Total")
        fig = px.bar(grp_v, x="fuente", y="Total", color="lead_activado",
                     barmode="stack", title="Activado / Sin actividad por fuente",
                     color_discrete_map=_COLOR_VALIDO)
        fig.update_layout(legend=dict(orientation="h", y=-0.4, title="",
                                       font_size=10), xaxis_title="")
        barca_layout(fig, 320)
        st.plotly_chart(fig, use_container_width=True)

    # Tabla: activado / sin actividad por tipo de programa
    _piv_val = (df.groupby(["tipo_programa", "lead_activado"]).size()
                .unstack(fill_value=0))
    for _c in ["Activado", "Sin actividad"]:
        if _c not in _piv_val.columns:
            _piv_val[_c] = 0
    _piv_val["Total"] = _piv_val["Activado"] + _piv_val["Sin actividad"]
    _piv_val["% Activado"] = (_piv_val["Activado"] / _piv_val["Total"] * 100).round(1)
    _piv_val = _piv_val.sort_values("Total", ascending=False)
    _piv_val.index.name = "Tipo de programa"
    st.dataframe(
        _piv_val[["Total", "Activado", "Sin actividad", "% Activado"]]
        .style.format({"% Activado": "{:.1f}%"}),
        use_container_width=True,
    )

    # ── Fuente × Estado ────────────────────────────────────────────────────────
    st.markdown("### Estado de lead por fuente de tráfico")
    grp = df.groupby(["fuente", "lead_status"]).size().reset_index(name="Total")
    col1, col2 = st.columns(2)
    with col1:
        fig = px.bar(grp, x="fuente", y="Total", color="lead_status",
                     barmode="stack", title="Volumen absoluto por fuente",
                     color_discrete_map=COLOR_ESTADOS,
                     category_orders={"lead_status": ESTADOS_ORDEN})
        fig.update_layout(legend=dict(orientation="h", y=-0.5, title="Estado",
                                       font_size=10))
        barca_layout(fig, 400)
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        tot_f = df.groupby("fuente").size().reset_index(name="Total_fuente")
        grp2 = grp.merge(tot_f, on="fuente")
        grp2["Pct"] = (grp2["Total"] / grp2["Total_fuente"] * 100).round(1)
        fig = px.bar(grp2, x="fuente", y="Pct", color="lead_status",
                     barmode="stack", title="Composición % por fuente",
                     color_discrete_map=COLOR_ESTADOS,
                     category_orders={"lead_status": ESTADOS_ORDEN})
        fig.update_layout(yaxis_title="%",
                          legend=dict(orientation="h", y=-0.5, title="Estado",
                                       font_size=10))
        barca_layout(fig, 400)
        st.plotly_chart(fig, use_container_width=True)

    # ── País × Estado ──────────────────────────────────────────────────────────
    st.markdown("### Estado de lead por país (Top 10)")
    top10 = df.groupby("pais").size().nlargest(10).index.tolist()
    df_top = df[df["pais"].isin(top10)]
    grp3 = df_top.groupby(["pais", "lead_status"]).size().reset_index(name="Total")
    col1, col2 = st.columns(2)
    with col1:
        fig = px.bar(grp3, x="pais", y="Total", color="lead_status",
                     barmode="stack", title="Volumen por país",
                     color_discrete_map=COLOR_ESTADOS,
                     category_orders={"lead_status": ESTADOS_ORDEN})
        fig.update_layout(legend=dict(orientation="h", y=-0.5, font_size=10))
        barca_layout(fig, 400)
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        tot_p = df_top.groupby("pais").size().reset_index(name="Total_pais")
        grp4 = grp3.merge(tot_p, on="pais")
        grp4["Pct"] = (grp4["Total"] / grp4["Total_pais"] * 100).round(1)
        fig = px.bar(grp4, x="pais", y="Pct", color="lead_status",
                     barmode="stack", title="Composición % por país",
                     color_discrete_map=COLOR_ESTADOS,
                     category_orders={"lead_status": ESTADOS_ORDEN})
        fig.update_layout(yaxis_title="%",
                          legend=dict(orientation="h", y=-0.5, font_size=10))
        barca_layout(fig, 400)
        st.plotly_chart(fig, use_container_width=True)

    # ── Estado de lead por mercado ────────────────────────────────────────────
    st.markdown("### Estado de lead por mercado")
    grp_m = df.groupby(["mercado", "lead_status"]).size().reset_index(name="Total")
    orden_mercado = (df.groupby("mercado").size()
                     .sort_values(ascending=False).index.tolist())
    col1, col2 = st.columns(2)
    with col1:
        fig = px.bar(grp_m, x="mercado", y="Total", color="lead_status",
                     barmode="stack", title="Volumen por mercado",
                     color_discrete_map=COLOR_ESTADOS,
                     category_orders={"lead_status": ESTADOS_ORDEN,
                                      "mercado": orden_mercado})
        fig.update_layout(legend=dict(orientation="h", y=-0.5, font_size=10))
        barca_layout(fig, 400)
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        tot_m = df.groupby("mercado").size().reset_index(name="Total_mercado")
        grp_m2 = grp_m.merge(tot_m, on="mercado")
        grp_m2["Pct"] = (grp_m2["Total"] / grp_m2["Total_mercado"] * 100).round(1)
        fig = px.bar(grp_m2, x="mercado", y="Pct", color="lead_status",
                     barmode="stack", title="Composición % por mercado",
                     color_discrete_map=COLOR_ESTADOS,
                     category_orders={"lead_status": ESTADOS_ORDEN,
                                      "mercado": orden_mercado})
        fig.update_layout(yaxis_title="%",
                          legend=dict(orientation="h", y=-0.5, font_size=10))
        barca_layout(fig, 400)
        st.plotly_chart(fig, use_container_width=True)

    # ── Tendencia mensual ─────────────────────────────────────────────────────
    if df["mes"].nunique() > 1:
        st.markdown("### Tendencia mensual")
        col1, col2 = st.columns(2)
        with col1:
            gm = df.groupby(["mes", "lead_status"]).size().reset_index(name="Total")
            fig = px.bar(gm, x="mes", y="Total", color="lead_status",
                         barmode="stack", title="Evolución mensual por estado",
                         color_discrete_map=COLOR_ESTADOS,
                         category_orders={"lead_status": ESTADOS_ORDEN})
            fig.update_layout(legend=dict(orientation="h", y=-0.45, font_size=10))
            barca_layout(fig, 340)
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            gm2 = df.groupby(["mes", "fuente"]).size().reset_index(name="Total")
            fig = px.line(gm2, x="mes", y="Total", color="fuente",
                          markers=True, title="Evolución por fuente de tráfico",
                          color_discrete_sequence=COLOR_FUENTES)
            fig.update_layout(legend=dict(orientation="h", y=-0.45, font_size=10))
            barca_layout(fig, 340)
            st.plotly_chart(fig, use_container_width=True)

    # ── Ventas del período ─────────────────────────────────────────────────────
    if not df_mat.empty:
        st.markdown(f"""<hr style="border:1px solid {BARCA['line']};margin:32px 0 20px">""",
                    unsafe_allow_html=True)
        mat_label = "todos los tiempos" if fi == "todos" else periodo_txt
        st.markdown(
            f"### 🎓 Ventas del período "
            f"<span style='font-size:14px;color:{BARCA['ink60']};font-weight:400'>"
            f"({n_mat} cierres ganados · por fecha de cierre del negocio · {mat_label})</span>",
            unsafe_allow_html=True
        )
        col1, col2, col3 = st.columns(3)
        with col1:
            mp = (df_mat.groupby("pais").size()
                  .reset_index(name="Total")
                  .sort_values("Total", ascending=False).head(12))
            fig = px.bar(mp, x="Total", y="pais", orientation="h", text_auto=True,
                         title="Ventas por país (Top 12)",
                         color="Total",
                         color_continuous_scale=[BARCA["line2"], BARCA["gold"],
                                                  BARCA["blue_ink"]])
            fig.update_layout(coloraxis_showscale=False,
                              yaxis=dict(categoryorder="total ascending"))
            barca_layout(fig, 360)
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            mf = (df_mat.groupby("fuente").size()
                  .reset_index(name="Total")
                  .sort_values("Total", ascending=False))
            fig = px.bar(mf, x="fuente", y="Total", text_auto=True,
                         title="Ventas por fuente de tráfico",
                         color="Total",
                         color_continuous_scale=[BARCA["line2"], BARCA["gold"],
                                                  BARCA["garnet"]])
            fig.update_layout(coloraxis_showscale=False)
            barca_layout(fig, 360)
            st.plotly_chart(fig, use_container_width=True)
        with col3:
            _fm = df_mat.copy()
            _fm["_f"] = pd.to_datetime(_fm["fecha_cierre"], errors="coerce")
            _fm = _fm.dropna(subset=["_f"])
            # Semana natural (lunes a domingo), etiquetada por el lunes de inicio
            _fm["_sem"] = _fm["_f"].dt.to_period("W-SUN").dt.start_time
            sm = (_fm.groupby("_sem").size()
                  .reset_index(name="Ventas")
                  .sort_values("_sem"))
            sm["Semana"] = sm["_sem"].dt.strftime("Sem %d/%m")
            if len(sm) > 1:
                fig = px.line(sm, x="Semana", y="Ventas", markers=True,
                              title="Evolución semanal de ventas",
                              color_discrete_sequence=[BARCA["gold"]])
                fig.update_traces(line_width=3, marker_size=8)
            else:
                fig = px.bar(sm, x="Semana", y="Ventas", text_auto=True,
                             title="Ventas por semana",
                             color_discrete_sequence=[BARCA["gold"]])
            fig.update_xaxes(type="category")
            barca_layout(fig, 360)
            st.plotly_chart(fig, use_container_width=True)

        # ── Detalle de matriculaciones (una fila por venta) ────────────────────
        st.markdown("#### 📄 Detalle de ventas")
        _cols_mat = ["pgm", "curso", "pais", "fuente", "edad", "nivel_estudios", "importe"]
        if all(c in df_mat.columns for c in _cols_mat):
            _det_mat = df_mat[_cols_mat].copy().rename(columns={
                "pgm":            "Programa (código)",
                "curso":          "Curso",
                "pais":           "País",
                "fuente":         "Fuente de tráfico",
                "edad":           "Edad",
                "nivel_estudios": "Nivel de estudios",
                "importe":        "Facturación (€)",
            }).sort_values("Facturación (€)", ascending=False)

            # ── Filtros ────────────────────────────────────────────────────────
            mf1, mf2, mf3, mf4, mf5 = st.columns(5)
            with mf1:
                _o_prog = sorted(_det_mat["Programa (código)"].dropna().unique())
                _sanea_estado("matdet_prog", _o_prog, multi=True)
                _f_prog = st.multiselect("Programa (código)", _o_prog, key="matdet_prog")
            with mf2:
                _o_pais = sorted(_det_mat["País"].dropna().unique())
                _sanea_estado("matdet_pais", _o_pais, multi=True)
                _f_pais = st.multiselect("País", _o_pais, key="matdet_pais")
            with mf3:
                _o_fnt = sorted(_det_mat["Fuente de tráfico"].dropna().unique())
                _sanea_estado("matdet_fuente", _o_fnt, multi=True)
                _f_fnt = st.multiselect("Fuente", _o_fnt, key="matdet_fuente")
            with mf4:
                _edades = _det_mat["Edad"].dropna()
                _rng = None
                if len(_edades) and int(_edades.min()) < int(_edades.max()):
                    _emin, _emax = int(_edades.min()), int(_edades.max())
                    _v = st.session_state.get("matdet_edad")
                    if _v is not None and not (isinstance(_v, (list, tuple)) and len(_v) == 2
                                               and _emin <= _v[0] <= _emax and _emin <= _v[1] <= _emax):
                        del st.session_state["matdet_edad"]
                    _rng = st.slider("Edad", _emin, _emax, (_emin, _emax), key="matdet_edad")
                    _rng = None if _rng == (_emin, _emax) else _rng
                else:
                    st.caption("Edad: sin datos suficientes")
            with mf5:
                _o_niv = sorted(x for x in _det_mat["Nivel de estudios"].dropna().unique() if x)
                _sanea_estado("matdet_nivel", _o_niv, multi=True)
                _f_niv = st.multiselect("Nivel de estudios", _o_niv, key="matdet_nivel")

            if _f_prog: _det_mat = _det_mat[_det_mat["Programa (código)"].isin(_f_prog)]
            if _f_pais: _det_mat = _det_mat[_det_mat["País"].isin(_f_pais)]
            if _f_fnt:  _det_mat = _det_mat[_det_mat["Fuente de tráfico"].isin(_f_fnt)]
            if _rng:    _det_mat = _det_mat[_det_mat["Edad"].between(_rng[0], _rng[1])]
            if _f_niv:  _det_mat = _det_mat[_det_mat["Nivel de estudios"].isin(_f_niv)]

            if _det_mat.empty:
                st.info("No hay ventas con los filtros aplicados.")
            else:
                st.dataframe(
                    _det_mat, use_container_width=True, hide_index=True,
                    height=min(520, len(_det_mat) * 36 + 40),
                    column_config={
                        "Programa (código)":  st.column_config.TextColumn(width="small"),
                        "Curso":              st.column_config.TextColumn(width="large"),
                        "País":               st.column_config.TextColumn(width="medium"),
                        "Fuente de tráfico":  st.column_config.TextColumn(width="medium"),
                        "Edad":               st.column_config.NumberColumn(format="%.0f", width="small"),
                        "Nivel de estudios":  st.column_config.TextColumn(width="medium"),
                        "Facturación (€)":    st.column_config.NumberColumn(format="%.0f €", width="small"),
                    },
                )
                st.caption(f"{len(_det_mat)} ventas · Facturación total: "
                           f"{_det_mat['Facturación (€)'].sum():,.0f} €".replace(",", "."))
        else:
            st.info("Actualiza los datos (🔄) para cargar edad, estudios e importe.")

    # ── Negocios cerrados — tabla y gráficos ──────────────────────────────────
    st.markdown(f"""<hr style="border:1px solid {BARCA['line']};margin:32px 0 20px">""",
                unsafe_allow_html=True)
    st.markdown("### 📊 Negocios de venta Low Ticket — Cierre Ganado y Perdido")
    st.caption(
        f"Fuente: **Pipeline de ventas** para cierres anteriores al "
        f"**{FECHA_CORTE_WOO}** y **WooCommerce Orders** a partir de esa fecha "
        f"(la operativa migró de uno a otro; el corte evita contar dos veces el "
        f"mismo pedido). La fecha usada es la del **negocio** (closedate), no la "
        f"del contacto — un lead creado en un mes puede cerrarse en otro. "
        f"Low Ticket no tiene propiedad de motivo de cierre perdido, así que el "
        f"**motivo** es la etapa en la que murió el pedido."
    )

    if df_deals_periodo.empty:
        st.info("No hay negocios cerrados (ganado/perdido) en el período seleccionado.")
    else:
        ganados  = df_deals_periodo[df_deals_periodo["etapa"] == "Cierre ganado"]
        perdidos = df_deals_periodo[df_deals_periodo["etapa"] == "Cierre perdido"]
        n_gan    = ganados["deal_id"].nunique()
        n_per    = perdidos["deal_id"].nunique()
        n_tot    = df_deals_periodo["deal_id"].nunique()
        tasa_conv = n_gan / n_tot * 100 if n_tot else 0

        # KPIs rápidos
        k1, k2, k3, k4 = st.columns(4)
        kpi_card(k1, "Total cerrados",  n_tot,                  BARCA["blue"])
        kpi_card(k2, "Cierre ganado",   n_gan,                  BARCA["gold"])
        kpi_card(k3, "Cierre perdido",  n_per,                  BARCA["garnet"])
        kpi_card(k4, "% Conversión",    f"{tasa_conv:.0f}%",    BARCA["blue_deep"])
        st.markdown("<br>", unsafe_allow_html=True)

        col1, col2 = st.columns(2)

        # ── Gráfico: Motivos de pérdida (etapa del pedido) ────────────────────
        with col1:
            if not perdidos.empty:
                mp = (perdidos.groupby("motivo")["deal_id"]
                      .nunique().reset_index(name="Deals")
                      .sort_values("Deals", ascending=True))
                fig = px.bar(mp, x="Deals", y="motivo", orientation="h",
                             text_auto=True,
                             title=f"Motivos de pérdida ({n_per} negocios)",
                             color="Deals",
                             color_continuous_scale=[BARCA["line2"], BARCA["garnet_deep"],
                                                      BARCA["garnet"]])
                fig.update_layout(coloraxis_showscale=False,
                                  yaxis=dict(categoryorder="total ascending"))
                barca_layout(fig, 360)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Sin cierres perdidos en el período.")

        # ── Gráfico: Evolución mensual ganado vs perdido (por closedate) ───────
        with col2:
            if df_deals_periodo["mes"].nunique() > 0:
                gm = (df_deals_periodo.groupby(["mes", "etapa"])["deal_id"]
                      .nunique().reset_index(name="Deals")
                      .sort_values("mes"))
                fig = px.bar(gm, x="mes", y="Deals", color="etapa",
                             barmode="group", text_auto=True,
                             title="Evolución mensual (por fecha de cierre)",
                             color_discrete_map={
                                 "Cierre ganado":  BARCA["gold"],
                                 "Cierre perdido": BARCA["garnet"],
                             })
                fig.update_layout(legend=dict(orientation="h", y=-0.25, title=""))
                barca_layout(fig, 360)
                st.plotly_chart(fig, use_container_width=True)

        # ── Donut motivos perdido + Cierre ganado por fuente ───────────────────
        col3, col4 = st.columns(2)
        with col3:
            if not perdidos.empty:
                mp_pie = (perdidos.groupby("motivo")["deal_id"]
                          .nunique().reset_index(name="Deals"))
                fig = px.pie(mp_pie, names="motivo", values="Deals",
                             title="Distribución de motivos de pérdida",
                             hole=0.5,
                             color_discrete_sequence=[
                                 BARCA["garnet"], BARCA["garnet_deep"], BARCA["blue"],
                                 BARCA["gold"], BARCA["ink60"], BARCA["ink40"],
                                 BARCA["yellow"], BARCA["blue_deep"],
                             ])
                fig.update_traces(textposition="outside", textinfo="percent+label",
                                  marker=dict(line=dict(color=BARCA["white"], width=2)))
                barca_layout(fig, 340)
                st.plotly_chart(fig, use_container_width=True)

        with col4:
            if not ganados.empty:
                mg = (ganados.groupby("fuente")["deal_id"]
                      .nunique().reset_index(name="Deals")
                      .sort_values("Deals", ascending=True))
                fig = px.bar(mg, x="Deals", y="fuente", orientation="h",
                             text_auto=True,
                             title=f"Cierre ganado por fuente ({n_gan} deals)",
                             color="Deals",
                             color_continuous_scale=[BARCA["line2"], BARCA["gold"],
                                                      BARCA["blue_ink"]])
                fig.update_layout(coloraxis_showscale=False,
                                  yaxis=dict(categoryorder="total ascending"))
                barca_layout(fig, 340)
                st.plotly_chart(fig, use_container_width=True)

        # ── Cierre perdido: Motivo × Fuente de tráfico ─────────────────────────
        if not perdidos.empty:
            st.markdown(
                f"<div style='font-weight:700;color:{BARCA['garnet']};"
                f"font-size:15px;margin:16px 0 8px'>● Cierre perdido — Motivo × Fuente</div>",
                unsafe_allow_html=True,
            )
            col_g, col_t = st.columns([3, 2])
            with col_g:
                grp = (perdidos.groupby(["motivo", "fuente"])["deal_id"]
                       .nunique().reset_index(name="Deals"))
                orden_motivos = (grp.groupby("motivo")["Deals"]
                                 .sum().sort_values(ascending=False).index.tolist())
                fig = px.bar(
                    grp, x="Deals", y="motivo", color="fuente",
                    barmode="stack", orientation="h",
                    title="Motivo de pérdida × Fuente de tráfico",
                    category_orders={"motivo": orden_motivos},
                    color_discrete_sequence=[
                        BARCA["blue_ink"], BARCA["blue_deep"], BARCA["blue"],
                        BARCA["garnet_deep"], BARCA["garnet"],
                        BARCA["gold"], BARCA["yellow"],
                        BARCA["ink60"], BARCA["ink40"], BARCA["ink20"],
                    ],
                )
                fig.update_layout(
                    legend=dict(orientation="h", y=-0.35, title="Fuente"),
                    yaxis=dict(categoryorder="array", categoryarray=orden_motivos[::-1]),
                )
                barca_layout(fig, max(300, len(orden_motivos) * 45 + 80))
                st.plotly_chart(fig, use_container_width=True)
            with col_t:
                tabla_mf = (perdidos.groupby(["motivo", "fuente"])["deal_id"]
                            .nunique().reset_index(name="Deals")
                            .sort_values(["Deals"], ascending=False))
                total_etapa = tabla_mf["Deals"].sum()
                tabla_mf["% total"] = (tabla_mf["Deals"] / total_etapa * 100).round(1).astype(str) + "%"
                tabla_mf.columns = ["Motivo", "Fuente", "Deals", "% total"]
                st.dataframe(tabla_mf, use_container_width=True, hide_index=True,
                             height=min(400, len(tabla_mf) * 36 + 40))

        # ── Tabla resumen general ──────────────────────────────────────────────
        with st.expander("📋 Ver tabla completa de negocios cerrados"):
            tabla = (df_deals_periodo
                     .groupby(["etapa", "motivo", "fuente"])["deal_id"]
                     .nunique()
                     .reset_index(name="Nº Deals")
                     .sort_values(["etapa", "Nº Deals"], ascending=[True, False]))
            totales = tabla.groupby("etapa")["Nº Deals"].transform("sum")
            tabla["% sobre etapa"] = (tabla["Nº Deals"] / totales * 100).round(1).astype(str) + "%"
            tabla.columns = ["Etapa", "Motivo de cierre", "Fuente", "Nº Deals", "% sobre etapa"]
            st.dataframe(tabla, use_container_width=True, hide_index=True)
            st.download_button(
                "⬇️ Descargar CSV",
                data=tabla.to_csv(index=False, encoding="utf-8-sig"),
                file_name=f"negocios_cerrados_{fi}_{ff}.csv",
                mime="text/csv",
                key="dl_negocios",
            )

    # ── Tiempo de cierre: creación del lead → cierre del negocio ───────────────
    st.markdown(f"""<hr style="border:1px solid {BARCA['line']};margin:32px 0 20px">""",
                unsafe_allow_html=True)
    st.markdown("### ⏱️ Tiempo de cierre — creación del lead → cierre del negocio")
    st.caption(
        "Días entre la **fecha de creación del contacto** (lead pgm: P_/CE_/C_) y la "
        "**fecha de cierre de su negocio** (ganado o perdido), para negocios cerrados en el período. "
        "La **mediana** es la referencia principal: el **promedio** se dispara por una cola de "
        "leads que tardan mucho en cerrar."
    )

    _COLOR_ETAPA = {"Cierre ganado": BARCA["gold"], "Cierre perdido": BARCA["garnet"]}
    _TIPOS_PGM = list(TIPO_PROGRAMA.values())   # Certificado / Programa / Curso

    if df_deals_periodo.empty or "dias_cierre" not in df_deals_periodo.columns:
        st.info("Sin negocios cerrados en el período seleccionado.")
    else:
        _dc = df_deals_periodo.drop_duplicates("deal_id").copy()
        _dc = _dc[_dc["dias_cierre"].notna() & (_dc["dias_cierre"] >= 0)]
        # Solo leads pgm (P_/CE_/C_), coherente con el universo de contactos
        _dc = _dc[_dc["tipo_programa"].isin(_TIPOS_PGM)]

        # Filtro por programa específico (código pgm) dentro de esta sección
        _fc1, _fc2 = st.columns(2)
        with _fc1:
            _tipos_disp = ["Todos"] + [t for t in _TIPOS_PGM
                                       if t in _dc["tipo_programa"].unique()]
            _sanea_estado("tc_tipo", _tipos_disp)
            _sel_tipo = st.selectbox("Tipo de programa", _tipos_disp, key="tc_tipo")
        _dc_t = _dc if _sel_tipo == "Todos" else _dc[_dc["tipo_programa"] == _sel_tipo]
        with _fc2:
            _pgm_disp = ["Todos"] + sorted(
                p for p in _dc_t["pgm"].dropna().unique() if p)
            _sanea_estado("tc_pgm", _pgm_disp)
            _sel_pgm = st.selectbox("Programa (código pgm)", _pgm_disp, key="tc_pgm")
        _dc = _dc_t if _sel_pgm == "Todos" else _dc_t[_dc_t["pgm"] == _sel_pgm]

        if _dc.empty:
            st.info("No hay fecha de creación de contacto para calcular el tiempo de cierre.")
        else:
            _g = _dc[_dc["etapa"] == "Cierre ganado"]["dias_cierre"]
            _p = _dc[_dc["etapa"] == "Cierre perdido"]["dias_cierre"]
            _med = lambda s: f"{s.median():.0f} días" if len(s) else "–"

            k1, k2, k3, k4 = st.columns(4)
            kpi_card(k1, "Mediana (global)",  f"{_dc['dias_cierre'].median():.0f} días", BARCA["blue"])
            kpi_card(k2, "Mediana ganado",    _med(_g), BARCA["gold"])
            kpi_card(k3, "Mediana perdido",   _med(_p), BARCA["garnet"])
            kpi_card(k4, "Promedio (ref.)",   f"{_dc['dias_cierre'].mean():.0f} días", BARCA["ink40"])
            st.markdown("<br>", unsafe_allow_html=True)

            col1, col2 = st.columns(2)
            with col1:
                _gtp = (_dc.groupby(["tipo_programa", "etapa"])["dias_cierre"]
                        .median().round(0).reset_index(name="Días"))
                fig = px.bar(_gtp, x="tipo_programa", y="Días", color="etapa",
                             barmode="group", text_auto=".0f",
                             title="Mediana de días hasta el cierre por tipo de programa",
                             color_discrete_map=_COLOR_ETAPA,
                             labels={"tipo_programa": ""})
                fig.update_layout(legend=dict(orientation="h", y=-0.25, title=""))
                barca_layout(fig, 360)
                st.plotly_chart(fig, use_container_width=True)
            with col2:
                fig = px.histogram(_dc, x="dias_cierre", color="etapa", nbins=30,
                                   title="Distribución de días hasta el cierre",
                                   color_discrete_map=_COLOR_ETAPA,
                                   labels={"dias_cierre": "Días hasta el cierre"})
                fig.update_layout(barmode="overlay", legend=dict(orientation="h", y=-0.25, title=""),
                                  yaxis_title="Nº negocios")
                fig.update_traces(opacity=0.75)
                barca_layout(fig, 360)
                st.plotly_chart(fig, use_container_width=True)

            # Tabla resumen por tipo de programa (mediana primero)
            _tab = (_dc.groupby("tipo_programa")["dias_cierre"]
                    .agg(Negocios="count", Mediana="median", Promedio="mean",
                         **{"Mín": "min", "Máx": "max"})
                    .round(1).reset_index()
                    .rename(columns={"tipo_programa": "Tipo de programa"})
                    .sort_values("Negocios", ascending=False))
            st.dataframe(
                _tab, use_container_width=True, hide_index=True,
                column_config={
                    "Mediana":  st.column_config.NumberColumn("Mediana (días)",  format="%.0f"),
                    "Promedio": st.column_config.NumberColumn("Promedio (días)", format="%.1f"),
                    "Mín":      st.column_config.NumberColumn("Mín (días)",       format="%.0f"),
                    "Máx":      st.column_config.NumberColumn("Máx (días)",       format="%.0f"),
                },
            )

    # ── Análisis y conclusiones ───────────────────────────────────────────────
    conclusiones(df, df_mat, df_deals_periodo)

    # ── Tabla y descarga ──────────────────────────────────────────────────────
    with st.expander("📋 Ver datos completos"):
        st.dataframe(
            df[["fecha", "mes", "pgm", "tipo_programa", "curso", "pais", "fuente",
                "lead_status", "lead_activado", "intentos"]]
            .sort_values(["fuente", "lead_status"]),
            use_container_width=True, hide_index=True,
        )
        st.download_button(
            "⬇️ Descargar CSV",
            data=df.to_csv(index=False, encoding="utf-8-sig"),
            file_name=f"{ACCOUNT_NAME.lower()}_low_ticket_{fi}_{ff}.csv",
            mime="text/csv",
        )

    st.markdown(
        f"<br><div style='text-align:center;color:{BARCA['ink40']};font-size:12px'>"
        f"{ACCOUNT_NAME} · Contactos Low Ticket por programa (pgm) · Datos actualizados automáticamente cada 5 min</div>",
        unsafe_allow_html=True
    )


def _render_leads_analysis_page(df, periodo_txt, fi, ff, df_deals_periodo=None):
    """Página de análisis de leads: origen, fuente y campaña por programa."""
    st.markdown("## 🧲 Análisis de Leads — origen y campaña")
    st.caption(
        f"📅 {periodo_txt} · De dónde vienen los leads (pgm P_/CE_/C_): fuente original o más "
        f"reciente, nombre de campaña y detalle de registro. Respeta los filtros del panel lateral."
    )
    if df.empty:
        st.info("No hay leads para el período y filtros seleccionados.")
        return

    PAGO = {"Búsqueda de pago", "Redes sociales de pago"}

    # ── Filtros locales ───────────────────────────────────────────────────────
    f1, f2, f3 = st.columns([1.4, 1, 1])
    with f1:
        origen = st.radio("Origen de tráfico a analizar", ["Original", "Más reciente"],
                          horizontal=True, key="la_origen")
    fuente_col = "fuente_original" if origen == "Original" else "fuente_reciente"
    camp_col   = "camp_original"  if origen == "Original" else "camp_reciente"
    with f2:
        solo_pago = st.checkbox("Solo fuentes de pago", value=False, key="la_pago")
    with f3:
        excl_sin = st.checkbox("Excluir 'Sin campaña'", value=False, key="la_sincamp")

    g1, g2, g3 = st.columns(3)
    with g1:
        _tipo_opts = sorted(df["tipo_programa"].dropna().unique())
        _sanea_estado("la_tipo", _tipo_opts, multi=True)
        tipo_sel = st.multiselect("Tipo de programa", _tipo_opts, key="la_tipo")
    with g2:
        _pgm_opts = sorted(df["pgm"].dropna().unique())
        _sanea_estado("la_pgm", _pgm_opts, multi=True)
        prog_sel = st.multiselect("Programa (pgm)", _pgm_opts, key="la_pgm")
    with g3:
        _fnt_opts = sorted(df[fuente_col].dropna().unique())
        _sanea_estado("la_fuente", _fnt_opts, multi=True)
        fuente_sel = st.multiselect("Fuente", _fnt_opts, key="la_fuente")

    d = df.copy()
    if tipo_sel:   d = d[d["tipo_programa"].isin(tipo_sel)]
    if prog_sel:   d = d[d["pgm"].isin(prog_sel)]
    if fuente_sel: d = d[d[fuente_col].isin(fuente_sel)]
    if solo_pago:  d = d[d[fuente_col].isin(PAGO)]
    if excl_sin:   d = d[d[camp_col] != "Sin campaña"]

    if d.empty:
        st.info("No hay leads con los filtros aplicados.")
        return

    # ── KPIs ──────────────────────────────────────────────────────────────────
    total  = len(d)
    n_camp = d[d[camp_col] != "Sin campaña"][camp_col].nunique()
    n_pgm  = d["pgm"].nunique()
    n_pago = int(d[fuente_col].isin(PAGO).sum())
    k1, k2, k3, k4 = st.columns(4)
    kpi_card(k1, "Leads",       total,                          BARCA["blue"])
    kpi_card(k2, "Campañas",    n_camp,                         BARCA["blue_deep"])
    kpi_card(k3, "Programas",   n_pgm,                          BARCA["gold"])
    kpi_card(k4, "% Pagados",   f"{n_pago/total*100:.0f}%",     BARCA["garnet"])
    st.markdown("<br>", unsafe_allow_html=True)

    # ── Leads por fuente + por tipo de programa ────────────────────────────────
    c1, c2 = st.columns(2)
    with c1:
        fc = d[fuente_col].value_counts().reset_index()
        fc.columns = [fuente_col, "Leads"]
        fig = px.bar(fc.sort_values("Leads"), x="Leads", y=fuente_col, orientation="h",
                     text_auto=True, title=f"Leads por fuente ({origen.lower()})",
                     color="Leads",
                     color_continuous_scale=[BARCA["bone"], BARCA["blue"], BARCA["blue_ink"]],
                     labels={fuente_col: ""})
        fig.update_layout(coloraxis_showscale=False,
                          yaxis=dict(categoryorder="total ascending"))
        barca_layout(fig, max(280, len(fc) * 40))
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        tc = d.groupby(["tipo_programa", fuente_col]).size().reset_index(name="Leads")
        fig = px.bar(tc, x="tipo_programa", y="Leads", color=fuente_col, barmode="stack",
                     title="Leads por tipo de programa y fuente",
                     color_discrete_sequence=COLOR_FUENTES, labels={"tipo_programa": ""})
        fig.update_layout(legend=dict(orientation="h", y=-0.3, title="", font_size=9))
        barca_layout(fig, 360)
        st.plotly_chart(fig, use_container_width=True)

    # ── Top campañas ───────────────────────────────────────────────────────────
    st.markdown("### 🏷️ Top campañas")
    camp = (d[d[camp_col] != "Sin campaña"].groupby(camp_col)
            .size().reset_index(name="Leads")
            .sort_values("Leads", ascending=True).tail(20))
    if camp.empty:
        st.info("Sin campañas identificadas para los filtros actuales.")
    else:
        fig = px.bar(camp, x="Leads", y=camp_col, orientation="h", text_auto=True,
                     title=f"Top 20 campañas ({origen.lower()})",
                     color="Leads",
                     color_continuous_scale=[BARCA["bone"], BARCA["gold"], BARCA["garnet"]],
                     labels={camp_col: ""})
        fig.update_layout(coloraxis_showscale=False,
                          yaxis=dict(categoryorder="total ascending"))
        barca_layout(fig, max(320, len(camp) * 32))
        st.plotly_chart(fig, use_container_width=True)

    # Negocios de Cierre Ganado del período (por fecha de cierre) y campaña a usar
    _camp_deal_col = "camp_original" if origen == "Original" else "camp_reciente"
    _gan_won = pd.DataFrame()
    if (df_deals_periodo is not None and not df_deals_periodo.empty
            and "etapa" in df_deals_periodo.columns and _camp_deal_col in df_deals_periodo.columns):
        _gan_won = df_deals_periodo[df_deals_periodo["etapa"] == "Cierre ganado"].drop_duplicates("deal_id")

    def _asigna_negocios(tbl):
        """Asigna "Ventas NEGOCIO" por [Programa(pgm), Campaña] sin duplicar:
        el recuento de cada campaña se coloca en su fila con más Leads. Así el total
        coincide en todas las tablas (mismo criterio pgm+campaña)."""
        tbl = tbl.copy()
        tbl["Neg. Ganados"] = 0
        if _gan_won.empty:
            return tbl
        won = _gan_won.groupby(["pgm", _camp_deal_col])["deal_id"].nunique()
        for (prog, camp), cnt in won.items():
            mask = (tbl["Programa"] == prog) & (tbl["Campaña"] == camp)
            if mask.any():
                idx = tbl.loc[mask, "Leads"].idxmax()
                tbl.at[idx, "Neg. Ganados"] = int(cnt)
        return tbl

    def _con_total(tbl, cols_num, cols_txt):
        """Añade una fila TOTAL al final; los % se recalculan sobre los totales."""
        if tbl.empty:
            return tbl
        tot = {c: "" for c in cols_txt}
        tot[cols_txt[0]] = "TOTAL"
        for c in cols_num:
            tot[c] = int(tbl[c].sum())
        tot["% Activado"] = round(tot["Activados"] / tot["Leads"] * 100, 1) if tot.get("Leads") else 0.0
        if "% Venta" in tbl.columns:
            tot["% Venta"] = round(tot["Ganados"] / tot["Leads"] * 100, 1) if tot.get("Leads") else 0.0
        return pd.concat([tbl, pd.DataFrame([tot])], ignore_index=True)

    # ── Tabla: Programa × Campaña ──────────────────────────────────────────────
    st.markdown("### 📋 Leads por programa y campaña")
    piv = (d.groupby(["pgm", "tipo_programa", fuente_col, camp_col])
           .agg(Leads=("email", "count"),
                Activados=("lead_activado", lambda s: int((s == "Activado").sum())),
                Ganados=("lead_status", lambda s: int((s == "Negocio ganado").sum())))
           .reset_index())
    piv["% Activado"] = (piv["Activados"] / piv["Leads"] * 100).round(1)
    piv["% Venta"]    = (piv["Ganados"] / piv["Leads"] * 100).round(1)
    piv = piv.rename(columns={"pgm": "Programa", "tipo_programa": "Tipo",
                              fuente_col: "Fuente", camp_col: "Campaña"})
    piv = _asigna_negocios(piv)
    piv = piv.sort_values("Leads", ascending=False)
    piv = _con_total(piv, ["Leads", "Activados", "Ganados", "Neg. Ganados"],
                     ["Programa", "Tipo", "Fuente", "Campaña"])
    st.dataframe(
        piv[["Programa", "Tipo", "Fuente", "Campaña", "Leads", "Activados", "% Activado",
             "Ganados", "% Venta", "Neg. Ganados"]],
        use_container_width=True, hide_index=True,
        column_config={
            "Campaña":       st.column_config.TextColumn(width="large"),
            "% Activado":    st.column_config.NumberColumn(format="%.1f%%", width="small"),
            "% Venta":       st.column_config.NumberColumn(format="%.1f%%", width="small"),
            "Ganados":       st.column_config.NumberColumn("Leads en 'Negocio ganado'", width="small"),
            "Neg. Ganados":  st.column_config.NumberColumn("Ventas NEGOCIO", width="small"),
        },
    )
    st.markdown(
        f"<div style='font-size:12px;color:{BARCA['ink40']};margin-top:6px;line-height:1.5'>"
        f"ℹ️ <b>Nota:</b> hay dos formas de contar venta por campaña:<br>"
        f"• <b>Ganados</b> (+ % Venta): <b>leads del período</b> (por fecha de creación) "
        f"que hoy tienen <code>lt_lead_status</code> = <b>'Negocio ganado'</b>, atribuidos a la "
        f"campaña que los captó.<br>"
        f"• <b>Ventas NEGOCIO</b>: negocios de <b>Cierre Ganado</b> de la campaña por "
        f"<b>fecha de cierre</b> del negocio (no importa cuándo se creó el lead) — misma base que el "
        f"KPI del Dashboard general.<br>"
        f"Ambas son útiles: la primera mide captación de campañas del período; la segunda, cierres "
        f"ocurridos en el período. Por eso pueden diferir.</div>",
        unsafe_allow_html=True,
    )

    # ── Tabla filtrable por Fuente y Región ────────────────────────────────────
    st.markdown("### 🌍 Leads por Fuente y Región")
    st.caption("Filtra por fuente de tráfico y por región (mercado) para ver el desglose por programa y campaña.")
    r1, r2 = st.columns(2)
    with r1:
        _f_opts = ["Todas"] + sorted(d[fuente_col].dropna().unique())
        _sanea_estado("la_tbl_fuente", _f_opts)
        _f_sel = st.selectbox("Fuente de tráfico", _f_opts, key="la_tbl_fuente")
    with r2:
        _r_opts = ["Todas"] + sorted(d["mercado"].dropna().unique())
        _sanea_estado("la_tbl_region", _r_opts)
        _r_sel = st.selectbox("Región (mercado)", _r_opts, key="la_tbl_region")

    _dr = d.copy()
    if _f_sel != "Todas": _dr = _dr[_dr[fuente_col] == _f_sel]
    if _r_sel != "Todas": _dr = _dr[_dr["mercado"] == _r_sel]

    if _dr.empty:
        st.info("No hay leads con esa combinación de fuente y región.")
    else:
        _tbl = (_dr.groupby(["mercado", fuente_col, "tipo_programa", "pgm", camp_col, "pais"])
                .agg(Leads=("email", "count"),
                     Activados=("lead_activado", lambda s: int((s == "Activado").sum())),
                     Ganados=("lead_status", lambda s: int((s == "Negocio ganado").sum())))
                .reset_index())
        _tbl["% Activado"] = (_tbl["Activados"] / _tbl["Leads"] * 100).round(1)
        _tbl = (_tbl.rename(columns={"mercado": "Región", fuente_col: "Fuente",
                                     "tipo_programa": "Tipo", "pgm": "Programa",
                                     camp_col: "Campaña", "pais": "País"}))
        # Mismo criterio de negocio que la tabla de campañas (por pgm+campaña) → totales cuadran
        _tbl = _asigna_negocios(_tbl)
        _tbl = _tbl.sort_values("Leads", ascending=False)
        _tbl = _con_total(_tbl, ["Leads", "Activados", "Ganados", "Neg. Ganados"],
                          ["Región", "Fuente", "Tipo", "Programa", "Campaña", "País"])
        st.dataframe(
            _tbl[["Región", "Fuente", "Tipo", "Programa", "Campaña", "País", "Leads",
                  "Activados", "% Activado", "Ganados", "Neg. Ganados"]],
            use_container_width=True, hide_index=True, height=440,
            column_config={
                "Campaña":       st.column_config.TextColumn(width="large"),
                "% Activado":    st.column_config.NumberColumn(format="%.1f%%", width="small"),
                "Neg. Ganados":  st.column_config.NumberColumn("Ventas NEGOCIO", width="small"),
            },
        )
        st.download_button(
            "⬇️ Descargar CSV (fuente × región)",
            data=_tbl.to_csv(index=False, encoding="utf-8-sig"),
            file_name=f"leads_fuente_region_{fi}_{ff}.csv",
            mime="text/csv", key="dl_leads_fuente_region",
        )

    # ── Detalle por lead ───────────────────────────────────────────────────────
    st.markdown("### 🔎 Detalle por lead")
    cols = ["fecha", "pgm", "tipo_programa", "pais",
            "fuente_original", "camp_original", "orig_d1", "orig_d2",
            "fuente_reciente", "camp_reciente", "rec_d1", "rec_d2", "fecha_fuente_reciente",
            "record_source", "record_d1", "record_d2", "record_d3",
            "lead_status", "lead_activado", "email"]
    cols = [c for c in cols if c in d.columns]
    rename = {
        "fecha": "Fecha creación", "pgm": "Programa (pgm)", "tipo_programa": "Tipo",
        "pais": "País",
        "fuente_original": "Fuente original", "camp_original": "Campaña (original)",
        "orig_d1": "Detalle 1 (orig)", "orig_d2": "Detalle 2 (orig)",
        "fuente_reciente": "Fuente reciente", "camp_reciente": "Campaña (reciente)",
        "rec_d1": "Detalle 1 (rec)", "rec_d2": "Detalle 2 (rec)",
        "fecha_fuente_reciente": "Fecha fuente reciente",
        "record_source": "Fuente del registro",
        "record_d1": "Detalle registro 1", "record_d2": "Detalle registro 2",
        "record_d3": "Detalle registro 3",
        "lead_status": "Estado", "lead_activado": "Actividad", "email": "Email",
    }
    det = d[cols].rename(columns=rename).sort_values("Fecha creación", ascending=False)
    st.dataframe(det, use_container_width=True, hide_index=True, height=460)
    st.download_button(
        "⬇️ Descargar CSV (detalle de leads)",
        data=det.to_csv(index=False, encoding="utf-8-sig"),
        file_name=f"analisis_leads_{fi}_{ff}.csv",
        mime="text/csv", key="dl_leads_analisis",
    )


def _render_conversion_page(df, df_ganados_prog, fi, ff):
    """Página de Conversión por Programa."""
    st.markdown("## 🎓 Conversión por Programa")

    # Filtros locales: mercado y país
    _col_m, _col_p = st.columns([1, 2])
    with _col_m:
        _mercado_sel = st.radio(
            "Mercado", ["Todos", "España", "Latam", "Europa", "Middle East", "África", "Norte América", "Asia", "Oceanía", "Otro"],
            horizontal=True, index=0, key="prog_mercado"
        )
    with _col_p:
        _paises_prog = sorted(
            [p for p in df["pais"].dropna().unique() if p not in ("Sin datos", "")]
        )
        _sanea_estado("prog_pais", _paises_prog, multi=True)
        _paises_prog_sel = st.multiselect("Filtrar por país", _paises_prog, key="prog_pais")

    # Dataset de leads por programa — recalcula mercado siempre desde pais
    df_leads_prog = df.copy()
    if not df_leads_prog.empty:
        df_leads_prog["mercado"] = df_leads_prog["pais"].apply(resolve_mercado)

    df_ganados_prog_f = df_ganados_prog.copy()
    if not df_ganados_prog_f.empty:
        df_ganados_prog_f["mercado"] = df_ganados_prog_f["pais"].apply(resolve_mercado)

    if _mercado_sel != "Todos":
        df_leads_prog     = df_leads_prog[df_leads_prog["mercado"] == _mercado_sel]
        df_ganados_prog_f = df_ganados_prog_f[df_ganados_prog_f["mercado"] == _mercado_sel]

    if _paises_prog_sel:
        df_leads_prog     = df_leads_prog[df_leads_prog["pais"].isin(_paises_prog_sel)]
        df_ganados_prog_f = df_ganados_prog_f[df_ganados_prog_f["pais"].isin(_paises_prog_sel)]

    # Etiqueta de programa AGRUPADA por código pgm base (unifica idiomas/nombres
    # del mismo programa). Nombre representativo = el más frecuente entre leads.
    _pgm_name_map = {}
    if not df_leads_prog.empty and "pgm" in df_leads_prog.columns:
        _t = df_leads_prog.copy()
        _t["_b"] = _t["pgm"].apply(pgm_base)
        for _b, _g in _t.groupby("_b"):
            _n = _g["programa"][_g["programa"] != "Sin programa"].mode()
            _pgm_name_map[_b] = _n.iloc[0] if not _n.empty else _b

    def _prog_label(pgm):
        b = pgm_base(pgm)
        if not b:
            return "Sin pgm"
        nom = _pgm_name_map.get(b)
        return f"{b} · {nom}" if nom and nom != b else b

    if not df_leads_prog.empty and "pgm" in df_leads_prog.columns:
        df_leads_prog["prog_pgm"] = df_leads_prog["pgm"].apply(_prog_label)
    if not df_ganados_prog_f.empty and "pgm" in df_ganados_prog_f.columns:
        df_ganados_prog_f["prog_pgm"] = df_ganados_prog_f["pgm"].apply(_prog_label)

    _tab1, _tab2, _tab3, _tab4 = st.tabs(["📊 Tabla de conversión", "🌍 Por mercado y país", "📡 Por fuente", "🗺️ Programa × País"])

    # ── Tab 1: Tabla principal de conversión ─────────────────────────────────
    with _tab1:
        st.caption("Programas agrupados por **código pgm** (unifica variantes de nombre e idioma).")
        leads_by_prog = (
            df_leads_prog.groupby("prog_pgm").size()
            .reset_index(name="Leads")
            .sort_values("Leads", ascending=False)
        ) if not df_leads_prog.empty and "prog_pgm" in df_leads_prog.columns else pd.DataFrame(columns=["prog_pgm", "Leads"])

        if not df_ganados_prog_f.empty and "prog_pgm" in df_ganados_prog_f.columns:
            mat_by_prog = (
                df_ganados_prog_f.groupby("prog_pgm").size()
                .reset_index(name="Ventas")
            )
        else:
            mat_by_prog = pd.DataFrame(columns=["prog_pgm", "Ventas"])

        conv_table = leads_by_prog.merge(mat_by_prog, on="prog_pgm", how="left").fillna(0)
        conv_table["Ventas"] = conv_table["Ventas"].astype(int)
        conv_table["Tasa (%)"] = (
            conv_table["Ventas"] / conv_table["Leads"] * 100
        ).round(1).where(conv_table["Leads"] > 0, 0)
        conv_table = conv_table.rename(columns={"prog_pgm": "Programa"})

        if conv_table.empty:
            st.info("No hay datos de programa en el período seleccionado.")
        else:
            n_leads_tot  = conv_table["Leads"].sum()
            n_mat_prog   = conv_table["Ventas"].sum()
            tasa_global  = round(n_mat_prog / n_leads_tot * 100, 1) if n_leads_tot else 0.0

            m1, m2, m3 = st.columns(3)
            kpi_card(m1, "Leads con programa",  int(n_leads_tot),  BARCA["blue"])
            kpi_card(m2, "Ventas",         int(n_mat_prog),   BARCA["gold"])
            kpi_card(m3, "Tasa de conversión",   f"{tasa_global}%", BARCA["garnet"])
            st.markdown("<br>", unsafe_allow_html=True)

            # Gráfico arriba y tabla debajo (a ancho completo) para que se lea bien
            fig_top = conv_table.head(15).copy()
            fig_c = px.bar(
                fig_top, x="Leads", y="Programa", orientation="h",
                title="Top programas por Leads",
                color="Tasa (%)",
                color_continuous_scale=[BARCA["blue"], BARCA["gold"], BARCA["garnet"]],
                text="Leads",
            )
            fig_c.update_layout(yaxis=dict(categoryorder="total ascending"))
            barca_layout(fig_c, max(480, len(fig_top) * 34 + 120))
            st.plotly_chart(fig_c, use_container_width=True)

            st.markdown("##### 📋 Detalle por programa")
            st.dataframe(
                conv_table.style
                    .background_gradient(subset=["Leads"],       cmap="Blues")
                    .background_gradient(subset=["Ventas"], cmap="Greens")
                    .background_gradient(subset=["Tasa (%)"],     cmap="YlOrRd", vmin=0, vmax=30)
                    .format({"Tasa (%)": "{:.1f}%"}),
                use_container_width=True,
                hide_index=True,
                height=min(700, len(conv_table) * 36 + 40),
            )

    # ── Tab 2: Por mercado y país ─────────────────────────────────────────────
    with _tab2:
        if conv_table.empty:
            st.info("Sin datos.")
        else:
            # Por mercado
            st.markdown("#### Por mercado")
            leads_m = (
                df_leads_prog[df_leads_prog["programa"] != "Sin programa"]
                .groupby("mercado").size().reset_index(name="Leads")
            ) if not df_leads_prog.empty else pd.DataFrame(columns=["mercado", "Leads"])

            if not df_ganados_prog_f.empty:
                mat_m = (
                    df_ganados_prog_f[df_ganados_prog_f["programa"] != "Sin programa"]
                    .groupby("mercado").size().reset_index(name="Ventas")
                )
            else:
                mat_m = pd.DataFrame(columns=["mercado", "Ventas"])

            merc_table = leads_m.merge(mat_m, on="mercado", how="outer").fillna(0)
            merc_table["Ventas"] = merc_table["Ventas"].astype(int)
            merc_table["Leads"]        = merc_table["Leads"].astype(int)
            merc_table["Tasa (%)"] = (
                merc_table["Ventas"] / merc_table["Leads"] * 100
            ).round(1).where(merc_table["Leads"] > 0, 0)
            merc_table = merc_table.rename(columns={"mercado": "Mercado"})

            col_a, col_b = st.columns(2)
            with col_a:
                st.dataframe(
                    merc_table.style
                        .background_gradient(subset=["Leads"],       cmap="Blues")
                        .background_gradient(subset=["Ventas"], cmap="Greens")
                        .format({"Tasa (%)": "{:.1f}%"}),
                    use_container_width=True, hide_index=True,
                )
            with col_b:
                fig_m = px.bar(
                    merc_table, x="Mercado", y=["Leads", "Ventas"],
                    barmode="group", title="Leads vs Ventas por mercado",
                    color_discrete_map={"Leads": BARCA["blue"], "Ventas": BARCA["gold"]},
                )
                barca_layout(fig_m, 300)
                st.plotly_chart(fig_m, use_container_width=True)

            # Top países con conversión
            st.markdown("#### Por país (top 20)")
            leads_p = (
                df_leads_prog[df_leads_prog["programa"] != "Sin programa"]
                .groupby("pais").size().reset_index(name="Leads")
            ) if not df_leads_prog.empty else pd.DataFrame(columns=["pais", "Leads"])

            if not df_ganados_prog_f.empty:
                mat_p = (
                    df_ganados_prog_f[df_ganados_prog_f["programa"] != "Sin programa"]
                    .groupby("pais").size().reset_index(name="Ventas")
                )
            else:
                mat_p = pd.DataFrame(columns=["pais", "Ventas"])

            pais_table = leads_p.merge(mat_p, on="pais", how="left").fillna(0)
            pais_table["Ventas"] = pais_table["Ventas"].astype(int)
            pais_table["Tasa (%)"] = (
                pais_table["Ventas"] / pais_table["Leads"] * 100
            ).round(1).where(pais_table["Leads"] > 0, 0)
            pais_table = pais_table.sort_values("Leads", ascending=False).head(50)
            pais_table = pais_table.rename(columns={"pais": "País"})

            st.dataframe(
                pais_table.style
                    .background_gradient(subset=["Leads"],       cmap="Blues")
                    .background_gradient(subset=["Ventas"], cmap="Greens")
                    .background_gradient(subset=["Tasa (%)"],     cmap="YlOrRd", vmin=0, vmax=30)
                    .format({"Tasa (%)": "{:.1f}%"}),
                use_container_width=True, hide_index=True,
                height=min(1900, len(pais_table) * 36 + 40),
            )

    # ── Tab 3: Por fuente ──────────────────────────────────────────────────────
    with _tab3:
        if conv_table.empty:
            st.info("Sin datos.")
        else:
            leads_f = (
                df_leads_prog[df_leads_prog["programa"] != "Sin programa"]
                .groupby("fuente").size().reset_index(name="Leads")
            ) if not df_leads_prog.empty else pd.DataFrame(columns=["fuente", "Leads"])

            if not df_ganados_prog_f.empty:
                mat_f = (
                    df_ganados_prog_f[df_ganados_prog_f["programa"] != "Sin programa"]
                    .groupby("fuente").size().reset_index(name="Ventas")
                )
            else:
                mat_f = pd.DataFrame(columns=["fuente", "Ventas"])

            fuente_table = leads_f.merge(mat_f, on="fuente", how="left").fillna(0)
            fuente_table["Ventas"] = fuente_table["Ventas"].astype(int)
            fuente_table["Tasa (%)"] = (
                fuente_table["Ventas"] / fuente_table["Leads"] * 100
            ).round(1).where(fuente_table["Leads"] > 0, 0)
            fuente_table = fuente_table.sort_values("Leads", ascending=False)
            fuente_table = fuente_table.rename(columns={"fuente": "Fuente"})

            col_g2, col_t2 = st.columns([3, 2])
            with col_g2:
                fig_f = px.bar(
                    fuente_table, x="Fuente", y=["Leads", "Ventas"],
                    barmode="group", title="Leads vs Ventas por fuente",
                    color_discrete_map={"Leads": BARCA["blue"], "Ventas": BARCA["gold"]},
                    text_auto=True,
                )
                barca_layout(fig_f, 380)
                st.plotly_chart(fig_f, use_container_width=True)

            with col_t2:
                st.dataframe(
                    fuente_table.style
                        .background_gradient(subset=["Leads"],       cmap="Blues")
                        .background_gradient(subset=["Ventas"], cmap="Greens")
                        .background_gradient(subset=["Tasa (%)"],     cmap="YlOrRd", vmin=0, vmax=30)
                        .format({"Tasa (%)": "{:.1f}%"}),
                    use_container_width=True, hide_index=True,
                )

            # Programa × Fuente pivot (agrupado por pgm)
            st.markdown("#### Programas × Fuente de tráfico")
            if not df_leads_prog.empty and "prog_pgm" in df_leads_prog.columns:
                pivot_pf = (
                    df_leads_prog
                    .groupby(["prog_pgm", "fuente"]).size()
                    .unstack(fill_value=0)
                )
                pivot_pf.columns.name = None
                pivot_pf.index.name = "Programa (pgm)"
                pivot_pf = pivot_pf.loc[pivot_pf.sum(axis=1).sort_values(ascending=False).index].head(50)
                st.dataframe(
                    pivot_pf.style.background_gradient(cmap="Blues"),
                    use_container_width=True,
                )

    # ── Tab 4: Por programa y país ─────────────────────────────────────────────
    with _tab4:
         st.markdown("#### Conversión por Programa y País")
         st.caption("Agrupado por **código de programa (pgm)**: unifica las variantes de nombre e idioma "
                    "(p. ej. PG_003_EN y PG_003_ES) del mismo programa.")

         # Usa la etiqueta agrupada por pgm (prog_pgm) calculada arriba
         _lg = df_leads_prog if ("prog_pgm" in df_leads_prog.columns) else pd.DataFrame(columns=["prog_pgm", "pais"])
         _mg = df_ganados_prog_f if ("prog_pgm" in df_ganados_prog_f.columns) else pd.DataFrame(columns=["prog_pgm", "pais"])

         _prog_pais_leads = (_lg.groupby(["prog_pgm", "pais"]).size().reset_index(name="Leads")
                             .rename(columns={"prog_pgm": "Programa"})
                             if not _lg.empty else pd.DataFrame(columns=["Programa", "pais", "Leads"]))
         _prog_pais_mat = (_mg.groupby(["prog_pgm", "pais"]).size().reset_index(name="Ventas")
                           .rename(columns={"prog_pgm": "Programa"})
                           if not _mg.empty else pd.DataFrame(columns=["Programa", "pais", "Ventas"]))

         prog_pais = _prog_pais_leads.merge(_prog_pais_mat, on=["Programa", "pais"], how="left").fillna(0)
         prog_pais["Ventas"] = prog_pais["Ventas"].astype(int)
         prog_pais["Tasa (%)"] = (
             prog_pais["Ventas"] / prog_pais["Leads"] * 100
         ).round(1).where(prog_pais["Leads"] > 0, 0)
         prog_pais = prog_pais.sort_values(["Leads", "Ventas"], ascending=False)
         prog_pais = prog_pais.rename(columns={"pais": "País"})

         if prog_pais.empty:
             st.info("Sin datos para el período y filtros seleccionados.")
         else:
             # Filtro de programa dentro del tab
             _progs_disponibles = sorted(prog_pais["Programa"].unique().tolist())
             _sanea_estado("tab4_prog_filter", _progs_disponibles, multi=True)
             _prog_sel = st.multiselect(
                 "Filtrar por programa (pgm)", _progs_disponibles,
                 key="tab4_prog_filter",
                 placeholder="Todos los programas",
             )
             if _prog_sel:
                 prog_pais = prog_pais[prog_pais["Programa"].isin(_prog_sel)]

             st.dataframe(
                 prog_pais.style
                     .background_gradient(subset=["Leads"],        cmap="Blues")
                     .background_gradient(subset=["Ventas"],  cmap="Greens")
                     .background_gradient(subset=["Tasa (%)"],      cmap="YlOrRd", vmin=0, vmax=30)
                     .format({"Tasa (%)": "{:.1f}%"}),
                 use_container_width=True,
                 hide_index=True,
                 height=min(600, len(prog_pais) * 36 + 40),
             )

             # Pivot: Programa (filas) × País (columnas) — tasa de conversión
             st.markdown("#### Pivot Programa × País (tasa de conversión %)")
             if len(prog_pais) > 0:
                 _src_leads = (
                     _prog_pais_leads if not _prog_sel
                     else _prog_pais_leads[_prog_pais_leads["Programa"].isin(_prog_sel)]
                 )
                 _src_mat = (
                     _prog_pais_mat if not _prog_sel
                     else _prog_pais_mat[_prog_pais_mat["Programa"].isin(_prog_sel)]
                 ) if not _prog_pais_mat.empty else pd.DataFrame(columns=["Programa", "pais", "Ventas"])

                 pivot_leads = _src_leads.pivot_table(
                     index="Programa", columns="pais", values="Leads", fill_value=0
                 )
                 pivot_mat = _src_mat.pivot_table(
                     index="Programa", columns="pais", values="Ventas", fill_value=0
                 ) if not _src_mat.empty else pd.DataFrame()

                 pivot_leads.columns.name = None
                 # Ordenar programas por total de leads
                 pivot_leads = pivot_leads.loc[
                     pivot_leads.sum(axis=1).sort_values(ascending=False).index
                 ].head(50)

                 if not pivot_mat.empty:
                     pivot_mat.columns.name = None
                     pivot_mat = pivot_mat.reindex(
                         index=pivot_leads.index, columns=pivot_leads.columns, fill_value=0
                     )
                     pivot_conv = (pivot_mat / pivot_leads.replace(0, float("nan")) * 100).round(1).fillna(0)
                 else:
                     pivot_conv = pivot_leads * 0.0

                 st.dataframe(
                     pivot_conv.style
                         .background_gradient(cmap="YlOrRd", vmin=0, vmax=30)
                         .format("{:.1f}%"),
                     use_container_width=True,
                 )

    st.markdown(
        f"<br><div style='text-align:center;color:{BARCA['ink40']};font-size:12px'>"
        f"{ACCOUNT_NAME} · Contactos Low Ticket por programa (pgm) · Datos actualizados automáticamente cada 5 min</div>",
        unsafe_allow_html=True
    )


if __name__ == "__main__":
    main()
