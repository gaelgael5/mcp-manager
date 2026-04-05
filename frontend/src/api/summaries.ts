import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./client";
import type { McpSummary, PaginatedResponse } from "../types";

export function useSummaries(mcp_service_id?: string) {
  const params = new URLSearchParams();
  if (mcp_service_id) params.set("mcp_service_id", mcp_service_id);
  const qs = params.toString();
  return useQuery({
    queryKey: ["summaries", qs],
    queryFn: () => apiFetch<PaginatedResponse<McpSummary>>(`/summaries?${qs}`),
    enabled: !!mcp_service_id,
  });
}

export function useGenerateSummary(mcp_service_id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiFetch<{ status: string; cultures: string[] }>(`/summaries/generate/${mcp_service_id}`, { method: "POST" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["summaries"] });
    },
  });
}
