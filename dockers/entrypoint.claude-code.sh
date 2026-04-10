#!/usr/bin/env bash
# entrypoint.sh

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

emit_event "progress" "\"Agent $AGENT_ROLE démarré — tâche $TASK_ID\""

MODEL_FLAG=""
if [ -n "${CLAUDE_MODEL:-}" ]; then
    MODEL_FLAG="--model $CLAUDE_MODEL"
fi

EXIT_CODE=0
RESULT=$(timeout "$TIMEOUT" claude \
    -p "$INSTRUCTION" \
    $MODEL_FLAG \
    --output-format stream-json \
    --allowedTools "$AGENT_ALLOWED_TOOLS" \
    --max-turns "$AGENT_MAX_TURNS" \
    2>/dev/null) || EXIT_CODE=$?

echo "$RESULT" | while IFS= read -r line; do
    TYPE=$(echo "$line" | jq -r '.type // empty')
    case "$TYPE" in
        "assistant")
            TEXT=$(echo "$line" | jq -c '.message.content[]? | select(.type=="text") | .text')
            [ -n "$TEXT" ] && emit_event "progress" "$TEXT"
            ;;
        "tool_use")
            TOOL=$(echo "$line" | jq -c '{tool: .name, input: .input}')
            emit_event "artifact" "$TOOL"
            ;;
        "result")
            COST=$(echo "$line" | jq -r '.cost_usd // 0')
            emit_event "progress" "\"cost_usd: $COST\""
            ;;
    esac
done

if [ "$EXIT_CODE" -eq 0 ]; then
    emit_event "result" "{\"status\":\"success\",\"exit_code\":0}"
else
    emit_event "result" "{\"status\":\"failure\",\"exit_code\":$EXIT_CODE}"
fi

exit $EXIT_CODE