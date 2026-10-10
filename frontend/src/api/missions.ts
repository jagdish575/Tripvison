import type {
  Delivery, Health, LocationSuggestion, MissionRequest, MissionResult, MissionStatus, MissionTemplate, NotificationPrefs,
  NotificationStatus, RecheckResult,
} from "../types/api";
import { request } from "./client";

export const analyzeMission = (payload: MissionRequest) =>
  request<{ mission_id: string; status: string; mode: "live" | "demo" }>("/missions/analyze", {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const getMission = (id: string) => request<MissionStatus>(`/missions/${encodeURIComponent(id)}`);

export const getRecommendations = (id: string) =>
  request<MissionResult>(`/missions/${encodeURIComponent(id)}/recommendations`);

export const getHealth = () => request<Health>("/health");

export const searchLocations = (q: string) =>
  request<{ results: LocationSuggestion[] }>(`/locations?q=${encodeURIComponent(q)}`);

export const getTemplates = () => request<{ templates: MissionTemplate[] }>("/templates");

export const subscribeNotifications = (id: string, prefs: NotificationPrefs) =>
  request<{ subscription: unknown; summary: Delivery | null }>(`/missions/${encodeURIComponent(id)}/notifications`, {
    method: "POST",
    body: JSON.stringify(prefs),
  });

export const getNotifications = (id: string) =>
  request<NotificationStatus>(`/missions/${encodeURIComponent(id)}/notifications`);

export const sendReminderNow = (id: string) =>
  request<{ results: (Delivery & { email: string })[] }>(`/missions/${encodeURIComponent(id)}/notifications/reminder`, {
    method: "POST",
  });

export const recheckMission = (id: string, simulateDelayMinutes?: number) =>
  request<RecheckResult>(`/missions/${encodeURIComponent(id)}/recheck`, {
    method: "POST",
    body: JSON.stringify(simulateDelayMinutes ? { simulate_delay_minutes: simulateDelayMinutes } : {}),
  });

/** Email previews are served by the backend under the same /api prefix as everything else. */
export const emailPreviewHref = (path: string) =>
  `${(import.meta.env.VITE_API_URL ?? "/api").replace(/\/$/, "")}${path.replace(/^\/api/, "")}`;
