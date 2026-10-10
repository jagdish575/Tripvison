# TripMission — UI / UX

## 1. Design intent

A serious travel product: **editorial travel magazine × precise productivity tool**. Calm, trustworthy,
data-first. The interface earns trust by showing *the numbers that matter* (arrival buffer, total cost,
risk) in a strong hierarchy — not by decoration.

Explicitly avoided: purple/blue AI gradients, glow blobs, glassmorphism, oversized rounded cards,
"AI-powered" banners, meaningless stats, decorative motion.

## 2. Colour tokens

| Token | Hex | Use |
|-------|-----|-----|
| `ink` | `#0B1220` | Headlines, primary dark surfaces (recommended journey header, footer) |
| `text` | `#0F172A` | Body text |
| `muted` | `#64748B` | Secondary text, labels |
| `line` | `#E2E8F0` | Hairline borders, dividers |
| `paper` | `#F8FAFC` | Page background |
| `surface` | `#FFFFFF` | Cards, inputs |
| `blue` | `#2563EB` | Actions, links, selection, focus |
| `amber` | `#F59E0B` (text `#B45309`) | Warnings, MEDIUM risk |
| `green` | `#16A34A` (text `#15803D`) | Safe / recommended / LOW risk |
| `red` | `#DC2626` (text `#B91C1C`) | Risk, HIGH, errors |

Colour is semantic. Blue never means "good"; green never decorates.

## 3. Typography

* **Display:** *Newsreader* (variable serif) — hero headline, page titles, the big score numeral. Gives the editorial voice.
* **UI / data:** *Inter* (variable) with `font-feature-settings: "tnum", "cv11"` for tabular numerals in times, prices and scores.
* Scale: 12 / 13 / 14 / 16 / 18 / 22 / 28 / 40 / 56 / 72. Body 15–16 px, line-height 1.55. Data labels 12 px uppercase, tracking 0.06em.
* Weights: 400 body, 500 labels, 600 emphasis. Serif headings at 400–500 (never bold).

## 4. Shape, depth, spacing

* Radius: `4px` inputs/badges, `8px` cards, `12px` large panels. Nothing pill-shaped except status badges.
* Borders over shadows. One shadow token (`0 1px 2px rgb(15 23 42 / .06), 0 8px 24px -12px rgb(15 23 42 / .12)`) for floating elements only.
* 8-px grid; section spacing 96 px desktop / 64 px mobile; max content width 1200 px with a 12-column grid.

## 5. Components

`Navbar` (wordmark, How it works, Plan, About, DEMO MODE badge) · `HeroMissionBar` · `MissionForm` with numbered
sections · `MissionTypeSelector` (icon tiles, radio-group semantics) · `MissionBrief` (live summary) ·
`SearchProgress` · `MissionSummaryBar` · `RecommendationCard` · `MissionScore` (ring + count-up) ·
`ScoreBreakdown` (bars with values) · `JourneyTimeline` · `RiskPanel` · `OptionSwitcher` · `FlightCard` · `HotelCard` ·
`ReviewInsights` · `LocalDiscovery` + `PlaceCard` · `ExplanationPanel` · `ConstraintSuggestions` · `DataSources` ·
`ComparisonTable` · `EmptyState` · `ErrorState` · `Skeleton` variants · `Footer`.

## 6. Layout

* **Landing** — asymmetric hero: serif headline left (7 cols), a "boarding pass" example mission card right (5 cols); full-width mission bar below the fold line. Then: the problem (three tools vs one decision), how it works (5 steps on a drawn route line), how we decide (weights), live data sources, CTA.
* **Plan** — form (8 cols) with numbered sections + sticky mission brief (4 cols). Mobile: single column, sticky bottom CTA.
* **Analyzing** — centred narrow column: the mission line, then the stage checklist with live counts.
* **Results** — summary bar; dark recommended-journey header with score and the four key numbers; then a two-column grid (timeline + map left, risk + explanation right); option switcher; hotel + reviews; local discovery; data sources.
* **Compare** — columns per option, rows per metric, best value per row highlighted; mobile becomes stacked option cards.

