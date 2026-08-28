import asyncio
from uuid import UUID

from httpx import ASGITransport, AsyncClient, Response

from avito_kitchen.main import create_app as create_kitchen_app
from restaurant_api.main import create_app as create_restaurant_app


async def request(app_kind: str, path: str, request_id: str | None = None) -> Response:
    app = create_kitchen_app() if app_kind == "kitchen" else create_restaurant_app()
    headers = {"X-Request-ID": request_id} if request_id is not None else {}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.get(path, headers=headers)


async def validation_request() -> Response:
    app = create_kitchen_app()

    @app.get("/validation/{item_id}")
    async def validation_route(item_id: UUID) -> dict[str, str]:
        return {"item_id": str(item_id)}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.get(
            "/validation/not-a-uuid", headers={"X-Request-ID": "validation-test"}
        )


async def failing_request() -> Response:
    app = create_kitchen_app()

    @app.get("/failure")
    async def failure_route() -> None:
        raise RuntimeError("sensitive database details")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.get("/failure", headers={"X-Request-ID": "failure-test"})


def test_kitchen_propagates_valid_request_id() -> None:
    response = asyncio.run(request("kitchen", "/api/v1/health", "checkout.trace-42"))

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "checkout.trace-42"


def test_kitchen_replaces_invalid_request_id() -> None:
    response = asyncio.run(request("kitchen", "/api/v1/health", "invalid request id"))

    generated = response.headers["X-Request-ID"]
    assert generated != "invalid request id"
    assert str(UUID(generated)) == generated


def test_kitchen_validation_error_uses_common_contract() -> None:
    response = asyncio.run(validation_request())

    assert response.status_code == 422
    assert response.headers["X-Request-ID"] == "validation-test"
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert error["message"] == "Ошибка валидации запроса"
    assert error["request_id"] == "validation-test"
    assert error["details"][0]["location"] == ["path", "item_id"]
    assert error["details"][0]["type"] == "uuid_parsing"


def test_restaurant_error_and_request_id_use_common_contract() -> None:
    response = asyncio.run(request("restaurant", "/missing", "restaurant-test"))

    assert response.status_code == 404
    assert response.headers["X-Request-ID"] == "restaurant-test"
    assert response.json()["error"] == {
        "code": "not_found",
        "message": "Not Found",
        "details": None,
        "request_id": "restaurant-test",
    }


def test_unexpected_error_does_not_leak_internal_details() -> None:
    response = asyncio.run(failing_request())

    assert response.status_code == 500
    assert response.headers["X-Request-ID"] == "failure-test"
    assert response.json()["error"] == {
        "code": "internal_error",
        "message": "Внутренняя ошибка сервиса",
        "details": None,
        "request_id": "failure-test",
    }
