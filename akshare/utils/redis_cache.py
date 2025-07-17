#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Redis-based distributed cache decorator for akshare
Provides LRU-like caching functionality using Redis cluster
"""

import os
import pickle
import hashlib
import functools
from typing import Any, Optional, Union, Callable
import redis
from redis.cluster import RedisCluster
import logging

logger = logging.getLogger(__name__)


class RedisLRUCache:
    """Redis-based LRU cache implementation"""
    
    def __init__(
        self,
        redis_url: Optional[str] = None,
        prefix: Optional[str] = None,
        max_age: int = 86400, # 24 hours default, = 24 * 60 * 60
        redis_client: Optional[Union[redis.Redis, RedisCluster]] = None,
        serialize_method: str = "pickle",
        func_key: Optional[str] = None,
        # key_version: str = "v1"
    ):
        """
        Initialize Redis LRU Cache
        
        Args:
            redis_url: Redis connection string, defaults to env REDIS_URL
            prefix: Cache key prefix, defaults to env AKSHARE_CACHE_PREFIX or 'akshare'
            max_age: Cache expiration time in seconds
            redis_client: Pre-configured Redis client
            serialize_method: Serialization method ('pickle',)
            func_key: Optional key for function-specific cache
            # key_version: Key version for cache invalidation
        """
        self.redis_url = redis_url or os.getenv('REDIS_URL', 'redis://tasks.redis-cluster_node')
        self.prefix = prefix or os.getenv('AKSHARE_CACHE_PREFIX', 'ak')
        self.max_age = max_age
        # self.key_version = key_version
        self.func_key = func_key
        # self.serialize_method = serialize_method
        
        # Initialize Redis client
        if redis_client:
            self.redis_client = redis_client
        else:
            self.redis_client = self._create_redis_client()
            
        # Initialize serializer
        self._init_serializer()
    
    def _create_redis_client(self) -> Union[redis.Redis, RedisCluster]:
        """Create Redis client from URL"""
        try:
            # Try to detect if it's a cluster URL
            if 'cluster' in self.redis_url.lower() or ',' in self.redis_url:
                # Handle cluster URLs - simplified approach
                # In production, you might want more sophisticated cluster detection
                hosts = []
                if ',' in self.redis_url:
                    # Handle comma-separated hosts
                    for host in self.redis_url.split(','):
                        host = host.strip()
                        if '://' in host:
                            host = host.split('://')[-1]
                        if ':' in host:
                            host, port = host.split(':')
                            hosts.append({'host': host, 'port': int(port)})
                        else:
                            hosts.append({'host': host, 'port': 6379})
                    return RedisCluster(startup_nodes=hosts, decode_responses=False)
                else:
                    return RedisCluster.from_url(self.redis_url, decode_responses=False)
            else:
                return redis.from_url(self.redis_url, decode_responses=False)
        except Exception as e:
            # FIXME: 测试用
            print(f"[redis client] - Failed to create Redis client: {e}")
            logger.warning(f"Failed to create Redis client: {e}")
            logger.warning("Falling back to localhost Redis")
            return redis.Redis(host='localhost', port=6379, decode_responses=False)
    
    def _init_serializer(self):
        """Initialize serialization method"""
        if self.serialize_method == "pickle":
            self.serialize = pickle.dumps
            self.deserialize = pickle.loads
        # elif self.serialize_method == "dill":
        #     try:
        #         import dill
        #         self.serialize = dill.dumps
        #         self.deserialize = dill.loads
        #     except ImportError:
        #         logger.warning("dill not available, falling back to pickle")
        #         self.serialize = pickle.dumps
        #         self.deserialize = pickle.loads
        else:
            raise ValueError(f"Unsupported serialize_method: {self.serialize_method}")
    
    def _generate_cache_key(self, func: Callable, args: tuple, kwargs: dict) -> str:
        """
        Generate unique cache key for function call
        
        Args:
            func: Function object
            args: Function positional arguments
            kwargs: Function keyword arguments
            
        Returns:
            Unique cache key string
        """
        # Get function identifier
        if isinstance(self.func_key, str):
            # Use provided func_key directly
            func_id = self.func_key
        else:
            # Fallback to module and function name
            func_module = getattr(func, '__module__', 'unknown')
            func_name = getattr(func, '__name__', 'unknown')
            func_id = f"{func_module}.{func_name}"
        
        # Create args signature
        if len(args) == 0 and len(kwargs) == 0:
            # Special case for no arguments
            args_hash = ''
        else:
            args_str = self._serialize_args(args, kwargs)
            args_hash = ':' + hashlib.md5(args_str.encode('utf-8')).hexdigest()
        
        # Combine into final key
        cache_key = f"{self.prefix}:{func_id}{args_hash}"
        return cache_key
    
    def _serialize_args(self, args: tuple, kwargs: dict) -> str:
        """
        Serialize function arguments to string for key generation
        
        Args:
            args: Positional arguments
            kwargs: Keyword arguments
            
        Returns:
            Serialized arguments string
        """
        try:
            # Convert args and kwargs to a deterministic string
            # Handle common data types that might not be pickle-able for keys
            serializable_args = []
            for arg in args:
                if hasattr(arg, '__dict__'):
                    # For complex objects, use string representation
                    serializable_args.append(str(arg))
                else:
                    serializable_args.append(arg)
            
            serializable_kwargs = {}
            for k, v in kwargs.items():
                if hasattr(v, '__dict__'):
                    serializable_kwargs[k] = str(v)
                else:
                    serializable_kwargs[k] = v
            
            # Create deterministic string representation
            args_repr = f"args:{repr(tuple(serializable_args))}_kwargs:{repr(sorted(serializable_kwargs.items()))}"
            return args_repr
            
        except Exception as e:
            # FIXME: 测试用
            print(f"[redis client] - Failed to serialize args normally, using pickle: {e}")
            logger.warning(f"Failed to serialize args normally, using pickle: {e}")
            # Fallback to pickle for key generation
            try:
                combined = (args, kwargs)
                pickled = pickle.dumps(combined)
                return hashlib.md5(pickled).hexdigest()
            except Exception as e2:
                # FIXME: 测试用
                print(f"[redis client] - Pickle fallback also failed: {e2}")
                logger.warning(f"Pickle fallback also failed: {e2}")
                # Ultimate fallback - use string representation
                return str((args, kwargs))
    
    def get(self, key: str) -> Any:
        """Get value from cache"""
        try:
            cached_data = self.redis_client.get(key)
            if cached_data is None:
                return None
            return self.deserialize(cached_data)
        except Exception as e:
            # FIXME: 测试用
            print(f"[redis client] - Failed to get from cache: {e}")
            logger.warning(f"Failed to get from cache: {e}")
            return None
    
    def set(self, key: str, value: Any, expire: Optional[int] = None) -> bool:
        """Set value in cache"""
        try:
            serialized_data = self.serialize(value)
            expire_time = expire or self.max_age
            self.redis_client.setex(key, expire_time, serialized_data)
            return True
        except Exception as e:
            # FIXME: 测试用
            print(f"[redis client] - Failed to set cache: {e}")
            logger.warning(f"Failed to set cache: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete key from cache"""
        try:
            return bool(self.redis_client.delete(key))
        except Exception as e:
            # FIXME: 测试用
            print(f"[redis client] - Failed to delete from cache: {e}")
            logger.warning(f"Failed to delete from cache: {e}")
            return False
    
    def clear_prefix(self, pattern: Optional[str] = None) -> int:
        """Clear all keys with prefix"""
        try:
            pattern = pattern or f"{self.prefix}:*"
            keys = self.redis_client.keys(pattern)
            if keys:
                return self.redis_client.delete(*keys)
            return 0
        except Exception as e:
            # FIXME: 测试用
            print(f"[redis client] - Failed to clear cache: {e}")
            logger.warning(f"Failed to clear cache: {e}")
            return 0


