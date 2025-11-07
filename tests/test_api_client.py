"""
Unit tests for API client, cache manager, and prompt builder.
Tests caching behavior, API integration, and response parsing.
"""
import pytest
import time
import json
from unittest.mock import Mock, patch, MagicMock
from raspberry_app.api.cache_manager import CacheManager
from raspberry_app.api.prompt_builder import PromptBuilder
from raspberry_app.api.claude_client import ClaudeClient


# ==================== CACHE MANAGER TESTS ====================

def test_cache_basic_operations():
    """Test basic cache set/get operations."""
    cache = CacheManager(max_size=10, ttl=3600)

    # Test set and get
    cache.set("key1", {"data": "value1"})
    result = cache.get("key1")

    assert result is not None
    assert result["data"] == "value1"

    # Test miss
    result = cache.get("nonexistent")
    assert result is None


def test_cache_lru_eviction():
    """Test LRU eviction when cache is full."""
    cache = CacheManager(max_size=3, ttl=3600)

    # Fill cache
    cache.set("key1", {"data": "value1"})
    cache.set("key2", {"data": "value2"})
    cache.set("key3", {"data": "value3"})

    # Add fourth item - should evict key1 (least recently used)
    cache.set("key4", {"data": "value4"})

    assert cache.get("key1") is None  # Evicted
    assert cache.get("key2") is not None
    assert cache.get("key3") is not None
    assert cache.get("key4") is not None

    stats = cache.get_stats()
    assert stats["size"] == 3
    assert stats["evictions"] == 1


def test_cache_lru_access_updates():
    """Test that accessing an item updates its LRU position."""
    cache = CacheManager(max_size=3, ttl=3600)

    cache.set("key1", {"data": "value1"})
    cache.set("key2", {"data": "value2"})
    cache.set("key3", {"data": "value3"})

    # Access key1 (moves to most recently used)
    cache.get("key1")

    # Add key4 - should evict key2 (now least recently used)
    cache.set("key4", {"data": "value4"})

    assert cache.get("key1") is not None  # Not evicted
    assert cache.get("key2") is None  # Evicted
    assert cache.get("key3") is not None
    assert cache.get("key4") is not None


def test_cache_ttl_expiration():
    """Test TTL expiration."""
    cache = CacheManager(max_size=10, ttl=1)  # 1 second TTL

    cache.set("key1", {"data": "value1"})

    # Immediately should exist
    result = cache.get("key1")
    assert result is not None

    # Wait for expiration
    time.sleep(1.2)

    # Should be expired
    result = cache.get("key1")
    assert result is None

    stats = cache.get_stats()
    assert stats["expirations"] == 1


def test_cache_clear():
    """Test cache clear operation."""
    cache = CacheManager(max_size=10, ttl=3600)

    cache.set("key1", {"data": "value1"})
    cache.set("key2", {"data": "value2"})

    assert cache.get_stats()["size"] == 2

    cache.clear()

    assert cache.get_stats()["size"] == 0
    assert cache.get("key1") is None
    assert cache.get("key2") is None


def test_cache_delete():
    """Test deleting specific cache entry."""
    cache = CacheManager(max_size=10, ttl=3600)

    cache.set("key1", {"data": "value1"})
    assert cache.get("key1") is not None

    deleted = cache.delete("key1")
    assert deleted is True
    assert cache.get("key1") is None

    # Try deleting non-existent key
    deleted = cache.delete("nonexistent")
    assert deleted is False


def test_cache_stats():
    """Test cache statistics tracking."""
    cache = CacheManager(max_size=10, ttl=3600)

    cache.set("key1", {"data": "value1"})

    # Generate hits and misses
    cache.get("key1")  # Hit
    cache.get("key1")  # Hit
    cache.get("key2")  # Miss

    stats = cache.get_stats()
    assert stats["hits"] == 2
    assert stats["misses"] == 1
    assert stats["hit_rate"] == pytest.approx(66.67, rel=0.1)


