import type { SyncStatus } from "../../types";
import { useTranslation } from "../../i18n";

export function SyncStatusBar({ status }: { status: SyncStatus | undefined }) {
  const { t } = useTranslation();
  if (!status) return null;
  return (
    <div className="flex items-center gap-4 text-sm">
      <span className={`inline-flex items-center gap-1.5 ${status.running ? "text-blue-600" : "text-gray-500"}`}>
        {status.running && <span className="h-2 w-2 animate-pulse rounded-full bg-blue-600" />}
        {status.running ? t("components.syncStatusBar.syncing") : t("components.syncStatusBar.idle")}
      </span>
      {status.last_run && <span className="text-gray-400">{t("components.syncStatusBar.lastRun", { date: new Date(status.last_run).toLocaleString() })}</span>}
      {status.last_stats && (
        <span className="text-gray-400">
          {t("components.syncStatusBar.stats", { new: status.last_stats.new, updated: status.last_stats.updated })}
        </span>
      )}
    </div>
  );
}
