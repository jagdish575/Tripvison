# TripMission — Risk Engine

`backend/app/engines/risk_engine.py`. The score asks *"how good is this journey?"*; the risk engine asks
*"how can this journey go wrong?"*. A journey can score well and still carry a specific risk worth naming.

## 1. Output

```json
{ "level": "LOW | MEDIUM | HIGH", "score": 0-100,
  "factors": [ { "key": "buffer", "severity": "high", "points": 40, "title": "Only 15-minute arrival buffer",
                 "detail": "You asked for 60 minutes. A short taxi delay would make you late." } ],
  "strengths": [ "Direct flight", "Hotel 1.3 km from venue" ],
  "recommendations": [ "Leave the hotel by 08:31 — 15 minutes earlier than the minimum." ] }
```

## 2. Factors

| # | Factor | Condition | Severity | Points |
|---|--------|-----------|----------|-------:|
| 1 | **Arrival buffer** | `b < 0` (misses deadline) | high | 60 |
| | | `b < 30` or `b < 0.5·r` | high | 40 |
| | | `b < r` | medium | 20 |
| 2 | **Flight connection** | each stop, same_day | medium | 12 |
| | | shortest layover < 60 min, same_day | high | 25 |
| | | overnight layover | medium | 10 |
| | | any stop, night_before (cushioned) | low | 5 |
| 3 | **Delay history** | Google Flights flags a segment *often delayed by 30+ min*, same_day | medium | 15 |
| | | same, night_before | low | 4 |
| 4 | **Ground transfer** | `G_morning > M` | high | 25 |
| | | `G_morning > 0.75·M` | medium | 10 |
| | | traffic upper bound adds ≥ 20 min | low | 5 |
| 5 | **Hotel distance** | `d > 10 km` | high | 20 |
| | | `d > 5 km` | medium | 10 |
| 6 | **Budget overrun** | `C > 1.10·B` | high | 25 |
| | | `C > B` | medium | 12 |
| | | `C > 0.95·B` | low | 4 |
| 7 | **Review warning** | hotel rating < `min_hotel_rating` or < 3.5 | medium | 10 |
| | | ≥ 30 % negative mentions on a key aspect (cleanliness, noise, staff, check-in) | low | 5 |
| 8 | **Missing data** | each estimated route / unknown hotel price / unknown hotel location | low | 4 (max 12) |
| 9 | **Late arrival** | night_before flight lands after 23:00 | low | 5 |

## 3. Level

```
score = min(100, Σ points)
HIGH    if any factor is high   or score ≥ 45
MEDIUM  if any factor is medium or score ≥ 20
LOW     otherwise
```

## 4. Strengths

Positive facts collected while evaluating: "75-minute arrival buffer", "Direct flight", "Hotel 1.3 km from
venue", "₹1,438 under budget", "Flight lands the evening before", "Real driving times from Google Maps".

## 5. Mitigations

Each factor carries a concrete recommendation, e.g.:

* buffer → "Leave 20 minutes earlier, or choose the night-before option."
* connection → "Book both legs on one ticket so the airline rebooks you if you miss the connection."
* delay history → "This flight is often delayed by 30+ minutes — keep the night-before alternative in mind."
* ground → "Book a cab in advance; airport queues add 10–20 minutes at peak."
* hotel distance → "Choose a hotel within 3 km of the venue."
* budget → "Exceeds budget by ₹1,340."
* missing data → "Some travel times are estimated from straight-line distance."

## 6. Mission-level "no fit" analysis

When no itinerary satisfies all constraints, the mission engine derives **relaxation suggestions** from the
closest itineraries:

| Blocking constraint | Suggestion |
|---------------------|------------|
| Budget | "Increase budget to ₹X" where X = cost of the best journey that meets all other constraints |
| Buffer | "Relax arrival buffer to N min" where N = best achievable buffer |
| Stops | "Allow one connection" if connecting flights would arrive in time (from the unfiltered search) |
| Ground time | "Allow up to N min of ground travel" |
| Hotel rating | "Lower minimum hotel rating to X" |
| Hotel distance | "Expand hotel radius" when every hotel is > 5 km away |
| No flights at all | "Travel the day before" / "Choose a later arrival time" |

## 7. Mode-specific factors (v2)

| Mode | Factor | Severity / points |
|------|--------|-------------------|
| Train / bus / transit | Each change of vehicle (separate tickets don't protect you) | medium 10 each (low if the night before with one change) |
| | Tight change (< 45 min between long-distance services) | medium 10 |
| | ≥ 6 h on long-distance services, no live running status | medium 12 same day · low 4 night before |
| Road trip | Drive over 8 h | medium 15 |
| All | Arrives 23:00–05:00 the night before | low 5 |

Example from live data: Indore → Bengaluru by train had a **15-minute** change at Chennai Central; the engine flags it.

## 8. Change alerts (notifications)

`services/email/changes.detect_changes(before, after)` compares stored snapshots of the same journey. An alert is sent
only when at least one change is meaningful:

| Change | Meaningful when |
|--------|-----------------|
| Arrival at the venue | shifts ≥ 15 min |
| Arrival buffer | drops ≥ 15 min, falls below the required buffer, or goes negative |
| Risk level | increases |
| Total trip cost | rises ≥ 10 % **and** ≥ ₹500 |
| Journey | no longer available, or the recommended journey changed |

A delayed flight the evening before that doesn't change the venue arrival is reported as "absorbed by your plan"
and does not trigger an alert.
