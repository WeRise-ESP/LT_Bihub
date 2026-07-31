# Dashboard CRM Low Ticket — BiHub

Contexto para trabajar en este proyecto. Léelo antes de tocar código.

## Qué es
Dashboard **Streamlit** de análisis de leads y conversión sobre el CRM de HubSpot
de **BiHub** (FC Barcelona), para la línea **Low Ticket** (certificados y cursos
online). Es el hermano del dashboard **RST / High Ticket**.

- **Repo:** `WeRise-ESP/LT_Bihub` (rama `main`)
- **App:** https://bi-lt-dashboard.streamlit.app  ⚠️ el subdominio
  (`bi-lt-dashboard`) NO coincide con el nombre del repo (`LT_Bihub`).
  Importante si hay que recrear la app.
- **Entry point / main file:** `dashboard_lt.py`
- **Actualizar = `git push` a `main`** → Streamlit Cloud redespliega solo.
- **Portal de HubSpot: 143790203** — el MISMO que High Ticket, así que se usa el
  mismo `HUBSPOT_TOKEN`.

## Arrancar en local
```bash
python3.12 -m venv venv && ./venv/bin/pip install -r requirements.txt
./venv/bin/streamlit run dashboard_lt.py
```
Necesitas `.streamlit/secrets.toml` con el token de HubSpot (NO está en git —
pídelo por el gestor de contraseñas del equipo).

## Reglas de negocio
- Los contactos se filtran por la propiedad **`pgm`** (prefijos `P_`, `CE_`, `C_`).
  Los prefijos de High Ticket (`EP_`, `PG_`, `M_`) NO entran aquí como leads,
  pero sí aparecen en algunos pedidos de WooCommerce (ver más abajo).
- **Qué es cada prefijo** (verificado contra los nombres reales de los productos
  en los line items — no te fíes de la intuición):

  | Prefijo | Producto | Ejemplo |
  |---|---|---|
  | `CE_` | **Certificado** | `CE_0009_EN` → *Certificate in Sports Cardiology* |
  | `P_` | **Diploma** | `P_0007_EN` → *Professional Diploma in Digital Marketing…* |
  | `C_` | **Curso** | `C_0167_EN` → *Course of Assessment Methods…* |

  ⚠️ `P_` es **Diploma**, no "Programa". Estuvo mal etiquetado en la primera
  versión del dashboard.
- El estado del lead sale de **`lt_lead_status`**, no de `hs_lead_status`. Su
  embudo es: Nuevo → Primera respuesta automatizada → Conversación iniciada →
  Negocio abierto → Negocio ganado. **No tiene estados de descarte**, así que la
  clasificación "Válido / No válido" de High Ticket NO aplica: aquí el eje
  equivalente es **Activado / Sin actividad** (¿el lead salió de "Nuevo"?).
- Las fechas se interpretan en zona horaria **Europe/Madrid** (igual que HubSpot).
- ⚠️ **Streamlit pinado a 1.57.0** en requirements — 1.58.0 tiene un bug en el
  DownloadButton. No subir la versión sin verificar.

## ⚠️ Las ventas vienen de DOS pipelines
La operativa de venta migró de **"Pipeline de ventas"** (id `default`, el
histórico) a **"WooCommerce Orders"** (id `3708462309`, el actual):

| | Pipeline de ventas | WooCommerce Orders |
|---|---|---|
| Último cierre | abril 2026 | — |
| Arranque real | — | mayo 2026 |
| Ganado | `closedwon` | `5146661068` (Completed) |
| Perdido | `closedlost` | Cancelled / Failed / Refunded / Checkout Abandoned |

Se aplica un **corte duro** en `FECHA_CORTE_WOO = "2026-05-01"`: los cierres
anteriores salen del pipeline histórico y los posteriores de Woo. Sin ese corte
se contarían dos veces los pedidos del solape (feb–abr 2026). **Si el corte real
cambia, mueve solo esa constante** — está en `dashboard_lt.py` y en los
`informe_lt*.py`.

## 🔑 El producto vendido sale del NEGOCIO, no del contacto
Regla importante y poco obvia. El `pgm` del **contacto** solo está relleno en
~40 % de los pedidos, así que **no sirve** para saber qué se ha vendido. El dato
bueno está en el propio negocio:

1. **`codigo_del_producto`** — en WooCommerce trae el código pgm directamente
   (`CE_0009_EN`, `P_0007_EN`): **99 % relleno**. En el pipeline histórico trae
   un id numérico de producto de HubSpot, que no sirve.
