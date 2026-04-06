import { useSyncStatus, useTriggerSync, useTriggerIndex } from "../api/sync";
import { useCurrentUser } from "../api/auth";
import { Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { SyncStatusBar } from "../components/domain/SyncStatusBar";

export function SyncPage() {
  const { data: user } = useCurrentUser();
  const { data: status } = useSyncStatus();
  const triggerSync = useTriggerSync();
  const triggerIndex = useTriggerIndex();

  if (!user?.is_admin) {
    return <p className="text-gray-500">Admin access required.</p>;
  }

  const indexing = (status as any)?.indexing === true;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Sync & Index</h1>
      <SyncStatusBar status={status} />

      <Card title="Sync Sources">
        <div className="flex gap-3">
          <Button onClick={() => triggerSync.mutate(undefined)} loading={triggerSync.isPending || status?.running} disabled={status?.running}>
            Sync All Sources
          </Button>
          <Button variant="secondary" onClick={() => triggerSync.mutate("docker_registry")} loading={status?.running} disabled={status?.running}>
            Docker Registry
          </Button>
          <Button variant="secondary" onClick={() => triggerSync.mutate("mcp_registry")} loading={status?.running} disabled={status?.running}>
            MCP Registry
          </Button>
          <Button variant="secondary" onClick={() => triggerSync.mutate("glama")} loading={status?.running} disabled={status?.running}>
            Glama
          </Button>
        </div>
        {status?.last_stats && (
          <div className="grid grid-cols-3 gap-4 text-center mt-4">
            <div><p className="text-2xl font-bold text-green-600">{status.last_stats.new}</p><p className="text-xs text-gray-500">New</p></div>
            <div><p className="text-2xl font-bold text-blue-600">{status.last_stats.updated}</p><p className="text-xs text-gray-500">Updated</p></div>
            <div><p className="text-2xl font-bold text-gray-400">{status.last_stats.unchanged}</p><p className="text-xs text-gray-500">Unchanged</p></div>
          </div>
        )}
      </Card>

      <Card title="Index (Summary + Embeddings + Params + Recipes)">
        <p className="text-sm text-gray-500 mb-3">
          Starts LLM providers, indexes services with needs_reindex=true, then stops providers.
        </p>
        <div className="flex gap-3">
          <Button onClick={() => triggerIndex.mutate(100)} loading={triggerIndex.isPending || indexing} disabled={indexing}>
            Index 100
          </Button>
          <Button variant="secondary" onClick={() => triggerIndex.mutate(500)} loading={triggerIndex.isPending || indexing} disabled={indexing}>
            Index 500
          </Button>
          <Button variant="secondary" onClick={() => triggerIndex.mutate(1000)} loading={triggerIndex.isPending || indexing} disabled={indexing}>
            Index 1000
          </Button>
        </div>
        {indexing && <p className="text-sm text-blue-600 mt-2">Indexing in progress...</p>}
        {(status as any)?.last_index && (
          <div className="mt-3 text-xs text-gray-500">
            Last index: {JSON.stringify((status as any).last_index.stats)} — {(status as any).last_index.time}
          </div>
        )}
      </Card>
    </div>
  );
}
