# TripMission — Low-Level Design

## 1. Backend module map

```
backend/app/
├── main.py                     FastAPI app factory, middleware, exception handlers, lifespan
├── core/
│   ├── config.py               Settings (pydantic-settings, .env)
│   ├── logging.py              JSON log formatter + secret redaction filter
│   ├── errors.py               AppError hierarchy → safe JSON error responses
│   ├── database.py             SQLAlchemy engine/session, Base, init_db()
│   ├── cache.py                CacheBackend: MemoryCache | DatabaseCache | RedisCache
│   └── rate_limit.py           In-memory sliding-window limiter for expensive endpoints
├── models/                     SQLAlchemy ORM (see DATABASE.md)
├── schemas/
│   ├── mission.py              MissionRequest (input validation), MissionStatusOut
│   ├── travel.py               Normalized* models + GeoPoint
│   └── result.py               Itinerary, ScoreBreakdown, RiskAssessment, MissionResult …
├── integrations/serpapi/
│   ├── client.py               SerpApiClient, CallTracker, exceptions
│   ├── flights.py              build_flight_params / parse_flights
│   ├── hotels.py               build_hotel_params / parse_hotels
│   ├── maps.py                 geocode params/parse, directions params/parse
│   ├── local.py                local places params/parse
│   ├── reviews.py              maps reviews params/parse
│   └── travel.py               travel explore params/parse (experimental)
├── services/
│   ├── providers.py            TravelDataProvider protocol, SerpApiProvider, get_provider()
│   ├── airports.py             Static IATA reference data + resolver
│   ├── geo.py                  haversine, road-distance estimate
│   ├── review_insights.py      Aspect extraction from review data
│   ├── explanation.py          RuleExplainer, AIExplainer, number fact-check
│   └── mission_service.py      create/run/get missions, persistence of results
├── engines/
│   ├── mission_engine.py       MissionEngine — orchestrates the whole pipeline
│   ├── itinerary_engine.py     ItineraryEngine — builds legs, timeline, cost
│   ├── scoring_engine.py       ScoringEngine + ScoringConfig
│   └── risk_engine.py          RiskEngine
├── repositories/
│   └── mission_repository.py   MissionRepository — all DB access for missions
├── api/
│   ├── deps.py                 DB session + provider dependencies
│   └── routes/                 health, missions, search (flights/hotels/places/directions/reviews/explore), airports
├── demo/
│   ├── dataset.py              Deterministic interview-scenario dataset
│   └── provider.py             DemoProvider (implements TravelDataProvider)
└── utils/time.py               Time parsing/formatting helpers
```

## 2. Key classes

| Class | Responsibility |
|-------|----------------|
| `SerpApiClient` | `async search(engine, params, ttl)` → dict. Cache lookup, httpx call, retry/backoff, error mapping, call tracking. |
| `CallTracker` | Per-mission record of every provider call (`api`, `cached`, `ok`, `ms`, `error`) for the transparency panel. |
| `TravelDataProvider` (Protocol) | `search_flights`, `search_hotels`, `geocode`, `directions`, `search_places`, `hotel_reviews`, `explore`. |
| `SerpApiProvider` | Implements the protocol with the SerpApi modules. |
| `DemoProvider` | Implements the protocol from `demo/dataset.py`. Only constructed when `DEMO_MODE=true`. |
| `ItineraryEngine` | Builds an `Itinerary` from (flight, hotel?, routes): legs, timeline events, venue arrival, cost. |
| `ScoringEngine` | Pure scoring of one itinerary given its siblings (for the relative duration component). |
| `RiskEngine` | Pure risk assessment of one itinerary. |
| `MissionEngine` | Orchestrates provider calls, funnel shortlisting, building, scoring, categorisation, reviews, places, explanation; reports progress through a callback. |
| `MissionService` | Creates missions, runs the engine in the background, persists results, maps failures to user-facing errors. |
| `MissionRepository` | CRUD for `Mission` and child tables. |
| `Explainer` | `RuleExplainer` (always available) and `AIExplainer` (optional) with `fact_check()`. |

## 3. Pydantic schemas (abridged)