## 7. Responsive behaviour

| Breakpoint | Behaviour |
|------------|-----------|
| Mobile 320–767 px | Single column; hero mission bar stacks; plan form single column with a sticky full-width *Find my journey*; Mission Brief becomes a compact collapsible summary; results order: recommended journey → score → budget → timeline → risk → alternatives; mode cards stack; comparison becomes stacked option cards; hamburger menu |
| Tablet 768–1023 px | Two-column form grid; results stack timeline above risk; navbar shows a links row under the logo bar |
| Desktop ≥ 1024 px | Full layouts: plan form + sticky Mission Brief side panel; results main column + side panel; mode cards 3–4 across |
| Large ≥ 1440 px | Content container caps at 1440 px, centred, with full-bleed backgrounds; text columns keep a readable measure instead of stretching |

Container: `.container-page` = `w-full max-w-[1440px] mx-auto`, side padding 16 / 24 / 40 / 48 px. Headings use
responsive sizes (e.g. 32 → 40 → 44 px) and `text-wrap: balance`. Grids always declare their column template
(`grid-cols-1` at mobile) so a long word can't widen an implicit track past the viewport. Verified with
`frontend/scripts/responsive-qa.mjs` at 320, 375, 390, 768, 1024, 1440 and 1920 px (see TESTING.md §7).

## 8. Motion (Framer Motion)

| Element | Motion | Duration |
|---------|--------|----------|
| Page | fade + 8 px rise | 280 ms ease-out |
| Card lists | stagger 50 ms, fade + 6 px rise | 240 ms |
| Analysis stages | check icon scale-in, row colour transition | 200 ms |
| Mission score | ring stroke draw + number count-up | 900 ms |
| Timeline | vertical path draws top-to-bottom; nodes fade in sequence | 700 ms |
| Option switch | cross-fade detail panels | 180 ms |
| Buttons | 1 px press translate, colour transition | 120 ms |

`prefers-reduced-motion: reduce` disables transforms and count-ups (values render final immediately).

## 9. Accessibility

* Semantic landmarks (`header`, `nav`, `main`, `footer`), one `h1` per page, ordered headings.
* All inputs labelled; errors linked with `aria-describedby`; required fields marked.
* Mission type selector is a `radiogroup` with arrow-key navigation.
* Analysis progress uses `aria-live="polite"`.
* Visible 2 px blue focus ring with offset on every interactive element.
* Colour is never the only signal: risk badges include text and an icon.
* Contrast ≥ 4.5:1 for text (amber/green/red use darker text variants).

## 10. Interaction patterns

* Primary CTA "Find my journey" — always one primary button per view.
* Option switching on results updates the URL (`?option=`), so a specific journey can be shared.
* Every network state has a designed loading (skeleton matching final layout), empty and error state with a next action.
* Constraint failures show concrete relaxations as buttons that pre-fill the form.

## 11. Multi-modal results (v2)

Order: mission summary (incl. priority) → relax-constraint suggestions (if needed) → headline → **Your options**
(one card per mode: icon, provider, departure → arrival, travel time, changes, ticket (est.), total trip, budget
left / over, buffer, score, risk, category labels; unavailable modes as dashed cards with the reason) → **Our picks**
(Best overall · Cheapest · Fastest · Safest · Best value) → featured journey (dark card) → *Why this option?* →
timeline + map | risk, **Total trip cost** (source badges), main-leg card → **Budget, time and money**
(budget bars with a budget marker, Time-vs-money scatter, compare table) → hotel & reviews → **Email updates** →
local discovery → transparency.

* **Mode identity** is restrained: Lucide icons (Plane, TrainFront, Bus, TramFront, CarFront) on neutral tiles; the
  selected mode turns ink. No per-mode colours — colour stays semantic.
