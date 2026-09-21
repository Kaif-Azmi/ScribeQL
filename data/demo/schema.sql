-- ScribeQL Demo Database Schema
-- Dialect: PostgreSQL
-- 8-table e-commerce database

CREATE SCHEMA IF NOT EXISTS demo;

-- 1. Categories
CREATE TABLE IF NOT EXISTS demo.categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    slug VARCHAR(120) NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 2. Products
CREATE TABLE IF NOT EXISTS demo.products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    category_id INT NOT NULL REFERENCES demo.categories(id) ON DELETE RESTRICT,
    sku VARCHAR(64) NOT NULL UNIQUE,
    price NUMERIC(10, 2) NOT NULL CHECK (price >= 0),
    cost_price NUMERIC(10, 2) NOT NULL CHECK (cost_price >= 0),
    stock_quantity INT NOT NULL DEFAULT 0 CHECK (stock_quantity >= 0),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 3. Customers
CREATE TABLE IF NOT EXISTS demo.customers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    phone VARCHAR(32),
    city VARCHAR(100),
    state VARCHAR(100),
    country VARCHAR(100) NOT NULL DEFAULT 'India',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 4. Orders
CREATE TABLE IF NOT EXISTS demo.orders (
    id SERIAL PRIMARY KEY,
    customer_id INT NOT NULL REFERENCES demo.customers(id) ON DELETE RESTRICT,
    order_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(32) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'shipped', 'delivered', 'cancelled', 'refunded')),
    subtotal NUMERIC(12, 2) NOT NULL DEFAULT 0.00 CHECK (subtotal >= 0),
    discount_amount NUMERIC(12, 2) NOT NULL DEFAULT 0.00 CHECK (discount_amount >= 0),
    tax_amount NUMERIC(12, 2) NOT NULL DEFAULT 0.00 CHECK (tax_amount >= 0),
    total NUMERIC(12, 2) NOT NULL DEFAULT 0.00 CHECK (total >= 0),
    notes TEXT
);

-- 5. Order Items
CREATE TABLE IF NOT EXISTS demo.order_items (
    id SERIAL PRIMARY KEY,
    order_id INT NOT NULL REFERENCES demo.orders(id) ON DELETE CASCADE,
    product_id INT NOT NULL REFERENCES demo.products(id) ON DELETE RESTRICT,
    quantity INT NOT NULL CHECK (quantity > 0),
    unit_price NUMERIC(10, 2) NOT NULL CHECK (unit_price >= 0),
    total_price NUMERIC(12, 2) NOT NULL CHECK (total_price >= 0)
);

-- 6. Payments
CREATE TABLE IF NOT EXISTS demo.payments (
    id SERIAL PRIMARY KEY,
    order_id INT NOT NULL REFERENCES demo.orders(id) ON DELETE RESTRICT,
    payment_method VARCHAR(50) NOT NULL CHECK (payment_method IN ('upi', 'credit_card', 'debit_card', 'net_banking', 'cod')),
    amount NUMERIC(12, 2) NOT NULL CHECK (amount >= 0),
    status VARCHAR(32) NOT NULL DEFAULT 'completed' CHECK (status IN ('pending', 'completed', 'failed', 'refunded')),
    transaction_ref VARCHAR(100) UNIQUE,
    paid_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 7. Shipments
CREATE TABLE IF NOT EXISTS demo.shipments (
    id SERIAL PRIMARY KEY,
    order_id INT NOT NULL REFERENCES demo.orders(id) ON DELETE RESTRICT,
    carrier VARCHAR(100) NOT NULL,
    tracking_number VARCHAR(100) UNIQUE,
    status VARCHAR(32) NOT NULL DEFAULT 'in_transit' CHECK (status IN ('pending', 'in_transit', 'out_for_delivery', 'delivered', 'failed')),
    shipped_at TIMESTAMPTZ,
    delivered_at TIMESTAMPTZ
);

-- 8. Reviews
CREATE TABLE IF NOT EXISTS demo.reviews (
    id SERIAL PRIMARY KEY,
    product_id INT NOT NULL REFERENCES demo.products(id) ON DELETE CASCADE,
    customer_id INT NOT NULL REFERENCES demo.customers(id) ON DELETE CASCADE,
    rating INT NOT NULL CHECK (rating >= 1 AND rating <= 5),
    title VARCHAR(200),
    comment TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_product_customer UNIQUE (product_id, customer_id)
);

-- Indexes for performance & query pattern support
CREATE INDEX IF NOT EXISTS idx_products_category_id ON demo.products(category_id);
CREATE INDEX IF NOT EXISTS idx_orders_customer_id ON demo.orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_orders_order_date ON demo.orders(order_date);
CREATE INDEX IF NOT EXISTS idx_orders_status ON demo.orders(status);
CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON demo.order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_order_items_product_id ON demo.order_items(product_id);
CREATE INDEX IF NOT EXISTS idx_payments_order_id ON demo.payments(order_id);
CREATE INDEX IF NOT EXISTS idx_shipments_order_id ON demo.shipments(order_id);
CREATE INDEX IF NOT EXISTS idx_reviews_product_id ON demo.reviews(product_id);
