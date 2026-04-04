FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml .
COPY mcp_manager/ ./mcp_manager/
COPY scripts/ ./scripts/
RUN pip install --no-cache-dir .
CMD ["uvicorn", "mcp_manager.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
