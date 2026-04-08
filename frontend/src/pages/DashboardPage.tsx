import { useStats } from "../api/stats";
import { useSyncStatus } from "../api/sync";
import { Card } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { SyncStatusBar } from "../components/domain/SyncStatusBar";

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

function Throughput({ value }: { value?: number }) {
  if (!value) return null;
  return <span className="text-xs text-yellow-600 font-normal">{value}/h</span>;
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

      {/* Indexation progress */}
      <Card title={
        <span className="flex items-center gap-2">
          MCP Services Indexation Progress
          {((syncStatus as any)?.running || (syncStatus as any)?.indexing) && (<>
            <span className="text-yellow-500 animate-pulse">⚡</span>
            <Throughput value={(syncStatus as any)?.indexing_throughput} />
          </>)}
        </span>
      }>
        <div className="space-y-3">
          <ProgressBar value={total - (idx?.needs_reindex ?? 0)} max={total} label="Traitement global" color="green" />
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

      {/* Skill Sources Progress */}
      <Card title={
        <span className="flex items-center gap-2">
          Skill Sources Enrichment Progress
          {(syncStatus as any)?.enriching && (<>
            <span className="text-yellow-500 animate-pulse">⚡</span>
            <Throughput value={(syncStatus as any)?.enriching_throughput} />
          </>)}
        </span>
      }>
        <div className="space-y-3">
          <ProgressBar value={((stats as any)?.skill_sources?.by_enrichment?.done ?? 0)} max={(stats as any)?.skill_sources?.total ?? 0} label="Traitement global" color="green" />
          <ProgressBar value={(stats as any)?.skill_sources?.with_repo ?? 0} max={(stats as any)?.skill_sources?.total ?? 0} label="Repo URL" color="blue" />
          <ProgressBar value={(stats as any)?.skill_sources?.with_summary_en ?? 0} max={(stats as any)?.skill_sources?.total ?? 0} label="Summary EN" color="purple" />
          <ProgressBar value={(stats as any)?.skill_sources?.with_summary_fr ?? 0} max={(stats as any)?.skill_sources?.total ?? 0} label="Summary FR" color="purple" />
          <ProgressBar value={(stats as any)?.skill_sources?.synced ?? 0} max={(stats as any)?.skill_sources?.total ?? 0} label="Synced" color="green" />
          <ProgressBar value={(stats as any)?.skill_sources?.with_rag ?? 0} max={(stats as any)?.skill_sources?.total ?? 0} label="RAG Indexed" color="yellow" />
          <div className="flex gap-4 text-xs text-gray-400 pt-1">
            {(stats as any)?.skill_sources?.by_enrichment && Object.entries((stats as any).skill_sources.by_enrichment).map(([k, v]) => (
              <span key={k}>{k}: {(v as number).toLocaleString()}</span>
            ))}
          </div>
        </div>
      </Card>

      {/* Skills Progress */}
      <Card title={
        <span className="flex items-center gap-2">
          Skills Indexation Progress
          {(syncStatus as any)?.indexing_skills && (<>
            <span className="text-yellow-500 animate-pulse">⚡</span>
            <Throughput value={(syncStatus as any)?.indexing_skills_throughput} />
          </>)}
        </span>
      }>
        <div className="space-y-3">
          <ProgressBar value={((stats as any)?.skills?.total ?? 0) - ((stats as any)?.skills?.needs_summary ?? 0)} max={(stats as any)?.skills?.total ?? 0} label="Traitement global" color="green" />
          <ProgressBar value={(stats as any)?.skills?.with_summary ?? 0} max={(stats as any)?.skills?.total ?? 0} label="With Summary" color="blue" />
          <ProgressBar value={(stats as any)?.skills?.with_rag ?? 0} max={(stats as any)?.skills?.total ?? 0} label="RAG Indexed" color="purple" />
        </div>
      </Card>

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
