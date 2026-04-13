import { Badge } from "./Badge";
import { useTranslation } from "../../i18n";

interface StatusBadgeProps {
  isDeprecated: boolean;
}

export function StatusBadge({ isDeprecated }: StatusBadgeProps) {
  const { t } = useTranslation();
  return isDeprecated
    ? <Badge color="red">{t("components.statusBadge.deprecated")}</Badge>
    : <Badge color="green">{t("components.statusBadge.active")}</Badge>;
}
