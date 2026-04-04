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
  is_deprecated: boolean;
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

export interface InstallTarget {
  id: string;
  name: string;
  description: string | null;
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
  outdated_summaries: number;
}

export interface SyncStatus {
  running: boolean;
  last_run: string | null;
  last_stats: { new: number; updated: number; unchanged: number } | null;
}
