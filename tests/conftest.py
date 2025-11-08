"""
Pytest configuration and shared fixtures.
Provides reusable fixtures for database, cache, API mocks, and sample data.
"""
import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch
import json

from raspberry_app.database.db_manager import DatabaseManager
from raspberry_app.database.models import Product
from raspberry_app.api.cache_manager import CacheManager
from raspberry_app.api.claude_client import ClaudeClient


@pytest.fixture
def temp_db():
    """
    Temporary SQLite database for tests.

    Creates a temporary file, yields the path, and cleans up after test.

    Yields:
        Path: Path to temporary database file

    Example:
        >>> def test_example(temp_db):
        ...     db = DatabaseManager(db_path=temp_db)
    """
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = Path(f.name)

    yield db_path

    # Cleanup
    if db_path.exists():
        db_path.unlink()


@pytest.fixture
def db_manager(temp_db):
    """
    DatabaseManager instance with temporary database.

    Provides a clean DatabaseManager for each test with schema initialized.

    Args:
        temp_db: Temporary database path fixture

    Returns:
        DatabaseManager: Initialized database manager

    Example:
        >>> def test_example(db_manager):
        ...     product_id = db_manager.add_product(product)
    """
    manager = DatabaseManager(db_path=temp_db)
    manager.init_database()  # Initialize schema
    return manager


@pytest.fixture
def sample_product():
    """
    Sample product for testing.

    Returns:
        Product: Test product with valid EAN-13

    Example:
        >>> def test_example(sample_product):
        ...     assert sample_product.ean == "8470001234568"
    """
    return Product(
        id=None,
        ean="8470001234568",
        name="Ibuprofeno 600mg 20 comprimidos",
        price=4.95,
        category="Analgésicos",
        active_ingredient="Ibuprofeno",
        description="Antiinflamatorio y analgésico para dolor moderado",
        stock=50
    )


@pytest.fixture
def sample_products():
    """
    List of sample products for testing cart scenarios.

    Returns:
        List[Product]: Multiple test products with valid EAN-13

    Example:
        >>> def test_cart(sample_products):
        ...     cart = [p.to_dict() for p in sample_products]
    """
    return [
        Product(
            id=None,
            ean="8470001234568",
            name="Ibuprofeno 600mg 20 comprimidos",
            price=4.95,
            category="Analgésicos",
            active_ingredient="Ibuprofeno",
            description="Antiinflamatorio y analgésico",
            stock=50
        ),
        Product(
            id=None,
            ean="8470002345671",
            name="Paracetamol 1g 40 comprimidos",
            price=3.50,
            category="Analgésicos",
            active_ingredient="Paracetamol",
            description="Analgésico y antipirético",
            stock=75
        ),
        Product(
            id=None,
            ean="8470003456786",
            name="Omeprazol 20mg 28 cápsulas",
            price=8.50,
            category="Digestivos",
            active_ingredient="Omeprazol",
            description="Protector gástrico",
            stock=30
        )
    ]


@pytest.fixture
def cache_manager():
    """
    CacheManager instance for testing.

    Provides a cache with small size and TTL for fast tests.

    Returns:
        CacheManager: Cache manager with max_size=10, ttl=60

    Example:
        >>> def test_cache(cache_manager):
        ...     cache_manager.set("key", {"data": "value"})
    """
    return CacheManager(max_size=10, ttl=60)


@pytest.fixture
def mock_anthropic_response():
    """
    Mock response from Anthropic Claude API.

    Returns valid JSON structure matching PromptBuilder expectations.

    Returns:
        dict: Mock recommendation response

    Example:
        >>> def test_api(mock_anthropic_response):
        ...     assert "recommendations" in mock_anthropic_response
    """
    return {
        "recommendations": [
            {
                "product_name": "Omeprazol 20mg 28 cápsulas",
                "category": "Digestivos",
                "reason": "Protector gástrico recomendado con antiinflamatorios para prevenir lesiones gástricas",
                "priority": "high",
                "estimated_price": "8.50"
            },
            {
                "product_name": "Vitamina C 1000mg 20 comprimidos",
                "category": "Vitaminas",
                "reason": "Complemento antioxidante para reforzar el sistema inmunitario",
                "priority": "medium",
                "estimated_price": "6.95"
            },
            {
                "product_name": "Crema antiinflamatoria 60g",
                "category": "Dermatología",
                "reason": "Tratamiento tópico complementario para dolores musculares",
                "priority": "low",
                "estimated_price": "7.50"
            }
        ],
        "analysis": "El cliente ha comprado analgésicos antiinflamatorios. Se recomienda protector gástrico como medida preventiva, vitaminas para apoyo general, y tratamiento tópico como alternativa complementaria."
    }


@pytest.fixture
def mock_claude_client(cache_manager, mock_anthropic_response):
    """
    ClaudeClient with mocked Anthropic API.

    Prevents real API calls during tests while maintaining cache behavior.

    Args:
        cache_manager: Cache manager fixture
        mock_anthropic_response: Mock response fixture

    Yields:
        ClaudeClient: Client with mocked API

    Example:
        >>> def test_recommendations(mock_claude_client):
        ...     cart = [{"name": "Ibuprofeno", "category": "Analgésicos"}]
        ...     result = mock_claude_client.get_recommendations(cart)
    """
    with patch('raspberry_app.api.claude_client.Anthropic') as mock_anthropic:
        # Configure mock response
        mock_instance = Mock()
        mock_response = Mock()
        mock_content = Mock()

        # Convert dict to JSON string (as API would return)
        mock_content.text = json.dumps(mock_anthropic_response)
        mock_response.content = [mock_content]
        mock_instance.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_instance

        # Create client with test API key
        client = ClaudeClient(
            cache_manager=cache_manager,
            api_key="test-api-key"
        )

        yield client


@pytest.fixture
def populated_db(db_manager, sample_products):
    """
    Database pre-populated with sample products.

    Useful for integration tests that need existing data.

    Args:
        db_manager: Database manager fixture
        sample_products: Sample products fixture

    Returns:
        DatabaseManager: Database with products inserted

    Example:
        >>> def test_lookup(populated_db):
        ...     product = populated_db.get_product_by_ean("8470001234568")
        ...     assert product is not None
    """
    for product in sample_products:
        db_manager.add_product(product)

    return db_manager


@pytest.fixture
def sample_cart(sample_products):
    """
    Sample shopping cart with multiple products.

    Returns cart in dict format suitable for API calls.

    Args:
        sample_products: Sample products fixture

    Returns:
        List[dict]: Cart items as dictionaries

    Example:
        >>> def test_cart_flow(sample_cart):
        ...     recommendations = client.get_recommendations(sample_cart)
    """
    return [
        {
            "name": product.name,
            "category": product.category,
            "active_ingredient": product.active_ingredient,
            "price": product.price
        }
        for product in sample_products[:2]  # First 2 products
    ]


# Performance testing helpers

@pytest.fixture
def performance_timer():
    """
    Simple timer for performance tests.

    Yields:
        function: Call timer() to get elapsed time in seconds

    Example:
        >>> def test_speed(performance_timer):
        ...     # do something
        ...     elapsed = performance_timer()
        ...     assert elapsed < 2.0
    """
    import time
    start_time = time.time()

    def timer():
        return time.time() - start_time

    yield timer


# Test markers

def pytest_configure(config):
    """
    Configure custom pytest markers.
    """
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "unit: mark test as unit test"
    )
