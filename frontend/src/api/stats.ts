import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "./client";
import type { Stats } from "../types";

export function useStats() {
  return useQuery({
    queryKey: ["stats"],
    queryFn: () => apiFetch<Stats>("/stats"),
  });
}