# Global cache instance
_default_cache = None


def get_default_cache() -> RedisLRUCache:
    """Get or create default cache instance"""
    global _default_cache
    if _default_cache is None:
        _default_cache = RedisLRUCache()
    return _default_cache


def lru_cache(
    redis_url: Optional[str] = None,
    prefix: Optional[str] = None,
    max_age: int = 86400, # 24小时， = 24 * 60 * 60,
    redis_client: Optional[Union[redis.Redis, RedisCluster]] = None,
    serialize_method: str = "pickle",
    func_key: Optional[str] = None,
    # key_version: str = "v1",
    cache_instance: Optional[RedisLRUCache] = None
):
    """
    Redis-based LRU cache decorator
    
    Usage:
        # Basic usage with default settings
        @lru_cache()
        def my_function():
            return expensive_operation()
        
        # With custom settings
        @lru_cache(
            redis_url='redis://localhost:6379',
            prefix='myapp',
            max_age=3600,  # 1 hour
        )
        def my_function():
            return expensive_operation()
        
        # With pre-configured cache
        cache = RedisLRUCache(redis_url='redis://localhost:6379')
        @lru_cache(cache_instance=cache)
        def my_function():
            return expensive_operation()
    
    Args:
        redis_url: Redis connection string
        prefix: Cache key prefix
        max_age: Cache expiration time in seconds
        redis_client: Pre-configured Redis client
        serialize_method: Serialization method
        func_key: Optional key for function-specific cache
        # key_version: Key version for cache invalidation
        cache_instance: Pre-configured cache instance
    """
    def decorator(func: Callable) -> Callable:
        # Create cache instance for this decorator
        if cache_instance:
            cache = cache_instance
        else:
            if all(param is None for param in [redis_url, prefix, redis_client]) and max_age == 86400: # 24小时默认值
                # Use default cache for minimal configuration
                cache = get_default_cache()
            else:
                # Create new cache instance with specific configuration
                cache = RedisLRUCache(
                    redis_url=redis_url,
                    prefix=prefix,
                    max_age=max_age,
                    redis_client=redis_client,
                    serialize_method=serialize_method,
                    func_key=func_key,
                    # key_version=key_version
                )
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = cache._generate_cache_key(func, args, kwargs)
            
            # Try to get from cache
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                # FIXME: 测试用
                print(f"[redis client] - Cache hit for {func.__name__}")
                logger.debug(f"Cache hit for {func.__name__}")
                return cached_result
            
            # Cache miss - execute function
            # FIXME: 测试用
            print(f"[redis client] - Cache miss for {func.__name__}")
            logger.debug(f"Cache miss for {func.__name__}")
            result = func(*args, **kwargs)
            
            # Store in cache
            cache.set(cache_key, result)
            
            return result
        
        # Add cache control methods to wrapper
        wrapper.cache = cache
        wrapper.cache_clear = lambda: cache.clear_prefix()
        wrapper.cache_info = lambda: {"cache_prefix": cache.prefix, "max_age": cache.max_age}
        
        return wrapper
    
    return decorator


# Convenience function for direct usage
def cached_function(func: Callable, **cache_kwargs) -> Callable:
    """
    Apply cache to existing function
    
    Usage:
        original_func = some_function
        cached_func = cached_function(original_func, max_age=3600)
    """
    return lru_cache(**cache_kwargs)(func)


# Cache management utilities
def clear_all_cache(prefix: Optional[str] = None):
    """Clear all cache with given prefix"""
    cache = get_default_cache()
    if prefix:
        return cache.clear_prefix(f"{prefix}:*")
    else:
        return cache.clear_prefix()


def configure_default_cache(**kwargs):
    """Configure the default cache instance"""
    global _default_cache
    _default_cache = RedisLRUCache(**kwargs)

