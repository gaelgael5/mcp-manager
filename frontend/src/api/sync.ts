import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./client";
import type { SyncStatus } from "../types";

export function useSyncStatus() {
  return useQuery({
    queryKey: ["sync-status"],
    queryFn: () => apiFetch<SyncStatus>("/services/sync/status"),
    refetchInterval: 5000,
  });
}

export function useTriggerSync() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (source?: string) => {
      const qs = source ? `?source=${source}` : "";
      return apiFetch<{ status: string }>(`/services/sync${qs}`, { method: "POST" });
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sync-status"] }),
  });
}

export function useTriggerIndex() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (limit: number = 500) =>
      apiFetch<{ status: string }>(`/services/index?limit=${limit}`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sync-status"] }),
  });
}

export function useTriggerScrapeSkills() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (opts?: { limit?: number; skipSummaries?: boolean }) => {
      const params = new URLSearchParams();
      if (opts?.limit) params.set("limit", String(opts.limit));
      if (opts?.skipSummaries) params.set("skip_summaries", "true");
      const qs = params.toString() ? `?${params.toString()}` : "";
      return apiFetch<{ status: string }>(`/services/scrape-skills${qs}`, { method: "POST" });
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sync-status"] }),
  });
}

export function useEnrichSkills() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiFetch<{ status: string }>("/services/enrich-skills", { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sync-status"] }),
  });
}

export function useStopEnrichSkills() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiFetch<{ status: string }>("/services/enrich-skills/stop", { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sync-status"] }),
  });
}
