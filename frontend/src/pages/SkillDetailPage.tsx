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
import type { SkillTranslation } from "../types";

interface SkillDetail {
  id: string;
  name: string;
  description: string | null;
  translations: SkillTranslation[];
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
  const byCulture = Object.fromEntries((skill.translations ?? []).map((t) => [t.culture, t]));
  const summaryEn = byCulture["en"]?.summary ?? null;
  const summaryFr = byCulture["fr"]?.summary ?? null;

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
          {(summaryEn || summaryFr) ? (
            <>
              <Tabs
                tabs={[
                  ...(summaryEn ? [{ key: "en", label: "EN" }] : []),
                  ...(summaryFr ? [{ key: "fr", label: "FR" }] : []),
                ]}
                active={contentTab}
                onChange={setContentTab}
              />
              {!collapsed && (
                <div className="prose prose-sm prose-gray max-w-none">
                  <Markdown>{contentTab === "fr" ? summaryFr || "" : summaryEn || ""}</Markdown>
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

      {/* Installation */}
      <SkillInstallBlock skillName={skill.name} sourceUrl={skill.source_url || ""} skillType={skill.target_type} />
    </div>
  );
}

interface TargetWithSkillModes {
  id: string;
  name: string;
  skill_modes: { action_type: string; template: string; compatible_skill_types?: string[] }[];
}

function SkillInstallBlock({ skillName, sourceUrl, skillType }: { skillName: string; sourceUrl: string; skillType: string }) {
  const { data: targets } = useQuery({
    queryKey: ["targets"],
    queryFn: () => apiFetch<TargetWithSkillModes[]>("/targets"),
  });
  const [installCollapsed, setInstallCollapsed] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const targetsWithSkills = (targets || [])
    .map((t) => ({
      ...t,
      skill_modes: (t.skill_modes || []).filter(
        (m) => !m.compatible_skill_types || m.compatible_skill_types.includes(skillType)
      ),
    }))
    .filter((t) => t.skill_modes.length > 0);

  if (targetsWithSkills.length === 0) return null;

  const renderCmd = (template: string) => {
    return template.replace("{name}", skillName).replace("{source_url}", sourceUrl);
  };

  const handleCopy = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <Card>
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-medium">Installation</h3>
        <button onClick={() => setInstallCollapsed(!installCollapsed)} className="text-xs text-gray-400 hover:text-gray-600">
          {installCollapsed ? "Expand" : "Collapse"}
        </button>
      </div>
      {!installCollapsed && (
        <div className="space-y-2">
          {targetsWithSkills.map((t) =>
            t.skill_modes.map((mode, i) => {
              const cmd = renderCmd(mode.template);
              const key = `${t.id}-${i}`;
              return (
                <div key={key} className="rounded-md border border-gray-200 bg-gray-50 p-3">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-medium text-gray-700">{t.name}</span>
                    <button onClick={() => handleCopy(cmd, key)} className="text-xs text-blue-600 hover:text-blue-700">
                      {copiedId === key ? "Copied!" : "Copy"}
                    </button>
                  </div>
                  <pre className="text-sm font-mono text-gray-800 overflow-x-auto whitespace-pre-wrap">{cmd}</pre>
                </div>
              );
            })
          )}
        </div>
      )}
    </Card>
  );
}
