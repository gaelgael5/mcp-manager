import { useStats } from "../api/stats";
import { useSyncStatus } from "../api/sync";
import { Card } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { SyncStatusBar } from "../components/domain/SyncStatusBar";
import { useTranslation } from "../i18n";

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

function formatEta(remaining: number, throughputPerHour: number): string | null {
  if (throughputPerHour <= 0 || remaining <= 0) return null;
  let totalMin = Math.ceil((remaining / throughputPerHour) * 60);
  const days = Math.floor(totalMin / 1440);
  totalMin -= days * 1440;
  const hours = Math.floor(totalMin / 60);
  const min = totalMin - hours * 60;
  const parts: string[] = [];
  if (days > 0) parts.push(`${days}j`);
  if (hours > 0) parts.push(`${hours}h`);
  parts.push(`${min}min`);
  return parts.join(" ");
}

function ETA({ processed, total, throughput }: { processed?: number; total?: number; throughput?: number }) {
  if (!throughput || !total || processed == null) return null;
  const remaining = total - processed;
  const eta = formatEta(remaining, throughput);
  if (!eta) return null;
  return <span className="text-xs text-gray-400 font-normal">~ {eta}</span>;
}

interface TranslationsProgress {
  languages: { code: string; name: string; is_baseline: boolean }[];
  mcp: Record<string, number>;
  skill_sources: Record<string, number>;
  skills: Record<string, number>;
}

function LanguageProgress({
  title,
  counts,
  languages,
}: {
  title: string;
  counts: Record<string, number>;
  languages: { code: string; name: string; is_baseline: boolean }[];
}) {
  const others = languages.filter((l) => !l.is_baseline);
  if (others.length === 0) return null;
  const baseline = counts.en ?? 0;
  return (
    <Card title={title}>
      <div className="space-y-2">
        <div className="text-xs text-gray-500">
          Baseline (English): {baseline.toLocaleString()}
        </div>
        {others.map((lang) => {
          const n = counts[lang.code] ?? 0;
          const missing = Math.max(baseline - n, 0);
          return (
            <ProgressBar
              key={lang.code}
              value={n}
              max={baseline}
              label={`${lang.name} (${lang.code}) — ${missing.toLocaleString()} missing`}
              color="blue"
            />
          );
        })}
      </div>
    </Card>
  );
}

function DriverChips({ batchId, syncStatus }: { batchId: string; syncStatus: any }) {
  const drivers = (syncStatus as any)?.driver_stats?.[batchId];
  if (!drivers?.length) return null;
  return (
    <div className="flex gap-1.5 flex-wrap mt-1">
      {drivers.map((d: any, i: number) => (
        <span key={i} className="inline-flex items-center gap-1 rounded-full bg-gray-100 px-2 py-0.5 text-xs">
          <span className={`h-1.5 w-1.5 rounded-full ${d.requests > 0 ? "bg-green-500" : "bg-gray-300"}`} />
          <span className="font-medium">{d.name}</span>
          <span className="text-gray-400">{d.requests}</span>
        </span>
      ))}
    </div>
  );
}

