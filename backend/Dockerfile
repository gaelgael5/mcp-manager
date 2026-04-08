FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/* \
    && curl -fsSL https://download.docker.com/linux/static/stable/x86_64/docker-27.5.1.tgz \
    | tar xz --strip-components=1 -C /usr/local/bin docker/docker
COPY pyproject.toml .
COPY alembic.ini .
COPY mcp_manager/ ./mcp_manager/
COPY prompts/ ./prompts/
COPY scripts/ ./scripts/
RUN pip install --no-cache-dir .
CMD ["uvicorn", "mcp_manager.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
