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
  clasificación "Válido / No válido" de High Ticket NO aplica.

## ⚠️ "Activado" NO sale de `lt_lead_status`
Es el error intuitivo y ya se cometió una vez. `clasif_activado()` mira señales
reales de interés del lead:

- abrió algún email de marketing (`hs_email_open`), o
- hizo clic en alguno (`hs_email_click`), o
- tiene actividad comercial anotada (`num_contacted_notes`).

**No vale usar `lt_lead_status` para esto**, por dos razones medidas sobre
ventanas de ~2.000 contactos:

1. El **~96 % de los contactos recibe el email** de marketing, en todos los
   períodos. "Haberlo recibido" no discrimina nada, así que un estado de
   "primera respuesta automatizada" no dice si el lead reaccionó.
2. Esa propiedad la escribe un workflow que **dejó de dispararse a mediados de
   junio de 2026**: el % con estado distinto de "Nuevo" cayó del 96,7 % al 0,8 %
   de una semana a otra, mientras la entrega de emails seguía plana al 95-96 %.
   Medía si la automatización funcionaba, no el interés del lead.

| Ventana | Métrica vieja (`lt_lead_status`) | Métrica actual | Abrió | Clic | Comercial |
|---|---:|---:|---:|---:|---:|
| 2–8 jun 2026 | 96,8 % | 61,3 % | 19,0 % | 3,6 % | 51,4 % |
| 16–22 jun 2026 | 0,8 % | 12,0 % | 11,5 % | 2,5 % | 1,4 % |
| 7–13 jul 2026 | 1,0 % | 16,2 % | 15,8 % | 2,5 % | 1,0 % |

La caída de junio sigue ahí (61 % → 12 %), pero ahora se ve **de qué es**: las
aperturas se mantienen (19 % → 11-16 %) y lo que se desploma es la **actividad
comercial** (51,4 % → 1,4 %). O sea, a los leads se les sigue mandando correo —
incluso más que antes— pero dejaron de trabajarse.
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

## 📥 Canal de entrada del contacto
**No hay propiedad curada.** `canal_de_contacto` existe pero está **vacía en el
100 %** de los contactos Low Ticket, y sus opciones (Email/Teléfono/Linkedin)
no tienen nada que ver. El canal se deduce en `canal_entrada()` a partir de:

1. `hs_object_source_label` — cómo se creó el registro (`FORM`, `CONVERSATIONS`,
   `INTEGRATION`, `CRM_UI`, `IMPORT`).
2. Si es `FORM`, el **nombre del formulario** en `hs_object_source_detail_1`.

Nomenclatura real de los formularios (los patrones se evalúan EN ORDEN, importa):

| Nombre del formulario | Canal |
|---|---|
| `Form_P_0023_ES_05/26`, `FormLargo_…`, `fcb_bihub_…_leadads…_fb/ig_…` | Facebook Lead Ads |
| `FORM_LowTicket_ES` / `_EN` / `_CA` | Formulario web Low Ticket |
| `FORM_LowTicket_ES_Landing`, `Barca Landing catalogo ES` | Landing |
| `FORM LOWTICKET - BANNER WEB` | Banner web |
| `FORM_HighTicket_*` | Formulario web High Ticket |
| `Formulario_Helpdesk_*` | Helpdesk |
| `TEST_*` | Test |
| `WooCommerce by MakeWebBetter` | Checkout / tienda |

⚠️ Ojo con el orden: `fcb_bihub_lowticket_leadadsgeneric_…` lleva "lowticket"
dentro pero es Lead Ads, y `FORM_LowTicket_ES_Landing` es una landing. Por eso
Lead Ads y Landing se comprueban **antes** que el formulario web.

Reparto real (junio 2026): Facebook Lead Ads **89 %**, formulario web 9,1 %,
landing 0,9 %, el resto testimonial. Pero la tasa de **activación** cuenta otra
historia: checkout 64,7 %, chatbot 47,8 %, formulario web 46,4 %, Lead Ads
43,4 % y landing solo 6 %.

## 🚫 Canales excluidos
`CANALES_EXCLUIDOS = {"Test", "Formulario web High Ticket"}`, filtrados en
`fetch_data` (capa de datos, no en las páginas) para que las cinco vistas
cuenten lo mismo:

- **Test**: formularios de prueba del equipo (`TEST_*`), no son leads.
- **Formulario web High Ticket**: aunque el contacto traiga un `pgm` de Low
  Ticket, entró por el embudo de High Ticket.

