


<run type="compose">
  agflow-aider:
    build:
      context: ./aider
      dockerfile: Dockerfile
    container_name: agent-{workflow_id}-{phase}-aider
    stdin_open: true
    tty: true
    network_mode: host
    environment:
      - {API_KEY_NAME}={{API_KEY_NAME}}
    volumes:
      - {WORKSPACE_PATH}:/app
    working_dir: /app
</run>


<run type="cmd">
docker run -it --rm \
  --name agent-{workflow_id}-{phase}-aider \
  --network host \
  -e {API_KEY_NAME}={{API_KEY_NAME}} \
  -w /app \
  agflow-aider
</run>


<default>
    API_KEY_NAME =	ANTHROPIC_API_KEY
    ANTHROPIC_API_KEY =	${ANTHROPIC_API_KEY}
    OPENAI_API_KEY=${OPENAI_API_KEY}
    MISTRAL_API_KEY=${MISTRAL_API_KEY}
	WORKSPACE_PATH = ${WORKSPACE_PATH:-./workspace}
</default>