def test_cache_cleanup_expired():
    """Test manual cleanup of expired entries."""
    cache = CacheManager(max_size=10, ttl=1)

    cache.set("key1", {"data": "value1"})
    cache.set("key2", {"data": "value2"})

    time.sleep(1.2)

    expired_count = cache.cleanup_expired()
    assert expired_count == 2
    assert cache.get_stats()["size"] == 0


# ==================== PROMPT BUILDER TESTS ====================

def test_prompt_building():
    """Test prompt generation with cart items."""
    cart_items = [
    {
            "name": "Ibuprofeno 600mg",
        "category": "Analgésicos",
        "active_ingredient": "Ibuprofeno",
        "price": 4.95
    }
    ]

    prompt = PromptBuilder.build_recommendation_prompt(cart_items)

    assert "Ibuprofeno 600mg" in prompt
    assert "Analgésicos" in prompt
    assert "Ibuprofeno" in prompt
    assert "4.95" in prompt
    assert "CARRITO ACTUAL" in prompt


def test_prompt_empty_cart():
    """Test prompt with empty cart."""
    prompt = PromptBuilder.build_recommendation_prompt([])
    assert "vacío" in prompt.lower()


def test_parse_clean_json():
    """Test parsing clean JSON response."""
    response = '''
    {
    "recommendations": [
            {
                "product_name": "Omeprazol 20mg",
            "category": "Digestivos",
            "reason": "Protección gástrica",
            "priority": "high",
            "estimated_price": "8.50"
        }
    ],
    "analysis": "Carrito con analgésicos"
    }
    '''

    result = PromptBuilder.parse_recommendations(response)

    assert result is not None
    assert "recommendations" in result
    assert len(result["recommendations"]) == 1
    assert result["recommendations"][0]["product_name"] == "Omeprazol 20mg"


def test_parse_json_in_markdown():
    """Test parsing JSON embedded in markdown."""
    response = '''
    Here are my recommendations:

    ```json
    {
    "recommendations": [
            {
                "product_name": "Probióticos",
            "category": "Digestivos",
            "reason": "Flora intestinal",
            "priority": "medium",
            "estimated_price": "12.95"
        }
    ],
    "analysis": "Productos complementarios"
    }
    ```
    '''

    result = PromptBuilder.parse_recommendations(response)

    assert result is not None
    assert "recommendations" in result
    assert result["recommendations"][0]["product_name"] == "Probióticos"


def test_parse_json_embedded_in_text():
    """Test parsing JSON embedded in plain text."""
    response = '''
    Based on your cart, I recommend:
    {"recommendations": [{"product_name": "Test Product", "category": "Test", "reason": "Test reason", "priority": "low", "estimated_price": "5.00"}], "analysis": "Test analysis"}
    These are my suggestions.
    '''

    result = PromptBuilder.parse_recommendations(response)

    assert result is not None
    assert "recommendations" in result


def test_parse_invalid_json():
    """Test parsing invalid JSON returns None."""
    response = "This is not JSON at all"

    result = PromptBuilder.parse_recommendations(response)

    assert result is None


def test_validate_recommendations():
    """Test recommendation validation."""
    builder = PromptBuilder()

    # Valid recommendations
    valid_data = {
    "recommendations": [
            {
                "product_name": "Test",
            "category": "Test",
            "reason": "Test",
            "priority": "high"
        }
    ]
    }
    assert builder.validate_recommendations(valid_data) is True

    # Missing required field
    invalid_data = {
    "recommendations": [
            {
                "product_name": "Test",
            "category": "Test",
            # Missing 'reason' and 'priority'
        }
    ]
    }
    assert builder.validate_recommendations(invalid_data) is False

    # Invalid priority
    invalid_priority = {
    "recommendations": [
            {
                "product_name": "Test",
            "category": "Test",
            "reason": "Test",
            "priority": "invalid"  # Not high/medium/low
        }
    ]
    }
    assert builder.validate_recommendations(invalid_priority) is False


# ==================== CLAUDE CLIENT TESTS ====================

