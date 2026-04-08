"""Seed script for skill_sources — pre-load all known skill repositories.

Usage:
  docker compose exec mcp-backend python scripts/seed_skill_sources.py
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

SOURCES = [
    # === Anthropic (Claude) ===
    {"name": "Anthropic Skills", "url": "https://github.com/anthropics/skills", "skills_path": "skills", "type": "claude"},

    # === OpenAI (Codex) — same SKILL.md format ===
    {"name": "OpenAI Codex Skills", "url": "https://github.com/openai/codex-skills", "skills_path": "skills", "type": "claude"},

    # === Google Gemini ===
    {"name": "Google Gemini Skills", "url": "https://github.com/google-gemini/gemini-skills", "skills_path": "skills", "type": "gemini"},
    {"name": "Google Labs Stitch", "url": "https://github.com/google-labs-code/stitch-skills", "skills_path": "skills", "type": "gemini"},
    {"name": "Google Workspace Skills", "url": "https://github.com/googleworkspace/gws-skills", "skills_path": "skills", "type": "gemini"},

    # === Orchestra Research ===
    {"name": "Orchestra AI Research", "url": "https://github.com/Orchestra-Research/AI-Research-SKILLs", "skills_path": "", "type": "claude"},

    # === Hugging Face ===
    {"name": "Hugging Face Skills", "url": "https://github.com/huggingface/agent-skills", "skills_path": "skills", "type": "claude"},

    # === Cloudflare ===
    {"name": "Cloudflare Skills", "url": "https://github.com/cloudflare/agent-skills", "skills_path": "skills", "type": "claude"},

    # === Netlify ===
    {"name": "Netlify Skills", "url": "https://github.com/netlify/agent-skills", "skills_path": "skills", "type": "claude"},

    # === Vercel ===
    {"name": "Vercel Skills", "url": "https://github.com/vercel-labs/agent-skills", "skills_path": "skills", "type": "claude"},

    # === HashiCorp ===
    {"name": "HashiCorp Terraform Skills", "url": "https://github.com/hashicorp/agent-skills", "skills_path": "skills", "type": "claude"},

    # === Neon Database ===
    {"name": "Neon Database Skills", "url": "https://github.com/neondatabase/agent-skills", "skills_path": "skills", "type": "claude"},

    # === Supabase ===
    {"name": "Supabase Skills", "url": "https://github.com/supabase/agent-skills", "skills_path": "skills", "type": "claude"},

    # === ClickHouse ===
    {"name": "ClickHouse Skills", "url": "https://github.com/clickhouse/agent-skills", "skills_path": "skills", "type": "claude"},

    # === DuckDB ===
    {"name": "DuckDB Skills", "url": "https://github.com/duckdb/agent-skills", "skills_path": "skills", "type": "claude"},

    # === Tinybird ===
    {"name": "Tinybird Skills", "url": "https://github.com/tinybirdco/agent-skills", "skills_path": "skills", "type": "claude"},

    # === Stripe ===
    {"name": "Stripe Skills", "url": "https://github.com/stripe/agent-skills", "skills_path": "skills", "type": "claude"},

    # === Figma ===
    {"name": "Figma Skills", "url": "https://github.com/figma/agent-skills", "skills_path": "skills", "type": "claude"},

    # === WordPress ===
    {"name": "WordPress Skills", "url": "https://github.com/WordPress/agent-skills", "skills_path": "skills", "type": "claude"},

    # === Sanity ===
    {"name": "Sanity Skills", "url": "https://github.com/sanity-io/agent-skills", "skills_path": "skills", "type": "claude"},

    # === Microsoft ===
    {"name": "Microsoft Skills", "url": "https://github.com/microsoft/agent-skills", "skills_path": "skills", "type": "claude"},

    # === Expo ===
    {"name": "Expo Skills", "url": "https://github.com/expo/agent-skills", "skills_path": "skills", "type": "claude"},

    # === React Native (Callstack) ===
    {"name": "React Native Skills", "url": "https://github.com/callstackincubator/agent-skills", "skills_path": "skills", "type": "claude"},

    # === GSAP / GreenSock ===
    {"name": "GSAP Skills", "url": "https://github.com/greensock/agent-skills", "skills_path": "skills", "type": "claude"},

    # === Firecrawl ===
    {"name": "Firecrawl Skills", "url": "https://github.com/firecrawl/agent-skills", "skills_path": "skills", "type": "claude"},

    # === Sentry ===
    {"name": "Sentry Skills", "url": "https://github.com/getsentry/agent-skills", "skills_path": "skills", "type": "claude"},

    # === Trail of Bits (Security) ===
    {"name": "Trail of Bits Skills", "url": "https://github.com/trailofbits/agent-skills", "skills_path": "skills", "type": "claude"},

    # === Resend (Email) ===
    {"name": "Resend Skills", "url": "https://github.com/resend/agent-skills", "skills_path": "skills", "type": "claude"},

    # === Courier ===
    {"name": "Courier Skills", "url": "https://github.com/trycourier/courier-skills", "skills_path": "skills", "type": "claude"},

    # === Composio ===
    {"name": "Composio Skills", "url": "https://github.com/composiohq/composio", "skills_path": "skills", "type": "claude"},

    # === Notion ===
    {"name": "Notion Skills", "url": "https://github.com/makenotion/agent-skills", "skills_path": "skills", "type": "claude"},

    # === VoltAgent ===
    {"name": "VoltAgent Skills", "url": "https://github.com/voltagent/agent-skills", "skills_path": "skills", "type": "claude"},

    # === Replicate ===
    {"name": "Replicate Skills", "url": "https://github.com/replicate/agent-skills", "skills_path": "skills", "type": "claude"},

    # === FAL.ai ===
    {"name": "FAL.ai Skills", "url": "https://github.com/fal-ai-community/agent-skills", "skills_path": "skills", "type": "claude"},

    # === MiniMax ===
    {"name": "MiniMax Skills", "url": "https://github.com/MiniMax-AI/agent-skills", "skills_path": "skills", "type": "claude"},

    # === Remotion ===
    {"name": "Remotion Skills", "url": "https://github.com/remotion-dev/agent-skills", "skills_path": "skills", "type": "claude"},

    # === Better Auth ===
    {"name": "Better Auth Skills", "url": "https://github.com/better-auth/agent-skills", "skills_path": "skills", "type": "claude"},

    # === Binance ===
    {"name": "Binance Skills", "url": "https://github.com/binance/agent-skills", "skills_path": "skills", "type": "claude"},

    # === Qdrant ===
    {"name": "Qdrant Skills", "url": "https://github.com/qdrant/skills", "skills_path": "skills", "type": "claude"},

    # === CodeRabbit ===
    {"name": "CodeRabbit Skills", "url": "https://github.com/coderabbitai/skills", "skills_path": "skills", "type": "claude"},

    # === Community collections ===
    {"name": "Awesome Agent Skills", "url": "https://github.com/heilcheng/awesome-agent-skills", "skills_path": "", "type": "claude"},
]


async def main():
    from sqlalchemy import select
    from mcp_manager.db.session import SessionLocal
    from mcp_manager.db.models import SkillSource

    async with SessionLocal() as db:
        created = 0
        skipped = 0
        for s in SOURCES:
            result = await db.execute(
                select(SkillSource).where(
                    (SkillSource.repo_url == s["url"]) | (SkillSource.url == s["url"])
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                # Backfill repo_url si manquant
                if not existing.repo_url:
                    existing.repo_url = s["url"]
                skipped += 1
            else:
                db.add(SkillSource(
                    name=s["name"],
                    url=s["url"],
                    repo_url=s["url"],
                    skills_path=s["skills_path"],
                    type=s["type"],
                ))
                created += 1
                print(f"  Created: {s['name']} ({s['type']})")

        await db.commit()

    print(f"\nDone: {created} created, {skipped} skipped (already exist). Total sources: {len(SOURCES)}.")


if __name__ == "__main__":
    asyncio.run(main())
