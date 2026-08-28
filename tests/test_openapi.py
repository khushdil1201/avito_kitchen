import json
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI

from avito_kitchen.main import create_app as create_kitchen_app
from restaurant_api.main import create_app as create_restaurant_app

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    ("filename", "app"),
    [
        ("kitchen-api.json", create_kitchen_app()),
        ("restaurant-api.json", create_restaurant_app()),
    ],
)
def test_committed_openapi_schema_matches_application(filename: str, app: FastAPI) -> None:
    schema_path = PROJECT_ROOT / "openapi" / filename
    committed_schema: dict[str, Any] = json.loads(schema_path.read_text(encoding="utf-8"))

    assert committed_schema == app.openapi(), (
        f"{filename} не соответствует коду приложения; выполните `make openapi`"
    )


@pytest.mark.parametrize("app", [create_kitchen_app(), create_restaurant_app()])
def test_openapi_documents_actual_error_envelope(app: FastAPI) -> None:
    schema = app.openapi()

    assert "HTTPValidationError" not in schema["components"]["schemas"]
    for path in schema["paths"].values():
        for operation in path.values():
            for status_code, response in operation["responses"].items():
                if int(status_code) < 400:
                    continue
                documented_schema = response["content"]["application/json"]["schema"]
                assert documented_schema == {"$ref": "#/components/schemas/ErrorResponse"}


def test_partner_api_documents_bearer_authentication() -> None:
    schema = create_kitchen_app().openapi()

    assert schema["components"]["securitySchemes"]["HTTPBearer"] == {
        "type": "http",
        "scheme": "bearer",
    }
    assert schema["paths"]["/api/v1/partner/orders"]["get"]["security"] == [{"HTTPBearer": []}]
