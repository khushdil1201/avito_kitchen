from functools import lru_cache

from pydantic import AnyHttpUrl, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class RestaurantSettings(BaseSettings):
    """Настройки интеграции демонстрационного заведения."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    kitchen_api_url: AnyHttpUrl = AnyHttpUrl("http://kitchen-api:8000")
    partner_api_token: SecretStr = SecretStr("demo-partner-token-change-me")
    kitchen_api_timeout_seconds: float = Field(default=3.0, gt=0, le=30)


@lru_cache
def get_restaurant_settings() -> RestaurantSettings:
    """Вернуть настройки сервиса заведения."""
    return RestaurantSettings()

