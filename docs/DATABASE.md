# TripMission — Database Design

PostgreSQL in production (`postgresql+psycopg://…`), SQLite for zero-setup local development
(`backend/tripvision.db` — the file keeps its original name so existing local data isn't orphaned).
JSON columns use SQLAlchemy's generic `JSON` type (`JSON` on PostgreSQL, `TEXT` on SQLite).

**Migrations.** On startup `init_db()` runs `create_all()` (new tables) and then `_add_missing_columns()`, an
additive forward migration: any nullable column a model declares but the database lacks is added with
`ALTER TABLE … ADD COLUMN`, plus its indexes. It never drops, renames or rewrites anything, so existing SQLite and
PostgreSQL databases upgrade in place without data loss. Every schema change so far (users, ownership, travel
options, email) has been additive. A destructive change (rename/drop/type change) would need Alembic — that is
the documented upgrade path and is deliberately not in place yet.

## Entity relationship

```
users 1───1 user_preferences            (profile, email + notification + travel preferences)
  │
  ├──* saved_missions *───1 missions    (unique per user + mission)
  └──* missions (user_id; null for missions created before sign-in existed — kept, but not
                                      viewable while AUTH_REQUIRED=true, since nobody owns them)

missions 1───1 mission_preferences
    │
    ├──* flight_options
    ├──* hotel_options ──* reviews
    ├──* places
    ├──* itineraries ──(flight_option_id, hotel_option_id)
    └──* recommendations ──1 itinerary
search_cache (independent)
```

## Tables

### users
| Column | Type | Notes |
|--------|------|-------|
| id | varchar(36) PK | UUID4 |
| google_sub | varchar(64) unique null | Google account subject — the stable identity; null for demo users |
| email | varchar(254) null, indexed | Verified Google email; null for demo users |
| name | varchar(120) | |
| picture | varchar(500) null | Google profile photo URL |
| is_demo | bool | Anonymous "Continue in Demo Mode" session |
| created_at / last_login_at | timestamptz | |

### user_preferences
One row per user (created on first read). Email: `email_trip_summary`, `email_departure_reminder`,
`email_journey_changes`, `email_price_changes` (default off — only where supported). Notifications:
`notifications_enabled`. Travel defaults for new missions: `home_city`, `default_priority`, `default_modes` (JSON),
`default_buffer_minutes`. `updated_at`.

### saved_missions
`id` PK, `user_id` FK → users (cascade), `mission_id` FK → missions (cascade), `saved_at`. Unique
`(user_id, mission_id)`.

### Ownership and isolation
`missions.user_id` (FK → users, `ON DELETE SET NULL`, indexed). Every read path filters by it: another user gets
`404`, no session gets `401`. `MissionRepository.for_user()` powers *My trips*.


### missions
| Column | Type | Notes |
|--------|------|-------|
| id | varchar(36) PK | UUID4 |
| created_at / updated_at | timestamptz | |
| status | varchar(16) | `queued`, `running`, `complete`, `failed` |
| mode | varchar(8) | `live` or `demo` — never mixed |
| mission_type | varchar(16) | interview, exam, … |
| origin_query / destination_query / venue_query | varchar | Raw user input |
| origin_airport / destination_airport | varchar(3) | Resolved IATA |
| travel_date | date | Mission day |
| arrival_deadline | time | Destination local time |
| travelers | int | |
| budget | numeric(12,2) | Total for all travellers |
| currency | varchar(3) | |
| progress | JSON | `{stage, completed[], counts{}, message}` |
| result | JSON | Snapshot of `MissionResult` served to the UI (denormalised for fast reads) |
| error | JSON | `{code, message}` when failed |
| client_ref | varchar(64) null | Reserved |

### mission_preferences
`mission_id` (PK/FK), `min_buffer_minutes`, `max_ground_minutes`, `hotel_required`,
`min_hotel_rating`, `max_stops`, `allow_previous_day`, `preferences` (JSON list of tags).

### flight_options
`id` PK, `mission_id` FK, `external_id`, `airline`, `flight_numbers` (JSON), `departure_airport`,
`arrival_airport`, `departure_time`, `arrival_time`, `duration_minutes`, `stops`, `price`, `currency`,
`often_delayed`, `strategy` (`same_day`/`night_before`), `shortlisted` bool, `data` (JSON normalised record).

### hotel_options
`id` PK, `mission_id` FK, `external_id`, `name`, `rating`, `review_count`, `price_per_night`,
`total_price`, `currency`, `latitude`, `longitude`, `distance_km`, `check_in_date`, `check_out_date`,
`shortlisted`, `data` (JSON).

### places
`id` PK, `mission_id` FK, `category`, `name`, `rating`, `review_count`, `address`, `latitude`,
`longitude`, `distance_km`, `data` (JSON).

### reviews
`id` PK, `mission_id` FK, `hotel_option_id` FK null, `source` (`google_maps_reviews`), `rating`,
`text`, `published` (varchar — provider relative date), `author`.

### itineraries
`pk` PK (UUID), `id` (engine id, e.g. `nb-QP1384-demo-lakev`, unique within a mission), `mission_id` FK, `flight_option_id` FK, `hotel_option_id`
FK null, `strategy`, `total_cost`, `venue_arrival`, `buffer_minutes`, `overall_score`,
`risk_level`, `risk_score`, `feasible`, `satisfies_constraints`, `data` (JSON full itinerary).

### recommendations
`id` PK, `mission_id` FK, `category` (`recommended`, `cheapest`, `fastest`, `safest`),
`itinerary_pk` FK, `explanation` (text, recommended only), `explanation_source` (`ai`/`rules`).
Unique `(mission_id, category)`.

### search_cache
| Column | Type | Notes |
|--------|------|-------|
| key | varchar(64) PK | SHA-256 of `engine` + sorted params (API key excluded) |
| engine | varchar(40) | e.g. `google_flights` |
| created_at | timestamptz | |
| expires_at | timestamptz | Indexed; expired rows are ignored and overwritten |
| payload | JSON | Raw SerpApi response |

## Indexes
* `missions(created_at)`, `flight_options(mission_id)`, `hotel_options(mission_id)`,
  `itineraries(mission_id, overall_score)`, `search_cache(expires_at)`.

## Data retention
Missions contain no personal identifiers beyond free-text venue names. Cache rows expire by TTL
(30 min flights, 60 min hotels, 24 h directions/places/reviews, 7 days geocoding).

## v2 tables and columns

* `mission_preferences` + `priority`, `modes`, `stay_nights`, `food_per_day`, `accessibility`
* `itineraries` + `mode`, `travel_option_id`
* **`travel_options`** — trains, buses, public transport and road trips: `mode`, `title`, `provider`,
  `departure_time`, `arrival_time`, `duration_minutes`, `transfers`, `distance_km`, `fare`, `fare_source`
  (`live`/`estimated`), `schedule_source`, `data`.
* **`email_subscriptions`** — `mission_id`, `email`, `trip_summary`, `reminder`, `changes`, `departure_at` (local),
  `utc_offset_minutes`, `reminder_sent_at`, `snapshot` (journey facts last emailed — used for change detection), `active`.
  Unique `(mission_id, email)`.
* **`email_messages`** — every email generated: `kind` (summary/reminder/change), `to_email`, `subject`, `html`,
  `text`, `provider`, `status` (sent/preview/failed), sanitised `error`.

New nullable columns are added automatically at startup (`core/database._add_missing_columns`), so existing
SQLite/PostgreSQL databases upgrade in place. A re-check replaces analysis rows but keeps subscriptions and emails.


## Mapping of product entities to tables

| Entity | Table(s) |
|--------|----------|
| User / Profile | `users` |
| Mission | `missions` (+ `result` JSON snapshot) |
| MissionPreference | `mission_preferences` |
| MissionTravelOption | `travel_options` (train/bus/road) and `flight_options` |
| MissionResult | `missions.result`, `itineraries`, `recommendations` |
| EmailPreference | `user_preferences` (email columns) and per-mission `email_subscriptions` |
| Notification | `email_messages` (every generated summary / reminder / change alert, with delivery status) |
| SavedMission | `saved_missions` |

Kept deliberately small: one preferences row instead of separate profile/notification tables, and the result
snapshot is denormalised for fast reads while the normalised rows support analytics.
