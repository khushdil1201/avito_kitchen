from collections import defaultdict
from uuid import UUID

import asyncpg

from avito_kitchen.domain.orders import (
    PARTNER_STATUS_TRANSITIONS,
    InvalidOrderTransitionError,
    Order,
    OrderItem,
    OrderStatus,
    OrderTransitionResult,
    PartnerOrderNotFoundError,
)
from avito_kitchen.infrastructure.database import DatabaseConnection


class PostgresPartnerOrdersRepository:
    """Читает и изменяет заказы конкретного заведения."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def list_orders(
        self,
        *,
        restaurant_id: UUID,
        order_status: OrderStatus | None,
        limit: int,
    ) -> tuple[Order, ...]:
        async with self._pool.acquire() as connection:
            order_rows = await connection.fetch(
                """
                SELECT
                    id, customer_id, establishment_id, status, currency,
                    total_minor, delivery_address, created_at, updated_at
                FROM orders
                WHERE establishment_id = $1
                    AND ($2::text IS NULL OR status = $2)
                ORDER BY created_at, id
                LIMIT $3
                """,
                restaurant_id,
                order_status.value if order_status is not None else None,
                limit,
            )
            if not order_rows:
                return ()
            items_by_order = await self._items_by_order(
                connection,
                [row["id"] for row in order_rows],
            )
        return tuple(
            self._order_from_record(row, tuple(items_by_order[row["id"]])) for row in order_rows
        )

    async def transition_order(
        self,
        *,
        restaurant_id: UUID,
        order_id: UUID,
        target_status: OrderStatus,
    ) -> OrderTransitionResult:
        async with self._pool.acquire() as connection, connection.transaction():
            order_row = await connection.fetchrow(
                """
                SELECT
                    id, customer_id, establishment_id, status, currency,
                    total_minor, delivery_address, created_at, updated_at
                FROM orders
                WHERE id = $1 AND establishment_id = $2
                FOR UPDATE
                """,
                order_id,
                restaurant_id,
            )
            if order_row is None:
                raise PartnerOrderNotFoundError

            current_status = OrderStatus(order_row["status"])
            replayed = current_status == target_status
            if not replayed:
                allowed_targets = PARTNER_STATUS_TRANSITIONS.get(current_status, frozenset())
                if target_status not in allowed_targets:
                    raise InvalidOrderTransitionError(current_status, target_status)
                order_row = await connection.fetchrow(
                    """
                    UPDATE orders
                    SET status = $2, updated_at = now()
                    WHERE id = $1
                    RETURNING
                        id, customer_id, establishment_id, status, currency,
                        total_minor, delivery_address, created_at, updated_at
                    """,
                    order_id,
                    target_status.value,
                )
                if order_row is None:
                    raise RuntimeError("PostgreSQL не вернул обновлённый заказ")
                await connection.execute(
                    """
                    INSERT INTO order_status_history (order_id, from_status, to_status, actor)
                    VALUES ($1, $2, $3, 'restaurant')
                    """,
                    order_id,
                    current_status.value,
                    target_status.value,
                )

            items_by_order = await self._items_by_order(connection, [order_id])
            return OrderTransitionResult(
                order=self._order_from_record(order_row, tuple(items_by_order[order_id])),
                replayed=replayed,
            )

    @staticmethod
    async def _items_by_order(
        connection: DatabaseConnection,
        order_ids: list[UUID],
    ) -> defaultdict[UUID, list[OrderItem]]:
        rows = await connection.fetch(
            """
            SELECT order_id, menu_item_id, name, price_minor, quantity
            FROM order_items
            WHERE order_id = ANY($1::uuid[])
            ORDER BY order_id, menu_item_id
            """,
            order_ids,
        )
        result: defaultdict[UUID, list[OrderItem]] = defaultdict(list)
        for row in rows:
            result[row["order_id"]].append(
                OrderItem(
                    menu_item_id=row["menu_item_id"],
                    name=row["name"],
                    price_minor=row["price_minor"],
                    quantity=row["quantity"],
                )
            )
        return result

    @staticmethod
    def _order_from_record(row: asyncpg.Record, items: tuple[OrderItem, ...]) -> Order:
        return Order(
            id=row["id"],
            customer_id=row["customer_id"],
            restaurant_id=row["establishment_id"],
            status=OrderStatus(row["status"]),
            currency=row["currency"],
            total_minor=row["total_minor"],
            delivery_address=row["delivery_address"],
            items=items,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
