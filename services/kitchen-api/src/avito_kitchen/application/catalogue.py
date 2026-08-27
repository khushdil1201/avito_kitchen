from typing import Protocol
from uuid import UUID

from avito_kitchen.domain.catalogue import MenuItem, Page, Restaurant, RestaurantNotFoundError


class CatalogueRepository(Protocol):
    """Порт чтения пользовательского каталога."""

    async def list_restaurants(
        self,
        *,
        name: str | None,
        limit: int,
        offset: int,
    ) -> Page[Restaurant]: ...

    async def get_restaurant(self, restaurant_id: UUID) -> Restaurant | None: ...

    async def list_menu_items(
        self,
        *,
        restaurant_id: UUID,
        available_only: bool,
        limit: int,
        offset: int,
    ) -> Page[MenuItem]: ...


class CatalogueService:
    """Оркестрирует пользовательские сценарии просмотра каталога."""

    def __init__(self, repository: CatalogueRepository) -> None:
        self._repository = repository

    async def list_restaurants(
        self,
        *,
        name: str | None,
        limit: int,
        offset: int,
    ) -> Page[Restaurant]:
        normalized_name = name.strip() if name is not None else None
        return await self._repository.list_restaurants(
            name=normalized_name,
            limit=limit,
            offset=offset,
        )

    async def get_menu(
        self,
        *,
        restaurant_id: UUID,
        available_only: bool,
        limit: int,
        offset: int,
    ) -> Page[MenuItem]:
        restaurant = await self._repository.get_restaurant(restaurant_id)
        if restaurant is None:
            raise RestaurantNotFoundError
        return await self._repository.list_menu_items(
            restaurant_id=restaurant_id,
            available_only=available_only,
            limit=limit,
            offset=offset,
        )
