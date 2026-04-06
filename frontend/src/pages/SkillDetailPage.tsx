import { useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import Markdown from "react-markdown";
import { apiFetch } from "../api/client";
import { useCurrentUser } from "../api/auth";
import { Card } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Tabs } from "../components/ui/Tabs";

interface SkillDetail {
  id: string;
  skill_source_id: string;
  name: string;
  description: string | null;
  summary_en: string | null;
  summary_fr: string | null;
  target_type: string;
  licence: string | null;
  licence_url: string | null;
  source_url: string | null;
  category: string | null;
  has_summary: boolean;
  created_at: string;
  updated_at: string;
}

const targetColors: Record<string, string> = {
  claude: "purple",
  copilot: "blue",
  cursor: "green",
  gemini: "yellow",
};

const licenceInfo: Record<string, { color: string; description: string }> = {
  "Apache 2.0": { color: "green", description: "Free to use, modify, and distribute with attribution." },
  "Apache-2.0": { color: "green", description: "Free to use, modify, and distribute with attribution." },
  "MIT": { color: "green", description: "Free to use with minimal restrictions." },
  "Proprietary": { color: "red", description: "Usage restricted. Check the license terms." },
  "Source-Available": { color: "yellow", description: "Source code visible but usage may be restricted." },
};

export function SkillDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data: user } = useCurrentUser();
  const isAdmin = user?.is_admin === true;
  const qc = useQueryClient();
  const [contentTab, setContentTab] = useState("en");
  const [collapsed, setCollapsed] = useState(false);

  const generateSummary = useMutation({
    mutationFn: () => apiFetch<{ status: string }>(`/skills/${id}/generate-summary`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["skill", id] }),
  });

  const { data: skill } = useQuery({
    queryKey: ["skill", id],
    queryFn: () => apiFetch<SkillDetail>(`/skills/${id}`),
    enabled: !!id,
  });

  if (!skill) return <p className="text-gray-500">Loading...</p>;

  const licence = licenceInfo[skill.licence || ""] || null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold">{skill.name}</h1>
        <div className="mt-2 flex flex-wrap gap-2">
          <Badge color={targetColors[skill.target_type] || "gray"}>{skill.target_type}</Badge>
          {skill.licence && <Badge color={licence?.color || "gray"}>{skill.licence}</Badge>}
          {skill.category && <Badge>{skill.category}</Badge>}
        </div>
        {skill.source_url && (
          <a href={skill.source_url} target="_blank" rel="noopener noreferrer" className="mt-2 block text-sm text-blue-600 hover:underline">
            {skill.source_url}
          </a>
        )}
      </div>

      {/* Summary */}
      <Card title="Summary">
        <div className="space-y-3">
          {(skill.summary_en || skill.summary_fr) ? (
            <>
              <Tabs
                tabs={[
                  ...(skill.summary_en ? [{ key: "en", label: "EN" }] : []),
                  ...(skill.summary_fr ? [{ key: "fr", label: "FR" }] : []),
                ]}
                active={contentTab}
                onChange={setContentTab}
              />
              {!collapsed && (
                <div className="prose prose-sm prose-gray max-w-none">
                  <Markdown>{contentTab === "fr" ? skill.summary_fr || "" : skill.summary_en || ""}</Markdown>
                </div>
              )}
            </>
          ) : (
            <p className="text-sm text-gray-500">No summary generated yet.</p>
          )}
          <div className="flex items-center gap-3">
            <button onClick={() => setCollapsed(!collapsed)} className="text-xs text-gray-400 hover:text-gray-600">
              {collapsed ? "Expand" : "Collapse"}
            </button>
            {isAdmin && (
              <Button
                size="sm"
                variant={skill.has_summary ? "secondary" : "primary"}
                onClick={() => generateSummary.mutate()}
                loading={generateSummary.isPending}
              >
                {skill.has_summary ? "Regenerate Summary" : "Generate Summary"}
              </Button>
            )}
            {generateSummary.isSuccess && <span className="text-sm text-green-600">Summaries generated</span>}
            {generateSummary.isError && <span className="text-sm text-red-600">Failed</span>}
          </div>
        </div>
      </Card>

      {/* Licence */}
      {skill.licence && (
        <Card title="License">
          <div className="flex items-center gap-3">
            <Badge color={licence?.color || "gray"}>{skill.licence}</Badge>
            {licence?.description && <span className="text-sm text-gray-600">{licence.description}</span>}
            {skill.licence_url && (
              <a href={skill.licence_url} target="_blank" rel="noopener noreferrer" className="text-xs text-blue-600 hover:underline">
                View LICENSE file
              </a>
            )}
          </div>
        </Card>
      )}

      {/* Description (from frontmatter) */}
      {skill.description && (
        <Card title="Trigger Description">
          <p className="text-sm text-gray-700 leading-relaxed">{skill.description}</p>
        </Card>
      )}
    </div>
  );
}