@pytest.fixture
def mock_cache():
    """Fixture for mock cache manager."""
    return CacheManager(max_size=10, ttl=3600)


@pytest.fixture
def mock_anthropic_response():
    """Fixture for mock Anthropic API response."""
    mock_response = Mock()
    mock_response.content = [
        Mock(text=json.dumps({
            "recommendations": [
                {
                    "product_name": "Omeprazol 20mg",
                "category": "Digestivos",
                "reason": "Protector gástrico con AINE",
                "priority": "high",
                "estimated_price": "8.50"
            }
        ],
        "analysis": "Carrito con antiinflamatorios"
    }))
    ]
    return mock_response


def test_cart_hash_generation(mock_cache):
    """Test cart hash generation is consistent."""
    client = ClaudeClient(mock_cache, api_key='test-key')

    cart1 = [
    {"name": "A", "category": "C1", "active_ingredient": "I1", "price": 5.0}
    ]
    cart2 = [
    {"name": "A", "category": "C1", "active_ingredient": "I1", "price": 5.0}
    ]

    hash1 = client._generate_cart_hash(cart1)
    hash2 = client._generate_cart_hash(cart2)

    assert hash1 == hash2
    assert len(hash1) == 32  # MD5 hash length


def test_cart_hash_order_independence(mock_cache):
    """Test hash is same regardless of cart item order."""
    client = ClaudeClient(mock_cache, api_key='test-key')

    cart1 = [
    {"name": "A", "category": "C1", "active_ingredient": "I1", "price": 5.0},
    {"name": "B", "category": "C2", "active_ingredient": "I2", "price": 10.0}
    ]
    cart2 = [
    {"name": "B", "category": "C2", "active_ingredient": "I2", "price": 10.0},
    {"name": "A", "category": "C1", "active_ingredient": "I1", "price": 5.0}
    ]

    hash1 = client._generate_cart_hash(cart1)
    hash2 = client._generate_cart_hash(cart2)

    assert hash1 == hash2


@patch('raspberry_app.api.claude_client.Anthropic')
def test_cache_hit(mock_anthropic_class, mock_cache, mock_anthropic_response):
    """Test that second call uses cache."""
    # Setup mock
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_anthropic_response
    mock_anthropic_class.return_value = mock_client

    client = ClaudeClient(mock_cache, api_key='test-key')

    cart = [
    {"name": "Ibuprofeno", "category": "Analgésicos",
     "active_ingredient": "Ibuprofeno", "price": 4.95}
    ]

    # First call - should hit API
    result1 = client.get_recommendations(cart)
    assert result1 is not None
    assert result1["source"] == "api"

    # Second call - should use cache
    result2 = client.get_recommendations(cart)
    assert result2 is not None
    assert result2["source"] == "cache"

    # Verify API was only called once
    assert mock_client.messages.create.call_count == 1


@patch('raspberry_app.api.claude_client.Anthropic')
def test_cache_miss_different_cart(mock_anthropic_class, mock_cache, mock_anthropic_response):
    """Test different carts generate different hashes."""
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_anthropic_response
    mock_anthropic_class.return_value = mock_client

    client = ClaudeClient(mock_cache, api_key="test-key")

    cart1 = [{"name": "A", "category": "C1", "active_ingredient": "I1", "price": 5.0}]
    cart2 = [{"name": "B", "category": "C2", "active_ingredient": "I2", "price": 10.0}]

    # Both should hit API (different carts)
    result1 = client.get_recommendations(cart1)
    result2 = client.get_recommendations(cart2)

    assert result1["source"] == "api"
    assert result2["source"] == "api"
    assert mock_client.messages.create.call_count == 2


