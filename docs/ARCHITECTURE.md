# TripMission — Architecture Overview

TripMission separates three responsibilities that "AI trip planners" usually blur:

```
USER ──► SERPAPI (live data) ──► NORMALIZATION ──► CONSTRAINT ENGINE ──► SCORING ──► RISK ──► RECOMMENDATION ──► (optional) AI EXPLANATION ──► USER
         integrations/serpapi    Normalized*        mission_engine       scoring_    risk_    categories          services/explanation
                                 models             itinerary_engine     engine      engine                      (fact-checked)
```

## Key decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Unit of evaluation | A complete **itinerary** (flight + optional hotel + timed ground legs) | Users miss interviews because of combinations, not single flights. |
| Strategies | `same_day` and `night_before` evaluated side by side | The most reliable fix for a morning deadline is often flying the day before; users rarely compare it explicitly. |
| Decision logic | Deterministic Python (`engines/`) | Reproducible, testable, explainable. |
| AI usage | Explanation only, with a numeric fact-check | Prevents hallucinated prices/times reaching users. |
| Provider abstraction | `TravelDataProvider` protocol, `SerpApiProvider` + `DemoProvider` | Demo data is isolated and never mixed with live data; tests can inject mocks. |
| Long-running analysis | Background task + polled status | Real stage-by-stage progress; short HTTP requests. |
| Caching | Redis → DB table → memory, same interface | Hackathon-simple locally, production-ready with Redis. |
| API-call budget | Funnel: 2 flight searches → shortlist → ≤ 2 hotel searches → directions only for top hotels → reviews for top 2 | ~18 searches per fresh mission, 0 on repeat. |
| Persistence | Normalised tables + a JSON result snapshot | Analytics-friendly *and* fast reads for the UI. |

## Request lifecycle

1. `POST /api/v1/missions/analyze` → Pydantic validation, rate limit, airport resolution, demo-route guard, `missions` row, background task.
2. `MissionEngine.run()` emits progress (`resolve → flights → arrival → hotels → ground → scoring → reviews → places → explain`), persisted to `missions.progress`.
3. The UI polls `GET /missions/{id}` and paces the checklist so each real stage is readable.
4. On completion, `MissionRepository.complete()` writes flights, hotels, reviews, places, itineraries, recommendations and the result snapshot.
5. `GET /missions/{id}/recommendations` serves the snapshot to the results, compare and map views.

See `HLD.md` (system view), `LLD.md` (modules and classes), `SCORING_ENGINE.md`, `RISK_ENGINE.md` and `SERPAPI_INTEGRATION.md` for detail.
