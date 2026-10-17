# TripMission

> **Don't just plan the trip. Make sure you can actually make it.**

TripMission is a **multi-modal, constraint-aware travel decision engine**. Give it a mission — *be at Manyata Tech
Park, Bengaluru, by 10:00 on 9 October, from Indore, for ₹10,000, with an hour to spare* — and it searches live
flights, **train and bus schedules**, road routes, hotels, maps, places and reviews through **SerpApi**, builds
every complete journey (flight / train / bus / road + hotel + timed transfers), costs it all-in, scores it,
analyses what could go wrong, and recommends the one you should take — then keeps you posted by email.

Built for the **Hacktoberfest 2026** event — Travel & Local Discovery.

![Results](docs/screenshots/results.png)

---

## The problem

Flight search tells you which flights exist. Hotel search tells you which hotels exist. Maps tells you how long
one drive takes. **None of them tells you whether the whole chain works** — and for an interview, an exam or a
hospital appointment, a broken chain means the trip failed.

## The solution

| | |
|--|--|
| **No airport? No problem** | Door → venue, not airport → airport. A destination without an airport (Ujjain) is a valid place: TripMission finds the nearest *practical* airport, adds the road transfer, marks long transfers *low practicality*, and skips flight searches entirely for short trips (Indore → Ujjain is 62 km — train, bus and road are compared instead). |
| **Flight vs train vs bus vs road** | Every mode is evaluated as a complete journey. Train/bus schedules are live from Google Maps transit; fares come from Google Search's transport-options box when a route clearly matches, otherwise they're labelled *Estimated fare*. Nothing is ever called a confirmed ticket. |
| **Total trip cost** | Ticket + ground transport + hotel × nights + food, each line labelled LIVE / ESTIMATED / YOUR INPUT / CALCULATED, with budget remaining or over budget. |
| **What matters most?** | Balanced, Save money, Save time or Avoid risk — deterministic weight profiles. Mission templates (interview, exam, wedding…) set sensible defaults. |
| **Time vs money** | Budget bars per mode, a cost-vs-time chart and a computed sentence: "Spend ₹3,780 more (flight instead of bus) to save about 26 hours." |
| **Email updates** | Trip summary, reminder 24 h before departure, and change alerts only for meaningful changes (SMTP / Resend / preview). |
| **Mission Score (0–100)** | Deterministic, weighted: arrival reliability, budget, ground travel, location, hotel, travel time, review confidence. Weights adapt to the mission type. |
| **Arrival buffer** | Every journey is timed door-to-venue, then adjusted for delay history, connections and real traffic ranges. |
| **Risk engine** | LOW / MEDIUM / HIGH with named factors ("Tight 55-minute layover", "Hotel 12 km from venue") and mitigations. |
| **Two strategies** | Same-morning vs fly-the-day-before, compared automatically. |
| **Best overall / Cheapest / Fastest / Safest / Best value** | Calculated categories — switch between them, or compare side by side. |
| **"No journey fits"** | Concrete relaxations computed from the data — *Increase budget to ₹6,600*, *A 09:00 start would work* — one click re-runs the mission. |
| **Review signals** | Strengths and concerns extracted from real review data, with verbatim quotes. Nothing generated. |
| **Local discovery** | Places chosen for the mission (interview → cafés, pharmacies; vacation → attractions, restaurants). |
| **Why this journey?** | Explanation from the engine's numbers; AI-written when configured, and **rejected if it contains any number not in the data**. |
| **How we decided** | A calm, collapsed panel: what's live, what's calculated, what's estimated. Request counts, timings and raw provider errors only with `DEBUG_MODE=true`. Optional data (cafés, reviews) fails quietly. |
| **Accounts** | Sign in with Google (verified server-side) or **Continue in Demo Mode**. Planning asks to sign in and then carries on with the same form. *My trips* (upcoming, past, saved) and *Profile* (email, travel and notification preferences). |

## Architecture

```
React + Vite UI ──► FastAPI ──► MissionEngine ──► ItineraryEngine ─► ScoringEngine ─► RiskEngine ─► Explanation
                                     │
                         TravelDataProvider ── SerpApiProvider ──► SerpApiClient (cache · retry · errors) ──► serpapi.com
                                     └──────── DemoProvider (DEMO_MODE only)
                         PostgreSQL / SQLite (missions, options, itineraries, recommendations, cache) · Redis (optional)
```

SerpApi is the live-data layer; our backend is the decision engine; AI only explains. Details in
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Tech stack

**Backend** Python 3.12+ · FastAPI · Pydantic v2 · SQLAlchemy 2 · PostgreSQL (SQLite for dev) · httpx · Redis (optional) · Anthropic SDK (optional) · pytest
**Frontend** React 19 · Vite · TypeScript (strict) · Tailwind CSS v4 · Framer Motion · TanStack Query · React Router · Lucide · Leaflet/OpenStreetMap · Vitest

## SerpApi APIs used

