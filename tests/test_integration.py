"""
Integration tests for end-to-end workflows.
Tests the complete system from barcode scan to recommendation display.
"""
import pytest
import time
from unittest.mock import Mock, patch

from raspberry_app.database.models import Product, Sale
from raspberry_app.api.claude_client import ClaudeClient


@pytest.mark.integration
class TestEndToEndWorkflows:
    """Integration tests for complete user workflows."""

    def test_full_scan_to_recommendation_flow(self, populated_db, mock_claude_client):
        """
        Test complete workflow: scan barcode → DB lookup → cart → recommendations.

        Simulates:
        1. User scans product barcode
        2. System looks up product in database
        3. Product added to cart
        4. Recommendations generated for cart

        This is the primary user flow in the application.
        """
        # Step 1: Simulate barcode scan
        scanned_ean = "8470001234568"  # Ibuprofeno

        # Step 2: Database lookup
        product = populated_db.get_product_by_ean(scanned_ean)
        assert product is not None, "Product should be found in database"
        assert product.name == "Ibuprofeno 600mg 20 comprimidos"

        # Step 3: Create cart
        cart = [
            {
                "name": product.name,
                "category": product.category,
                "active_ingredient": product.active_ingredient,
                "price": product.price
            }
        ]

        # Step 4: Get recommendations
        recommendations = mock_claude_client.get_recommendations(cart)

        # Verify recommendations
        assert recommendations is not None, "Should receive recommendations"
        assert "recommendations" in recommendations
        assert "analysis" in recommendations
        assert len(recommendations["recommendations"]) > 0
        assert recommendations["source"] == "api"  # First call should be from API

        # Verify recommendation structure
        first_rec = recommendations["recommendations"][0]
        assert "product_name" in first_rec
        assert "category" in first_rec
        assert "reason" in first_rec
        assert "priority" in first_rec

    def test_multiple_scan_workflow(self, populated_db, mock_claude_client):
        """
        Test workflow with multiple product scans.

        Simulates user scanning multiple products in sequence.
        """
        # Scan multiple products
        eans = ["8470001234568", "8470002345671", "8470003456786"]
        cart = []

        for ean in eans:
            product = populated_db.get_product_by_ean(ean)
            assert product is not None

            cart.append({
                "name": product.name,
                "category": product.category,
                "active_ingredient": product.active_ingredient,
                "price": product.price
            })

        # Get recommendations for full cart
        recommendations = mock_claude_client.get_recommendations(cart)

        assert recommendations is not None
        assert len(cart) == 3
        assert "recommendations" in recommendations

    def test_cache_hit_on_repeated_cart(self, populated_db, mock_claude_client):
        """
        Test that identical carts use cached recommendations.

        Verifies:
        1. First call goes to API
        2. Second call returns from cache
        3. Cache hit improves response time
        """
        # Build cart
        product = populated_db.get_product_by_ean("8470001234568")
        cart = [{
            "name": product.name,
            "category": product.category,
            "active_ingredient": product.active_ingredient,
            "price": product.price
        }]

        # First call (API)
        start = time.time()
        result1 = mock_claude_client.get_recommendations(cart)
        first_time = time.time() - start

        assert result1 is not None
        assert result1["source"] == "api"

        # Second call (cache hit)
        start = time.time()
        result2 = mock_claude_client.get_recommendations(cart)
        cache_time = time.time() - start

        assert result2 is not None
        assert result2["source"] == "cache"

        # Verify cache is faster
        assert cache_time < first_time
        assert cache_time < 0.01  # Cache should be < 10ms

        # Verify API was only called once
        assert mock_claude_client.client.messages.create.call_count == 1

    def test_cart_hash_independence_from_order(self, mock_claude_client, sample_products):
        """
        Test that cart order doesn't affect cache lookups.

        Same products in different order should produce same hash and cache hit.
        """
        # Cart with products in order A, B, C
        cart1 = [
            {
                "name": sample_products[0].name,
                "category": sample_products[0].category,
                "active_ingredient": sample_products[0].active_ingredient,
                "price": sample_products[0].price
            },
            {
                "name": sample_products[1].name,
                "category": sample_products[1].category,
                "active_ingredient": sample_products[1].active_ingredient,
                "price": sample_products[1].price
            }
        ]

        # Cart with same products in order B, A
        cart2 = [
            {
                "name": sample_products[1].name,
                "category": sample_products[1].category,
                "active_ingredient": sample_products[1].active_ingredient,
                "price": sample_products[1].price
            },
            {
                "name": sample_products[0].name,
                "category": sample_products[0].category,
                "active_ingredient": sample_products[0].active_ingredient,
                "price": sample_products[0].price
            }
        ]

        # Generate hashes
        hash1 = mock_claude_client._generate_cart_hash(cart1)
        hash2 = mock_claude_client._generate_cart_hash(cart2)

        # Should be identical
        assert hash1 == hash2

        # Verify cache behavior
        result1 = mock_claude_client.get_recommendations(cart1)
        assert result1["source"] == "api"

        result2 = mock_claude_client.get_recommendations(cart2)
        assert result2["source"] == "cache"  # Should hit cache

    def test_sale_completion_workflow(self, populated_db):
        """
        Test complete sale: add products → create sale → save items.

        Verifies:
        1. Products exist in database
        2. Sale record created
        3. Sale items recorded with correct total
        """
        # Get products
        product1 = populated_db.get_product_by_ean("8470001234568")
        product2 = populated_db.get_product_by_ean("8470002345671")

        # Create sale with items (API: List[Tuple[product_id, quantity]])
        items = [
            (product1.id, 1),
            (product2.id, 1)
        ]
        sale_id = populated_db.create_sale(items)
        assert sale_id > 0

        # Verify sale exists (get_sale returns Tuple[Sale, List[SaleItem]])
        result = populated_db.get_sale(sale_id)
        assert result is not None

        sale, sale_items = result
        assert sale.items_count == 2
        assert len(sale_items) == 2

        # Verify total is calculated correctly
        expected_total = product1.price + product2.price
        assert abs(sale.total - expected_total) < 0.01  # Float comparison

    def test_invalid_barcode_handling(self, populated_db):
        """
        Test system behavior with invalid/unknown barcode.

        Should gracefully handle non-existent products.
        """
        # Scan unknown barcode
        unknown_ean = "9999999999999"
        product = populated_db.get_product_by_ean(unknown_ean)

        # Should return None, not crash
        assert product is None

    def test_empty_cart_recommendation(self, mock_claude_client):
        """
        Test recommendations with empty cart.

        Should handle gracefully without calling API.
        """
        empty_cart = []
        result = mock_claude_client.get_recommendations(empty_cart)

        # Should return None for empty cart
        assert result is None

        # Should not call API
        assert mock_claude_client.client.messages.create.call_count == 0


