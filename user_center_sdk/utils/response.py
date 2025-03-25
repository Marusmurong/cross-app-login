"""
用户中心SDK的API响应类
增强版 - 提供更多功能和改进的错误处理
"""

import json
import time
from typing import Dict, Any, Optional, List, Union


class ApiResponse:
    """
    API响应类，用于统一处理API响应
    增强版 - 提供更多功能和改进的错误处理
    """

    def __init__(
        self,
        success: bool,
        status_code: int,
        data: Dict[str, Any],
        message: str,
        headers: Dict[str, str],
        request_id: Optional[str] = None,
        request_time: Optional[float] = None,
        response_time: Optional[float] = None,
        cache_hit: bool = False,
        errors: Optional[List[Dict[str, Any]]] = None,
        rate_limit_remaining: Optional[int] = None,
        rate_limit_reset: Optional[int] = None,
    ):
        """
        初始化API响应

        Args:
            success: 请求是否成功
            status_code: HTTP状态码
            data: 响应数据
            message: 响应消息
            headers: 响应头
            request_id: 请求ID，用于跟踪
            request_time: 请求发送时间戳
            response_time: 响应接收时间戳
            cache_hit: 是否命中缓存
            errors: 详细错误信息列表
            rate_limit_remaining: 剩余的速率限制次数
            rate_limit_reset: 速率限制重置时间戳
        """
        self.success = success
        self.status_code = status_code
        self.data = data
        self.message = message
        self.headers = headers
        self.request_id = request_id or headers.get("X-Request-ID")
        self.request_time = request_time
        self.response_time = response_time or time.time()
        self.cache_hit = cache_hit
        self.errors = errors or []
        
        # 提取速率限制信息
        self.rate_limit_remaining = rate_limit_remaining or self._extract_rate_limit_remaining()
        self.rate_limit_reset = rate_limit_reset or self._extract_rate_limit_reset()
        
        # 计算响应时间
        self.response_duration = None
        if self.request_time and self.response_time:
            self.response_duration = self.response_time - self.request_time

    def __bool__(self) -> bool:
        """
        将响应转换为布尔值，用于条件判断

        Returns:
            请求是否成功
        """
        return self.success

    def __repr__(self) -> str:
        """
        响应的字符串表示

        Returns:
            响应的字符串表示
        """
        return f"ApiResponse(success={self.success}, status_code={self.status_code}, message={self.message})"

    def _extract_rate_limit_remaining(self) -> Optional[int]:
        """
        从响应头中提取剩余的速率限制次数

        Returns:
            剩余的速率限制次数
        """
        remaining = self.headers.get("X-RateLimit-Remaining")
        if remaining is not None:
            try:
                return int(remaining)
            except (ValueError, TypeError):
                pass
        return None

    def _extract_rate_limit_reset(self) -> Optional[int]:
        """
        从响应头中提取速率限制重置时间戳

        Returns:
            速率限制重置时间戳
        """
        reset = self.headers.get("X-RateLimit-Reset")
        if reset is not None:
            try:
                return int(reset)
            except (ValueError, TypeError):
                pass
        return None

    def json(self) -> Dict[str, Any]:
        """
        将响应转换为JSON格式的字典

        Returns:
            JSON格式的字典
        """
        return {
            "success": self.success,
            "status_code": self.status_code,
            "data": self.data,
            "message": self.message,
            "request_id": self.request_id,
            "response_duration": self.response_duration,
            "cache_hit": self.cache_hit,
            "errors": self.errors,
            "rate_limit": {
                "remaining": self.rate_limit_remaining,
                "reset": self.rate_limit_reset
            }
        }

    def to_dict(self) -> Dict[str, Any]:
        """
        将响应转换为字典，与json()方法相同

        Returns:
            字典
        """
        return self.json()

    def to_json_string(self) -> str:
        """
        将响应转换为JSON字符串

        Returns:
            JSON字符串
        """
        return json.dumps(self.json(), ensure_ascii=False)

    def get_data(self, key: str, default: Any = None) -> Any:
        """
        获取响应数据中的值

        Args:
            key: 键
            default: 默认值

        Returns:
            值
        """
        if not self.data:
            return default
        return self.data.get(key, default)

    def has_error(self, error_code: Union[str, int]) -> bool:
        """
        检查响应是否包含指定的错误代码

        Args:
            error_code: 错误代码

        Returns:
            是否包含指定的错误代码
        """
        if not self.errors:
            return False
        
        for error in self.errors:
            if error.get("code") == error_code:
                return True
        return False

    def add_error(self, code: Union[str, int], message: str, details: Optional[Dict[str, Any]] = None) -> None:
        """
        添加错误信息

        Args:
            code: 错误代码
            message: 错误消息
            details: 错误详情
        """
        self.errors.append({
            "code": code,
            "message": message,
            "details": details or {}
        })
        
    def is_auth_error(self) -> bool:
        """
        检查是否为认证错误
        
        Returns:
            是否为认证错误
        """
        return self.status_code in (401, 403)
    
    def is_rate_limited(self) -> bool:
        """
        检查是否被速率限制
        
        Returns:
            是否被速率限制
        """
        return self.status_code == 429
    
    def is_server_error(self) -> bool:
        """
        检查是否为服务器错误
        
        Returns:
            是否为服务器错误
        """
        return 500 <= self.status_code < 600
    
    def is_client_error(self) -> bool:
        """
        检查是否为客户端错误
        
        Returns:
            是否为客户端错误
        """
        return 400 <= self.status_code < 500 and self.status_code != 401 and self.status_code != 403

    def is_retryable(self) -> bool:
        """
        检查是否可以重试
        
        Returns:
            是否可以重试
        """
        # 服务器错误和特定客户端错误可以重试
        return self.is_server_error() or self.status_code in (408, 429)
