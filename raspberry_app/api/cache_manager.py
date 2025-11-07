"""
LRU + TTL cache manager for API responses.
Thread-safe caching system with automatic expiration and eviction.
"""
import time
from typing import Optional, Dict, Any
from collections import OrderedDict
from threading import Lock
from raspberry_app.utils.logger import LoggerMixin


class CacheManager(LoggerMixin):
    """
    Thread-safe LRU (Least Recently Used) cache with TTL (Time To Live).

    Features:
    - LRU eviction when max_size reached
    - TTL-based expiration
    - Thread-safe operations
    - Statistics tracking (hits, misses, evictions)

    Example:
        >>> cache = CacheManager(max_size=100, ttl=3600)
        >>> cache.set("key1", {"data": "value"})
        >>> result = cache.get("key1")
        >>> stats = cache.get_stats()
    """

    def __init__(self, max_size: int = 100, ttl: int = 3600):
        """
        Initialize cache manager.

        Args:
            max_size: Maximum number of entries before LRU eviction
            ttl: Time to live in seconds (default 1 hour)
        """
        self.max_size = max_size
        self.ttl = ttl
        self.cache: OrderedDict[str, Any] = OrderedDict()
        self.timestamps: Dict[str, float] = {}
        self.lock = Lock()

        # Statistics
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        self.expirations = 0

        self.logger.info(f"CacheManager initialized: max_size={max_size}, ttl={ttl}s")

    def get(self, key: str) -> Optional[Dict]:
        """
        Retrieve value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value if exists and not expired, None otherwise

        Example:
            >>> cache = CacheManager()
            >>> cache.set("cart_123", {"recommendations": [...]})
            >>> result = cache.get("cart_123")
        """
        with self.lock:
            # Check if key exists
            if key not in self.cache:
                self.misses += 1
                self.logger.debug(f"Cache miss: {key}")
                return None

            # Check if expired
            timestamp = self.timestamps.get(key, 0)
            if time.time() - timestamp > self.ttl:
                # Expired - remove from cache
                self._remove_key(key)
                self.expirations += 1
                self.misses += 1
                self.logger.debug(f"Cache expired: {key}")
                return None

            # Cache hit - move to end (most recently used)
            self.cache.move_to_end(key)
            self.hits += 1
            self.logger.debug(f"Cache hit: {key}")
            return self.cache[key]

    def set(self, key: str, value: Dict) -> None:
        """
        Store value in cache.

        If cache is full, evicts least recently used entry.
        Updates timestamp for TTL tracking.

        Args:
            key: Cache key
            value: Value to cache (must be dict)

        Example:
            >>> cache = CacheManager(max_size=2)
            >>> cache.set("key1", {"data": "value1"})
            >>> cache.set("key2", {"data": "value2"})
            >>> cache.set("key3", {"data": "value3"})  # Evicts key1
        """
        with self.lock:
            # If key already exists, remove it first (will be re-added at end)
            if key in self.cache:
                del self.cache[key]
                del self.timestamps[key]

            # Check if cache is full
            if len(self.cache) >= self.max_size:
                # Evict least recently used (first item)
                oldest_key = next(iter(self.cache))
                self._remove_key(oldest_key)
                self.evictions += 1
                self.logger.debug(f"Cache eviction (LRU): {oldest_key}")

            # Add new entry
            self.cache[key] = value
            self.timestamps[key] = time.time()
            self.logger.debug(f"Cache set: {key}")

    def clear(self) -> None:
        """
        Clear all cache entries.

        Example:
            >>> cache = CacheManager()
            >>> cache.set("key1", {"data": "value"})
            >>> cache.clear()
            >>> cache.get("key1")
            None
        """
        with self.lock:
            count = len(self.cache)
            self.cache.clear()
            self.timestamps.clear()
            self.logger.info(f"Cache cleared: {count} entries removed")

    def delete(self, key: str) -> bool:
        """
        Delete specific key from cache.

        Args:
            key: Cache key to delete

        Returns:
            True if key was deleted, False if not found

        Example:
            >>> cache = CacheManager()
            >>> cache.set("key1", {"data": "value"})
            >>> cache.delete("key1")
            True
            >>> cache.delete("key1")
            False
        """
        with self.lock:
            if key in self.cache:
                self._remove_key(key)
                self.logger.debug(f"Cache delete: {key}")
                return True
            return False

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dict with cache metrics:
            - size: Current number of entries
            - max_size: Maximum capacity
            - hits: Number of cache hits
            - misses: Number of cache misses
            - hit_rate: Percentage of requests that hit cache
            - evictions: Number of LRU evictions
            - expirations: Number of TTL expirations
            - ttl: Time to live setting

        Example:
            >>> cache = CacheManager()
            >>> cache.set("key1", {"data": "value"})
            >>> cache.get("key1")
            >>> stats = cache.get_stats()
            >>> print(f"Hit rate: {stats['hit_rate']:.1f}%")
        """
        with self.lock:
            total_requests = self.hits + self.misses
            hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0.0

            return {
                "size": len(self.cache),
                "max_size": self.max_size,
                "hits": self.hits,
                "misses": self.misses,
                "hit_rate": hit_rate,
                "evictions": self.evictions,
                "expirations": self.expirations,
                "ttl": self.ttl
            }

    def reset_stats(self) -> None:
        """
        Reset statistics counters.

        Example:
            >>> cache = CacheManager()
            >>> cache.get("key1")  # miss
            >>> cache.reset_stats()
            >>> stats = cache.get_stats()
            >>> stats["misses"]
            0
        """
        with self.lock:
            self.hits = 0
            self.misses = 0
            self.evictions = 0
            self.expirations = 0
            self.logger.info("Cache statistics reset")

    def _remove_key(self, key: str) -> None:
        """
        Internal method to remove key from cache and timestamps.
        Must be called within lock context.

        Args:
            key: Cache key to remove
        """
        if key in self.cache:
            del self.cache[key]
        if key in self.timestamps:
            del self.timestamps[key]

    def cleanup_expired(self) -> int:
        """
        Manually remove all expired entries.

        Returns:
            Number of expired entries removed

        Example:
            >>> cache = CacheManager(ttl=1)
            >>> cache.set("key1", {"data": "value"})
            >>> time.sleep(2)
            >>> expired_count = cache.cleanup_expired()
            >>> expired_count
            1
        """
        with self.lock:
            current_time = time.time()
            expired_keys = []

            # Find expired keys
            for key, timestamp in self.timestamps.items():
                if current_time - timestamp > self.ttl:
                    expired_keys.append(key)

            # Remove expired keys
            for key in expired_keys:
                self._remove_key(key)
                self.expirations += 1

            if expired_keys:
                self.logger.info(f"Cleanup: {len(expired_keys)} expired entries removed")

            return len(expired_keys)


# Example usage and testing
if __name__ == "__main__":
    import time

    print("=" * 60)
    print("TESTING CACHE MANAGER")
    print("=" * 60)

    # Test 1: Basic operations
    print("\n1. Basic set/get operations:")
    cache = CacheManager(max_size=3, ttl=2)

    cache.set("key1", {"data": "value1"})
    cache.set("key2", {"data": "value2"})

    result1 = cache.get("key1")
    result2 = cache.get("key3")  # Miss

    print(f"   Get key1: {'✅' if result1 else '❌'}")
    print(f"   Get key3 (miss): {'✅' if result2 is None else '❌'}")

    stats = cache.get_stats()
    print(f"   Stats: {stats['hits']} hits, {stats['misses']} misses, hit rate: {stats['hit_rate']:.1f}%")

    # Test 2: LRU eviction
    print("\n2. LRU eviction (max_size=3):")
    cache.set("key3", {"data": "value3"})
    cache.set("key4", {"data": "value4"})  # Should evict key1

    result1 = cache.get("key1")  # Should be None (evicted)
    result4 = cache.get("key4")  # Should exist

    print(f"   Key1 evicted: {'✅' if result1 is None else '❌'}")
    print(f"   Key4 exists: {'✅' if result4 else '❌'}")
    print(f"   Cache size: {cache.get_stats()['size']}/3")

    # Test 3: TTL expiration
    print("\n3. TTL expiration (ttl=2s):")
    cache2 = CacheManager(max_size=10, ttl=1)
    cache2.set("temp_key", {"data": "temporary"})

    result_before = cache2.get("temp_key")
    print(f"   Before expiration: {'✅' if result_before else '❌'}")

    time.sleep(1.5)

    result_after = cache2.get("temp_key")
    print(f"   After expiration: {'✅' if result_after is None else '❌'}")

    # Test 4: Clear cache
    print("\n4. Clear cache:")
    cache.set("key5", {"data": "value5"})
    print(f"   Size before clear: {cache.get_stats()['size']}")
    cache.clear()
    print(f"   Size after clear: {cache.get_stats()['size']}")

    # Final stats
    print("\n" + "=" * 60)
    print("FINAL STATISTICS")
    print("=" * 60)
    stats = cache.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")

    print("\n✅ CacheManager testing complete")
