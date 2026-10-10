# TripMission — Scoring Engine

`backend/app/engines/scoring_engine.py` — deterministic, side-effect free, unit-tested.

## 1. Definitions

For an itinerary *i*:

| Symbol | Meaning |
|--------|---------|
| `D` | Arrival deadline at the venue (destination local time) |
| `A` | Estimated arrival at the venue |
| `b = D − A` | **Arrival buffer** in minutes |
| `r` | User's required minimum buffer (`min_buffer_minutes`) |
| `C` | Total cost = flight × travellers + hotel nights + ground transfers |
| `B` | Budget (total) |
| `G` | Ground minutes on the **mission morning** (critical path) + ½ × ground minutes the evening before |
| `M` | `max_ground_minutes` |
| `d` | Hotel → venue distance (km) |

### Journey strategies
* **same_day** — flight lands on the mission day. Path: airport exit (25 min) → (hotel bag-drop 15 min →) venue.
* **night_before** — flight lands the day before; the traveller sleeps at the hotel and leaves in the morning
  so they arrive `r + 15` minutes before the deadline (`leave_hotel_at` is shown).

An itinerary with `b < 0` is **infeasible**: its overall score is capped at 25 and it is never recommended.

## 2. Components (each 0–100)

### 2.1 Arrival reliability
Exposure to things that eat the buffer:

```
E = 30·[often delayed]  + 20·stops + 15·[shortest layover < 60 min]      (same_day only; 0 for night_before)
T = max(0.15·G_morning, traffic_upper_bound − duration)                  (traffic margin, from typical_duration_range)
eb = b − E − T                                                            (effective buffer)

f(eb) = max(5, 30 + eb/2)                 if eb ≤ 0
        30 + 50·eb/r                      if 0 < eb < r
        80 + 20·(eb − r)/90               if r ≤ eb ≤ r + 90
        100                               if r + 90 < eb ≤ r + 180
        100 − min(15, (eb − r − 180)/20)  if eb > r + 180      ← enormous buffers are not rewarded blindly

arrival = 0                               if b < 0
          min(100, f(eb) + 8)             for night_before (overnight cushion absorbs flight delays)
          f(eb)                           otherwise
```
(If `r = 0`, `r` is treated as 15 to keep the curve defined.)

### 2.2 Budget
```
q = C / B
budget = 100                        if q ≤ 0.70
         100 − 20·(q − 0.70)/0.30   if 0.70 < q ≤ 1.00    (80 at exactly the budget)
         max(0, 80 − 300·(q − 1))   if q > 1.00            (−3 points per 1 % over budget)
```

### 2.3 Ground travel
```
ground = 100                                  if G ≤ 0.5·M
         100 − 30·(G − 0.5M)/(0.5M)           if 0.5M < G ≤ M
         max(0, 70 − 70·(G − M)/M)            if G > M
```

### 2.4 Location (hotel → venue distance; only when the itinerary has a hotel)
```
location = 100                          if d ≤ 1.5 km
           100 − 25·(d − 1.5)/3.5       if d ≤ 5
           75 − 40·(d − 5)/10           if d ≤ 15
           max(10, 35 − 2·(d − 15))     otherwise
```
Same-day itineraries without a hotel → `None` (weight redistributed).

### 2.5 Hotel quality
```
hotel = clamp(100·(rating − 2.5)/2.5, 0, 100) − 20·[rating < min_hotel_rating]
      = 50 if rating unknown
```

### 2.6 Duration (relative)
```
Tt = flight duration + airport exit + all taxi legs (+ bag-drop stop)   — time actually in transit
F  = min Tt over all candidate itineraries of the mission
duration = max(0, 100 − 60·(Tt − F)/F) − 10·[departure before 05:00] − 10·[night_before landing after 23:00]
```

### 2.7 Review confidence (only with a hotel)
```
v = min(1, log10(n + 1)/3)                          (n = review count; 1,000 reviews → 1.0)
p = Σpositive / Σ(positive + negative) from reviews_breakdown   (fallback: rating/5)
review = 100·(0.4·v + 0.6·p)        ;  35 if no reviews at all
```

## 3. Weights — chosen by "What matters most?" (v2)

All profiles live in one object, `ScoringConfig.profiles` (`engines/scoring_engine.py`). The AI never sees or changes
them. `SCORING_WEIGHTS` overrides the balanced profile. Mission **templates** pick a default priority
(interview/exam/medical → Avoid risk, business → Save time, others → Balanced); the user can change it.