```python
class MissionRequest(BaseModel):
    origin: str                      # city or IATA, 2–80 chars
    destination: str
    venue: str | None                # "Manyata Tech Park"
    mission_type: MissionType        # interview|exam|business|conference|wedding|medical|vacation|family|other
    travel_date: date                # mission day (must be today or later, ≤ 330 days)
    arrival_deadline: time           # local time at destination
    travelers: int = 1               # 1–9
    budget: float                    # total for all travellers, > 0
    currency: str = "INR"
    min_buffer_minutes: int = 60     # 0–240
    max_ground_minutes: int = 90     # 15–300
    hotel_required: bool = True
    min_hotel_rating: float = 3.5    # 0–5
    max_stops: int = 1               # 0–2
    allow_previous_day: bool = True
    preferences: list[Preference] = []

class NormalizedFlight:  id, airline, airline_logo, flight_numbers[], departure_airport, arrival_airport,
                         departure_time, arrival_time, duration_minutes, stops, layovers[], price, currency,
                         often_delayed, segments[], booking_token
class NormalizedHotel:   id, name, rating, reviews, price_per_night, total_price, currency, location(GeoPoint),
                         address, amenities[], image, images[], hotel_class, free_cancellation,
                         review_breakdown[], link, check_in_time, distance_km (filled by engine)
class NormalizedRoute:   origin, destination, distance_km, duration_minutes, typical_max_minutes, mode, estimated
class NormalizedPlace:   id, name, category, rating, reviews, address, location, distance_km, hours, thumbnail, data_id
class NormalizedReview:  rating, text, date, author

class ScoreBreakdown:    overall, arrival, budget, ground, location, hotel, duration, review, weights, factors[]
class RiskAssessment:    level, score, factors[RiskFactor], strengths[], recommendations[]
class Itinerary:         id, strategy, flight, hotel, legs[], timeline[], cost, arrival, ground_minutes,
                         total_travel_minutes, scores, risk, constraints, tags[], highlights[]
class MissionResult:     mission, status, mode, categories, itineraries[], suggestions[], review_insights,
                         places[], explanation, data_sources, warnings[]
```

## 4. API endpoints

See `API_SPECIFICATION.md`. Routers live in `app/api/routes/` and contain no business logic.

## 5. Frontend architecture

```
frontend/src/
├── main.tsx / App.tsx            Router, QueryClient, layout
├── api/client.ts                 fetch wrapper → typed ApiError
├── api/missions.ts               analyzeMission, getMission, getRecommendations, getHealth, searchAirports
├── types/                        Mirrors backend result schemas
├── hooks/                        useMissionStatus (polling), useHealth, useReducedMotion helpers
├── layouts/AppLayout.tsx         Navbar + page transition outlet + Footer
├── pages/                        Landing, Plan, Analyzing, Results, Compare, About, NotFound
├── components/
│   ├── layout/                   Navbar, Footer, DemoBadge
│   ├── mission/                  MissionForm, HeroMissionBar, MissionTypeSelector, MissionBrief, Field primitives
│   ├── analysis/                 SearchProgress
│   ├── results/                  MissionSummaryBar, RecommendationCard, MissionScore, ScoreBreakdown,
│   │                             JourneyTimeline, RiskPanel, OptionSwitcher, FlightCard, HotelCard,
│   │                             ReviewInsights, LocalDiscovery, PlaceCard, ExplanationPanel,
│   │                             DataSources, ConstraintSuggestions, JourneyMap
│   ├── compare/                  ComparisonTable
│   └── ui/                       Button, Badge, RiskBadge, Skeleton, EmptyState, ErrorState, CountUp, Tabs
├── utils/format.ts               currency, minutes, time, dates
├── animations/motion.ts          Shared variants + durations (respect reduced motion)
└── styles/index.css              Tailwind v4 theme tokens
```

### State management
* Server state: TanStack Query (`['mission', id]` polled every 800 ms while running; results cached).
* Form state: local `useState` with a typed `MissionDraft`; landing → plan hand-off via `sessionStorage`.
* Selected itinerary on the results page: URL search param `?option=<id>` so a comparison link is shareable.

## 6. Error handling

Backend errors are raised as `AppError(code, message, status, details)` and serialised as
`{"error": {"code", "message", "details", "request_id"}}`. Unknown exceptions return a generic 500 with
the request id (details logged server-side, never returned).

| Code | Status | Trigger |
|------|--------|---------|
| `validation_error` | 422 | Pydantic validation / business validation (date in past) |
| `unknown_location` | 422 | Origin/destination cannot be mapped to an airport |
| `same_origin_destination` | 422 | Origin and destination resolve to the same airport |
| `setup_required` | 503 | Live mode without `SERPAPI_API_KEY` |
| `demo_route_unsupported` | 422 | Demo mode used with a route outside the demo dataset |
| `rate_limited` | 429 | Our own analyze rate limit |
| `upstream_rate_limited` | 503 | SerpApi 429 after retries |
| `upstream_quota_exhausted` | 503 | SerpApi account out of searches |
| `upstream_auth` | 503 | Invalid SerpApi key |
| `upstream_timeout` / `upstream_error` | 504 / 502 | Network or provider failure |
| `no_flights` | — | Result status `no_options` (not an HTTP error — the UI renders guidance) |
| `not_found` | 404 | Unknown mission id |
| `payload_too_large` | 413 | Body > 32 KB |

