#!/usr/bin/env bash
# entrypoint.claude-code.sh — daemon loop. Reads one JSON task per line on
# stdin, emits one JSON response per line on stdout.
set -uo pipefail

emit() { printf '%s\n' "$1"; }

while IFS= read -r TASK_JSON; do
    [ -z "$TASK_JSON" ] && continue

    TASK_ID=$(printf '%s' "$TASK_JSON" | jq -r '.task_id')
    INSTRUCTION=$(printf '%s' "$TASK_JSON" | jq -r '.payload.instruction')
    TIMEOUT=$(printf '%s' "$TASK_JSON" | jq -r '.timeout_seconds // 300')

    MODEL_FLAG=""
    if [ -n "${CLAUDE_MODEL:-}" ]; then
        MODEL_FLAG="--model $CLAUDE_MODEL"
    fi

    EXIT_CODE=0
    CLI_OUTPUT=$(timeout "$TIMEOUT" claude \
        -p "$INSTRUCTION" \
        $MODEL_FLAG \
        --output-format stream-json \
        --verbose \
        --allowedTools "${AGENT_ALLOWED_TOOLS:-}" \
        --max-turns "${AGENT_MAX_TURNS:-5}" \
        2>/dev/null) || EXIT_CODE=$?

    # Collapse all "assistant text" chunks into a single result string.
    # Also scan the terminal "result" line for is_error=true, which signals
    # an authenticated-but-failed API call (invalid key, rate limit, etc.)
    # where the assistant text contains the error message rather than a real
    # model response.
    RESULT=""
    IS_ERROR=false
    while IFS= read -r line; do
        [ -z "$line" ] && continue
        TYPE=$(printf '%s' "$line" | jq -r '.type // empty' 2>/dev/null || true)
        if [ "$TYPE" = "assistant" ]; then
            CHUNK=$(printf '%s' "$line" | jq -r '.message.content[]? | select(.type=="text") | .text' 2>/dev/null || true)
            [ -n "$CHUNK" ] && RESULT="${RESULT}${CHUNK}"
        elif [ "$TYPE" = "result" ]; then
            ERR=$(printf '%s' "$line" | jq -r '.is_error // false' 2>/dev/null || true)
            [ "$ERR" = "true" ] && IS_ERROR=true
        fi
    done <<< "$CLI_OUTPUT"

    if [ "$EXIT_CODE" -eq 0 ] && [ -n "$RESULT" ] && [ "$IS_ERROR" = "false" ]; then
        ESCAPED=$(printf '%s' "$RESULT" | jq -Rs '.')
        emit "{\"task_id\":\"$TASK_ID\",\"status\":\"success\",\"data\":$ESCAPED}"
    else
        emit "{\"task_id\":\"$TASK_ID\",\"status\":\"failure\",\"exit_code\":$EXIT_CODE}"
    fi
done
