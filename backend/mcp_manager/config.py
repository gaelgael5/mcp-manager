from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://langgraph:langgraph@localhost:5432/langgraph"
    ollama_base_url: str = "http://192.168.10.80:11434"
    ollama_summary_model: str = "llama3.1"
    cors_origins: list[str] = ["http://localhost:3001"]
    github_token: str = ""
    google_client_id: str = ""
    google_client_secret: str = ""
    admin_email: str = ""
    jwt_secret: str = "mcp-manager-jwt-secret-change-me"

    model_config = {"env_prefix": "", "env_file": ".env"}


settings = Settings()
