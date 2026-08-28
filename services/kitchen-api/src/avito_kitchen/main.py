from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from avito_kitchen.config import Settings, get_settings
from avito_kitchen.infrastructure.database import Database
from avito_kitchen.presentation.http.catalogue import router as catalogue_router
from avito_kitchen.presentation.http.health import router as health_router
from avito_kitchen.presentation.http.orders import router as orders_router
from avito_kitchen.presentation.http.partner_orders import router as partner_orders_router


def create_app(settings: Settings | None = None) -> FastAPI:
    """Создать и настроить экземпляр HTTP-приложения."""
    resolved_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        database = Database(
            dsn=str(resolved_settings.database_url),
            min_size=resolved_settings.database_pool_min_size,
            max_size=resolved_settings.database_pool_max_size,
        )
        await database.connect()
        app.state.database = database
        try:
            yield
        finally:
            await database.disconnect()

    app = FastAPI(
        title="Авито.Кухня API",
        summary="API платформы для заказа еды",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(catalogue_router, prefix="/api/v1")
    app.include_router(orders_router, prefix="/api/v1")
    app.include_router(partner_orders_router, prefix="/api/v1")
    return app


app = create_app()
