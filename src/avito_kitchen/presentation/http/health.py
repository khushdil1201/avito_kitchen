from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

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

