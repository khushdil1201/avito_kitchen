from typing import Literal

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from avito_kitchen.infrastructure.database import Database

router = APIRouter(tags=["Состояние сервиса"])


class HealthResponse(BaseModel):
    """Ответ проверки состояния процесса приложения."""

    status: Literal["ok"]


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Проверить состояние процесса",
)
async def health() -> HealthResponse:
    """Подтвердить, что HTTP-процесс запущен и принимает запросы."""
    return HealthResponse(status="ok")


@router.get(
    "/ready",
    response_model=HealthResponse,
    summary="Проверить готовность сервиса",
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"description": "База данных недоступна"}},
)
async def readiness(request: Request) -> HealthResponse:
    """Проверить доступность обязательных зависимостей приложения."""
    database: Database = request.app.state.database
    if not await database.is_ready():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="База данных недоступна",
        )
    return HealthResponse(status="ok")
