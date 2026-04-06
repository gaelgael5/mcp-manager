

<run type="compose">

  agflow-claude-code:
    build:
      context: ./claude-code
      dockerfile: Dockerfile
    container_name: agent-{workflow_id}-{phase}-claude-code
    stdin_open: true
    tty: true
    network_mode: host
    environment:
      - ANTHROPIC_API_KEY={API_KEY}
    volumes:
      - ${WORKSPACE_PATH}:/app
    working_dir: /app

</run>


<run type="cmd">
docker run -it --rm \
  --name agent-{id provider}-claude-code \
  --network host \
  -e ANTHROPIC_API_KEY={API_KEY} \
  -v {WORKSPACE_PATH}:/app \
  -w /app \
  agent-claude-code
</run>


<default>
	API_KEY =	${ANTHROPIC_API_KEY}
	WORKSPACE_PATH = ${WORKSPACE_PATH:-./workspace}
</default>