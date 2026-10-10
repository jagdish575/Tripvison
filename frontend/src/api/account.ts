import type { AuthConfig, Preferences, Trip, User } from "../types/api";
import { request } from "./client";

export const getAuthConfig = () => request<AuthConfig>("/auth/config");
export const getMe = () => request<{ user: User | null }>("/auth/me");
export const signInWithGoogle = (credential: string) =>
  request<{ user: User }>("/auth/google", { method: "POST", body: JSON.stringify({ credential }) });
export const signInDemo = () => request<{ user: User }>("/auth/demo", { method: "POST" });
export const signOut = () => request<{ ok: boolean }>("/auth/logout", { method: "POST" });

export const getTrips = () => request<{ trips: Trip[] }>("/me/trips");
export const saveMission = (id: string) =>
  request<{ saved: boolean; email: { status: string } | null }>(`/missions/${encodeURIComponent(id)}/save`, { method: "POST" });
export const unsaveMission = (id: string) =>
  request<{ saved: boolean }>(`/missions/${encodeURIComponent(id)}/save`, { method: "DELETE" });

export const getPreferences = () => request<{ preferences: Preferences; user: User }>("/me/preferences");
export const updatePreferences = (patch: Partial<Preferences>) =>
  request<{ preferences: Preferences }>("/me/preferences", { method: "PUT", body: JSON.stringify(patch) });
