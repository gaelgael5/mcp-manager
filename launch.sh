#!/usr/bin/env bash
# launch.sh — Start MCP Manager services, recreating containers if images changed.
#              Cleans up stopped containers older than 24h and dangling images.
#
# Usage:
#   ./launch.sh              # Launch all services
#   ./launch.sh backend      # Launch backend only
#   ./launch.sh frontend     # Launch frontend only

set -euo pipefail

cd "$(dirname "$0")"

# --- Launch services (recreate only if image changed) ---

if [ $# -eq 0 ]; then
    echo "Starting all services..."
    docker compose up -d
else
    for service in "$@"; do
        case "$service" in
            backend)  svc="mcp-backend" ;;
            frontend) svc="mcp-frontend" ;;
            postgres) svc="mcp-manager-postgres" ;;
            *)        svc="$service" ;;
        esac
        echo "Starting $svc..."
        docker compose up -d "$svc"
    done
fi

echo ""
echo "Status:"
docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"

# --- Cleanup: stopped containers older than 24h ---

echo ""
old_containers=$(docker ps -a --filter "status=exited" --filter "label=com.docker.compose.project=mcp-manager" --format "{{.ID}} {{.Names}} {{.Status}}" 2>/dev/null | grep -i "ago" || true)

if [ -n "$old_containers" ]; then
    echo "Cleaning stopped containers (>24h)..."
    docker container prune --filter "label=com.docker.compose.project=mcp-manager" --filter "until=24h" -f 2>/dev/null || true
else
    echo "No stopped containers to clean."
fi

# --- Cleanup: dangling images ---

dangling=$(docker images -f "dangling=true" -q 2>/dev/null || true)
if [ -n "$dangling" ]; then
    echo "Cleaning dangling images..."
    docker image prune -f 2>/dev/null || true
else
    echo "No dangling images to clean."
fi

echo ""
echo "Done."
