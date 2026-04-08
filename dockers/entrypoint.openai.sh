#!/usr/bin/env bash
# entrypoint.openai.sh

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

EXIT_CODE=0
RESULT=$(timeout "$TIMEOUT" python3 -c "
import json, os, sys
from openai import OpenAI

client = OpenAI(api_key=os.environ['OPENAI_API_KEY'])
resp = client.chat.completions.create(
    model=os.environ.get('OPENAI_MODEL', 'gpt-4o'),
    max_tokens=int(os.environ.get('AGENT_MAX_TOKENS', '4096')),
    messages=[
        {'role': 'system', 'content': 'Tu es un agent $AGENT_ROLE. Reponds de maniere structuree et concise.'},
        {'role': 'user', 'content': sys.argv[1]},
    ],
)
text = resp.choices[0].message.content or ''
usage = resp.usage
print(json.dumps({'text': text, 'prompt_tokens': usage.prompt_tokens, 'completion_tokens': usage.completion_tokens, 'total_tokens': usage.total_tokens}))
" "$INSTRUCTION" 2>/dev/null) || EXIT_CODE=$?

if [ "$EXIT_CODE" -eq 0 ] && [ -n "$RESULT" ]; then
    TEXT=$(echo "$RESULT" | jq -c '.text')
    TOKENS=$(echo "$RESULT" | jq -r '.total_tokens // 0')
    emit_event "progress" "$TEXT"
    emit_event "progress" "\"tokens: $TOKENS\""
    emit_event "result" "{\"status\":\"success\",\"exit_code\":0}"
else
    emit_event "result" "{\"status\":\"failure\",\"exit_code\":$EXIT_CODE}"
fi

exit $EXIT_CODE
