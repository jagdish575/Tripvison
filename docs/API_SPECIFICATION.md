# TripMission — API Specification

Base URL: `/api/v1`. All responses are JSON. Errors use one envelope:

```json
{ "error": { "code": "unknown_location", "message": "We couldn't find \"Atlantis\". Check the spelling or try the nearest town or city.", "details": { "field": "destination" } } }
```

Locations are validated as "can we resolve this place?", never "does it have an airport?" — `Ujjain` is valid and
routes through the nearest practical airport/station. Error messages never contain provider names, HTTP details,
exception text or request IDs. `request_id` is added to the envelope **only** when `DEBUG_MODE=true`
(the `X-Request-ID` response header is always present for support).

**Authentication.** The session is an HttpOnly, `SameSite=Lax` cookie (`tm_session`, HS256, `SESSION_TTL_HOURS`).
Send requests with `credentials: "include"`. State-changing requests from a browser must come from an origin in
`FRONTEND_URL` (else `403 forbidden_origin`). Endpoints marked 🔒 return `401 auth_required` without a session.

---

## GET /health
Service and configuration status (never returns secrets).
```json
{ "status": "ok", "version": "1.0.0", "demo_mode": false, "serpapi_configured": true,
  "ai_configured": true, "database": "postgresql", "cache": "redis" }
```

## GET /airports?q=bang
Airport/city autocomplete from the static IATA reference.
```json
{ "results": [ { "code": "BLR", "city": "Bengaluru", "name": "Kempegowda International Airport", "country": "IN" } ] }
```

## POST /missions/analyze  → 202
Creates a mission and starts the analysis in the background. Rate limited (12/min per client IP).

Request:
```json
{
  "origin": "Indore", "destination": "Bangalore", "venue": "Manyata Tech Park",
  "mission_type": "interview", "travel_date": "2026-10-09", "arrival_deadline": "10:00",
  "travelers": 1, "budget": 10000, "currency": "INR",
  "min_buffer_minutes": 60, "max_ground_minutes": 90,
  "hotel_required": true, "min_hotel_rating": 3.5, "max_stops": 1,
  "allow_previous_day": true, "preferences": ["avoid_early_departure"]
}
```
Validation: `travel_date` today…+330 days; `travelers` 1–9; `budget` > 0; `min_buffer_minutes` 0–240;
`max_ground_minutes` 15–300; `min_hotel_rating` 0–5; `max_stops` 0–2; preferences from the enum
`prefer_direct | avoid_early_departure | night_before_preferred | same_day_only | breakfast_included | free_cancellation`.

Response:
```json
{ "mission_id": "8f1d…", "status": "queued", "mode": "live" }
```
Errors: `422 validation_error | unknown_location | same_origin_destination | demo_route_unsupported`,
`503 setup_required`, `429 rate_limited`, `413 payload_too_large`.

## GET /missions/{mission_id}
Status + progress (polled by the analysis screen) and the input.
```json
{
  "mission_id": "8f1d…", "status": "running", "mode": "live",
  "progress": { "stage": "hotels", "completed": ["resolve", "flights", "arrival"],
                "counts": { "flights": 47, "flights_feasible": 9 }, "message": "Finding hotels near Manyata Tech Park" },
  "input": { … MissionRequest … },
  "error": null
}
```
Stages, in order: `resolve, flights, arrival, hotels, ground, scoring, reviews, places, explain`.
When `status = failed`, `error = {code, message}`.

## GET /missions/{mission_id}/recommendations
Full `MissionResult`. `409 not_ready` while running, `404 not_found` for unknown ids.

