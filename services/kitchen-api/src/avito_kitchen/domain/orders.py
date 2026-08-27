from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class OrderStatus(StrEnum):
    """Состояние заказа, которым владеет платформа."""

    CREATED = "created"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    PREPARING = "preparing"
    READY = "ready"
    DELIVERING = "delivering"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class RequestedOrderItem:
    """Выбранное блюдо и количество порций."""

    menu_item_id: UUID
    quantity: int


@dataclass(frozen=True, slots=True)
class CreateOrderCommand:
    """Команда оформления заказа."""

    customer_id: UUID
    restaurant_id: UUID
    delivery_address: str
    items: tuple[RequestedOrderItem, ...]


@dataclass(frozen=True, slots=True)
class OrderItem:
    """Неизменяемый снимок позиции меню внутри заказа."""

    menu_item_id: UUID
    name: str
    price_minor: int
    quantity: int


@dataclass(frozen=True, slots=True)
class Order:
    """Пользовательский заказ."""

    id: UUID
    customer_id: UUID
    restaurant_id: UUID
    status: OrderStatus
    currency: str
    total_minor: int
    delivery_address: str
    items: tuple[OrderItem, ...]
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class OrderCreationResult:
    """Результат создания или идемпотентного повтора заказа."""

    order: Order
    replayed: bool


class RestaurantUnavailableError(Exception):
    """Заведение отсутствует или временно не принимает заказы."""


class MenuItemsUnavailableError(Exception):
    """Одна или несколько позиций отсутствуют либо недоступны."""

    def __init__(self, item_ids: tuple[UUID, ...]) -> None:
        self.item_ids = item_ids
        super().__init__("Некоторые позиции меню недоступны")


class IdempotencyConflictError(Exception):
    """Ключ идемпотентности уже использован для другого запроса."""


class OrderNotFoundError(Exception):
    """Заказ не существует или принадлежит другому пользователю."""
