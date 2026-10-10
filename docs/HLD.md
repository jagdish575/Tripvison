# TripMission — High-Level Design

## 1. Overall architecture

```
┌──────────────────────────┐        ┌──────────────────────────────────────────────────────────┐
│  React + Vite frontend   │  HTTP  │                    FastAPI backend                        │
│  (TypeScript, Tailwind)  │ ─────► │                                                          │
│                          │  JSON  │  api/ (routers) ─► services/mission_service               │
│  • Mission form          │        │                         │                                 │
│  • Analysis progress     │ ◄───── │                         ▼                                 │
│    (polls status)        │        │              engines/mission_engine  (orchestrator)       │
│  • Results / Compare     │        │      ┌──────────┬─────────┴──────┬────────────┐           │
└──────────────────────────┘        │      ▼          ▼                ▼            ▼           │
                                    │  itinerary   scoring          risk        explanation     │
                                    │   engine      engine          engine       service (AI)   │
                                    │      ▲                                                     │
                                    │      │ normalized models only                              │
                                    │  services/providers: TravelDataProvider                    │
                                    │      ├── SerpApiProvider ──► integrations/serpapi/*        │
                                    │      └── DemoProvider    ──► demo/dataset (DEMO_MODE only) │
                                    │                                                          │
                                    │  core/cache (Redis │ DB │ memory) ── SerpApi responses    │
                                    │  repositories ── SQLAlchemy ── PostgreSQL (SQLite in dev) │
                                    └──────────────────────────────────────────────────────────┘
                                                         │ HTTPS (key server-side only)
                                                         ▼
                                                     serpapi.com
```

## 2. Frontend

* SPA built with React 18, Vite, TypeScript, Tailwind CSS v4, Framer Motion, Lucide icons, TanStack Query, React Router, Leaflet with OpenStreetMap tiles (map, lazy-loaded).
* Talks only to our backend (`/api/v1/*`). It never sees the SerpApi or AI keys.
* Routes: `/`, `/plan`, `/analyzing/:missionId`, `/results/:missionId`, `/compare/:missionId`, `/about`.

## 3. Backend

* FastAPI (async) with Pydantic v2 schemas.
* `POST /missions/analyze` validates the mission, persists it, and starts the analysis as a background task. The client polls `GET /missions/{id}` for stage-level progress. This keeps HTTP requests short and lets the UI show *real* progress rather than a fake spinner.
* All provider-specific data shapes stay inside `integrations/serpapi/`. Everything above that layer works with normalized models (`NormalizedFlight`, `NormalizedHotel`, `NormalizedRoute`, `NormalizedPlace`, `NormalizedReview`).

## 4. Database

* PostgreSQL in Docker/production; SQLite by default for zero-setup local development (same SQLAlchemy models).
* Stores missions, preferences, candidate flights/hotels, places, reviews, scored itineraries, recommendations and the SerpApi response cache. See `DATABASE.md`.

## 5. SerpApi layer

* One `SerpApiClient` (httpx async) handles auth, timeouts, retries with exponential backoff, 429 handling, structured errors, call tracking and caching.
* One module per Google surface: `flights.py`, `hotels.py`, `maps.py` (geocoding + directions), `local.py`, `reviews.py`, `travel.py` (Travel Explore, experimental).
* Each module = request builder + response normalizer. See `SERPAPI_INTEGRATION.md`.

## 6. AI service

* Optional. Enabled when `AI_API_KEY` is set. `AI_PROVIDER=euri` uses EURI's OpenAI-compatible chat completions (with an optional fallback model); `anthropic` uses the Anthropic Messages API.
* Input: a JSON *fact sheet* derived from the scored recommendation. Output: 2–4 sentence explanation.
* Guardrail: every number in the AI text must appear in the fact sheet, otherwise the text is discarded and the deterministic rule-based explanation is shown. The UI labels which source produced the text.

## 7. Scoring engine

Deterministic, pure functions. Seven components, weighted, renormalized when a component does not
apply (e.g. no hotel). Weights adapt to mission type (time-critical vs leisure) and can be overridden
with `SCORING_WEIGHTS`. See `SCORING_ENGINE.md`.

## 8. Risk engine

