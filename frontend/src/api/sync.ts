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

export function useStopIndex() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiFetch<{ status: string }>("/services/index/stop", { method: "POST" }),
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

export function useIndexSkills() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiFetch<{ status: string }>("/services/index-skills", { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sync-status"] }),
  });
}

export function useRagIndex() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (scope: string = "all") =>
      apiFetch<{ status: string }>(`/services/rag-index?scope=${scope}`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sync-status"] }),
  });
}

export function useStopRagIndex() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiFetch<{ status: string }>("/services/rag-index/stop", { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sync-status"] }),
  });
}

export function useStartAgents() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (args: { batchId: string; providerId?: number }) => {
      const qs = args.providerId != null ? `?provider_id=${args.providerId}` : "";
      return apiFetch<{ status: string }>(`/services/agents/${args.batchId}/start${qs}`, { method: "POST" });
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sync-status"] }),
  });
}

export function useStopAgents() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (args: { batchId: string; providerId?: number }) => {
      const qs = args.providerId != null ? `?provider_id=${args.providerId}` : "";
      return apiFetch<{ status: string }>(`/services/agents/${args.batchId}/stop${qs}`, { method: "POST" });
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sync-status"] }),
  });
}

export function useStopIndexSkills() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiFetch<{ status: string }>("/services/index-skills/stop", { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sync-status"] }),
  });
}

export function useEvalHeuristic() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (scope: string) =>
      apiFetch<{ status: string }>(`/quality/eval-heuristic/${scope}`, { method: "POST" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["sync-status"] });
      qc.invalidateQueries({ queryKey: ["eval-stats"] });
    },
  });
}

export function useStopEvalHeuristic() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (scope: string) =>
      apiFetch<{ status: string }>(`/quality/eval-heuristic/${scope}/stop`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["eval-stats"] }),
  });
}

export function useEvalLLM() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (scope: string) =>
      apiFetch<{ status: string }>(`/quality/eval-llm/${scope}`, { method: "POST" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["sync-status"] });
      qc.invalidateQueries({ queryKey: ["eval-stats"] });
    },
  });
}

export function useStopEvalLLM() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (scope: string) =>
      apiFetch<{ status: string }>(`/quality/eval-llm/${scope}/stop`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["eval-stats"] }),
  });
}

export function useEvalStats() {
  return useQuery({
    queryKey: ["eval-stats"],
    queryFn: () => apiFetch<Record<string, any>>("/quality/eval-stats"),
    refetchInterval: 5000,
  });
}
