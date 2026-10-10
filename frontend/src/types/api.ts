// Mirrors backend/app/schemas/*.py — the contract between the engine and the UI.

export type MissionType =
  | "interview" | "exam" | "business" | "conference" | "wedding" | "medical" | "vacation" | "family" | "other";

export type Preference =
  | "prefer_direct" | "avoid_early_departure" | "night_before_preferred" | "same_day_only"
  | "breakfast_included" | "free_cancellation";

export type Priority = "balanced" | "save_money" | "save_time" | "avoid_risk";
export type TravelModeChoice = "flight" | "train" | "bus" | "ground";
export type AccessibilityNeed = "wheelchair" | "elevator" | "accessible_hotel" | "accessible_transport";

export interface NotificationPrefs { email: string; trip_summary: boolean; reminder: boolean; changes: boolean }

export interface MissionRequest {
  origin: string;
  destination: string;
  venue?: string | null;
  mission_type: MissionType;
  travel_date: string;
  arrival_deadline: string;
  travelers: number;
  budget: number;
  currency: string;
  min_buffer_minutes: number;
  max_ground_minutes: number;
  hotel_required: boolean;
  min_hotel_rating: number;
  max_stops: number;
  allow_previous_day: boolean;
  preferences: Preference[];
  priority: Priority;
  modes: TravelModeChoice[];
  stay_nights: number;
  food_per_day: number;
  accessibility: AccessibilityNeed[];
  notifications?: NotificationPrefs | null;
}

export interface GeoPoint { lat: number; lng: number }

export interface Airport { code: string; city: string; name: string; country: string; location: GeoPoint }

export interface NearbyHub {
  kind: "airport" | "railway_station" | "bus_point"; code: string | null; name: string; city: string;
  location: GeoPoint | null; distance_km: number | null; road_km: number | null; transfer_minutes: number | null;
  practical: boolean;
}

/** A place the traveller named — a city, town or landmark. It may have no airport. */
export interface ResolvedLocation {
  query: string; city: string; name: string; country: string; location: GeoPoint; code: string | null;
  has_airport: boolean; airports: Airport[]; nearby_airports: NearbyHub[]; railway_stations: string[];
  bus_points: string[]; source: "airport" | "reference" | "geocoded" | "demo";
}

export interface LocationSuggestion { label: string; code: string | null; detail: string; has_airport: boolean }

export interface Layover { airport: string; airport_name?: string | null; duration_minutes: number; overnight: boolean }

export interface FlightSegment {
  airline: string; flight_number: string; departure_airport: string; departure_airport_name?: string | null;
  arrival_airport: string; arrival_airport_name?: string | null; departure_time: string; arrival_time: string;
  duration_minutes: number; often_delayed: boolean; airplane?: string | null;
}

export interface Flight {
  id: string; airline: string; airline_logo?: string | null; flight_numbers: string[];
  departure_airport: string; arrival_airport: string; departure_time: string; arrival_time: string;
  duration_minutes: number; stops: number; layovers: Layover[]; segments: FlightSegment[];
  price: number | null; currency: string; often_delayed: boolean; source: string;
}

export interface ReviewAspect { name: string; positive: number; negative: number; neutral: number; total: number }

export interface Hotel {
  id: string; name: string; rating: number | null; reviews: number | null; price_per_night: number | null;
  total_price: number | null; currency: string; location: GeoPoint | null; address: string | null;
  amenities: string[]; image: string | null; images: string[]; hotel_class: number | null;
  free_cancellation: boolean | null; review_breakdown: ReviewAspect[]; link: string | null;
  check_in_time: string | null; check_out_time: string | null; distance_km: number | null; source: string;
}

export interface Place {
  id: string; name: string; category: string | null; rating: number | null; reviews: number | null;
  address: string | null; location: GeoPoint | null; distance_km: number | null; hours: string | null;
  thumbnail: string | null; price: string | null; source: string;
}

export type PlaceKind = "airport" | "hotel" | "venue" | "station" | "origin";
export interface GroundLeg {
  from_label: string; to_label: string; from_kind: PlaceKind; to_kind: PlaceKind;
  depart_at: string; arrive_at: string; duration_minutes: number; typical_max_minutes: number | null;
  distance_km: number; mode: string; estimated: boolean; cost: number; day: "before" | "mission";
}

export type TimelineKind = "depart" | "land" | "exit" | "transfer" | "hotel" | "leave" | "arrive" | "deadline" | "board" | "change";

export interface TimelineEvent {
  time: string; kind: TimelineKind; title: string; detail: string | null;
  duration_to_next_minutes: number | null; mode_to_next: string | null; distance_to_next_km: number | null;
}

export type SourceType = "live" | "estimated" | "user_provided" | "calculated";
export interface CostItem { key: "ticket" | "ground" | "hotel" | "food" | "other"; label: string; amount: number; source: SourceType; detail: string | null }

export interface CostBreakdown {
  ticket: number | null; hotel: number | null; ground: number; food: number; total: number | null; currency: string;
  ground_estimated: boolean; hotel_nights: number; hotel_per_night: number | null; ticket_price_known: boolean;
  ticket_source: SourceType; items: CostItem[]; budget: number | null; budget_remaining: number | null;
}

