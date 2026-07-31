# Dashboard Low Ticket — BiHub

Dashboard de análisis de leads y conversión (Streamlit) conectado al CRM de HubSpot de BiHub,
para la línea **Low Ticket** (certificados y cursos online).
Fichero principal: **`dashboard_lt.py`**. Repo: `WeRise-ESP/LT_Bihub` (rama `main`).
App en producción: **https://bi-lt-dashboard.streamlit.app** (⚠️ el subdominio no coincide
con el nombre del repo). Actualizar la app = `git push` a `main`; Streamlit Cloud redespliega solo.

Los contactos se filtran por la propiedad `pgm` (prefijos `P_`, `CE_`, `C_`), el estado del
lead sale de `lt_lead_status` y las fechas se interpretan en zona horaria **Europe/Madrid**,
igual que en HubSpot. Es el mismo portal (**143790203**) que el dashboard de High Ticket, así
que se reutiliza el mismo token.

---

## 🚀 Puesta en marcha (primera vez)

> **Requisito importante:** usar **Python 3.12** (con 3.13/3.14 la app falla en Streamlit Cloud).

**1. Clonar el repositorio** (necesitas acceso de colaborador en GitHub):
```bash
git clone https://github.com/WeRise-ESP/LT_Bihub.git
cd LT_Bihub
```

**2. Crear el entorno virtual e instalar dependencias:**
```bash
python3.12 -m venv venv
./venv/bin/pip install -r requirements.txt
```

**3. Crear el archivo `.env`** en la raíz del proyecto con el token de HubSpot
(te lo pasa el responsable del proyecto — **NO está en GitHub**):
```
HUBSPOT_TOKEN=pat-eu1-XXXXXXXX
```

**4. Ejecutar el dashboard en local:**
```bash
./venv/bin/streamlit run dashboard_lt.py
```
Se abre en `http://localhost:8501`.

---

## 📝 Qué está y qué no en GitHub

Al clonar tienes **todo el código**. Lo único que hay que conseguir aparte:

| Elemento | ¿En GitHub? | Cómo obtenerlo |
|---|---|---|
| Código (`dashboard_lt.py`, `requirements.txt`, …) | ✅ Sí | Viene al clonar |
| **`.env`** (token de HubSpot) | ❌ No (gitignored) | Te lo pasa el responsable; creas el archivo |
| **`venv/`** (entorno) | ❌ No | Lo creas tú con `pip install` (paso 2) |
| **`exports/`** (Excel de los informes) | ❌ No | Se generan al ejecutar los `informe_lt*.py` |

---

## 🔄 Publicar cambios (deploy)

La app está desplegada en **Streamlit Cloud** y **se actualiza sola** al hacer *push* a `main`.
No hay que hacer nada más para "publicar":

```bash
git pull origin main          # 1) antes de trabajar: trae cambios de tu compañera
# ... editas / pruebas en local ...
git add -A
git commit -m "descripción del cambio"
git push origin main          # 2) publica → Streamlit Cloud redespliega (~1-3 min)
```

> Al ser varias personas sobre el mismo repo, **haz `git pull` antes de empezar** y `git push`
> al terminar, para no pisaros los cambios.

---

## 🧭 Estructura de la app

Cinco páginas (selector "📄 Página" en el panel lateral):
- **📊 Dashboard general** — KPIs, embudo Low Ticket y negocios de venta.
- **💶 Ventas y Facturación** — resumen ejecutivo (ventas, facturación, ticket medio
  y % de facturación por tipo de curso), matrículas y facturación por origen y por
  país, cruce origen × país × tipo, y ranking de programas.
- **📥 Contactos y Canales** — la misma estructura pero de captación: contactos y
  tasa de activación por **canal de entrada** (Facebook Lead Ads, formulario web,
  landing, banner, chatbot…), por país, cruce canal × país × tipo y ranking de
  programas por contactos captados.
- **🎓 Conversión por Programa** — conversión agrupada por código `pgm`.
- **🧲 Análisis de Leads** — origen, fuente y campaña por programa.

### Canal de entrada vs. origen de tráfico

Son dos cosas distintas y conviene no confundirlas:

