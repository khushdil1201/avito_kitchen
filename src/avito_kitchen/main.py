from fastapi import FastAPI

from avito_kitchen.presentation.http.health import router as health_router


def create_app() -> FastAPI:
    """Создать и настроить экземпляр HTTP-приложения."""
    app = FastAPI(
        title="Авито.Кухня API",
        summary="API платформы для заказа еды",
        version="0.1.0",
    )
    app.include_router(health_router, prefix="/api/v1")
    return app


app = create_app()

