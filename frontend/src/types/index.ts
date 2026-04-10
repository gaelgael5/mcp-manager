export interface McpService {
  id: string;
  name: string;
  source_url: string;
  doc_url: string | null;
  doc_hash: string | null;
  branch_hash: string | null;
  source_type: string;
  transport: string | null;
  category: string | null;
  tags: string[];
  repo_status: string | null;
  stars: number | null;
  canonical_id: string | null;
  is_deprecated: boolean;
  has_summaries: boolean;
  created_at: string;
  updated_at: string;
}

export interface McpSummary {
  id: string;
  mcp_service_id: string;
  culture: string;
  summary: string;
  source_hash: string | null;
  created_at: string;
  updated_at: string;
}

export interface SkillTranslation {
  culture: "en" | "fr";
  summary: string;
  source_hash?: string | null;
  heuristic_quality?: number | null;
  llm_quality?: number | null;
  created_at?: string | null;
  updated_at?: string | null;
  rag_indexed_at?: string | null;
}

export interface InstallMode {
  runtime: string;
  action_type: string;
  template: string;
}

export interface InstallTarget {
  id: string;
  name: string;
  description: string | null;
  modes: InstallMode[];
  created_at: string;
}

export interface McpInstallation {
  id: string;
  mcp_service_id: string;
  install_target_id: string;
  action_type: string;
  data: string;
  env_vars: Record<string, string>;
  created_at: string;
  updated_at: string;
}

export interface McpParameter {
  id: string;
  mcp_service_id: string;
  name: string;
  description: string | null;
  is_required: boolean;
  is_secret: boolean;
  source: string;
  created_at: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  per_page: number;
}

export interface Stats {
  total_services: number;
  by_source: Record<string, number>;
  by_category: Record<string, number>;
  by_repo_status: Record<string, number>;
  indexation: {
    with_summaries: number;
    with_embeddings: number;
    total_embeddings: number;
    with_params: number;
    with_installations: number;
    needs_reindex: number;
    outdated_summaries: number;
  };
}

export interface SyncStatus {
  running: boolean;
  last_run: string | null;
  last_stats: { new: number; updated: number; unchanged: number } | null;
}
