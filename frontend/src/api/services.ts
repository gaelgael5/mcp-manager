import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./client";
import type { McpService, PaginatedResponse } from "../types";

interface ServiceFilters {
  page?: number;
  per_page?: number;
  source_type?: string;
  category?: string;
  transport?: string;
  repo_status?: string;
  has_summaries?: string;
  search?: string;
  is_deprecated?: boolean;
}

export function useServices(filters: ServiceFilters = {}) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([k, v]) => {
    if (v !== undefined && v !== "") params.set(k, String(v));
  });
  const qs = params.toString();
  return useQuery({
    queryKey: ["services", qs],
    queryFn: () => apiFetch<PaginatedResponse<McpService>>(`/services?${qs}`),
  });
}

export function useService(id: string) {
  return useQuery({
    queryKey: ["service", id],
    queryFn: () => apiFetch<McpService>(`/services/${id}`),
    enabled: !!id,
  });
}

export function useUpdateService(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { source_url?: string; doc_url?: string; transport?: string; category?: string }) =>
      apiFetch<McpService>(`/services/${id}`, {
        method: "PATCH",
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["service", id] });
      qc.invalidateQueries({ queryKey: ["services"] });
    },
  });
}
