import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./client";
import type { InstallTarget } from "../types";

export function useTargets() {
  return useQuery({
    queryKey: ["targets"],
    queryFn: () => apiFetch<InstallTarget[]>("/targets"),
  });
}

export function useCreateTarget() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { name: string; description?: string }) =>
      apiFetch<InstallTarget>("/targets", { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["targets"] }),
  });
}