Failures inside optional stages (reviews, places, AI explanation) never fail the mission; they add a
`warning` and the UI shows a section-level empty/error state.

## 7. v2 modules (multi-modal, cost, email)

| Module | Responsibility |
|--------|----------------|
| `integrations/serpapi/maps.py` `parse_transit()` | Google Maps transit → `NormalizedTransit` (segments, operators, transfers). Rebuilds dates from clock-only times using the requested arrive-by time. |
| `engines/itinerary_engine.py` | `build()` (flight), `build_transit()` (train/bus/transit), `build_ground()` (road trip). Shared `_costs()` emits sourced `CostItem`s (ticket, ground, hotel × nights, food), `budget_remaining`, accessibility notes. |
| `engines/scoring_engine.py` | `ScoringConfig.profiles` = priority weight profiles; components arrival, budget (fit + relative), ground, location & stay, duration (log scale), review, convenience; `value` index for Best value. |
| `engines/risk_engine.py` | Mode-aware: flight connections/delay flags; train/bus changes, tight changes, punctuality without live running status; long drives. |
| `engines/mission_engine.py` | Parallel flight/transit/road search, `_classify_transit`, `_build_transit_and_ground`, `_mode_summaries`, `_tradeoff`, `_deltas`, mode-aware suggestions (`unlocks`). |
| `core/templates.py` | Mission templates (priority, buffer, stops, hotel, risk tolerance). |
| `services/email/providers.py` | `SmtpProvider`, `ResendProvider`, `PreviewProvider`, `get_email_provider()`. |
| `services/email/templates.py` | Responsive HTML + text for summary, reminder, change alert — values from stored snapshots only. |
| `services/email/changes.py` | `snapshot()`, `detect_changes()` with alert thresholds. |
| `services/email/service.py` | `EmailService.send_trip_summary / send_trip_reminder / send_trip_change_alert`; logs every email; never raises. |
| `services/notifications.py` | `NotificationService.subscribe / on_mission_complete / recheck / send_reminder / process_due_reminders`, `reminder_loop()`. |

New schemas: `NormalizedTransit`, `TransitSegment`, `MainLeg`, `CostItem`, `ModeSummary`, `Tradeoff`, `OptionDelta`,
`AccessibilityNote`, `NotificationPrefs`; `MissionRequest` gains `priority`, `modes`, `stay_nights`, `food_per_day`,
`accessibility`, `notifications`.

## 8. v3 modules — door-to-door routing, fares, accounts

### Backend

| Module | Responsibility |
|--------|----------------|
| `services/places_reference.py` | City-centre gazetteer (cities **and** airport-less towns: Ujjain, Mathura, Haridwar…). Stable geography, not inventory. |
| `services/location_resolution.py` | `LocationResolutionService.resolve(query, field)` → `ResolvedLocation`. Order: gazetteer → airport table (names, aliases, IATA, "Bangalore (BLR)") → live geocoding (`google_maps`). Attaches the city's own airport (within `OWN_AIRPORT_RADIUS_KM`) and up to 3 `nearby_airports` (`NearbyHub`: road km, `transfer_minutes`, `practical`). Unresolvable → `422 unknown_location` ("We couldn't find…"). Never fails for lack of an airport. |
| `services/route_intelligence.py` | `RouteIntelligenceService.plan()` → `RoutePlan`: distance, road estimate, origin/destination airport hubs (destination hub measured **to the venue**), `flight` searched/skipped + reason, `flight_practicality`, `ground_search`, `modes_evaluated`, `notices[]`. Pure function of coordinates + settings. |
| `services/geo.py` | `haversine_km`, `road_km_estimate` (×1.35 city / ×1.2 highway), `estimate_transfer_minutes`, `estimate_route()` (always flagged `estimated`). |
| `integrations/serpapi/transport.py` | Google Search transport-options answer box: `build_params()`, `parse_transport_options()` → `ReportedTransportRoute`, `parse_money()` (never guesses a currency). |
| `engines/mission_engine.py` | `match_reported_route()` / `attach_reported_fares()` (see below); `_reported_fares()` optional lookup; `_record_hubs()` collects railway stations / bus points from live transit; `_optional()` wraps optional calls with `OPTIONAL_TIMEOUT_SECONDS`; `_degrade(key, detail)` records a friendly message + debug-only detail. |
| `services/auth.py` | Google ID-token verification (PyJWT + Google JWKS, RS256, aud/iss/exp, `email_verified`), `upsert_google_user`, `create_demo_user`, HS256 session tokens (`iss=tripmission`), cookie helpers, dependencies `optional_user`, `require_user`, `mission_user`. |
| `api/routes/auth.py` | `/auth/config`, `/auth/me`, `/auth/google`, `/auth/demo`, `/auth/logout`. |
| `api/routes/me.py` | `/me/trips`, `/me/preferences` (GET/PUT), `/missions/{id}/save` (POST/DELETE; save auto-subscribes per email preferences). |
| `services/mission_service.py` | `check_access()` owner-only rule; `public_result()` strips `calls`, `live_calls`, `cache_hits`, `diagnostics` unless `DEBUG_MODE`. Demo users always get `DemoProvider`. |

