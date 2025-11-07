-- Schema for Pharmacy Recommendation System
-- SQLite Database Design

-- Enable foreign keys
PRAGMA foreign_keys = ON;

-- Products table: catalog of pharmaceutical products
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ean TEXT NOT NULL UNIQUE,  -- EAN-13 barcode
    name TEXT NOT NULL,
    price REAL NOT NULL CHECK(price > 0),
    category TEXT NOT NULL,
    active_ingredient TEXT,
    description TEXT,
    stock INTEGER NOT NULL DEFAULT 0 CHECK(stock >= 0),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_products_ean ON products(ean);
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);
CREATE INDEX IF NOT EXISTS idx_products_active_ingredient ON products(active_ingredient);

-- Sales table: completed sales transactions
CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    total REAL NOT NULL CHECK(total >= 0),
    items_count INTEGER NOT NULL CHECK(items_count > 0),
    completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Sale items table: individual items in each sale
CREATE TABLE IF NOT EXISTS sale_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL CHECK(quantity > 0),
    unit_price REAL NOT NULL CHECK(unit_price > 0),
    subtotal REAL NOT NULL CHECK(subtotal > 0),
    FOREIGN KEY (sale_id) REFERENCES sales(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT
);

-- Indexes for sale items
CREATE INDEX IF NOT EXISTS idx_sale_items_sale_id ON sale_items(sale_id);
CREATE INDEX IF NOT EXISTS idx_sale_items_product_id ON sale_items(product_id);

-- Recommendation cache: stores AI-generated recommendations by cart hash
CREATE TABLE IF NOT EXISTS recommendation_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cart_hash TEXT NOT NULL UNIQUE,  -- MD5 hash of cart contents
    recommendations TEXT NOT NULL,  -- JSON array of recommendations
    hit_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL
);

-- Index for cache lookups
CREATE INDEX IF NOT EXISTS idx_cache_cart_hash ON recommendation_cache(cart_hash);
CREATE INDEX IF NOT EXISTS idx_cache_expires_at ON recommendation_cache(expires_at);

-- API logs: track API calls for monitoring and debugging
CREATE TABLE IF NOT EXISTS api_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_type TEXT NOT NULL,  -- 'recommendation', 'product_info', etc.
    cart_items INTEGER,  -- number of items in cart
    response_time_ms INTEGER,  -- response time in milliseconds
    success BOOLEAN NOT NULL,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for API logs analysis
CREATE INDEX IF NOT EXISTS idx_api_logs_created_at ON api_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_api_logs_success ON api_logs(success);

-- Trigger to update updated_at timestamp on products
CREATE TRIGGER IF NOT EXISTS update_products_timestamp
AFTER UPDATE ON products
FOR EACH ROW
BEGIN
    UPDATE products SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- Trigger to update last_accessed_at on cache hits
CREATE TRIGGER IF NOT EXISTS update_cache_access
AFTER UPDATE OF hit_count ON recommendation_cache
FOR EACH ROW
BEGIN
    UPDATE recommendation_cache
    SET last_accessed_at = CURRENT_TIMESTAMP
    WHERE id = NEW.id;
END;
