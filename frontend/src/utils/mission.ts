import {
  Briefcase, Coffee, GraduationCap, HeartHandshake, Laptop, Landmark, Camera, Pill, Presentation, Scissors, Gift,
  Stethoscope, TreePalm, Trees, Users, Utensils, PenLine, Banknote, Compass, Plane, TrainFront, Bus, CarFront,
  TramFront, Scale, Wallet, Zap, ShieldCheck, Trophy, Gem, type LucideIcon,
} from "lucide-react";
import type {
  Category, MissionRequest, MissionType, Mode, Preference, Priority, RiskLevel, SourceType, Stage, TravelModeChoice,
} from "../types/api";
import { todayIso } from "./format";

export const MISSION_TYPES: { id: MissionType; label: string; noun: string; icon: LucideIcon }[] = [
  { id: "interview", label: "Interview", noun: "interview", icon: Briefcase },
  { id: "exam", label: "Exam", noun: "exam", icon: GraduationCap },
  { id: "business", label: "Business", noun: "meeting", icon: Laptop },
  { id: "conference", label: "Conference", noun: "conference", icon: Presentation },
  { id: "wedding", label: "Wedding", noun: "wedding", icon: HeartHandshake },
  { id: "medical", label: "Medical", noun: "appointment", icon: Stethoscope },
  { id: "vacation", label: "Vacation", noun: "trip", icon: TreePalm },
  { id: "family", label: "Family", noun: "family visit", icon: Users },
  { id: "other", label: "Other", noun: "plans", icon: Compass },
];

export const missionMeta = (type: MissionType) => MISSION_TYPES.find((m) => m.id === type) ?? MISSION_TYPES[8];

export const PREFERENCES: { id: Preference; label: string; hint: string }[] = [
  { id: "prefer_direct", label: "Prefer direct flights", hint: "+3 for nonstop, −3 for connections" },
  { id: "avoid_early_departure", label: "Avoid departures before 6 am", hint: "−4 for very early flights" },
  { id: "night_before_preferred", label: "I'd rather arrive the night before", hint: "+4 for night-before journeys" },
  { id: "same_day_only", label: "Same-day travel only", hint: "Skips day-before flights" },
  { id: "breakfast_included", label: "Breakfast at the hotel", hint: "+3 if the hotel lists breakfast" },
  { id: "free_cancellation", label: "Free cancellation", hint: "+3 if the hotel offers it" },
];

export const STAGE_LABELS: Record<Stage, string> = {
  resolve: "Checking nearby transport hubs",
  flights: "Finding practical routes",
  arrival: "Comparing travel options",
  hotels: "Comparing hotels",
  ground: "Calculating total journey cost",
  scoring: "Evaluating arrival buffer & risk",
  reviews: "Calculating mission score",
  places: "Checking local options",
  explain: "Explaining the recommendation",
};
export const STAGES = Object.keys(STAGE_LABELS) as Stage[];

export const CATEGORY_META: Record<Category, { label: string; hint: string; icon: LucideIcon }> = {
  recommended: { label: "Best overall", hint: "Highest Mission Score", icon: Trophy },
  cheapest: { label: "Cheapest", hint: "Lowest total trip cost that still arrives on time", icon: Wallet },
  fastest: { label: "Fastest", hint: "Least time spent travelling", icon: Zap },
  safest: { label: "Safest", hint: "Lowest risk of arriving late", icon: ShieldCheck },
  best_value: { label: "Best value", hint: "Best balance of cost, time and reliability", icon: Gem },
};

export const CATEGORY_ORDER: Category[] = ["recommended", "cheapest", "fastest", "safest", "best_value"];

export const MODE_META: Record<Mode, { label: string; noun: string; icon: LucideIcon }> = {
  flight: { label: "Flight", noun: "flight", icon: Plane },
  train: { label: "Train", noun: "train", icon: TrainFront },
  bus: { label: "Bus", noun: "bus", icon: Bus },
  transit: { label: "Public transport", noun: "public transport", icon: TramFront },
  ground: { label: "Road trip", noun: "drive", icon: CarFront },
};

export const MODE_CHOICES: { id: TravelModeChoice; label: string; hint: string }[] = [
  { id: "flight", label: "Flight", hint: "Live fares · includes airport transfers door to door" },
  { id: "train", label: "Train", hint: "Live schedules · estimated fare" },
  { id: "bus", label: "Bus", hint: "Estimated bus/transit routes · estimated fare" },
  { id: "ground", label: "Road trip", hint: "Live road route · estimated cab fare" },
];

export const PRIORITIES: { id: Priority; label: string; hint: string; icon: LucideIcon }[] = [
  { id: "balanced", label: "Balanced", hint: "Reliability first, then cost and time", icon: Scale },
  { id: "save_money", label: "Save money", hint: "Cost weighs 45% of the score", icon: Wallet },
  { id: "save_time", label: "Save time", hint: "Travel time weighs 40%", icon: Zap },
  { id: "avoid_risk", label: "Avoid risk", hint: "Arrival reliability weighs 40%", icon: ShieldCheck },
];

export const SOURCE_META: Record<SourceType, { label: string; hint: string }> = {
  live: { label: "Live", hint: "From a live search just now" },
  estimated: { label: "Estimated", hint: "Calculated from a documented model, not a quoted price" },
  user_provided: { label: "Your input", hint: "Based on a value you entered" },
  calculated: { label: "Calculated", hint: "Derived from live data" },
};

export const RISK_COPY: Record<RiskLevel, { label: string; tone: string }> = {
  LOW: { label: "Low risk", tone: "green" },
  MEDIUM: { label: "Medium risk", tone: "amber" },
  HIGH: { label: "High risk", tone: "red" },
};

export const PLACE_ICONS: Record<string, LucideIcon> = {
  cafe: Coffee, pharmacy: Pill, restaurant: Utensils, stationery: PenLine, coworking: Laptop, atm: Banknote,
  salon: Scissors, gift: Gift, attraction: Landmark, viewpoint: Camera, park: Trees,
};

export function defaultMission(): MissionRequest {
  return {
    origin: "Indore",
    destination: "Bangalore",
    venue: "Manyata Tech Park",
    mission_type: "interview",
    travel_date: todayIso(2),
    arrival_deadline: "10:00",
    travelers: 1,
    budget: 10000,
    currency: "INR",
    min_buffer_minutes: 60,
    max_ground_minutes: 90,
    hotel_required: true,
    min_hotel_rating: 3.5,
    max_stops: 1,
    allow_previous_day: true,
    preferences: [],
    priority: "avoid_risk",
    modes: ["flight", "train", "bus", "ground"],
    stay_nights: 1,
    food_per_day: 500,
    accessibility: [],
    notifications: null,
  };
}

const DRAFT_KEY = "tripmission:draft";

export function saveDraft(draft: MissionRequest): void {
  try {
    sessionStorage.setItem(DRAFT_KEY, JSON.stringify(draft));
  } catch {
    /* storage unavailable — non-critical */
  }
}

export function loadDraft(): MissionRequest | null {
  try {
    const raw = sessionStorage.getItem(DRAFT_KEY);
    if (!raw) return null;
    const draft = { ...defaultMission(), ...(JSON.parse(raw) as Partial<MissionRequest>) };
    if (draft.travel_date < todayIso(0)) draft.travel_date = todayIso(2);
    return draft;
  } catch {
    return null;
  }
}
