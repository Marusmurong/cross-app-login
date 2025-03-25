"""
用户中心SDK的配置管理
增强版 - 提供更多高级配置选项
"""

import os
import json
from typing import Dict, Any, Optional, Union, List


class Config:
    """
    用户中心SDK的配置类
    增强版 - 支持更多高级配置选项
    """

    def __init__(
        self,
        api_base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: Optional[int] = None,
        max_retries: Optional[int] = None,
        cache_enabled: Optional[bool] = None,
        cache_timeout: Optional[int] = None,
        auto_refresh_token: Optional[bool] = None,
        # 新增参数 - 连接池配置
        pool_connections: Optional[int] = None,
        pool_maxsize: Optional[int] = None,
        # 新增参数 - 分离超时配置
        connect_timeout: Optional[float] = None,
        read_timeout: Optional[float] = None,
        # 新增参数 - 高级缓存配置
        cache_backend: Optional[str] = None,
        cache_redis_url: Optional[str] = None,
        cache_namespace: Optional[str] = None,
        # 新增参数 - 安全配置
        token_encryption_key: Optional[str] = None,
        verify_ssl: Optional[bool] = None,
        # 新增参数 - 监控与调试
        enable_performance_tracking: Optional[bool] = None,
        enable_debug_logging: Optional[bool] = None,
        # 新增参数 - 断路器配置
        circuit_breaker_enabled: Optional[bool] = None,
        circuit_breaker_failure_threshold: Optional[int] = None,
        circuit_breaker_recovery_timeout: Optional[int] = None,
        # 新增参数 - 令牌安全策略
        token_ip_binding: Optional[bool] = None,
        token_max_uses: Optional[int] = None,
        token_lifetime: Optional[int] = None,
        refresh_token_lifetime: Optional[int] = None,
    ):
        """
        初始化配置

        Args:
            api_base_url: 用户中心API的基础URL
            api_key: 用于API文档访问的API密钥
            timeout: 请求超时时间（秒）
            max_retries: 最大重试次数
            cache_enabled: 是否启用缓存
            cache_timeout: 缓存超时时间（秒）
            auto_refresh_token: 是否自动刷新令牌
            
            # 连接池配置
            pool_connections: 连接池连接数
            pool_maxsize: 连接池最大连接数
            
            # 分离超时配置
            connect_timeout: 连接超时时间（秒）
            read_timeout: 读取超时时间（秒）
            
            # 高级缓存配置
            cache_backend: 缓存后端（memory, redis, django）
            cache_redis_url: Redis缓存URL
            cache_namespace: 缓存命名空间
            
            # 安全配置
            token_encryption_key: 令牌加密密钥
            verify_ssl: 是否验证SSL证书
            
            # 监控与调试
            enable_performance_tracking: 是否启用性能跟踪
            enable_debug_logging: 是否启用调试日志
            
            # 断路器配置
            circuit_breaker_enabled: 是否启用断路器
            circuit_breaker_failure_threshold: 断路器失败阈值
            circuit_breaker_recovery_timeout: 断路器恢复超时时间（秒）
            
            # 令牌安全策略
            token_ip_binding: 是否启用令牌IP绑定
            token_max_uses: 令牌最大使用次数
            token_lifetime: 令牌生命周期（秒）
            refresh_token_lifetime: 刷新令牌生命周期（秒）
        """
        # 尝试从Django设置中获取配置
        django_config = self._get_django_config()

        # 设置配置值，优先级：传入参数 > 环境变量 > Django设置 > 默认值
        self.api_base_url = api_base_url or os.environ.get(
            "USER_CENTER_API_BASE_URL",
            django_config.get("API_BASE_URL", "http://localhost:5200/api/v1/"),
        )
        
        # 确保API基础URL以斜杠结尾
        if not self.api_base_url.endswith("/"):
            self.api_base_url += "/"

        self.api_key = api_key or os.environ.get(
            "USER_CENTER_API_KEY",
            django_config.get("API_KEY", "usercenter2025"),
        )
        
        # 基础HTTP配置
        self.timeout = timeout or int(os.environ.get(
            "USER_CENTER_TIMEOUT",
            django_config.get("DEFAULT_TIMEOUT", 10),
        ))
        
        self.max_retries = max_retries or int(os.environ.get(
            "USER_CENTER_MAX_RETRIES",
            django_config.get("MAX_RETRIES", 3),
        ))
        
        # 缓存配置
        self.cache_enabled = cache_enabled if cache_enabled is not None else (
            os.environ.get("USER_CENTER_CACHE_ENABLED", "").lower() == "true"
            if os.environ.get("USER_CENTER_CACHE_ENABLED", "")
            else django_config.get("CACHE_ENABLED", True)
        )
        
        self.cache_timeout = cache_timeout or int(os.environ.get(
            "USER_CENTER_CACHE_TIMEOUT",
            django_config.get("CACHE_TIMEOUT", 300),
        ))
        
        # 令牌配置
        self.auto_refresh_token = auto_refresh_token if auto_refresh_token is not None else (
            os.environ.get("USER_CENTER_AUTO_REFRESH_TOKEN", "").lower() == "true"
            if os.environ.get("USER_CENTER_AUTO_REFRESH_TOKEN", "")
            else django_config.get("AUTO_REFRESH_TOKEN", True)
        )
        
        # 连接池配置
        self.pool_connections = pool_connections or int(os.environ.get(
            "USER_CENTER_POOL_CONNECTIONS",
            django_config.get("POOL_CONNECTIONS", 10),
        ))
        
        self.pool_maxsize = pool_maxsize or int(os.environ.get(
            "USER_CENTER_POOL_MAXSIZE",
            django_config.get("POOL_MAXSIZE", 20),
        ))
        
        # 分离超时配置
        self.connect_timeout = connect_timeout or float(os.environ.get(
            "USER_CENTER_CONNECT_TIMEOUT",
            django_config.get("CONNECT_TIMEOUT", self.timeout / 3),
        ))
        
        self.read_timeout = read_timeout or float(os.environ.get(
            "USER_CENTER_READ_TIMEOUT",
            django_config.get("READ_TIMEOUT", self.timeout),
        ))
        
        # 高级缓存配置
        self.cache_backend = cache_backend or os.environ.get(
            "USER_CENTER_CACHE_BACKEND",
            django_config.get("CACHE_BACKEND", "memory"),
        )
        
        self.cache_redis_url = cache_redis_url or os.environ.get(
            "USER_CENTER_CACHE_REDIS_URL",
            django_config.get("CACHE_REDIS_URL", "redis://localhost:6379/0"),
        )
        
        self.cache_namespace = cache_namespace or os.environ.get(
            "USER_CENTER_CACHE_NAMESPACE",
            django_config.get("CACHE_NAMESPACE", "user_center_sdk"),
        )
        
        # 安全配置
        self.token_encryption_key = token_encryption_key or os.environ.get(
            "USER_CENTER_TOKEN_ENCRYPTION_KEY",
            django_config.get("TOKEN_ENCRYPTION_KEY", ""),
        )
        
        self.verify_ssl = verify_ssl if verify_ssl is not None else (
            os.environ.get("USER_CENTER_VERIFY_SSL", "").lower() != "false"
            if os.environ.get("USER_CENTER_VERIFY_SSL", "")
            else django_config.get("VERIFY_SSL", True)
        )
        
        # 监控与调试
        self.enable_performance_tracking = enable_performance_tracking if enable_performance_tracking is not None else (
            os.environ.get("USER_CENTER_ENABLE_PERFORMANCE_TRACKING", "").lower() == "true"
            if os.environ.get("USER_CENTER_ENABLE_PERFORMANCE_TRACKING", "")
            else django_config.get("ENABLE_PERFORMANCE_TRACKING", False)
        )
        
        self.enable_debug_logging = enable_debug_logging if enable_debug_logging is not None else (
            os.environ.get("USER_CENTER_ENABLE_DEBUG_LOGGING", "").lower() == "true"
            if os.environ.get("USER_CENTER_ENABLE_DEBUG_LOGGING", "")
            else django_config.get("ENABLE_DEBUG_LOGGING", False)
        )
        
        # 断路器配置
        self.circuit_breaker_enabled = circuit_breaker_enabled if circuit_breaker_enabled is not None else (
            os.environ.get("USER_CENTER_CIRCUIT_BREAKER_ENABLED", "").lower() == "true"
            if os.environ.get("USER_CENTER_CIRCUIT_BREAKER_ENABLED", "")
            else django_config.get("CIRCUIT_BREAKER_ENABLED", True)
        )
        
        self.circuit_breaker_failure_threshold = circuit_breaker_failure_threshold or int(os.environ.get(
            "USER_CENTER_CIRCUIT_BREAKER_FAILURE_THRESHOLD",
            django_config.get("CIRCUIT_BREAKER_FAILURE_THRESHOLD", 5),
        ))
        
        self.circuit_breaker_recovery_timeout = circuit_breaker_recovery_timeout or int(os.environ.get(
            "USER_CENTER_CIRCUIT_BREAKER_RECOVERY_TIMEOUT",
            django_config.get("CIRCUIT_BREAKER_RECOVERY_TIMEOUT", 30),
        ))
        
        # 令牌安全策略
        self.token_ip_binding = token_ip_binding if token_ip_binding is not None else (
            os.environ.get("USER_CENTER_TOKEN_IP_BINDING", "").lower() == "true"
            if os.environ.get("USER_CENTER_TOKEN_IP_BINDING", "")
            else django_config.get("TOKEN_IP_BINDING", False)
        )
        
        self.token_max_uses = token_max_uses or int(os.environ.get(
            "USER_CENTER_TOKEN_MAX_USES",
            django_config.get("TOKEN_MAX_USES", 0),  # 0表示不限制使用次数
        ))
        
        self.token_lifetime = token_lifetime or int(os.environ.get(
            "USER_CENTER_TOKEN_LIFETIME",
            django_config.get("TOKEN_LIFETIME", 1800),  # 默认30分钟
        ))
        
        self.refresh_token_lifetime = refresh_token_lifetime or int(os.environ.get(
            "USER_CENTER_REFRESH_TOKEN_LIFETIME",
            django_config.get("REFRESH_TOKEN_LIFETIME", 86400 * 7),  # 默认7天
        ))

    def _get_django_config(self) -> Dict[str, Any]:
        """
        从Django设置中获取配置

        Returns:
            Django设置中的配置字典
        """
        try:
            from django.conf import settings
            if hasattr(settings, "USER_CENTER_SDK"):
                return getattr(settings, "USER_CENTER_SDK", {})
        except (ImportError, ModuleNotFoundError):
            # Django不可用或未正确配置，忽略并返回空字典
            pass
        except Exception:
            # 其他异常（如ImproperlyConfigured），忽略并返回空字典
            pass
        return {}

    def to_dict(self) -> Dict[str, Any]:
        """
        将配置转换为字典

        Returns:
            配置的字典表示
        """
        return {
            # 基础配置
            "api_base_url": self.api_base_url,
            "api_key": self.api_key,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
            "cache_enabled": self.cache_enabled,
            "cache_timeout": self.cache_timeout,
            "auto_refresh_token": self.auto_refresh_token,
            
            # 连接池配置
            "pool_connections": self.pool_connections,
            "pool_maxsize": self.pool_maxsize,
            
            # 分离超时配置
            "connect_timeout": self.connect_timeout,
            "read_timeout": self.read_timeout,
            
            # 高级缓存配置
            "cache_backend": self.cache_backend,
            "cache_redis_url": self.cache_redis_url,
            "cache_namespace": self.cache_namespace,
            
            # 安全配置
            "token_encryption_key": "******" if self.token_encryption_key else None,
            "verify_ssl": self.verify_ssl,
            
            # 监控与调试
            "enable_performance_tracking": self.enable_performance_tracking,
            "enable_debug_logging": self.enable_debug_logging,
            
            # 断路器配置
            "circuit_breaker_enabled": self.circuit_breaker_enabled,
            "circuit_breaker_failure_threshold": self.circuit_breaker_failure_threshold, 
            "circuit_breaker_recovery_timeout": self.circuit_breaker_recovery_timeout,
            
            # 令牌安全策略
            "token_ip_binding": self.token_ip_binding,
            "token_max_uses": self.token_max_uses,
            "token_lifetime": self.token_lifetime,
            "refresh_token_lifetime": self.refresh_token_lifetime,
        }
        
    def to_json(self) -> str:
        """
        将配置转换为JSON字符串
        
        Returns:
            配置的JSON字符串表示
        """
        return json.dumps(self.to_dict(), indent=2)
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'Config':
        """
        从字典创建配置
        
        Args:
            config_dict: 配置字典
            
        Returns:
            配置对象
        """
        return cls(**config_dict)
    
    @classmethod
    def from_json(cls, config_json: str) -> 'Config':
        """
        从JSON字符串创建配置
        
        Args:
            config_json: 配置JSON字符串
            
        Returns:
            配置对象
        """
        config_dict = json.loads(config_json)
        return cls.from_dict(config_dict)
