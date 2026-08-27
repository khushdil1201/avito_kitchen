from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class Restaurant:
    """Доступное пользователю заведение."""

    id: UUID
    name: str
    description: str
    currency: str


@dataclass(frozen=True, slots=True)
class MenuItem:
    """Позиция меню заведения."""

    id: UUID
    restaurant_id: UUID
    name: str
    description: str
    price_minor: int
    is_available: bool


@dataclass(frozen=True, slots=True)
class Page[T]:
    """Страница результатов и общее число подходящих записей."""

    items: tuple[T, ...]
    total: int
    limit: int
    offset: int


class RestaurantNotFoundError(Exception):
    """Запрошенное заведение не существует или недоступно пользователю."""