| Engine | What it contributes |
|--------|---------------------|
| `google_flights` | Flights for the mission day **and** the day before; prices, layovers, *often delayed by 30+ min* flags |
| `google_hotels` | Hotels near the venue: rates, ratings, coordinates, per-aspect review breakdowns |
| `google_maps` | Geocodes the venue; finds each shortlisted hotel's place id |
| `google_maps_directions` | Driving times + traffic ranges for every transfer; **transit mode** for live train/bus schedules (Indian Railways, city buses); the road-trip route |
| `google_local` | Mission-contextual nearby places |
| `google_maps_reviews` | Recent reviews and topics for the top hotels |
| `google` (Google Search) | The **transport options** answer box: train/bus fares and ticket sellers, matched onto Maps transit options |
| `google_travel_explore` | Experimental `/api/v1/explore` endpoint |

SerpApi has **no bus/train booking or seat-inventory API** (checked October 2026) — schedules come from Google Maps
transit and fares, where Google shows them, from the Google Search transport-options answer box.
A long-distance mission costs ~22 searches, a short one far fewer (flight searches are skipped); repeats are served
from cache (Redis or the database). See [docs/SERPAPI_INTEGRATION.md](docs/SERPAPI_INTEGRATION.md).

## Screenshots

| Landing | Analysis | Compare |
|--|--|--|
| ![](docs/screenshots/landing.png) | ![](docs/screenshots/analyzing.png) | ![](docs/screenshots/compare.png) |
| **No journey fits** | **Mobile** | |
| ![](docs/screenshots/no-fit.png) | ![](docs/screenshots/mobile.png) | |

## Setup

Prerequisites: Python 3.12+, Node 20.19+. Optional: Docker.

```bash
cp .env.example .env          # add SERPAPI_API_KEY, or set DEMO_MODE=true
```

### Environment variables

| Variable | Required | Notes |
|----------|----------|-------|
| `SERPAPI_API_KEY` | for live mode | Backend only — never sent to the browser |
| `DEMO_MODE` | no | `true` = labelled demo dataset (Indore → Bengaluru) |
| `DATABASE_URL` | no | Empty = SQLite in `backend/`. Docker Postgres from compose: `postgresql+psycopg://tripvision:tripvision@localhost:55432/tripvision` |
| `REDIS_URL` | no | Empty = database cache |
| `EMAIL_PROVIDER`, `SMTP_*`, `RESEND_API_KEY`, `EMAIL_FROM`, `APP_BASE_URL` | no | Email delivery; without them emails are in-app previews |
| `AI_PROVIDER` | no | `euri` (OpenAI-compatible, euron.one) or `anthropic` |
| `AI_API_KEY` | no | Key for the chosen provider; `AI_MODEL` (+ optional fallback `AI_MODEL_FAST`), `AI_BASE_URL` for euri |
| `FRONTEND_URL` | no | CORS origins (comma-separated, credentials allowed), default `http://localhost:5173` |
| `GOOGLE_CLIENT_ID` | for Google sign-in | OAuth **Web** client ID (public by design; served by `/api/v1/auth/config`). Empty = Demo Mode only |
| `GOOGLE_CLIENT_SECRET` | no | Not used by the ID-token flow; if set it stays server-side |
| `SESSION_SECRET` | **yes in production** | Long random string signing the session cookie. Empty = random per restart (dev only) |
| `SESSION_TTL_HOURS`, `SESSION_COOKIE_SECURE` | no | Session length (default 14 days); Secure cookies auto-on for https |
| `AUTH_REQUIRED` | no | `true` (default) = planning needs a Google or demo session |
| `DEMO_LOGIN_ENABLED` | no | `true` (default) = offer *Continue in Demo Mode* |
| `DEBUG_MODE` | no | `true` = developer diagnostics (request counts, timings, cache hits, raw errors, request IDs). Keep `false` for users |
| `MAX_PRACTICAL_AIRPORT_TRANSFER_MINUTES` | no | Default 180 — farther airports are never used for flight + transfer |
| `LOW_PRACTICALITY_AIRPORT_TRANSFER_MINUTES` | no | Default 90 — flight journeys above this are marked low practicality |
| `MIN_FLIGHT_DISTANCE_KM` | no | Default 200 — shorter trips skip flight searches |
| `AIRPORT_CHECKIN_MINUTES`, `OPTIONAL_TIMEOUT_SECONDS` | no | Defaults 75 and 8 |
| `SCORING_WEIGHTS` | no | JSON override of the default weight profile |

### Google sign-in setup

