# Enrich Skills Pipeline — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the "Fill repo URLs" button with a full enrichment pipeline that fills repo URLs, generates summaries, syncs skills, is stoppable, and resumes after redeployments.

**Architecture:** A new `enrichment_status` column on `skill_sources` tracks each source's state (`pending`/`enriching`/`done`/`failed`). The pipeline iterates over all non-`done` sources, running 3 steps per source (fill repo, summary, sync). A cancel flag allows graceful stop. On backend startup, `enriching` rows are reset to `pending` so interrupted work resumes on next run.

**Tech Stack:** FastAPI background tasks, SQLAlchemy async, httpx, Ollama (existing), React/TanStack Query (existing)

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `backend/mcp_manager/db/models.py` | Modify | Add `enrichment_status` column to `SkillSource` |
| `backend/mcp_manager/api/routers/sync.py` | Modify | Replace `fill-skill-repo-urls` with `enrich-skills` pipeline + stop endpoint |
| `backend/mcp_manager/api/routers/skill_sources.py` | Modify | Extract summary/sync logic into reusable functions |
| `backend/mcp_manager/api/app.py` | Modify | Add startup hook to reset `enriching` → `pending` |
| `frontend/src/api/sync.ts` | Modify | Replace `useFillSkillRepoUrls` with `useEnrichSkills` + `useStopEnrichSkills` |
| `frontend/src/pages/SyncPage.tsx` | Modify | Replace "Fill repo URLs" button with "Enrich Skills" + "Stop" |

---

### Task 1: Add `enrichment_status` column to `SkillSource`

**Files:**
- Modify: `backend/mcp_manager/db/models.py:160-188`

- [ ] **Step 1: Add the column to the model**

In `backend/mcp_manager/db/models.py`, add after the `stars` field (line 183):

```python
enrichment_status: Mapped[str] = mapped_column(
    String(20), default="pending", server_default="pending"
)  # pending, enriching, done, failed
```

- [ ] **Step 2: Run ALTER TABLE on the server**

```bash
ssh -i ~/.ssh/id_shellia root@192.168.10.99 "cd /root/mcp-manager && docker compose exec mcp-manager-postgres psql -U langgraph -d langgraph -c \"ALTER TABLE skill_sources ADD COLUMN IF NOT EXISTS enrichment_status varchar(20) DEFAULT 'pending';\""
```

- [ ] **Step 3: Set existing enriched sources to 'done'**

Sources that already have `summary_en` AND `last_sync` should be marked `done`:

```bash
ssh -i ~/.ssh/id_shellia root@192.168.10.99 "cd /root/mcp-manager && docker compose exec mcp-manager-postgres psql -U langgraph -d langgraph -c \"UPDATE skill_sources SET enrichment_status = 'done' WHERE summary_en IS NOT NULL AND last_sync IS NOT NULL;\""
```

- [ ] **Step 4: Commit**

```bash
git add backend/mcp_manager/db/models.py
git commit -m "feat: ajout enrichment_status sur skill_sources"
```

---

### Task 2: Extract reusable enrichment functions from `skill_sources.py`

**Files:**
- Modify: `backend/mcp_manager/api/routers/skill_sources.py`

The existing `generate_source_summary` and `sync_skill_source` endpoints contain the logic we need, but they're coupled to HTTP request/response. Extract the core logic into standalone async functions that take a `db` session and a `SkillSource` object.

- [ ] **Step 1: Extract `_enrich_repo_url` function**

Add at the bottom of `skill_sources.py`, before `_serialize_source`:

```python
async def _enrich_repo_url(source: SkillSource) -> bool:
    """Fill repo_url by scraping skills.sh page. Returns True if updated."""
    import re
    import httpx

    if source.repo_url:
        return False
    if not source.url or "skills.sh" not in source.url:
        # Derive from URL pattern
        derived = _derive_repo_url(source.url)
        if derived:
            source.repo_url = derived
            return True
        return False

    try:
        async with httpx.AsyncClient(timeout=20.0, headers={"User-Agent": "MCPManager/1.0"}, follow_redirects=True) as client:
            resp = await client.get(source.url)
            if resp.status_code == 200:
                text = re.sub(r"<[^>]+>", " ", resp.text)
                m = re.search(r"npx\s+skills\s+add\s+(https?://[^\s\"'<]+)", text)
                if m:
                    source.repo_url = m.group(1)
                    return True
    except Exception:
        pass
    return False
```

