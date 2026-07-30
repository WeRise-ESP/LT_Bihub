# 📘 Manual de instalación — Dashboard Low Ticket BiHub

Guía paso a paso para dejar el dashboard funcionando en tu ordenador, poder editarlo con
**Claude Code** y publicar los cambios. No hace falta ser técnica: sigue los pasos en orden.

> ⏱️ Tiempo aprox.: 20–30 min la primera vez. Luego solo abres y trabajas.

---

## ✅ Antes de empezar — lo que necesitas de Misael

1. **Invitación al repositorio de GitHub** `LT_Bihub` (te llega un email → acéptala).
2. **El token de HubSpot** (un texto largo tipo `pat-eu1-xxxx`). Te lo pasa por un canal seguro.
   👉 Guárdalo, lo usarás en el **Paso 5**. **No lo compartas ni lo subas a ningún sitio público.**

---

## PASO 1 · Instalar los programas base

Necesitas 3 cosas: **Git**, **Python 3.12** y **Claude Code**. Elige tu sistema:

### 🍎 En Mac

1. Abre la app **Terminal** (búscala con `Cmd + Espacio` → escribe "Terminal").
2. Instala **Homebrew** (gestor que facilita instalar lo demás). Pega esto y pulsa Enter:
   ```bash
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   ```
   Sigue las instrucciones en pantalla (te pedirá tu contraseña del Mac).
3. Instala **Git** y **Python 3.12**:
   ```bash
   brew install git python@3.12
   ```
4. Comprueba que funcionan:
   ```bash
   git --version
   python3.12 --version
   ```
   Deberías ver una versión de git y `Python 3.12.x`.

### 🪟 En Windows

1. **Git:** descarga e instala desde 👉 https://git-scm.com/download/win (deja todas las opciones por defecto → Next → Next → Install).
2. **Python 3.12:** descarga desde 👉 https://www.python.org/downloads/release/python-3120/
   (baja hasta "Windows installer 64-bit").
   ⚠️ **MUY IMPORTANTE:** en la primera pantalla del instalador, **marca la casilla
   “Add python.exe to PATH”** antes de darle a *Install Now*.
3. Abre **PowerShell** (menú inicio → escribe "PowerShell") y comprueba:
   ```powershell
   git --version
   python --version
   ```
   Debería mostrar git y `Python 3.12.x`.

### 🤖 Claude Code (los dos sistemas)

Instálalo siguiendo la guía oficial: 👉 https://docs.anthropic.com/claude-code
(Si Misael te lo instaló ya, salta este punto.)

---

## PASO 2 · Aceptar la invitación de GitHub

1. Revisa tu email: hay una invitación al repositorio **LT_Bihub**.
2. Pulsa **“Accept invitation”**.
3. Si no tienes cuenta de GitHub, créala gratis en https://github.com y pídele a Misael que
   te reinvite con tu usuario.

---

## PASO 3 · Descargar el proyecto (clonar)

En la **Terminal** (Mac) o **PowerShell** (Windows), colócate donde quieras guardar el proyecto
(por ejemplo el Escritorio) y clónalo:

```bash
cd Desktop
git clone https://github.com/WeRise-ESP/LT_Bihub.git
cd LT_Bihub
```

> Si te pide usuario/contraseña de GitHub, usa tu usuario y un **token personal** de GitHub
> (Settings → Developer settings → Personal access tokens) como contraseña. Windows suele abrir
> una ventana para iniciar sesión con el navegador; hazlo ahí.

Ahora ya tienes **todo el código** en la carpeta `LT_Bihub`.

---

## PASO 4 · Crear el entorno e instalar dependencias

Esto crea una "cajita" aislada con las librerías que necesita el dashboard.

### 🍎 Mac
```bash
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 🪟 Windows
```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Cuando el entorno está activado verás `(venv)` al principio de la línea. La instalación tarda
un par de minutos.

---

## PASO 5 · Poner el token de HubSpot

El proyecto necesita el token para leer los datos del CRM. **No viene en GitHub** (por seguridad),
así que lo pones tú:

