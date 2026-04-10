#!/usr/bin/env bash
# entrypoint.codex.sh

set -euo pipefail

TASK_JSON=$(cat)

TASK_ID=$(echo "$TASK_JSON"    | jq -r '.task_id')
INSTRUCTION=$(echo "$TASK_JSON" | jq -r '.payload.instruction')
TIMEOUT=$(echo "$TASK_JSON"    | jq -r '.timeout_seconds // 300')

emit_event() {
    local type=$1
    local data=$2
    echo "{\"task_id\":\"$TASK_ID\",\"type\":\"$type\",\"data\":$data}"
}

emit_event "progress" "\"Agent $AGENT_ROLE demarre — tache $TASK_ID\""

MODEL_FLAG=""
if [ -n "${CODEX_MODEL:-}" ]; then
    MODEL_FLAG="--model $CODEX_MODEL"
fi

EXIT_CODE=0
RESULT=$(timeout "$TIMEOUT" codex \
    --quiet \
    --full-auto \
    $MODEL_FLAG \
    "$INSTRUCTION" \
    2>/dev/null) || EXIT_CODE=$?

if [ "$EXIT_CODE" -eq 0 ] && [ -n "$RESULT" ]; then
    # Escape result for JSON
    ESCAPED=$(echo "$RESULT" | jq -Rs '.')
    emit_event "progress" "$ESCAPED"
    emit_event "result" "{\"status\":\"success\",\"exit_code\":0}"
else
    emit_event "result" "{\"status\":\"failure\",\"exit_code\":$EXIT_CODE}"
fi

exit $EXIT_CODE
