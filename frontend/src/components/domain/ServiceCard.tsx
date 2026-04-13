import { Link } from "react-router-dom";
import type { McpService } from "../../types";
import { useTranslation } from "../../i18n";
import { Badge } from "../ui/Badge";
import { StatusBadge } from "../ui/StatusBadge";

const sourceColors: Record<string, string> = {
  docker_registry: "purple",
  mcp_registry: "blue",
};

export function ServiceCard({ service }: { service: McpService }) {
  const { t } = useTranslation();
  const hasRepo = Boolean(service.source_url);

  return (
    <Link to={`/services/${service.id}`} className={`block rounded-lg border p-4 hover:shadow-md transition-shadow ${hasRepo ? "border-gray-200 bg-white" : "border-gray-200 bg-gray-50 opacity-75"}`}>
      <div className="flex items-start justify-between">
        <div>
          <h3 className={`font-medium ${hasRepo ? "text-gray-900" : "text-gray-500"}`}>{service.name}</h3>
          <div className="mt-1 flex flex-wrap gap-1.5">
            <Badge color={sourceColors[service.source_type] || "gray"}>{service.source_type}</Badge>
            {service.transport && <Badge color="yellow">{service.transport}</Badge>}
            {service.category && <Badge>{service.category}</Badge>}
            {!hasRepo && <Badge color="red">{t("components.serviceCard.noRepo")}</Badge>}
            {service.stars != null && <Badge color="yellow">&#9733; {service.stars.toLocaleString()}</Badge>}
            {service.repo_status === "404" && <Badge color="red">404</Badge>}
            {!service.has_summaries && <Badge color="yellow">{t("components.serviceCard.noSummary")}</Badge>}
            {(service as any).groups?.map((g: { id: string; name: string }) => (
              <Badge key={g.id} color="green">{g.name}</Badge>
            ))}
          </div>
        </div>
        <StatusBadge isDeprecated={service.is_deprecated} />
      </div>
      {service.tags?.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {service.tags.slice(0, 5).map((tag) => (
            <span key={tag} className="text-xs text-gray-500">#{tag}</span>
          ))}
        </div>
      )}
    </Link>
  );
}
