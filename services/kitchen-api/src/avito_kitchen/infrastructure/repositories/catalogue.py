from uuid import UUID

import asyncpg

from avito_kitchen.domain.catalogue import MenuItem, Page, Restaurant


class PostgresCatalogueRepository:
    """Читает каталог из PostgreSQL явными SQL-запросами."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def list_restaurants(
        self,
        *,
        name: str | None,
        limit: int,
        offset: int,
    ) -> Page[Restaurant]:
        async with (
            self._pool.acquire() as connection,
            connection.transaction(isolation="repeatable_read", readonly=True),
        ):
            total = await connection.fetchval(
                """
                SELECT count(*)
                FROM establishments
                WHERE is_active AND ($1::text IS NULL OR name ILIKE '%' || $1 || '%')
                """,
                name,
            )
            rows = await connection.fetch(
                """
                    SELECT id, name, description, currency
                    FROM establishments
                    WHERE is_active
                        AND ($1::text IS NULL OR name ILIKE '%' || $1 || '%')
                    ORDER BY name, id
                    LIMIT $2 OFFSET $3
                """,
                name,
                limit,
                offset,
            )
        return Page(
            items=tuple(self._restaurant_from_record(row) for row in rows),
            total=int(total),
            limit=limit,
            offset=offset,
        )

    async def get_restaurant(self, restaurant_id: UUID) -> Restaurant | None:
        row = await self._pool.fetchrow(
            """
            SELECT id, name, description, currency
            FROM establishments
            WHERE id = $1 AND is_active
            """,
            restaurant_id,
        )
        return self._restaurant_from_record(row) if row is not None else None

    async def list_menu_items(
        self,
        *,
        restaurant_id: UUID,
        available_only: bool,
        limit: int,
        offset: int,
    ) -> Page[MenuItem]:
        async with (
            self._pool.acquire() as connection,
            connection.transaction(isolation="repeatable_read", readonly=True),
        ):
            total = await connection.fetchval(
                """
                SELECT count(*)
                FROM menu_items
                WHERE establishment_id = $1 AND (NOT $2::boolean OR is_available)
                """,
                restaurant_id,
                available_only,
            )
            rows = await connection.fetch(
                """
                    SELECT id, establishment_id, name, description, price_minor, is_available
                    FROM menu_items
                    WHERE establishment_id = $1 AND (NOT $2::boolean OR is_available)
                    ORDER BY name, id
                    LIMIT $3 OFFSET $4
                """,
                restaurant_id,
                available_only,
                limit,
                offset,
            )
        return Page(
            items=tuple(self._menu_item_from_record(row) for row in rows),
            total=int(total),
            limit=limit,
            offset=offset,
        )

    @staticmethod
    def _restaurant_from_record(row: asyncpg.Record) -> Restaurant:
        return Restaurant(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            currency=row["currency"],
        )

    @staticmethod
    def _menu_item_from_record(row: asyncpg.Record) -> MenuItem:
        return MenuItem(
            id=row["id"],
            restaurant_id=row["establishment_id"],
            name=row["name"],
            description=row["description"],
            price_minor=row["price_minor"],
            is_available=row["is_available"],
        )
