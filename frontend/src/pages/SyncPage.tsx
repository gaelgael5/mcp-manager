import { useSyncStatus, useTriggerSync, useTriggerIndex, useTriggerScrapeSkills, useEnrichSkills, useStopEnrichSkills, useIndexSkills, useStopIndexSkills } from "../api/sync";
import { useCurrentUser } from "../api/auth";
import { Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { SyncStatusBar } from "../components/domain/SyncStatusBar";

export function SyncPage() {
  const { data: user } = useCurrentUser();
  const { data: status } = useSyncStatus();
  const triggerSync = useTriggerSync();
  const triggerIndex = useTriggerIndex();
  const scrapeSkills = useTriggerScrapeSkills();
  const enrichSkills = useEnrichSkills();
  const stopEnrich = useStopEnrichSkills();
  const indexSkills = useIndexSkills();
  const stopIndexSkills = useStopIndexSkills();

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
        </div>
        {status?.last_stats && (
          <div className="grid grid-cols-3 gap-4 text-center mt-4">
            <div><p className="text-2xl font-bold text-green-600">{status.last_stats.new}</p><p className="text-xs text-gray-500">New</p></div>
            <div><p className="text-2xl font-bold text-blue-600">{status.last_stats.updated}</p><p className="text-xs text-gray-500">Updated</p></div>
            <div><p className="text-2xl font-bold text-gray-400">{status.last_stats.unchanged}</p><p className="text-xs text-gray-500">Unchanged</p></div>
          </div>
        )}
      </Card>

      <Card title="Skills.sh Enrichment">
        <p className="text-sm text-gray-500 mb-3">
          Enrichit les Skill Sources : repo URL, summaries EN/FR, sync des skills depuis GitHub.
        </p>
        <div className="flex gap-3">
          <Button onClick={() => scrapeSkills.mutate({ limit: 10, skipSummaries: true })} loading={scrapeSkills.isPending || (status as any)?.scraping} disabled={(status as any)?.scraping || (status as any)?.enriching}>
            Scrape (10 test)
          </Button>
          <Button variant="secondary" onClick={() => scrapeSkills.mutate({})} loading={scrapeSkills.isPending || (status as any)?.scraping} disabled={(status as any)?.scraping || (status as any)?.enriching}>
            Scrape All
          </Button>
          {(status as any)?.enriching ? (
            <Button variant="danger" onClick={() => stopEnrich.mutate()} loading={stopEnrich.isPending}>
              Stop Enrich
            </Button>
          ) : (
            <Button onClick={() => enrichSkills.mutate()} loading={enrichSkills.isPending} disabled={(status as any)?.scraping}>
              Enrich Skills
            </Button>
          )}
        </div>
        {(status as any)?.enriching && (status as any)?.enrich_progress && (
          <div className="mt-3 text-sm text-blue-600">
            <p>Enrichissement : {(status as any).enrich_progress.done}/{(status as any).enrich_progress.total}</p>
            <p className="text-xs text-gray-500">
              Repos: {(status as any).enrich_progress.repos_filled} |
              Summaries: {(status as any).enrich_progress.summaries} |
              Syncs: {(status as any).enrich_progress.syncs} |
              Failed: {(status as any).enrich_progress.failed}
            </p>
          </div>
        )}
        {(status as any)?.scraping && <p className="text-sm text-blue-600 mt-2">Scraping in progress...</p>}
        {(status as any)?.last_enrich && (
          <div className="mt-3 text-xs text-gray-500">
            Last enrich: {(status as any).last_enrich.done} done, {(status as any).last_enrich.failed} failed,
            {" "}{(status as any).last_enrich.repos_filled} repos, {(status as any).last_enrich.summaries} summaries,
            {" "}{(status as any).last_enrich.syncs} syncs — {(status as any).last_enrich.time}
          </div>
        )}
      </Card>

      <Card title="Index Skills (Summary + RAG)">
        <p className="text-sm text-gray-500 mb-3">
          Genere les summaries EN/FR et indexe le RAG pour les skills avec needs_summary=true.
        </p>
        <div className="flex gap-3">
          {(status as any)?.indexing_skills ? (
            <Button variant="danger" onClick={() => stopIndexSkills.mutate()} loading={stopIndexSkills.isPending}>
              Stop Index Skills
            </Button>
          ) : (
            <Button onClick={() => indexSkills.mutate()} loading={indexSkills.isPending}>
              Index Skills
            </Button>
          )}
        </div>
        {(status as any)?.indexing_skills && (status as any)?.index_skills_progress && (
          <div className="mt-3 text-sm text-blue-600">
            <p>Index Skills : {(status as any).index_skills_progress.done}/{(status as any).index_skills_progress.total}</p>
            <p className="text-xs text-gray-500">
              Summaries: {(status as any).index_skills_progress.summaries} |
              Unchanged: {(status as any).index_skills_progress.unchanged} |
              Failed: {(status as any).index_skills_progress.failed}
            </p>
          </div>
        )}
        {(status as any)?.last_index_skills && (
          <div className="mt-3 text-xs text-gray-500">
            Last: {(status as any).last_index_skills.done} done, {(status as any).last_index_skills.summaries} summaries,
            {" "}{(status as any).last_index_skills.failed} failed — {(status as any).last_index_skills.time}
          </div>
        )}
      </Card>

      <Card title="Index MCP (Summary + Embeddings + Params + Recipes)">
        <p className="text-sm text-gray-500 mb-3">
          Starts LLM providers, indexes MCP services with needs_reindex=true, then stops providers.
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
          <Button variant="secondary" onClick={() => triggerIndex.mutate(5000)} loading={triggerIndex.isPending || indexing} disabled={indexing}>
            Index 5000
          </Button>
          <Button variant="danger" onClick={() => triggerIndex.mutate(999999)} loading={triggerIndex.isPending || indexing} disabled={indexing}>
            Index All
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
