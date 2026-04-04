import type { SyncStatus } from "../../types";

export function SyncStatusBar({ status }: { status: SyncStatus | undefined }) {
  if (!status) return null;
  return (
    <div className="flex items-center gap-4 text-sm">
      <span className={`inline-flex items-center gap-1.5 ${status.running ? "text-blue-600" : "text-gray-500"}`}>
        {status.running && <span className="h-2 w-2 animate-pulse rounded-full bg-blue-600" />}
        {status.running ? "Syncing..." : "Idle"}
      </span>
      {status.last_run && <span className="text-gray-400">Last: {new Date(status.last_run).toLocaleString()}</span>}
      {status.last_stats && (
        <span className="text-gray-400">
          {status.last_stats.new} new, {status.last_stats.updated} updated
        </span>
      )}
    </div>
  );
}