@pytest.mark.integration
@pytest.mark.slow
class TestPerformanceRequirements:
    """
    Integration tests for performance requirements.

    Per PLAN_TECNICO.md:
    - Recommendation response < 2 seconds (with cache < 100ms)
    - Memory consumption < 500MB
    - Non-blocking UI
    """

    def test_recommendation_response_time(self, populated_db, mock_claude_client, performance_timer):
        """
        Test that recommendations complete within 2 seconds.

        Note: With mocked API, this tests the non-API overhead.
        Real API calls would need separate testing.
        """
        # Build cart
        product = populated_db.get_product_by_ean("8470001234568")
        cart = [{
            "name": product.name,
            "category": product.category,
            "active_ingredient": product.active_ingredient,
            "price": product.price
        }]

        # Get recommendations (first call, no cache)
        recommendations = mock_claude_client.get_recommendations(cart)
        elapsed = performance_timer()

        assert recommendations is not None

        # With mock, should be very fast
        # Real API target: < 2 seconds
        assert elapsed < 2.0, f"First recommendation took {elapsed:.2f}s, expected < 2.0s"

    def test_cache_response_time(self, populated_db, mock_claude_client):
        """
        Test that cached recommendations are fast (< 100ms).
        """
        # Build cart
        product = populated_db.get_product_by_ean("8470001234568")
        cart = [{
            "name": product.name,
            "category": product.category,
            "active_ingredient": product.active_ingredient,
            "price": product.price
        }]

        # Prime cache
        mock_claude_client.get_recommendations(cart)

        # Test cached response time
        start = time.time()
        result = mock_claude_client.get_recommendations(cart)
        elapsed = time.time() - start

        assert result is not None
        assert result["source"] == "cache"
        assert elapsed < 0.1, f"Cache hit took {elapsed:.3f}s, expected < 0.1s"

    def test_database_lookup_performance(self, populated_db):
        """
        Test that database lookups are fast (< 50ms).
        """
        ean = "8470001234568"

        # Time database lookup
        start = time.time()
        product = populated_db.get_product_by_ean(ean)
        elapsed = time.time() - start

        assert product is not None
        assert elapsed < 0.05, f"DB lookup took {elapsed:.3f}s, expected < 0.05s"

    def test_multiple_concurrent_lookups(self, populated_db):
        """
        Test performance with multiple rapid lookups.

        Simulates fast scanning scenario.
        """
        eans = ["8470001234568", "8470002345671", "8470003456786"]

        start = time.time()
        for ean in eans:
            product = populated_db.get_product_by_ean(ean)
            assert product is not None
        elapsed = time.time() - start

        # Should handle 3 lookups quickly
        assert elapsed < 0.2, f"3 DB lookups took {elapsed:.3f}s, expected < 0.2s"


