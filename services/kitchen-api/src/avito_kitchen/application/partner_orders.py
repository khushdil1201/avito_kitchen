from typing import Protocol
from uuid import UUID

from avito_kitchen.domain.orders import Order, OrderStatus, OrderTransitionResult


class PartnerOrdersRepository(Protocol):
    """Порт очереди и изменения заказов заведения."""

    async def list_orders(
        self,
        *,
        restaurant_id: UUID,
        order_status: OrderStatus | None,
        limit: int,
    ) -> tuple[Order, ...]: ...

    async def transition_order(
        self,
        *,
        restaurant_id: UUID,
        order_id: UUID,
        target_status: OrderStatus,
    ) -> OrderTransitionResult: ...


class PartnerOrdersService:
    """Оркестрирует сценарии обработки заказов заведением."""

    def __init__(self, repository: PartnerOrdersRepository) -> None:
        self._repository = repository

    async def list_orders(
        self,
        *,
        restaurant_id: UUID,
        order_status: OrderStatus | None,
        limit: int,
    ) -> tuple[Order, ...]:
        return await self._repository.list_orders(
            restaurant_id=restaurant_id,
            order_status=order_status,
            limit=limit,
        )

    async def transition_order(
        self,
        *,
        restaurant_id: UUID,
        order_id: UUID,
        target_status: OrderStatus,
    ) -> OrderTransitionResult:
        return await self._repository.transition_order(
            restaurant_id=restaurant_id,
            order_id=order_id,
            target_status=target_status,
        )