```json
{
  "mission_id": "…", "status": "complete | partial | no_options", "mode": "live",
  "mission": { "origin": {"code":"IDR","city":"Indore",…}, "destination": {…}, "venue": {"name":"…","location":{"lat":13.04,"lng":77.62}},
               "travel_date": "2026-10-09", "arrival_deadline": "10:00", "budget": 10000, … },
  "categories": { "recommended": "nb-6E6311-h1", "cheapest": "…", "fastest": "…", "safest": "…" },
  "itineraries": [ {
      "id": "nb-6E6311-h1", "strategy": "night_before",
      "flight": { "airline": "IndiGo", "flight_numbers": ["6E 6311"], "departure_time": "2026-10-08T18:40", … },
      "hotel":  { "name": "…", "rating": 4.3, "reviews": 2180, "price_per_night": 3400, "distance_km": 1.3, … },
      "legs":   [ { "kind": "ground", "from": "BLR", "to": "…", "duration_minutes": 46, "distance_km": 27.9, "mode": "Taxi", "estimated": false } ],
      "timeline": [ { "time": "2026-10-08T18:40", "title": "Depart Indore (IDR)", "kind": "depart", "detail": "IndiGo 6E 6311" }, … ],
      "cost": { "flight": 4350, "hotel": 3400, "ground": 812, "total": 8562, "currency": "INR", "ground_estimated": true },
      "arrival": { "venue_arrival": "2026-10-09T08:45", "deadline": "2026-10-09T10:00", "buffer_minutes": 75, "required_buffer_minutes": 60, "leave_hotel_at": "2026-10-09T08:31" },
      "scores": { "overall": 91, "arrival": 94, "budget": 87, "ground": 90, "location": 100, "hotel": 72, "duration": 88, "review": 85, "weights": {…}, "factors": [ … ] },
      "risk": { "level": "LOW", "score": 8, "factors": [ … ], "strengths": [ … ], "recommendations": [ … ] },
      "constraints": { "within_budget": true, "buffer_ok": true, "ground_ok": true, "rating_ok": true, "all_ok": true },
      "tags": ["recommended", "safest"]
  } ],
  "suggestions": [ { "kind": "increase_budget", "title": "Increase budget to ₹11,400", "detail": "…" } ],
  "review_insights": { "<hotel_id>": { "strengths": [ {"aspect":"Location","mentions":12} ], "concerns": [ … ], "quotes": [ … ], "source": "google_maps_reviews", "review_count": 10 } },
  "places": [ { "category": "cafe", "label": "Cafés to wait in", "items": [ … ] } ],
  "explanation": { "text": "…", "source": "ai | rules", "model": "claude-opus-5-5" },
  "data_sources": { "calls": [ {"api": "google_flights", "cached": false, "ok": true, "ms": 1820 } ], "live_calls": 14, "cache_hits": 2, "fetched_at": "…" },
  "warnings": [ "Reviews could not be loaded for one hotel." ]
}
```

---

## Direct search endpoints
Thin, cached wrappers over the provider used by the engine — useful for debugging and judges.
All return normalized models, never raw SerpApi JSON.

| Endpoint | Query params | Returns |
|----------|--------------|---------|
| `GET /flights/search` | `origin`, `destination`, `date`, `travelers=1`, `max_stops=2`, `currency=INR` | `{ "results": [NormalizedFlight] }` |
| `GET /hotels/search` | `q`, `check_in`, `check_out`, `travelers=1`, `min_rating`, `currency=INR` | `{ "results": [NormalizedHotel] }` |
| `GET /places/search` | `q`, `near` (free text) | `{ "results": [NormalizedPlace] }` |
| `GET /directions` | `from`, `to` (free text or `lat,lng`), `mode=driving` | `{ "route": NormalizedRoute }` |
| `GET /reviews` | `place` (name + city) | `{ "place": NormalizedPlace, "reviews": [NormalizedReview], "topics": [...] }` |
| `GET /explore` | `origin`, `date` | `{ "results": [ExploreDestination] }` *(experimental)* |

These endpoints are rate limited (30/min per IP) and follow the same live/demo separation.

---

## v2 additions

### POST /missions/analyze — new optional fields
```json
{ "priority": "balanced | save_money | save_time | avoid_risk",
  "modes": ["flight", "train", "bus", "ground"],
  "stay_nights": 1, "food_per_day": 500,
  "accessibility": ["wheelchair", "elevator", "accessible_hotel", "accessible_transport"],
  "notifications": { "email": "you@example.com", "trip_summary": true, "reminder": true, "changes": true } }
```

### Result additions (`GET /missions/{id}/recommendations`)
* `itineraries[].mode`, `.main` (mode-independent leg), `.transit`, `.confidence`, `.accessibility`
* `itineraries[].cost.items[]` — `{key, label, amount, source: live|estimated|user_provided|calculated, detail}`,
  plus `food`, `hotel_nights`, `hotel_per_night`, `ticket_source`, `budget`, `budget_remaining`
* `itineraries[].scores` — `convenience`, `value`, `priority`
* `categories.best_value`
* `modes[]` — `{mode, available, best_id, options, reason, confidence, schedule_source, fare_source}`
* `tradeoff` — `{cheapest_id, fastest_id, extra_cost, time_saved_minutes, sentence}`
* `deltas[id]` — `{money_saved_vs_fastest, time_saved_vs_cheapest_minutes}`
* `suggestions[].unlocks` — e.g. "Train becomes available"

### GET /templates
Mission templates: `{templates: [{mission_type, label, priority, min_buffer_minutes, max_stops, hotel_required, risk_tolerance, highlights}]}`

### POST /missions/{id}/notifications
Body `NotificationPrefs`. Creates/updates the subscription and sends the trip summary.
```json
{ "subscription": {"email": "...", "trip_summary": true, "reminder": true, "changes": true, "departure_at": "2026-10-09T19:50:00"},
  "summary": { "status": "sent | preview | failed | pending", "message": "...", "message_id": "...", "preview_url": "/api/v1/emails/<id>" } }
```
A failed send returns `status: "failed"` with *"Your journey was created, but we couldn't send the email."*

### GET /missions/{id}/notifications
Subscriptions, last 20 emails (`kind`, `status`, `preview_url`) and the active `delivery` provider.

### POST /missions/{id}/notifications/reminder
Sends the reminder now (testing/demo). The scheduler sends it automatically 24 h before departure.

