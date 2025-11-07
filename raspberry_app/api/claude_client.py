"""
Claude API client with integrated caching.
Handles recommendation requests with intelligent caching and error handling.
"""
import hashlib
import json
import time
from typing import List, Dict, Optional
from anthropic import Anthropic, APIError, APITimeoutError, APIConnectionError
from raspberry_app.api.cache_manager import CacheManager
from raspberry_app.api.prompt_builder import PromptBuilder
from raspberry_app.config import config
from raspberry_app.utils.logger import LoggerMixin


class ClaudeClient(LoggerMixin):
    """
    Client for Anthropic Claude API with integrated caching.

    Features:
    - Cart-based recommendation generation
    - Intelligent LRU+TTL caching
    - Automatic retries with exponential backoff
    - Comprehensive error handling
    - Request logging for monitoring

    Example:
        >>> from raspberry_app.api.cache_manager import CacheManager
        >>> cache = CacheManager()
        >>> client = ClaudeClient(cache)
        >>> cart = [{"name": "Ibuprofeno", "category": "Analgésicos", ...}]
        >>> recommendations = client.get_recommendations(cart)
    """

    def __init__(
        self,
        cache_manager: Optional[CacheManager] = None,
        api_key: Optional[str] = None
    ):
        """
        Initialize Claude API client.

        Args:
            cache_manager: CacheManager instance. If None, creates new one.
            api_key: Optional API key override (mainly for testing).
                    If None, uses config.ANTHROPIC_API_KEY.
        """
        # Get API key (test override or config)
        api_key = api_key or config.ANTHROPIC_API_KEY

        # Validate API key
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY not configured. "
                "Set it in your .env file or environment."
            )

        self.client = Anthropic(api_key=api_key)
        self.cache_manager = cache_manager or CacheManager(
            max_size=config.CACHE_MAX_SIZE,
            ttl=config.CACHE_TTL
        )
        self.prompt_builder = PromptBuilder()

        # Stats
        self.api_calls = 0
        self.api_errors = 0
        self.cache_hits = 0

        self.logger.info(
            f"ClaudeClient initialized: model={config.CLAUDE_MODEL}, "
            f"cache={'enabled' if config.CACHE_ENABLED else 'disabled'}"
        )

    def get_recommendations(
        self,
        cart_items: List[Dict],
        force_refresh: bool = False
    ) -> Optional[Dict]:
        """
        Get product recommendations for cart.

        Workflow:
        1. Generate cart hash
        2. Check cache (unless force_refresh)
        3. If cache miss, call Claude API
        4. Parse and validate response
        5. Store in cache
        6. Return recommendations

        Args:
            cart_items: List of products in cart, each with:
                - name: Product name
                - category: Product category
                - active_ingredient: Active ingredient
                - price: Product price
            force_refresh: Skip cache and force API call

        Returns:
            Dict with:
                - recommendations: List of recommended products
                - analysis: Overall analysis of cart
                - source: "cache" or "api"
                - timestamp: When recommendation was generated
            Returns None if API call fails

        Example:
            >>> cart = [
            ...     {
            ...         "name": "Ibuprofeno 600mg",
            ...         "category": "Analgésicos",
            ...         "active_ingredient": "Ibuprofeno",
            ...         "price": 4.95
            ...     }
            ... ]
            >>> result = client.get_recommendations(cart)
            >>> if result:
            ...     print(f"Got {len(result['recommendations'])} recommendations")
            ...     print(f"Source: {result['source']}")
        """
        if not cart_items:
            self.logger.warning("Empty cart provided")
            return None

        # Generate cart hash for caching
        cart_hash = self._generate_cart_hash(cart_items)
        self.logger.info(f"Processing cart: {len(cart_items)} items, hash={cart_hash[:8]}...")

        # Check cache (unless force refresh)
        if config.CACHE_ENABLED and not force_refresh:
            cached = self.cache_manager.get(cart_hash)
            if cached:
                self.cache_hits += 1
                self.logger.info(f"Cache hit for cart {cart_hash[:8]}")
                cached["source"] = "cache"
                return cached

            self.logger.debug(f"Cache miss for cart {cart_hash[:8]}")

        # Build prompt
        user_prompt = self.prompt_builder.build_recommendation_prompt(cart_items)

        # Call API
        try:
            response_text = self._call_api(user_prompt)
            if not response_text:
                return None

            # Parse response
            recommendations = self.prompt_builder.parse_recommendations(response_text)
            if not recommendations:
                self.logger.error("Failed to parse API response")
                return None

            # Validate recommendations
            if not self.prompt_builder.validate_recommendations(recommendations):
                self.logger.error("Invalid recommendations structure")
                return None

            # Add metadata
            result = {
                **recommendations,
                "source": "api",
                "timestamp": time.time(),
                "cart_hash": cart_hash
            }

            # Store in cache
            if config.CACHE_ENABLED:
                self.cache_manager.set(cart_hash, result)
                self.logger.info(f"Stored recommendations in cache: {cart_hash[:8]}")

            self.logger.info(
                f"Successfully generated {len(recommendations['recommendations'])} "
                f"recommendations for cart {cart_hash[:8]}"
            )

            return result

        except Exception as e:
            self.logger.error(f"Error getting recommendations: {e}")
            self.api_errors += 1
            return None

    def _generate_cart_hash(self, cart_items: List[Dict]) -> str:
        """
        Generate unique hash for cart contents.

        Hash is based on:
        - Product names (sorted)
        - Categories (sorted)
        - Active ingredients (sorted)

        This ensures same cart contents always produce same hash,
        regardless of item order.

        Args:
            cart_items: List of cart products

        Returns:
            MD5 hash string (32 chars hex)

        Example:
            >>> cart1 = [{"name": "A", "category": "C1", "active_ingredient": "I1"}]
            >>> cart2 = [{"name": "A", "category": "C1", "active_ingredient": "I1"}]
            >>> hash1 = client._generate_cart_hash(cart1)
            >>> hash2 = client._generate_cart_hash(cart2)
            >>> hash1 == hash2
            True
        """
        # Extract relevant fields
        names = sorted([item.get('name', '') for item in cart_items])
        categories = sorted([item.get('category', '') for item in cart_items])
        ingredients = sorted([item.get('active_ingredient', '') for item in cart_items])

        # Create hash input string
        hash_input = json.dumps({
            "names": names,
            "categories": categories,
            "ingredients": ingredients
        }, sort_keys=True)

        # Generate MD5 hash
        return hashlib.md5(hash_input.encode('utf-8')).hexdigest()

    def _call_api(
        self,
        prompt: str,
        max_retries: int = 3,
        initial_backoff: float = 1.0
    ) -> Optional[str]:
        """
        Call Claude API with retry logic.

        Implements exponential backoff for transient failures.

        Args:
            prompt: User prompt to send to Claude
            max_retries: Maximum number of retry attempts
            initial_backoff: Initial backoff delay in seconds

        Returns:
            Response text from Claude, or None if all retries fail

        Raises:
            No exceptions - logs errors and returns None on failure
        """
        backoff = initial_backoff

        for attempt in range(max_retries):
            try:
                self.logger.debug(
                    f"API call attempt {attempt + 1}/{max_retries}: "
                    f"model={config.CLAUDE_MODEL}, tokens={config.MAX_TOKENS}"
                )

                start_time = time.time()

                # Call Anthropic API
                response = self.client.messages.create(
                    model=config.CLAUDE_MODEL,
                    max_tokens=config.MAX_TOKENS,
                    temperature=config.TEMPERATURE,
                    system=self.prompt_builder.SYSTEM_PROMPT,
                    messages=[
                        {"role": "user", "content": prompt}
                    ],
                    timeout=config.API_TIMEOUT
                )

                elapsed = time.time() - start_time
                self.api_calls += 1

                # Extract text from response
                response_text = response.content[0].text

                self.logger.info(
                    f"API call successful: {len(response_text)} chars, "
                    f"{elapsed:.2f}s, attempt {attempt + 1}"
                )

                return response_text

            except APITimeoutError as e:
                self.logger.warning(f"API timeout on attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    self.logger.info(f"Retrying in {backoff:.1f}s...")
                    time.sleep(backoff)
                    backoff *= 2  # Exponential backoff

            except APIConnectionError as e:
                self.logger.warning(f"API connection error on attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    self.logger.info(f"Retrying in {backoff:.1f}s...")
                    time.sleep(backoff)
                    backoff *= 2

            except APIError as e:
                self.logger.error(f"API error on attempt {attempt + 1}: {e}")
                # Don't retry on API errors (usually client errors)
                self.api_errors += 1
                return None

            except Exception as e:
                self.logger.error(f"Unexpected error on attempt {attempt + 1}: {e}")
                self.api_errors += 1
                return None

        # All retries exhausted
        self.logger.error(f"API call failed after {max_retries} attempts")
        self.api_errors += 1
        return None

    def get_stats(self) -> Dict:
        """
        Get client statistics.

        Returns:
            Dict with:
                - api_calls: Total API calls made
                - api_errors: Number of API errors
                - cache_hits: Number of cache hits
                - cache_stats: Cache manager statistics

        Example:
            >>> stats = client.get_stats()
            >>> print(f"API calls: {stats['api_calls']}")
            >>> print(f"Cache hit rate: {stats['cache_stats']['hit_rate']:.1f}%")
        """
        return {
            "api_calls": self.api_calls,
            "api_errors": self.api_errors,
            "cache_hits": self.cache_hits,
            "cache_stats": self.cache_manager.get_stats() if config.CACHE_ENABLED else {}
        }

    def clear_cache(self) -> None:
        """
        Clear all cached recommendations.

        Example:
            >>> client.clear_cache()
        """
        if config.CACHE_ENABLED:
            self.cache_manager.clear()
            self.logger.info("Cache cleared")


# Example usage
if __name__ == "__main__":
    print("=" * 60)
    print("TESTING CLAUDE CLIENT")
    print("=" * 60)

    try:
        # Initialize client
        cache = CacheManager(max_size=100, ttl=3600)
        client = ClaudeClient(cache)

        # Sample cart
        sample_cart = [
            {
                "name": "Ibuprofeno 600mg 20 comprimidos",
                "category": "Analgésicos",
                "active_ingredient": "Ibuprofeno",
                "price": 4.95
            },
            {
                "name": "Paracetamol 1g 40 comprimidos",
                "category": "Analgésicos",
                "active_ingredient": "Paracetamol",
                "price": 3.50
            }
        ]

        print("\n1. Testing cart hash generation:")
        hash1 = client._generate_cart_hash(sample_cart)
        hash2 = client._generate_cart_hash(sample_cart)
        print(f"   Hash consistency: {'✅' if hash1 == hash2 else '❌'}")
        print(f"   Hash: {hash1}")

        print("\n2. Testing API call (requires API key):")
        if config.ANTHROPIC_API_KEY:
            recommendations = client.get_recommendations(sample_cart)

            if recommendations:
                print(f"   ✅ Got recommendations")
                print(f"   - Source: {recommendations['source']}")
                print(f"   - Count: {len(recommendations['recommendations'])}")
                print(f"   - Analysis: {recommendations['analysis'][:100]}...")

                # Test cache hit
                print("\n3. Testing cache hit:")
                cached = client.get_recommendations(sample_cart)
                if cached and cached['source'] == 'cache':
                    print("   ✅ Cache hit successful")
                else:
                    print("   ❌ Cache hit failed")
            else:
                print("   ❌ Failed to get recommendations")
        else:
            print("   ⚠️  Skipped (no API key configured)")

        print("\n4. Client statistics:")
        stats = client.get_stats()
        for key, value in stats.items():
            if key != 'cache_stats':
                print(f"   {key}: {value}")

        print("\n✅ ClaudeClient testing complete")

    except ValueError as e:
        print(f"   ⚠️  {e}")
        print("   Set ANTHROPIC_API_KEY in .env to test API calls")
