import { useState } from "react";
import { useServices } from "../api/services";
import { ServiceCard } from "../components/domain/ServiceCard";
import { FilterPanel } from "../components/domain/FilterPanel";
import { Button } from "../components/ui/Button";

export function ServicesPage() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [sourceType, setSourceType] = useState("");
  const { data, isLoading } = useServices({ page, search, source_type: sourceType || undefined });

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">MCP Services</h1>
      <FilterPanel search={search} onSearchChange={setSearch} sourceType={sourceType} onSourceTypeChange={setSourceType} />
      {isLoading ? (
        <p className="text-gray-500">Loading...</p>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {data?.items.map((s) => <ServiceCard key={s.id} service={s} />)}
          </div>
          {data && data.total > data.per_page && (
            <div className="flex gap-2 justify-center pt-4">
              <Button variant="secondary" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</Button>
              <span className="text-sm text-gray-500 py-1.5">Page {page} / {Math.ceil(data.total / data.per_page)}</span>
              <Button variant="secondary" size="sm" disabled={page * data.per_page >= data.total} onClick={() => setPage(page + 1)}>Next</Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
