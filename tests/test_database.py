"""
Unit tests for database module.
Tests models, database manager, and CRUD operations.
"""
import pytest
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
import tempfile
import json

from raspberry_app.database.db_manager import DatabaseManager
from raspberry_app.database.models import Product, Sale, SaleItem, RecommendationCache, APILog


@pytest.fixture
def temp_db():
    """Create temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = Path(f.name)

    db = DatabaseManager(db_path)
    db.init_database()

    yield db

    # Cleanup
    if db_path.exists():
        db_path.unlink()


@pytest.fixture
def sample_product():
    """Create sample product for testing."""
    return Product(
        ean="8470001234567",
        name="Test Ibuprofeno 600mg",
        price=4.95,
        category="Analgésicos",
        active_ingredient="Ibuprofeno",
        description="Test product",
        stock=50
    )


# ==================== PRODUCT TESTS ====================

def test_add_and_retrieve_product(temp_db, sample_product):
    """Test adding and retrieving a product."""
    # Add product
    product_id = temp_db.add_product(sample_product)
    assert product_id > 0

    # Retrieve by EAN
    retrieved = temp_db.get_product_by_ean(sample_product.ean)
    assert retrieved is not None
    assert retrieved.name == sample_product.name
    assert retrieved.price == sample_product.price
    assert retrieved.category == sample_product.category

    # Retrieve by ID
    retrieved_by_id = temp_db.get_product_by_id(product_id)
    assert retrieved_by_id is not None
    assert retrieved_by_id.ean == sample_product.ean


def test_ean_uniqueness(temp_db, sample_product):
    """Test that EAN must be unique."""
    temp_db.add_product(sample_product)

    # Try to add duplicate EAN
    duplicate = Product(
        ean=sample_product.ean,  # Same EAN
        name="Different product",
        price=10.0,
        category="Test",
        stock=10
    )

    with pytest.raises(sqlite3.IntegrityError):
        temp_db.add_product(duplicate)


def test_get_all_products(temp_db):
    """Test retrieving all products."""
    # Add multiple products
    products = [
        Product(ean="8470001111111", name="Product 1", price=5.0, category="Cat1", stock=10),
        Product(ean="8470002222222", name="Product 2", price=10.0, category="Cat2", stock=20),
        Product(ean="8470003333333", name="Product 3", price=15.0, category="Cat1", stock=30),
    ]

    for product in products:
        temp_db.add_product(product)

    # Get all
    all_products = temp_db.get_all_products()
    assert len(all_products) == 3

    # Filter by category
    cat1_products = temp_db.get_all_products(category="Cat1")
    assert len(cat1_products) == 2


def test_update_stock(temp_db, sample_product):
    """Test updating product stock."""
    product_id = temp_db.add_product(sample_product)

    # Update stock
    temp_db.update_stock(product_id, 100)

    # Verify
    updated = temp_db.get_product_by_id(product_id)
    assert updated.stock == 100

    # Test negative stock validation
    with pytest.raises(ValueError):
        temp_db.update_stock(product_id, -10)


def test_search_products(temp_db):
    """Test product search functionality."""
    products = [
        Product(ean="8470001111111", name="Ibuprofeno 600mg", price=5.0,
                category="Analgésicos", active_ingredient="Ibuprofeno", stock=10),
        Product(ean="8470002222222", name="Paracetamol 1g", price=3.0,
                category="Analgésicos", active_ingredient="Paracetamol", stock=20),
        Product(ean="8470003333333", name="Omeprazol 20mg", price=4.0,
                category="Digestivos", active_ingredient="Omeprazol", stock=15),
    ]

    for product in products:
        temp_db.add_product(product)

    # Search by name
    results = temp_db.search_products("Ibuprofeno")
    assert len(results) == 1
    assert results[0].name == "Ibuprofeno 600mg"

    # Search by active ingredient
    results = temp_db.search_products("Paracetamol")
    assert len(results) == 1

    # Partial search (case-insensitive)
    results = temp_db.search_products("buprofe")
    assert len(results) == 1


# ==================== SALES TESTS ====================

def test_create_sale(temp_db):
    """Test creating a sale with items."""
    # Add products first
    product1 = Product(ean="8470001111111", name="Product 1", price=10.0, category="Test", stock=50)
    product2 = Product(ean="8470002222222", name="Product 2", price=5.0, category="Test", stock=30)

    id1 = temp_db.add_product(product1)
    id2 = temp_db.add_product(product2)

    # Create sale
    items = [
        (id1, 2),  # 2 units of product 1
        (id2, 3),  # 3 units of product 2
    ]

    sale_id = temp_db.create_sale(items)
    assert sale_id > 0

    # Retrieve sale
    sale, sale_items = temp_db.get_sale(sale_id)
    assert sale is not None
    assert sale.total == (10.0 * 2) + (5.0 * 3)  # 35.0
    assert sale.items_count == 2
    assert len(sale_items) == 2

    # Verify stock was updated
    product1_updated = temp_db.get_product_by_id(id1)
    assert product1_updated.stock == 48  # 50 - 2

    product2_updated = temp_db.get_product_by_id(id2)
    assert product2_updated.stock == 27  # 30 - 3


def test_sale_insufficient_stock(temp_db):
    """Test that sale fails with insufficient stock."""
    product = Product(ean="8470001111111", name="Product 1", price=10.0, category="Test", stock=5)
    product_id = temp_db.add_product(product)

    # Try to sell more than available
    items = [(product_id, 10)]

    with pytest.raises(ValueError, match="Insufficient stock"):
        temp_db.create_sale(items)


def test_foreign_key_cascade(temp_db):
    """Test that deleting a sale cascades to sale_items."""
    # Add product and create sale
    product = Product(ean="8470001111111", name="Product 1", price=10.0, category="Test", stock=50)
    product_id = temp_db.add_product(product)

    items = [(product_id, 2)]
    sale_id = temp_db.create_sale(items)

    # Verify sale and items exist
    sale, sale_items = temp_db.get_sale(sale_id)
    assert len(sale_items) == 1

    # Delete sale
    with temp_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sales WHERE id = ?", (sale_id,))

        # Verify sale_items were cascaded
        cursor.execute("SELECT COUNT(*) as count FROM sale_items WHERE sale_id = ?", (sale_id,))
        count = cursor.fetchone()['count']
        assert count == 0


# ==================== CACHE TESTS ====================

def test_save_and_retrieve_cache(temp_db):
    """Test caching recommendations."""
    cart_hash = "test_hash_123"
    recommendations = json.dumps([{"name": "Product A", "priority": "high"}])

    # Save to cache
    temp_db.save_recommendations(cart_hash, recommendations, ttl_seconds=3600)

    # Retrieve from cache
    cached = temp_db.get_cached_recommendations(cart_hash)
    assert cached is not None
    assert cached.cart_hash == cart_hash
    assert cached.recommendations == recommendations
    assert cached.hit_count == 1  # First access


def test_cache_hit_counter(temp_db):
    """Test that cache hit counter increments."""
    cart_hash = "test_hash_456"
    recommendations = json.dumps([{"name": "Product B"}])

    temp_db.save_recommendations(cart_hash, recommendations)

    # Access multiple times
    for i in range(3):
        cached = temp_db.get_cached_recommendations(cart_hash)
        assert cached.hit_count == i + 1


def test_cache_expiration(temp_db):
    """Test that expired cache entries are not returned."""
    cart_hash = "test_hash_789"
    recommendations = json.dumps([{"name": "Product C"}])

    # Save with 1 second TTL
    temp_db.save_recommendations(cart_hash, recommendations, ttl_seconds=1)

    # Immediate retrieval should work
    cached = temp_db.get_cached_recommendations(cart_hash)
    assert cached is not None

    # After expiration, should return None
    import time
    time.sleep(2)
    expired = temp_db.get_cached_recommendations(cart_hash)
    assert expired is None


def test_clear_expired_cache(temp_db):
    """Test clearing expired cache entries."""
    # Add expired entry
    with temp_db.get_connection() as conn:
        cursor = conn.cursor()
        expired_time = (datetime.now() - timedelta(hours=2)).isoformat()
        cursor.execute("""
            INSERT INTO recommendation_cache (cart_hash, recommendations, expires_at)
            VALUES (?, ?, ?)
        """, ("expired_hash", "[]", expired_time))

    # Add valid entry
    temp_db.save_recommendations("valid_hash", "[]", ttl_seconds=3600)

    # Clear expired
    cleared_count = temp_db.clear_expired_cache()
    assert cleared_count == 1

    # Verify valid entry still exists
    valid = temp_db.get_cached_recommendations("valid_hash")
    assert valid is not None


# ==================== API LOG TESTS ====================

def test_log_api_call(temp_db):
    """Test logging API calls."""
    log_entry = APILog(
        request_type="recommendation",
        cart_items=3,
        response_time_ms=1500,
        success=True
    )

    log_id = temp_db.log_api_call(log_entry)
    assert log_id > 0


def test_api_stats(temp_db):
    """Test retrieving API statistics."""
    # Log several calls
    logs = [
        APILog(request_type="recommendation", cart_items=2, response_time_ms=1000, success=True),
        APILog(request_type="recommendation", cart_items=3, response_time_ms=1500, success=True),
        APILog(request_type="recommendation", cart_items=1, response_time_ms=2000, success=False, error_message="Timeout"),
    ]

    for log in logs:
        temp_db.log_api_call(log)

    # Get stats
    stats = temp_db.get_api_stats(since_hours=24)

    assert stats['total_calls'] == 3
    assert stats['successful_calls'] == 2
    assert stats['failed_calls'] == 1
    assert stats['success_rate'] == pytest.approx(66.67, rel=0.1)
    assert stats['avg_response_time_ms'] == pytest.approx(1500.0, rel=0.1)
    assert stats['max_response_time_ms'] == 2000
    assert stats['min_response_time_ms'] == 1000


# ==================== MODEL TESTS ====================

def test_product_to_dict():
    """Test Product.to_dict() conversion."""
    product = Product(
        id=1,
        ean="8470001234567",
        name="Test Product",
        price=9.99,
        category="Test",
        active_ingredient="Test Ingredient",
        description="Test description",
        stock=25
    )

    data = product.to_dict()
    assert data['id'] == 1
    assert data['ean'] == "8470001234567"
    assert data['name'] == "Test Product"
    assert data['price'] == 9.99


def test_product_str():
    """Test Product string representation."""
    product = Product(
        ean="8470001234567",
        name="Test Product",
        price=9.99,
        category="Test",
        stock=25
    )

    str_repr = str(product)
    assert "8470001234567" in str_repr
    assert "Test Product" in str_repr
    assert "9.99" in str_repr


# ==================== INDEX TESTS ====================

def test_indexes_exist(temp_db):
    """Verify that all required indexes exist."""
    with temp_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='index' AND sql IS NOT NULL
            ORDER BY name
        """)
        indexes = [row['name'] for row in cursor.fetchall()]

    # Check required indexes
    required_indexes = [
        'idx_products_ean',
        'idx_products_category',
        'idx_products_active_ingredient',
        'idx_sale_items_sale_id',
        'idx_sale_items_product_id',
        'idx_cache_cart_hash',
        'idx_cache_expires_at',
        'idx_api_logs_created_at',
        'idx_api_logs_success'
    ]

    for index in required_indexes:
        assert index in indexes, f"Missing index: {index}"


