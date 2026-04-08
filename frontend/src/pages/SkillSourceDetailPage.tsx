import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import Markdown from "react-markdown";
import { apiFetch } from "../api/client";
import { useCurrentUser } from "../api/auth";
import { Card } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Tabs } from "../components/ui/Tabs";

interface SkillSourceDetail {
  id: string;
  name: string;
  url: string;
  skills_path: string;
  type: string;
  repo_url: string | null;
  description: string | null;
  summary_en: string | null;
  summary_fr: string | null;
  has_summary: boolean;
  branch_hash: string | null;
  is_active: boolean;
  last_sync: string | null;
  stars: number | null;
  last_sync_count: number;
  created_at: string;
}

const targetColors: Record<string, string> = {
  claude: "purple",
  copilot: "blue",
  cursor: "green",
  gemini: "yellow",
};

export function SkillSourceDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data: user } = useCurrentUser();
  const isAdmin = user?.is_admin === true;
  const qc = useQueryClient();
  const [tab, setTab] = useState("en");

  interface Skill {
    id: string;
    name: string;
    description: string | null;
    target_type: string;
    install_command: string | null;
    weekly_installs: number;
    has_summary: boolean;
  }

  const { data: source } = useQuery({
    queryKey: ["skill-source", id],
    queryFn: () => apiFetch<SkillSourceDetail>(`/skill-sources/${id}`),
    enabled: !!id,
  });

  const { data: skills } = useQuery({
    queryKey: ["skills", `source_id=${id}`],
    queryFn: () => apiFetch<Skill[]>(`/skills?source_id=${id}`),
    enabled: !!id,
  });

  const generateSummary = useMutation({
    mutationFn: () => apiFetch<{ status: string }>(`/skill-sources/${id}/generate-summary`, { method: "POST" }),
    onSuccess: () => qc.refetchQueries({ queryKey: ["skill-source", id] }),
  });

  const syncSource = useMutation({
    mutationFn: () => apiFetch<{ status: string; added: number; updated: number }>(`/skill-sources/${id}/sync`, { method: "POST" }),
    onSuccess: () => {
      qc.refetchQueries({ queryKey: ["skill-source", id] });
      qc.refetchQueries({ queryKey: ["skills", `source_id=${id}`] });
    },
  });

  if (!source) return <p className="text-gray-500">Loading...</p>;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2 text-sm text-gray-500 mb-2">
          <Link to="/skills" className="hover:text-blue-600">Skill Sources</Link>
          <span>/</span>
          <span>{source.name}</span>
        </div>
        <h1 className="text-2xl font-bold">{source.name}</h1>
        <div className="mt-2 flex flex-wrap gap-2">
          <Badge color={targetColors[source.type] || "gray"}>{source.type}</Badge>
          <Badge color={source.is_active ? "green" : "red"}>{source.is_active ? "active" : "inactive"}</Badge>
          {source.stars != null && <Badge color="yellow">&#9733; {source.stars.toLocaleString()}</Badge>}
          <Badge color="blue">{source.last_sync_count} skills</Badge>
        </div>
        <a href={source.url} target="_blank" rel="noopener noreferrer" className="mt-2 block text-sm text-blue-600 hover:underline">
          {source.url}
        </a>
        {source.repo_url && (
          <a href={source.repo_url} target="_blank" rel="noopener noreferrer" className="block text-sm text-gray-600 hover:underline">
            {source.repo_url}
          </a>
        )}
        <div className="text-xs text-gray-400 mt-1">
          {source.last_sync ? `Last sync: ${new Date(source.last_sync).toLocaleString()}` : "Never synced"}
          {source.branch_hash && ` — ${source.branch_hash.slice(0, 8)}`}
        </div>
      </div>

      {/* Summary */}
      <Card title="Summary">
        <div className="space-y-3">
          {(source.summary_en || source.summary_fr) ? (
            <>
              <Tabs
                tabs={[
                  ...(source.summary_en ? [{ key: "en", label: "EN" }] : []),
                  ...(source.summary_fr ? [{ key: "fr", label: "FR" }] : []),
                ]}
                active={tab}
                onChange={setTab}
              />
              <div className="prose prose-sm prose-gray max-w-none">
                <Markdown>{tab === "fr" ? source.summary_fr || "" : source.summary_en || ""}</Markdown>
              </div>
            </>
          ) : (
            <p className="text-sm text-gray-500">No summary generated yet.</p>
          )}
          {isAdmin && (
            <div className="flex items-center gap-3">
              <Button
                size="sm"
                variant={source.has_summary ? "secondary" : "primary"}
                onClick={() => generateSummary.mutate()}
                loading={generateSummary.isPending}
              >
                {source.has_summary ? "Regenerate Summary" : "Generate Summary"}
              </Button>
              {generateSummary.isSuccess && <span className="text-sm text-green-600">Summary generated</span>}
              {generateSummary.isError && <span className="text-sm text-red-600">Failed</span>}
            </div>
          )}
        </div>
      </Card>

      {/* Skills list */}
      <Card title={`Skills${skills?.length ? ` (${skills.length})` : ""}`}>
        <div className="space-y-3">
          {isAdmin && (
            <div className="flex items-center gap-3">
              <Button size="sm" variant="secondary" onClick={() => syncSource.mutate()} loading={syncSource.isPending}>
                Sync
              </Button>
              {syncSource.isSuccess && syncSource.data && (
                <span className="text-sm text-green-600">
                  Sync terminé : {syncSource.data.added} ajoutés, {syncSource.data.updated} mis à jour
                </span>
              )}
              {syncSource.isError && <span className="text-sm text-red-600">Échec du sync</span>}
            </div>
          )}
          {skills && skills.length > 0 ? (
            <div className="space-y-1">
              {skills.map((s) => (
                <Link
                  key={s.id}
                  to={`/skills-catalog/${s.id}`}
                  className="flex items-center justify-between rounded border border-gray-100 bg-gray-50 px-3 py-2 hover:bg-blue-50 transition-colors"
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="text-sm font-medium truncate">{s.name}</span>
                    {s.has_summary && <Badge color="green">summarized</Badge>}
                  </div>
                  <div className="flex items-center gap-2 text-xs text-gray-400 shrink-0">
                    {s.description && <span className="truncate max-w-xs">{s.description}</span>}
                  </div>
                </Link>
              ))}
            </div>
          ) : (
            <p className="text-sm text-gray-500">Aucun skill trouvé. Lancez un Sync pour scanner le dépôt.</p>
          )}
        </div>
      </Card>
    </div>
  );
}