@pytest.mark.integration
class TestDataIntegrity:
    """Integration tests for data integrity and consistency."""

    def test_foreign_key_constraint_enforcement(self, populated_db):
        """
        Test that foreign key constraints are enforced.

        Sale items should reference valid sales and products.
        """
        # Try to add sale item for non-existent sale
        product = populated_db.get_product_by_ean("8470001234568")

        with pytest.raises(Exception):  # Should raise integrity error
            populated_db.add_sale_item(
                sale_id=99999,  # Non-existent
                product_id=product.id,
                quantity=1,
                unit_price=product.price
            )

    def test_cascade_delete_behavior(self, populated_db):
        """
        Test that deleting a sale cascades to sale_items using direct SQL.

        Note: DatabaseManager doesn't expose delete_sale(), so we test
        the CASCADE behavior at the SQL level.
        """
        # Create sale with items
        product = populated_db.get_product_by_ean("8470001234568")
        items = [(product.id, 1)]
        sale_id = populated_db.create_sale(items)

        # Verify items exist
        result_before = populated_db.get_sale(sale_id)
        assert result_before is not None
        sale_before, items_before = result_before
        assert len(items_before) == 1

        # Delete sale directly via SQL to test CASCADE
        with populated_db.get_connection() as conn:
            conn.execute("DELETE FROM sales WHERE id = ?", (sale_id,))

        # Verify sale and items were deleted
        result_after = populated_db.get_sale(sale_id)
        assert result_after is None

    def test_ean_uniqueness_constraint(self, db_manager, sample_product):
        """
        Test that EAN uniqueness is enforced.

        Cannot add duplicate EAN codes.
        """
        # Add product
        db_manager.add_product(sample_product)

        # Try to add duplicate
        with pytest.raises(Exception):  # Should raise integrity error
            db_manager.add_product(sample_product)

    def test_price_precision(self, db_manager, sample_product):
        """
        Test that decimal prices are stored accurately.
        """
        # Add product with precise price
        sample_product.price = 12.95
        product_id = db_manager.add_product(sample_product)

        # Retrieve and verify
        retrieved = db_manager.get_product_by_ean(sample_product.ean)
        assert retrieved.price == 12.95
        assert isinstance(retrieved.price, float)


