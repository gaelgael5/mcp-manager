#!/usr/bin/env bash
set -euo pipefail

TASK_JSON=$(cat)
TASK_ID=$(echo "$TASK_JSON"    | jq -r '.task_id')
INSTRUCTION=$(echo "$TASK_JSON" | jq -r '.payload.instruction')
TIMEOUT=$(echo "$TASK_JSON"    | jq -r '.timeout_seconds // 300')
MODEL=$(echo "$TASK_JSON"      | jq -r '.payload.model // "sonnet"')

emit_event() {
    local type=$1
    local data=$2
    echo "{\"task_id\":\"$TASK_ID\",\"type\":\"$type\",\"data\":$data}"
}

emit_event "progress" "\"Agent $AGENT_ROLE démarré — tâche $TASK_ID — modèle $MODEL\""

EXIT_CODE=0
RESULT=$(timeout "$TIMEOUT" aider \
    --model "$MODEL" \
    --message "$INSTRUCTION" \
    --yes \
    --no-git \
    2>/dev/null) || EXIT_CODE=$?

echo "$RESULT" | while IFS= read -r line; do
    [ -z "$line" ] && continue
    emit_event "progress" "\"$(echo "$line" | sed 's/"/\\"/g')\""
done

if [ "$EXIT_CODE" -eq 0 ]; then
    emit_event "result" "{\"status\":\"success\",\"exit_code\":0}"
else
    emit_event "result" "{\"status\":\"failure\",\"exit_code\":$EXIT_CODE}"
fi

exit $EXIT_CODE