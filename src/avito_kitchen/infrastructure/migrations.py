import asyncio
import hashlib
from pathlib import Path

import asyncpg

from avito_kitchen.config import get_settings

MIGRATIONS_PATH = Path("migrations")
MIGRATION_LOCK_ID = 734_826_411


async def migrate() -> None:
    """Последовательно применить ещё не выполненные SQL-миграции."""
    settings = get_settings()
    connection = await asyncpg.connect(str(settings.database_url))
    try:
        await connection.execute("SELECT pg_advisory_lock($1)", MIGRATION_LOCK_ID)
        await connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                checksum CHAR(64) NOT NULL,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )

        applied_rows = await connection.fetch("SELECT version, checksum FROM schema_migrations")
        applied = {row["version"]: row["checksum"] for row in applied_rows}

        for path in sorted(MIGRATIONS_PATH.glob("*.sql")):
            sql = path.read_text(encoding="utf-8")
            checksum = hashlib.sha256(sql.encode()).hexdigest()
            previous_checksum = applied.get(path.name)
            if previous_checksum is not None:
                if previous_checksum != checksum:
                    raise RuntimeError(f"Изменена уже применённая миграция: {path.name}")
                continue

            async with connection.transaction():
                await connection.execute(sql)
                await connection.execute(
                    "INSERT INTO schema_migrations (version, checksum) VALUES ($1, $2)",
                    path.name,
                    checksum,
                )
            print(f"Применена миграция {path.name}")
    finally:
        await connection.close()


if __name__ == "__main__":
    asyncio.run(migrate())