2. **Nombre del producto**, vía los **line items** del negocio (`name` + `hs_sku`).
   Es lo que salva al pipeline histórico, cuyo `dealname` ya lleva el nombre del
   curso (`"Professional Diploma in X - email@dominio"`), mientras que el de Woo
   es solo el número de pedido (`"#15497 Chloe Thompson"`).
3. El `pgm` del contacto, ya solo como último recurso.

Eso es lo que hacen `codigo_producto()`, `tipo_producto()` y
`fetch_ventas_detalle()`. Con esta cadena la atribución por programa pasó del
**17 % al 91 %**. **No vuelvas a atribuir ventas por el `pgm` del contacto.**

## ⚠️ Bug del 207 (ojo, está también en el dashboard de High Ticket)
`hs_post()` daba por bueno **solo el HTTP 200**. Los endpoints `batch/read`
devuelven **207 (Multi-Status)** cuando alguno de los inputs falla — por ejemplo
un negocio sin contacto asociado, que es normalísimo. Al no ser 200 ni 429 ni
5xx, `raise_for_status()` no hacía nada, el bucle agotaba los 5 reintentos y
lanzaba `RuntimeError`, que el `except Exception: pass` del batch se tragaba
**entero**: un solo negocio huérfano dejaba sin país, fuente ni programa a los
otros 99 del lote.

Con el arreglo (aceptar cualquier 2xx) la cobertura de país y origen en los
negocios pasó del **22 % al 99 %**. `bihub-rst-dashboard` tiene el mismo código
y por tanto el mismo bug: **conviene replicar el arreglo allá**.

## 🚫 High Ticket NO cuenta (decisión de negocio)
Por WooCommerce se venden también productos `EP_` / `PG_` / `M_` (programas
ejecutivos, postgrados y másters). **No entran en ninguna cifra de este
dashboard**: se filtran en la capa de datos (`fetch_negocios_cerrados` y
`fetch_ganados_por_programa`), no en las páginas, para que todas las vistas den
lo mismo. La constante es `EXCLUIR_HIGH_TICKET = True`; ponla a `False` si
alguna vez hace falta ver el canal completo.

Pesan lo suyo: en junio de 2026 eran 10 ventas y **69.581 €**, un 29 % de la
facturación que se veía antes del filtro.

## ⚠️ El `hs_sku` de los line items no es de fiar
Al clasificar productos, **usa `codigo_del_producto` del negocio y el NOMBRE del
producto — nunca el `hs_sku` del line item**. Hay registros con el SKU obsoleto:

- `EP_009_EN` etiquetando *"Certificate in Football Tactical Analyst"*
- `M_001_EN` sobre *"Professional Diploma in Sports Marketing and Sponsorship"*
- `PG_003_EN` en extras que ni siquiera son cursos (*"FAMILY ACCESS - ALUMNI"*,
  *"OFFICIAL GRADUATION CEREMONY"*)

Fiarse del SKU colaba ventas de Low Ticket como High Ticket y las eliminaba del
dashboard. El tipo se decide **una sola vez**, en `fetch_negocios_cerrados`, con
datos del negocio; el nombre del line item solo afina los que quedaron en
"Otros", y nunca puede reclasificar algo *como* High Ticket.

## Qué hay dentro de "Otros"
~9 % de la facturación. Son productos reales de Low Ticket que no siguen la
nomenclatura `pgm`: Barça Coach Academy, Football Scouting, Coaches Academy,
Digital Capacity Management, Business Intelligence in Sports, Introduction to
Sports Analytics… Ahí dentro hay además **63 ventas / 21.657 € (ene–jul 2026)
que no son cursos**, sino extras de alumni (`PREMIUM EXPERIENCE`,
`FAMILY ACCESS`, `OFFICIAL GRADUATION CEREMONY`). Hoy **sí cuentan**; si se
decide que no, hay que filtrarlos por nombre en `fetch_negocios_cerrados`.

## Otras notas
- **Batches de HubSpot: máximo 100 inputs** por llamada (400 con más).
- Low Ticket **no tiene** propiedad de motivo de cierre perdido (el
  `motivos_de_cierre_perdido_rst` es de RST). El "motivo" que se muestra es la
  **etapa** en la que murió el pedido.
- `nivel_de_estudios` ("Nivel de Estudios (cursos online)") es la propiedad de
  Low Ticket; `nivel_estudios` es la de EPs y másters — no confundirlas.
- Este repo comparte estructura con `bihub-rst-dashboard` y
  `hofmann-crm-dashboard`. Si arreglas un bug de presentación aquí, mira si
  aplica allá — pero **la capa de datos es distinta**, no copies filtros a ciegas.
- `requirements.txt` es solo para la app de Streamlit. Los scripts de consola
  (`informe_lt*.py`, `contactos.py`, …) necesitan además `requirements-cli.txt`.
