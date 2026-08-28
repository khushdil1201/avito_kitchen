# Restaurant API

Демонстрационный сервис заведения показывает интеграцию без прямого доступа к
базе платформы. Он получает очередь заказов и меняет их статусы только через
закрытый HTTP API Kitchen API.

Основные маршруты:

- `GET /api/v1/orders` — получить очередь заведения;
- `POST /api/v1/orders/{order_id}/accept` — принять заказ;
- `POST /api/v1/orders/{order_id}/reject` — отклонить заказ;
- `POST /api/v1/orders/{order_id}/preparing` — начать приготовление;
- `POST /api/v1/orders/{order_id}/ready` — сообщить о готовности.
