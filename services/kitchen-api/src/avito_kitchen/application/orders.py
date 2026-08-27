import hashlib
import json
from typing import Protocol
from uuid import UUID

from avito_kitchen.domain.orders import (
    CreateOrderCommand,
    Order,
    OrderCreationResult,
    OrderNotFoundError,
)


class OrdersRepository(Protocol):
    """Порт записи и чтения заказов."""

    async def create_order(
        self,
        *,
        command: CreateOrderCommand,
        idempotency_key: str,
        request_hash: str,
    ) -> OrderCreationResult: ...

    async def get_order(self, *, order_id: UUID, customer_id: UUID) -> Order | None: ...


class OrdersService:
    """Оркестрирует пользовательские сценарии заказов."""

    def __init__(self, repository: OrdersRepository) -> None:
        self._repository = repository

    async def create_order(
        self,
        *,
        command: CreateOrderCommand,
        idempotency_key: str,
    ) -> OrderCreationResult:
        normalized_command = CreateOrderCommand(
            customer_id=command.customer_id,
            restaurant_id=command.restaurant_id,
            delivery_address=command.delivery_address.strip(),
            items=tuple(sorted(command.items, key=lambda item: str(item.menu_item_id))),
        )
        request_hash = self._request_hash(normalized_command)
        return await self._repository.create_order(
            command=normalized_command,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
        )

    async def get_order(self, *, order_id: UUID, customer_id: UUID) -> Order:
        order = await self._repository.get_order(order_id=order_id, customer_id=customer_id)
        if order is None:
            raise OrderNotFoundError
        return order

    @staticmethod
    def _request_hash(command: CreateOrderCommand) -> str:
        payload = {
            "customer_id": str(command.customer_id),
            "restaurant_id": str(command.restaurant_id),
            "delivery_address": command.delivery_address,
            "items": [
                {"menu_item_id": str(item.menu_item_id), "quantity": item.quantity}
                for item in command.items
            ],
        }
        canonical = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        return hashlib.sha256(canonical.encode()).hexdigest()