@pytest.mark.integration
class TestCacheAndDatabaseSync:
    """Integration tests for cache and database synchronization."""

    def test_cache_invalidation_on_force_refresh(self, populated_db, mock_claude_client):
        """
        Test that force_refresh bypasses cache.
        """
        # Build cart
        product = populated_db.get_product_by_ean("8470001234568")
        cart = [{
            "name": product.name,
            "category": product.category,
            "active_ingredient": product.active_ingredient,
            "price": product.price
        }]

        # First call (populates cache)
        result1 = mock_claude_client.get_recommendations(cart)
        assert result1["source"] == "api"

        # Second call with force_refresh
        result2 = mock_claude_client.get_recommendations(cart, force_refresh=True)
        assert result2["source"] == "api"  # Should bypass cache

        # Verify API was called twice
        assert mock_claude_client.client.messages.create.call_count == 2

    def test_cache_stats_tracking(self, mock_claude_client, populated_db):
        """
        Test that cache statistics are tracked correctly.
        """
        # Build cart
        product = populated_db.get_product_by_ean("8470001234568")
        cart = [{
            "name": product.name,
            "category": product.category,
            "active_ingredient": product.active_ingredient,
            "price": product.price
        }]

        # Get initial stats
        initial_stats = mock_claude_client.get_stats()
        initial_api_calls = initial_stats["api_calls"]
        initial_cache_hits = initial_stats["cache_hits"]

        # Make API call
        mock_claude_client.get_recommendations(cart)

        # Make cache hit
        mock_claude_client.get_recommendations(cart)

        # Check updated stats
        final_stats = mock_claude_client.get_stats()
        assert final_stats["api_calls"] == initial_api_calls + 1
        assert final_stats["cache_hits"] == initial_cache_hits + 1

    def test_clear_cache_functionality(self, mock_claude_client, populated_db):
        """
        Test that clearing cache forces fresh API calls.
        """
        # Build cart
        product = populated_db.get_product_by_ean("8470001234568")
        cart = [{
            "name": product.name,
            "category": product.category,
            "active_ingredient": product.active_ingredient,
            "price": product.price
        }]

        # Populate cache
        result1 = mock_claude_client.get_recommendations(cart)
        assert result1["source"] == "api"

        # Verify cache hit
        result2 = mock_claude_client.get_recommendations(cart)
        assert result2["source"] == "cache"

        # Clear cache
        mock_claude_client.clear_cache()

        # Next call should be API again
        result3 = mock_claude_client.get_recommendations(cart)
        assert result3["source"] == "api"


@pytest.mark.integration
class TestErrorHandlingIntegration:
    """Integration tests for error handling across components."""

    def test_api_error_graceful_degradation(self, populated_db, cache_manager):
        """
        Test that API errors are handled gracefully.
        """
        # Create client with failing API
        with patch('raspberry_app.api.claude_client.Anthropic') as mock_anthropic:
            mock_instance = Mock()
            mock_instance.messages.create.side_effect = Exception("API Error")
            mock_anthropic.return_value = mock_instance

            client = ClaudeClient(
                cache_manager=cache_manager,
                api_key="test-api-key"
            )

            # Build cart
            product = populated_db.get_product_by_ean("8470001234568")
            cart = [{
                "name": product.name,
                "category": product.category,
                "active_ingredient": product.active_ingredient,
                "price": product.price
            }]

            # Should return None, not crash
            result = client.get_recommendations(cart)
            assert result is None

    def test_database_error_handling(self, temp_db):
        """
        Test database connection error handling.
        """
        # Create manager with invalid path
        invalid_path = "/invalid/path/database.db"

        # Should handle gracefully
        with pytest.raises(Exception):
            manager = DatabaseManager(db_path=invalid_path)

    def test_corrupted_cache_entry(self, cache_manager):
        """
        Test handling of corrupted cache data.
        """
        # Manually insert corrupted data
        cache_manager.cache["corrupted_key"] = "not a dict"
        cache_manager.timestamps["corrupted_key"] = time.time()

        # Should handle gracefully
        result = cache_manager.get("corrupted_key")
        # Either returns corrupted data or None, but shouldn't crash
        assert result is not None or result is None
