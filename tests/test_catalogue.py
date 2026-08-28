import asyncio
from uuid import UUID

from httpx import ASGITransport, AsyncClient, Response

from avito_kitchen.application.catalogue import CatalogueService
from avito_kitchen.domain.catalogue import MenuItem, Page, Restaurant
from avito_kitchen.main import create_app
from avito_kitchen.presentation.http.catalogue import get_catalogue_service

RESTAURANT_ID = UUID("10000000-0000-4000-8000-000000000001")
MENU_ITEM_ID = UUID("20000000-0000-4000-8000-000000000001")


class FakeCatalogueRepository:
    async def list_restaurants(
        self,
        *,
        name: str | None,
        limit: int,
        offset: int,
    ) -> Page[Restaurant]:
        restaurant = Restaurant(
            id=RESTAURANT_ID,
            name="Тестовая кухня",
            description="Домашние блюда",
            currency="RUB",
        )
        items = (restaurant,) if name is None or name.lower() in restaurant.name.lower() else ()
        return Page(items=items, total=len(items), limit=limit, offset=offset)

    async def get_restaurant(self, restaurant_id: UUID) -> Restaurant | None:
        if restaurant_id != RESTAURANT_ID:
            return None
        return Restaurant(
            id=RESTAURANT_ID,
            name="Тестовая кухня",
            description="Домашние блюда",
            currency="RUB",
        )

    async def list_menu_items(
        self,
        *,
        restaurant_id: UUID,
        available_only: bool,
        limit: int,
        offset: int,
    ) -> Page[MenuItem]:
        item = MenuItem(
            id=MENU_ITEM_ID,
            restaurant_id=restaurant_id,
            name="Борщ",
            description="Борщ из говядины",
            price_minor=39_000,
            is_available=True,
        )
        return Page(items=(item,), total=1, limit=limit, offset=offset)


async def request(path: str) -> Response:
    app = create_app()
    service = CatalogueService(FakeCatalogueRepository())
    app.dependency_overrides[get_catalogue_service] = lambda: service
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path)


def test_list_restaurants_returns_filtered_page() -> None:
    response = asyncio.run(request("/api/v1/restaurants?name=кухня&limit=10"))

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "id": str(RESTAURANT_ID),
                "name": "Тестовая кухня",
                "description": "Домашние блюда",
                "currency": "RUB",
            }
        ],
        "pagination": {"limit": 10, "offset": 0, "total": 1},
    }


def test_get_menu_returns_available_items() -> None:
    response = asyncio.run(request(f"/api/v1/restaurants/{RESTAURANT_ID}/menu"))

    assert response.status_code == 200
    assert response.json()["items"][0]["price_minor"] == 39_000


def test_get_menu_returns_not_found_for_unknown_restaurant() -> None:
    unknown_id = UUID("10000000-0000-4000-8000-000000000099")

    response = asyncio.run(request(f"/api/v1/restaurants/{unknown_id}/menu"))

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
    assert response.json()["error"]["message"] == "Заведение не найдено"
