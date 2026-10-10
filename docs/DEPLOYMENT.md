# TripMission — Deployment

## 1. Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SERPAPI_API_KEY` | live mode | — | SerpApi key (backend only) |
| `DEMO_MODE` | no | `false` | `true` serves the labelled demo dataset instead of live data |
| `DATABASE_URL` | no | `sqlite:///./tripvision.db` | e.g. `postgresql+psycopg://tripvision:tripvision@localhost:55432/tripvision` |
| `REDIS_URL` | no | — | e.g. `redis://localhost:6379/0`; if unset, the DB cache is used |
| `AI_PROVIDER` | no | `anthropic` | `euri` (OpenAI-compatible chat completions) or `anthropic` |
| `AI_API_KEY` | no | — | Key for the provider; "Why this journey?" falls back to rule-based text without it |
| `AI_MODEL` | no | `claude-opus-5-5` | Model used for explanations (e.g. `gpt-5.4-mini` on euri) |
| `AI_MODEL_FAST` | no | — | Fallback model tried if `AI_MODEL` fails (euri) |
| `AI_BASE_URL` | no | `https://api.euron.one/api/v1/euri` | OpenAI-compatible base URL (euri) |
| `FRONTEND_URL` | no | `http://localhost:5173` | Comma-separated CORS origins |
| `EMAIL_PROVIDER` | no | `auto` | `smtp`, `resend`, `preview` or `auto` (SMTP if `SMTP_HOST`, Resend if `RESEND_API_KEY`, else preview) |
| `EMAIL_FROM` | no | `TripMission <no-reply@tripvision.app>` | Sender (must be allowed by your provider) |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` / `SMTP_USE_TLS` | no | — / 587 / — / — / true | SMTP delivery (e.g. Gmail app password) |
| `RESEND_API_KEY` | no | — | Resend delivery |
| `APP_BASE_URL` | no | first `FRONTEND_URL` | Base for "View my journey" links in emails |
| `REMINDER_HOURS_BEFORE` | no | `24` | When reminders are sent |
| `SCORING_WEIGHTS` | no | — | JSON override of the default weight profile |
| `LOG_LEVEL` | no | `INFO` | |
| `VITE_API_URL` | no (frontend) | `/api` | Backend base URL for the frontend build |

Copy `.env.example` to `.env` at the repository root. The backend reads `../.env` and `./.env`.

## 2. Local development (no Docker)

Prerequisites: Python 3.12+, Node 20.19+.

```bash
# backend
cd backend
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt        # Windows  (macOS/Linux: .venv/bin/pip)
.venv/Scripts/python -m uvicorn app.main:app --reload --port 8000

# frontend (second terminal)
cd frontend
npm install
npm run dev                                           # http://localhost:5173 (proxies /api → :8000)
```

Demo without a SerpApi key: set `DEMO_MODE=true` in `.env`, restart the backend. The navbar shows a
**DEMO MODE** badge and every result is labelled as demo data.

## 3. Docker Compose (PostgreSQL + Redis)

```bash
cp .env.example .env          # add SERPAPI_API_KEY (and optionally AI_API_KEY)
docker compose up --build
# frontend → http://localhost:8080   backend → http://localhost:8000/api/v1/health
```

Services: `postgres:16-alpine`, `redis:7-alpine`, `backend` (Python 3.12 slim + uvicorn),
`frontend` (Node build → nginx; `/api` proxied to the backend).

## 4. Production notes

* Run the backend behind HTTPS; set `FRONTEND_URL` to the real origin(s).
* Use managed PostgreSQL and Redis; `DATABASE_URL` must use the `postgresql+psycopg://` driver.
* Run a single uvicorn worker per container for the in-memory rate limiter, or move the limiter to Redis
  before scaling horizontally (documented limitation).
* Never bake `.env` into images — inject secrets via the platform's secret store.
* Background analyses run in-process; a mission interrupted by a restart is marked `failed` on startup
  (users simply re-run it). A task queue (Celery/RQ/Arq) is the post-MVP upgrade.
