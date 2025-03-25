"""
用户中心SDK的HTTP客户端
增强版 - 实现连接池管理、断路器模式和性能跟踪
"""

import json
import time
import uuid
import hashlib
import logging
import threading
from typing import Dict, Any, Optional, Union, List, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import Config
from .response import ApiResponse
from .circuit_breaker import CircuitBreakerRegistry
from .cache import CacheManager, generate_cache_key

logger = logging.getLogger(__name__)


class HttpClient:
    """
    用户中心SDK的HTTP客户端类，处理所有HTTP请求
    增强版 - 实现连接池管理、断路器模式和性能跟踪
    """

    def __init__(
        self,
        config: Config,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
        api_monitor=None,
    ):
        """
        初始化HTTP客户端

        Args:
            config: SDK配置
            access_token: 访问令牌
            refresh_token: 刷新令牌
            api_monitor: API监控对象
        """
        self.config = config
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.api_monitor = api_monitor
        
        # 创建会话和初始化断路器
        self.session = self._create_session()
        self._init_circuit_breakers()
        
        # 初始化性能跟踪
        self.request_times = []
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.performance_lock = threading.RLock()
        
        # 初始化缓存管理器
        self._init_cache_manager()
        
        # 初始化令牌刷新锁
        self.token_refresh_lock = threading.RLock()

    def _create_session(self) -> requests.Session:
        """
        创建并配置请求会话

        Returns:
            配置好的requests.Session对象
        """
        session = requests.Session()
        
        # 配置重试策略
        retry_strategy = Retry(
            total=self.config.max_retries,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
            respect_retry_after_header=True,
        )
        
        # 配置连接池
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=self.config.pool_connections,
            pool_maxsize=self.config.pool_maxsize,
            pool_block=True
        )
        
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session

    def _init_circuit_breakers(self) -> None:
        """
        初始化断路器
        """
        if hasattr(self.config, "circuit_breaker_enabled") and self.config.circuit_breaker_enabled:
            self.circuit_breaker_registry = CircuitBreakerRegistry()
            self.global_circuit_breaker = self.circuit_breaker_registry.get_or_create(
                name="global",
                failure_threshold=self.config.circuit_breaker_failure_threshold,
                recovery_timeout=self.config.circuit_breaker_recovery_timeout,
            )
        else:
            self.circuit_breaker_registry = None
            self.global_circuit_breaker = None
    
    def _init_cache_manager(self) -> None:
        """
        初始化缓存管理器
        """
        if hasattr(self.config, "cache_enabled") and self.config.cache_enabled:
            self.cache = CacheManager(
                enabled=self.config.cache_enabled,
                backend=getattr(self.config, "cache_backend", "memory"),
                ttl=self.config.cache_timeout,
                namespace=getattr(self.config, "cache_namespace", "user_center_sdk"),
                redis_url=getattr(self.config, "cache_redis_url", "redis://localhost:6379/0"),
                max_memory_size=1000,
            )
        else:
            self.cache = None

    def set_tokens(self, access_token: str, refresh_token: str) -> None:
        """
        设置访问令牌和刷新令牌

        Args:
            access_token: 访问令牌
            refresh_token: 刷新令牌
        """
        self.access_token = access_token
        self.refresh_token = refresh_token
        
        # 当令牌更改时清除缓存
        if self.cache:
            self.cache.clear()

    def clear_tokens(self) -> None:
        """
        清除访问令牌和刷新令牌
        """
        self.access_token = None
        self.refresh_token = None
        
        # 当令牌清除时清除缓存
        if self.cache:
            self.cache.clear()

    def _get_headers(self, additional_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """
        获取请求头

        Args:
            additional_headers: 额外的请求头

        Returns:
            完整的请求头字典
        """
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": f"UserCenterSDK/2.0",
            "X-Request-ID": str(uuid.uuid4()),
        }
        
        # 如果有访问令牌，添加到请求头
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        
        # 添加额外的请求头
        if additional_headers:
            headers.update(additional_headers)
        
        return headers

    def _build_url(self, endpoint: str) -> str:
        """
        构建完整的API URL

        Args:
            endpoint: API端点路径

        Returns:
            完整的API URL
        """
        # 确保endpoint不以斜杠开头
        if endpoint.startswith("/"):
            endpoint = endpoint[1:]
        
        return f"{self.config.api_base_url}{endpoint}"

    def _handle_response(
        self, 
        response: requests.Response, 
        request_time: float, 
        cache_hit: bool = False
    ) -> ApiResponse:
        """
        处理API响应

        Args:
            response: requests.Response对象
            request_time: 请求发送时间戳
            cache_hit: 是否命中缓存

        Returns:
            ApiResponse对象
        """
        try:
            # 尝试解析JSON响应
            data = response.json() if response.content else {}
            
            # 提取响应中的错误信息
            errors = []
            if isinstance(data, dict) and "errors" in data and isinstance(data["errors"], list):
                errors = data["errors"]
            
            # 记录响应时间
            response_time = time.time()
            
            # 检查响应状态码
            if 200 <= response.status_code < 300:
                # 记录成功请求
                with self.performance_lock:
                    self.successful_requests += 1
                    self.total_requests += 1
                    
                    # 记录请求时间（仅非缓存命中的请求）
                    if not cache_hit:
                        self.request_times.append(response_time - request_time)
                        # 只保留最近100个请求的时间
                        if len(self.request_times) > 100:
                            self.request_times.pop(0)
                
                # 如果使用断路器，记录成功
                if self.global_circuit_breaker:
                    self.global_circuit_breaker.record_success()
                
                # 确保success为True
                success = True
                message = data.get("message", "请求成功") if isinstance(data, dict) else "请求成功"
                
                return ApiResponse(
                    success=success,
                    status_code=response.status_code,
                    data=data,
                    message=message,
                    headers=dict(response.headers),
                    request_id=response.headers.get("X-Request-ID"),
                    request_time=request_time,
                    response_time=response_time,
                    cache_hit=cache_hit,
                    errors=errors,
                )
            else:
                # 记录失败请求
                with self.performance_lock:
                    self.failed_requests += 1
                    self.total_requests += 1
                
                # 处理错误响应
                message = data.get("message", data.get("detail", "请求失败"))
                if isinstance(message, list) and len(message) > 0:
                    message = message[0]
                
                # 如果使用断路器，记录失败（对于特定状态码）
                if self.global_circuit_breaker and response.status_code in [500, 502, 503, 504]:
                    self.global_circuit_breaker.record_failure()
                
                return ApiResponse(
                    success=False,
                    status_code=response.status_code,
                    data=data,
                    message=message,
                    headers=dict(response.headers),
                    request_id=response.headers.get("X-Request-ID"),
                    request_time=request_time,
                    response_time=response_time,
                    cache_hit=cache_hit,
                    errors=errors,
                )
        except ValueError as e:
            # JSON解析错误
            with self.performance_lock:
                self.failed_requests += 1
                self.total_requests += 1
            
            # 如果使用断路器，记录失败
            if self.global_circuit_breaker:
                self.global_circuit_breaker.record_failure()
                
            return ApiResponse(
                success=False,
                status_code=response.status_code,
                data={},
                message=f"无法解析响应: {str(e)}",
                headers=dict(response.headers),
                request_id=response.headers.get("X-Request-ID"),
                request_time=request_time,
                response_time=time.time(),
                errors=[{"code": "PARSE_ERROR", "message": str(e)}],
            )
        except Exception as e:
            # 处理其他异常
            with self.performance_lock:
                self.failed_requests += 1
                self.total_requests += 1
                
            # 如果使用断路器，记录失败
            if self.global_circuit_breaker:
                self.global_circuit_breaker.record_failure()
            
            logger.exception(f"处理响应时发生异常: {str(e)}")
            return ApiResponse(
                success=False,
                status_code=response.status_code if hasattr(response, "status_code") else 500,
                data={},
                message=f"处理响应时发生异常: {str(e)}",
                headers=dict(response.headers) if hasattr(response, "headers") else {},
                request_id=response.headers.get("X-Request-ID") if hasattr(response, "headers") else None,
                request_time=request_time,
                response_time=time.time(),
                errors=[{"code": "UNEXPECTED_ERROR", "message": str(e)}],
            )

    def _should_refresh_token(self, response: ApiResponse) -> bool:
        """
        判断是否应该刷新令牌

        Args:
            response: ApiResponse对象

        Returns:
            是否应该刷新令牌
        """
        # 如果响应状态码为401（未授权）且配置了自动刷新令牌，则尝试刷新令牌
        return (
            response.status_code == 401
            and self.config.auto_refresh_token
            and self.refresh_token is not None
        )

    def _refresh_token(self) -> Tuple[bool, Optional[str]]:
        """
        刷新访问令牌

        Returns:
            (是否成功, 错误消息)
        """
        # 使用线程锁确保只有一个线程在刷新令牌
        with self.token_refresh_lock:
            try:
                # 构建刷新令牌请求
                url = self._build_url("user/token/refresh/")
                headers = {"Content-Type": "application/json", "Accept": "application/json"}
                data = {"refresh": self.refresh_token}
                
                # 发送请求
                response = self.session.post(
                    url=url,
                    headers=headers,
                    json=data,
                    timeout=(
                        self.config.connect_timeout if hasattr(self.config, "connect_timeout") else self.config.timeout,
                        self.config.read_timeout if hasattr(self.config, "read_timeout") else self.config.timeout,
                    ),
                    verify=getattr(self.config, "verify_ssl", True),
                )
                
                # 处理响应
                if response.status_code == 200:
                    data = response.json()
                    self.access_token = data.get("access")
                    # 有些API会在刷新时同时返回新的刷新令牌
                    if "refresh" in data:
                        self.refresh_token = data.get("refresh")
                    
                    # 当令牌更改时清除缓存
                    if self.cache:
                        self.cache.clear()
                        
                    return True, None
                else:
                    # 刷新失败，清除令牌
                    self.clear_tokens()
                    return False, f"刷新令牌失败: {response.text}"
                    
            except Exception as e:
                # 发生异常，清除令牌
                self.clear_tokens()
                return False, f"刷新令牌时发生异常: {str(e)}"

    def request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        files: Optional[Dict[str, Any]] = None,
        retry_on_auth_failure: bool = True,
        cache_ttl: Optional[int] = None,
        use_cache: bool = True,
    ) -> ApiResponse:
        """
        发送HTTP请求

        Args:
            method: HTTP方法（GET, POST, PUT, DELETE, PATCH）
            endpoint: API端点路径
            data: 请求体数据
            params: URL查询参数
            headers: 额外的请求头
            files: 要上传的文件
            retry_on_auth_failure: 认证失败时是否重试
            cache_ttl: 缓存生存时间（秒）
            use_cache: 是否使用缓存（仅对GET请求有效）

        Returns:
            ApiResponse对象
        """
        # 检查是否应该使用缓存
        can_use_cache = (
            self.cache is not None
            and use_cache
            and method.upper() == "GET"
            and not files
            and not (self.config.token_ip_binding if hasattr(self.config, "token_ip_binding") else False)
        )
        
        # 如果可以使用缓存，尝试从缓存获取
        if can_use_cache:
            cache_key = generate_cache_key(
                f"http:{method.lower()}:{endpoint}",
                params=params,
                access_token=self.access_token[:8] if self.access_token else None,
            )
            cached_response, cache_hit = self.cache.get(cache_key)
            if cache_hit:
                logger.debug(f"缓存命中: {cache_key}")
                
                # 记录缓存命中的API请求（如果启用了监控）
                if self.api_monitor:
                    self.api_monitor.record_request(
                        method=method,
                        endpoint=endpoint,
                        response=cached_response,
                        cache_hit=True
                    )
                
                return cached_response
        
        # 检查断路器状态
        if self.global_circuit_breaker and not self.global_circuit_breaker.allow_request():
            # 断路器打开，拒绝请求
            logger.warning(f"断路器已打开，请求被拒绝: {method} {endpoint}")
            api_response = ApiResponse(
                success=False,
                status_code=503,
                data={},
                message="服务暂时不可用，请稍后重试",
                headers={},
                errors=[{"code": "CIRCUIT_BREAKER_OPEN", "message": "服务暂时不可用，请稍后重试"}],
            )
            
            # 记录断路器拒绝的API请求（如果启用了监控）
            if self.api_monitor:
                self.api_monitor.record_request(
                    method=method,
                    endpoint=endpoint,
                    response=api_response,
                    cache_hit=False
                )
            
            return api_response
        
        url = self._build_url(endpoint)
        request_headers = self._get_headers(headers)
        request_time = time.time()
        
        try:
            # 发送请求
            response = self.session.request(
                method=method,
                url=url,
                json=data if data and not files else None,
                data=data if files else None,
                params=params,
                headers=request_headers,
                files=files,
                timeout=(
                    self.config.connect_timeout if hasattr(self.config, "connect_timeout") else self.config.timeout,
                    self.config.read_timeout if hasattr(self.config, "read_timeout") else self.config.timeout,
                ),
                verify=getattr(self.config, "verify_ssl", True),
            )
            
            # 处理响应
            api_response = self._handle_response(response, request_time)
            
            # 记录成功的API请求（如果启用了监控）
            if self.api_monitor:
                self.api_monitor.record_request(
                    method=method,
                    endpoint=endpoint,
                    response=api_response,
                    cache_hit=False,
                    request_data=data,
                    request_headers=request_headers
                )
            
            # 如果需要刷新令牌
            if self._should_refresh_token(api_response) and retry_on_auth_failure:
                success, error = self._refresh_token()
                if success:
                    # 令牌刷新成功，重试请求
                    logger.debug("令牌已刷新，重试请求")
                    return self.request(
                        method=method,
                        endpoint=endpoint,
                        data=data,
                        params=params,
                        headers=headers,
                        files=files,
                        retry_on_auth_failure=False,  # 防止无限循环
                        cache_ttl=cache_ttl,
                        use_cache=use_cache,
                    )
                else:
                    # 令牌刷新失败
                    logger.warning(f"令牌刷新失败: {error}")
            
            # 如果请求成功且可以使用缓存，将响应保存到缓存
            if can_use_cache and api_response.success:
                self.cache.set(
                    cache_key,
                    api_response,
                    ttl=cache_ttl or self.config.cache_timeout,
                )
            
            return api_response
            
        except requests.RequestException as e:
            # 处理请求异常
            with self.performance_lock:
                self.failed_requests += 1
                self.total_requests += 1
                
            # 如果使用断路器，记录失败
            if self.global_circuit_breaker:
                self.global_circuit_breaker.record_failure()
            
            error_response = ApiResponse(
                success=False,
                status_code=getattr(e.response, "status_code", 500) if hasattr(e, "response") else 500,
                data={},
                message=f"发送请求时发生异常: {str(e)}",
                headers=getattr(e.response, "headers", {}) if hasattr(e, "response") else {},
                request_id=getattr(e.response, "headers", {}).get("X-Request-ID") if hasattr(e, "response") else None,
                request_time=request_time,
                response_time=time.time(),
                errors=[{"code": "REQUEST_ERROR", "message": str(e)}],
            )
            
            # 记录失败的API请求（如果启用了监控）
            if self.api_monitor:
                self.api_monitor.record_request(
                    method=method,
                    endpoint=endpoint,
                    response=error_response,
                    cache_hit=False,
                    request_data=data,
                    request_headers=request_headers,
                    error=str(e)
                )
                
            logger.exception(f"发送请求时发生异常: {str(e)}")
            return error_response
            
        except Exception as e:
            # 处理其他异常
            with self.performance_lock:
                self.failed_requests += 1
                self.total_requests += 1
                
            # 如果使用断路器，记录失败
            if self.global_circuit_breaker:
                self.global_circuit_breaker.record_failure()
            
            error_response = ApiResponse(
                success=False,
                status_code=500,
                data={},
                message=f"发送请求时发生未知异常: {str(e)}",
                headers={},
                request_time=request_time,
                response_time=time.time(),
                errors=[{"code": "UNEXPECTED_ERROR", "message": str(e)}],
            )
            
            # 记录失败的API请求（如果启用了监控）
            if self.api_monitor:
                self.api_monitor.record_request(
                    method=method,
                    endpoint=endpoint,
                    response=error_response,
                    cache_hit=False,
                    request_data=data,
                    request_headers=request_headers,
                    error=str(e)
                )
                
            logger.exception(f"发送请求时发生未知异常: {str(e)}")
            return error_response

    def get(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        cache_ttl: Optional[int] = None,
        use_cache: bool = True,
    ) -> ApiResponse:
        """
        发送GET请求

        Args:
            endpoint: API端点路径
            params: URL查询参数
            headers: 额外的请求头
            cache_ttl: 缓存生存时间（秒）
            use_cache: 是否使用缓存

        Returns:
            ApiResponse对象
        """
        return self.request(
            method="GET",
            endpoint=endpoint,
            params=params,
            headers=headers,
            cache_ttl=cache_ttl,
            use_cache=use_cache,
        )

    def post(
        self,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        files: Optional[Dict[str, Any]] = None,
    ) -> ApiResponse:
        """
        发送POST请求

        Args:
            endpoint: API端点路径
            data: 请求体数据
            params: URL查询参数
            headers: 额外的请求头
            files: 要上传的文件

        Returns:
            ApiResponse对象
        """
        return self.request(
            method="POST",
            endpoint=endpoint,
            data=data,
            params=params,
            headers=headers,
            files=files,
            use_cache=False,
        )

    def put(
        self,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        files: Optional[Dict[str, Any]] = None,
    ) -> ApiResponse:
        """
        发送PUT请求

        Args:
            endpoint: API端点路径
            data: 请求体数据
            params: URL查询参数
            headers: 额外的请求头
            files: 要上传的文件

        Returns:
            ApiResponse对象
        """
        return self.request(
            method="PUT",
            endpoint=endpoint,
            data=data,
            params=params,
            headers=headers,
            files=files,
            use_cache=False,
        )

    def patch(
        self,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        files: Optional[Dict[str, Any]] = None,
    ) -> ApiResponse:
        """
        发送PATCH请求

        Args:
            endpoint: API端点路径
            data: 请求体数据
            params: URL查询参数
            headers: 额外的请求头
            files: 要上传的文件

        Returns:
            ApiResponse对象
        """
        return self.request(
            method="PATCH",
            endpoint=endpoint,
            data=data,
            params=params,
            headers=headers,
            files=files,
            use_cache=False,
        )

    def delete(
        self,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> ApiResponse:
        """
        发送DELETE请求

        Args:
            endpoint: API端点路径
            data: 请求体数据
            params: URL查询参数
            headers: 额外的请求头

        Returns:
            ApiResponse对象
        """
        return self.request(
            method="DELETE",
            endpoint=endpoint,
            data=data,
            params=params,
            headers=headers,
            use_cache=False,
        )
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """
        获取性能统计信息
        
        Returns:
            性能统计信息
        """
        with self.performance_lock:
            stats = {
                "total_requests": self.total_requests,
                "successful_requests": self.successful_requests,
                "failed_requests": self.failed_requests,
                "success_rate": (self.successful_requests / self.total_requests * 100) if self.total_requests > 0 else 0,
                "average_response_time": sum(self.request_times) / len(self.request_times) if self.request_times else 0,
                "min_response_time": min(self.request_times) if self.request_times else 0,
                "max_response_time": max(self.request_times) if self.request_times else 0,
            }
            
            # 添加断路器信息
            if self.global_circuit_breaker:
                stats["circuit_breaker"] = self.global_circuit_breaker.get_metrics()
            
            # 添加缓存信息
            if self.cache:
                stats["cache"] = self.cache.get_stats()
                
            return stats
