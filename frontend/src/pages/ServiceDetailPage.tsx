import { useParams } from "react-router-dom";
import { useService } from "../api/services";
import { useSummaries, useGenerateSummary } from "../api/summaries";
import { useInstallations } from "../api/installations";
import { Card } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { StatusBadge } from "../components/ui/StatusBadge";
import { SummaryView } from "../components/domain/SummaryView";
import { InstallCommand } from "../components/domain/InstallCommand";

export function ServiceDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data: service } = useService(id!);
  const { data: summariesData, refetch: refetchSummaries } = useSummaries(id);
  const { data: installsData } = useInstallations(id);
  const generateSummary = useGenerateSummary(id!);

  if (!service) return <p className="text-gray-500">Loading...</p>;

  const hasSummaries = summariesData?.items && summariesData.items.length > 0;

  const handleGenerate = () => {
    generateSummary.mutate(undefined, {
      onSuccess: () => {
        setTimeout(() => refetchSummaries(), 8000);
      },
    });
  };

  return (
    <div className="space-y-6">
      <div>
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold">{service.name}</h1>
          <StatusBadge isDeprecated={service.is_deprecated} />
        </div>
        <div className="mt-2 flex flex-wrap gap-2">
          <Badge color="purple">{service.source_type}</Badge>
          {service.transport && <Badge color="yellow">{service.transport}</Badge>}
          {service.category && <Badge>{service.category}</Badge>}
          {service.tags.map((t) => <Badge key={t}>{t}</Badge>)}
        </div>
        {service.source_url ? (
          <a href={service.source_url} target="_blank" rel="noopener noreferrer" className="mt-2 block text-sm text-blue-600 hover:underline">{service.source_url}</a>
        ) : (
          <p className="mt-2 text-sm text-gray-400">Remote service — no source code available</p>
        )}
      </div>

      <Card title="Summary">
        <div className="space-y-3">
          <SummaryView summaries={summariesData?.items ?? []} />
          <div className="flex items-center gap-3 pt-2">
            <Button
              variant={hasSummaries ? "secondary" : "primary"}
              size="sm"
              onClick={handleGenerate}
              loading={generateSummary.isPending}
            >
              {hasSummaries ? "Regenerate Summary" : "Generate Summary"}
            </Button>
            {generateSummary.isSuccess && (
              <span className="text-sm text-green-600">Generation started — refreshing in a few seconds...</span>
            )}
            {generateSummary.isError && (
              <span className="text-sm text-red-600">Failed to start generation</span>
            )}
          </div>
        </div>
      </Card>

      <Card title="Installation">
        {installsData?.items && installsData.items.length > 0 ? (
          <div className="space-y-3">
            {installsData.items.map((inst) => <InstallCommand key={inst.id} installation={inst} />)}
          </div>
        ) : <p className="text-sm text-gray-500">No installation recipes available.</p>}
      </Card>
    </div>
  );
}
