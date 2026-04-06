import { useStats } from "../api/stats";
import { useSyncStatus } from "../api/sync";
import { Card } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { SyncStatusBar } from "../components/domain/SyncStatusBar";

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="text-center">
      <p className="text-3xl font-bold">{value}</p>
      <p className="text-xs text-gray-500 mt-1">{label}</p>
      {sub && <p className="text-xs text-gray-400">{sub}</p>}
    </div>
  );
}

function ProgressBar({ value, max, label, color = "blue" }: { value: number; max: number; label: string; color?: string }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0;
  const colors: Record<string, string> = {
    blue: "bg-blue-500",
    green: "bg-green-500",
    yellow: "bg-yellow-500",
    purple: "bg-purple-500",
  };
  return (
    <div>
      <div className="flex justify-between text-xs text-gray-500 mb-1">
        <span>{label}</span>
        <span>{value.toLocaleString()} / {max.toLocaleString()} ({pct}%)</span>
      </div>
      <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
        <div className={`h-full ${colors[color] || colors.blue} rounded-full`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

export function DashboardPage() {
  const { data: stats } = useStats();
  const { data: syncStatus } = useSyncStatus();
  const idx = stats?.indexation;
  const total = stats?.total_services ?? 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <SyncStatusBar status={syncStatus} />
      </div>

      {/* Headline stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card><StatCard label="Total Services" value={total.toLocaleString()} /></Card>
        <Card><StatCard label="Repos OK" value={(stats?.by_repo_status?.ok ?? 0).toLocaleString()} sub={`${((stats?.by_repo_status?.["404"] ?? 0)).toLocaleString()} en 404`} /></Card>
        <Card><StatCard label="With Summaries" value={(idx?.with_summaries ?? 0).toLocaleString()} /></Card>
        <Card><StatCard label="Needs Reindex" value={(idx?.needs_reindex ?? 0).toLocaleString()} /></Card>
      </div>

      {/* Indexation progress */}
      <Card title="MCP Services Indexation Progress">
        <div className="space-y-3">
          <ProgressBar value={idx?.with_summaries ?? 0} max={total} label="Summaries" color="blue" />
          <ProgressBar value={idx?.with_embeddings ?? 0} max={total} label="Embeddings" color="purple" />
          <ProgressBar value={idx?.with_installations ?? 0} max={total} label="Installations" color="green" />
          <ProgressBar value={idx?.with_params ?? 0} max={total} label="Parameters" color="yellow" />
          <div className="flex gap-4 text-xs text-gray-400 pt-1">
            <span>{(idx?.total_embeddings ?? 0).toLocaleString()} total embedding vectors</span>
            <span>{(idx?.outdated_summaries ?? 0)} outdated summaries</span>
          </div>
        </div>
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* By source */}
        <Card title="By Source">
          {stats?.by_source ? (
            <div className="space-y-2">
              {Object.entries(stats.by_source)
                .sort(([, a], [, b]) => b - a)
                .map(([k, v]) => (
                  <div key={k} className="flex items-center justify-between">
                    <Badge color="purple">{k}</Badge>
                    <span className="text-sm font-medium">{v.toLocaleString()}</span>
                  </div>
                ))}
            </div>
          ) : <p className="text-gray-400">-</p>}
        </Card>

        {/* Top categories */}
        <Card title="Top Categories">
          {stats?.by_category ? (
            <div className="space-y-1">
              {Object.entries(stats.by_category)
                .sort(([, a], [, b]) => b - a)
                .slice(0, 15)
                .map(([k, v]) => (
                  <div key={k} className="flex items-center justify-between text-sm">
                    <span className="text-gray-600">{k}</span>
                    <span className="font-medium">{v.toLocaleString()}</span>
                  </div>
                ))}
            </div>
          ) : <p className="text-gray-400">-</p>}
        </Card>
      </div>

      {/* Repo status */}
      <Card title="Repository Status">
        {stats?.by_repo_status ? (
          <div className="flex gap-6">
            {Object.entries(stats.by_repo_status)
              .sort(([, a], [, b]) => b - a)
              .map(([k, v]) => (
                <div key={k} className="text-center">
                  <p className="text-2xl font-bold">{v.toLocaleString()}</p>
                  <Badge color={k === "ok" ? "green" : k === "404" ? "red" : "gray"}>{k}</Badge>
                </div>
              ))}
          </div>
        ) : <p className="text-gray-400">-</p>}
      </Card>
    </div>
  );
}
