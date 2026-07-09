# Claude Usage Tracker (Backend)

On-premise FastAPI backend that turns Claude Code `/usage` screenshots into structured usage data for a team dashboard.

## Quick start (local)

```bash
python -m venv .venv
. .venv/Scripts/activate  # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The API is now available at `http://localhost:8000` with interactive docs at `/docs`.

## Configuration

Copy `.env.example` to `.env` and adjust:

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///./claude_usage.db` | SQLite or Postgres URL |
| `UPLOAD_DIR` | `./uploads` | Where screenshots are stored |
| `EXTRACTION_MODE` | `ocr_only` | `ocr_only`, `ocr_plus_manual_vlm`, or `vlm_only` |
| `OLLAMA_HOST` | `http://localhost:11434` | Local Ollama API |
| `OLLAMA_MODEL` | `qwen2.5vl:3b` | Model used for manual re-extraction |
| `MAX_FILE_SIZE` | `10485760` | Max upload size in bytes (10 MB) |

## Web UI

The app is server-rendered with Jinja2 + HTMX + Alpine.js. All JS libraries are vendored locally under `app/static/vendor/` so the app works offline.

- `/` — Upload page (drag-and-drop or click-to-browse)
- `/dashboard` — Summary widgets, leaderboard, per-user trend charts, and upload table
- `/dashboard/user/{uploader_name}` — Per-user history and trend line chart

## API endpoints

- `POST /api/uploads` — upload a PNG/JPG screenshot, run OCR, return extracted values (not saved yet)
- `POST /api/uploads/reextract?image_path=<path>` — manual VLM re-extraction via local Ollama
- `POST /api/uploads/confirm` — save the user-confirmed upload
- `GET /api/uploads?user=&from=&to=&skip=&limit=` — list confirmed uploads
- `GET /api/uploads/{id}` — single upload detail
- `GET /api/dashboard/summary` — aggregate stats, leaderboard, trends
- `GET /api/dashboard/users/{uploader_name}/history` — per-user history + trend
- `GET /uploads/{filename}` — served screenshot

## OCR behavior

The default path uses **PaddleOCR** with regex tuned to Claude Code usage screens:

- Account info: auth method, email, organization, plan
- Usage: session %, weekly %, weekly Fable %
- Resets: session, weekly, and Fable reset times (converted to UTC)

Both the classic `/usage` command layout and the newer **Account & Usage** dialog are supported.

PaddleOCR downloads its model weights on first use and caches them locally. Subsequent runs are fully offline.

> **Windows note:** If you see `DLL load failed while importing cv2`, your Windows edition may be missing the Media Feature Pack (common on N/KN editions). Install the Media Feature Pack, or run the backend inside Docker/WSL where the required libraries are present.

> **Schema note:** If you have an existing `claude_usage.db` from before these fields were added, delete it so SQLAlchemy can recreate the schema.

## Manual VLM fallback

If OCR is inaccurate, the frontend can call `POST /api/uploads/reextract` to run the local **Ollama** model `qwen2.5vl:3b`. This is CPU-only and can take 10–40 seconds per image. The backend sends `"keep_alive": 0` so the model unloads from RAM immediately after each inference.

## Hardware notes

- Target machine: CPU-only, ~16 GB RAM, often only a few GB free.
- Keep `EXTRACTION_MODE=ocr_only` for the lightest footprint.
- For VLM usage, ensure ~4–6 GB of free RAM during inference and close heavy apps if needed.

## Running with Docker Compose

Copy `.env.example` to `.env` and adjust as needed, then run:

```bash
docker compose up --build
```

This starts:
- `api` — the FastAPI backend on `http://localhost:8000`
- `db` — PostgreSQL for persistent storage
- `ollama` — local Ollama instance; on first run it pulls `qwen2.5vl:3b`

To run without the VLM service (lightest footprint), set `EXTRACTION_MODE=ocr_only` in `.env` and start only the API and database:

```bash
docker compose up api db --build
```

## Running tests

```bash
pytest
```
