import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./client";
import type { InstallTarget, InstallMode } from "../types";

export function useTargets() {
  return useQuery({
    queryKey: ["targets"],
    queryFn: () => apiFetch<InstallTarget[]>("/targets"),
  });
}

export function useCreateTarget() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { name: string; description?: string; modes?: InstallMode[] }) =>
      apiFetch<InstallTarget>("/targets", { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["targets"] }),
  });
}

export function useUpdateTarget() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: { id: string; name?: string; description?: string; modes?: InstallMode[] }) =>
      apiFetch<InstallTarget>(`/targets/${id}`, { method: "PUT", body: JSON.stringify(body) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["targets"] }),
  });
}
