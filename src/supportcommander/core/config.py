from functools import lru_cache
from urllib.parse import quote_plus
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    log_level: str = 'INFO'

    app_api_key: str | None = None  # Set in production to gate sensitive endpoints

    openai_api_key: str
    openai_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"

    mongo_host: str = "localhost"
    mongo_port: int = 27017
    mongo_root_username: str
    mongo_root_password: str
    mongo_db: str = "support_commander"

    model_config = SettingsConfigDict(env_file = ".env", env_file_encoding = "utf-8", extra="ignore")

    @property
    def mongo_uri(self) -> str:
        username = quote_plus(self.mongo_root_username)
        password = quote_plus(self.mongo_root_password)
        return (
            f"mongodb://{username}:{password}@{self.mongo_host}:{self.mongo_port}/{self.mongo_db}?authSource=admin"
        )

@lru_cache
def get_settings() -> Settings:
    return Settings()