import asyncio
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

from httpx import ASGITransport, AsyncClient, Response

from avito_kitchen.application.partner_orders import PartnerOrdersService
from avito_kitchen.config import Settings, get_settings
from avito_kitchen.domain.orders import (
    PARTNER_STATUS_TRANSITIONS,
    InvalidOrderTransitionError,
    Order,
    OrderItem,
    OrderStatus,
    OrderTransitionResult,
    PartnerOrderNotFoundError,
)
from avito_kitchen.main import create_app
from avito_kitchen.presentation.http.partner_orders import get_partner_orders_service

RESTAURANT_ID = UUID("10000000-0000-4000-8000-000000000001")
ORDER_ID = UUID("40000000-0000-4000-8000-000000000001")
PARTNER_TOKEN = "test-partner-token"


def make_order() -> Order:
    now = datetime(2026, 8, 28, tzinfo=UTC)
    return Order(
        id=ORDER_ID,
        customer_id=UUID("30000000-0000-4000-8000-000000000001"),
        restaurant_id=RESTAURANT_ID,
        status=OrderStatus.CREATED,
        currency="RUB",
        total_minor=39_000,
        delivery_address="ул. Примерная, 1",
        items=(
            OrderItem(
                menu_item_id=UUID("20000000-0000-4000-8000-000000000001"),
                name="Борщ",
                price_minor=39_000,
                quantity=1,
            ),
        ),
        created_at=now,
        updated_at=now,
    )


class FakePartnerOrdersRepository:
    def __init__(self) -> None:
        self.order = make_order()
        self.transitions = 0

    async def list_orders(
        self,
        *,
        restaurant_id: UUID,
        order_status: OrderStatus | None,
        limit: int,
    ) -> tuple[Order, ...]:
        if restaurant_id != self.order.restaurant_id:
            return ()
        if order_status is not None and order_status != self.order.status:
            return ()
        return (self.order,)[:limit]

    async def transition_order(
        self,
        *,
        restaurant_id: UUID,
        order_id: UUID,
        target_status: OrderStatus,
    ) -> OrderTransitionResult:
        if restaurant_id != self.order.restaurant_id or order_id != self.order.id:
            raise PartnerOrderNotFoundError
        if self.order.status == target_status:
            return OrderTransitionResult(order=self.order, replayed=True)
        if target_status not in PARTNER_STATUS_TRANSITIONS.get(self.order.status, frozenset()):
            raise InvalidOrderTransitionError(self.order.status, target_status)
        self.order = replace(self.order, status=target_status)
        self.transitions += 1
        return OrderTransitionResult(order=self.order, replayed=False)


async def request(
    method: str,
    path: str,
    *,
    repository: FakePartnerOrdersRepository,
    token: str | None = PARTNER_TOKEN,
    json: dict[str, str] | None = None,
) -> Response:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        partner_api_token=PARTNER_TOKEN,
        partner_restaurant_id=RESTAURANT_ID,
    )
    service = PartnerOrdersService(repository)
    app.dependency_overrides[get_partner_orders_service] = lambda: service
    transport = ASGITransport(app=app)
    headers = {"X-Partner-Token": token} if token is not None else {}
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(method, path, headers=headers, json=json)


def test_partner_queue_requires_valid_token() -> None:
    repository = FakePartnerOrdersRepository()

    response = asyncio.run(
        request("GET", "/api/v1/partner/orders", repository=repository, token=None)
    )

    assert response.status_code == 401


def test_partner_reads_created_order_queue() -> None:
    repository = FakePartnerOrdersRepository()

    response = asyncio.run(request("GET", "/api/v1/partner/orders", repository=repository))

    assert response.status_code == 200
    assert response.json()["items"][0]["id"] == str(ORDER_ID)
    assert response.json()["items"][0]["status"] == "created"


def test_partner_transition_is_validated_and_repeat_is_safe() -> None:
    async def scenario() -> tuple[Response, Response, Response]:
        repository = FakePartnerOrdersRepository()
        accepted = await request(
            "PATCH",
            f"/api/v1/partner/orders/{ORDER_ID}/status",
            repository=repository,
            json={"status": "accepted"},
        )
        replay = await request(
            "PATCH",
            f"/api/v1/partner/orders/{ORDER_ID}/status",
            repository=repository,
            json={"status": "accepted"},
        )
        invalid = await request(
            "PATCH",
            f"/api/v1/partner/orders/{ORDER_ID}/status",
            repository=repository,
            json={"status": "ready"},
        )
        assert repository.transitions == 1
        return accepted, replay, invalid

    accepted, replay, invalid = asyncio.run(scenario())

    assert accepted.status_code == 200
    assert replay.status_code == 200
    assert invalid.status_code == 409
    assert invalid.json()["detail"]["current"] == "accepted"
