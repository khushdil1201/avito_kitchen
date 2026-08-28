import asyncio
from datetime import UTC, datetime
from uuid import UUID

from httpx import ASGITransport, AsyncClient

from avito_kitchen.application.orders import OrdersService
from avito_kitchen.domain.orders import (
    CreateOrderCommand,
    IdempotencyConflictError,
    MenuItemsUnavailableError,
    Order,
    OrderCreationResult,
    OrderItem,
    OrderStatus,
)
from avito_kitchen.main import create_app
from avito_kitchen.presentation.http.orders import get_orders_service

CUSTOMER_ID = UUID("30000000-0000-4000-8000-000000000001")
OTHER_CUSTOMER_ID = UUID("30000000-0000-4000-8000-000000000002")
RESTAURANT_ID = UUID("10000000-0000-4000-8000-000000000001")
MENU_ITEM_ID = UUID("20000000-0000-4000-8000-000000000001")
UNAVAILABLE_ITEM_ID = UUID("20000000-0000-4000-8000-000000000004")
ORDER_ID = UUID("40000000-0000-4000-8000-000000000001")
NOW = datetime(2026, 8, 28, tzinfo=UTC)


class FakeOrdersRepository:
    def __init__(self) -> None:
        self.order: Order | None = None
        self.idempotency: dict[str, tuple[str, Order]] = {}

    async def create_order(
        self,
        *,
        command: CreateOrderCommand,
        idempotency_key: str,
        request_hash: str,
    ) -> OrderCreationResult:
        existing = self.idempotency.get(idempotency_key)
        if existing is not None:
            existing_hash, order = existing
            if existing_hash != request_hash:
                raise IdempotencyConflictError
            return OrderCreationResult(order=order, replayed=True)
        if any(item.menu_item_id == UNAVAILABLE_ITEM_ID for item in command.items):
            raise MenuItemsUnavailableError((UNAVAILABLE_ITEM_ID,))

        requested = command.items[0]
        item = OrderItem(
            menu_item_id=requested.menu_item_id,
            name="Борщ",
            price_minor=39_000,
            quantity=requested.quantity,
        )
        self.order = Order(
            id=ORDER_ID,
            customer_id=command.customer_id,
            restaurant_id=command.restaurant_id,
            status=OrderStatus.CREATED,
            currency="RUB",
            total_minor=item.price_minor * item.quantity,
            delivery_address=command.delivery_address,
            items=(item,),
            created_at=NOW,
            updated_at=NOW,
        )
        self.idempotency[idempotency_key] = (request_hash, self.order)
        return OrderCreationResult(order=self.order, replayed=False)

    async def get_order(self, *, order_id: UUID, customer_id: UUID) -> Order | None:
        if self.order is None:
            return None
        if self.order.id != order_id or self.order.customer_id != customer_id:
            return None
        return self.order


def order_body(*, menu_item_id: UUID = MENU_ITEM_ID, quantity: int = 2) -> dict[str, object]:
    return {
        "customer_id": str(CUSTOMER_ID),
        "restaurant_id": str(RESTAURANT_ID),
        "delivery_address": "ул. Примерная, 1",
        "items": [{"menu_item_id": str(menu_item_id), "quantity": quantity}],
    }


def test_create_order_and_idempotent_replay() -> None:
    async def scenario() -> tuple[int, int, dict[str, object], dict[str, object]]:
        app = create_app()
        service = OrdersService(FakeOrdersRepository())
        app.dependency_overrides[get_orders_service] = lambda: service
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            first = await client.post(
                "/api/v1/orders",
                headers={"Idempotency-Key": "checkout-001"},
                json=order_body(),
            )
            replay = await client.post(
                "/api/v1/orders",
                headers={"Idempotency-Key": "checkout-001"},
                json=order_body(),
            )
        return first.status_code, replay.status_code, first.json(), replay.json()

    first_status, replay_status, first_body, replay_body = asyncio.run(scenario())

    assert first_status == 201
    assert replay_status == 200
    assert first_body == replay_body
    assert first_body["total_minor"] == 78_000
    assert first_body["items"][0]["name"] == "Борщ"  # type: ignore[index]


def test_reusing_key_with_different_request_returns_conflict() -> None:
    async def scenario() -> tuple[int, dict[str, object]]:
        app = create_app()
        service = OrdersService(FakeOrdersRepository())
        app.dependency_overrides[get_orders_service] = lambda: service
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post(
                "/api/v1/orders",
                headers={"Idempotency-Key": "checkout-002"},
                json=order_body(quantity=1),
            )
            conflict = await client.post(
                "/api/v1/orders",
                headers={"Idempotency-Key": "checkout-002"},
                json=order_body(quantity=2),
            )
        return conflict.status_code, conflict.json()

    status_code, body = asyncio.run(scenario())

    assert status_code == 409
    assert body["error"]["code"] == "conflict"  # type: ignore[index]
    assert body["error"]["message"] == (  # type: ignore[index]
        "Ключ идемпотентности уже использован для другого запроса"
    )


def test_unavailable_item_rejects_whole_order() -> None:
    async def scenario() -> tuple[int, dict[str, object]]:
        app = create_app()
        service = OrdersService(FakeOrdersRepository())
        app.dependency_overrides[get_orders_service] = lambda: service
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/orders",
                headers={"Idempotency-Key": "checkout-003"},
                json=order_body(menu_item_id=UNAVAILABLE_ITEM_ID),
            )
        return response.status_code, response.json()

    status_code, body = asyncio.run(scenario())

    assert status_code == 409
    assert body["error"]["details"]["item_ids"] == [  # type: ignore[index]
        str(UNAVAILABLE_ITEM_ID)
    ]


def test_order_is_not_visible_to_another_customer() -> None:
    async def scenario() -> int:
        app = create_app()
        service = OrdersService(FakeOrdersRepository())
        app.dependency_overrides[get_orders_service] = lambda: service
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post(
                "/api/v1/orders",
                headers={"Idempotency-Key": "checkout-004"},
                json=order_body(),
            )
            response = await client.get(
                f"/api/v1/orders/{ORDER_ID}",
                params={"customer_id": str(OTHER_CUSTOMER_ID)},
            )
        return response.status_code

    assert asyncio.run(scenario()) == 404