* **Source badges**: LIVE (green), ESTIMATED (amber), YOUR INPUT (blue), CALCULATED (neutral).
* **Time vs money**: two axes, one dot per mode, dashed budget line, lower-left is better; on phones a narrower
  viewBox keeps text legible. Hover/focus shows cost, time, score, risk, time saved vs cheapest, money saved vs fastest.
* **Plan form**: Route (+ travel modes) · Mission (template note) · What matters most? · Timing · Budget & stay
  (food, nights) · Preferences & access · Email updates.
* **Motion**: mode cards stagger in; budget bars grow; scatter points fade in; email confirmations rise in.
  All respect `prefers-reduced-motion`.


## 12. v3 — accounts, routing transparency and calm failure states

**Navbar.** One product name everywhere: **TripMission**. Sticky, 56 px (64 px ≥ md), translucent paper background
with a hairline border. Desktop: logo · How it works · How we decide · My trips — then *Plan a mission* (primary)
and the avatar menu (or *Sign in*). The avatar menu shows photo/initials, name, email, My trips, Saved missions,
Email preferences, Settings, Sign out (demo: "End demo session"). Mobile: logo + avatar + menu button; the panel
slides open (220 ms, ease-out) with links, account block and a full-width *Plan a mission*. A **DEMO MODE** badge
sits next to the logo (≥ 640 px) or at the top of the mobile menu.

**Sign-in modal.** Not a generic SaaS form: a dark two-panel card — left, a drawn door-to-door route with
"Flight, train, bus or road — whichever actually gets you there."; right, the logo, *Plan a real journey with
TripMission*, one line of why, **Continue with Google**, **Continue in Demo Mode** (with "No account needed ·
labelled demo data, no live searches"), and a short privacy note. No other fields. On mobile it becomes a bottom
sheet. Focus is trapped; Esc and the backdrop close it; after sign-in the original action continues with the same
form values.

**My trips (`/trips`).** Tabs Upcoming · Past · Saved. Each trip card: route, venue, date and deadline, recommended
mode icon, Mission Score, risk, total cost and status, *View journey*. Empty states point to *Plan a mission*.

**Profile (`/profile`).** Account (photo, name, email, demo notice), Email preferences (trip summary, departure
reminder, important journey changes, price changes — "where supported"), Travel preferences (home city, priority,
modes, default buffer — pre-fill new missions), Notifications, Sign out. Each section saves independently with an
inline "Saved" note.

**Routing transparency.** *How we routed this trip* sits above the recommendation: calm, icon-led notices
("Ujjain doesn't have a commercial airport…", "only about 62 km by road, so we compared train, bus and road…")
and the hubs discovered (nearest practical airport, railway stations, bus points). Never red, never an error.

**Fares.** Every price says what it is: *Fare* (live or shown by Google Search) or *Estimated fare*; cost lines
carry Live / Estimated / Calculated / Your input badges. Buses without a reported fare read *Estimated bus/transit
route*. Nothing is ever called a confirmed ticket.

**Progress.** The analysis screen speaks product, not plumbing: Checking nearby transport hubs → Finding practical
routes → Comparing travel options → Comparing hotels → Calculating total journey cost → Evaluating arrival buffer &
risk → Calculating mission score → Checking local options.

**How we decided.** Collapsed by default, at the end of results: Live travel data (which kinds, via SerpApi),
Calculated (door-to-door time, total cost, buffer, risk, Mission Score — deterministic engine), Estimated (cab,
fares, check-in time, food where exact prices aren't available). Request counts, timings and raw errors appear only
in a dashed *Developer diagnostics* block when `DEBUG_MODE=true`.

**Degraded data.** Optional sections fail quietly: nearby places → "Nearby recommendations are temporarily
unavailable. Your journey to … is unaffected." (or the section is omitted); missing reviews or fares change labels,
not layout. Essential failures use a single neutral card with *Retry* — no HTTP codes, provider names, exception
text or request IDs.