En julio de 2026 eran 5 y 46 contactos: 11.132 → 11.083.

## ⚠️ La activación se desplomó a mitad de junio de 2026
Dato de negocio, no bug del dashboard, pero conviene tenerlo presente al leer
cualquier tasa de activación:

| Semana de creación | Contactos | % Activados |
|---|---:|---:|
| 01/06/2026 | 2.464 | 96,6 % |
| 08/06/2026 | 1.705 | 94,8 % |
| 15/06/2026 | 2.257 | **2,9 %** |
| 22/06/2026 | 2.207 | 1,3 % |
| julio (media) | ~9.400 | ~1 % |
| 27/07/2026 | 1.347 | 18,9 % |

No es que los leads sean recientes: los de mediados de junio llevan seis semanas
y siguen al 1 %. Todo apunta a que el workflow de **"Primera respuesta
automatizada"** dejó de dispararse alrededor del **15 de junio de 2026**. Desde
el dashboard solo se ve el efecto sobre `lt_lead_status`; para confirmarlo hay
que mirar el workflow en HubSpot.

## ⚠️ La "IA" NO es un canal de entrada
Es una **fuente de tráfico**: `hs_analytics_source = AI_REFERRALS` →
"Referencias de la IA". Son personas que preguntan a ChatGPT y similares, llegan
a la web y entran por el formulario normal. Si buscas leads de IA, mira la
dimensión de **origen**, no la de canal. En junio de 2026 fueron 40 contactos.

Tampoco existe un canal "chatbot" como formulario: los del chat entran con
`hs_object_source_label = CONVERSATIONS` (23 en junio).

## 🗂️ Los nombres de curso salen del catálogo de productos
Los contactos **no traen el nombre del curso**: `mail_programa_interes` y
`curso` están casi siempre vacíos en Low Ticket, solo viene el código en `pgm`.
Para poder enseñar "CE_0044 · Certificate in Football Scouting" en vez de un
código pelado, `fetch_catalogo_productos()` construye un mapa
**código base → nombre** leyendo el catálogo de productos de HubSpot
(`/crm/v3/objects/products`, campo `hs_sku`).

⚠️ **El catálogo solo tiene el nombre en inglés.** La ficha `CE_0009_ES` se
llama *"Certificate in Sports Cardiology [CE_0009] - Spanish"* y `description`
está vacía en los 91 productos `_ES`. No hay campo de nombre traducido.

El nombre en castellano solo existe en el **evento de conversión** del contacto
(`first_conversion_event_name`), que es el título de la página del curso:
*"Certificado en Cardiología del Deporte - Barça Innovation Hub: FORM_…"*.
`fetch_nombres_cursos_es()` lo extrae recortando por `" - Barça"`.

El idioma se elige por el **sufijo del `pgm` del contacto** (`_ES` → `_CA` →
`_EN`), no adivinándolo del texto: hay cursos con nombre de marca
(*Barça Coach Academy*, *Coaches Academy II*) que parecen inglés y no lo son.

`nombres_cursos()` mezcla las dos fuentes: manda el castellano y el catálogo
queda de respaldo para los cursos que solo se imparten en inglés (18 de 89).

Cobertura en junio de 2026: **121 códigos** en el mapa, 92 de Low Ticket, que
nombran el **100 %** de los códigos del ranking. Cuesta ~30 s la primera vez
(47 páginas de contactos + 10 de productos), por eso la caché es de **2 horas**.

Lo usan el ranking de captación (página de Contactos) y `_prog_label` de la
página de Conversión. Si un código sale con "—", no está ni en el catálogo ni
en ningún evento de conversión.

## Nombres de país: pasan por `normaliza_pais()`
El país llega escrito de muchas formas según la fuente del dato (formulario en
español, país de la IP en inglés, código ISO, hasta una ciudad). Sin unificar se
partía en filas distintas: **"España" (1.254) y "Spain" (280) se contaban por
separado**, y España no aparecía como el primer país que en realidad es.

`normaliza_pais()` canoniza antes de agrupar (`Spain` / `es` / `Valencia` →
`España`, `Viet Nam` → `Vietnam`, `Marokko` → `Morocco`…) y manda a "Sin datos"
lo que no es un país (prefijos como `+1`, ids sueltos, `0: Object`). Bajó de 170
a 145 valores distintos. Si aparece una variante nueva, añádela a
`_PAIS_CANONICO`.

⚠️ Los `informe_lt*.py` tienen su **propia** `resolve_pais` y NO normalizan
todavía: si sacas un Excel, España y Spain saldrán separados.

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
