from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Policy Impact Engine"
    debug: bool = True
    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/policy_impact_engine"
    )
    redis_url: str = "redis://localhost:6379/0"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    upload_dir: str = "data/uploads"
    max_upload_size_mb: int = 50

    model_config = {"env_file": ".env"}


settings = Settings()