- **Canal de entrada** = por dónde rellenó el formulario (Lead Ads, web, landing,
  banner, chatbot). Se deduce del nombre del formulario, porque en HubSpot no hay
  una propiedad curada de canal.
- **Origen de tráfico** = de dónde venía (búsqueda de pago, orgánica, redes,
  **Referencias de la IA**…). Ahí es donde se ven los leads que llegan desde
  ChatGPT y similares: **la IA es un origen, no un canal**.

---

## 📐 De dónde salen los números

| Métrica | Fuente |
|---|---|
| **Leads nuevos** | Contactos con `pgm` = `P_*` / `CE_*` / `C_*`, por `createdate` |
| **Estado del lead** | `lt_lead_status` (Nuevo → Primera respuesta → Conversación iniciada → Negocio abierto → Negocio ganado) |
| **Activado / Sin actividad** | ¿El lead superó el estado "Nuevo"? |
| **Ventas** | Negocios en **Cierre ganado**, por `closedate` |
| **Negocios perdidos** | Negocios en etapas de pérdida, por `closedate` |
| **Facturación** | `amount` del negocio |
| **Tipo de curso** | Código del producto del **negocio** (`codigo_del_producto`) y, si no, el nombre del producto |

### Tipos de curso

| Prefijo | Producto | Ejemplo real |
|---|---|---|
| `CE_` | **Certificado** | *Certificate in Sports Cardiology* |
| `P_` | **Diploma** | *Professional Diploma in Digital Marketing…* |
| `C_` | **Curso** | *Course of Assessment Methods…* |
| `EP_` `PG_` `M_` | **High Ticket** | Se venden también por este canal, pero **no cuentan** en este dashboard |

> 🚫 **High Ticket no entra.** Los másters, postgrados y programas ejecutivos se
> excluyen de todas las cifras de venta, aunque se compren por el mismo canal de
> WooCommerce. El filtro está en la capa de datos (constante `EXCLUIR_HIGH_TICKET`),
> así que todas las páginas cuadran entre sí.

### ⚠️ Las ventas vienen de dos pipelines

La operativa migró de **"Pipeline de ventas"** (histórico) a **"WooCommerce Orders"** (actual).
El dashboard aplica un **corte duro** el **1 de mayo de 2026** (`FECHA_CORTE_WOO`): los cierres
anteriores se leen del pipeline histórico y los posteriores de WooCommerce. Sin ese corte se
contarían dos veces los pedidos del solape.

### Cómo se sabe qué se ha vendido

El `pgm` del **contacto** solo está relleno en ~40 % de los pedidos, así que el producto
se identifica desde el **negocio**: primero `codigo_del_producto` (99 % relleno en
WooCommerce) y, si no, el nombre del producto de los *line items* o del propio negocio.
Con esta cadena la atribución por programa está en el **91 %**.

Queda un resto sin identificar (~9 %): son productos que no siguen la nomenclatura
`pgm` (Barça Coach Academy, Coaches Academy, Football Scouting, gift cards…). Aparecen
agrupados como **"Otros"**.

---

## 📄 Informes en Excel

Además de la app hay tres scripts que exportan Excel a `exports/`:

```bash
pip install -r requirements.txt -r requirements-cli.txt
python informe_lt.py                 # países, estados, calidad y fuentes
python informe_lt_fuente.py          # estado de lead × fuente de tráfico
python informe_lt_lead_status.py     # estado de lead × país
```

Comparan **dos meses**, definidos en la constante `PERIODOS` de cada script
(por defecto junio y julio de 2026). Edítala para sacar otro par de meses.

---

## 🔐 Seguridad

- El **token de HubSpot** da acceso al CRM. Compártelo solo por canal seguro y nunca lo subas a GitHub.
- En **Streamlit Cloud** el token está en *Settings → Secrets* (`HUBSPOT_TOKEN`).
- Si hay que revocarlo: se regenera en HubSpot y se actualiza en el `.env` de cada persona
  y en los Secrets de Streamlit Cloud. Ojo: **el token es compartido con el dashboard de
  High Ticket**, así que hay que actualizarlo en los dos sitios.
