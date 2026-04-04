import { SearchInput } from "../ui/SearchInput";

interface FilterPanelProps {
  search: string;
  onSearchChange: (v: string) => void;
  sourceType: string;
  onSourceTypeChange: (v: string) => void;
}

export function FilterPanel({ search, onSearchChange, sourceType, onSourceTypeChange }: FilterPanelProps) {
  return (
    <div className="flex gap-4 items-end">
      <div className="flex-1">
        <SearchInput value={search} onChange={onSearchChange} placeholder="Search services..." />
      </div>
      <select
        value={sourceType}
        onChange={(e) => onSourceTypeChange(e.target.value)}
        className="rounded-md border border-gray-300 px-3 py-2 text-sm"
      >
        <option value="">All sources</option>
        <option value="docker_registry">Docker Registry</option>
        <option value="mcp_registry">MCP Registry</option>
      </select>
    </div>
  );
}
