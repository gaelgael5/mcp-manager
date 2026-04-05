import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./client";
import type { McpInstallation, PaginatedResponse } from "../types";

export function useInstallations(mcp_service_id?: string) {
  const params = new URLSearchParams();
  if (mcp_service_id) params.set("mcp_service_id", mcp_service_id);
  const qs = params.toString();
  return useQuery({
    queryKey: ["installations", qs],
    queryFn: () => apiFetch<PaginatedResponse<McpInstallation>>(`/installations?${qs}`),
    enabled: !!mcp_service_id,
  });
}

export function useGenerateInstallations(mcp_service_id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiFetch<{ status: string; targets: string[] }>(`/installations/generate/${mcp_service_id}`, { method: "POST" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["installations"] });
    },
  });
}
