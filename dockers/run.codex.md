

<run type="compose">

  agflow-codex:
    build:
      context: ./codex
      dockerfile: Dockerfile
    container_name: agent-{workflow_id}-{phase}-codex
    stdin_open: true
    tty: true
    network_mode: host
    volumes:
      - ${WORKSPACE_PATH}:/app
      - ${CODEX_AUTH_PATH}:/home/agent/.codex/auth.json:ro
    working_dir: /app

</run>


<run type="cmd">
docker run -it --rm \
  --name agent-{id provider}-codex \
  --network host \
  -v {WORKSPACE_PATH}:/app \
  -v {CODEX_AUTH_PATH}:/home/agent/.codex/auth.json:ro \
  -w /app \
  agent-codex
</run>


<default>
	CODEX_AUTH_PATH = ${CODEX_AUTH_PATH:-/root/.codex/auth.json}
	WORKSPACE_PATH = ${WORKSPACE_PATH:-./workspace}
</default>
