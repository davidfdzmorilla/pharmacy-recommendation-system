"""
Database manager for Pharmacy Recommendation System.
Provides connection management and CRUD operations with context managers.
"""
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import List, Optional, Tuple
from datetime import datetime, timedelta

from raspberry_app.database.models import (
    Product, Sale, SaleItem, RecommendationCache, APILog
)
from raspberry_app.utils.logger import LoggerMixin


class DatabaseManager(LoggerMixin):
    """
    Manages SQLite database connections and operations.

    Example:
        >>> db = DatabaseManager()
        >>> db.init_database()
        >>> product = db.get_product_by_ean("8470001234567")
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize database manager.

        Args:
            db_path: Path to SQLite database file. If None, uses config.DB_PATH
        """
        if db_path is None:
            from raspberry_app.config import config
            db_path = config.DB_PATH

        self.db_path = Path(db_path)
        self.logger.info(f"DatabaseManager initialized with {self.db_path}")

    @contextmanager
    def get_connection(self):
        """
        Context manager for safe database connections.

        Yields:
            sqlite3.Connection: Database connection with Row factory

        Example:
            >>> with db.get_connection() as conn:
            ...     cursor = conn.cursor()
            ...     cursor.execute("SELECT * FROM products")
        """
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            # Enable foreign keys
            conn.execute("PRAGMA foreign_keys = ON")
            yield conn
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            self.logger.error(f"Database error: {e}")
            raise
        finally:
            if conn:
                conn.close()

    def init_database(self) -> None:
        """
        Initialize database from schema.sql file.

        Raises:
            FileNotFoundError: If schema.sql not found
        """
        schema_path = Path(__file__).parent / "schema.sql"
        if not schema_path.exists():
            raise FileNotFoundError(f"Schema file not found: {schema_path}")

        with schema_path.open("r") as f:
            schema_sql = f.read()

        with self.get_connection() as conn:
            conn.executescript(schema_sql)

        self.logger.info("Database initialized successfully")

    # ==================== PRODUCT OPERATIONS ====================

    def add_product(self, product: Product) -> int:
        """
        Insert new product into database.

        Args:
            product: Product instance to insert

        Returns:
            int: ID of inserted product

        Raises:
            sqlite3.IntegrityError: If EAN already exists
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO products (ean, name, price, category, active_ingredient, description, stock)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                product.ean, product.name, product.price, product.category,
                product.active_ingredient, product.description, product.stock
            ))
            product_id = cursor.lastrowid
            self.logger.debug(f"Added product: {product}")
            return product_id

    def get_product_by_ean(self, ean: str) -> Optional[Product]:
        """
        Retrieve product by EAN barcode.

        Args:
            ean: EAN-13 barcode

        Returns:
            Product if found, None otherwise
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM products WHERE ean = ?", (ean,))
            row = cursor.fetchone()
            if row:
                return Product.from_db_row(row)
            return None

    def get_product_by_id(self, product_id: int) -> Optional[Product]:
        """
        Retrieve product by ID.

        Args:
            product_id: Product ID

        Returns:
            Product if found, None otherwise
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,))
            row = cursor.fetchone()
            if row:
                return Product.from_db_row(row)
            return None

    def get_all_products(self, category: Optional[str] = None) -> List[Product]:
        """
        Retrieve all products, optionally filtered by category.

        Args:
            category: Optional category filter

        Returns:
            List of Product instances
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if category:
                cursor.execute("SELECT * FROM products WHERE category = ? ORDER BY name", (category,))
            else:
                cursor.execute("SELECT * FROM products ORDER BY category, name")
            return [Product.from_db_row(row) for row in cursor.fetchall()]

    def update_stock(self, product_id: int, quantity: int) -> None:
        """
        Update product stock quantity.

        Args:
            product_id: Product ID
            quantity: New stock quantity

        Raises:
            ValueError: If quantity is negative
        """
        if quantity < 0:
            raise ValueError("Stock quantity cannot be negative")

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE products SET stock = ? WHERE id = ?", (quantity, product_id))
            if cursor.rowcount == 0:
                raise ValueError(f"Product {product_id} not found")
            self.logger.debug(f"Updated stock for product {product_id}: {quantity}")

    def search_products(self, query: str) -> List[Product]:
        """
        Search products by name or active ingredient.

        Args:
            query: Search query string

        Returns:
            List of matching Product instances
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            search_pattern = f"%{query}%"
            cursor.execute("""
                SELECT * FROM products
                WHERE LOWER(name) LIKE LOWER(?) OR LOWER(active_ingredient) LIKE LOWER(?)
                ORDER BY name
            """, (search_pattern, search_pattern))
            return [Product.from_db_row(row) for row in cursor.fetchall()]

    # ==================== SALES OPERATIONS ====================

    def create_sale(self, items: List[Tuple[int, int]]) -> int:
        """
        Create new sale transaction with items.

        Args:
            items: List of (product_id, quantity) tuples

        Returns:
            int: ID of created sale

        Raises:
            ValueError: If any product not found or insufficient stock
        """
        if not items:
            raise ValueError("Sale must have at least one item")

        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Calculate total and validate products
            total = 0.0
            sale_items_data = []

            for product_id, quantity in items:
                cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,))
                row = cursor.fetchone()
                if not row:
                    raise ValueError(f"Product {product_id} not found")

                product = Product.from_db_row(row)
                if product.stock < quantity:
                    raise ValueError(f"Insufficient stock for {product.name}")

                subtotal = product.price * quantity
                total += subtotal
                sale_items_data.append((product_id, quantity, product.price, subtotal))

                # Update stock
                new_stock = product.stock - quantity
                cursor.execute("UPDATE products SET stock = ? WHERE id = ?", (new_stock, product_id))

            # Create sale
            cursor.execute("""
                INSERT INTO sales (total, items_count)
                VALUES (?, ?)
            """, (total, len(items)))
            sale_id = cursor.lastrowid

            # Create sale items
            for product_id, quantity, unit_price, subtotal in sale_items_data:
                cursor.execute("""
                    INSERT INTO sale_items (sale_id, product_id, quantity, unit_price, subtotal)
                    VALUES (?, ?, ?, ?, ?)
                """, (sale_id, product_id, quantity, unit_price, subtotal))

            self.logger.info(f"Created sale {sale_id}: €{total:.2f} ({len(items)} items)")
            return sale_id

    def get_sale(self, sale_id: int) -> Optional[Tuple[Sale, List[SaleItem]]]:
        """
        Retrieve sale with its items.

        Args:
            sale_id: Sale ID

        Returns:
            Tuple of (Sale, List[SaleItem]) if found, None otherwise
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Get sale
            cursor.execute("SELECT * FROM sales WHERE id = ?", (sale_id,))
            sale_row = cursor.fetchone()
            if not sale_row:
                return None

            sale = Sale.from_db_row(sale_row)

            # Get items
            cursor.execute("SELECT * FROM sale_items WHERE sale_id = ?", (sale_id,))
            items = [SaleItem.from_db_row(row) for row in cursor.fetchall()]

            return (sale, items)

    # ==================== CACHE OPERATIONS ====================

    def get_cached_recommendations(self, cart_hash: str) -> Optional[RecommendationCache]:
        """
        Retrieve cached recommendations by cart hash.

        Args:
            cart_hash: MD5 hash of cart contents

        Returns:
            RecommendationCache if found and not expired, None otherwise
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM recommendation_cache
                WHERE cart_hash = ? AND expires_at > ?
            """, (cart_hash, datetime.now().isoformat()))

            row = cursor.fetchone()
            if row:
                # Increment hit count
                cache_id = row["id"]
                cursor.execute("""
                    UPDATE recommendation_cache
                    SET hit_count = hit_count + 1
                    WHERE id = ?
                """, (cache_id,))

                # Fetch updated row to get correct hit_count
                cursor.execute("SELECT * FROM recommendation_cache WHERE id = ?", (cache_id,))
                updated_row = cursor.fetchone()

                self.logger.debug(f"Cache hit for {cart_hash[:8]}...")
                return RecommendationCache.from_db_row(updated_row)

            self.logger.debug(f"Cache miss for {cart_hash[:8]}...")
            return None

    def save_recommendations(self, cart_hash: str, recommendations: str, ttl_seconds: int = 3600) -> None:
        """
        Save recommendations to cache.

        Args:
            cart_hash: MD5 hash of cart contents
            recommendations: JSON string of recommendations
            ttl_seconds: Time to live in seconds (default: 1 hour)
        """
        expires_at = datetime.now() + timedelta(seconds=ttl_seconds)

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO recommendation_cache
                (cart_hash, recommendations, expires_at, hit_count)
                VALUES (?, ?, ?, 0)
            """, (cart_hash, recommendations, expires_at.isoformat()))

            self.logger.debug(f"Saved recommendations to cache: {cart_hash[:8]}...")

    def clear_expired_cache(self) -> int:
        """
        Remove expired cache entries.

        Returns:
            int: Number of entries removed
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM recommendation_cache
                WHERE expires_at <= ?
            """, (datetime.now().isoformat(),))
            count = cursor.rowcount
            self.logger.info(f"Cleared {count} expired cache entries")
            return count

    # ==================== API LOG OPERATIONS ====================

    def log_api_call(self, log_entry: APILog) -> int:
        """
        Log API call for monitoring.

        Args:
            log_entry: APILog instance

        Returns:
            int: ID of log entry
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO api_logs (request_type, cart_items, response_time_ms, success, error_message)
                VALUES (?, ?, ?, ?, ?)
            """, (
                log_entry.request_type, log_entry.cart_items,
                log_entry.response_time_ms, log_entry.success, log_entry.error_message
            ))
            return cursor.lastrowid

    def get_api_stats(self, since_hours: int = 24) -> dict:
        """
        Get API call statistics.

        Args:
            since_hours: Look back this many hours

        Returns:
            dict: Statistics including total calls, success rate, avg response time
        """
        since = datetime.now() - timedelta(hours=since_hours)

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    COUNT(*) as total_calls,
                    SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful_calls,
                    AVG(response_time_ms) as avg_response_time,
                    MAX(response_time_ms) as max_response_time,
                    MIN(response_time_ms) as min_response_time
                FROM api_logs
                WHERE created_at >= ?
            """, (since.isoformat(),))

            row = cursor.fetchone()
            total = row["total_calls"] or 0
            successful = row["successful_calls"] or 0

            return {
                "total_calls": total,
                "successful_calls": successful,
                "failed_calls": total - successful,
                "success_rate": (successful / total * 100) if total > 0 else 0,
                "avg_response_time_ms": row["avg_response_time"] or 0,
                "max_response_time_ms": row["max_response_time"] or 0,
                "min_response_time_ms": row["min_response_time"] or 0
            }
