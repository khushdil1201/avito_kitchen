from collections.abc import Sequence
from uuid import UUID, uuid4

import asyncpg

from avito_kitchen.domain.orders import (
    CreateOrderCommand,
    IdempotencyConflictError,
    MenuItemsUnavailableError,
    Order,
    OrderCreationResult,
    OrderItem,
    OrderStatus,
    RestaurantUnavailableError,
)
from avito_kitchen.infrastructure.database import DatabaseConnection


class PostgresOrdersRepository:
    """Сохраняет заказы и их снимки меню в одной транзакции PostgreSQL."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def create_order(
        self,
        *,
        command: CreateOrderCommand,
        idempotency_key: str,
        request_hash: str,
    ) -> OrderCreationResult:
        order_id = uuid4()
        scope = f"create-order:{command.customer_id}"
        async with self._pool.acquire() as connection, connection.transaction():
            claimed = await connection.fetchrow(
                """
                INSERT INTO idempotency_keys (scope, key, request_hash, resource_id)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (scope, key) DO NOTHING
                RETURNING resource_id
                """,
                scope,
                idempotency_key,
                request_hash,
                order_id,
            )
            if claimed is None:
                return await self._replay_order(
                    connection=connection,
                    scope=scope,
                    idempotency_key=idempotency_key,
                    request_hash=request_hash,
                    customer_id=command.customer_id,
                )

            restaurant = await connection.fetchrow(
                """
                SELECT currency
                FROM establishments
                WHERE id = $1 AND is_active
                FOR SHARE
                """,
                command.restaurant_id,
            )
            if restaurant is None:
                raise RestaurantUnavailableError

            requested_ids = [item.menu_item_id for item in command.items]
            menu_rows = await connection.fetch(
                """
                SELECT id, name, price_minor, is_available
                FROM menu_items
                WHERE establishment_id = $1 AND id = ANY($2::uuid[])
                FOR SHARE
                """,
                command.restaurant_id,
                requested_ids,
            )
            menu_by_id = {row["id"]: row for row in menu_rows}
            unavailable_ids = tuple(
                sorted(
                    (
                        item_id
                        for item_id in requested_ids
                        if item_id not in menu_by_id or not menu_by_id[item_id]["is_available"]
                    ),
                    key=str,
                )
            )
            if unavailable_ids:
                raise MenuItemsUnavailableError(unavailable_ids)

            items = tuple(
                OrderItem(
                    menu_item_id=requested.menu_item_id,
                    name=menu_by_id[requested.menu_item_id]["name"],
                    price_minor=menu_by_id[requested.menu_item_id]["price_minor"],
                    quantity=requested.quantity,
                )
                for requested in command.items
            )
            total_minor = sum(item.price_minor * item.quantity for item in items)
            order_row = await connection.fetchrow(
                """
                INSERT INTO orders (
                    id, customer_id, establishment_id, currency,
                    total_minor, delivery_address
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING created_at, updated_at
                """,
                order_id,
                command.customer_id,
                command.restaurant_id,
                restaurant["currency"],
                total_minor,
                command.delivery_address,
            )
            if order_row is None:
                raise RuntimeError("PostgreSQL не вернул созданный заказ")

            await connection.executemany(
                """
                INSERT INTO order_items (
                    order_id, menu_item_id, establishment_id, name, price_minor, quantity
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                [
                    (
                        order_id,
                        item.menu_item_id,
                        command.restaurant_id,
                        item.name,
                        item.price_minor,
                        item.quantity,
                    )
                    for item in items
                ],
            )
            await connection.execute(
                """
                INSERT INTO order_status_history (order_id, from_status, to_status, actor)
                VALUES ($1, NULL, $2, 'platform')
                """,
                order_id,
                OrderStatus.CREATED.value,
            )

            return OrderCreationResult(
                order=Order(
                    id=order_id,
                    customer_id=command.customer_id,
                    restaurant_id=command.restaurant_id,
                    status=OrderStatus.CREATED,
                    currency=restaurant["currency"],
                    total_minor=total_minor,
                    delivery_address=command.delivery_address,
                    items=items,
                    created_at=order_row["created_at"],
                    updated_at=order_row["updated_at"],
                ),
                replayed=False,
            )

    async def get_order(self, *, order_id: UUID, customer_id: UUID) -> Order | None:
        async with self._pool.acquire() as connection:
            return await self._get_order(
                connection=connection,
                order_id=order_id,
                customer_id=customer_id,
            )

    async def _replay_order(
        self,
        *,
        connection: DatabaseConnection,
        scope: str,
        idempotency_key: str,
        request_hash: str,
        customer_id: UUID,
    ) -> OrderCreationResult:
        key_row = await connection.fetchrow(
            """
            SELECT request_hash, resource_id
            FROM idempotency_keys
            WHERE scope = $1 AND key = $2
            """,
            scope,
            idempotency_key,
        )
        if key_row is None:
            raise RuntimeError("Ключ идемпотентности исчез во время транзакции")
        if key_row["request_hash"] != request_hash:
            raise IdempotencyConflictError
        order = await self._get_order(
            connection=connection,
            order_id=key_row["resource_id"],
            customer_id=customer_id,
        )
        if order is None:
            raise RuntimeError("Ключ идемпотентности ссылается на отсутствующий заказ")
        return OrderCreationResult(order=order, replayed=True)

    @staticmethod
    async def _get_order(
        *,
        connection: DatabaseConnection,
        order_id: UUID,
        customer_id: UUID,
    ) -> Order | None:
        order_row = await connection.fetchrow(
            """
            SELECT
                id, customer_id, establishment_id, status, currency,
                total_minor, delivery_address, created_at, updated_at
            FROM orders
            WHERE id = $1 AND customer_id = $2
            """,
            order_id,
            customer_id,
        )
        if order_row is None:
            return None
        item_rows: Sequence[asyncpg.Record] = await connection.fetch(
            """
            SELECT menu_item_id, name, price_minor, quantity
            FROM order_items
            WHERE order_id = $1
            ORDER BY menu_item_id
            """,
            order_id,
        )
        return Order(
            id=order_row["id"],
            customer_id=order_row["customer_id"],
            restaurant_id=order_row["establishment_id"],
            status=OrderStatus(order_row["status"]),
            currency=order_row["currency"],
            total_minor=order_row["total_minor"],
            delivery_address=order_row["delivery_address"],
            items=tuple(
                OrderItem(
                    menu_item_id=row["menu_item_id"],
                    name=row["name"],
                    price_minor=row["price_minor"],
                    quantity=row["quantity"],
                )
                for row in item_rows
            ),
            created_at=order_row["created_at"],
            updated_at=order_row["updated_at"],
        )
