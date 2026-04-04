import { useSyncStatus, useTriggerSync } from "../api/sync";
import { Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { SyncStatusBar } from "../components/domain/SyncStatusBar";

export function SyncPage() {
  const { data: status } = useSyncStatus();
  const triggerSync = useTriggerSync();

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Sync</h1>
      <SyncStatusBar status={status} />
      <div className="flex gap-3">
        <Button onClick={() => triggerSync.mutate(undefined)} loading={triggerSync.isPending || status?.running} disabled={status?.running}>
          Sync All Sources
        </Button>
        <Button variant="secondary" onClick={() => triggerSync.mutate("docker_registry")} loading={status?.running} disabled={status?.running}>
          Docker Registry Only
        </Button>
        <Button variant="secondary" onClick={() => triggerSync.mutate("mcp_registry")} loading={status?.running} disabled={status?.running}>
          MCP Registry Only
        </Button>
      </div>
      {status?.last_stats && (
        <Card title="Last Sync Results">
          <div className="grid grid-cols-3 gap-4 text-center">
            <div><p className="text-2xl font-bold text-green-600">{status.last_stats.new}</p><p className="text-xs text-gray-500">New</p></div>
            <div><p className="text-2xl font-bold text-blue-600">{status.last_stats.updated}</p><p className="text-xs text-gray-500">Updated</p></div>
            <div><p className="text-2xl font-bold text-gray-400">{status.last_stats.unchanged}</p><p className="text-xs text-gray-500">Unchanged</p></div>
          </div>
        </Card>
      )}
    </div>
  );
}
