import asyncio

from httpx import ASGITransport, AsyncClient

from avito_kitchen.main import create_app


def test_health_returns_ok() -> None:
    async def request_health() -> tuple[int, dict[str, str]]:
        transport = ASGITransport(app=create_app())
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/health")
        return response.status_code, response.json()

    status_code, body = asyncio.run(request_health())

    assert status_code == 200
    assert body == {"status": "ok"}
