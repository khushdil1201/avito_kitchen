import secrets
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from pydantic import BaseModel

from avito_kitchen.application.partner_orders import PartnerOrdersService
from avito_kitchen.config import Settings, get_settings
from avito_kitchen.domain.orders import (
    InvalidOrderTransitionError,
    OrderStatus,
    PartnerOrderNotFoundError,
)
from avito_kitchen.infrastructure.database import Database
from avito_kitchen.infrastructure.repositories.partner_orders import (
    PostgresPartnerOrdersRepository,
)
from avito_kitchen.presentation.http.orders import OrderResponse, _order_response

router = APIRouter(prefix="/partner/orders", tags=["Интеграция заведения"])


class PartnerTargetStatus(StrEnum):
    """Статусы, которые разрешено устанавливать заведению."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"
    PREPARING = "preparing"
    READY = "ready"


class TransitionOrderRequest(BaseModel):
    """Команда изменения состояния заказа заведением."""

    status: PartnerTargetStatus


class PartnerOrderListResponse(BaseModel):
    """Ограниченная очередь заказов заведения."""

    items: list[OrderResponse]


def authenticate_partner(
    settings: Annotated[Settings, Depends(get_settings)],
    token: Annotated[str | None, Header(alias="X-Partner-Token")] = None,
) -> UUID:
    """Проверить демонстрационный токен и вернуть связанное заведение."""
    expected = settings.partner_api_token.get_secret_value()
    if token is None or not secrets.compare_digest(token, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный токен заведения",
        )
    return settings.partner_restaurant_id


def get_partner_orders_service(request: Request) -> PartnerOrdersService:
    """Собрать сервис партнёрских заказов для текущего запроса."""
    database: Database = request.app.state.database
    return PartnerOrdersService(PostgresPartnerOrdersRepository(database.pool))


@router.get("", response_model=PartnerOrderListResponse, summary="Получить очередь заказов")
async def list_partner_orders(
    restaurant_id: Annotated[UUID, Depends(authenticate_partner)],
    service: Annotated[PartnerOrdersService, Depends(get_partner_orders_service)],
    order_status: Annotated[OrderStatus | None, Query(alias="status")] = OrderStatus.CREATED,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> PartnerOrderListResponse:
    orders = await service.list_orders(
        restaurant_id=restaurant_id,
        order_status=order_status,
        limit=limit,
    )
    return PartnerOrderListResponse(items=[_order_response(order) for order in orders])


@router.patch(
    "/{order_id}/status",
    response_model=OrderResponse,
    summary="Изменить статус заказа",
)
async def transition_partner_order(
    order_id: UUID,
    body: TransitionOrderRequest,
    restaurant_id: Annotated[UUID, Depends(authenticate_partner)],
    service: Annotated[PartnerOrdersService, Depends(get_partner_orders_service)],
) -> OrderResponse:
    try:
        result = await service.transition_order(
            restaurant_id=restaurant_id,
            order_id=order_id,
            target_status=OrderStatus(body.status.value),
        )
    except PartnerOrderNotFoundError as error:
        raise HTTPException(status_code=404, detail="Заказ заведения не найден") from error
    except InvalidOrderTransitionError as error:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Недопустимый переход статуса",
                "current": error.current.value,
                "target": error.target.value,
            },
        ) from error
    return _order_response(result.order)

