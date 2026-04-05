"""Seed script for install_targets with their installation modes.

Usage:
  docker compose exec mcp-backend python scripts/seed_targets.py
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

TARGETS = [
    {
        "name": "claude_code",
        "description": "Claude Code CLI (claude mcp add)",
        "modes": [
            {"runtime": "npx", "action_type": "cmd", "template": "claude mcp add {name} -- npx -y {package}"},
            {"runtime": "uvx", "action_type": "cmd", "template": "claude mcp add {name} -- uvx {package}"},
            {"runtime": "docker", "action_type": "cmd", "template": "claude mcp add {name} -- docker run -i --rm {env_flags} {package}"},
            {"runtime": "python", "action_type": "cmd", "template": "claude mcp add {name} -- python -m {package}"},
            {"runtime": "node", "action_type": "cmd", "template": "claude mcp add {name} -- node {package}"},
        ],
    },
    {
        "name": "claude_desktop",
        "description": "Claude Desktop app (claude_desktop_config.json)",
        "modes": [
            {"runtime": "npx", "action_type": "insert_in_file", "template": '{"mcpServers": {"{name}": {"command": "npx", "args": ["-y", "{package}"]}}}'},
            {"runtime": "uvx", "action_type": "insert_in_file", "template": '{"mcpServers": {"{name}": {"command": "uvx", "args": ["{package}"]}}}'},
            {"runtime": "docker", "action_type": "insert_in_file", "template": '{"mcpServers": {"{name}": {"command": "docker", "args": ["run", "-i", "--rm", "{package}"]}}}'},
        ],
    },
    {
        "name": "VS Code",
        "description": "VS Code settings.json (mcp.servers section)",
        "modes": [
            {"runtime": "npx", "action_type": "insert_in_file", "template": '{"mcp.servers": {"{name}": {"command": "npx", "args": ["-y", "{package}"]}}}'},
            {"runtime": "uvx", "action_type": "insert_in_file", "template": '{"mcp.servers": {"{name}": {"command": "uvx", "args": ["{package}"]}}}'},
            {"runtime": "docker", "action_type": "insert_in_file", "template": '{"mcp.servers": {"{name}": {"command": "docker", "args": ["run", "-i", "--rm", "{package}"]}}}'},
        ],
    },
    {
        "name": "Cursor",
        "description": "Cursor editor (.cursor/mcp.json)",
        "modes": [
            {"runtime": "npx", "action_type": "insert_in_file", "template": '{"mcpServers": {"{name}": {"command": "npx", "args": ["-y", "{package}"]}}}'},
            {"runtime": "uvx", "action_type": "insert_in_file", "template": '{"mcpServers": {"{name}": {"command": "uvx", "args": ["{package}"]}}}'},
            {"runtime": "docker", "action_type": "insert_in_file", "template": '{"mcpServers": {"{name}": {"command": "docker", "args": ["run", "-i", "--rm", "{package}"]}}}'},
        ],
    },
    {
        "name": "Windsurf",
        "description": "Windsurf IDE (~/.codeium/windsurf/mcp_config.json)",
        "modes": [
            {"runtime": "npx", "action_type": "insert_in_file", "template": '{"mcpServers": {"{name}": {"command": "npx", "args": ["-y", "{package}"]}}}'},
            {"runtime": "uvx", "action_type": "insert_in_file", "template": '{"mcpServers": {"{name}": {"command": "uvx", "args": ["{package}"]}}}'},
            {"runtime": "docker", "action_type": "insert_in_file", "template": '{"mcpServers": {"{name}": {"command": "docker", "args": ["run", "-i", "--rm", "{package}"]}}}'},
        ],
    },
    {
        "name": "JetBrains",
        "description": "JetBrains IDEs (.idea/mcp.json)",
        "modes": [
            {"runtime": "npx", "action_type": "insert_in_file", "template": '{"servers": {"{name}": {"command": "npx", "args": ["-y", "{package}"], "disabled": false}}}'},
            {"runtime": "uvx", "action_type": "insert_in_file", "template": '{"servers": {"{name}": {"command": "uvx", "args": ["{package}"], "disabled": false}}}'},
            {"runtime": "docker", "action_type": "insert_in_file", "template": '{"servers": {"{name}": {"command": "docker", "args": ["run", "-i", "--rm", "{package}"], "disabled": false}}}'},
        ],
    },
    {
        "name": "Zed",
        "description": "Zed editor (settings.json context_servers)",
        "modes": [
            {"runtime": "npx", "action_type": "insert_in_file", "template": '{"context_servers": {"{name}": {"command": {"path": "npx", "args": ["-y", "{package}"]}}}}'},
            {"runtime": "uvx", "action_type": "insert_in_file", "template": '{"context_servers": {"{name}": {"command": {"path": "uvx", "args": ["{package}"]}}}}'},
            {"runtime": "docker", "action_type": "insert_in_file", "template": '{"context_servers": {"{name}": {"command": {"path": "docker", "args": ["run", "-i", "--rm", "{package}"]}}}}'},
        ],
    },
    {
        "name": "Cline",
        "description": "Cline / Roo Code extension (cline_mcp_settings.json)",
        "modes": [
            {"runtime": "npx", "action_type": "insert_in_file", "template": '{"mcpServers": {"{name}": {"command": "npx", "args": ["-y", "{package}"], "disabled": false}}}'},
            {"runtime": "uvx", "action_type": "insert_in_file", "template": '{"mcpServers": {"{name}": {"command": "uvx", "args": ["{package}"], "disabled": false}}}'},
            {"runtime": "docker", "action_type": "insert_in_file", "template": '{"mcpServers": {"{name}": {"command": "docker", "args": ["run", "-i", "--rm", "{package}"], "disabled": false}}}'},
        ],
    },
    {
        "name": "Continue",
        "description": "Continue extension (config.yaml mcpServers)",
        "modes": [
            {"runtime": "npx", "action_type": "insert_in_file", "template": "mcpServers:\n  - name: {name}\n    command: npx\n    args:\n      - -y\n      - {package}"},
            {"runtime": "uvx", "action_type": "insert_in_file", "template": "mcpServers:\n  - name: {name}\n    command: uvx\n    args:\n      - {package}"},
            {"runtime": "docker", "action_type": "insert_in_file", "template": "mcpServers:\n  - name: {name}\n    command: docker\n    args:\n      - run\n      - -i\n      - --rm\n      - {package}"},
        ],
    },
    {
        "name": "Gemini CLI",
        "description": "Google Gemini CLI (settings.json mcpServers)",
        "modes": [
            {"runtime": "npx", "action_type": "insert_in_file", "template": '{"mcpServers": {"{name}": {"command": "npx", "args": ["-y", "{package}"]}}}'},
            {"runtime": "uvx", "action_type": "insert_in_file", "template": '{"mcpServers": {"{name}": {"command": "uvx", "args": ["{package}"]}}}'},
            {"runtime": "docker", "action_type": "insert_in_file", "template": '{"mcpServers": {"{name}": {"command": "docker", "args": ["run", "-i", "--rm", "{package}"]}}}'},
        ],
    },
    {
        "name": "Amazon Q CLI",
        "description": "AWS Q Developer CLI (~/.amazonq/mcp.json)",
        "modes": [
            {"runtime": "npx", "action_type": "insert_in_file", "template": '{"mcpServers": {"{name}": {"command": "npx", "args": ["-y", "{package}"]}}}'},
            {"runtime": "uvx", "action_type": "insert_in_file", "template": '{"mcpServers": {"{name}": {"command": "uvx", "args": ["{package}"]}}}'},
            {"runtime": "docker", "action_type": "insert_in_file", "template": '{"mcpServers": {"{name}": {"command": "docker", "args": ["run", "-i", "--rm", "{package}"]}}}'},
        ],
    },
    {
        "name": "OpenAI Codex CLI",
        "description": "OpenAI Codex CLI (codex_mcp.json)",
        "modes": [
            {"runtime": "npx", "action_type": "insert_in_file", "template": '{"mcpServers": {"{name}": {"command": "npx", "args": ["-y", "{package}"]}}}'},
            {"runtime": "uvx", "action_type": "insert_in_file", "template": '{"mcpServers": {"{name}": {"command": "uvx", "args": ["{package}"]}}}'},
        ],
    },
    {
        "name": "GitHub Copilot",
        "description": "GitHub Copilot in VS Code (settings.json mcp.servers)",
        "modes": [
            {"runtime": "npx", "action_type": "insert_in_file", "template": '{"mcp.servers": {"{name}": {"command": "npx", "args": ["-y", "{package}"]}}}'},
            {"runtime": "uvx", "action_type": "insert_in_file", "template": '{"mcp.servers": {"{name}": {"command": "uvx", "args": ["{package}"]}}}'},
            {"runtime": "docker", "action_type": "insert_in_file", "template": '{"mcp.servers": {"{name}": {"command": "docker", "args": ["run", "-i", "--rm", "{package}"]}}}'},
        ],
    },
    {
        "name": "langgraph",
        "description": "LangGraph mcp_servers.json (command + args + transport)",
        "modes": [
            {"runtime": "npx", "action_type": "insert_in_file", "template": '{"command": "npx", "args": ["-y", "{package}"], "transport": "stdio", "name": "{name}", "enabled": true}'},
            {"runtime": "uvx", "action_type": "insert_in_file", "template": '{"command": "uvx", "args": ["{package}"], "transport": "stdio", "name": "{name}", "enabled": true}'},
            {"runtime": "python", "action_type": "insert_in_file", "template": '{"command": "python", "args": ["-m", "{package}"], "transport": "stdio", "name": "{name}", "enabled": true}'},
            {"runtime": "docker", "action_type": "insert_in_file", "template": '{"command": "docker", "args": ["run", "-i", "--rm", "{package}"], "transport": "stdio", "name": "{name}", "enabled": true}'},
        ],
    },
    {
        "name": "docker_stdio",
        "description": "Docker container avec transport stdio (docker run -i)",
        "modes": [
            {"runtime": "docker", "action_type": "docker_run", "template": "docker run -i --rm {env_flags} {package}"},
        ],
    },
    # === IDE/editors — additional ===
    {
        "name": "Roo Code",
        "description": "Roo Code extension (cline_mcp_settings.json)",
        "modes": [
            {"runtime": "npx", "action_type": "insert_in_file", "template": '{"mcpServers": {"{name}": {"command": "npx", "args": ["-y", "{package}"], "disabled": false}}}'},
            {"runtime": "uvx", "action_type": "insert_in_file", "template": '{"mcpServers": {"{name}": {"command": "uvx", "args": ["{package}"], "disabled": false}}}'},
            {"runtime": "docker", "action_type": "insert_in_file", "template": '{"mcpServers": {"{name}": {"command": "docker", "args": ["run", "-i", "--rm", "{package}"], "disabled": false}}}'},
        ],
    },
    {
        "name": "Augment Code",
        "description": "Augment Code extension (settings.json mcp.servers)",
        "modes": [
            {"runtime": "npx", "action_type": "insert_in_file", "template": '{"mcpServers": {"{name}": {"command": "npx", "args": ["-y", "{package}"]}}}'},
            {"runtime": "uvx", "action_type": "insert_in_file", "template": '{"mcpServers": {"{name}": {"command": "uvx", "args": ["{package}"]}}}'},
        ],
    },
    {
        "name": "Zencoder",
        "description": "Zencoder AI (mcp_config.json)",
        "modes": [
            {"runtime": "npx", "action_type": "insert_in_file", "template": '{"mcpServers": {"{name}": {"command": "npx", "args": ["-y", "{package}"]}}}'},
            {"runtime": "uvx", "action_type": "insert_in_file", "template": '{"mcpServers": {"{name}": {"command": "uvx", "args": ["{package}"]}}}'},
        ],
    },
    {
        "name": "Warp",
        "description": "Warp terminal AI (mcp.json)",
        "modes": [
            {"runtime": "npx", "action_type": "insert_in_file", "template": '{"mcpServers": {"{name}": {"command": "npx", "args": ["-y", "{package}"]}}}'},
            {"runtime": "uvx", "action_type": "insert_in_file", "template": '{"mcpServers": {"{name}": {"command": "uvx", "args": ["{package}"]}}}'},
            {"runtime": "docker", "action_type": "insert_in_file", "template": '{"mcpServers": {"{name}": {"command": "docker", "args": ["run", "-i", "--rm", "{package}"]}}}'},
        ],
    },
    # === Desktop/Chat apps ===
    {
        "name": "5ire",
        "description": "5ire desktop app (mcpServers config)",
        "modes": [
            {"runtime": "npx", "action_type": "insert_in_file", "template": '{"mcpServers": {"{name}": {"command": "npx", "args": ["-y", "{package}"]}}}'},
            {"runtime": "uvx", "action_type": "insert_in_file", "template": '{"mcpServers": {"{name}": {"command": "uvx", "args": ["{package}"]}}}'},
        ],
    },
    {
        "name": "BoltAI",
        "description": "BoltAI macOS app (mcpServers config)",
        "modes": [
            {"runtime": "npx", "action_type": "insert_in_file", "template": '{"mcpServers": {"{name}": {"command": "npx", "args": ["-y", "{package}"]}}}'},
            {"runtime": "uvx", "action_type": "insert_in_file", "template": '{"mcpServers": {"{name}": {"command": "uvx", "args": ["{package}"]}}}'},
        ],
    },
    {
        "name": "Witsy",
        "description": "Witsy desktop app (mcpServers config)",
        "modes": [
            {"runtime": "npx", "action_type": "insert_in_file", "template": '{"mcpServers": {"{name}": {"command": "npx", "args": ["-y", "{package}"]}}}'},
            {"runtime": "uvx", "action_type": "insert_in_file", "template": '{"mcpServers": {"{name}": {"command": "uvx", "args": ["{package}"]}}}'},
        ],
    },
    {
        "name": "Tome",
        "description": "Tome desktop app (mcpServers config)",
        "modes": [
            {"runtime": "npx", "action_type": "insert_in_file", "template": '{"mcpServers": {"{name}": {"command": "npx", "args": ["-y", "{package}"]}}}'},
            {"runtime": "uvx", "action_type": "insert_in_file", "template": '{"mcpServers": {"{name}": {"command": "uvx", "args": ["{package}"]}}}'},
        ],
    },
    {
        "name": "oterm",
        "description": "oterm terminal (mcpServers config)",
        "modes": [
            {"runtime": "npx", "action_type": "insert_in_file", "template": '{"mcpServers": {"{name}": {"command": "npx", "args": ["-y", "{package}"]}}}'},
            {"runtime": "uvx", "action_type": "insert_in_file", "template": '{"mcpServers": {"{name}": {"command": "uvx", "args": ["{package}"]}}}'},
        ],
    },
    {
        "name": "Msty Studio",
        "description": "Msty Studio desktop app (mcpServers config)",
        "modes": [
            {"runtime": "npx", "action_type": "insert_in_file", "template": '{"mcpServers": {"{name}": {"command": "npx", "args": ["-y", "{package}"]}}}'},
            {"runtime": "uvx", "action_type": "insert_in_file", "template": '{"mcpServers": {"{name}": {"command": "uvx", "args": ["{package}"]}}}'},
        ],
    },
    {
        "name": "TypingMind",
        "description": "TypingMind app (mcpServers config)",
        "modes": [
            {"runtime": "npx", "action_type": "insert_in_file", "template": '{"mcpServers": {"{name}": {"command": "npx", "args": ["-y", "{package}"]}}}'},
            {"runtime": "uvx", "action_type": "insert_in_file", "template": '{"mcpServers": {"{name}": {"command": "uvx", "args": ["{package}"]}}}'},
        ],
    },
    {
        "name": "Glama App",
        "description": "Glama desktop app (mcpServers config)",
        "modes": [
            {"runtime": "npx", "action_type": "insert_in_file", "template": '{"mcpServers": {"{name}": {"command": "npx", "args": ["-y", "{package}"]}}}'},
            {"runtime": "uvx", "action_type": "insert_in_file", "template": '{"mcpServers": {"{name}": {"command": "uvx", "args": ["{package}"]}}}'},
        ],
    },
    {
        "name": "HyperChat",
        "description": "HyperChat app (mcpServers config)",
        "modes": [
            {"runtime": "npx", "action_type": "insert_in_file", "template": '{"mcpServers": {"{name}": {"command": "npx", "args": ["-y", "{package}"]}}}'},
            {"runtime": "uvx", "action_type": "insert_in_file", "template": '{"mcpServers": {"{name}": {"command": "uvx", "args": ["{package}"]}}}'},
        ],
    },
    {
        "name": "LibreChat",
        "description": "LibreChat self-hosted (librechat.yaml mcpServers)",
        "modes": [
            {"runtime": "npx", "action_type": "insert_in_file", "template": '{"mcpServers": {"{name}": {"command": "npx", "args": ["-y", "{package}"]}}}'},
            {"runtime": "uvx", "action_type": "insert_in_file", "template": '{"mcpServers": {"{name}": {"command": "uvx", "args": ["{package}"]}}}'},
            {"runtime": "docker", "action_type": "insert_in_file", "template": '{"mcpServers": {"{name}": {"command": "docker", "args": ["run", "-i", "--rm", "{package}"]}}}'},
        ],
    },
    {
        "name": "MooPoint",
        "description": "MooPoint app (mcpServers config)",
        "modes": [
            {"runtime": "npx", "action_type": "insert_in_file", "template": '{"mcpServers": {"{name}": {"command": "npx", "args": ["-y", "{package}"]}}}'},
            {"runtime": "uvx", "action_type": "insert_in_file", "template": '{"mcpServers": {"{name}": {"command": "uvx", "args": ["{package}"]}}}'},
        ],
    },
    # === Platforms ===
    {
        "name": "Claude.ai",
        "description": "Claude.ai web app (remote MCP servers via streamable-http)",
        "modes": [
            {"runtime": "streamable-http", "action_type": "insert_in_file", "template": '{"url": "{package}", "transport": "streamable-http"}'},
        ],
    },
    {
        "name": "Microsoft Copilot Studio",
        "description": "Microsoft Copilot Studio (mcpServers config)",
        "modes": [
            {"runtime": "npx", "action_type": "insert_in_file", "template": '{"mcpServers": {"{name}": {"command": "npx", "args": ["-y", "{package}"]}}}'},
            {"runtime": "uvx", "action_type": "insert_in_file", "template": '{"mcpServers": {"{name}": {"command": "uvx", "args": ["{package}"]}}}'},
        ],
    },
    {
        "name": "Goose",
        "description": "Goose AI agent (~/.config/goose/config.yaml)",
        "modes": [
            {"runtime": "npx", "action_type": "insert_in_file", "template": "mcpServers:\n  {name}:\n    command: npx\n    args:\n      - -y\n      - {package}"},
            {"runtime": "uvx", "action_type": "insert_in_file", "template": "mcpServers:\n  {name}:\n    command: uvx\n    args:\n      - {package}"},
            {"runtime": "docker", "action_type": "insert_in_file", "template": "mcpServers:\n  {name}:\n    command: docker\n    args:\n      - run\n      - -i\n      - --rm\n      - {package}"},
        ],
    },
    {
        "name": "Postman",
        "description": "Postman MCP debug (connect to running MCP server)",
        "modes": [
            {"runtime": "npx", "action_type": "cmd", "template": "npx -y {package}"},
            {"runtime": "uvx", "action_type": "cmd", "template": "uvx {package}"},
        ],
    },
]


async def main():
    from sqlalchemy import select
    from mcp_manager.db.session import SessionLocal
    from mcp_manager.db.models import InstallTarget

    async with SessionLocal() as db:
        for t in TARGETS:
            result = await db.execute(
                select(InstallTarget).where(InstallTarget.name == t["name"])
            )
            existing = result.scalar_one_or_none()

            if existing:
                existing.description = t["description"]
                existing.modes = t["modes"]
                print(f"  Updated: {t['name']} ({len(t['modes'])} modes)")
            else:
                db.add(InstallTarget(
                    name=t["name"],
                    description=t["description"],
                    modes=t["modes"],
                ))
                print(f"  Created: {t['name']} ({len(t['modes'])} modes)")

        await db.commit()

    print(f"\nDone: {len(TARGETS)} targets seeded.")


if __name__ == "__main__":
    asyncio.run(main())