- [ ] **Step 2: Extract `_enrich_summaries` function**

```python
async def _enrich_summaries(source: SkillSource, db: AsyncSession) -> bool:
    """Generate EN/FR summaries if missing. Returns True if generated."""
    import os
    from mcp_manager.summarizer.ollama_client import ollama_generate
    from mcp_manager.summarizer.cleaner import clean_markdown
    from mcp_manager.connectors.github_readme import fetch_github_readme

    if source.summary_en and source.summary_fr:
        return False

    # Derive repo_url if missing
    if not source.repo_url:
        source.repo_url = _derive_repo_url(source.url)

    context = ""
    if source.repo_url:
        readme = await fetch_github_readme(source.repo_url)
        if readme:
            context = clean_markdown(readme)
            if len(context) > 6000:
                context = context[:6000]

    if not context:
        context = f"Skill source: {source.name}\nURL: {source.url}\nType: {source.type}"

    prompts_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "prompts")

    if not source.summary_en:
        with open(os.path.join(prompts_dir, "source_summary_en.md"), encoding="utf-8") as f:
            prompt_en = f.read().replace("{content}", context)
        source.summary_en = await ollama_generate(prompt_en)
        if not source.summary_en:
            source.summary_en = await ollama_generate(prompt_en)
        source.summary_en = source.summary_en or None

    if not source.summary_fr:
        with open(os.path.join(prompts_dir, "source_summary_fr.md"), encoding="utf-8") as f:
            prompt_fr = f.read().replace("{content}", context)
        source.summary_fr = await ollama_generate(prompt_fr)
        if not source.summary_fr:
            source.summary_fr = await ollama_generate(prompt_fr)
        source.summary_fr = source.summary_fr or None

    return bool(source.summary_en or source.summary_fr)
```

- [ ] **Step 3: Extract `_enrich_sync_skills` function**

```python
async def _enrich_sync_skills(source: SkillSource, db: AsyncSession) -> int:
    """Sync skills from GitHub repo if not yet synced. Returns count of skills added/updated."""
    from datetime import datetime, timezone

    if source.last_sync:
        return 0

    if not source.repo_url:
        source.repo_url = _derive_repo_url(source.url)

    if not source.repo_url:
        return 0

    from mcp_manager.connectors.skillssh_scanner import scan_repo_skills
    scan_result = await scan_repo_skills(source.repo_url)
    source.repo_status = scan_result["status"]
    raw_skills = scan_result["skills"]

    # Fetch GitHub stars (best-effort)
    import httpx
    from mcp_manager.config import settings as _settings
    try:
        parts = source.repo_url.rstrip("/").split("/")
        owner, repo = parts[-2], parts[-1]
        headers = {"Accept": "application/vnd.github.v3+json"}
        if _settings.github_token:
            headers["Authorization"] = f"token {_settings.github_token}"
        async with httpx.AsyncClient(timeout=10.0) as gh:
            resp = await gh.get(f"https://api.github.com/repos/{owner}/{repo}", headers=headers)
            if resp.status_code == 200:
                source.stars = resp.json().get("stargazers_count")
    except Exception:
        pass

    added = 0
    for raw in raw_skills:
        existing = await db.execute(
            select(Skill)
            .join(skill_source_skills, skill_source_skills.c.skill_id == Skill.id)
            .where(
                skill_source_skills.c.skill_source_id == source.id,
                Skill.name == raw["name"],
            )
        )
        skill = existing.scalar_one_or_none()
        if skill:
            skill.description = raw["description"]
            skill.source_url = raw.get("source_url")
            skill.needs_summary = True
        else:
            new_skill = Skill(
                name=raw["name"],
                description=raw["description"],
                target_type=source.type,
                source_url=raw.get("source_url"),
                licence=raw.get("licence"),
                category=raw.get("category"),
                needs_summary=True,
            )
            db.add(new_skill)
            await db.flush()
            await db.execute(
                skill_source_skills.insert().values(
                    skill_source_id=source.id, skill_id=new_skill.id
                )
            )
            added += 1

    source.last_sync = datetime.now(timezone.utc)
    source.last_sync_count = len(raw_skills)
    return added
```

- [ ] **Step 4: Commit**

```bash
git add backend/mcp_manager/api/routers/skill_sources.py
git commit -m "refactor: extraction fonctions enrichissement skill_sources"
```

