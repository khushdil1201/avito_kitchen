CREATE TABLE establishments (
    id UUID PRIMARY KEY,
    external_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL CHECK (length(trim(name)) BETWEEN 1 AND 200),
    description TEXT NOT NULL DEFAULT '',
    currency CHAR(3) NOT NULL DEFAULT 'RUB' CHECK (currency ~ '^[A-Z]{3}$'),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE menu_items (
    id UUID PRIMARY KEY,
    establishment_id UUID NOT NULL REFERENCES establishments(id),
    external_id TEXT NOT NULL,
    name TEXT NOT NULL CHECK (length(trim(name)) BETWEEN 1 AND 200),
    description TEXT NOT NULL DEFAULT '',
    price_minor BIGINT NOT NULL CHECK (price_minor > 0),
    is_available BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (establishment_id, external_id),
    UNIQUE (id, establishment_id)
);

CREATE INDEX idx_menu_items_available
    ON menu_items (establishment_id, id)
    WHERE is_available;

CREATE TABLE orders (
    id UUID PRIMARY KEY,
    customer_id UUID NOT NULL,
    establishment_id UUID NOT NULL REFERENCES establishments(id),
    status TEXT NOT NULL DEFAULT 'created' CHECK (
        status IN (
            'created', 'accepted', 'rejected', 'preparing',
            'ready', 'delivering', 'completed', 'cancelled'
        )
    ),
    currency CHAR(3) NOT NULL CHECK (currency ~ '^[A-Z]{3}$'),
    total_minor BIGINT NOT NULL CHECK (total_minor > 0),
    delivery_address TEXT NOT NULL CHECK (length(trim(delivery_address)) BETWEEN 1 AND 500),
    external_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (establishment_id, external_id),
    UNIQUE (id, establishment_id)
);

CREATE INDEX idx_orders_customer_created
    ON orders (customer_id, created_at DESC, id);

CREATE INDEX idx_orders_establishment_status
    ON orders (establishment_id, status, created_at);

CREATE TABLE order_items (
    order_id UUID NOT NULL,
    menu_item_id UUID NOT NULL,
    establishment_id UUID NOT NULL,
    name TEXT NOT NULL CHECK (length(trim(name)) BETWEEN 1 AND 200),
    price_minor BIGINT NOT NULL CHECK (price_minor > 0),
    quantity INTEGER NOT NULL CHECK (quantity BETWEEN 1 AND 100),
    PRIMARY KEY (order_id, menu_item_id),
    FOREIGN KEY (order_id, establishment_id)
        REFERENCES orders(id, establishment_id) ON DELETE CASCADE,
    FOREIGN KEY (menu_item_id, establishment_id)
        REFERENCES menu_items(id, establishment_id)
);

CREATE TABLE order_status_history (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_id UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    from_status TEXT,
    to_status TEXT NOT NULL,
    actor TEXT NOT NULL CHECK (actor IN ('platform', 'restaurant')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (from_status IS NULL OR from_status <> to_status)
);

CREATE INDEX idx_order_status_history_order
    ON order_status_history (order_id, id);

CREATE TABLE idempotency_keys (
    scope TEXT NOT NULL,
    key TEXT NOT NULL,
    request_hash CHAR(64) NOT NULL CHECK (request_hash ~ '^[0-9a-f]{64}$'),
    resource_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (scope, key)
);
