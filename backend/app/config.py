from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = "sqlite:///./data/sidewatch.db"
    session_ttl_minutes: int = 30
    secret_key: str = "change-me"

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()