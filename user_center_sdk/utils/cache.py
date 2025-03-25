"""
用户中心SDK的缓存实现
支持多种缓存后端（内存、Redis、Django缓存）
"""

import json
import time
import hashlib
import logging
import threading
from typing import Dict, Any, Optional, Union, Callable, List, Tuple

logger = logging.getLogger(__name__)

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

try:
    from django.core.cache import cache as django_cache
    DJANGO_CACHE_AVAILABLE = True
except ImportError:
    DJANGO_CACHE_AVAILABLE = False


class CacheEntry:
    """
    缓存条目类，包含值和元数据
    """
    
    def __init__(
        self,
        key: str,
        value: Any,
        expires_at: float,
        created_at: float = None,
        metadata: Dict[str, Any] = None
    ):
        """
        初始化缓存条目
        
        Args:
            key: 缓存键
            value: 缓存值
            expires_at: 过期时间戳
            created_at: 创建时间戳
            metadata: 元数据
        """
        self.key = key
        self.value = value
        self.expires_at = expires_at
        self.created_at = created_at or time.time()
        self.metadata = metadata or {}
        
    def is_expired(self) -> bool:
        """
        检查缓存是否已过期
        
        Returns:
            是否已过期
        """
        return time.time() > self.expires_at
    
    def remaining_ttl(self) -> float:
        """
        获取剩余生存时间（秒）
        
        Returns:
            剩余生存时间（秒）
        """
        return max(0, self.expires_at - time.time())
    
    def to_dict(self) -> Dict[str, Any]:
        """
        将缓存条目转换为字典
        
        Returns:
            字典
        """
        return {
            "key": self.key,
            "value": self.value,
            "expires_at": self.expires_at,
            "created_at": self.created_at,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CacheEntry':
        """
        从字典创建缓存条目
        
        Args:
            data: 字典
            
        Returns:
            缓存条目
        """
        return cls(
            key=data["key"],
            value=data["value"],
            expires_at=data["expires_at"],
            created_at=data.get("created_at"),
            metadata=data.get("metadata", {})
        )


class CacheBackend:
    """
    缓存后端基类
    """
    
    def get(self, key: str) -> Optional[Any]:
        """
        获取缓存值
        
        Args:
            key: 缓存键
            
        Returns:
            缓存值，如果不存在则返回None
        """
        raise NotImplementedError("子类必须实现此方法")
    
    def set(self, key: str, value: Any, ttl: int = 300, metadata: Dict[str, Any] = None) -> bool:
        """
        设置缓存值
        
        Args:
            key: 缓存键
            value: 缓存值
            ttl: 生存时间（秒）
            metadata: 元数据
            
        Returns:
            是否设置成功
        """
        raise NotImplementedError("子类必须实现此方法")
    
    def delete(self, key: str) -> bool:
        """
        删除缓存值
        
        Args:
            key: 缓存键
            
        Returns:
            是否删除成功
        """
        raise NotImplementedError("子类必须实现此方法")
    
    def exists(self, key: str) -> bool:
        """
        检查缓存键是否存在
        
        Args:
            key: 缓存键
            
        Returns:
            是否存在
        """
        raise NotImplementedError("子类必须实现此方法")
    
    def clear(self) -> bool:
        """
        清除所有缓存
        
        Returns:
            是否清除成功
        """
        raise NotImplementedError("子类必须实现此方法")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息
        
        Returns:
            缓存统计信息
        """
        raise NotImplementedError("子类必须实现此方法")


class MemoryCacheBackend(CacheBackend):
    """
    内存缓存后端
    """
    
    def __init__(self, max_size: int = 1000):
        """
        初始化内存缓存后端
        
        Args:
            max_size: 最大缓存条目数
        """
        self.max_size = max_size
        self.cache: Dict[str, CacheEntry] = {}
        self.lock = threading.RLock()
        self.hits = 0
        self.misses = 0
        self.created_at = time.time()
        
    def get(self, key: str) -> Optional[Any]:
        """
        获取缓存值
        
        Args:
            key: 缓存键
            
        Returns:
            缓存值，如果不存在或已过期则返回None
        """
        with self.lock:
            if key not in self.cache:
                self.misses += 1
                return None
            
            entry = self.cache[key]
            
            # 检查是否过期
            if entry.is_expired():
                del self.cache[key]
                self.misses += 1
                return None
            
            self.hits += 1
            return entry.value
    
    def set(self, key: str, value: Any, ttl: int = 300, metadata: Dict[str, Any] = None) -> bool:
        """
        设置缓存值
        
        Args:
            key: 缓存键
            value: 缓存值
            ttl: 生存时间（秒）
            metadata: 元数据
            
        Returns:
            是否设置成功
        """
        with self.lock:
            # 如果达到最大大小且键不存在，则删除最旧的条目
            if len(self.cache) >= self.max_size and key not in self.cache:
                oldest_key = min(self.cache.items(), key=lambda x: x[1].created_at)[0]
                del self.cache[oldest_key]
            
            # 设置缓存
            self.cache[key] = CacheEntry(
                key=key,
                value=value,
                expires_at=time.time() + ttl,
                metadata=metadata
            )
            
            return True
    
    def delete(self, key: str) -> bool:
        """
        删除缓存值
        
        Args:
            key: 缓存键
            
        Returns:
            是否删除成功
        """
        with self.lock:
            if key in self.cache:
                del self.cache[key]
                return True
            return False
    
    def exists(self, key: str) -> bool:
        """
        检查缓存键是否存在且未过期
        
        Args:
            key: 缓存键
            
        Returns:
            是否存在且未过期
        """
        with self.lock:
            if key not in self.cache:
                return False
            
            # 检查是否过期
            if self.cache[key].is_expired():
                del self.cache[key]
                return False
            
            return True
    
    def clear(self) -> bool:
        """
        清除所有缓存
        
        Returns:
            是否清除成功
        """
        with self.lock:
            self.cache.clear()
            return True
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息
        
        Returns:
            缓存统计信息
        """
        with self.lock:
            total_requests = self.hits + self.misses
            
            # 删除过期项
            expired_count = 0
            current_time = time.time()
            for key in list(self.cache.keys()):
                if current_time > self.cache[key].expires_at:
                    del self.cache[key]
                    expired_count += 1
            
            return {
                "backend": "memory",
                "size": len(self.cache),
                "max_size": self.max_size,
                "hits": self.hits,
                "misses": self.misses,
                "hit_rate": (self.hits / total_requests) if total_requests > 0 else 0,
                "expired_count": expired_count,
                "uptime": time.time() - self.created_at
            }


class RedisCacheBackend(CacheBackend):
    """
    Redis缓存后端
    """
    
    def __init__(self, redis_url: str, namespace: str = "user_center_sdk"):
        """
        初始化Redis缓存后端
        
        Args:
            redis_url: Redis URL
            namespace: 缓存命名空间
        """
        if not REDIS_AVAILABLE:
            raise ImportError("Redis缓存后端需要安装redis包")
        
        self.namespace = namespace
        self.client = redis.from_url(redis_url)
        self.hits = 0
        self.misses = 0
        self.created_at = time.time()
    
    def _make_key(self, key: str) -> str:
        """
        生成带命名空间的缓存键
        
        Args:
            key: 原始缓存键
            
        Returns:
            带命名空间的缓存键
        """
        return f"{self.namespace}:{key}"
    
    def get(self, key: str) -> Optional[Any]:
        """
        获取缓存值
        
        Args:
            key: 缓存键
            
        Returns:
            缓存值，如果不存在则返回None
        """
        redis_key = self._make_key(key)
        data = self.client.get(redis_key)
        
        if data is None:
            self.misses += 1
            return None
        
        try:
            entry = CacheEntry.from_dict(json.loads(data))
            self.hits += 1
            return entry.value
        except (json.JSONDecodeError, KeyError):
            self.misses += 1
            return None
    
    def set(self, key: str, value: Any, ttl: int = 300, metadata: Dict[str, Any] = None) -> bool:
        """
        设置缓存值
        
        Args:
            key: 缓存键
            value: 缓存值
            ttl: 生存时间（秒）
            metadata: 元数据
            
        Returns:
            是否设置成功
        """
        redis_key = self._make_key(key)
        expires_at = time.time() + ttl
        
        entry = CacheEntry(
            key=key,
            value=value,
            expires_at=expires_at,
            metadata=metadata
        )
        
        try:
            self.client.setex(
                redis_key,
                ttl,
                json.dumps(entry.to_dict())
            )
            return True
        except Exception as e:
            logger.error(f"Redis缓存设置失败: {str(e)}")
            return False
    
    def delete(self, key: str) -> bool:
        """
        删除缓存值
        
        Args:
            key: 缓存键
            
        Returns:
            是否删除成功
        """
        redis_key = self._make_key(key)
        return self.client.delete(redis_key) > 0
    
    def exists(self, key: str) -> bool:
        """
        检查缓存键是否存在
        
        Args:
            key: 缓存键
            
        Returns:
            是否存在
        """
        redis_key = self._make_key(key)
        return bool(self.client.exists(redis_key))
    
    def clear(self) -> bool:
        """
        清除所有缓存
        
        Returns:
            是否清除成功
        """
        keys = self.client.keys(f"{self.namespace}:*")
        if keys:
            self.client.delete(*keys)
        return True
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息
        
        Returns:
            缓存统计信息
        """
        total_requests = self.hits + self.misses
        
        # 获取键数量
        keys = self.client.keys(f"{self.namespace}:*")
        
        # 获取Redis信息
        redis_info = self.client.info()
        
        return {
            "backend": "redis",
            "size": len(keys),
            "namespace": self.namespace,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": (self.hits / total_requests) if total_requests > 0 else 0,
            "uptime": time.time() - self.created_at,
            "redis_used_memory": redis_info.get("used_memory_human", "N/A"),
            "redis_version": redis_info.get("redis_version", "N/A")
        }


class DjangoCacheBackend(CacheBackend):
    """
    Django缓存后端
    """
    
    def __init__(self, namespace: str = "user_center_sdk"):
        """
        初始化Django缓存后端
        
        Args:
            namespace: 缓存命名空间
        """
        if not DJANGO_CACHE_AVAILABLE:
            raise ImportError("Django缓存后端需要在Django环境中运行")
        
        self.namespace = namespace
        self.hits = 0
        self.misses = 0
        self.created_at = time.time()
    
    def _make_key(self, key: str) -> str:
        """
        生成带命名空间的缓存键
        
        Args:
            key: 原始缓存键
            
        Returns:
            带命名空间的缓存键
        """
        return f"{self.namespace}:{key}"
    
    def get(self, key: str) -> Optional[Any]:
        """
        获取缓存值
        
        Args:
            key: 缓存键
            
        Returns:
            缓存值，如果不存在则返回None
        """
        django_key = self._make_key(key)
        data = django_cache.get(django_key)
        
        if data is None:
            self.misses += 1
            return None
        
        try:
            entry = CacheEntry.from_dict(data)
            
            # Django缓存自己管理过期时间，但我们仍需检查
            if entry.is_expired():
                django_cache.delete(django_key)
                self.misses += 1
                return None
                
            self.hits += 1
            return entry.value
        except (KeyError, TypeError):
            self.misses += 1
            return None
    
    def set(self, key: str, value: Any, ttl: int = 300, metadata: Dict[str, Any] = None) -> bool:
        """
        设置缓存值
        
        Args:
            key: 缓存键
            value: 缓存值
            ttl: 生存时间（秒）
            metadata: 元数据
            
        Returns:
            是否设置成功
        """
        django_key = self._make_key(key)
        expires_at = time.time() + ttl
        
        entry = CacheEntry(
            key=key,
            value=value,
            expires_at=expires_at,
            metadata=metadata
        )
        
        try:
            django_cache.set(django_key, entry.to_dict(), ttl)
            return True
        except Exception as e:
            logger.error(f"Django缓存设置失败: {str(e)}")
            return False
    
    def delete(self, key: str) -> bool:
        """
        删除缓存值
        
        Args:
            key: 缓存键
            
        Returns:
            是否删除成功
        """
        django_key = self._make_key(key)
        django_cache.delete(django_key)
        return True  # Django缓存不返回是否删除成功
    
    def exists(self, key: str) -> bool:
        """
        检查缓存键是否存在
        
        Args:
            key: 缓存键
            
        Returns:
            是否存在
        """
        django_key = self._make_key(key)
        return django_cache.get(django_key) is not None
    
    def clear(self) -> bool:
        """
        清除命名空间下的所有缓存
        注意：Django缓存没有直接的方法来清除特定命名空间的缓存
        此方法尝试通过获取所有键并逐个删除来实现
        
        Returns:
            是否清除成功
        """
        # 这是一个不完美的解决方案，只适用于某些Django缓存后端
        # 对于生产环境，建议使用版本化的命名空间
        try:
            django_cache.clear()
            return True
        except NotImplementedError:
            # 如果后端不支持clear()，我们无法有效地清除命名空间
            logger.warning("当前Django缓存后端不支持clear()方法，无法清除命名空间下的所有缓存")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息
        
        Returns:
            缓存统计信息
        """
        total_requests = self.hits + self.misses
        
        return {
            "backend": "django",
            "namespace": self.namespace,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": (self.hits / total_requests) if total_requests > 0 else 0,
            "uptime": time.time() - self.created_at
        }


class CacheManager:
    """
    缓存管理器，根据配置选择合适的缓存后端
    """
    
    def __init__(
        self,
        enabled: bool = True,
        backend: str = "memory",
        ttl: int = 300,
        namespace: str = "user_center_sdk",
        redis_url: str = "redis://localhost:6379/0",
        max_memory_size: int = 1000,
    ):
        """
        初始化缓存管理器
        
        Args:
            enabled: 是否启用缓存
            backend: 缓存后端（memory, redis, django）
            ttl: 默认缓存生存时间（秒）
            namespace: 缓存命名空间
            redis_url: Redis URL
            max_memory_size: 内存缓存最大条目数
        """
        self.enabled = enabled
        self.backend_name = backend
        self.default_ttl = ttl
        self.namespace = namespace
        self.cached_keys = set()
        
        # 根据配置创建合适的缓存后端
        if not enabled:
            self.backend = None
        elif backend == "redis":
            try:
                self.backend = RedisCacheBackend(redis_url, namespace)
            except (ImportError, Exception) as e:
                logger.warning(f"无法创建Redis缓存后端，回退到内存缓存: {str(e)}")
                self.backend = MemoryCacheBackend(max_memory_size)
                self.backend_name = "memory"
        elif backend == "django":
            try:
                self.backend = DjangoCacheBackend(namespace)
            except (ImportError, Exception) as e:
                logger.warning(f"无法创建Django缓存后端，回退到内存缓存: {str(e)}")
                self.backend = MemoryCacheBackend(max_memory_size)
                self.backend_name = "memory"
        else:
            self.backend = MemoryCacheBackend(max_memory_size)
            self.backend_name = "memory"
    
    def get(self, key: str) -> Tuple[Optional[Any], bool]:
        """
        获取缓存值
        
        Args:
            key: 缓存键
            
        Returns:
            (缓存值, 是否命中)，如果缓存未启用或不存在则返回(None, False)
        """
        if not self.enabled or not self.backend:
            return None, False
        
        value = self.backend.get(key)
        return value, value is not None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None, metadata: Dict[str, Any] = None) -> bool:
        """
        设置缓存值
        
        Args:
            key: 缓存键
            value: 缓存值
            ttl: 生存时间（秒），如果为None则使用默认值
            metadata: 元数据
            
        Returns:
            是否设置成功，如果缓存未启用则返回False
        """
        if not self.enabled or not self.backend:
            return False
        
        ttl = ttl if ttl is not None else self.default_ttl
        result = self.backend.set(key, value, ttl, metadata)
        
        if result:
            self.cached_keys.add(key)
            
        return result
    
    def delete(self, key: str) -> bool:
        """
        删除缓存值
        
        Args:
            key: 缓存键
            
        Returns:
            是否删除成功，如果缓存未启用则返回False
        """
        if not self.enabled or not self.backend:
            return False
        
        result = self.backend.delete(key)
        
        if result and key in self.cached_keys:
            self.cached_keys.remove(key)
            
        return result
    
    def exists(self, key: str) -> bool:
        """
        检查缓存键是否存在
        
        Args:
            key: 缓存键
            
        Returns:
            是否存在，如果缓存未启用则返回False
        """
        if not self.enabled or not self.backend:
            return False
        
        return self.backend.exists(key)
    
    def clear(self) -> bool:
        """
        清除所有缓存
        
        Returns:
            是否清除成功，如果缓存未启用则返回False
        """
        if not self.enabled or not self.backend:
            return False
        
        result = self.backend.clear()
        
        if result:
            self.cached_keys.clear()
            
        return result
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息
        
        Returns:
            缓存统计信息
        """
        if not self.enabled or not self.backend:
            return {
                "enabled": False,
                "backend": None
            }
        
        backend_stats = self.backend.get_stats()
        
        return {
            "enabled": self.enabled,
            "backend": self.backend_name,
            "default_ttl": self.default_ttl,
            "namespace": self.namespace,
            "cached_keys_count": len(self.cached_keys),
            **backend_stats
        }
    
    def invalidate_pattern(self, pattern: str) -> int:
        """
        根据模式失效缓存
        
        Args:
            pattern: 模式字符串
            
        Returns:
            删除的键数量
        """
        if not self.enabled or not self.backend:
            return 0
        
        import re
        regex = re.compile(pattern)
        
        to_delete = [key for key in self.cached_keys if regex.match(key)]
        deleted = 0
        
        for key in to_delete:
            if self.delete(key):
                deleted += 1
                
        return deleted


def generate_cache_key(prefix: str, *args, **kwargs) -> str:
    """
    根据前缀和参数生成缓存键
    
    Args:
        prefix: 前缀
        *args: 位置参数
        **kwargs: 关键字参数
        
    Returns:
        缓存键
    """
    # 将位置参数和关键字参数转换为字符串
    args_str = ",".join(str(arg) for arg in args)
    kwargs_str = ",".join(f"{k}={v}" for k, v in sorted(kwargs.items()))
    
    # 组合前缀和参数
    key_parts = [prefix]
    if args_str:
        key_parts.append(args_str)
    if kwargs_str:
        key_parts.append(kwargs_str)
    
    # 使用MD5哈希生成固定长度的键
    combined = ":".join(key_parts)
    hashed = hashlib.md5(combined.encode()).hexdigest()
    
    return f"{prefix}:{hashed}"


def cached(prefix: str, ttl: Optional[int] = None) -> Callable:
    """
    缓存装饰器，用于缓存函数返回值
    
    Args:
        prefix: 缓存键前缀
        ttl: 生存时间（秒），如果为None则使用缓存管理器的默认值
        
    Returns:
        装饰器函数
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(self, *args, **kwargs) -> Any:
            # 如果缓存未启用或未初始化，则直接调用函数
            if not hasattr(self, "cache") or not getattr(self, "cache"):
                return func(self, *args, **kwargs)
            
            cache_manager = getattr(self, "cache")
            
            # 生成缓存键
            cache_key = generate_cache_key(prefix, *args, **kwargs)
            
            # 尝试从缓存获取
            value, hit = cache_manager.get(cache_key)
            if hit:
                return value
            
            # 调用原始函数
            result = func(self, *args, **kwargs)
            
            # 设置缓存
            cache_manager.set(cache_key, result, ttl)
            
            return result
            
        return wrapper
    return decorator
