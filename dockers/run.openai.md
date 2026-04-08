

<run type="compose">

  agflow-openai:
    build:
      context: ./openai
      dockerfile: Dockerfile
    container_name: agent-{workflow_id}-{phase}-openai
    stdin_open: true
    tty: true
    network_mode: host
    environment:
      - OPENAI_API_KEY={API_KEY}
      - OPENAI_MODEL={MODEL}
    volumes:
      - ${WORKSPACE_PATH}:/app
    working_dir: /app

</run>


<run type="cmd">
docker run -it --rm \
  --name agent-{id provider}-openai \
  --network host \
  -e OPENAI_API_KEY={API_KEY} \
  -e OPENAI_MODEL={MODEL} \
  -v {WORKSPACE_PATH}:/app \
  -w /app \
  agent-openai
</run>


<default>
	API_KEY =	${OPENAI_API_KEY}
	MODEL =	${OPENAI_MODEL:-gpt-4o}
	WORKSPACE_PATH = ${WORKSPACE_PATH:-./workspace}
</default>