---

### Task 3: Replace fill-repo-urls with enrich-skills pipeline in `sync.py`

**Files:**
- Modify: `backend/mcp_manager/api/routers/sync.py`

- [ ] **Step 1: Replace the endpoint and add stop endpoint**

Replace the `fill-skill-repo-urls` endpoint and `_run_fill_skill_repo_urls_bg` function with:

```python
@router.post("/services/enrich-skills")
async def trigger_enrich_skills(
    background_tasks: BackgroundTasks,
):
    if _sync_status.get("enriching"):
        return {"status": "already_running"}
    _sync_status["enriching"] = True
    _sync_status["enrich_cancel"] = False
    background_tasks.add_task(_run_enrich_skills_bg)
    return {"status": "started"}


@router.post("/services/enrich-skills/stop")
async def stop_enrich_skills():
    if not _sync_status.get("enriching"):
        return {"status": "not_running"}
    _sync_status["enrich_cancel"] = True
    return {"status": "stopping"}
```

- [ ] **Step 2: Write the pipeline background function**

Replace `_run_fill_skill_repo_urls_bg` with:

```python
async def _run_enrich_skills_bg():
    import logging
    from datetime import datetime, timezone
    from mcp_manager.db.session import SessionLocal
    from mcp_manager.db.models import SkillSource
    from mcp_manager.api.routers.skill_sources import (
        _enrich_repo_url, _enrich_summaries, _enrich_sync_skills,
    )
    from sqlalchemy import select, or_

    enrich_logger = logging.getLogger("enrich-pipeline")

    try:
        async with SessionLocal() as db:
            result = await db.execute(
                select(SkillSource).where(
                    or_(
                        SkillSource.enrichment_status == "pending",
                        SkillSource.enrichment_status == "enriching",
                        SkillSource.enrichment_status.is_(None),
                    )
                ).order_by(SkillSource.created_at)
            )
            sources = result.scalars().all()
            total = len(sources)
            enrich_logger.info("enrich-pipeline: %d sources to process", total)

            stats = {"total": total, "done": 0, "repos_filled": 0, "summaries": 0, "syncs": 0, "failed": 0}
            _sync_status["enrich_progress"] = stats

            for i, source in enumerate(sources):
                # Check cancel flag
                if _sync_status.get("enrich_cancel"):
                    enrich_logger.info("enrich-pipeline: cancelled at %d/%d", i, total)
                    break

                source.enrichment_status = "enriching"
                await db.commit()

                try:
                    # Step 1: Fill repo URL
                    if await _enrich_repo_url(source):
                        stats["repos_filled"] += 1

                    # Step 2: Generate summaries (requires Ollama)
                    try:
                        if await _enrich_summaries(source, db):
                            stats["summaries"] += 1
                    except Exception:
                        enrich_logger.warning("enrich-pipeline: summary failed for %s", source.name)

                    # Step 3: Sync skills from GitHub
                    try:
                        added = await _enrich_sync_skills(source, db)
                        if added > 0:
                            stats["syncs"] += 1
                    except Exception:
                        enrich_logger.warning("enrich-pipeline: sync failed for %s", source.name)

                    source.enrichment_status = "done"
                    stats["done"] += 1

                except Exception:
                    enrich_logger.exception("enrich-pipeline: failed for %s", source.name)
                    source.enrichment_status = "failed"
                    stats["failed"] += 1

                await db.commit()

                if (i + 1) % 10 == 0:
                    enrich_logger.info("enrich-pipeline: %d/%d done", i + 1, total)
                    _sync_status["enrich_progress"] = dict(stats)

            _sync_status["enrich_progress"] = dict(stats)

        _sync_status["last_enrich"] = {
            "time": datetime.now(timezone.utc).isoformat(),
            **stats,
        }
        enrich_logger.info(
            "enrich-pipeline: done — %d done, %d failed, %d repos, %d summaries, %d syncs",
            stats["done"], stats["failed"], stats["repos_filled"], stats["summaries"], stats["syncs"],
        )
    except Exception:
        enrich_logger.exception("enrich-pipeline failed")
    finally:
        _sync_status["enriching"] = False
        _sync_status["enrich_cancel"] = False
```

- [ ] **Step 3: Remove old fill-skill-repo-urls endpoint and function**

