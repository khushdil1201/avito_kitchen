from functools import lru_cache

from pydantic import PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки, получаемые из переменных окружения."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: PostgresDsn = PostgresDsn(
        "postgresql://avito_kitchen:avito_kitchen@localhost:5432/avito_kitchen"
    )
    database_pool_min_size: int = 1
    database_pool_max_size: int = 10


@lru_cache
def get_settings() -> Settings:
    """Вернуть неизменяемый для процесса набор настроек."""
    return Settings()