export type Mode = "flight" | "train" | "bus" | "transit" | "ground";
export type Confidence = "high" | "medium" | "low";

export interface MainLeg {
  mode: Mode; provider: string | null; title: string; references: string[]; departure_label: string;
  arrival_label: string; departure_time: string; arrival_time: string; duration_minutes: number; stops: number;
  transfers: number; distance_km: number | null; schedule_source: SourceType; note: string | null;
  data_source: string | null; fare_label: string;
}

export interface TransitSegment {
  mode: string; name: string; operator: string | null; from_stop: string | null; to_stop: string | null;
  depart_at: string | null; arrive_at: string | null; duration_minutes: number; stops_count: number; distance_km: number | null;
}

export interface Transit {
  id: string; mode: string; title: string; provider: string | null; departure_time: string; arrival_time: string;
  duration_minutes: number; distance_km: number | null; transfers: number; walking_minutes: number;
  segments: TransitSegment[]; fare: number | null; source: string; fare_source?: string | null; fare_seller?: string | null;
}

export interface AccessibilityNote { need: string; status: "available" | "requested" | "unavailable"; detail: string }

export interface ArrivalInfo {
  venue_arrival: string; deadline: string; buffer_minutes: number; required_buffer_minutes: number;
  leave_hotel_at: string | null; effective_buffer_minutes: number;
}

export type Impact = "positive" | "negative" | "neutral";
export interface ScoreFactor { key: string; label: string; impact: Impact; detail: string | null }

export interface ScoreBreakdown {
  overall: number; arrival: number; budget: number; ground: number; location: number | null; duration: number;
  review: number | null; convenience: number; value: number; weights: Record<string, number>; priority: Priority;
  factors: ScoreFactor[];
}

export type RiskLevel = "LOW" | "MEDIUM" | "HIGH";
export interface RiskFactor {
  key: string; severity: "low" | "medium" | "high"; points: number; title: string; detail: string;
  recommendation: string | null;
}
export interface RiskAssessment {
  level: RiskLevel; score: number; factors: RiskFactor[]; strengths: string[]; recommendations: string[];
}

export interface ConstraintCheck {
  feasible: boolean; within_budget: boolean; buffer_ok: boolean; ground_ok: boolean; rating_ok: boolean; all_ok: boolean;
}

export type Strategy = "same_day" | "night_before";
export type Category = "recommended" | "cheapest" | "fastest" | "safest" | "best_value";

export interface Itinerary {
  id: string; mode: Mode; strategy: Strategy; main: MainLeg; flight: Flight | null; transit: Transit | null;
  hotel: Hotel | null; hotel_check_in: string | null;
  hotel_check_out: string | null; legs: GroundLeg[]; timeline: TimelineEvent[]; cost: CostBreakdown;
  arrival: ArrivalInfo; ground_minutes_mission_day: number; ground_minutes_before: number;
  total_travel_minutes: number; door_to_venue_minutes: number; scores: ScoreBreakdown; risk: RiskAssessment;
  constraints: ConstraintCheck; tags: Category[]; data_quality: string[]; confidence: Confidence;
  practicality: "high" | "low"; accessibility: AccessibilityNote[];
}

export interface Suggestion { kind: string; title: string; detail: string; unlocks: string | null; patch: Partial<MissionRequest> }

export interface ReviewSignal { aspect: string; mentions: number; positive: number; negative: number; source: string }
export interface ReviewQuote { text: string; rating: number | null; date: string | null; aspect: string | null; sentiment: Impact }
export interface ReviewInsights {
  hotel_id: string; hotel_name: string; strengths: ReviewSignal[]; concerns: ReviewSignal[]; quotes: ReviewQuote[];
  topics: { keyword: string; mentions: number }[]; review_count: number; rating: number | null; sources: string[];
}

export interface PlaceGroup { category: string; label: string; reason: string; items: Place[] }

export interface Explanation { text: string; source: "ai" | "rules"; model: string | null; note: string | null }

export interface ApiCall { api: string; purpose: string; cached: boolean; ok: boolean; ms: number; error: string | null }
/** `calls`, `live_calls` and `cache_hits` are developer diagnostics — null unless the server runs with DEBUG_MODE. */
export interface DataSources {
  mode: "live" | "demo"; calls: ApiCall[] | null; live_calls: number | null; cache_hits: number | null; fetched_at: string;
}

export interface MethodNote { key: string; label: string; kind: "live" | "calculated" | "estimated" | "demo"; detail: string }

export interface RouteNotice { kind: string; message: string }

export interface RoutePlan {
  distance_km: number; road_km: number; road_minutes: number; origin_airport: NearbyHub | null;
  destination_airport: NearbyHub | null; origin_has_airport: boolean; destination_has_airport: boolean;
  flight: "searched" | "skipped" | "not_requested"; flight_practicality: "high" | "low" | null;
  flight_reason: string | null; ground_search: boolean; ground_reason: string | null; modes_requested: string[];
  modes_evaluated: string[]; notices: RouteNotice[]; railway_stations: string[]; bus_points: string[];
}

