from typing import Any
from uuid import UUID

import httpx

from restaurant_api.models import Order, OrderList, OrderStatus


class KitchenAPIError(Exception):
    """Kitchen API вернул ошибку или оказался недоступен."""

    def __init__(self, status_code: int, message: str, details: Any = None) -> None:
        self.status_code = status_code
        self.message = message
        self.details = details
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
            raise _parse_error_response(response)
        return response.json()


def _parse_error_response(response: httpx.Response) -> KitchenAPIError:
    """Преобразовать ошибочный ответ платформы в типизированную ошибку клиента."""
    fallback_message = response.text or "Kitchen API вернул ошибку"
    try:
        payload = response.json()
    except ValueError:
        return KitchenAPIError(response.status_code, fallback_message)

    if not isinstance(payload, dict):
        return KitchenAPIError(response.status_code, fallback_message, payload)

    envelope = payload.get("error")
    if isinstance(envelope, dict):
        message = envelope.get("message")
        if isinstance(message, str):
            return KitchenAPIError(response.status_code, message, envelope.get("details"))

    legacy_detail = payload.get("detail")
    if isinstance(legacy_detail, str):
        return KitchenAPIError(response.status_code, legacy_detail)
    if isinstance(legacy_detail, dict):
        message = legacy_detail.get("message")
        if isinstance(message, str):
            return KitchenAPIError(response.status_code, message, legacy_detail)

    return KitchenAPIError(response.status_code, fallback_message, payload)
