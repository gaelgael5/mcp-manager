#!/usr/bin/env bash
# entrypoint.codex.sh — daemon loop. Reads one JSON task per line on stdin,
# emits one JSON response per line on stdout.
#
# Request:  {"task_id":"...","payload":{"instruction":"..."},"timeout_seconds":N}
# Response: {"task_id":"...","status":"success","data":"..."}
#           {"task_id":"...","status":"failure","exit_code":N}
set -uo pipefail

emit() { printf '%s\n' "$1"; }

while IFS= read -r TASK_JSON; do
    [ -z "$TASK_JSON" ] && continue

    TASK_ID=$(printf '%s' "$TASK_JSON" | jq -r '.task_id')
    INSTRUCTION=$(printf '%s' "$TASK_JSON" | jq -r '.payload.instruction')
    TIMEOUT=$(printf '%s' "$TASK_JSON" | jq -r '.timeout_seconds // 300')

    MODEL_FLAG=""
    if [ -n "${CODEX_MODEL:-}" ]; then
        MODEL_FLAG="-m $CODEX_MODEL"
    fi

    LAST_MSG_FILE=$(mktemp)
    EXIT_CODE=0
    timeout "$TIMEOUT" codex exec \
        --full-auto \
        --skip-git-repo-check \
        --output-last-message "$LAST_MSG_FILE" \
        $MODEL_FLAG \
        "$INSTRUCTION" \
        </dev/null >/dev/null 2>&1 || EXIT_CODE=$?

    RESULT=""
    if [ -f "$LAST_MSG_FILE" ]; then
        RESULT=$(cat "$LAST_MSG_FILE")
        rm -f "$LAST_MSG_FILE"
    fi

    if [ "$EXIT_CODE" -eq 0 ] && [ -n "$RESULT" ]; then
        ESCAPED=$(printf '%s' "$RESULT" | jq -Rs '.')
        emit "{\"task_id\":\"$TASK_ID\",\"status\":\"success\",\"data\":$ESCAPED}"
    else
        emit "{\"task_id\":\"$TASK_ID\",\"status\":\"failure\",\"exit_code\":$EXIT_CODE}"
    fi
done
