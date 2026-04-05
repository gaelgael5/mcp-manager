import { useState } from "react";
import { useServices, useSearchServices } from "../api/services";
import { ServiceCard } from "../components/domain/ServiceCard";
import { FilterPanel } from "../components/domain/FilterPanel";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/Badge";

export function ServicesPage() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [semantic, setSemantic] = useState(false);
  const [sourceType, setSourceType] = useState("");
  const [transport, setTransport] = useState("");
  const [repoStatus, setRepoStatus] = useState("");
  const [hasSummaries, setHasSummaries] = useState("");
  const [category, setCategory] = useState("");

  // Use search API when semantic is on and there's a query
  const useSemanticMode = semantic && search.length > 0;

  const servicesQuery = useServices({
    page, search: useSemanticMode ? undefined : search,
    source_type: sourceType || undefined,
    transport: transport || undefined,
    repo_status: repoStatus || undefined,
    has_summaries: hasSummaries || undefined,
    category: category || undefined,
  });

  const searchQuery = useSearchServices({
    q: search,
    semantic: true,
    page,
    per_page: 20,
    transport: transport || undefined,
    category: category || undefined,
    source_type: sourceType || undefined,
    repo_status: repoStatus || undefined,
    has_summaries: hasSummaries || undefined,
  });

  const data = useSemanticMode ? searchQuery.data : servicesQuery.data;
  const isLoading = useSemanticMode ? searchQuery.isLoading : servicesQuery.isLoading;

  const handleFilterChange = (setter: (v: string) => void) => (v: string) => {
    setter(v);
    setPage(1);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">MCP Services</h1>
        <div className="flex items-center gap-3">
          {data && <span className="text-sm text-gray-500">{data.total.toLocaleString()} results</span>}
        </div>
      </div>

      <div className="space-y-3">
        <FilterPanel
          search={search} onSearchChange={handleFilterChange(setSearch)}
          sourceType={sourceType} onSourceTypeChange={handleFilterChange(setSourceType)}
          transport={transport} onTransportChange={handleFilterChange(setTransport)}
          repoStatus={repoStatus} onRepoStatusChange={handleFilterChange(setRepoStatus)}
          hasSummaries={hasSummaries} onHasSummariesChange={handleFilterChange(setHasSummaries)}
          category={category} onCategoryChange={handleFilterChange(setCategory)}
        />
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-2 text-sm cursor-pointer">
            <input
              type="checkbox"
              checked={semantic}
              onChange={(e) => { setSemantic(e.target.checked); setPage(1); }}
              className="rounded border-gray-300"
            />
            Semantic search
          </label>
          {semantic && <Badge color="purple">pgvector</Badge>}
          {semantic && !search && <span className="text-xs text-gray-400">Type a natural language query to use semantic search</span>}
        </div>
      </div>

      {isLoading ? (
        <p className="text-gray-500">Loading...</p>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {data?.items.map((s: any) => (
              <div key={s.id} className="relative">
                <ServiceCard service={s} />
                {useSemanticMode && s.similarity != null && (
                  <span className="absolute top-2 right-2 text-xs bg-purple-100 text-purple-700 px-2 py-0.5 rounded-full">
                    {Math.round(s.similarity * 100)}%
                  </span>
                )}
              </div>
            ))}
          </div>
          {data && data.total > (data.per_page || 20) && (
            <div className="flex gap-2 justify-center pt-4">
              <Button variant="secondary" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</Button>
              <span className="text-sm text-gray-500 py-1.5">Page {page} / {Math.ceil(data.total / (data.per_page || 20))}</span>
              <Button variant="secondary" size="sm" disabled={page * (data.per_page || 20) >= data.total} onClick={() => setPage(page + 1)}>Next</Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
