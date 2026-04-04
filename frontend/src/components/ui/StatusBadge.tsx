import { Badge } from "./Badge";

interface StatusBadgeProps {
  isDeprecated: boolean;
}

export function StatusBadge({ isDeprecated }: StatusBadgeProps) {
  return isDeprecated
    ? <Badge color="red">Deprecated</Badge>
    : <Badge color="green">Active</Badge>;
}
