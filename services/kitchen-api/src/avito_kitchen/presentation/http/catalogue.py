from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from avito_kitchen.application.catalogue import CatalogueService
from avito_kitchen.domain.catalogue import MenuItem, Page, Restaurant, RestaurantNotFoundError
from avito_kitchen.infrastructure.database import Database
from avito_kitchen.infrastructure.repositories.catalogue import PostgresCatalogueRepository

router = APIRouter(prefix="/restaurants", tags=["Каталог"])

PageLimit = Annotated[int, Query(ge=1, le=100)]
PageOffset = Annotated[int, Query(ge=0, le=10_000)]


class PaginationResponse(BaseModel):
    """Метаданные offset-пагинации."""

    limit: int
    offset: int
    total: int


class RestaurantResponse(BaseModel):
    """Заведение в пользовательском каталоге."""

    id: UUID
    name: str
    description: str
    currency: str = Field(min_length=3, max_length=3)


class RestaurantListResponse(BaseModel):
    """Страница доступных заведений."""

    items: list[RestaurantResponse]
    pagination: PaginationResponse


class MenuItemResponse(BaseModel):
    """Позиция меню; цена указана в минимальных единицах валюты."""

    id: UUID
    restaurant_id: UUID
    name: str
    description: str
    price_minor: int = Field(gt=0)
    is_available: bool


class MenuResponse(BaseModel):
    """Страница меню заведения."""

    items: list[MenuItemResponse]
    pagination: PaginationResponse


def get_catalogue_service(request: Request) -> CatalogueService:
    """Собрать прикладной сервис для текущего запроса."""
    database: Database = request.app.state.database
    return CatalogueService(PostgresCatalogueRepository(database.pool))


@router.get("", response_model=RestaurantListResponse, summary="Получить список заведений")
async def list_restaurants(
    service: Annotated[CatalogueService, Depends(get_catalogue_service)],
    name: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    limit: PageLimit = 20,
    offset: PageOffset = 0,
) -> RestaurantListResponse:
    page = await service.list_restaurants(name=name, limit=limit, offset=offset)
    return _restaurant_page_response(page)


@router.get(
    "/{restaurant_id}/menu",
    response_model=MenuResponse,
    summary="Получить меню заведения",
    responses={status.HTTP_404_NOT_FOUND: {"description": "Заведение не найдено"}},
)
async def get_menu(
    restaurant_id: UUID,
    service: Annotated[CatalogueService, Depends(get_catalogue_service)],
    available_only: bool = True,
    limit: PageLimit = 20,
    offset: PageOffset = 0,
) -> MenuResponse:
    try:
        page = await service.get_menu(
            restaurant_id=restaurant_id,
            available_only=available_only,
            limit=limit,
            offset=offset,
        )
    except RestaurantNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Заведение не найдено",
        ) from error
    return _menu_page_response(page)


def _restaurant_page_response(page: Page[Restaurant]) -> RestaurantListResponse:
    return RestaurantListResponse(
        items=[
            RestaurantResponse.model_validate(item, from_attributes=True) for item in page.items
        ],
        pagination=PaginationResponse(limit=page.limit, offset=page.offset, total=page.total),
    )


def _menu_page_response(page: Page[MenuItem]) -> MenuResponse:
    return MenuResponse(
        items=[MenuItemResponse.model_validate(item, from_attributes=True) for item in page.items],
        pagination=PaginationResponse(limit=page.limit, offset=page.offset, total=page.total),
    )
