import json
import logging
import re
from collections.abc import Mapping
from contextvars import ContextVar
from datetime import UTC, datetime
from time import perf_counter
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException

REQUEST_ID_HEADER = "X-Request-ID"
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_request_id: ContextVar[str] = ContextVar("request_id", default="-")
logger = logging.getLogger("avito_kitchen.http")


class ErrorBody(BaseModel):
    """Машиночитаемое описание ошибки."""

    code: str
    message: str
    details: Any = None
    request_id: str


class ErrorResponse(BaseModel):
    """Единая оболочка ошибочного HTTP-ответа."""

    error: ErrorBody


DEFAULT_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: {"model": ErrorResponse, "description": "Некорректный запрос"},
    401: {"model": ErrorResponse, "description": "Требуется авторизация"},
    404: {"model": ErrorResponse, "description": "Объект не найден"},
    409: {"model": ErrorResponse, "description": "Конфликт состояния"},
    422: {"model": ErrorResponse, "description": "Ошибка валидации запроса"},
    500: {"model": ErrorResponse, "description": "Внутренняя ошибка сервиса"},
    503: {"model": ErrorResponse, "description": "Сервис временно недоступен"},
}


class JsonFormatter(logging.Formatter):
    """Форматировать журналы сервиса как однострочный JSON."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", _request_id.get()),
        }
        for field in ("method", "path", "status_code", "duration_ms"):
            if hasattr(record, field):
                payload[field] = getattr(record, field)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str) -> None:
    """Настроить журнал сервиса без изменения глобального логгера процесса."""
    service_logger = logging.getLogger("avito_kitchen")
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    service_logger.handlers = [handler]
    service_logger.setLevel(level.upper())
    service_logger.propagate = False


def install_observability(app: FastAPI) -> None:
    """Подключить трассировку запросов и единый контракт ошибок."""

    @app.middleware("http")
    async def request_context(request: Request, call_next: Any) -> Any:
        incoming = request.headers.get(REQUEST_ID_HEADER, "")
        request_id = incoming if _REQUEST_ID_PATTERN.fullmatch(incoming) else str(uuid4())
        token = _request_id.set(request_id)
        started_at = perf_counter()
        status_code = 500
        try:
            try:
                response = await call_next(request)
            except Exception as exc:
                logger.exception("Unhandled application error", exc_info=exc)
                response = _error_response(500, "internal_error", "Внутренняя ошибка сервиса")
            status_code = response.status_code
            response.headers[REQUEST_ID_HEADER] = request_id
            return response
        finally:
            logger.info(
                "HTTP request completed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": status_code,
                    "duration_ms": round((perf_counter() - started_at) * 1000, 2),
                },
            )
            _request_id.reset(token)

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        del request
        detail = exc.detail
        if isinstance(detail, str):
            message, details = detail, None
        elif isinstance(detail, dict):
            message, details = detail.get("message", "Ошибка запроса"), detail
        else:
            message, details = "Ошибка запроса", detail
        return _error_response(
            exc.status_code,
            _error_code(exc.status_code),
            message,
            details,
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        del request
        details = [
            {"location": error["loc"], "message": error["msg"], "type": error["type"]}
            for error in exc.errors()
        ]
        return _error_response(422, "validation_error", "Ошибка валидации запроса", details)


def _error_response(
    status_code: int,
    code: str,
    message: str,
    details: Any = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        headers=headers,
        content=jsonable_encoder(
            {
                "error": {
                    "code": code,
                    "message": message,
                    "details": details,
                    "request_id": _request_id.get(),
                }
            }
        ),
    )


def _error_code(status_code: int) -> str:
    return {
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        409: "conflict",
        422: "validation_error",
        503: "service_unavailable",
    }.get(status_code, "http_error")
