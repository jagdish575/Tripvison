# TripMission — Testing

## 1. Principles

* Automated tests **never call the real SerpApi or AI APIs**. SerpApi is mocked at the HTTP layer with
  `httpx.MockTransport`, using fixture payloads shaped like real SerpApi responses (`backend/tests/fixtures/serpapi_payloads.py`).
* Engines are pure and tested directly with hand-built normalized models.
* Live verification is manual: set `SERPAPI_API_KEY`, `DEMO_MODE=false`, and run a mission (or call `/api/v1/flights/search`).

## 2. Backend (pytest)

```bash
cd backend
.venv/Scripts/python -m pytest -q        # Windows
.venv/bin/python -m pytest -q            # macOS/Linux
```

| File | Covers |
|------|--------|
| `test_normalization.py` | Flight, hotel, directions, geocode, local, reviews parsers — full payloads, missing keys, malformed items, empty results; duration-text parsing |
| `test_serpapi_client.py` | Cache hit/miss, retries on 5xx/429, auth/quota errors (no retry), timeout mapping, empty results (not cached), malformed body, log redaction |
| `test_scoring.py` | The 7 required scoring behaviours, budget/arrival/ground/location curves, weight renormalisation, mission-type profiles, preference adjustments |
| `test_risk_and_itinerary.py` | Same-day and night-before timelines, buffer computation, group cab costs, buffer thresholds, delay cushioning, ground/budget/hotel-distance risks, review signals |
| `test_mission_engine.py` | Full engine over mocked SerpApi HTTP (call counts per engine), cache on second run, no flights, impossible deadline, budget too low, optional-stage failures, required-stage failure, unknown location, demo scenario |
| `test_api.py` | `/health`, `/airports`, analyze → poll → recommendations, persistence, 404, validation errors, unknown fields, 413, rate limit, setup_required, demo route guard, search endpoints |
| `test_explanation_and_reviews.py` | Rule explanation, fact-check accepts copied / rejects invented numbers, AI text accepted only after fact-check, verbatim review quotes |

| `test_multimodal.py` | Train/bus normalisation from a **real** Google Maps transit response, total cost items + sources, hotel nights, budget remaining / over budget, CASE 1–4, priority-based recommendations, Best value, road trip + trade-off sentence, templates endpoint, accessibility never guesses, mode filter |
| `test_email.py` | Summary email uses only stored values, provider failure never fails a mission (CASE 5), preview provider + preview endpoint, meaningful-change detection, reminder due logic (sent once), demo re-check alert only for meaningful changes, simulated delay is demo-only |
| `test_route_intelligence.py` | City without airport is valid, resolution for cities/towns, live geocoding of unknown towns, short trips skip flights, nearby-airport fallback, configurable transfer threshold, impractical road not searched, **Indore → Ujjain (Mahakal Mandir) end to end**, flight + ground transfer, total cost legs, optional timeout, partial failure, user-safe messages |
| `test_auth.py` | Mission creation requires sign-in, Google sign-in/session/sign-out, invalid/unverified tokens, Google not configured, config never exposes secrets, tampered cookie, cross-site POST blocked, users only see their own missions, demo sessions (labelled data, never live calls, can be disabled), trips + save + summary email, email preferences, email failure doesn't fail saving, request counts hidden, upstream errors user-safe |
| `test_transport_options.py` | Google Search transport-options answer box: documented layout, alternative `direct_answer_box` layout, money parsing (no guessed currency), query building, matching by service numbers, currency guard, Indore → Ujjain train gets the reported fare while the bus stays estimated, lookup failure is silent, demo never supplies search fares |

Run against PostgreSQL instead of SQLite with `TEST_DATABASE_URL=postgresql+psycopg://user:pass@host:5432/db`.

**Latest run (10 Oct 2026): 155 passed** on SQLite (`pytest -q`, ~13 s). Frontend: **16 passed** (`npm test`),
`npm run typecheck` clean. (Earlier milestone: 103 passed on SQLite and PostgreSQL 16.)

Live end-to-end (Phase 38) verified with real SerpApi + EURI + PostgreSQL + Redis: Indore → Bangalore, interview,
10:00, ₹10,000, Balanced — 22 live calls, 17 flights, 6 train routes (Indian Railways), 40 hotels, 27 journeys;
bus and road correctly reported unavailable; ₹5,000 budget → "Increase budget by ₹600 → Train becomes available".

Required scoring scenarios (all in `test_scoring.py`):
1. Cheap but late itinerary scores poorly.
2. Expensive but very reliable itinerary scores well but does not automatically win.
3. Over-budget itinerary is penalized.
4. Very small arrival buffer → HIGH risk.
5. Direct flight → lower connection risk.
6. Far hotel → lower location score.
7. Missing information does not crash.

## 3. Frontend (Vitest + Testing Library)

```bash
cd frontend
npm test
```

| File | Covers |
|------|--------|
| `src/utils/format.test.ts` | Currency (Indian grouping), minutes, buffer and clock formatting |
| `src/components/__tests__/components.test.tsx` | MissionScore accessible label, RiskPanel content, ErrorState retry, MissionTypeSelector radiogroup + keyboard |
| `src/components/__tests__/costs.test.tsx` | Cost source badges, remaining budget, OVER BUDGET label, selecting a mode from the budget bars |
| `src/components/__tests__/product.test.tsx` | Auth gate (modal → Demo Mode → original action resumes), runs immediately when signed in, "How we decided" without request counts, soft notices, route notices, error states without raw errors, hero bar drops a venue from another city |

`vite.config.ts` sets `testTimeout: 30000`: the first render in each file pays for jsdom + framer-motion start-up,
which exceeded the 5 s default on slower Windows machines.

`npm run build` runs the TypeScript compiler in strict mode (type errors fail the build).

