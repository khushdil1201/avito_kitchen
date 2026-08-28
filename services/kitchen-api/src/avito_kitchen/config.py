from functools import lru_cache
from uuid import UUID

from pydantic import PostgresDsn, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки, получаемые из переменных окружения."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: PostgresDsn = PostgresDsn(
        "postgresql://avito_kitchen:avito_kitchen@localhost:5432/avito_kitchen"
    )
    database_pool_min_size: int = 1
    database_pool_max_size: int = 10
    partner_api_token: SecretStr = SecretStr("demo-partner-token-change-me")
    partner_restaurant_id: UUID = UUID("10000000-0000-4000-8000-000000000001")


@lru_cache
def get_settings() -> Settings:
    """Вернуть неизменяемый для процесса набор настроек."""
    return Settings()