Delete the `trigger_fill_skill_repo_urls` endpoint and the entire `_run_fill_skill_repo_urls_bg` function.

- [ ] **Step 4: Commit**

```bash
git add backend/mcp_manager/api/routers/sync.py
git commit -m "feat: pipeline enrichissement skill_sources avec stop"
```

---

### Task 4: Add startup hook to reset interrupted enrichments

**Files:**
- Modify: `backend/mcp_manager/api/app.py`

- [ ] **Step 1: Add startup event**

```python
def create_app() -> FastAPI:
    app = FastAPI(title="MCP Manager", version="0.1.0")

    @app.on_event("startup")
    async def reset_interrupted_enrichments():
        from mcp_manager.db.session import SessionLocal
        from mcp_manager.db.models import SkillSource
        from sqlalchemy import update
        import logging
        logger = logging.getLogger("startup")
        async with SessionLocal() as db:
            result = await db.execute(
                update(SkillSource)
                .where(SkillSource.enrichment_status == "enriching")
                .values(enrichment_status="pending")
            )
            await db.commit()
            if result.rowcount > 0:
                logger.info("startup: reset %d interrupted enrichments to pending", result.rowcount)

    app.add_middleware(RateLimitMiddleware)
    # ... rest unchanged
```

- [ ] **Step 2: Commit**

```bash
git add backend/mcp_manager/api/app.py
git commit -m "feat: reset enrichissement interrompus au demarrage"
```

---

### Task 5: Update frontend — Enrich Skills button with Stop

**Files:**
- Modify: `frontend/src/api/sync.ts`
- Modify: `frontend/src/pages/SyncPage.tsx`

- [ ] **Step 1: Replace hooks in `sync.ts`**

Replace `useFillSkillRepoUrls` with:

```typescript
export function useEnrichSkills() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiFetch<{ status: string }>("/services/enrich-skills", { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sync-status"] }),
  });
}

export function useStopEnrichSkills() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiFetch<{ status: string }>("/services/enrich-skills/stop", { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sync-status"] }),
  });
}
```

- [ ] **Step 2: Update `SyncPage.tsx`**

Replace imports:
```typescript
import { useSyncStatus, useTriggerSync, useTriggerIndex, useTriggerScrapeSkills, useEnrichSkills, useStopEnrichSkills } from "../api/sync";
```

Replace hooks in the component:
```typescript
const enrichSkills = useEnrichSkills();
const stopEnrich = useStopEnrichSkills();
```

Replace the "Scrape Skills.sh" Card with:

```tsx
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
      {(status as any).last_enrich.repos_filled} repos, {(status as any).last_enrich.summaries} summaries,
      {(status as any).last_enrich.syncs} syncs — {(status as any).last_enrich.time}
    </div>
  )}
</Card>
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/sync.ts frontend/src/pages/SyncPage.tsx
git commit -m "feat: bouton Enrich Skills avec stop et progression"
```

---

### Task 6: Deploy and verify

- [ ] **Step 1: Deploy to server**

```bash
cd /e/srcs/mcp_manager
tar --exclude='.git' --exclude='node_modules' --exclude='.venv' --exclude='__pycache__' --exclude='dist' --exclude='.env' --exclude='.playwright-mcp' -czf /tmp/mcp-manager.tar.gz .
scp -i ~/.ssh/id_shellia /tmp/mcp-manager.tar.gz root@192.168.10.99:/tmp/
ssh -i ~/.ssh/id_shellia root@192.168.10.99 "cd /root/mcp-manager && tar xzf /tmp/mcp-manager.tar.gz && rm /tmp/mcp-manager.tar.gz && docker compose up -d --build mcp-backend mcp-frontend"
```

- [ ] **Step 2: Verify health**

```bash
ssh -i ~/.ssh/id_shellia root@192.168.10.99 "cd /root/mcp-manager && docker compose exec mcp-backend curl -sf http://localhost:8000/api/v1/health"
```

- [ ] **Step 3: Check startup log for reset message**

```bash
ssh -i ~/.ssh/id_shellia root@192.168.10.99 "cd /root/mcp-manager && docker compose logs mcp-backend --tail 20"
```

- [ ] **Step 4: Test enrichment on a small batch via the UI**

Navigate to https://mcp.yoops.org, go to Sync page, click "Enrich Skills". Check progress updates. Click "Stop Enrich" to verify graceful cancellation.
