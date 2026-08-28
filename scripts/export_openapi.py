"""Экспортировать OpenAPI-схемы обоих HTTP-сервисов в репозиторий."""

import json
from pathlib import Path
from typing import Any

from avito_kitchen.main import create_app as create_kitchen_app
from restaurant_api.main import create_app as create_restaurant_app

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OPENAPI_DIRECTORY = PROJECT_ROOT / "openapi"


def _write_schema(filename: str, schema: dict[str, Any]) -> None:
    target = OPENAPI_DIRECTORY / filename
    target.write_text(
        json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    """Создать воспроизводимые JSON-файлы спецификаций."""
    OPENAPI_DIRECTORY.mkdir(exist_ok=True)
    _write_schema("kitchen-api.json", create_kitchen_app().openapi())
    _write_schema("restaurant-api.json", create_restaurant_app().openapi())


if __name__ == "__main__":
    main()
