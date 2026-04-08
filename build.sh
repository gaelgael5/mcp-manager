#!/usr/bin/env bash
# build.sh — Build (or rebuild) MCP Manager Docker images without starting services.
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

echo ""
echo "Done. Run ./launch.sh to start services."