export function DashboardPage() {
  const { t } = useTranslation();
  const { data: stats } = useStats();
  const { data: syncStatus } = useSyncStatus();
  const idx = stats?.indexation;
  const total = stats?.total_services ?? 0;
  const progress = (stats as any)?.translations_progress as TranslationsProgress | undefined;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">{t("pages.dashboard.title")}</h1>
        <SyncStatusBar status={syncStatus} />
      </div>

      {/* Indexation progress */}
      <Card title={
        <span className="flex items-center gap-2">
          {t("pages.dashboard.mcpIndexationTitle")}
          {((syncStatus as any)?.running || (syncStatus as any)?.indexing) && (<>
            <span className="text-yellow-500 animate-pulse">⚡</span>
            <Throughput value={(syncStatus as any)?.indexing_throughput} />
            <ETA processed={(syncStatus as any)?.indexing_progress?.processed} total={(syncStatus as any)?.indexing_progress?.total} throughput={(syncStatus as any)?.indexing_throughput} />
          </>)}
        </span>
      }>
        <div className="space-y-3">
          <ProgressBar value={total - (idx?.needs_reindex ?? 0)} max={total} label={t("pages.dashboard.overallProcessing")} color="green" />
          <ProgressBar value={idx?.with_summaries ?? 0} max={total} label={t("pages.dashboard.summaries")} color="blue" />
          <ProgressBar value={idx?.with_installations ?? 0} max={total} label={t("pages.dashboard.installations")} color="yellow" />
          <ProgressBar value={idx?.with_params ?? 0} max={total} label={t("pages.dashboard.parameters")} color="yellow" />
          <ProgressBar value={((stats as any)?.rag_pending?.mcp_total ?? 0) - ((stats as any)?.rag_pending?.mcp ?? 0)} max={(stats as any)?.rag_pending?.mcp_total ?? 0} label={t("pages.dashboard.ragIndexed")} color="purple" />
          <div className="flex gap-4 text-xs text-gray-400 pt-1">
            <span>{(idx?.total_embeddings ?? 0).toLocaleString()} {t("pages.dashboard.totalEmbeddings")}</span>
            <span>{(idx?.outdated_summaries ?? 0)} {t("pages.dashboard.outdatedSummaries")}</span>
            {((stats as any)?.rag_pending?.total ?? 0) > 0 && (
              <span className="text-yellow-500">{(stats as any).rag_pending.total} {t("pages.dashboard.ragPending")}</span>
            )}
          </div>
          <DriverChips batchId="mcp" syncStatus={syncStatus} />
        </div>
      </Card>

      {/* Skill Sources Progress */}
      <Card title={
        <span className="flex items-center gap-2">
          {t("pages.dashboard.skillSourcesEnrichmentTitle")}
          {(syncStatus as any)?.enriching && (<>
            <span className="text-yellow-500 animate-pulse">⚡</span>
            <Throughput value={(syncStatus as any)?.enriching_throughput} />
            <ETA processed={(syncStatus as any)?.enrich_progress?.done} total={(syncStatus as any)?.enrich_progress?.total} throughput={(syncStatus as any)?.enriching_throughput} />
          </>)}
        </span>
      }>
        <div className="space-y-3">
          <ProgressBar value={((stats as any)?.skill_sources?.by_enrichment?.done ?? 0)} max={(stats as any)?.skill_sources?.total ?? 0} label={t("pages.dashboard.overallProcessing")} color="green" />
          <ProgressBar value={(stats as any)?.skill_sources?.with_summary_en ?? 0} max={(stats as any)?.skill_sources?.total ?? 0} label={t("pages.dashboard.summaries")} color="blue" />
          <ProgressBar value={(stats as any)?.skill_sources?.synced ?? 0} max={(stats as any)?.skill_sources?.total ?? 0} label={t("pages.dashboard.synced")} color="yellow" />
          <ProgressBar value={((stats as any)?.rag_pending?.sources_total ?? 0) - ((stats as any)?.rag_pending?.sources ?? 0)} max={(stats as any)?.rag_pending?.sources_total ?? 0} label={t("pages.dashboard.ragIndexed")} color="purple" />
          <div className="flex gap-4 text-xs text-gray-400 pt-1">
            {(stats as any)?.skill_sources?.by_enrichment && Object.entries((stats as any).skill_sources.by_enrichment).map(([k, v]) => (
              <span key={k}>{k}: {(v as number).toLocaleString()}</span>
            ))}
            {((stats as any)?.rag_pending?.sources ?? 0) > 0 && (
              <span className="text-yellow-500">{(stats as any).rag_pending.sources} {t("pages.dashboard.ragPending")}</span>
            )}
          </div>
          <DriverChips batchId="enrich" syncStatus={syncStatus} />
        </div>
      </Card>

      {/* Skills Progress */}
      <Card title={
        <span className="flex items-center gap-2">
          {t("pages.dashboard.skillsIndexationTitle")}
          {(syncStatus as any)?.indexing_skills && (<>
            <span className="text-yellow-500 animate-pulse">⚡</span>
            <Throughput value={(syncStatus as any)?.indexing_skills_throughput} />
            <ETA processed={(syncStatus as any)?.index_skills_progress?.done} total={(syncStatus as any)?.index_skills_progress?.total} throughput={(syncStatus as any)?.indexing_skills_throughput} />
          </>)}
        </span>
      }>
        <div className="space-y-3">
          <ProgressBar value={((stats as any)?.skills?.total ?? 0) - ((stats as any)?.skills?.needs_summary ?? 0)} max={(stats as any)?.skills?.total ?? 0} label={t("pages.dashboard.overallProcessing")} color="green" />
          <ProgressBar value={(stats as any)?.skills?.with_summary ?? 0} max={(stats as any)?.skills?.total ?? 0} label={t("pages.dashboard.summaries")} color="blue" />
          <ProgressBar value={((stats as any)?.rag_pending?.skills_total ?? 0) - ((stats as any)?.rag_pending?.skills ?? 0)} max={(stats as any)?.rag_pending?.skills_total ?? 0} label={t("pages.dashboard.ragIndexed")} color="purple" />
          <div className="flex gap-4 text-xs text-gray-400 pt-1">
            {((stats as any)?.rag_pending?.skills ?? 0) > 0 && (
              <span className="text-yellow-500">{(stats as any).rag_pending.skills} {t("pages.dashboard.ragPending")}</span>
            )}
          </div>
          <DriverChips batchId="skills" syncStatus={syncStatus} />
        </div>
      </Card>

      {/* Translations progress per language */}
      {progress && progress.languages.filter((l) => !l.is_baseline).length > 0 && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <LanguageProgress
            title={t("pages.dashboard.mcpTranslations")}
            counts={progress.mcp}
            languages={progress.languages}
          />
          <LanguageProgress
            title={t("pages.dashboard.skillSourcesTranslations")}
            counts={progress.skill_sources}
            languages={progress.languages}
          />
          <LanguageProgress
            title={t("pages.dashboard.skillsTranslations")}
            counts={progress.skills}
            languages={progress.languages}
          />
        </div>
      )}

      {/* Disk usage */}
      {(stats as any)?.disk && (
        <div className="flex items-center gap-3 text-xs text-gray-500">
          <span>{t("pages.dashboard.diskLabel")}</span>
          <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden max-w-xs">
            <div
              className={`h-full rounded-full ${(stats as any).disk.percent > 90 ? "bg-red-500" : (stats as any).disk.percent > 75 ? "bg-yellow-500" : "bg-green-500"}`}
              style={{ width: `${(stats as any).disk.percent}%` }}
            />
          </div>
          <span>{(stats as any).disk.used_gb}G / {(stats as any).disk.total_gb}G ({(stats as any).disk.free_gb}G free)</span>
        </div>
      )}

      {/* Repo status */}
      <Card title={t("pages.dashboard.repositoryStatusTitle")}>
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
