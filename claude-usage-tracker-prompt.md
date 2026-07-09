# Prompt for Claude Code (On-Premise / Fully Local Version)

Copy everything below into Claude Code (in your empty project folder) to kick off the build.

---

## Prompt

Build a full-stack web application called **"Claude Usage Tracker"** that lets a team track everyone's Claude / Claude Code usage limits by uploading screenshots of the `/usage` command output. **This must run 100% on-premise — no external API calls, no cloud services, no internet dependency once set up.**

### Tech Stack
- **Backend:** FastAPI (Python 3.11+), SQLAlchemy, Pydantic v2
- **Database:** PostgreSQL (via Docker Compose) — SQLite is also acceptable as a lighter default given the target machine has limited RAM; make this configurable via `.env`
- **Frontend:** Server-rendered with Jinja2 + HTMX + Alpine.js (no separate SPA build step), styled with Tailwind CSS (use a locally vendored copy, not a CDN, to keep this fully offline-capable)
- **Image → data extraction (local only, no cloud):** This is the primary path, not a two-stage automatic pipeline. Since every screenshot comes from the same source (Claude Code's `/usage` command) with a fixed, predictable field layout, OCR + regex is the main solution — not a "fast path" that falls back automatically.
  1. **Primary — PaddleOCR + regex:** Run PaddleOCR (not Tesseract — it handles small UI/terminal text and varying color themes noticeably better) on every uploaded screenshot, then parse the extracted text with regex/heuristics tuned to the fixed `/usage` field names (Session %, Weekly %, plan tier, reset time). This runs on every upload, is CPU-fast, and needs no model download.
  2. **Manual, on-demand — local VLM:** Do **not** auto-trigger this on low OCR confidence. The OCR result always goes straight to the editable confirmation form first. Only if the user judges it badly wrong do they click a **"Re-extract with AI"** button, which sends the image to a **local Ollama instance running `qwen2.5vl:3b`** (4-bit GGUF, CPU inference) with a strict JSON-only extraction prompt. This keeps the VLM as an on-demand tool, not a background cost on every upload.
  - OCR is the only automatic path; the VLM is available only through the manual "Re-extract with AI" button.
- **Containerization:** Docker Compose with services: `api` (FastAPI), `db` (Postgres, optional/SQLite fallback), `ollama` (runs `qwen2.5vl:3b`, CPU-only, no GPU passthrough required). Configure the Ollama call with **`keep_alive=0`** so the model unloads from RAM immediately after each inference instead of staying resident — on a 16GB machine with only a few GB typically free, reclaiming that RAM between uploads matters more than shaving a few seconds off inference latency.

### Hardware Context (design around this)
Target machine: no dedicated GPU (Intel integrated graphics only), 16 GB RAM (often only a few GB free at any given time), CPU-only inference. Design choices should account for this:
- Keep the Ollama container CPU-only, and note in the README that `qwen2.5vl:3b` inference may take 10–40 seconds per image when manually triggered — this is expected, not a bug. Show a loading/progress state on the "Re-extract with AI" action rather than blocking.
- PaddleOCR is the default path for every upload, so the VLM only consumes CPU/RAM when a user explicitly clicks "Re-extract with AI" — this keeps standing resource usage low.
- Ollama must be called with `keep_alive=0` (or the equivalent config) on every request so the model is unloaded from RAM right after each inference rather than staying resident between uploads.
- Document minimum recommended free RAM (~4–6 GB) for the brief window when the VLM is actively running, and suggest the user close other heavy apps if extraction is slow or fails.
- `docker-compose.yml` should let the user disable the `ollama` service entirely for a lighter footprint if they don't need the VLM fallback at all.

### No Authentication
This is an internal tracking tool, not a multi-tenant app — skip login/auth entirely. On the upload page, just have the person type or select their name/identifier (a simple text input, ideally with autocomplete/datalist from names seen in past uploads so it stays consistent). Store that name directly on the `UsageUpload` row. No user table, no passwords, no sessions, no roles — anyone with access to the app can upload and view the dashboard.

### Page 1: Upload Page (`/upload`)
- File upload form (drag-and-drop + click-to-browse), accepts PNG/JPG
- On submit:
  - Save the image to disk (local `./uploads` volume, mounted in Docker)
  - Run PaddleOCR + regex extraction immediately (this is the default path for every upload)
  - Show the user a preview of the extracted values with an **editable confirmation form** before saving (extraction won't be perfect — always let the human correct it before committing to DB)
  - Include a **"Re-extract with AI"** button next to the form that calls the local Qwen2.5-VL model on-demand and repopulates the form if the user isn't happy with the OCR result — this should show a "processing, may take up to a minute" state, not block the page
  - Store the uploader's name (as entered on the form), upload timestamp, original filename, extracted data, and **which extraction method was used** (`ocr` / `vlm` / `manual`)
- Show recent uploads (from everyone, or filterable to "just mine" by name) below the form

### Page 2: Dashboard (`/dashboard`)
**Per-entry table/feed (main requirement):**
- Uploader name/avatar
- Upload date & time (and "time ago")
- Session usage % (current 5-hour window, if shown)
- Weekly usage %
- Plan tier (Pro / Max 5x / Max 20x / Team, etc. — whatever the screenshot shows)
- Time until reset
- Thumbnail of the uploaded screenshot (click to view full size)
- Extraction method badge (OCR / AI / Manually edited)

**Aggregate/summary widgets at the top:**
- Team-wide average usage % (session & weekly)
- Leaderboard: who's closest to hitting their limit
- Number of uploads today / this week
- Per-user usage trend sparkline (Chart.js, vendored locally not via CDN)
- Filter/search bar: filter by user, date range, plan tier

**Detail view (`/dashboard/user/{uploader_name}`):**
- Full history of that user's uploads with all extracted fields
- Trend line chart over time

### Data Model (suggested — adjust as needed)
```
UsageUpload
- id
- uploader_name          # free-text name entered on upload, no user table/auth
- uploaded_at (timestamp)
- image_path
- original_filename
- session_usage_pct
- weekly_usage_pct
- plan_tier
- session_reset_at
- weekly_reset_at
- extraction_method     # 'ocr' | 'vlm' | 'manual'
- raw_extracted_text    # raw OCR text or raw VLM JSON, for debugging
- was_manually_edited   # bool
```

### API Endpoints (FastAPI)
- `POST /api/uploads` — accepts image, runs PaddleOCR + regex extraction, returns parsed JSON (does NOT save yet)
- `POST /api/uploads/reextract` — triggered only by the "Re-extract with AI" button; calls the local Ollama `qwen2.5vl:3b` model (with `keep_alive=0`) on a given image and returns updated parsed JSON
- `POST /api/uploads/confirm` — saves the (possibly user-edited) extracted data + image reference
- `GET /api/uploads?user=&from=&to=` — filterable list, paginated
- `GET /api/dashboard/summary` — aggregate stats for the top widgets
- `GET /api/users/{uploader_name}/history`
- All endpoints return typed Pydantic response models; add OpenAPI docs at `/docs`

### Local VLM Extraction Prompt (for `qwen2.5vl:3b` via Ollama, manual trigger only)
Call the local Ollama API (`http://ollama:11434/api/generate` or `/api/chat` with an image payload), always passing **`"keep_alive": 0`** in the request so the model unloads from RAM immediately after responding, and instruct the model to return **strict JSON only**, e.g.:
```json
{
  "session_usage_pct": 42,
  "weekly_usage_pct": 18,
  "plan_tier": "Max 5x",
  "session_reset_at": "2026-07-07T18:00:00",
  "weekly_reset_at": "2026-07-10T00:00:00"
}
```
Handle missing/unparseable fields gracefully (null them out) rather than failing the whole request — always fall back to the manual-edit confirmation screen. Set a reasonable timeout (e.g. 60s) on the Ollama call and show a clear "still processing, this can take up to a minute on CPU" message in the UI.

### Project Structure (suggested)
```
.
├── docker-compose.yml
├── Dockerfile
├── .env.example
├── app/
│   ├── main.py
│   ├── models.py
│   ├── schemas.py
│   ├── database.py
│   ├── extraction/
│   │   ├── ocr_extractor.py     # PaddleOCR + regex, default path for every upload
│   │   └── vlm_extractor.py     # Ollama qwen2.5vl:3b call, manual "Re-extract with AI" trigger only, keep_alive=0
│   ├── routers/
│   │   ├── uploads.py
│   │   └── dashboard.py
│   ├── templates/                # Jinja2 HTML
│   └── static/                   # includes vendored Tailwind + Chart.js
├── uploads/                       # volume-mounted image storage
└── tests/
```

### Build Steps
1. Scaffold the FastAPI app, DB models (default to SQLite for zero-friction local dev, Postgres optional), and Alembic migrations
2. Build auth (login/register/session)
3. Build the PaddleOCR + regex extractor first — get this working end-to-end before touching the VLM, since this is the primary path for every upload
4. Add the `ollama` service to Docker Compose and wire up the "Re-extract with AI" manual-trigger VLM extractor, with `keep_alive=0` on every call
5. Build the confirmation/edit form
6. Build the dashboard with the summary widgets and table
7. Add the per-user detail/trend page
8. Write a `docker-compose.yml` that spins up everything with one `docker compose up` — including a step that pulls `qwen2.5vl:3b` into the Ollama container on first run
9. Add a `README.md` with setup instructions, hardware expectations (CPU-only, expect 10-40s VLM extraction time), and a `.env.example` listing required vars (`DATABASE_URL`, `OLLAMA_HOST`, `OLLAMA_MODEL`, `SECRET_KEY`)

### Non-functional requirements
- No external network calls at runtime — everything (model weights, fonts, JS libs) should be either vendored/local or pulled once during `docker compose up` and cached in a volume
- All timestamps stored in UTC, displayed in local time on the frontend
- Basic input validation and error handling on the upload endpoint (file size/type limits)
- Seed script to create a demo admin user and a couple of sample uploads for quick testing
- Keep the UI clean and minimal — this is an internal tool, not a marketing site

Ask me clarifying questions before starting if anything above is ambiguous (e.g., SQLite vs Postgres as the real default, whether OCR-only is sufficient for launch and the VLM fallback can come later). Otherwise, start by scaffolding the project structure and the Docker Compose setup with the OCR-only fast path first.
