# CLAUDE.md — zxb-pet

Mascota virtual tipo Tamagotchi conectada al vault de Obsidian "SegundoCerebro". Proyecto de portafolio (Cloud Engineer).

## Idioma
Responde y documenta en **español**. Código, identificadores y commits en inglés.

## Arquitectura (decidida: no cambiar sin consultar)
- **Sync:** Syncthing PC (send-only) → zxb-app01 (receive-only). En el contenedor el vault se monta **read-only**.
- **Backend:** Python + FastAPI + SQLite, con Docker Compose en zxb-app01 (192.168.1.63, Debian 12, 3 GB RAM). El puerto 3000 ya lo usa el Job Hunter.
- **Endpoints:** `GET /health`, `/tasks`, `/study`, `/briefing` (cacheado por día, `?refresh=true`), `/pet`.
- **LLM:** Claude Haiku (verificar el ID vigente en docs.claude.com). Un briefing al día.
- **Cliente:** la UI la sirve el backend. En el PC solo hay un cascarón Tauri: ventana transparente y siempre visible, autoarranque, y **una única función local**: crear notas nuevas en `00-Inbox`. Si el backend no responde → mascota dormida.
- Acceso remoto (Tailscale / Cloudflare Tunnel): después del MVP.

## Reglas
- El backend **nunca** escribe en el vault. La mascota **nunca** modifica notas existentes.
- Vault: `C:\Users\Zeb\iCloudDrive\iCloud~md~obsidian\SegundoCerebro`. Solo lectura, salvo `01-Proyectos/Mascota Virtual.md` (y su carpeta de subnotas si hace falta). Actualizar esa nota al final de cada sesión y fase.
- Ningún secreto en git ni en el vault: la API key va en `.env`.
- Servidor: dar los comandos al usuario; pedir permiso antes de ejecutar algo por SSH.
- Red sin IPv6: preferir IPv4 (`curl -4`, bind a `0.0.0.0`).
- Trabajar por fases (F0–F6) y detenerse al final de cada una para que el usuario apruebe.

## Mascota
Zebot: sarcástico y con jerga gamer. Dificultad `casual|normal|hardcore` (por defecto `normal`), adaptativa (+1 tras 3 días sin actividad, −1 con racha de 7).

## Estructura y comandos
- `backend/app/vault/`: parser (`markdown.py`, `tasks.py`, `study.py`). `pet.py` (reglas puras), `db.py` (SQLite), `briefing.py` (Claude), `main.py` (FastAPI).
- Tests: `cd backend && .venv\Scripts\python -m pytest`. El vault de prueba está en `backend/tests/fixtures/vault/`. La API de Claude siempre se mockea en los tests.
- Local: `VAULT_PATH` y `DATA_DIR` como variables de entorno, luego `uvicorn app.main:app`.
- Docker: `docker compose up -d --build` en la raíz del repo, con `.env` (plantilla en `.env.example`).
- Modelo: `claude-haiku-4-5` (verificado el 2026-09-30: activo, retiro "no antes del 2026-10-15", con 60 días de aviso). Sin `thinking` ni `effort`, porque Haiku 4.5 no los usa así.

## Reglas del parser
Ver la sección "Reglas del parser" en la nota del vault `01-Proyectos/Mascota Virtual.md`.
