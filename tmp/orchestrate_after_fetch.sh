#!/bin/bash
# Monitors /tmp/fetch.log inside mcp-backend. When it sees "Done:" (the batch
# finished line emitted by fetch-branch-shas), runs two follow-up actions:
#   1. UPDATE mcp_services SET needs_reindex=true (all rows, no filter)
#   2. Launch python -m mcp_manager.cli index --limit 100000 in the backend
#      container, writing its output to /tmp/index.log
# Everything is logged to /tmp/orchestrate.log on the LXC host.
set -u

LOG=/root/orchestrate.log
COMPOSE="docker compose -f /root/mcp-manager/docker-compose.yml"

echo "[$(date -Is)] orchestrator started, waiting for fetch-branch-shas to finish" >> $LOG

while true; do
    if $COMPOSE exec -T mcp-backend grep -q "^Done:" /tmp/fetch.log 2>/dev/null; then
        break
    fi
    sleep 60
done

echo "[$(date -Is)] fetch-branch-shas finished" >> $LOG
$COMPOSE exec -T mcp-backend tail -5 /tmp/fetch.log >> $LOG 2>&1

echo "[$(date -Is)] flagging all mcp_services as needs_reindex=true" >> $LOG
$COMPOSE exec -T mcp-manager-postgres psql -U langgraph -d langgraph -c \
    "UPDATE mcp_services SET needs_reindex=true;" >> $LOG 2>&1

echo "[$(date -Is)] launching normal indexer pipeline" >> $LOG
$COMPOSE exec -T mcp-backend bash -c 'rm -f /tmp/index.log; nohup python -m mcp_manager.cli index --limit 100000 > /tmp/index.log 2>&1 &'

echo "[$(date -Is)] orchestrator done, indexer running in background" >> $LOG
