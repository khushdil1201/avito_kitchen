# Схема базы данных

PostgreSQL является владельцем состояния каталога и заказов. Все изменения
схемы оформляются неизменяемыми SQL-файлами в каталоге `migrations`. Runner
сохраняет версию и SHA-256 каждой применённой миграции, выполняет новую миграцию
в транзакции и использует advisory lock против одновременного запуска.

```mermaid
erDiagram
    ESTABLISHMENTS ||--o{ MENU_ITEMS : содержит
    ESTABLISHMENTS ||--o{ ORDERS : принимает
    ORDERS ||--|{ ORDER_ITEMS : содержит
    MENU_ITEMS ||--o{ ORDER_ITEMS : фиксируется_в
    ORDERS ||--o{ ORDER_STATUS_HISTORY : изменяет_статус

    ESTABLISHMENTS {
        uuid id PK
        text external_id UK
        text name
        char currency
        boolean is_active
    }
    MENU_ITEMS {
        uuid id PK
        uuid establishment_id FK
        text external_id
        text name
        bigint price_minor
        boolean is_available
    }
    ORDERS {
        uuid id PK
        uuid customer_id
        uuid establishment_id FK
        text status
        char currency
        bigint total_minor
        text delivery_address
        text external_id
    }
    ORDER_ITEMS {
        uuid order_id PK,FK
        uuid menu_item_id PK,FK
        uuid establishment_id FK
        text name
        bigint price_minor
        integer quantity
    }
    ORDER_STATUS_HISTORY {
        bigint id PK
        uuid order_id FK
        text from_status
        text to_status
        text actor
    }
```

Таблица `idempotency_keys` техническая и не показана на диаграмме: она связывает
область операции и клиентский ключ с хешем запроса и созданным ресурсом.

## Основные решения

- UUID генерируются приложением, что не привязывает API к конкретной базе данных.
- Суммы хранятся как целые числа `price_minor` и `total_minor`; валюта заказа
  фиксируется отдельно.
- `order_items` хранит снимок названия и цены. Изменение или скрытие блюда не
  переписывает историю заказа.
- Составной внешний ключ позиции гарантирует, что блюдо и заказ принадлежат
  одному заведению.
- Удаление заказов бизнес-сценарием не предусмотрено. Каскад нужен только для
  административного удаления ошибочно созданной записи.
