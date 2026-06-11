"""
简单内存缓存模块

使用 Python 内置 dict 实现 TTL 缓存，无需额外依赖
"""

from functools import wraps
import time
import hashlib
import json


class SimpleCache:
    """简单的 TTL 缓存实现"""
    
    def __init__(self, maxsize=1000, ttl=300):
        self.maxsize = maxsize
        self.ttl = ttl
        self._cache = {}
        self._timestamps = {}
    
    def get(self, key):
        if key not in self._cache:
            return None
        if time.time() - self._timestamps.get(key, 0) > self.ttl:
            del self._cache[key]
            del self._timestamps[key]
            return None
        return self._cache[key]
    
    def set(self, key, value):
        if len(self._cache) >= self.maxsize:
            self._cleanup()
        self._cache[key] = value
        self._timestamps[key] = time.time()
    
    def _cleanup(self):
        now = time.time()
        expired = [k for k, t in self._timestamps.items() if now - t > self.ttl]
        for k in expired:
            del self._cache[k]
            del self._timestamps[k]
    
    def clear(self):
        self._cache.clear()
        self._timestamps.clear()


def cache_key(*args, **kwargs):
    """生成缓存键"""
    key_data = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True, default=str)
    return hashlib.md5(key_data.encode()).hexdigest()


def api_cache(ttl=300, maxsize=1000):
    """
    API 缓存装饰器
    
    使用方式：
        @api_cache(ttl=60)
        def get_consecutive_rank(date):
            ...
    """
    cache = SimpleCache(maxsize=maxsize, ttl=ttl)
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            key = cache_key(func.__name__, *args, **kwargs)
            result = cache.get(key)
            if result is not None:
                return result
            result = func(*args, **kwargs)
            cache.set(key, result)
            return result
        
        wrapper.cache_clear = cache.clear
        wrapper.cache_info = lambda: {"size": len(cache._cache), "maxsize": maxsize, "ttl": ttl}
        
        return wrapper
    
    return decorator


# 缓存配置
CACHE_SHORT = 60
CACHE_MEDIUM = 300
CACHE_LONG = 3600