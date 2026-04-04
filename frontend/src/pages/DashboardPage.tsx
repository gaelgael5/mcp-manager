import { useStats } from "../api/stats";
import { useSyncStatus } from "../api/sync";
import { Card } from "../components/ui/Card";
import { SyncStatusBar } from "../components/domain/SyncStatusBar";

export function DashboardPage() {
  const { data: stats } = useStats();
  const { data: syncStatus } = useSyncStatus();

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <SyncStatusBar status={syncStatus} />
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card title="Total Services">
          <p className="text-3xl font-bold">{stats?.total_services ?? "-"}</p>
        </Card>
        <Card title="By Source">
          {stats?.by_source ? (
            <ul className="space-y-1 text-sm">
              {Object.entries(stats.by_source).map(([k, v]) => (
                <li key={k} className="flex justify-between"><span>{k}</span><span className="font-medium">{v}</span></li>
              ))}
            </ul>
          ) : <p className="text-gray-400">-</p>}
        </Card>
        <Card title="Outdated Summaries">
          <p className="text-3xl font-bold">{stats?.outdated_summaries ?? "-"}</p>
        </Card>
      </div>
    </div>
  );
}