1. En la carpeta del proyecto, crea un archivo llamado exactamente **`.env`** (con el punto delante).
   - Mac (terminal): `nano .env` → pega la línea de abajo → `Ctrl+O`, Enter, `Ctrl+X`.
   - Windows: `notepad .env` → pega la línea → Guardar. (Si pregunta por la extensión, guárdalo
     como *Todos los archivos* y nombre `.env`).
2. Contenido del archivo (sustituye por el token que te pasó Misael):
   ```
   HUBSPOT_TOKEN=pat-eu1-EL_TOKEN_QUE_TE_PASO
   ```
3. Guárdalo. ⚠️ Nunca subas este archivo a GitHub (ya está protegido en `.gitignore`).

---

## PASO 6 · Ejecutar el dashboard en tu ordenador

Con el entorno activado (`(venv)` visible):

```bash
streamlit run dashboard_lt.py
```

Se abre solo en el navegador (`http://localhost:8501`). Si ves el dashboard con datos, **¡todo listo!** 🎉
Para pararlo: en la terminal pulsa `Ctrl + C`.

---

## PASO 7 · Trabajar con Claude Code

1. Abre **Claude Code** dentro de la carpeta `LT_Bihub`.
2. Pídele los cambios en lenguaje normal (ej. *"añade una columna X a la tabla Y"*).
3. Claude edita el código; tú puedes volver a ejecutar el Paso 6 para ver el resultado en local.

---

## PASO 8 · Publicar los cambios (que se vean en el dashboard en vivo)

El dashboard en internet se actualiza **solo** cuando subes los cambios a GitHub:

```bash
git pull origin main                     # 1) trae lo último (antes de empezar)
# ...haces cambios y pruebas...
git add -A
git commit -m "describe lo que cambiaste"
git push origin main                     # 2) publica → se actualiza en 1-3 min
```

> No hay que tocar nada más: al hacer `push`, el servidor (Streamlit Cloud) reconstruye la app sola.

---

## 🔁 Rutina del día a día (para no pisaros)

Como sois dos trabajando el mismo proyecto:

- **Al empezar:** `git pull origin main` (trae lo que subió la otra persona).
- **Al terminar:** `git add -A && git commit -m "..."` y `git push origin main`.

Y cada vez que abras una terminal nueva, recuerda activar el entorno:
- Mac: `source venv/bin/activate`
- Windows: `venv\Scripts\activate`

---

## 🆘 Problemas frecuentes

| Síntoma | Solución |
|---|---|
| `command not found: python3.12` / `python no se reconoce` | Reinstala Python 3.12 marcando "Add to PATH" (Windows) o `brew install python@3.12` (Mac). Cierra y abre la terminal. |
| `ModuleNotFoundError` al ejecutar | ¿Está activado el entorno? Debe verse `(venv)`. Si no: activa (Paso 4) y repite `pip install -r requirements.txt`. |
| El dashboard dice `HUBSPOT_TOKEN no encontrado` | Revisa que el archivo `.env` esté en la carpeta del proyecto y con la línea correcta. |
| `git push` rechazado (`rejected`) | Alguien subió cambios antes. Haz `git pull origin main`, resuelve si pide algo, y vuelve a `git push`. |
| La app en internet da "Error running app" | Casi siempre es la versión de Python en Streamlit Cloud: debe ser **3.12**. Avisa a Misael. |

---

## 🔐 Seguridad (importante)

- El **token de HubSpot** da acceso a los datos del CRM. No lo compartas ni lo subas a GitHub.
- Es **el mismo token** que usa el dashboard de High Ticket (mismo portal de HubSpot): si se
  regenera, hay que actualizarlo en los **dos** proyectos.
- Si crees que se ha filtrado, avisa: se regenera en HubSpot y se actualiza en cada `.env` y en
  los *Secrets* de Streamlit Cloud.

---

## 📄 Extra · Los informes en Excel

Aparte del dashboard hay tres scripts que generan Excel en la carpeta `exports/`.
Necesitan un par de librerías más:

```bash
pip install -r requirements.txt -r requirements-cli.txt
python informe_lt.py
python informe_lt_fuente.py
python informe_lt_lead_status.py
```

Comparan dos meses. Para cambiarlos, edita la constante `PERIODOS` al principio de cada script.

---

¿Dudas? Escríbele a Misael. En el repo también está el `README.md` con el resumen rápido.
