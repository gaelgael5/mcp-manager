import { useState } from "react";
import { useSyncStatus, useTriggerSync, useTriggerIndex, useStopIndex, useRagIndex, useStopRagIndex, useStartAgents, useStopAgents, useEvalHeuristic, useStopEvalHeuristic, useEvalLLM, useStopEvalLLM, useEvalStats } from "../api/sync";
import { useCurrentUser } from "../api/auth";
import { Card } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { SyncStatusBar } from "../components/domain/SyncStatusBar";
import { apiFetch } from "../api/client";

function RecentItems({ scope }: { scope: "mcp" }) {
  const [items, setItems] = useState<{ id: number; name: string; url: string }[] | null>(null);
  const [loading, setLoading] = useState(false);

  const fetch = async () => {
    setLoading(true);
    try {
      const data = await apiFetch<{ id: number; name: string; url: string }[]>(`/services/sync/recent/${scope}`);
      setItems(data);
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mt-3 flex items-start gap-3">
      <Button size="sm" variant="secondary" onClick={fetch} loading={loading}>
        5 derniers
      </Button>
      {items && items.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {items.map((item) => (
            <a
              key={item.id}
              href={item.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-blue-600 hover:underline bg-blue-50 px-2 py-1 rounded"
              title={item.name}
            >
              {item.name.length > 30 ? item.name.slice(0, 30) + "…" : item.name}
            </a>
          ))}
        </div>
      )}
      {items && items.length === 0 && (
        <span className="text-xs text-gray-400">Aucun item traité</span>
      )}
    </div>
  );
}

function p20Color(value: number | null | undefined): string {
  if (value == null) return "text-gray-400";
  if (value >= 60) return "text-green-600";
  if (value >= 30) return "text-orange-500";
  return "text-red-500";
}

function QualityEval({ scope, evalStats }: { scope: string; evalStats: any }) {
  const evalHeuristic = useEvalHeuristic();
  const stopHeuristic = useStopEvalHeuristic();
  const evalLLM = useEvalLLM();
  const stopLLM = useStopEvalLLM();

  const stats = evalStats?.[scope];
  if (!stats && !evalStats) return null;

  const hRunning = stats?.heuristic_running;
  const lRunning = stats?.llm_running;
  const hProgress = stats?.heuristic_progress;
  const lProgress = stats?.llm_progress;

  return (
    <div className="mt-4 pt-3 border-t border-gray-200">
      <p className="text-xs font-semibold text-gray-500 mb-2">Quality Eval</p>
      <div className="flex gap-2 items-center mb-2">
        {hRunning ? (
          <Button size="sm" variant="danger" onClick={() => stopHeuristic.mutate(scope)} loading={stopHeuristic.isPending}>
            Stop Heuristic
          </Button>
        ) : (
          <Button size="sm" variant="secondary" onClick={() => evalHeuristic.mutate(scope)} loading={evalHeuristic.isPending}>
            Eval Heuristic
          </Button>
        )}
        {lRunning ? (
          <Button size="sm" variant="danger" onClick={() => stopLLM.mutate(scope)} loading={stopLLM.isPending}>
            Stop LLM
          </Button>
        ) : (
          <Button size="sm" variant="secondary" onClick={() => evalLLM.mutate(scope)} loading={evalLLM.isPending}>
            Eval LLM
          </Button>
        )}
      </div>
      {hRunning && hProgress && (
        <p className="text-xs text-blue-600 mb-1">Heuristic: {hProgress.done}/{hProgress.total}</p>
      )}
      {lRunning && lProgress && (
        <p className="text-xs text-blue-600 mb-1">LLM: {lProgress.done}/{lProgress.total}{lProgress.failed > 0 ? ` (${lProgress.failed} failed)` : ""}</p>
      )}
      <div className="flex gap-6 text-sm">
        <div>
          <span className="text-gray-500">P20 heuristic: </span>
          <span className={`font-bold ${p20Color(stats?.p20_heuristic)}`}>
            {stats?.p20_heuristic != null ? `${stats.p20_heuristic}/100` : "--"}
          </span>
          <span className="text-xs text-gray-400 ml-1">({stats?.heuristic_count ?? 0})</span>
        </div>
        <div>
          <span className="text-gray-500">P20 LLM: </span>
          <span className={`font-bold ${p20Color(stats?.p20_llm)}`}>
            {stats?.p20_llm != null ? `${stats.p20_llm}/100` : "--"}
          </span>
          <span className="text-xs text-gray-400 ml-1">({stats?.llm_count ?? 0})</span>
        </div>
      </div>
    </div>
  );
}

function DockerAgents({ batchId, status }: { batchId: string; status: any }) {
  const agents = (status as any)?.docker_agents;
  const startAgents = useStartAgents();
  const stopAgents = useStopAgents();
  const driverStats = (status as any)?.driver_stats?.[batchId];

  if (!agents?.providers?.length) return null;
  const containers = agents.batches?.[batchId] || [];
  if (!containers.length) return null;

  return (
    <div className="flex gap-2 items-center flex-wrap mt-2">
      <span className="text-xs text-gray-400">Agents:</span>
      {containers.map((c: any) => {
        const provider = agents.providers.find((p: any) => p.id === c.provider_id);
        const imageOk = provider?.image_exists;
        const ds = driverStats?.find((d: any) => d.name === c.image);
        const reqCount = ds?.requests ?? 0;
        return (
          <span key={c.container} className="inline-flex items-center gap-1">
            <Badge color={c.running ? "green" : imageOk ? "gray" : "red"}>
              {c.image}
              {c.running && reqCount > 0 && <span className="ml-1 text-[10px] opacity-70">{reqCount}</span>}
            </Badge>
            {c.running ? (
              <button
                onClick={() => stopAgents.mutate({ batchId, providerId: c.provider_id })}
                className="text-[10px] text-red-400 hover:text-red-600"
                title={`Stop ${c.image}`}
              >
                ■
              </button>
            ) : imageOk ? (
              <button
                onClick={() => startAgents.mutate({ batchId, providerId: c.provider_id })}
                className="text-[10px] text-green-500 hover:text-green-700"
                title={`Start ${c.image}`}
              >
                ▶
              </button>
            ) : (
              <span className="text-[10px] text-red-400">no img</span>
            )}
          </span>
        );
      })}
    </div>
  );
}

export function SyncPage() {
  const { data: user } = useCurrentUser();
  const { data: status } = useSyncStatus();
  const triggerSync = useTriggerSync();
  const triggerIndex = useTriggerIndex();
  const stopIndex = useStopIndex();
  const ragIndex = useRagIndex();
  const stopRag = useStopRagIndex();
  const { data: evalStats } = useEvalStats();

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
          <Button variant="secondary" onClick={() => triggerSync.mutate("pulsemcp")} loading={status?.running} disabled={status?.running}>
            PulseMCP
          </Button>
          <Button variant="secondary" onClick={() => triggerSync.mutate("mcp_servers_repo")} loading={status?.running} disabled={status?.running}>
            MCP Servers Repo
          </Button>
          <Button variant="secondary" onClick={() => triggerSync.mutate("github_topics")} loading={status?.running} disabled={status?.running}>
            GitHub Topics
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

      <Card title="Index MCP (Summary + Params + Recipes)">
        <p className="text-sm text-gray-500 mb-3">
          Indexe les MCP services (summaries, params, recettes) et genere les embeddings RAG.
        </p>
        <div className="flex gap-3">
          {indexing ? (
            <Button variant="danger" onClick={() => stopIndex.mutate()} loading={stopIndex.isPending}>
              Stop Index MCP
            </Button>
          ) : (
            <Button onClick={() => triggerIndex.mutate(999999)} loading={triggerIndex.isPending} disabled={(status as any)?.rag_indexing}>
              Index All
            </Button>
          )}
          {(status as any)?.rag_indexing && (status as any)?.rag_scope === "mcp" ? (
            <Button variant="danger" onClick={() => stopRag.mutate()} loading={stopRag.isPending}>
              Stop RAG
            </Button>
          ) : (
            <Button variant="secondary" onClick={() => ragIndex.mutate("mcp")} loading={ragIndex.isPending} disabled={indexing || (status as any)?.rag_indexing}>
              RAG Index
            </Button>
          )}
        </div>
        {indexing && (status as any)?.indexing_progress && (
          <div className="mt-3 text-sm text-blue-600">
            <p>Index MCP : {(status as any).indexing_progress.processed}/{(status as any).indexing_progress.total}</p>
            <p className="text-xs text-gray-500">
              Summaries: {(status as any).indexing_progress.summaries} |
              Params: {(status as any).indexing_progress.params} |
              Recipes: {(status as any).indexing_progress.recipes} |
              Skipped: {(status as any).indexing_progress.skipped_no_doc}
            </p>
          </div>
        )}
        {(status as any)?.rag_indexing && (status as any)?.rag_progress && (
          <div className="mt-3 text-sm text-blue-600">
            <p>RAG Index : {(status as any).rag_progress.done}/{(status as any).rag_progress.total}</p>
            <p className="text-xs text-gray-500">
              MCP Summaries: {(status as any).rag_progress.mcp_summaries} |
              Failed: {(status as any).rag_progress.failed}
            </p>
          </div>
        )}
        {(status as any)?.last_index && (
          <div className="mt-3 text-xs text-gray-500">
            Last index: {(status as any).last_index.stats?.processed} processed, {(status as any).last_index.stats?.summaries} summaries,
            {" "}{(status as any).last_index.stats?.skipped_no_doc} skipped — {(status as any).last_index.time}
          </div>
        )}
        {(status as any)?.last_rag && (
          <div className="mt-3 text-xs text-gray-500">
            Last RAG: {(status as any).last_rag.mcp_summaries} MCP, {(status as any).last_rag.failed} failed — {(status as any).last_rag.time}
          </div>
        )}
        <RecentItems scope="mcp" />
        <DockerAgents batchId="mcp" status={status} />
        <QualityEval scope="mcp" evalStats={evalStats} />
      </Card>
    </div>
  );
}
