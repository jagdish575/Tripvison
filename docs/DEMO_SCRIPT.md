# TripMission — 3-Minute Demo Script

## A. Judges' quick path (90 seconds, no account needed)

Works on any server — Demo Mode never calls live APIs and is labelled everywhere.

| Time | On screen | Say |
|------|-----------|-----|
| 0:00 | Landing. Point at the navbar: How it works · How we decide · My trips · **Plan a mission** | "TripMission isn't a flight search. It decides how to get you door to door." |
| 0:10 | Hero bar: **Indore → Ujjain**, mission **Other**, 10:00, ₹10,000 → *Venue, buffer, hotel and more constraints* → venue **Mahakal Mandir** → **Find my journey** | "Ujjain has no airport. Most planners stop here." |
| 0:20 | Sign-in modal → **Continue in Demo Mode** | "Real users sign in with Google; judges can skip it. The form isn't lost — the mission just continues." |
| 0:30 | Analysis: *Checking nearby transport hubs → Finding practical routes → …* | "Product language, not API calls." |
| 0:40 | Results → *How we routed this trip* | "Ujjain doesn't have a commercial airport — nearest practical is Indore (IDR). And it's only ~62 km, so we didn't waste a flight search: train, bus and road are compared instead." |
| 0:55 | Mode cards Train · Bus · Road, recommended journey ending **Arrive at Mahakal Mandir** | "Door to door, to the temple — not to the city centre. Total cost, budget remaining, buffer, risk, Mission Score." |
| 1:10 | Fare labels: *Estimated fare* / *Estimated bus/transit route* | "We never invent a ticket. When Google shows a real fare we use it and say so; otherwise it's labelled an estimate." |
| 1:20 | **Save journey** → avatar menu → **My trips** → **Profile › Email preferences** | "Saved, in My trips, with the emails I chose." |

Then switch to the long-distance script below for the full story.

## B. Long-distance mission (3 minutes)

**Setup before recording**
* Live: `SERPAPI_API_KEY` set, `DEMO_MODE=false`. Run the mission once beforehand so responses are cached in Redis
  (a repeat costs ~0–2 searches and takes ~10 s instead of ~100 s).
* Offline / no key: `DEMO_MODE=true`. Flights, hotels, reviews and places are a labelled demo dataset; train schedules
  are a recorded real Google Maps transit response; the bus option is illustrative. The numbers below are from demo
  mode with priority **Balanced** — with live data, read them off the screen.
* Browser at 1440 px, landing page open, mission date two days from today.

| Time | On screen | Say |
|------|-----------|-----|
| **0:00 – 0:20** Problem | Landing hero | "You can search flights, trains, hotels and directions separately. None of them tell you which *complete* journey gets you to a 10 AM interview — and what it really costs." |
| **0:20 – 0:45** Mission | Plan page: Indore → Bangalore, venue Manyata Tech Park, **Interview** (template sets a 60-min buffer and *Avoid risk* — switch to **Balanced**), modes Flight/Train/Bus/Road, ₹10,000, tick **Send me trip updates**. **Find my journey**. | "I describe the mission — deadline, budget, safety buffer, what matters most — not just a route." |
| **0:45 – 1:00** Live analysis | Checklist: flights, trains & buses → arrival times → hotels → ground → scores → reviews → places | "In parallel: Google Flights for two days, Google Maps transit for Indian Railways schedules, a road route, then hotels, directions, reviews and places — only for the promising options." |
| **1:00 – 1:25** Your options | Mode cards: Flight 91 · Train 78 (HIGH risk) · Bus 81 · Road trip *not available — 26 h by road* | "Every mode, costed all-in. The train is cheapest on the ticket but the engine flags a 15-minute change at Chennai with no live running status — high risk. Road is honestly ruled out." |
| **1:25 – 1:45** Recommendation | Dark card: **Flight · Best overall · Best value**, ₹8,062, ₹1,938 left, at venue 08:45, 75-min buffer, Low risk | "Best overall: fly in the day before on QP 1384 and stay 3.6 km from the venue. Here's why —" read the first line of *Why this option?* ("You spend ₹1,228 more than the cheapest option, but save about 26 hours…"). |
| **1:45 – 2:05** Total cost & trade-off | Total trip cost panel with LIVE / ESTIMATED badges, then Budget bars + Time vs money | "Not just the ticket: flight live, taxis and food estimated — and labelled. Spend ₹3,780 more than the bus to save about 26 hours. That sentence is computed, not generated." |
| **2:05 – 2:25** Timeline & risk | Step-by-step timeline, *Can this journey go wrong?* | "Land 15:15, check in, leave the hotel at 08:30, arrive 08:45. Low risk — and it still tells me what reviews say about the hotel." |
| **2:25 – 2:45** Email | Email panel: summary preview → **Simulate a 45-min delay** (demo) → "No meaningful change — absorbed by your overnight stay" | "I get a summary, a reminder 24 h before departure, and an alert only for meaningful changes. A delay the night before doesn't change my arrival, so no alert." |
| **2:45 – 3:00** Close | *How we decided* panel (collapsed by default) | "SerpApi is the live data. TripMission is the decision: which way to travel, what it really costs, and whether it works." |

**Backup moments**
* *Relax constraints:* budget ₹5,000 → "No journey fully satisfies your constraints" → **Increase budget by ₹600 → Train becomes available**.
* *Priorities:* switch to **Save money** and re-run — the cheaper option climbs; **Save time** favours flights.
* *Change alert:* a same-day-only mission + **Simulate a 45-min delay** → "Your journey needs attention" email preview.
* *Why not an LLM planner?* "The model never chooses or invents a price; it only words the engine's decision, and any number it adds is rejected."
