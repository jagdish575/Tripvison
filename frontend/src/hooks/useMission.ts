import { useMutation, useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { analyzeMission, getHealth, getMission, getRecommendations, getTemplates } from "../api/missions";
import type { ApiError } from "../api/client";
import type { MissionRequest } from "../types/api";
import { saveDraft } from "../utils/mission";

export function useHealth() {
  return useQuery({ queryKey: ["health"], queryFn: getHealth, staleTime: 60_000, retry: 1 });
}

export function useMissionStatus(id: string | undefined) {
  return useQuery({
    queryKey: ["mission", id],
    queryFn: () => getMission(id!),
    enabled: Boolean(id),
    refetchInterval: (query) => {
      if (query.state.error) return false;
      const status = query.state.data?.status;
      return status === "complete" || status === "failed" ? false : 700;
    },
    retry: (count, error) => (error as ApiError).status !== 404 && count < 3,
  });
}

export function useRecommendations(id: string | undefined) {
  return useQuery({
    queryKey: ["recommendations", id],
    queryFn: () => getRecommendations(id!),
    enabled: Boolean(id),
    staleTime: Infinity,
    retry: (count, error) => ![404, 409].includes((error as ApiError).status) && count < 2,
  });
}

/** Starts an analysis and moves to the analysis screen. `start()` asks the traveller to sign in first when
 * needed (or when the server says the session expired) and then continues with the same mission — the form
 * is also kept in sessionStorage, so nothing typed is lost. */
export function useStartMission() {
  const navigate = useNavigate();
  const { requireAuth, signInThen } = useAuth();
  const mutation = useMutation<{ mission_id: string }, ApiError, MissionRequest>({
    mutationFn: analyzeMission,
    onMutate: (payload) => saveDraft(payload),
    onSuccess: (data) => navigate(`/analyzing/${data.mission_id}`),
    onError: (error, payload) => {
      if (error.code === "auth_required") signInThen(() => mutation.mutate(payload), "plan");
    },
  });
  const start = (payload: MissionRequest) => {
    saveDraft(payload);
    requireAuth(() => mutation.mutate(payload), "plan");
  };
  /** The error to show — sign-in prompts are handled by the modal, not shown as errors. */
  const visibleError = mutation.error && mutation.error.code !== "auth_required" ? mutation.error : null;
  return { ...mutation, start, visibleError };
}

/** Every "Plan a mission" entry point: signed in → the plan page; signed out → the Google / Demo sign-in popup,
 * then the plan page. (The /plan route is also protected, so a typed URL can't skip sign-in.) */
export function usePlanMission() {
  const navigate = useNavigate();
  const { requireAuth } = useAuth();
  return () => requireAuth(() => navigate("/plan"), "plan");
}

export function useTemplates() {
  return useQuery({ queryKey: ["templates"], queryFn: getTemplates, staleTime: Infinity, retry: 1 });
}
