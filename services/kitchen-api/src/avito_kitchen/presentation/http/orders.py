from datetime import datetime
from typing import Annotated, Self
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, model_validator

from avito_kitchen.application.orders import OrdersService
from avito_kitchen.domain.orders import (
    CreateOrderCommand,
    IdempotencyConflictError,
    MenuItemsUnavailableError,
    Order,
    OrderNotFoundError,
    OrderStatus,
    RequestedOrderItem,
    RestaurantUnavailableError,
)
from avito_kitchen.infrastructure.database import Database
from avito_kitchen.infrastructure.repositories.orders import PostgresOrdersRepository

router = APIRouter(prefix="/orders", tags=["Заказы"])


class CreateOrderItemRequest(BaseModel):
    """Блюдо и требуемое количество."""

    menu_item_id: UUID
    quantity: int = Field(ge=1, le=100)


class CreateOrderRequest(BaseModel):
    """Данные для оформления заказа."""

    model_config = ConfigDict(str_strip_whitespace=True)

    customer_id: UUID
    restaurant_id: UUID
    delivery_address: str = Field(min_length=1, max_length=500)
    items: list[CreateOrderItemRequest] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def items_are_unique(self) -> Self:
        item_ids = [item.menu_item_id for item in self.items]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("Позиции заказа не должны повторяться")
        return self


class OrderItemResponse(BaseModel):
    """Снимок блюда в оформленном заказе."""

    menu_item_id: UUID
    name: str
    price_minor: int
    quantity: int


class OrderResponse(BaseModel):
    """Заказ и зафиксированные позиции."""

    id: UUID
    customer_id: UUID
    restaurant_id: UUID
    status: OrderStatus
    currency: str
    total_minor: int
    delivery_address: str
    items: list[OrderItemResponse]
    created_at: datetime
    updated_at: datetime


def get_orders_service(request: Request) -> OrdersService:
    """Собрать прикладной сервис заказов для текущего запроса."""
    database: Database = request.app.state.database
    return OrdersService(PostgresOrdersRepository(database.pool))


@router.post(
    "",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Оформить заказ",
    responses={status.HTTP_409_CONFLICT: {"description": "Каталог изменился или ключ занят"}},
)
async def create_order(
    body: CreateOrderRequest,
    response: Response,
    service: Annotated[OrdersService, Depends(get_orders_service)],
    idempotency_key: Annotated[
        str,
        Header(
            alias="Idempotency-Key",
            min_length=8,
            max_length=128,
            pattern=r"^[A-Za-z0-9._:-]+$",
        ),
    ],
) -> OrderResponse:
    command = CreateOrderCommand(
        customer_id=body.customer_id,
        restaurant_id=body.restaurant_id,
        delivery_address=body.delivery_address,
        items=tuple(
            RequestedOrderItem(menu_item_id=item.menu_item_id, quantity=item.quantity)
            for item in body.items
        ),
    )
    try:
        result = await service.create_order(command=command, idempotency_key=idempotency_key)
    except RestaurantUnavailableError as error:
        raise HTTPException(status_code=409, detail="Заведение сейчас недоступно") from error
    except MenuItemsUnavailableError as error:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Некоторые позиции меню недоступны",
                "item_ids": [str(item_id) for item_id in error.item_ids],
            },
        ) from error
    except IdempotencyConflictError as error:
        raise HTTPException(
            status_code=409,
            detail="Ключ идемпотентности уже использован для другого запроса",
        ) from error
    if result.replayed:
        response.status_code = status.HTTP_200_OK
    return _order_response(result.order)


@router.get(
    "/{order_id}",
    response_model=OrderResponse,
    summary="Получить заказ",
    responses={status.HTTP_404_NOT_FOUND: {"description": "Заказ не найден"}},
)
async def get_order(
    order_id: UUID,
    customer_id: Annotated[UUID, Query(description="Временный идентификатор пользователя")],
    service: Annotated[OrdersService, Depends(get_orders_service)],
) -> OrderResponse:
    try:
        order = await service.get_order(order_id=order_id, customer_id=customer_id)
    except OrderNotFoundError as error:
        raise HTTPException(status_code=404, detail="Заказ не найден") from error
    return _order_response(order)


def _order_response(order: Order) -> OrderResponse:
    return OrderResponse.model_validate(order, from_attributes=True)
