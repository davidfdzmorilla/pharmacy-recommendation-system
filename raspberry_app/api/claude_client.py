"""
Claude API client with integrated caching.
Handles recommendation requests with intelligent caching and error handling.
"""
import hashlib
import json
import re
import time
from typing import List, Dict, Optional
from anthropic import Anthropic, APIError, APITimeoutError, APIConnectionError
from raspberry_app.api.cache_manager import CacheManager
from raspberry_app.api.prompt_builder import PromptBuilder
from raspberry_app.database.db_manager import DatabaseManager
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

    # List of active ingredients that ALWAYS require prescription in Spain
    # Based on Real Decreto 1345/2007 and subsequent updates
    # This provides a safety layer independent of database classification
    PRESCRIPTION_ACTIVE_INGREDIENTS = {
        # Antibiotics
        'amoxicilina', 'azitromicina', 'ciprofloxacino', 'levofloxacino',
        'ácido fusídico', 'sulfadiazina', 'fusídico', 'argéntica',

        # High-potency NSAIDs
        'metamizol', 'nolotil', 'dexketoprofeno', 'enantyum',
        'diclofenaco', 'voltadol',

        # Opioids
        'codeína', 'tramadol', 'fentanilo', 'codeina',

        # Antiemetics and digestive
        'metoclopramida', 'primperan', 'domperidona',

        # New-generation antihistamines
        'desloratadina', 'aerius', 'bilastina', 'bilaxten',

        # Respiratory
        'bromhexina', 'cloperastina', 'dextrometorfano',

        # Others
        'flurbiprofeno', 'nafazolina'
    }

    # Regex patterns for prescription medications (dose-dependent)
    PRESCRIPTION_NAME_PATTERNS = {
        r'omeprazol.*2[4-9].*(?:cápsulas|comprimidos)': 'PPI long-term (>14 days)',
        r'omeprazol.*3\d.*(?:cápsulas|comprimidos)': 'PPI long-term (>14 days)',
        r'ibuprofeno.*(600|800)\s*mg': 'Ibuprofeno high dose (>400mg)',
        r'loperamida.*[2-9]\s*mg': 'Loperamida prescription strength',
        r'diclofenaco.*(?:75|100)\s*mg': 'Diclofenaco high dose'
    }

    def __init__(
        self,
        cache_manager: Optional[CacheManager] = None,
        api_key: Optional[str] = None,
        db_manager: Optional[DatabaseManager] = None
    ):
        """
        Initialize Claude API client.

        Args:
            cache_manager: CacheManager instance. If None, creates new one.
            api_key: Optional API key override (mainly for testing).
                    If None, uses config.ANTHROPIC_API_KEY.
            db_manager: DatabaseManager for prescription validation. If None, creates new one.
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
        self.db_manager = db_manager or DatabaseManager(db_path=config.DB_PATH)

        # Stats
        self.api_calls = 0
        self.api_errors = 0
        self.cache_hits = 0
        self.prescription_filtered = 0  # Track how many prescription meds filtered

        # Build system prompt with dynamic OTC catalog
        self._system_prompt = self._build_system_prompt()

        self.logger.info(
            f"ClaudeClient initialized: model={config.CLAUDE_MODEL}, "
            f"cache={'enabled' if config.CACHE_ENABLED else 'disabled'}"
        )

    def _get_otc_products(self) -> List[Dict]:
        """
        Fetch OTC products from database for catalog generation.

        Returns:
            List of dicts with 'name' and 'category' keys for each OTC product

        Example:
            >>> otc_products = client._get_otc_products()
            >>> len(otc_products)
            83
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT name, category
                    FROM products
                    WHERE requires_prescription = 0
                    ORDER BY category, name
                """)
                products = [
                    {"name": row["name"], "category": row["category"]}
                    for row in cursor.fetchall()
                ]

                self.logger.debug(f"Fetched {len(products)} OTC products from database")
                return products

        except Exception as e:
            self.logger.error(f"Error fetching OTC products: {e}")
            return []

    def _build_system_prompt(self) -> str:
        """
        Build system prompt with dynamic OTC catalog from database.

        Returns:
            Complete system prompt with injected OTC catalog

        Example:
            >>> prompt = client._build_system_prompt()
            >>> '{OTC_CATALOG}' not in prompt
            True
        """
        # Fetch OTC products from database
        otc_products = self._get_otc_products()

        # Generate catalog text
        catalog = self.prompt_builder.generate_otc_catalog(otc_products)

        # Replace placeholder with actual catalog
        system_prompt = self.prompt_builder.SYSTEM_PROMPT.replace("{OTC_CATALOG}", catalog)

        self.logger.info(
            f"Built system prompt with {len(otc_products)} OTC products "
            f"({len(system_prompt)} chars)"
        )

        return system_prompt

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

            # CRITICAL: Filter out prescription medications
            filtered_recommendations = self._filter_prescription_products(
                recommendations['recommendations']
            )

            if not filtered_recommendations:
                self.logger.warning("All recommendations were prescription products - returning None")
                return None

            # Update recommendations with filtered list
            recommendations['recommendations'] = filtered_recommendations

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
                f"Successfully generated {len(filtered_recommendations)} "
                f"OTC recommendations for cart {cart_hash[:8]}"
            )

            return result

        except Exception as e:
            self.logger.error(f"Error getting recommendations: {e}")
            self.api_errors += 1
            return None

    def _filter_prescription_products(self, recommendations: List[Dict]) -> List[Dict]:
        """
        Filter out prescription medications from recommendations.

        Uses database lookup to verify each recommended product is OTC.
        This provides a safety layer in addition to prompt engineering.

        Args:
            recommendations: List of recommendation dicts from API

        Returns:
            Filtered list containing only OTC products

        Example:
            >>> recs = [
            ...     {"product_name": "Omeprazol 20mg", ...},  # Prescription
            ...     {"product_name": "Almax 1g", ...}          # OTC
            ... ]
            >>> filtered = client._filter_prescription_products(recs)
            >>> len(filtered)
            1
        """
        if not recommendations:
            return []

        filtered = []

        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()

            for rec in recommendations:
                product_name = rec.get('product_name', '')

                if not product_name:
                    self.logger.warning("Recommendation missing product_name, skipping")
                    continue

                # LAYER 1: Hardcoded validation of active ingredients
                # This provides safety independent of database classification
                product_lower = product_name.lower()
                blocked_by_ingredient = False

                for ingredient in self.PRESCRIPTION_ACTIVE_INGREDIENTS:
                    if ingredient in product_lower:
                        self.prescription_filtered += 1
                        self.logger.warning(
                            f"🔴 FILTERED by active ingredient: {product_name} "
                            f"(contains: {ingredient})"
                        )
                        blocked_by_ingredient = True
                        break

                if blocked_by_ingredient:
                    continue

                # LAYER 2: Pattern-based validation (dose-dependent prescriptions)
                blocked_by_pattern = False

                for pattern, reason in self.PRESCRIPTION_NAME_PATTERNS.items():
                    if re.search(pattern, product_lower):
                        self.prescription_filtered += 1
                        self.logger.warning(
                            f"🔴 FILTERED by pattern: {product_name} ({reason})"
                        )
                        blocked_by_pattern = True
                        break

                if blocked_by_pattern:
                    continue

                # LAYER 3: Database lookup validation (fuzzy search)
                # Checks if product exists in catalog and its prescription status
                # Uses LIKE for partial matching (e.g., "Omeprazol" matches "Omeprazol 20mg 28 cápsulas")
                # ORDER BY ensures deterministic results (prioritize prescription detection)
                cursor.execute("""
                    SELECT name, requires_prescription
                    FROM products
                    WHERE name LIKE ? OR ? LIKE '%' || name || '%'
                    ORDER BY
                        requires_prescription DESC,  -- Prioritize prescriptions (conservative approach)
                        LENGTH(name) ASC,             -- Prefer shorter/more specific matches
                        name ASC                      -- Alphabetical for consistency
                    LIMIT 1
                """, (f"%{product_name}%", product_name))

                result = cursor.fetchone()

                if result:
                    db_name = result['name']
                    requires_rx = bool(result['requires_prescription'])

                    if requires_rx:
                        # BLOCK: Product requires prescription
                        self.prescription_filtered += 1
                        self.logger.warning(
                            f"🔴 FILTERED prescription product: {product_name} "
                            f"(matched: {db_name})"
                        )
                        continue
                    else:
                        # ALLOW: Product is OTC
                        self.logger.debug(f"✅ Approved OTC product: {product_name}")
                        filtered.append(rec)
                else:
                    # Product not found in DB - BLOCK for safety
                    # ONLY recommend products explicitly verified in our catalog
                    # This is critical for Spanish legal compliance (Real Decreto 1345/2007)
                    self.prescription_filtered += 1
                    self.logger.error(
                        f"🔴 BLOCKED unknown product: {product_name} "
                        f"(not in catalog - requires manual verification before recommendation)"
                    )
                    # Do NOT add to filtered list - product is blocked
                    continue

        if self.prescription_filtered > 0:
            self.logger.info(
                f"Filtered {self.prescription_filtered} prescription products "
                f"from recommendations"
            )

        return filtered

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
                    system=self._system_prompt,
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
                - prescription_filtered: Number of prescription products filtered
                - cache_stats: Cache manager statistics

        Example:
            >>> stats = client.get_stats()
            >>> print(f"API calls: {stats['api_calls']}")
            >>> print(f"Prescription filtered: {stats['prescription_filtered']}")
            >>> print(f"Cache hit rate: {stats['cache_stats']['hit_rate']:.1f}%")
        """
        return {
            "api_calls": self.api_calls,
            "api_errors": self.api_errors,
            "cache_hits": self.cache_hits,
            "prescription_filtered": self.prescription_filtered,
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
