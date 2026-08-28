import asyncio
from datetime import UTC, datetime
from uuid import UUID

from httpx import ASGITransport, AsyncClient, Response

from restaurant_api.kitchen_client import KitchenAPIError
from restaurant_api.main import create_app, get_kitchen_client
from restaurant_api.models import Order, OrderItem, OrderList, OrderStatus

ORDER_ID = UUID("40000000-0000-4000-8000-000000000001")


def make_order(status: OrderStatus = OrderStatus.CREATED) -> Order:
    now = datetime(2026, 8, 28, tzinfo=UTC)
    return Order(
        id=ORDER_ID,
        customer_id=UUID("30000000-0000-4000-8000-000000000001"),
        restaurant_id=UUID("10000000-0000-4000-8000-000000000001"),
        status=status,
        currency="RUB",
        total_minor=39_000,
        delivery_address="ул. Примерная, 1",
        items=[
            OrderItem(
                menu_item_id=UUID("20000000-0000-4000-8000-000000000001"),
                name="Борщ",
                price_minor=39_000,
                quantity=1,
            )
        ],
        created_at=now,
        updated_at=now,
    )


class FakeKitchenClient:
    def __init__(self, *, error: KitchenAPIError | None = None) -> None:
        self.error = error
        self.target_status: OrderStatus | None = None

    async def list_orders(self, order_status: OrderStatus | None) -> OrderList:
        if self.error is not None:
            raise self.error
        order = make_order()
        if order_status is not None and order_status != order.status:
            return OrderList(items=[])
        return OrderList(items=[order])

    async def transition_order(self, order_id: UUID, target_status: OrderStatus) -> Order:
        if self.error is not None:
            raise self.error
        assert order_id == ORDER_ID
        self.target_status = target_status
        return make_order(target_status)


async def request(
    method: str,
    path: str,
    *,
    client: FakeKitchenClient,
) -> Response:
    app = create_app()
    app.dependency_overrides[get_kitchen_client] = lambda: client
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        return await http_client.request(method, path)


def test_restaurant_reads_order_queue() -> None:
    response = asyncio.run(
        request("GET", "/api/v1/orders?status=created", client=FakeKitchenClient())
    )

    assert response.status_code == 200
    assert response.json()["items"][0]["id"] == str(ORDER_ID)


def test_restaurant_accepts_order_through_kitchen_client() -> None:
    client = FakeKitchenClient()

    response = asyncio.run(request("POST", f"/api/v1/orders/{ORDER_ID}/accept", client=client))

    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
    assert client.target_status == OrderStatus.ACCEPTED


def test_restaurant_preserves_upstream_business_error() -> None:
    client = FakeKitchenClient(error=KitchenAPIError(409, "Недопустимый переход"))

    response = asyncio.run(request("POST", f"/api/v1/orders/{ORDER_ID}/ready", client=client))

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"
    assert response.json()["error"]["message"] == "Недопустимый переход"


def test_restaurant_health() -> None:
    response = asyncio.run(request("GET", "/health", client=FakeKitchenClient()))

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