Independent from the score: it looks for *ways the journey can fail* (thin buffer, connections,
delay-prone flights, long transfers, far hotel, budget overrun, review warnings, missing data) and
returns `LOW | MEDIUM | HIGH`, a 0–100 risk score, factors and mitigations. See `RISK_ENGINE.md`.

## 9. Request flow (analyze)

```
POST /api/v1/missions/analyze
  └─ validate (Pydantic) → rate-limit → persist Mission(status=queued) → 202 {mission_id}
     background:
       1 resolve      airports (static IATA reference) + venue geocode (Google Maps)
       2 flights      Google Flights × {mission day, day before}           (parallel)
       3 arrival      filter by stops & physical arrival feasibility; shortlist top N per strategy
       4 hotels       Google Hotels × {night before, night of}             (parallel, only if needed)
                      distance to venue (haversine) → shortlist top K
       5 ground       Google Maps Directions for airport→venue, airport→hotel, hotel→venue (parallel)
       6 scoring      build itineraries (flight × hotel × legs) → score → risk → categories
       7 reviews      Google Maps → data_id → Google Maps Reviews for top hotels (≤2)
       8 places       Google Local for 3 mission-contextual categories near the venue
       9 explain      AI (fact-checked) or rules
      10 persist      itineraries, recommendations, result snapshot → status=complete
GET /api/v1/missions/{id}  (polled)  → status + progress
GET /api/v1/missions/{id}/recommendations → full result
```

## 10. Data flow and API-call budget

The funnel keeps SerpApi usage low (typically 12–18 calls for a fresh mission, 0 for a repeated one):

```
~100 flights (2 searches) → hard filters → top 4 per strategy
~40 hotels  (≤2 searches) → rating/distance pre-score → top 3 per stay
directions only for shortlisted hotels (≤7 calls)
→ ≤ 24 complete itineraries scored → top 3 → reviews for ≤ 2 hotels
```

## 11. Deployment architecture

`docker-compose.yml` runs `postgres`, `redis`, `backend` (uvicorn) and `frontend` (static build served by
nginx, proxying `/api` to the backend). Any container host (Render, Railway, Fly.io, a VM) can run the
same images. See `DEPLOYMENT.md`.

## 12. Multi-modal travel (v2)

TripMission compares **flight, train, bus, public transport and road trips** as complete journeys.

```
analyze
  ├─ Google Flights × {day, day before}         ─┐
  ├─ Google Maps Directions (transit, arrive_by) ├─ in parallel   (trains / buses / metro)
  └─ Google Maps Directions (driving, city→venue)┘               (road trip)
  → classify by arrival (same day / night before) → shortlist per mode
  → hotels for the needed stays → hotel↔venue directions
  → build itineraries per mode → total trip cost → score (priority weights) → risk
  → categories: Best overall · Cheapest · Fastest · Safest · Best value
  → mode summaries (incl. honest "not available" reasons) → trade-off sentence → explanation
```

* **Trains/buses:** Google Maps transit returns real schedules (Indian Railways train numbers, stations, times,
  city buses for the last mile) but usually **no fares**. In parallel, Google Search's transport-options answer box
  is queried; when one of its routes clearly matches a Maps option (same service numbers, or same mode/changes and
  departure within 10 min) its fare replaces the estimate and is labelled "Fare shown by Google Search". Otherwise
  fares stay ESTIMATED. Nothing is a booking.
* **Intercity buses** appear only where Google Maps has schedules; otherwise the Bus card says so.
* **Road trip:** live road route; one-way outstation-cab fare estimated; drives over 16 h are not offered.

## 13. Data confidence

Every cost line and schedule carries a source: `live` (from a search just now), `estimated` (documented model),
`user_provided` (e.g. a custom food budget), `calculated` (derived from live data, e.g. totals, nightly × nights).
Each itinerary has `confidence`: high (live price + live schedule), medium (live schedule, estimated fare), low.

## 14. Notifications

`EmailService` (SMTP / Resend / Preview providers) is independent of the engine. `NotificationService` handles
opt-in, the trip summary on completion, reminders (in-process loop every 5 min, 24 h before departure) and
change alerts after a re-check. Failed emails never fail a mission. See LLD §7.


## 15. Door-to-door routing — locations, hubs and route intelligence (v3)

TripMission plans **door → venue**, not airport → airport. Two services run before any search is spent:

