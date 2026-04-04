import { useParams } from "react-router-dom";
import { useService } from "../api/services";
import { useSummaries } from "../api/summaries";
import { useInstallations } from "../api/installations";
import { Card } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { StatusBadge } from "../components/ui/StatusBadge";
import { SummaryView } from "../components/domain/SummaryView";
import { InstallCommand } from "../components/domain/InstallCommand";

export function ServiceDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data: service } = useService(id!);
  const { data: summariesData } = useSummaries(id);
  const { data: installsData } = useInstallations(id);

  if (!service) return <p className="text-gray-500">Loading...</p>;

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
        {service.source_url && (
          <a href={service.source_url} target="_blank" rel="noopener noreferrer" className="mt-2 block text-sm text-blue-600 hover:underline">{service.source_url}</a>
        )}
      </div>

      <Card title="Summary">
        <SummaryView summaries={summariesData?.items ?? []} />
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
