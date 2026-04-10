import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./client";

export interface Language {
  code: string;
  name: string;
  is_active: boolean;
  display_order: number;
}

export function useLanguages() {
  return useQuery({
    queryKey: ["languages"],
    queryFn: () => apiFetch<Language[]>("/settings/languages"),
  });
}

export function useUpdateLanguage() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: { code: string; patch: Partial<Omit<Language, "code">> }) =>
      apiFetch<Language>(`/settings/languages/${vars.code}`, {
        method: "PATCH",
        body: JSON.stringify(vars.patch),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["languages"] });
      qc.invalidateQueries({ queryKey: ["prompts"] });
      qc.invalidateQueries({ queryKey: ["stats"] });
    },
  });
}

export function useCreateLanguage() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Language) =>
      apiFetch<Language>("/settings/languages", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["languages"] }),
  });
}

export function useDeleteLanguage() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (code: string) =>
      apiFetch<{ status: string }>(`/settings/languages/${code}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["languages"] }),
  });
}