```
origin / destination text
  → LocationResolutionService      "can we resolve this place?" — gazetteer → airport table → live geocoding
      ResolvedLocation { city, country, lat/lng, has_airport, airports[], nearby_airports[] (with road transfer) }
venue text → geocoded near the destination (the venue is the journey's endpoint; city centre only as a fallback)
  → RouteIntelligenceService.plan(origin, destination, venue, modes)
      distance & road estimate · origin/destination airport (own or nearest practical) · flight searched/skipped
      · low practicality · road search worth it? · friendly notices
  → MissionEngine searches only the modes that make sense, in parallel
```

* A city **without an airport is valid**. If flights are evaluated, the nearest airport whose road transfer to
  the *venue* is within `MAX_PRACTICAL_AIRPORT_TRANSFER_MINUTES` (180) is used and the transfer is added to the
  journey; above `LOW_PRACTICALITY_AIRPORT_TRANSFER_MINUTES` (90) the flight is marked **low practicality**.
* Flights are **skipped** (no search spent) when the trip is shorter than `MIN_FLIGHT_DISTANCE_KM` (200), when
  both ends share the nearest airport, or when no practical airport exists. Train, bus and road are always compared
  where they make sense; if every requested mode is impractical, practical ones are added and the user is told.
* Missing airports are **routing decisions shown as calm notices**, never validation errors — e.g. *"Ujjain doesn't
  have a commercial airport. We found Indore Airport as the nearest practical airport and added the road transfer
  to your journey."*
* Every option's time and cost are **door to door**: home → hub transfer, check-in assumption, main leg, hub →
  venue transfer (and hotel legs), plus hotel and food — with `budget_remaining` against the user's budget.
* Nothing is city-specific: coordinates (`places_reference.py`, `airports.py`) plus configurable thresholds.

## 16. Authentication, demo mode and accounts (v3)

```
Browser ──(Google Identity Services button)──► ID token
        ──POST /auth/google {credential}──► backend verifies with Google JWKS (aud = GOOGLE_CLIENT_ID, iss, exp,
                                            email_verified) → upsert users → HS256 session JWT in HttpOnly cookie
        ──POST /auth/demo──► anonymous is_demo user → same cookie; missions use the labelled demo dataset only
```

* No Google secret, SerpApi key or SMTP credential ever reaches the browser; `/auth/config` serves only the public
  client ID. `GOOGLE_CLIENT_SECRET` is not needed by the ID-token flow and is never exposed.
* Landing, *How it works* and *How we decide* are public. **Plan a mission / Find my journey** open a sign-in modal
  (Google or Demo); after sign-in the pending action resumes with the same form data (kept in `sessionStorage`).
* `/trips` and `/profile` are protected pages; every mission read is owner-only (404 for others, 401 anonymous).
* CORS is an explicit allow-list (`FRONTEND_URL`) with credentials; POST/PUT/DELETE from other origins are
  rejected (CSRF defence in depth on top of `SameSite=Lax`).

## 17. Failure policy, performance and DEBUG_MODE (v3)

| Class | Calls | Timeout | On failure |
|-------|-------|---------|-----------|
| Critical | flights, transit schedules, road route, hotels (when required) | `SERPAPI_TIMEOUT_SECONDS` + retries | that mode shows a friendly reason; the mission fails only if **no** mode works |
| Optional | places (cafés, restaurants…), hotel reviews, train/bus fare lookup | `OPTIONAL_TIMEOUT_SECONDS` (8 s) | silently degraded: "Some local recommendations are temporarily unavailable." or nothing at all |

* Independent searches run concurrently (`asyncio.gather`) under a process-wide semaphore; local places start as
  soon as the venue is known and run alongside everything else.
* Staged funnel: all flights → feasible → shortlist → hotels only for the stays still needed → directions only
  for shortlisted hotels → reviews only for the top hotels → places only for the destination venue.
* Users see product-language progress ("Finding practical routes", "Comparing hotels"…), a collapsed **How we
  decided** panel, and no request counts, provider names in errors, HTTP codes or request IDs.
* `DEBUG_MODE=true` adds a *Developer diagnostics* panel (per-call engine, purpose, cache hit, timing, raw
  provider error codes) and `request_id` in error bodies.
