import { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { apiFetch } from "../api/client";
import { useCurrentUser } from "../api/auth";
import { Card } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { SearchInput } from "../components/ui/SearchInput";

interface SkillSource {
  id: string;
  name: string;
  url: string;
  skills_path: string;
  type: string;
  has_summary: boolean;
  branch_hash: string | null;
  is_active: boolean;
  stars: number | null;
  last_sync: string | null;
  last_sync_count: number;
  created_at: string;
}

const PAGE_SIZE = 20;

const targetColors: Record<string, string> = {
  claude: "purple",
  copilot: "blue",
  cursor: "green",
  gemini: "yellow",
};

function useSkillSources() {
  return useQuery({
    queryKey: ["skill-sources"],
    queryFn: () => apiFetch<SkillSource[]>("/skill-sources"),
  });
}

export function SkillsPage() {
  const { data: user } = useCurrentUser();
  const isAdmin = user?.is_admin === true;
  const { data: sources } = useSkillSources();

  const qc = useQueryClient();

  const createSource = useMutation({
    mutationFn: (body: { name: string; url: string; skills_path: string; type: string }) =>
      apiFetch<SkillSource>("/skill-sources", { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["skill-sources"] }),
  });

  const syncAll = useMutation({
    mutationFn: () =>
      apiFetch<{ status: string; added: number; updated: number }>("/skill-sources/sync-all", { method: "POST" }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["skill-sources"] }); qc.invalidateQueries({ queryKey: ["skills"] }); },
  });

  const deleteSource = useMutation({
    mutationFn: (id: string) =>
      apiFetch<{ status: string }>(`/skill-sources/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["skill-sources"] }),
  });

  const [search, setSearch] = useState("");
  const [filterType, setFilterType] = useState("");
  const [filterSummary, setFilterSummary] = useState<"" | "yes" | "no">("");
  const [filterSynced, setFilterSynced] = useState<"" | "yes" | "no">("");
  const [filterStars, setFilterStars] = useState<"" | "yes">("");
  const [sortBy, setSortBy] = useState<"stars" | "name" | "recent">("stars");
  const [page, setPage] = useState(1);
  const [newName, setNewName] = useState("");
  const [newUrl, setNewUrl] = useState("");
  const [newPath, setNewPath] = useState("skills");
  const [newType, setNewType] = useState("claude");

  const filteredSources = useMemo(() => {
    if (!sources) return [];
    const filtered = sources.filter((s) => {
      const q = search.toLowerCase();
      const matchSearch = !q || s.name.toLowerCase().includes(q) || s.url.toLowerCase().includes(q);
      const matchType = !filterType || s.type === filterType;
      const matchSummary = !filterSummary || (filterSummary === "yes" ? s.has_summary : !s.has_summary);
      const matchSynced = !filterSynced || (filterSynced === "yes" ? !!s.last_sync : !s.last_sync);
      const matchStars = !filterStars || s.stars != null;
      return matchSearch && matchType && matchSummary && matchSynced && matchStars;
    });
    return filtered.sort((a, b) => {
      if (sortBy === "stars") return (b.stars ?? -1) - (a.stars ?? -1);
      if (sortBy === "name") return a.name.localeCompare(b.name);
      return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
    });
  }, [sources, search, filterType, filterSummary, filterSynced, filterStars, sortBy]);

  // Reset page when filters change
  const totalPages = Math.max(1, Math.ceil(filteredSources.length / PAGE_SIZE));
  const currentPage = Math.min(page, totalPages);
  const pagedSources = filteredSources.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);

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
        <div className="space-y-2 mb-3">
          <div className="flex gap-2">
            <SearchInput value={search} onChange={(v) => { setSearch(v); setPage(1); }} placeholder="Search sources..." />
            <select value={filterType} onChange={(e) => { setFilterType(e.target.value); setPage(1); }} className="rounded-md border border-gray-300 px-2 py-1.5 text-xs">
              <option value="">All types</option>
              <option value="claude">claude</option>
              <option value="copilot">copilot</option>
              <option value="cursor">cursor</option>
              <option value="gemini">gemini</option>
            </select>
            <select value={sortBy} onChange={(e) => { setSortBy(e.target.value as "stars" | "name" | "recent"); setPage(1); }} className="rounded-md border border-gray-300 px-2 py-1.5 text-xs">
              <option value="stars">&#9733; Stars</option>
              <option value="name">A-Z</option>
              <option value="recent">Recent</option>
            </select>
            <span className="text-xs text-gray-400 self-center whitespace-nowrap">{filteredSources.length}/{sources?.length || 0}</span>
          </div>
          <div className="flex gap-1.5 flex-wrap">
            <button onClick={() => { setFilterSummary(v => v === "yes" ? "" : "yes"); setPage(1); }} className={`px-2 py-0.5 text-xs rounded-full border transition-colors ${filterSummary === "yes" ? "bg-purple-100 border-purple-300 text-purple-700" : "border-gray-300 text-gray-500 hover:bg-gray-100"}`}>summarized</button>
            <button onClick={() => { setFilterSummary(v => v === "no" ? "" : "no"); setPage(1); }} className={`px-2 py-0.5 text-xs rounded-full border transition-colors ${filterSummary === "no" ? "bg-yellow-100 border-yellow-300 text-yellow-700" : "border-gray-300 text-gray-500 hover:bg-gray-100"}`}>no summary</button>
            <button onClick={() => { setFilterSynced(v => v === "yes" ? "" : "yes"); setPage(1); }} className={`px-2 py-0.5 text-xs rounded-full border transition-colors ${filterSynced === "yes" ? "bg-green-100 border-green-300 text-green-700" : "border-gray-300 text-gray-500 hover:bg-gray-100"}`}>synced</button>
            <button onClick={() => { setFilterSynced(v => v === "no" ? "" : "no"); setPage(1); }} className={`px-2 py-0.5 text-xs rounded-full border transition-colors ${filterSynced === "no" ? "bg-red-100 border-red-300 text-red-700" : "border-gray-300 text-gray-500 hover:bg-gray-100"}`}>never synced</button>
            <button onClick={() => { setFilterStars(v => v === "yes" ? "" : "yes"); setPage(1); }} className={`px-2 py-0.5 text-xs rounded-full border transition-colors ${filterStars === "yes" ? "bg-yellow-100 border-yellow-300 text-yellow-700" : "border-gray-300 text-gray-500 hover:bg-gray-100"}`}>&#9733; has stars</button>
          </div>
        </div>
        <div className="space-y-1">
          {pagedSources.map((s) => (
            <Link
              key={s.id}
              to={`/skills/${s.id}`}
              className="flex items-center justify-between rounded border border-gray-100 bg-gray-50 px-3 py-2 hover:bg-blue-50 transition-colors cursor-pointer"
            >
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-sm truncate">{s.name}</span>
                  <Badge color={targetColors[s.type] || "gray"}>{s.type}</Badge>
                  <Badge color={s.is_active ? "green" : "red"}>{s.is_active ? "active" : "inactive"}</Badge>
                  {s.stars != null && <Badge color="yellow">&#9733; {s.stars.toLocaleString()}</Badge>}
                  {s.has_summary && <Badge color="purple">summarized</Badge>}
                </div>
                <div className="text-xs text-gray-400 truncate">{s.url}</div>
                <div className="text-xs text-gray-400">
                  {s.last_sync ? `Synced: ${new Date(s.last_sync).toLocaleDateString()} (${s.last_sync_count} skills)` : "Never synced"}
                </div>
              </div>
              {isAdmin && (
                <div className="flex gap-2 shrink-0 ml-2" onClick={(e) => e.preventDefault()}>
                  <Button size="sm" variant="danger" onClick={(e) => { e.preventDefault(); if (confirm(`Delete "${s.name}"?`)) deleteSource.mutate(s.id); }}>
                    Remove
                  </Button>
                </div>
              )}
            </Link>
          ))}
          {filteredSources.length === 0 && <p className="text-sm text-gray-500">{sources?.length ? "No sources match your search." : "No skill sources configured."}</p>}
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-center gap-2 mt-3">
            <button
              onClick={() => setPage(Math.max(1, currentPage - 1))}
              disabled={currentPage === 1}
              className="px-2 py-1 text-xs rounded border border-gray-300 disabled:opacity-40 hover:bg-gray-100"
            >
              Prev
            </button>
            <span className="text-xs text-gray-500">
              {currentPage} / {totalPages}
            </span>
            <button
              onClick={() => setPage(Math.min(totalPages, currentPage + 1))}
              disabled={currentPage === totalPages}
              className="px-2 py-1 text-xs rounded border border-gray-300 disabled:opacity-40 hover:bg-gray-100"
            >
              Next
            </button>
          </div>
        )}

        {isAdmin && (
          <div className="mt-3 flex items-center gap-2">
            <Button size="sm" variant="secondary" onClick={() => syncAll.mutate()} loading={syncAll.isPending}>Sync All Sources</Button>
          </div>
        )}

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
    </div>
  );
}