## 4. Manual / E2E verification checklist

Run with `DEMO_MODE=true` and again with a real `SERPAPI_API_KEY`:

* Landing → hero form → analysis → results renders without console errors.
* Plan page validation messages for missing/invalid fields.
* Results: score count-up, timeline, risk, switch options, compare page, hotel, reviews, local places, data sources.
* Error states: stop the backend (network failure), invalid city, budget ₹2,000 (no fit + suggestions), deadline 06:00 (no flights).
* Mobile (375 px) and tablet (768 px) layouts.
* Keyboard-only pass through the form; reduced-motion setting.

Screenshots used during QA are produced with `frontend/scripts/screenshots.mjs` (Playwright driving the
system Edge/Chrome).

## 5. Error scenarios covered

No flights · no hotels · no places · API timeout · API 5xx · SerpApi 429 · quota exhausted · invalid key ·
malformed JSON · invalid destination · invalid date · budget too low · nothing satisfies constraints ·
AI failure / AI hallucinated number · network failure (frontend).


## 6. Required cases → tests

| # | Case | Test |
|---|------|------|
| 1 | City without airport | `test_route_intelligence::test_city_without_airport_is_a_valid_location` |
| 2 | Ujjain-style destination | `test_route_intelligence::test_indore_to_ujjain_mahakal_mandir_end_to_end` |
| 3 | Nearby airport fallback | `test_route_intelligence::test_long_trip_to_airportless_city_uses_nearby_airport` |
| 4 | Venue resolution | `test_indore_to_ujjain_mahakal_mandir_end_to_end` (every journey ends "Arrive at Mahakal Mandir"; road route measured to the venue) |
| 5 | Flight + ground transfer | `test_route_intelligence::test_flight_plus_ground_transfer_to_airportless_city` |
| 6 | Train route | `test_multimodal::test_train_normalization_from_real_google_maps_transit_response`, `test_transport_options::test_indore_ujjain_train_gets_the_reported_fare_and_bus_stays_estimated` |
| 7 | Bus route | `test_multimodal::test_bus_normalization_and_empty_results`; Ujjain end-to-end (`Estimated bus/transit route`, never "confirmed") |
| 8 | Road route | `test_multimodal::test_ground_option_and_tradeoff_sentence`; `test_impractical_road_is_not_searched` |
| 9 | Total cost | `test_multimodal::test_total_trip_cost_items_sources_and_budget_remaining`, `test_flight_total_cost_includes_every_leg` |
| 10 | Budget | `test_multimodal::test_over_budget_is_negative_remaining`, `test_case3_over_budget_strongly_penalised` |
| 11 | Arrival buffer | `test_risk_and_itinerary::test_buffer_thresholds`, `test_same_day_with_hotel_timeline_and_buffer` |
| 12 | Authentication | `test_auth::test_google_sign_in_session_and_sign_out`, `test_invalid_google_token_is_rejected`, `test_tampered_session_cookie_is_ignored` |
| 13 | Protected mission creation | `test_auth::test_mission_creation_requires_sign_in`, `test_users_only_see_their_own_missions`; frontend auth-gate test |
| 14 | Demo mode | `test_auth::test_demo_session_uses_labelled_demo_data`, `test_demo_session_never_calls_live_apis`, `test_transport_options::test_demo_provider_never_supplies_search_fares` |
| 15 | Email preferences | `test_auth::test_email_preferences_persist_and_control_subscriptions` |
| 16 | Email failure | `test_auth::test_email_failure_does_not_fail_saving`, `test_email::test_provider_failure_never_fails_the_mission` |
| 17 | Optional API timeout | `test_route_intelligence::test_optional_api_timeout_does_not_block_the_mission` |
| 18 | Partial API failure | `test_route_intelligence::test_partial_failure_keeps_the_journey_and_hides_raw_errors`, `test_mission_engine::test_optional_stage_failures_do_not_fail_mission` |
| 19 | Mobile behaviour | `frontend/scripts/responsive-qa.mjs` (below) — the API is identical for mobile; no device-specific endpoints |
| 20 | No raw errors exposed | `test_auth::test_upstream_errors_are_user_safe`, `test_results_hide_request_counts_and_diagnostics`, `test_failed_flight_search_message_is_user_safe`; frontend "How we decided" test |

## 7. Responsive + end-to-end QA (Playwright)

```bash
# backend + frontend running (any DB; the script uses Demo Mode, so no SerpApi quota is spent)
cd frontend && node scripts/responsive-qa.mjs ../screenshots/responsive http://localhost:5173
```

The script drives the real app in Edge/Chrome: landing → hero (Indore → Ujjain, Other) → *more constraints* → plan
form keeps the values → venue **Mahakal Mandir** → *Find my journey* → sign-in modal → *Continue in Demo Mode* →
analysis → results. It asserts the airport-fallback notice, that Mahakal Mandir is the endpoint, and that no
developer text appears ("data requests", "SerpApi request", "couldn't match"…). It saves the journey, then loads
`/`, `/plan`, results, compare, `/trips`, `/trips?tab=saved`, `/profile`, `/about` at **320, 375, 390, 768, 1024,
1440 and 1920 px**, failing on any element wider than the viewport (`body { overflow-x: hidden }` is deliberately
not treated as a fix — iOS Safari still pans), opens the mobile menu below 768 px and the profile menu on desktop.

Latest run (10 Oct 2026): **no horizontal overflow at any width, no page errors**. Fixed during that run: mode
cards on results overflowed at 320 px (implicit grid track sized to content → `grid-cols-1`); the profile
buffer selector overflowed at 320 px; the demo badge showed (and wrapped) in the mobile top bar; the hero bar
carried the default Bangalore venue into an Ujjain mission.