| Component | Balanced (default) | Save money | Save time | Avoid risk |
|-----------|------:|------:|------:|------:|
| arrival (reliability) | 0.30 | 0.20 | 0.30 | 0.40 |
| budget (cost) | 0.20 | 0.45 | 0.15 | 0.15 |
| ground | 0.15 | — | — | 0.15 |
| location & stay | 0.10 | 0.10 | 0.05 | 0.10 |
| duration (time) | 0.10 | 0.15 | 0.40 | 0.05 |
| review | 0.05 | — | — | 0.05 |
| convenience | 0.10 | 0.10 | 0.10 | 0.10 |

Components that don't apply (no hotel → location, review) are dropped and the rest renormalised.

### v2 component changes
* **Budget** = 0.5 × fit-to-budget curve (§2.2) + 0.5 × 100 × (cheapest on-time total / this total) — a cheaper
  journey always earns credit, even when everything is comfortably within budget.
* **Location & stay** = 0.6 × distance curve (§2.4) + 0.4 × rating curve (§2.5).
* **Duration** uses time actually travelling, on a log scale: `100 − 35·log2(T / fastest)` (2× → 65, 4× → 30, 8× → 0).
* **Convenience** = 100 − 12 per change of vehicle − 15 departure before 05:00 − 10 arrival 23:00–05:00
  − 12 per night spent on board (train/bus) − 8 if > 20 min walking − 15 for drives over 8 h.
* **Arrival delay exposure** for trains/buses (no live running status): 20 per change + 5 per hour of long-distance
  travel (max 60) on the mission day; zero when arriving the day before.
* **Value index** (Best value) = 100 × (0.4 × cheapest/cost + 0.3 × fastest/time + 0.3 × arrival/100).

## Total trip cost

`total = ticket + ground + hotel + food`. Totals are only shown when every included part is known.

| Item | Source | Model |
|------|--------|-------|
| Flight ticket | live | Google Flights price (for all travellers) |
| Train ticket | estimated | ₹1.25/km (≈ 3AC) × route km, min ₹300, + ₹40 per local metro/bus segment, × travellers |
| Bus ticket | estimated | ₹1.8/km (≈ AC sleeper) × km, × travellers |
| Road trip | estimated | ₹13/km outstation cab + ₹300 driver allowance per 8 h, per 4 travellers |
| Taxi transfers | estimated | ₹100 + ₹18/km per cab |
| Hotel | live / calculated | Google Hotels total for the searched nights; nightly × nights when a train arrives earlier |
| Food | estimated / user_provided | food_per_day × days from departure to mission day × travellers |

## 4. Preference adjustments (small, explicit, ±3–4 points, recorded as factors)

| Preference | Effect |
|------------|--------|
| `prefer_direct` | +3 for nonstop, −3 for connections |
| `avoid_early_departure` | −4 if departure before 06:00 |
| `night_before_preferred` | +4 for night_before |
| `same_day_only` | previous-day flights are not searched |
| `breakfast_included` | +3 if hotel amenities mention breakfast |
| `free_cancellation` | +3 if the hotel offers free cancellation |

## 5. Outputs

`overall_score, arrival_score, budget_score, ground_travel_score, location_score, hotel_score,
duration_score, review_score, weights, explanation_factors[]` where each factor is
`{key, label, impact: "positive"|"negative"|"neutral", detail}` — e.g.
`{"key":"buffer","label":"75-minute arrival buffer","impact":"positive"}`.

## 6. Categories

* **Best overall** (`recommended`) — highest overall among journeys meeting *every* constraint; else among feasible.
* **Cheapest** — lowest total trip cost among feasible journeys.
* **Fastest** — least time travelling (`total_travel_minutes`).
* **Safest** — lowest risk score (ties → higher arrival score).
* **Best value** — highest value index among journeys within budget.

Feasible = arrives before the deadline. Each mode's card shows its best journey using the same ranking as Best overall.
The **trade-off sentence** compares Fastest and Cheapest: "Spend ₹X more (flight instead of train) to save about N
hours of travel." — computed, never written by AI.

## 7. Required behaviours (enforced by tests)

1. Cheap but late itinerary scores poorly.
2. Expensive but very reliable itinerary scores well but does not automatically win.
3. Over-budget itinerary is penalized.
4. Very small arrival buffer → high risk.
5. Direct flight → lower connection risk than connecting.
6. Hotel far from venue → lower location score.
7. Missing information does not crash the engine.
