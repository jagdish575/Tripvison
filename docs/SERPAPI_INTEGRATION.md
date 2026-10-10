# TripMission — SerpApi Integration

SerpApi is TripMission's live-data infrastructure. Every request goes **from our backend** to
`https://serpapi.com/search.json`; the frontend never sees the key.

## 1. APIs used and why

| # | SerpApi engine | Used for | Calls per fresh mission |
|---|----------------|----------|-------------------------|
| 1 | `google_flights` | One-way flights for the mission day and the day before | 2 |
| 2 | `google_hotels` | Hotels near the venue for the night before / night of | 1–2 |
| 3 | `google_maps` (search) | Geocoding the venue; finding a hotel's `data_id` for reviews | 1 + ≤2 |
| 3b | `google_maps_directions` | Real driving time/distance: airport→venue, airport→hotel, hotel→venue | ≤ 7 |
| 4 | `google_local` | Mission-contextual nearby places (cafés, pharmacies, …) | ≤ 3 |
| 5 | `google_maps_reviews` | Recent reviews and topic keywords for shortlisted hotels | ≤ 2 |
| 6 | `google_travel_explore` | Experimental `/explore` endpoint (not in the main flow) | 0 |
| 7 | `google_maps_directions` (`travel_mode=3`) | Train and bus schedules door → venue (`prefer=`prefer=bus` or `prefer=train` / `prefer=bus`) | 1 per surface mode |
| 8 | `google` (Google Search) — `answer_box.type == "transport_options"` | Train/bus **fares** Google shows for the route, matched onto Maps transit options | 1 per surface mode (optional) |

Flight searches are skipped entirely for short trips (`MIN_FLIGHT_DISTANCE_KM`), when origin and destination share
an airport, or when no practical airport exists — see *Route intelligence* in `LLD.md`. That alone saves 2 of the
~22 searches on trips like Indore → Ujjain.

## 2. Request parameters

### Google Flights (`integrations/serpapi/flights.py`)
| Param | Value |
|-------|-------|
| `engine` | `google_flights` |
| `departure_id` / `arrival_id` | IATA codes resolved from the static airport reference |
| `outbound_date` | `YYYY-MM-DD` |
| `type` | `2` (one way) |
| `adults` | travellers |
| `stops` | `1` nonstop · `2` ≤1 stop · `3` ≤2 stops (from `max_stops`) |
| `currency`, `hl=en`, `gl=in` | |

Normalized from `best_flights[]` + `other_flights[]`: each item's `flights[]` segments,
`layovers[]`, `total_duration`, `price`, `often_delayed_by_over_30_min` (per segment — used by the risk engine),
`airline_logo`, `booking_token`.

### Google Hotels (`hotels.py`)
`engine=google_hotels`, `q="hotels near <venue>, <city>"`, `check_in_date`, `check_out_date`, `adults`,
`currency`, `gl`, `hl`, `rating` (7 = 3.5+, 8 = 4.0+, 9 = 4.5+ when `min_hotel_rating ≥ 3.5`).
Normalized from `properties[]`: `name`, `gps_coordinates`, `overall_rating`, `reviews`,
`rate_per_night.extracted_lowest`, `total_rate.extracted_lowest`, `amenities`, `images[0]`,
`extracted_hotel_class`, `reviews_breakdown[]` (positive/negative mentions per aspect), `free_cancellation`,
`link`, `property_token`. Items without coordinates are kept but marked `distance_known=false`.

### Google Maps search (`maps.py`)
`engine=google_maps`, `type=search`, `q=<venue, city>`. Uses `place_results` if present, otherwise the first
`local_results[]` item → `NormalizedPlace` with `gps_coordinates`, `address`, `data_id`.

### Google Maps Directions (`maps.py`)
`engine=google_maps_directions`, `start_coords="lat,lng"` (or `start_addr`), `end_coords` / `end_addr`,
`travel_mode=0` (driving; SerpApi codes: 6 best, 0 driving, 9 two-wheeler, 3 transit, 2 walking, 1 cycling), `distance_unit=0` (km). Parsed from `directions[0]`: `distance` (m),
`duration` (s), `formatted_*`, `typical_duration_range` ("35 min to 1 hr 5 min" → upper bound used as
the traffic-adjusted worst case).

### Google Local (`local.py`)
`engine=google_local`, `q="<category> near <venue>, <city>"`, `hl`, `gl`. Parsed from `local_results[]`:
`title`, `rating`, `reviews`, `type`, `address`, `gps_coordinates`, `hours`, `thumbnail`, `place_id`.

### Google Maps Reviews (`reviews.py`)
`engine=google_maps_reviews`, `data_id`, `sort_by=newestFirst`, `hl=en`. Parsed: `place_info`,
`topics[]` (`keyword`, `mentions`), `reviews[]` (`rating`, `snippet`, `date`, `user.name`).

### Google Travel Explore (`travel.py`, experimental)
`engine=google_travel_explore`, `departure_id`, `outbound_date`, `currency`. Parsed `destinations[]`.

## 3. Normalization

Provider structures never leave `integrations/serpapi/`. Each module exports a pure
`parse_*(payload) -> list[Normalized*]` function that is tolerant of missing keys: a malformed
*item* is skipped with a debug log; a malformed *payload* (not a dict) raises `SerpApiMalformedResponse`.

## 4. Error handling

| Situation | Detection | Behaviour |
|-----------|-----------|-----------|
| Timeout / network | `httpx.TimeoutException`, `httpx.TransportError` | Retry (backoff), then `SerpApiTimeoutError` |
| HTTP 429 | status | Retry honouring `Retry-After` (cap 8 s), then `SerpApiRateLimitError` |
| HTTP 5xx | status | Retry, then `SerpApiUpstreamError` |
| HTTP 401 / "Invalid API key" | status / `error` | `SerpApiAuthError` — no retry |
| "run out of searches" | `error` text | `SerpApiQuotaError` — no retry |
| "hasn't returned any results" | `error` text | Treated as **empty result** (not an error) |
| Non-JSON / non-object body | parse | `SerpApiMalformedResponse` |

Required stages (flights) propagate errors to the mission (`failed` with a user-safe message). Optional
stages (directions → fall back to a clearly-flagged distance estimate; reviews; places) degrade gracefully
and add a warning.

## 5. Rate limiting & concurrency

* A process-wide `asyncio.Semaphore(SERPAPI_MAX_CONCURRENCY=4)` bounds parallel calls.
* Our own `/missions/analyze` is limited to 12 requests/min per IP to protect the SerpApi quota.

## 6. Caching

Decision: **pluggable cache with three backends**, chosen at startup:

1. `RedisCache` when `REDIS_URL` is set and reachable (docker-compose default).
2. `DatabaseCache` (`search_cache` table) otherwise — works with SQLite and PostgreSQL, survives restarts, zero extra infra.
3. `MemoryCache` for tests.

Key = SHA-256 of `engine` + JSON of params with sorted keys (API key and `output` removed), so the key
captures API, query, location, dates and filters. TTLs: flights 30 min, hotels 60 min, directions 24 h,
local 24 h, reviews 24 h, geocoding 7 days. Cache hits are reported in the result's `data_sources` panel.

## 7. API key handling

* `SERPAPI_API_KEY` is read from the environment (`.env` locally) by `core/config.py`.
* It is added to the query string inside `SerpApiClient` only; logs pass through a redaction filter that
  masks `api_key=…` and any configured secret value.
* `/health` reports `serpapi_configured: true/false`, never the key.
* Missing key with `DEMO_MODE=false` → `503 setup_required` with setup instructions. There is **no silent
  fallback to demo data**.

## 8. Retry & timeout strategy

* `SERPAPI_TIMEOUT_SECONDS=25` per request (Google Flights can be slow), connect timeout 5 s.
* `SERPAPI_MAX_RETRIES=2` → up to 3 attempts, backoff `0.6 s × 2^attempt` + jitter.
* The whole mission has no global timeout, but each stage is bounded by its calls' timeouts.

## 9. Transit (trains, buses, metro) — v2

`engine=google_maps_directions`, `travel_mode=3`, `start_addr=<origin city>`, `end_coords=<venue>`,
`time=arrive_by:<epoch>` (deadline − required buffer, IST for Indian destinations), `route=4` when wheelchair
access is requested.

Parsed from `directions[]` where `travel_mode == "Transit"`: `start_time`/`end_time` (clock only, e.g. `9:38 PM`),
`duration`, `distance`, and `trips[]` with `title` (`"12622 - Tamil Nadu Express …"`), `start_stop`/`end_stop`
(`name`, `time`), `stops[]`, `icon` (`rail2.svg` → train, `bus2.svg` → bus), `service_run_by.name` (operator).
Absolute datetimes are reconstructed backwards from the requested arrival time, then forwards segment by segment.
A journey is **train** if any segment ≥ 90 min is rail, **bus** if a long segment is a bus, else **transit**.

Google Maps returns **no fares** for Indian long-distance services (`cost` is used when present). Verified against
a live response for Indore → Manyata Tech Park (3 options, all Indian Railways with a BMTC bus last mile); that
response is stored as `backend/tests/fixtures/serpapi_transit_idr_blr.json` and replayed in DEMO_MODE.

Driving for road trips: same engine, `travel_mode=0` (driving — note SerpApi's codes: 6 best, 0 driving,
9 two-wheeler, 3 transit, 2 walking, 1 cycling, 4 flight), `start_addr=<origin city>`.

API budget per fresh mission: ~22 searches for a long trip (2 flights, 2 transit, ≤ 2 fare lookups, 1 driving, 1 geocode,
2 hotels, ≤ 8 directions, ≤ 4 review lookups, 3 local); short trips skip flights and most airport routing. Users never see
this count — it appears only in the `DEBUG_MODE` diagnostics panel. Transit responses are cached 6 h.


## 10. Bus, train and ground transport — catalog investigation (October 2026)

Question: does SerpApi offer a dedicated bus/train search or booking API we should use instead of assuming Google
Flights is the only travel source?

Checked against SerpApi's own documentation and changelog (not guessed):

| Need | SerpApi option | Verdict |
|------|----------------|---------|
| Bus/train **booking or seat inventory** | — | **None exists.** No engine returns bookable bus/train inventory or seat availability. |
| Door-to-door **schedules** (train, bus, metro, walking legs) | Google Maps Directions API, `engine=google_maps_directions`, `travel_mode=3`, `prefer=bus` or `prefer=train`\|train` | Used (§9). Returns timed segments, stops and operators; usually **no fare** for Indian long-distance services. |
| **Fares and ticket sellers** for a train/bus route | Google Search API, `engine=google`, Transport Options answer box (`answer_box` with `type: "transport_options"`) — [docs](https://serpapi.com/direct-answer-box-api#api-examples-transport-options-answer-box), added in the [July 20–26 2026 changelog](https://serpapi.com/blog/serpapi-weekly-changelog-july-20-26-2026.md); alternative layouts under `direct_answer_box` ([roadmap #3621](https://github.com/serpapi/public-roadmap/issues/3621)) | **Integrated** as optional fare enrichment (below). |
| Road route | Google Maps Directions, `travel_mode=0` | Used for road trips and every transfer leg. |
| Local transport hubs | Discovered from transit results (boarding/alighting stops) | Used for "Railway stations" / "Bus points" in the route panel. |

### Transport Options answer box (`integrations/serpapi/transport.py`)

Request: `engine=google`, `q="trains from Indore to Ujjain on 12 October 2026"` (or `buses …`), `gl`, `hl`.

Shape (per SerpApi's documented example): `answer_box.title` ("Trains from Boston to Newark"), `routes[]` with
`time` ("5:05 AM – 9:13 AM"), `duration` ("4h 8m"), `fare` ("$217" or "Price unavailable"), `changes`
("0 changes"), `itinerary[]` segments (`service_by`, `transport_number`, `departure_time`, `arrival_time`; transfers
are `{"mode": "Change"}`) and `tickets_details[]` (`company`, `url`, optional `price`).

Normalized to `ReportedTransportRoute`: mode (from the title or segment icons), departure/arrival clock, duration,
changes, fare + currency (route `fare`, else the cheapest seller `price` if all sellers share a currency), service
numbers, operators and ticket sellers. A bare number is never treated as money — no currency is guessed.

**How it is used — enrichment, never replacement.** The answer box has station-to-station services and no
coordinates, so it can't build a door-to-door journey on its own. `MissionEngine.attach_reported_fares` copies a
fare onto a Google Maps transit option only when the route clearly is the same journey:

1. identical service numbers (e.g. trains 12919 + 12622 + 20607), **or**, when either side has no numbers,
2. same mode, same number of changes, and first departure within `FARE_MATCH_MINUTES` (10),

and only when the fare is in the mission's currency (fares are never converted). Matched options show **"Fare"**
with the detail *"Fare shown by Google Search (listed by IRCTC) — check availability before booking"*; local
connections are added as labelled estimates. Unmatched options keep **"Estimated fare"**. Nothing is ever labelled a
confirmed ticket.

**Failure policy.** The lookup runs concurrently with the Maps transit searches under `OPTIONAL_TIMEOUT_SECONDS`.
A timeout, error or missing box leaves fares estimated and adds only a debug note (visible with `DEBUG_MODE=true`) —
no user-facing warning, because nothing the user relies on is missing. Demo mode returns no answer-box data, so
demo journeys never mix in live fares. Cached 6 h.

**Limits.** The box appears only for some queries and regions; coverage of Indian intercity buses is unverified.
Treat it as a best-effort fare source.
