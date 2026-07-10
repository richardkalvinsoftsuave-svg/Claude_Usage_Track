# Setup Guide

This guide walks a new contributor through setting up and running **Claude Usage Tracker** after cloning the repository. The project has two parts:

- **`app/`** — FastAPI backend (REST API, OCR/VLM extraction, MySQL storage)
- **`frontend/`** — React + TypeScript + Vite single-page app (dashboard UI)

---

## 1. Prerequisites

Install these before you start:

| Tool | Version | Notes |
|------|---------|-------|
| Python | 3.11+ | Backend runtime |
| Node.js | 18+ (20+ recommended) | Frontend runtime, includes `npm` |
| MySQL | 8.x | Default database (or use Docker Compose, see below) |
| Git | any recent version | To clone the repo |

Optional:
- **Docker + Docker Compose** — lets you run the backend, database, and local VLM without installing MySQL/Python dependencies yourself.
- **Ollama** — only needed if you want the "Re-extract with AI" fallback feature to work locally.

---

## 2. Clone the repository

```bash
git clone <repository-url>
cd "claude usgae tracking"
```

---

## 3. Backend setup (FastAPI)

### 3.1 Create a virtual environment and install dependencies

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

> PaddleOCR downloads its model weights the first time it runs and caches them locally, so the first upload/extraction will be slower and needs internet access once.

### 3.2 Configure environment variables

Copy the example env file and adjust values for your machine:

```bash
cp .env.example .env
```

Key variables in `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `mysql+pymysql://root:password@localhost:3306/usage_db` | MySQL connection string |
| `MYSQL_USER` / `MYSQL_PASSWORD` / `MYSQL_DB` | `root` / `password` / `usage_db` | Used by Docker Compose if applicable |
| `UPLOAD_DIR` | `./uploads` | Where uploaded screenshots are stored |
| `OLLAMA_HOST` | `http://localhost:11434` | Local Ollama API (only used for manual re-extraction) |
| `OLLAMA_MODEL` | `qwen2.5vl:3b` | Model used for manual re-extraction |
| `MAX_FILE_SIZE` | `10485760` | Max upload size in bytes (10 MB) |

### 3.3 Create the database

The app does **not** create the MySQL database itself (it only creates tables). Create an empty database matching `DATABASE_URL` first, e.g.:

```sql
CREATE DATABASE usage_db;
```

Tables are created automatically on first run via SQLAlchemy.

### 3.4 Run the backend

```bash
uvicorn app.main:app --reload
```

On Windows you can alternatively use the helper script, which checks for port conflicts first:

```powershell
.\start.ps1
```

The API is now available at `http://localhost:8000`:
- Interactive docs: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`

---

## 4. Frontend setup (React + Vite)

Open a second terminal (keep the backend running).

```bash
cd frontend
npm install
npm run dev
```

The frontend dev server runs at `http://localhost:5173` and proxies `/api` and `/uploads` requests to the backend on `http://127.0.0.1:8000` (see `frontend/vite.config.ts`), so make sure the backend is running first.

Other useful frontend scripts:

```bash
npm run build     # type-check and build for production (outputs to frontend/dist)
npm run preview   # preview the production build locally
npm run lint       # run oxlint
```

---

## 5. Running everything together

1. Terminal 1: start the backend (`uvicorn app.main:app --reload`) from the repo root.
2. Terminal 2: start the frontend (`npm run dev`) from `frontend/`.
3. Open `http://localhost:5173` in your browser.

---

## 6. Running with Docker Compose (alternative to manual setup)

If you'd rather not install MySQL/Python locally, Docker Compose can run the backend, database, and a local Ollama instance for you:

```bash
cp .env.example .env
docker compose up --build
```

This starts:
- `api` — the FastAPI backend on `http://localhost:8000`
- `db` — the database for persistent storage
- `ollama` — local Ollama instance; on first run it pulls the configured model

To skip the VLM service and start only the API and database:

```bash
docker compose up api db --build
```

> Note: Docker Compose still runs only the backend container. You still need to run the frontend separately with `npm run dev` from `frontend/` (Step 4).

---

## 7. Running tests

Backend tests (pytest):

```bash
pytest
```

---

## 8. Troubleshooting

- **`DLL load failed while importing cv2` (Windows)** — Your Windows edition may be missing the Media Feature Pack (common on N/KN editions). Install the Media Feature Pack, or run the backend inside Docker/WSL instead.
- **Frontend can't reach the API** — Confirm the backend is running on `http://127.0.0.1:8000` before starting the frontend; the Vite dev server proxies to that address.
- **MySQL connection errors** — Verify `DATABASE_URL` in `.env` matches a MySQL server you can reach, and that the database named in the URL already exists.
- **Slow first extraction** — PaddleOCR downloads model weights on first use; subsequent runs are fully offline and faster.
- **"Re-extract with AI" not working** — This feature requires a local Ollama instance running the model set in `OLLAMA_MODEL`. It's optional; OCR extraction works without it.
