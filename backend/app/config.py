from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Policy Impact Engine"
    debug: bool = True
    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/policy_impact_engine"
    )
    redis_url: str = "redis://localhost:6379/0"

    # LLM Provider: "openai" or "azure"
    llm_provider: str = "openai"

    # OpenAI settings
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"

    # Azure OpenAI settings
    azure_openai_api_key: str = ""
    azure_openai_endpoint: str = ""       # e.g. https://my-resource.openai.azure.com
    azure_openai_deployment: str = ""     # e.g. gpt-4o
    azure_openai_api_version: str = "2024-08-01-preview"

    upload_dir: str = "data/uploads"
    max_upload_size_mb: int = 50

    model_config = {"env_file": ".env"}


settings = Settings()
