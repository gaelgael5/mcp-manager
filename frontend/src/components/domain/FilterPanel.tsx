import { useTranslation } from "../../i18n";
import { SearchInput } from "../ui/SearchInput";

interface FilterPanelProps {
  search: string;
  onSearchChange: (v: string) => void;
  sourceType: string;
  onSourceTypeChange: (v: string) => void;
  transport: string;
  onTransportChange: (v: string) => void;
  repoStatus: string;
  onRepoStatusChange: (v: string) => void;
  hasSummaries: string;
  onHasSummariesChange: (v: string) => void;
  category: string;
  onCategoryChange: (v: string) => void;
}

export function FilterPanel({
  search, onSearchChange,
  sourceType, onSourceTypeChange,
  transport, onTransportChange,
  repoStatus, onRepoStatusChange,
  hasSummaries, onHasSummariesChange,
  category, onCategoryChange,
}: FilterPanelProps) {
  const { t } = useTranslation();
  return (
    <div className="space-y-3">
      <div className="flex gap-3">
        <div className="flex-1">
          <SearchInput value={search} onChange={onSearchChange} placeholder={t("components.filterPanel.searchPlaceholder")} />
        </div>
      </div>
      <div className="flex flex-wrap gap-2">
        <select value={sourceType} onChange={(e) => onSourceTypeChange(e.target.value)} className="rounded-md border border-gray-300 px-2 py-1.5 text-xs">
          <option value="">{t("common.filters.allSources")}</option>
          <option value="docker_registry">Docker Registry</option>
          <option value="mcp_registry">MCP Registry</option>
          <option value="glama">Glama</option>
          <option value="pulsemcp">PulseMCP</option>
          <option value="mcp_servers_repo">Reference</option>
        </select>
        <select value={transport} onChange={(e) => onTransportChange(e.target.value)} className="rounded-md border border-gray-300 px-2 py-1.5 text-xs">
          <option value="">{t("common.filters.allTransports")}</option>
          <option value="stdio">stdio</option>
          <option value="sse">sse</option>
          <option value="streamable-http">streamable-http</option>
        </select>
        <select value={repoStatus} onChange={(e) => onRepoStatusChange(e.target.value)} className="rounded-md border border-gray-300 px-2 py-1.5 text-xs">
          <option value="">{t("common.filters.allRepoStatus")}</option>
          <option value="ok">{t("components.filterPanel.repoOk")}</option>
          <option value="404">{t("components.filterPanel.repo404")}</option>
          <option value="none">{t("components.filterPanel.notChecked")}</option>
        </select>
        <select value={hasSummaries} onChange={(e) => onHasSummariesChange(e.target.value)} className="rounded-md border border-gray-300 px-2 py-1.5 text-xs">
          <option value="">{t("common.filters.allSummaries")}</option>
          <option value="true">{t("components.filterPanel.hasSummary")}</option>
          <option value="false">{t("components.filterPanel.noSummary")}</option>
        </select>
        <select value={category} onChange={(e) => onCategoryChange(e.target.value)} className="rounded-md border border-gray-300 px-2 py-1.5 text-xs">
          <option value="">{t("common.filters.allCategories")}</option>
          <option value="ai">ai</option>
          <option value="ai-ml">ai-ml</option>
          <option value="analytics">analytics</option>
          <option value="automation">automation</option>
          <option value="blockchain">blockchain</option>
          <option value="cloud">cloud</option>
          <option value="commerce">commerce</option>
          <option value="communication">communication</option>
          <option value="data-analytics">data-analytics</option>
          <option value="data-visualization">data-visualization</option>
          <option value="database">database</option>
          <option value="developer-tools">developer-tools</option>
          <option value="development">development</option>
          <option value="devops">devops</option>
          <option value="documentation">documentation</option>
          <option value="ecommerce">ecommerce</option>
          <option value="education">education</option>
          <option value="email">email</option>
          <option value="finance">finance</option>
          <option value="games">games</option>
          <option value="healthcare">healthcare</option>
          <option value="infrastructure">infrastructure</option>
          <option value="integration">integration</option>
          <option value="messaging">messaging</option>
          <option value="monitoring">monitoring</option>
          <option value="productivity">productivity</option>
          <option value="search">search</option>
          <option value="security">security</option>
          <option value="social">social</option>
          <option value="testing">testing</option>
          <option value="web">web</option>
        </select>
      </div>
    </div>
  );
}
