# TripMission — Product Requirements

> "Don't just plan the trip. Make sure you can actually make it."

## 1. Product vision

TripMission is a **constraint-aware travel decision engine**. A traveller gives it a real-world
*mission* — be at a specific place, by a specific time, within a specific budget — and TripMission
answers the question no travel search engine answers today:

> **Will this complete journey actually work, and which one is the best bet?**

It combines live flights, hotels, directions, local places and reviews (all via SerpApi), evaluates
every complete door-to-venue journey against the user's constraints, scores it, quantifies the risk,
and recommends one journey with a transparent explanation.

## 2. Problem statement

Travel tools are fragmented by data type:

| Tool | Answers | Does not answer |
|------|---------|-----------------|
| Flight search | Which flights exist, at what price | Will I reach the venue on time after landing? |
| Hotel search | Which hotels exist, at what price | Is the hotel close to *where I need to be*? |
| Maps | How long a drive is | Does that drive fit inside my arrival buffer? |
| Reviews | What people said | Is anything in those reviews a risk for *my* trip? |

For time-critical trips (job interview, exam, medical appointment, wedding), the cost of a bad
combination is not "a slightly worse holiday" — it is a missed interview. Users currently stitch
these tools together by hand, in their heads, under stress.

## 3. Target users

* **Time-critical travellers** — candidates, students, patients, professionals with a fixed start time.
* **Event travellers** — weddings, conferences, family functions.
* **Leisure travellers** who still want a defensible plan (family trips, vacations).

Primary market for the hackathon: India domestic travel (INR, Indian airports), with the engine
being currency- and region-agnostic.

## 4. Personas

| Persona | Situation | What they need |
|---------|-----------|----------------|
| **Aditi, 24, job candidate (Indore)** | Final-round interview at Manyata Tech Park, Bangalore, 10:00 AM. Budget ₹10,000, paying herself. | One journey she can trust, a clear buffer, no surprises. |
| **Rahul, 19, exam candidate** | Entrance exam centre in another city, reporting time 08:30. | Hard deadline, cheap, safe. Knows little about the destination. |
| **Meera, 38, medical appointment** | Specialist appointment with an elderly parent. | Short ground transfers, hotel close to hospital, pharmacy nearby. |
| **Karan, 31, consultant** | Client meeting, expense-capped. | Minimal time away, policy-compliant cost, coworking nearby. |
| **The Sharma family** | Wedding in Jaipur, 4 travellers. | Budget across travellers, good-rated hotel near venue. |

## 5. User journeys

**Primary journey — "Will I make my interview?"**
1. Lands on the home page, fills the hero mission bar: Indore → Bangalore, Interview, 9 Oct, arrive by 10:00, ₹10,000.
2. Optionally opens *More constraints*: venue (Manyata Tech Park), 60-minute buffer, max 90 min ground travel, hotel required, ≥ 4.0 rating, max 1 stop.
3. Clicks **Find my journey** → sees a live analysis checklist (flights → arrival times → hotels → ground travel → scoring → reviews → local places).
4. Lands on results: one **recommended journey** with its Mission Score, buffer, risk level and a minute-by-minute timeline.
5. Reads *Can this journey go wrong?* and *Why this journey?*.
6. Compares *Recommended / Cheapest / Fastest / Safest* side by side, switches between them.
7. Checks the hotel, its review signals, and what is near the venue (cafés, pharmacies).

**Failure journey — "Nothing fits"**
1. User sets a ₹4,000 budget with a 90-minute buffer.
2. TripMission shows "No journey fully satisfies your constraints", the closest journeys anyway,
   and **concrete relaxations** computed from the data ("Increase budget by ₹1,340", "Relax buffer to 45 min", "Allow one connection").

## 6. Core features (MVP)

1. **Mission form** — origin, destination, venue, date, mission type, travellers, arrival deadline, budget, minimum buffer, max ground time, hotel requirement, min hotel rating, max stops, preferences.
2. **Live data acquisition (SerpApi)** — Google Flights, Google Hotels, Google Maps (geocoding), Google Maps Directions, Google Local, Google Maps Reviews.
3. **Two journey strategies** — *same-day* (fly on the mission day) and *night-before* (fly the day before, sleep near the venue). The engine evaluates both.
4. **Constraint engine** — hard constraints (must arrive before deadline, max stops) and soft constraints (buffer, budget, ground time, hotel rating).
5. **Mission Score (0–100)** — deterministic weighted score with seven components (arrival reliability, budget, ground travel, location, hotel, duration, review confidence). Weights are configurable and adapt to mission type.
6. **Risk engine** — LOW / MEDIUM / HIGH with factor-level explanations and mitigations.
7. **Recommendation categories** — Recommended, Cheapest, Fastest, Safest.
8. **Journey timeline** — every leg with time, duration, distance and mode, ending at the required arrival.
9. **Review signals** — strengths and concerns extracted from real review data (no invented text).
10. **Local discovery** — mission-contextual nearby places (interview → cafés, pharmacies; vacation → restaurants, attractions).
11. **"Why this journey?"** — explanation generated from structured scoring output; AI-written when an AI key is configured, rule-based otherwise; AI output is fact-checked against the structured data before display.
12. **Constraint relaxation suggestions** when nothing fully fits.
13. **Transparency** — which live sources were called, which were cache hits, when data was fetched.
14. **Demo mode** — explicit, labelled, deterministic dataset for the interview scenario.

## 7. Future features

* Return journeys and multi-city missions.
* Train and bus options (Indian Railways, intercity buses) as alternative modes.
* Live flight-status monitoring on the day, with re-planning alerts.
* Google Travel Explore — "flexible destination" missions (endpoint implemented, UI not yet).
* Calendar import (ICS) to create missions automatically.
* Accounts, saved missions, sharing a mission with family.
* Booking deep-links and price alerts.

## 8. Non-goals

* TripMission is **not** a booking engine — it links out, it does not transact.
* It does **not** generate itineraries with an LLM. The LLM never chooses or invents a journey.
* It does **not** guarantee arrival; it quantifies risk from available data.
* No authentication in the MVP.

## 9. Hackathon positioning

Track: **Travel & Local Discovery** — "Help people decide where to go and how to get there using
current flights, hotels, maps, places, reviews, and destination data."

TripMission focuses on the *decide* in that sentence. SerpApi is used for what it is best at — fresh,
structured search data across six Google surfaces — and our backend turns that data into a decision.

**30-second pitch for judges**

* **What:** you enter a deadline, budget and destination; you get the one journey most likely to get you there.
* **Why it matters:** a missed interview or exam is not recoverable; existing tools never check the whole chain.
* **Why SerpApi:** the decision needs six kinds of live data at once (flights, hotels, geocoding, directions, places, reviews) — SerpApi provides all of them through one consistent API.
* **What's different:** Mission Score + arrival buffer + risk analysis on complete journeys, not lists of flights.

## 10. Competitive differentiation

| | Google Flights / MakeMyTrip | Generic AI trip planners | **TripMission** |
|--|--|--|--|
| Unit of analysis | Single flight or hotel | Free-text itinerary | **Complete journey to the venue** |
| Deadline awareness | No | Superficial | **Arrival buffer computed per journey** |
| Data | Live | Often hallucinated | **Live, structured, cited** |
| Risk | No | No | **Factor-level risk engine** |
| Explanation | No | Persuasive but unverifiable | **Generated from scores, fact-checked** |
