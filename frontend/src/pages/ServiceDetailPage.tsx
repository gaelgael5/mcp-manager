import { useState } from "react";
import { useParams } from "react-router-dom";
import { useService, useUpdateService } from "../api/services";
import { useSummaries, useGenerateSummary } from "../api/summaries";
import { useInstallations, useGenerateInstallations } from "../api/installations";
import { Card } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { StatusBadge } from "../components/ui/StatusBadge";
import { SummaryView } from "../components/domain/SummaryView";
import { InstallCommand } from "../components/domain/InstallCommand";

export function ServiceDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data: service } = useService(id!);
  const { data: summariesData } = useSummaries(id);
  const { data: installsData } = useInstallations(id);
  const generateSummary = useGenerateSummary(id!);
  const generateInstalls = useGenerateInstallations(id!);
  const updateService = useUpdateService(id!);

  const [editingUrl, setEditingUrl] = useState(false);
  const [urlInput, setUrlInput] = useState("");

  if (!service) return <p className="text-gray-500">Loading...</p>;

  const hasSummaries = summariesData?.items && summariesData.items.length > 0;
  const hasInstalls = installsData?.items && installsData.items.length > 0;

  const handleSaveUrl = () => {
    if (!urlInput.trim()) return;
    updateService.mutate({ source_url: urlInput.trim() }, {
      onSuccess: () => {
        setEditingUrl(false);
        setUrlInput("");
      },
    });
  };

  const handleStartEdit = () => {
    setUrlInput(service.source_url || "");
    setEditingUrl(true);
  };

  return (
    <div className="space-y-6">
      <div>
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold">{service.name}</h1>
          <StatusBadge isDeprecated={service.is_deprecated} />
          {service.repo_status === "404" && <Badge color="red">404</Badge>}
        </div>
        <div className="mt-2 flex flex-wrap gap-2">
          <Badge color="purple">{service.source_type}</Badge>
          {service.transport && <Badge color="yellow">{service.transport}</Badge>}
          {service.category && <Badge>{service.category}</Badge>}
          {service.tags.map((t) => <Badge key={t}>{t}</Badge>)}
        </div>

        {editingUrl ? (
          <div className="mt-2 flex items-center gap-2">
            <input
              type="url"
              value={urlInput}
              onChange={(e) => setUrlInput(e.target.value)}
              placeholder="https://github.com/owner/repo"
              className="flex-1 rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              autoFocus
              onKeyDown={(e) => { if (e.key === "Enter") handleSaveUrl(); if (e.key === "Escape") setEditingUrl(false); }}
            />
            <Button size="sm" onClick={handleSaveUrl} loading={updateService.isPending}>Save</Button>
            <Button size="sm" variant="secondary" onClick={() => setEditingUrl(false)}>Cancel</Button>
          </div>
        ) : service.source_url ? (
          <div className="mt-2 flex items-center gap-2">
            <a href={service.source_url} target="_blank" rel="noopener noreferrer" className="text-sm text-blue-600 hover:underline">{service.source_url}</a>
            <button onClick={handleStartEdit} className="text-xs text-gray-400 hover:text-gray-600">edit</button>
          </div>
        ) : (
          <div className="mt-2 flex items-center gap-2">
            <span className="text-sm text-gray-400">No repository URL</span>
            <Button size="sm" variant="secondary" onClick={handleStartEdit}>Add URL</Button>
          </div>
        )}
      </div>

      <Card title="Summary">
        <div className="space-y-3">
          <SummaryView summaries={summariesData?.items ?? []} />
          <div className="flex items-center gap-3 pt-2">
            <Button
              variant={hasSummaries ? "secondary" : "primary"}
              size="sm"
              onClick={() => generateSummary.mutate()}
              loading={generateSummary.isPending}
            >
              {hasSummaries ? "Regenerate Summary" : "Generate Summary"}
            </Button>
            {generateSummary.isSuccess && (
              <span className="text-sm text-green-600">Summaries generated</span>
            )}
            {generateSummary.isError && (
              <span className="text-sm text-red-600">Failed to generate summary</span>
            )}
          </div>
        </div>
      </Card>

      <Card title="Installation">
        <div className="space-y-3">
          {hasInstalls ? (
            installsData.items.map((inst) => <InstallCommand key={inst.id} installation={inst} />)
          ) : (
            <p className="text-sm text-gray-500">No installation recipes available.</p>
          )}
          <div className="flex items-center gap-3 pt-2">
            <Button
              variant={hasInstalls ? "secondary" : "primary"}
              size="sm"
              onClick={() => generateInstalls.mutate()}
              loading={generateInstalls.isPending}
            >
              {hasInstalls ? "Regenerate Recipes" : "Generate Recipes"}
            </Button>
            {generateInstalls.isSuccess && (
              <span className="text-sm text-green-600">Recipes generated</span>
            )}
            {generateInstalls.isError && (
              <span className="text-sm text-red-600">Failed to generate recipes</span>
            )}
          </div>
        </div>
      </Card>
    </div>
  );
}