# ==================== INTEGRATION TEST ====================

def test_full_workflow(temp_db):
    """Integration test: complete workflow from product to sale."""
    # 1. Add products
    products = [
        Product(ean="8470001111111", name="Ibuprofeno", price=5.0, category="Analgésicos", stock=100),
        Product(ean="8470002222222", name="Paracetamol", price=3.5, category="Analgésicos", stock=150),
    ]

    product_ids = []
    for product in products:
        product_ids.append(temp_db.add_product(product))

    # 2. Create sale
    items = [(product_ids[0], 2), (product_ids[1], 3)]
    sale_id = temp_db.create_sale(items)

    # 3. Verify sale
    sale, sale_items = temp_db.get_sale(sale_id)
    assert sale.total == (5.0 * 2) + (3.5 * 3)
    assert len(sale_items) == 2

    # 4. Cache recommendations
    cart_hash = "workflow_test_hash"
    recommendations = json.dumps([{"name": "Omeprazol", "priority": "high"}])
    temp_db.save_recommendations(cart_hash, recommendations)

    # 5. Retrieve cache
    cached = temp_db.get_cached_recommendations(cart_hash)
    assert cached is not None

    # 6. Log API call
    log = APILog(request_type="recommendation", cart_items=2, response_time_ms=1200, success=True)
    temp_db.log_api_call(log)

    # 7. Get stats
    stats = temp_db.get_api_stats()
    assert stats['total_calls'] == 1
    assert stats['success_rate'] == 100.0
