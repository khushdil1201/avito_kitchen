from typing import Any
from uuid import UUID

import httpx

from restaurant_api.models import Order, OrderList, OrderStatus


class KitchenAPIError(Exception):
    """Kitchen API вернул ошибку или оказался недоступен."""

    def __init__(self, status_code: int, detail: Any) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Kitchen API error: {status_code}")


class KitchenClient:
    """Типизированный HTTP-клиент закрытого API платформы."""

    def __init__(self, *, base_url: str, token: str, timeout: float) -> None:
        self._base_url = base_url
        self._headers = {"X-Partner-Token": token}
        self._timeout = timeout

    async def list_orders(self, order_status: OrderStatus | None) -> OrderList:
        params = {"status": order_status.value} if order_status is not None else {}
        payload = await self._request("GET", "/api/v1/partner/orders", params=params)
        return OrderList.model_validate(payload)

    async def transition_order(self, order_id: UUID, target_status: OrderStatus) -> Order:
        payload = await self._request(
            "PATCH",
            f"/api/v1/partner/orders/{order_id}/status",
            json={"status": target_status.value},
        )
        return Order.model_validate(payload)

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            async with httpx.AsyncClient(
                base_url=self._base_url,
                headers=self._headers,
                timeout=self._timeout,
            ) as client:
                response = await client.request(method, path, **kwargs)
        except httpx.RequestError as error:
            raise KitchenAPIError(503, "Kitchen API недоступен") from error

        if response.is_error:
            try:
                detail = response.json().get("detail", response.text)
            except ValueError:
                detail = response.text
            raise KitchenAPIError(response.status_code, detail)
        return response.json()