**Fare matching** (`attach_reported_fares(options, routes, currency)`): for each Maps transit option without a fare,
take its long-distance services (train/bus segments ≥ 45 min). A reported route matches if its service-number set
equals the option's; if either side lacks numbers, it must have the same mode, the same number of changes and a first
departure within `FARE_MATCH_MINUTES` (10, midnight-aware). Only fares in the mission currency are attached;
`fare_source="google_search_transport_options"`, `fare_seller` = first listed seller. `ItineraryEngine.build_transit`
then labels the ticket `live`, adds local-connection estimates, and sets `data_source` / note accordingly.

**Door-to-door time** for a flight journey = origin → airport transfer + `AIRPORT_CHECKIN_MINUTES` + flight +
`AIRPORT_EXIT_MINUTES` + airport → venue (or → hotel, then hotel → venue next morning). Train/bus = Maps transit
door → venue (includes walking and city legs). Road = live drive origin → venue. `total_travel_minutes` and
`door_to_venue_minutes` are what the UI and scoring use — never the flight duration alone.

**Configuration** (`core/config.py`, all env-overridable): `MAX_PRACTICAL_AIRPORT_TRANSFER_MINUTES=180`,
`LOW_PRACTICALITY_AIRPORT_TRANSFER_MINUTES=90`, `MIN_FLIGHT_DISTANCE_KM=200`, `OWN_AIRPORT_RADIUS_KM=35`,
`AIRPORT_CHECKIN_MINUTES=75`, `OPTIONAL_TIMEOUT_SECONDS=8`, `DEBUG_MODE`, `AUTH_REQUIRED`, `DEMO_LOGIN_ENABLED`,
`SESSION_*`, `GOOGLE_CLIENT_ID/SECRET`.

### Frontend

| Module | Responsibility |
|--------|----------------|
| `auth/AuthContext.tsx` | `useAuth()`: `user`, `requireAuth(action, reason)` (runs now, or opens the modal and runs after sign-in), `signInThen` (session expired), `signOut` (clears cached trips/missions). Renders `LoginModal`. |
| `auth/RequireAuth.tsx` | Protected-page wrapper: skeleton while loading, inline sign-in panel when signed out. |
| `components/auth/LoginModal.tsx`, `GoogleButton.tsx` | Two-panel modal (travel visual + "Plan a real journey with TripMission"), Google Identity Services button (loaded only when configured), Continue in Demo Mode, privacy note; focus-trapped, Esc to close. |
| `components/layout/Navbar.tsx` | Sticky, compact. Desktop: logo · How it works · How we decide · My trips · Plan a mission · avatar menu (name, email, My trips, Saved missions, Email preferences, Settings, Sign out). Tablet: links row. Mobile: hamburger with animated panel. Demo badge. |
| `hooks/useMission.ts` `useStartMission()` | Saves the draft, gates on auth, resumes the same mission after sign-in; `auth_required` from the server re-opens the modal. |
| `components/mission/HeroMissionBar.tsx` | Quick mission bar; changing the destination clears a venue picked for another city. |
| `pages/TripsPage.tsx` | `/trips`: Upcoming · Past · Saved tabs; score, status, recommended mode, total cost, View journey. |
| `pages/ProfilePage.tsx` | `/profile`: Account, Email preferences, Travel preferences, Notifications, Sign out. |
| `components/results/DataSources.tsx` | "How we decided" (collapsed) + DEBUG-only diagnostics; `SoftNotices` for degraded data. |
| `components/results/RouteNotices.tsx` | "How we routed this trip": airport fallback, skipped flights, hubs discovered. |
