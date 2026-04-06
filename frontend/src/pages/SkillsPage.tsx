import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "../api/client";
import { useCurrentUser } from "../api/auth";
import { Card } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";

interface SkillSource {
  id: string;
  name: string;
  url: string;
  skills_path: string;
  type: string;
  branch_hash: string | null;
  is_active: boolean;
  last_sync: string | null;
  last_sync_count: number;
  created_at: string;
}

interface Skill {
  id: string;
  skill_source_id: string;
  name: string;
  description: string | null;
  content: string | null;
  target_type: string;
  licence: string | null;
  source_url: string | null;
  category: string | null;
}

const targetColors: Record<string, string> = {
  "claude-code": "purple",
  "copilot": "blue",
  "cursor": "green",
  "gemini": "yellow",
};

function useSkillSources() {
  return useQuery({
    queryKey: ["skill-sources"],
    queryFn: () => apiFetch<SkillSource[]>("/skill-sources"),
  });
}

function useSkills(sourceId?: string, targetType?: string) {
  const params = new URLSearchParams();
  if (sourceId) params.set("source_id", sourceId);
  if (targetType) params.set("target_type", targetType);
  const qs = params.toString();
  return useQuery({
    queryKey: ["skills", qs],
    queryFn: () => apiFetch<Skill[]>(`/skills?${qs}`),
  });
}

export function SkillsPage() {
  const { data: user } = useCurrentUser();
  const isAdmin = user?.is_admin === true;
  const { data: sources } = useSkillSources();
  const [selectedSource, setSelectedSource] = useState<string>("");
  const [selectedTarget, setSelectedTarget] = useState<string>("");
  const { data: skills } = useSkills(selectedSource || undefined, selectedTarget || undefined);
  const [expandedSkill, setExpandedSkill] = useState<string | null>(null);

  const qc = useQueryClient();

  const createSource = useMutation({
    mutationFn: (body: { name: string; url: string; type: string }) =>
      apiFetch<SkillSource>("/skill-sources", { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["skill-sources"] }),
  });

  const deleteSource = useMutation({
    mutationFn: (id: string) =>
      apiFetch<{ status: string }>(`/skill-sources/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["skill-sources"] }),
  });

  const [newName, setNewName] = useState("");
  const [newUrl, setNewUrl] = useState("");
  const [newPath, setNewPath] = useState("skills");
  const [newType, setNewType] = useState("claude");

  const handleCreate = () => {
    if (!newName.trim() || !newUrl.trim()) return;
    createSource.mutate({ name: newName.trim(), url: newUrl.trim(), skills_path: newPath.trim(), type: newType });
    setNewName("");
    setNewUrl("");
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Skills & Prompts</h1>

      {/* Sources */}
      <Card title="Skill Sources">
        <div className="space-y-2">
          {sources?.map((s) => (
            <div key={s.id} className="flex items-center justify-between rounded border border-gray-100 bg-gray-50 px-3 py-2">
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-medium text-sm">{s.name}</span>
                  <Badge color={targetColors[s.type] || "gray"}>{s.type}</Badge>
                  <Badge color={s.is_active ? "green" : "red"}>{s.is_active ? "active" : "inactive"}</Badge>
                </div>
                <a href={s.url} target="_blank" rel="noopener noreferrer" className="text-xs text-blue-600 hover:underline">{s.url}</a>
                <span className="text-xs text-gray-400 ml-2">path: {s.skills_path || "skills"}</span>
                <div className="text-xs text-gray-400">
                  {s.last_sync ? `Last sync: ${new Date(s.last_sync).toLocaleString()} (${s.last_sync_count} skills)` : "Never synced"}
                  {s.branch_hash && ` — ${s.branch_hash.slice(0, 8)}`}
                </div>
              </div>
              {isAdmin && (
                <Button size="sm" variant="danger" onClick={() => deleteSource.mutate(s.id)}>Remove</Button>
              )}
            </div>
          ))}
          {(!sources || sources.length === 0) && <p className="text-sm text-gray-500">No skill sources configured.</p>}
        </div>

        {isAdmin && (
          <div className="mt-4 flex gap-3 items-end">
            <div>
              <label className="block text-xs text-gray-500 mb-1">Name</label>
              <input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="Anthropic Skills" className="rounded-md border border-gray-300 px-3 py-2 text-sm" />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">URL</label>
              <input value={newUrl} onChange={(e) => setNewUrl(e.target.value)} placeholder="https://github.com/anthropics/skills" className="rounded-md border border-gray-300 px-3 py-2 text-sm w-80" />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Skills Path</label>
              <input value={newPath} onChange={(e) => setNewPath(e.target.value)} placeholder="skills" className="rounded-md border border-gray-300 px-3 py-2 text-sm w-32" />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Type</label>
              <select value={newType} onChange={(e) => setNewType(e.target.value)} className="rounded-md border border-gray-300 px-3 py-2 text-sm">
                <option value="claude">claude</option>
                <option value="copilot">copilot</option>
                <option value="cursor">cursor</option>
                <option value="gemini">gemini</option>
              </select>
            </div>
            <Button onClick={handleCreate} loading={createSource.isPending}>Add</Button>
          </div>
        )}
      </Card>

      {/* Skills */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-medium">Skills Catalog</h2>
          <div className="flex gap-2">
            <select value={selectedSource} onChange={(e) => setSelectedSource(e.target.value)} className="rounded border border-gray-300 px-2 py-1 text-xs">
              <option value="">All sources</option>
              {sources?.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
            <select value={selectedTarget} onChange={(e) => setSelectedTarget(e.target.value)} className="rounded border border-gray-300 px-2 py-1 text-xs">
              <option value="">All targets</option>
              <option value="claude-code">claude-code</option>
              <option value="copilot">copilot</option>
              <option value="cursor">cursor</option>
              <option value="gemini">gemini</option>
            </select>
          </div>
        </div>

        {skills?.map((skill) => (
          <Card key={skill.id}>
            <div className="flex items-start justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-medium">{skill.name}</span>
                  <Badge color={targetColors[skill.target_type] || "gray"}>{skill.target_type}</Badge>
                  {skill.licence && <Badge color="gray">{skill.licence}</Badge>}
                  {skill.category && <Badge>{skill.category}</Badge>}
                </div>
                {skill.description && <p className="text-sm text-gray-600 mt-1 line-clamp-2">{skill.description}</p>}
                {skill.source_url && (
                  <a href={skill.source_url} target="_blank" rel="noopener noreferrer" className="text-xs text-blue-600 hover:underline mt-1 block">{skill.source_url}</a>
                )}
              </div>
              <button
                onClick={() => setExpandedSkill(expandedSkill === skill.id ? null : skill.id)}
                className="text-xs text-gray-400 hover:text-gray-600"
              >
                {expandedSkill === skill.id ? "Collapse" : "View"}
              </button>
            </div>
            {expandedSkill === skill.id && skill.content && (
              <pre className="mt-3 text-xs font-mono bg-gray-50 border rounded p-3 overflow-auto max-h-96 whitespace-pre-wrap">{skill.content}</pre>
            )}
          </Card>
        ))}
        {skills?.length === 0 && <p className="text-sm text-gray-500">No skills indexed yet. Add a source and sync.</p>}
      </div>
    </div>
  );
}