### POST /missions/{id}/recheck
Re-runs the analysis with fresh data, stores the new result, compares it with what subscribers were told and
sends a change alert only if the change is meaningful. Body `{ "simulate_delay_minutes": 45 }` is **DEMO_MODE only**
(`422 demo_only` otherwise).
```json
{ "report": {"meaningful": true, "journey_unavailable": false,
             "changes": [{"field": "venue_arrival", "label": "Arrival at the venue", "before": "...", "after": "...", "meaningful": true}]},
  "alerts": [{"email": "...", "meaningful": true, "alert": {"status": "preview", "preview_url": "..."}}], "simulated": false }
```

### GET /emails/{message_id}
The stored HTML email (preview), served with a restrictive Content-Security-Policy.

### GET /health — additions
`ai_provider`, `email_delivery` (`smtp | resend | preview`).


## v3 additions — authentication, accounts, routing

### GET /auth/config
Public sign-in configuration. The Google **client ID** is public by design; the secret is never returned.
```json
{ "google_client_id": "123….apps.googleusercontent.com", "google_enabled": true, "demo_enabled": true, "auth_required": true }
```

### GET /auth/me
`{ "user": { "id": "…", "name": "Asha", "email": "asha@example.com", "picture": "https://…", "is_demo": false } }` or `{ "user": null }`.

### POST /auth/google
Body `{ "credential": "<Google Identity Services ID token>" }`. The backend verifies signature (Google JWKS), audience
(`GOOGLE_CLIENT_ID`), issuer, expiry and `email_verified`, upserts the user and sets the session cookie.
Errors: `401 auth_required` (invalid token / unverified email), `503 google_auth_unavailable` when `GOOGLE_CLIENT_ID` isn't set. Rate limited (20/min per IP).

### POST /auth/demo
Starts an anonymous demo session (`is_demo: true`). Its missions always use the labelled demo dataset — never live
searches. `403 demo_disabled` when `DEMO_LOGIN_ENABLED=false`.

### POST /auth/logout
Clears the session cookie.

### POST /missions/analyze 🔒
Requires a session unless `AUTH_REQUIRED=false`. The mission is owned by the signed-in user.

### GET /missions/{id} · GET /missions/{id}/recommendations
A mission owned by a user is visible **only to that user**: another signed-in user gets `404 not_found` (not 403,
so mission IDs can't be probed) and a request without a session gets `401 auth_required`. Result additions:

* `route` — the route-intelligence decision: `distance_km`, `road_km`, `origin_airport` / `destination_airport`
  (`code`, `name`, `transfer_minutes`, `practical`), `destination_has_airport`, `flight` (`searched` | `skipped`),
  `flight_reason`, `flight_practicality` (`high` | `low`), `modes_evaluated`, `railway_stations`, `bus_points`,
  `notices[]` (`kind`: `airport_fallback`, `no_airport`, `short_distance`, `flight_skipped`, `origin_transfer`,
  `low_practicality`, `modes_added`; `message` is user-ready text).
* `methodology[]` — "How we decided": `{ key, label, kind: live|calculated|estimated|demo, detail }`.
* Itinerary `main.data_source` / `main.fare_label` (`Fare` or `Estimated fare`), `cost.items[].source`
  (`live` | `estimated` | `calculated` | `user_provided`), `practicality`, `confidence`.
* `warnings[]` — friendly degraded-data messages only (e.g. "Some local recommendations are temporarily unavailable.").
* `data_sources.calls` and `diagnostics` (request count, timings, cache hits, raw provider errors) are present
  **only when `DEBUG_MODE=true`**.

### GET /locations?q=ujj
Suggestions for From/To: cities with or without an airport.
```json
{ "results": [ { "label": "Ujjain", "code": null, "detail": "No airport · we'll route via the nearest hub", "has_airport": false } ] }
```

### GET /me/trips 🔒
All missions of the signed-in user, newest first:
`{ "trips": [ { "mission_id", "status", "mode", "origin", "destination", "venue", "travel_date", "arrival_deadline",
"budget", "currency", "upcoming", "saved", "headline", "recommended": { "mode", "total_cost", "score", "risk", "buffer_minutes" } } ] }`.

### POST /missions/{id}/save 🔒 · DELETE /missions/{id}/save 🔒
Saves/unsaves a finished journey (`409 not_ready` if unfinished). Saving subscribes the user's email to the alerts
enabled in their email preferences; an email failure never fails the save (`"email": {"status": "failed"}`).

### GET /me/preferences 🔒 · PUT /me/preferences 🔒
```json
{ "preferences": {
    "email": { "trip_summary": true, "departure_reminder": true, "journey_changes": true, "price_changes": false },
    "notifications": { "enabled": true },
    "travel": { "home_city": "Indore", "priority": "balanced", "modes": ["flight","train","bus","ground"], "buffer_minutes": 60 } } }
```
`PUT` accepts any subset of `email`, `notifications`, `travel` and returns the stored preferences.

### GET /health — v3 additions
`debug_mode`, `google_auth` (Google sign-in configured), `ready` (live data or demo available), `email_delivery`.
