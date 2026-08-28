import os
from uuid import UUID, uuid4

import httpx
import pytest

pytestmark = pytest.mark.e2e

RESTAURANT_ID = "10000000-0000-4000-8000-000000000001"
MENU_ITEM_ID = "20000000-0000-4000-8000-000000000001"
UNAVAILABLE_ITEM_ID = "20000000-0000-4000-8000-000000000004"
CUSTOMER_ID = "30000000-0000-4000-8000-000000000001"
OTHER_CUSTOMER_ID = "30000000-0000-4000-8000-000000000002"


def order_body(menu_item_id: str = MENU_ITEM_ID) -> dict[str, object]:
    return {
        "customer_id": CUSTOMER_ID,
        "restaurant_id": RESTAURANT_ID,
        "delivery_address": "ул. Интеграционная, 1",
        "items": [{"menu_item_id": menu_item_id, "quantity": 2}],
    }


def test_real_order_flow_through_both_services_and_postgres() -> None:
    kitchen_url = os.environ["KITCHEN_API_URL"]
    restaurant_url = os.environ["RESTAURANT_API_URL"]
    idempotency_key = f"e2e-{uuid4()}"

    with (
        httpx.Client(base_url=kitchen_url, timeout=5) as kitchen,
        httpx.Client(base_url=restaurant_url, timeout=5) as restaurant,
    ):
        readiness = kitchen.get("/api/v1/ready")
        assert readiness.status_code == 200

        menu = kitchen.get(f"/api/v1/restaurants/{RESTAURANT_ID}/menu")
        assert menu.status_code == 200
        assert MENU_ITEM_ID in {item["id"] for item in menu.json()["items"]}

        unavailable = kitchen.post(
            "/api/v1/orders",
            headers={"Idempotency-Key": f"unavailable-{uuid4()}"},
            json=order_body(UNAVAILABLE_ITEM_ID),
        )
        assert unavailable.status_code == 409
        assert unavailable.json()["error"]["details"]["item_ids"] == [UNAVAILABLE_ITEM_ID]

        created = kitchen.post(
            "/api/v1/orders",
            headers={
                "Idempotency-Key": idempotency_key,
                "X-Request-ID": "e2e-create-order",
            },
            json=order_body(),
        )
        assert created.status_code == 201
        assert created.headers["X-Request-ID"] == "e2e-create-order"
        order = created.json()
        order_id = order["id"]
        assert str(UUID(order_id)) == order_id
        assert order["status"] == "created"
        assert order["total_minor"] == 78_000

        replay = kitchen.post(
            "/api/v1/orders",
            headers={"Idempotency-Key": idempotency_key},
            json=order_body(),
        )
        assert replay.status_code == 200
        assert replay.json() == order

        hidden = kitchen.get(
            f"/api/v1/orders/{order_id}", params={"customer_id": OTHER_CUSTOMER_ID}
        )
        assert hidden.status_code == 404

        queue = restaurant.get("/api/v1/orders", params={"status": "created"})
        assert queue.status_code == 200
        assert order_id in {item["id"] for item in queue.json()["items"]}

        for action, expected_status in (
            ("accept", "accepted"),
            ("preparing", "preparing"),
            ("ready", "ready"),
        ):
            transitioned = restaurant.post(f"/api/v1/orders/{order_id}/{action}")
            assert transitioned.status_code == 200
            assert transitioned.json()["status"] == expected_status

        customer_view = kitchen.get(
            f"/api/v1/orders/{order_id}", params={"customer_id": CUSTOMER_ID}
        )
        assert customer_view.status_code == 200
        assert customer_view.json()["status"] == "ready"
