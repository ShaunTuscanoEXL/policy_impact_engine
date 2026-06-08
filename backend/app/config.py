import os

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Policy Impact Engine"
    debug: bool = True
    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/policy_impact_engine"
    )
    redis_url: str = "redis://localhost:6379/0"

    # LLM Provider: "openai" or "azure"
    llm_provider: str = os.getenv("LLM_PROVIDER", "claude")

    # OpenAI settings
    openai_api_key: str = ""
    openai_model: str = "gpt-5.4-mini"

    # Azure OpenAI settings
    azure_openai_api_key: str = os.getenv("AZURE_OPENAI_API_KEY")
    azure_openai_endpoint: str = os.getenv("AZURE_OPENAI_ENDPOINT")
    azure_openai_deployment: str = os.getenv("AZURE_OPENAI_DEPLOYMENT")
    azure_openai_api_version: str = os.getenv("AZURE_OPENAI_API_VERSION")

    claude_api_key: str = os.getenv("CLAUDE_API_KEY")

    upload_dir: str = "data/uploads"
    max_upload_size_mb: int = 50

    model_config = {"env_file": ".env"}


settings = Settings()
