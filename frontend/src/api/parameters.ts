import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./client";
import type { McpParameter } from "../types";

export function useParameters(mcp_service_id: string) {
  return useQuery({
    queryKey: ["parameters", mcp_service_id],
    queryFn: () => apiFetch<McpParameter[]>(`/parameters/${mcp_service_id}`),
    enabled: !!mcp_service_id,
  });
}

export function useDetectParameters(mcp_service_id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiFetch<{ status: string; detected: number; added: number }>(
        `/parameters/${mcp_service_id}/detect`,
        { method: "POST" }
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["parameters", mcp_service_id] });
    },
  });
}

export function useAddParameter(mcp_service_id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { name: string; description?: string; is_required?: boolean; is_secret?: boolean }) =>
      apiFetch<McpParameter>(`/parameters/${mcp_service_id}`, {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["parameters", mcp_service_id] });
    },
  });
}

export function useDeleteParameter() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (paramId: string) =>
      apiFetch<{ status: string }>(`/parameters/${paramId}`, { method: "DELETE" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["parameters"] });
    },
  });
}
