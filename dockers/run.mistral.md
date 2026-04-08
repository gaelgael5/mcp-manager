

<run type="compose">

  agflow-mistral:
    build:
      context: ./mistral
      dockerfile: Dockerfile
    container_name: agent-{workflow_id}-{phase}-mistral
    stdin_open: true
    tty: true
    network_mode: host
    environment:
      - MISTRAL_API_KEY={API_KEY}
      - MISTRAL_MODEL={MODEL}
    volumes:
      - ${WORKSPACE_PATH}:/app
    working_dir: /app

</run>


<run type="cmd">
docker run -it --rm \
  --name agent-{id provider}-mistral \
  --network host \
  -e MISTRAL_API_KEY={API_KEY} \
  -e MISTRAL_MODEL={MODEL} \
  -v {WORKSPACE_PATH}:/app \
  -w /app \
  agent-mistral
</run>


<default>
	API_KEY =	${MISTRAL_API_KEY}
	MODEL =	${MISTRAL_MODEL:-mistral-large-latest}
	WORKSPACE_PATH = ${WORKSPACE_PATH:-./workspace}
</default>
