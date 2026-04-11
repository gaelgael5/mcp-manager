#!/usr/bin/env bash
# entrypoint.mistral.sh — daemon loop. Reads one JSON task per line on stdin,
# emits one JSON response per line on stdout.
set -uo pipefail

emit() { printf '%s\n' "$1"; }

while IFS= read -r TASK_JSON; do
    [ -z "$TASK_JSON" ] && continue

    TASK_ID=$(printf '%s' "$TASK_JSON" | jq -r '.task_id')
    INSTRUCTION=$(printf '%s' "$TASK_JSON" | jq -r '.payload.instruction')
    TIMEOUT=$(printf '%s' "$TASK_JSON" | jq -r '.timeout_seconds // 300')

    EXIT_CODE=0
    CLI_OUTPUT=$(timeout "$TIMEOUT" python3 -c "
import os, sys
from mistralai import Mistral

client = Mistral(api_key=os.environ['MISTRAL_API_KEY'])
resp = client.chat.complete(
    model=os.environ.get('MISTRAL_MODEL', 'mistral-large-latest'),
    max_tokens=int(os.environ.get('AGENT_MAX_TOKENS', '4096')),
    messages=[
        {'role': 'system', 'content': 'Tu es un agent ' + os.environ.get('AGENT_ROLE', 'worker') + '. Reponds de maniere structuree et concise.'},
        {'role': 'user', 'content': sys.argv[1]},
    ],
)
print(resp.choices[0].message.content or '')
" "$INSTRUCTION" 2>/dev/null) || EXIT_CODE=$?

    if [ "$EXIT_CODE" -eq 0 ] && [ -n "$CLI_OUTPUT" ]; then
        ESCAPED=$(printf '%s' "$CLI_OUTPUT" | jq -Rs '.')
        emit "{\"task_id\":\"$TASK_ID\",\"status\":\"success\",\"data\":$ESCAPED}"
    else
        emit "{\"task_id\":\"$TASK_ID\",\"status\":\"failure\",\"exit_code\":$EXIT_CODE}"
    fi
done
