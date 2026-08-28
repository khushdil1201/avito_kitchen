from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel


class OrderStatus(StrEnum):
    """Статусы заказа, видимые заведению."""

    CREATED = "created"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    PREPARING = "preparing"
    READY = "ready"
    DELIVERING = "delivering"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class OrderItem(BaseModel):
    """Зафиксированная позиция заказа."""

    menu_item_id: UUID
    name: str
    price_minor: int
    quantity: int


class Order(BaseModel):
    """Заказ, полученный от платформы."""

    id: UUID
    customer_id: UUID
    restaurant_id: UUID
    status: OrderStatus
    currency: str
    total_minor: int
    delivery_address: str
    items: list[OrderItem]
    created_at: datetime
    updated_at: datetime


class OrderList(BaseModel):
    """Очередь заказов заведения."""

    items: list[Order]