@patch('raspberry_app.api.claude_client.Anthropic')
def test_force_refresh(mock_anthropic_class, mock_cache, mock_anthropic_response):
    """Test force_refresh bypasses cache."""
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_anthropic_response
    mock_anthropic_class.return_value = mock_client

    client = ClaudeClient(mock_cache, api_key="test-key")

    cart = [{"name": "A", "category": "C1", "active_ingredient": "I1", "price": 5.0}]

    # First call
    client.get_recommendations(cart)

    # Force refresh should bypass cache
    result = client.get_recommendations(cart, force_refresh=True)

    assert result["source"] == "api"
    assert mock_client.messages.create.call_count == 2


@patch('raspberry_app.api.claude_client.Anthropic')
def test_api_error_handling(mock_anthropic_class, mock_cache):
    """Test API error handling."""
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = Exception("API Error")
    mock_anthropic_class.return_value = mock_client

    client = ClaudeClient(mock_cache, api_key="test-key")

    cart = [{"name": "A", "category": "C1", "active_ingredient": "I1", "price": 5.0}]

    result = client.get_recommendations(cart)

    assert result is None
    assert client.api_errors > 0


def test_empty_cart(mock_cache):
    """Test handling of empty cart."""
    client = ClaudeClient(mock_cache, api_key="test-key")

    result = client.get_recommendations([])

    assert result is None


def test_client_stats(mock_cache):
    """Test client statistics tracking."""
    client = ClaudeClient(mock_cache, api_key="test-key")

    stats = client.get_stats()

    assert "api_calls" in stats
    assert "api_errors" in stats
    assert "cache_hits" in stats
    assert "cache_stats" in stats


def test_clear_cache_method(mock_cache):
    """Test clear cache method."""
    client = ClaudeClient(mock_cache, api_key="test-key")

    # Add something to cache
    mock_cache.set("test", {"data": "value"})
    assert mock_cache.get("test") is not None

    # Clear cache
    client.clear_cache()

    assert mock_cache.get("test") is None


# ==================== INTEGRATION TESTS ====================

@patch('raspberry_app.api.claude_client.Anthropic')
def test_full_workflow(mock_anthropic_class, mock_anthropic_response):
    """Test complete workflow: cart → hash → API → parse → cache."""
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_anthropic_response
    mock_anthropic_class.return_value = mock_client

    cache = CacheManager(max_size=100, ttl=3600)
    client = ClaudeClient(cache, api_key="test-key")

    cart = [
            {
                "name": "Ibuprofeno 600mg",
            "category": "Analgésicos",
            "active_ingredient": "Ibuprofeno",
            "price": 4.95
        }
    ]

    # First call
    result = client.get_recommendations(cart)

    assert result is not None
    assert result["source"] == "api"
    assert "recommendations" in result
    assert len(result["recommendations"]) > 0
    assert "cart_hash" in result
    assert "timestamp" in result

    # Second call should hit cache
    result2 = client.get_recommendations(cart)
    assert result2["source"] == "cache"

    # Stats should reflect one API call and one cache hit
    stats = client.get_stats()
    assert stats["api_calls"] == 1
    assert stats["cache_hits"] == 1


# ==================== PERFORMANCE TESTS ====================

def test_cache_performance():
    """Test cache operations are fast."""
    cache = CacheManager(max_size=1000, ttl=3600)

    # Benchmark set operations
    start = time.time()
    for i in range(1000):
        cache.set(f"key{i}", {"data": f"value{i}"})
    set_time = time.time() - start

    # Benchmark get operations
    start = time.time()
    for i in range(1000):
        cache.get(f"key{i}")
    get_time = time.time() - start

    # Should be very fast (< 100ms for 1000 ops)
    assert set_time < 0.1
    assert get_time < 0.1


def test_hash_generation_performance(mock_cache):
    """Test hash generation is fast."""
    client = ClaudeClient(mock_cache, api_key="test-key")

    cart = [
            {"name": f"Product{i}", "category": "Cat", "active_ingredient": "Ing", "price": 10.0}
            for i in range(10)
    ]

    start = time.time()
    for _ in range(1000):
            client._generate_cart_hash(cart)
    elapsed = time.time() - start

    # Should generate 1000 hashes in < 100ms
    assert elapsed < 0.1
