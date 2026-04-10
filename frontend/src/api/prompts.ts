import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./client";

export type PromptKind = "summarize" | "skill_summary" | "source_summary";

export interface PromptListItem {
  kind: PromptKind;
  language: string;
  language_name: string;
  is_active: boolean;
  exists: boolean;
  size: number;
}

export interface PromptContent {
  kind: PromptKind;
  language: string;
  content: string;
}

export function usePromptList() {
  return useQuery({
    queryKey: ["prompts"],
    queryFn: () => apiFetch<PromptListItem[]>("/settings/prompts"),
  });
}

export function usePrompt(kind: PromptKind | null, language: string | null) {
  return useQuery({
    queryKey: ["prompt", kind, language],
    queryFn: () =>
      apiFetch<PromptContent>(`/settings/prompts/${kind}/${language}`),
    enabled: !!kind && !!language,
  });
}

export function useUpdatePrompt() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: { kind: PromptKind; language: string; content: string }) =>
      apiFetch<{ status: string; size: number }>(
        `/settings/prompts/${vars.kind}/${vars.language}`,
        {
          method: "PUT",
          body: JSON.stringify({ content: vars.content }),
        },
      ),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ["prompt", vars.kind, vars.language] });
      qc.invalidateQueries({ queryKey: ["prompts"] });
    },
  });
}