1. [Google Cloud Console](https://console.cloud.google.com/) → create/select a project → **APIs & Services → OAuth
   consent screen**: External, app name *TripMission*, support email, scopes `openid`, `email`, `profile`; add test
   users while the app is in *Testing*.
2. **Credentials → Create credentials → OAuth client ID → Web application.**
   *Authorized JavaScript origins*: `http://localhost:5173` (dev), `http://localhost:8080` (Docker) and your
   production origin. No redirect URI is needed — the Google Identity Services button returns an ID token.
3. Put the client ID in `.env` as `GOOGLE_CLIENT_ID=…apps.googleusercontent.com`, set a long random
   `SESSION_SECRET` (`python -c "import secrets;print(secrets.token_urlsafe(48))"`), and make sure `FRONTEND_URL`
   lists the same origins. Restart the backend. `/api/v1/health` shows `"google_auth": true`.
4. The backend verifies every token (signature via Google's keys, audience, issuer, expiry, verified email) before
   creating a session. The client secret is never needed or exposed.

### Email setup

Without configuration, emails are generated as in-app previews (nothing is sent). To send real email:

* **Gmail SMTP** — enable 2-Step Verification, create an **App password** (Google Account → Security → App
  passwords), then: `EMAIL_PROVIDER=smtp`, `SMTP_HOST=smtp.gmail.com`, `SMTP_PORT=587`, `SMTP_USE_TLS=true`,
  `SMTP_USERNAME=you@gmail.com`, `SMTP_PASSWORD=<16-char app password>`, `SMTP_FROM_EMAIL=you@gmail.com`.
* **Resend** — verify a sending domain, then `EMAIL_PROVIDER=resend`, `RESEND_API_KEY=…`,
  `EMAIL_FROM="TripMission <trips@yourdomain>"`.
* Set `APP_BASE_URL` to the public frontend URL so "View my journey" links work. `/api/v1/health` reports the
  active `email_delivery`. A failed email never fails a mission or a save.

### Run the backend

Optional — PostgreSQL + Redis in Docker for a local backend (Postgres is published on **55432** so it never clashes with a locally installed PostgreSQL on 5432/5433):

```bash
docker compose up -d postgres redis
```

```bash
cd backend
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt          # macOS/Linux: .venv/bin/pip
.venv/Scripts/python -m uvicorn app.main:app --reload --port 8000
```
API docs: http://localhost:8000/api/docs · health: http://localhost:8000/api/v1/health

### Run the frontend

```bash
cd frontend
npm install
npm run dev            # http://localhost:5173 — proxies /api to :8000
```

### Run with Docker (PostgreSQL + Redis)

```bash
docker compose up --build      # UI http://localhost:8080 · API http://localhost:8000
```

## Tests

```bash
cd backend  && .venv/Scripts/python -m pytest -q     # 155 tests, mocked SerpApi — never calls the real API
cd frontend && npm test                              # 16 component/unit tests
cd frontend && npm run build                         # strict type-check + production build
```
Backend tests also run against PostgreSQL: `TEST_DATABASE_URL=postgresql+psycopg://... pytest`.
Responsive + E2E QA: `node frontend/scripts/responsive-qa.mjs <outDir>` — sign-in gate → Demo Mode → Indore →
Ujjain (Mahakal Mandir) → every page at 320–1920 px, failing on horizontal overflow or developer text.
Visual QA: `node frontend/scripts/screenshots.mjs <outDir>` (drives the system Edge/Chrome).

## Demo mode

Two ways in, same labelled dataset:

* **Continue in Demo Mode** (sign-in modal) — no Google account needed; that session's missions always use demo
  data, even when the server has a live key. Ideal for judges.
* **`DEMO_MODE=true`** — the whole server uses demo data.

Demo scenarios: Indore → Bengaluru (interview at Manyata Tech Park) and Indore → Ujjain (Mahakal Mandir, the
airport-less case). It is clearly labelled in the navbar, analysis screen and results, and is **never mixed with
live data**. Hotel, café and review content in it is fictional. Other routes return a clear
`demo_route_unsupported` message. Without a key and with demo mode off, the API returns `setup_required` —
there is no silent fallback to fake data.

## Deployment

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md). Any container host works; use managed PostgreSQL/Redis and inject
secrets from the platform's secret store.

## Documentation

[Product requirements](docs/PRODUCT_REQUIREMENTS.md) · [HLD](docs/HLD.md) · [LLD](docs/LLD.md) ·
[Architecture](docs/ARCHITECTURE.md) · [Database](docs/DATABASE.md) · [API](docs/API_SPECIFICATION.md) ·
[SerpApi integration](docs/SERPAPI_INTEGRATION.md) · [Scoring](docs/SCORING_ENGINE.md) · [Risk](docs/RISK_ENGINE.md) ·
[UI/UX](docs/UI_UX.md) · [Testing](docs/TESTING.md) · [Deployment](docs/DEPLOYMENT.md) · [Demo script](docs/DEMO_SCRIPT.md)

## Roadmap

Return and multi-city missions · live train fares and seat availability (IRCTC partner API) · intercity bus
operators · live flight/train running status for re-planning on the day ·
flexible-destination missions via Travel Explore · calendar import · shared missions · booking deep links.

## Hackathon

Hacktoberfest 2026 — **Travel & Local Discovery**: *help people decide where to go and how to get there
using current flights, hotels, maps, places, reviews, and destination data.* TripMission focuses on the
**decide**.
