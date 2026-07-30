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
  Los prefijos de High Ticket (`EP_`, `PG_`, `M_`) NO entran aquí.
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

## ⚠️ Limitación conocida: atribución lead → venta
Buena parte de los pedidos de WooCommerce **no enlazan con un contacto que tenga
`pgm`**: en un muestreo de 60 pedidos Completed, 31 (53 %) tenían el contacto sin
`pgm` y 13 lo tenían con prefijo de High Ticket. Consecuencia práctica:

- Los KPIs de **ventas** (que salen del pipeline) son correctos.
- La **conversión por programa** y las tablas de campaña infra-atribuyen: en
  junio de 2026, 372 de 445 negocios ganados quedaron como "Sin programa".

No es un bug del dashboard, es un hueco de datos en el CRM. Si se quiere cerrar,
hay que rellenar `pgm` (o `curso`) en los contactos que compran por WooCommerce.

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
