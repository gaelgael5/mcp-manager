import asyncio
from mcp_manager.connectors.skillssh_scanner import scan_repo_skills

async def main():
    r = await scan_repo_skills("https://github.com/wshobson/agents")
    print("status:", r["status"])
    print("repo_format:", r["repo_format"])
    print("skills found:", len(r["skills"]))
    if r["skills"]:
        for s in r["skills"][:5]:
            name = s["name"]
            plugin = s["category"]
            src = s["source_url"]
            print(f"  - {name} (plugin={plugin}): {src}")

asyncio.run(main())
