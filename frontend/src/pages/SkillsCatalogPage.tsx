import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { apiFetch } from "../api/client";
import { Badge } from "../components/ui/Badge";
import { SearchInput } from "../components/ui/SearchInput";

interface Skill {
  id: string;
  skill_source_id: string;
  name: string;
  description: string | null;
  target_type: string;
  licence: string | null;
  source_url: string | null;
  category: string | null;
}

interface SkillSource {
  id: string;
  name: string;
  type: string;
}

const targetColors: Record<string, string> = {
  claude: "purple",
  copilot: "blue",
  cursor: "green",
  gemini: "yellow",
};

function useSkills(sourceId?: string, targetType?: string) {
  const params = new URLSearchParams();
  if (sourceId) params.set("source_id", sourceId);
  if (targetType) params.set("target_type", targetType);
  return useQuery({
    queryKey: ["skills", params.toString()],
    queryFn: () => apiFetch<Skill[]>(`/skills?${params.toString()}`),
  });
}

function useSkillSources() {
  return useQuery({
    queryKey: ["skill-sources"],
    queryFn: () => apiFetch<SkillSource[]>("/skill-sources"),
  });
}

export function SkillsCatalogPage() {
  const [search, setSearch] = useState("");
  const [selectedSource, setSelectedSource] = useState("");
  const [selectedTarget, setSelectedTarget] = useState("");
  const { data: skills } = useSkills(selectedSource || undefined, selectedTarget || undefined);
  const { data: sources } = useSkillSources();

  const filtered = (skills || []).filter((s) => {
    if (!search) return true;
    const q = search.toLowerCase();
    return s.name.toLowerCase().includes(q) || (s.description || "").toLowerCase().includes(q);
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Skills Catalog</h1>
        <span className="text-sm text-gray-500">{filtered.length} skills</span>
      </div>

      <div className="space-y-3">
        <SearchInput value={search} onChange={setSearch} placeholder="Search skills..." />
        <div className="flex gap-2">
          <select value={selectedSource} onChange={(e) => setSelectedSource(e.target.value)} className="rounded-md border border-gray-300 px-2 py-1.5 text-xs">
            <option value="">All sources</option>
            {sources?.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
          <select value={selectedTarget} onChange={(e) => setSelectedTarget(e.target.value)} className="rounded-md border border-gray-300 px-2 py-1.5 text-xs">
            <option value="">All targets</option>
            <option value="claude">claude</option>
            <option value="copilot">copilot</option>
            <option value="cursor">cursor</option>
            <option value="gemini">gemini</option>
          </select>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {filtered.map((skill) => (
          <Link
            key={skill.id}
            to={`/skills-catalog/${skill.id}`}
            className="block rounded-lg border border-gray-200 bg-white p-4 hover:shadow-md transition-shadow"
          >
            <div className="flex items-start justify-between">
              <div>
                <h3 className="font-medium text-gray-900">{skill.name}</h3>
                <div className="mt-1 flex flex-wrap gap-1.5">
                  <Badge color={targetColors[skill.target_type] || "gray"}>{skill.target_type}</Badge>
                  {sources && <Badge color="blue">{sources.find((s) => s.id === skill.skill_source_id)?.name || "unknown"}</Badge>}
                  {skill.licence && <Badge color="gray">{skill.licence}</Badge>}
                  {skill.category && <Badge>{skill.category}</Badge>}
                </div>
              </div>
            </div>
            {skill.description && (
              <p className="mt-2 text-sm text-gray-600 line-clamp-3">{skill.description}</p>
            )}
          </Link>
        ))}
      </div>

      {filtered.length === 0 && (
        <p className="text-sm text-gray-500">
          {skills?.length === 0 ? "No skills indexed yet." : "No skills match your search."}
        </p>
      )}
    </div>
  );
}
