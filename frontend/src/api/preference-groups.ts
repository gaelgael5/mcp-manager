import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./client";

export interface PreferenceGroup {
  id: string;
  name: string;
  description: string | null;
  is_public: boolean;
  is_owner: boolean;
  owner_pseudo: string | null;
  service_count: number;
  skill_count: number;
  created_at: string;
}

export interface PreferenceGroupDetail {
  id: string;
  name: string;
  description: string | null;
  is_public: boolean;
  is_owner: boolean;
  owner_pseudo: string | null;
  created_at: string;
  updated_at: string;
  services: { id: string; name: string; source_type: string; category: string | null }[];
  skills: { id: string; name: string; target_type: string; category: string | null }[];
}

export interface GroupRef {
  id: string;
  name: string;
}

export function usePreferenceGroups() {
  return useQuery({
    queryKey: ["preference-groups"],
    queryFn: () => apiFetch<PreferenceGroup[]>("/preference-groups"),
  });
}

export function usePreferenceGroup(id: string) {
  return useQuery({
    queryKey: ["preference-groups", id],
    queryFn: () => apiFetch<PreferenceGroupDetail>(`/preference-groups/${id}`),
    enabled: !!id,
  });
}

export function useCreateGroup() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { name: string; description?: string }) =>
      apiFetch<{ id: string; name: string; description: string | null }>("/preference-groups", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["preference-groups"] }),
  });
}

export function useUpdateGroup(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { name?: string; description?: string; is_public?: boolean }) =>
      apiFetch(`/preference-groups/${id}`, {
        method: "PUT",
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["preference-groups"] });
      qc.invalidateQueries({ queryKey: ["preference-groups", id] });
    },
  });
}

export function useDeleteGroup() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch(`/preference-groups/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["preference-groups"] }),
  });
}

export function useAddServiceToGroup() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ groupId, serviceId }: { groupId: string; serviceId: string }) =>
      apiFetch(`/preference-groups/${groupId}/services/${serviceId}`, { method: "POST" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["preference-groups"] });
      qc.invalidateQueries({ queryKey: ["service-groups"] });
    },
  });
}

export function useRemoveServiceFromGroup() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ groupId, serviceId }: { groupId: string; serviceId: string }) =>
      apiFetch(`/preference-groups/${groupId}/services/${serviceId}`, { method: "DELETE" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["preference-groups"] });
      qc.invalidateQueries({ queryKey: ["service-groups"] });
    },
  });
}

export function useAddSkillToGroup() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ groupId, skillId }: { groupId: string; skillId: string }) =>
      apiFetch(`/preference-groups/${groupId}/skills/${skillId}`, { method: "POST" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["preference-groups"] });
      qc.invalidateQueries({ queryKey: ["skill-groups"] });
    },
  });
}

export function useRemoveSkillFromGroup() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ groupId, skillId }: { groupId: string; skillId: string }) =>
      apiFetch(`/preference-groups/${groupId}/skills/${skillId}`, { method: "DELETE" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["preference-groups"] });
      qc.invalidateQueries({ queryKey: ["skill-groups"] });
    },
  });
}

export function useServiceGroups(serviceId: string | undefined) {
  return useQuery({
    queryKey: ["service-groups", serviceId],
    queryFn: () => apiFetch<GroupRef[]>(`/services/${serviceId}/groups`),
    enabled: !!serviceId,
  });
}

export function useSkillGroups(skillId: string | undefined) {
  return useQuery({
    queryKey: ["skill-groups", skillId],
    queryFn: () => apiFetch<GroupRef[]>(`/skills/${skillId}/groups`),
    enabled: !!skillId,
  });
}