export interface VenueInfo { name: string; address: string | null; location: GeoPoint; resolved: boolean }

export interface MissionSummary {
  origin: ResolvedLocation; destination: ResolvedLocation; origin_airport: Airport | null;
  destination_airport: Airport | null; venue: VenueInfo; mission_type: MissionType; travel_date: string;
  arrival_deadline: string; travelers: number; budget: number; currency: string; min_buffer_minutes: number;
  max_ground_minutes: number; hotel_required: boolean; min_hotel_rating: number; max_stops: number; preferences: string[];
  priority: Priority; modes: TravelModeChoice[]; stay_nights: number; food_per_day: number; accessibility: string[];
}

export interface ModeSummary {
  mode: Mode; available: boolean; best_id: string | null; options: number; reason: string | null;
  confidence: Confidence | null; schedule_source: string | null; fare_source: string | null;
}

export interface Tradeoff { cheapest_id: string; fastest_id: string; extra_cost: number; time_saved_minutes: number; sentence: string }
export interface OptionDelta { money_saved_vs_fastest: number | null; time_saved_vs_cheapest_minutes: number | null }

export interface FunnelStats {
  transit_found: number; fares_matched?: number;
  flights_found: number; flights_feasible: number; flights_shortlisted: number; hotels_found: number;
  hotels_shortlisted: number; routes_calculated: number; itineraries_scored: number;
}

export interface MissionResult {
  mission_id: string; status: "complete" | "partial" | "no_options"; mode: "live" | "demo";
  mission: MissionSummary; categories: Partial<Record<Category, string>>; itineraries: Itinerary[];
  modes: ModeSummary[]; tradeoff: Tradeoff | null; deltas: Record<string, OptionDelta>;
  suggestions: Suggestion[]; review_insights: Record<string, ReviewInsights>; places: PlaceGroup[];
  explanation: Explanation | null; funnel: FunnelStats; data_sources: DataSources; warnings: string[]; headline: string;
  route: RoutePlan | null; methodology: MethodNote[]; diagnostics: Record<string, unknown> | null;
}

export type Stage = "resolve" | "flights" | "arrival" | "hotels" | "ground" | "scoring" | "reviews" | "places" | "explain";

export interface MissionStatus {
  mission_id: string; status: "queued" | "running" | "complete" | "failed"; mode: "live" | "demo";
  progress: { stage: Stage | "queued" | "done"; completed: Stage[]; counts: Record<string, number>; message: string };
  input: MissionRequest; error: { code: string; message: string } | null; created_at: string;
}

export interface Health {
  status: string; version: string; demo_mode: boolean; debug_mode: boolean; google_auth: boolean;
  serpapi_configured: boolean; ai_configured: boolean;
  ai_provider: string | null; ai_model: string | null; database: string; cache: string; ready: boolean;
  email_delivery: "smtp" | "resend" | "preview";
}

export interface MissionTemplate {
  mission_type: MissionType; label: string; priority: Priority; min_buffer_minutes: number; max_stops: number;
  hotel_required: boolean; risk_tolerance: string; highlights: string[];
}

export interface Delivery {
  status: "sent" | "preview" | "failed" | "pending" | "skipped"; message: string;
  message_id?: string | null; preview_url?: string | null;
}

export interface NotificationStatus {
  subscriptions: (NotificationPrefs & { departure_at: string | null; reminder_sent_at: string | null; active: boolean })[];
  messages: { id: string; kind: "summary" | "reminder" | "change"; to: string; subject: string; status: string;
              provider: string; created_at: string; preview_url: string }[];
  delivery: "smtp" | "resend" | "preview";
}

export interface ChangeEntry { field: string; label: string; before: unknown; after: unknown; meaningful: boolean }

export interface RecheckResult {
  report: { meaningful: boolean; journey_unavailable: boolean; changes: ChangeEntry[] } | null;
  alerts: { email: string; meaningful: boolean; alert: Delivery | null }[];
  simulated: boolean;
}

// ------------------------------------------------------------------ accounts
export interface User { id: string; email: string | null; name: string; picture: string | null; is_demo: boolean }

export interface AuthConfig {
  google_client_id: string | null; google_enabled: boolean; demo_enabled: boolean; auth_required: boolean;
}

export interface Trip {
  mission_id: string; status: MissionStatus["status"]; mode: "live" | "demo"; result_status: MissionResult["status"] | null;
  mission_type: MissionType; origin: string; destination: string; venue: string | null; travel_date: string;
  arrival_deadline: string; budget: number; currency: string; created_at: string; upcoming: boolean; saved: boolean;
  headline: string | null;
  recommended: { mode: Mode; total_cost: number | null; score: number | null; risk: RiskLevel | null; buffer_minutes: number | null } | null;
}

export interface Preferences {
  email: { trip_summary: boolean; departure_reminder: boolean; journey_changes: boolean; price_changes: boolean };
  notifications: { enabled: boolean };
  travel: { home_city: string | null; priority: Priority; modes: TravelModeChoice[]; buffer_minutes: number };
}
