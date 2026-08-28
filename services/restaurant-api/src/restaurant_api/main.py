from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel

from restaurant_api.config import RestaurantSettings, get_restaurant_settings
from restaurant_api.kitchen_client import KitchenAPIError, KitchenClient
from restaurant_api.models import Order, OrderList, OrderStatus
from restaurant_api.observability import (
    DEFAULT_ERROR_RESPONSES,
    configure_logging,
    install_observability,
)


class HealthResponse(BaseModel):
    """Ответ проверки процесса сервиса заведения."""

    status: Literal["ok"]


def get_kitchen_client(
    settings: Annotated[RestaurantSettings, Depends(get_restaurant_settings)],
) -> KitchenClient:
    """Создать клиент платформы из настроек окружения."""
    return KitchenClient(
        base_url=str(settings.kitchen_api_url),
        token=settings.partner_api_token.get_secret_value(),
        timeout=settings.kitchen_api_timeout_seconds,
    )


router = APIRouter(prefix="/api/v1/orders", tags=["Заказы заведения"])


@router.get("", response_model=OrderList, summary="Получить очередь заказов")
async def list_orders(
    client: Annotated[KitchenClient, Depends(get_kitchen_client)],
    order_status: Annotated[OrderStatus | None, Query(alias="status")] = OrderStatus.CREATED,
) -> OrderList:
    try:
        return await client.list_orders(order_status)
    except KitchenAPIError as error:
        raise _upstream_http_error(error) from error


@router.post("/{order_id}/accept", response_model=Order, summary="Принять заказ")
async def accept_order(
    order_id: UUID,
    client: Annotated[KitchenClient, Depends(get_kitchen_client)],
) -> Order:
    return await _transition(client, order_id, OrderStatus.ACCEPTED)


@router.post("/{order_id}/reject", response_model=Order, summary="Отклонить заказ")
async def reject_order(
    order_id: UUID,
    client: Annotated[KitchenClient, Depends(get_kitchen_client)],
) -> Order:
    return await _transition(client, order_id, OrderStatus.REJECTED)


@router.post("/{order_id}/preparing", response_model=Order, summary="Начать приготовление")
async def start_preparing(
    order_id: UUID,
    client: Annotated[KitchenClient, Depends(get_kitchen_client)],
) -> Order:
    return await _transition(client, order_id, OrderStatus.PREPARING)


@router.post("/{order_id}/ready", response_model=Order, summary="Завершить приготовление")
async def mark_ready(
    order_id: UUID,
    client: Annotated[KitchenClient, Depends(get_kitchen_client)],
) -> Order:
    return await _transition(client, order_id, OrderStatus.READY)


async def _transition(client: KitchenClient, order_id: UUID, target: OrderStatus) -> Order:
    try:
        return await client.transition_order(order_id, target)
    except KitchenAPIError as error:
        raise _upstream_http_error(error) from error


def _upstream_http_error(error: KitchenAPIError) -> HTTPException:
    status_code = error.status_code if 400 <= error.status_code < 500 else 503
    if isinstance(error.details, dict):
        detail: str | dict[str, object] = {**error.details, "message": error.message}
    elif error.details is not None:
        detail = {"message": error.message, "upstream_details": error.details}
    else:
        detail = error.message
    return HTTPException(status_code=status_code, detail=detail)


def create_app(settings: RestaurantSettings | None = None) -> FastAPI:
    """Создать HTTP-приложение демонстрационного заведения."""
    resolved_settings = settings or get_restaurant_settings()
    configure_logging(resolved_settings.log_level)
    app = FastAPI(
        title="Тестовая кухня API",
        summary="Пример интеграции заведения и Авито.Кухни",
        version="0.1.0",
        responses=DEFAULT_ERROR_RESPONSES,
    )
    install_observability(app)

    @app.get("/health", response_model=HealthResponse, tags=["Состояние сервиса"])
    async def health() -> HealthResponse:
        return HealthResponse(status="ok")

    app.include_router(router)
    return app


app = create_app()
