#!/usr/bin/env bash
# build.sh — Build (or rebuild) MCP Manager Docker images without starting services.
# Cleans up old dangling images and stopped containers after build.
#
# Usage:
#   ./build.sh              # Build all images
#   ./build.sh backend      # Build backend image only
#   ./build.sh frontend     # Build frontend image only
#   ./build.sh backend frontend  # Build both app images

set -euo pipefail

cd "$(dirname "$0")"

if [ $# -eq 0 ]; then
    echo "Building all images..."
    docker compose build
else
    for service in "$@"; do
        case "$service" in
            backend)  svc="mcp-backend" ;;
            frontend) svc="mcp-frontend" ;;
            postgres) svc="mcp-manager-postgres" ;;
            *)        svc="$service" ;;
        esac
        echo "Building $svc..."
        docker compose build "$svc"
    done
fi

# --- Cleanup ---
echo ""
echo "Cleaning up..."

# Remove stopped containers (older than 1h)
stopped=$(docker ps -a --filter "status=exited" --filter "status=dead" -q 2>/dev/null || true)
if [ -n "$stopped" ]; then
    echo "Removing $(echo "$stopped" | wc -l) stopped container(s)..."
    echo "$stopped" | xargs -r docker rm -f 2>/dev/null || true
fi

# Remove dangling images (untagged, no longer referenced)
dangling=$(docker images -f "dangling=true" -q 2>/dev/null || true)
if [ -n "$dangling" ]; then
    echo "Removing $(echo "$dangling" | wc -l) dangling image(s)..."
    echo "$dangling" | xargs -r docker rmi -f 2>/dev/null || true
fi

# Remove old mcp-manager images that are no longer the current tag
for img in mcp-manager-mcp-backend mcp-manager-mcp-frontend; do
    current=$(docker images "$img:latest" -q 2>/dev/null || true)
    old=$(docker images "$img" -q 2>/dev/null | sort -u || true)
    if [ -n "$current" ] && [ -n "$old" ]; then
        for id in $old; do
            if [ "$id" != "$current" ]; then
                echo "Removing old $img image $id..."
                docker rmi -f "$id" 2>/dev/null || true
            fi
        done
    fi
done

# Prune build cache older than 24h
docker builder prune -f --filter "until=24h" 2>/dev/null || true

echo ""
echo "Done. Run ./launch.sh to start services."
