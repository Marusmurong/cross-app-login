"""
用户中心SDK的API监控工具
提供API请求监控、性能分析和错误追踪功能
"""

import time
import json
import logging
import threading
import uuid
from typing import Dict, List, Any, Optional, Tuple, Union, Callable

logger = logging.getLogger(__name__)


class MetricsCollector:
    """
    指标收集器，用于收集API调用指标
    """
    
    def __init__(self, capacity: int = 1000):
        """
        初始化指标收集器
        
        Args:
            capacity: 指标历史记录容量
        """
        self.capacity = capacity
        self.metrics = []
        self.lock = threading.RLock()
        self.started_at = time.time()
        
        # 统计数据
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.total_response_time = 0
        
        # 端点统计
        self.endpoint_metrics: Dict[str, Dict[str, Any]] = {}
        
        # 错误统计
        self.error_metrics: Dict[str, Dict[str, Any]] = {}
        
    def record_request(
        self,
        endpoint: str,
        method: str,
        status_code: int,
        response_time: float,
        success: bool,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> None:
        """
        记录API请求
        
        Args:
            endpoint: API端点
            method: HTTP方法
            status_code: 状态码
            response_time: 响应时间（秒）
            success: 是否成功
            error_code: 错误代码
            error_message: 错误消息
            request_id: 请求ID
        """
        with self.lock:
            # 创建指标记录
            metric = {
                "timestamp": time.time(),
                "endpoint": endpoint,
                "method": method,
                "status_code": status_code,
                "response_time": response_time,
                "success": success,
                "request_id": request_id or str(uuid.uuid4()),
            }
            
            if error_code:
                metric["error_code"] = error_code
                
            if error_message:
                metric["error_message"] = error_message
                
            # 更新统计数据
            self.total_requests += 1
            if success:
                self.successful_requests += 1
            else:
                self.failed_requests += 1
                
            self.total_response_time += response_time
            
            # 更新端点统计
            endpoint_key = f"{method.upper()} {endpoint}"
            if endpoint_key not in self.endpoint_metrics:
                self.endpoint_metrics[endpoint_key] = {
                    "total": 0,
                    "success": 0,
                    "failed": 0,
                    "total_time": 0,
                    "min_time": float('inf'),
                    "max_time": 0,
                }
                
            endpoint_stat = self.endpoint_metrics[endpoint_key]
            endpoint_stat["total"] += 1
            if success:
                endpoint_stat["success"] += 1
            else:
                endpoint_stat["failed"] += 1
                
            endpoint_stat["total_time"] += response_time
            endpoint_stat["min_time"] = min(endpoint_stat["min_time"], response_time)
            endpoint_stat["max_time"] = max(endpoint_stat["max_time"], response_time)
            
            # 更新错误统计
            if not success and error_code:
                if error_code not in self.error_metrics:
                    self.error_metrics[error_code] = {
                        "count": 0,
                        "endpoints": {},
                        "last_message": "",
                        "last_timestamp": 0,
                    }
                    
                error_stat = self.error_metrics[error_code]
                error_stat["count"] += 1
                error_stat["last_message"] = error_message or ""
                error_stat["last_timestamp"] = time.time()
                
                if endpoint_key not in error_stat["endpoints"]:
                    error_stat["endpoints"][endpoint_key] = 0
                    
                error_stat["endpoints"][endpoint_key] += 1
            
            # 添加到历史记录
            self.metrics.append(metric)
            
            # 保持容量限制
            if len(self.metrics) > self.capacity:
                self.metrics.pop(0)
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        获取API监控指标

        Returns:
            dict: 包含各种指标的字典
        """
        with self.lock:
            total_requests = self.total_requests
            successful_requests = self.successful_requests
            failed_requests = self.failed_requests
            
            # 计算平均响应时间
            avg_response_time = 0.0
            if total_requests > 0 and self.total_response_time > 0:
                avg_response_time = self.total_response_time / total_requests
                
            # 计算成功率
            success_rate = 0.0
            if total_requests > 0:
                success_rate = (successful_requests / total_requests) * 100
                
            # 汇总指标
            summary = {
                "total_requests": total_requests,
                "successful_requests": successful_requests,
                "failed_requests": failed_requests,
                "avg_response_time": avg_response_time,
                "success_rate": success_rate,
                "uptime": time.time() - self.started_at,
            }
            
            # 端点指标
            endpoints = {}
            for endpoint, metrics in self.endpoint_metrics.items():
                endpoints[endpoint] = metrics.copy()
                
            # 错误指标
            errors = {}
            for error_type, count in self.error_metrics.items():
                errors[error_type] = count
                
            return {
                "enabled": True,
                "summary": summary,
                "endpoints": endpoints,
                "errors": errors,
            }
    
    def get_recent_requests(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        获取最近的请求记录
        
        Args:
            limit: 最大记录数
            
        Returns:
            最近的请求记录
        """
        with self.lock:
            return self.metrics[-limit:]
    
    def get_endpoint_metrics(self, endpoint: str, method: str) -> Dict[str, Any]:
        """
        获取特定端点的指标
        
        Args:
            endpoint: API端点
            method: HTTP方法
            
        Returns:
            端点指标
        """
        with self.lock:
            endpoint_key = f"{method.upper()} {endpoint}"
            if endpoint_key not in self.endpoint_metrics:
                return {}
                
            stats = self.endpoint_metrics[endpoint_key]
            avg_time = stats["total_time"] / stats["total"] if stats["total"] > 0 else 0
            success_rate = (stats["success"] / stats["total"] * 100) if stats["total"] > 0 else 0
            
            return {
                "total": stats["total"],
                "success": stats["success"],
                "failed": stats["failed"],
                "success_rate": success_rate,
                "avg_response_time": avg_time,
                "min_response_time": stats["min_time"] if stats["min_time"] != float('inf') else 0,
                "max_response_time": stats["max_time"],
            }
    
    def get_error_metrics(self, error_code: str) -> Dict[str, Any]:
        """
        获取特定错误的指标
        
        Args:
            error_code: 错误代码
            
        Returns:
            错误指标
        """
        with self.lock:
            if error_code not in self.error_metrics:
                return {}
                
            stats = self.error_metrics[error_code]
            return {
                "count": stats["count"],
                "last_message": stats["last_message"],
                "last_timestamp": stats["last_timestamp"],
                "top_endpoints": sorted(
                    stats["endpoints"].items(), 
                    key=lambda x: x[1], 
                    reverse=True
                ),
            }
    
    def reset(self) -> None:
        """
        重置所有指标
        """
        with self.lock:
            self.metrics = []
            self.total_requests = 0
            self.successful_requests = 0
            self.failed_requests = 0
            self.total_response_time = 0
            self.endpoint_metrics = {}
            self.error_metrics = {}
            self.started_at = time.time()
            
    def set_test_metrics(self, metrics: Dict[str, Any]) -> None:
        """
        仅用于测试：手动设置API指标
        
        Args:
            metrics: 包含要设置的指标的字典
        """
        with self.lock:
            if "total_requests" in metrics:
                self.total_requests = metrics["total_requests"]
            if "successful_requests" in metrics:
                self.successful_requests = metrics["successful_requests"]
            if "failed_requests" in metrics:
                self.failed_requests = metrics["failed_requests"]
            if "avg_response_time" in metrics and metrics["avg_response_time"] > 0:
                # 创建足够的请求时间记录以产生期望的平均响应时间
                count = max(10, self.total_requests)
                self.total_response_time = metrics["avg_response_time"] * count


class RequestLogger:
    """
    请求日志记录器，用于记录API请求日志
    """
    
    def __init__(self, logger_name: str = "user_center_sdk.api"):
        """
        初始化请求日志记录器
        
        Args:
            logger_name: 日志记录器名称
        """
        self.logger = logging.getLogger(logger_name)
        
    def log_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
    ) -> None:
        """
        记录请求日志
        
        Args:
            method: HTTP方法
            endpoint: API端点
            params: 查询参数
            data: 请求体数据
            headers: 请求头
            request_id: 请求ID
        """
        try:
            # 创建日志数据
            log_data = {
                "type": "request",
                "method": method,
                "endpoint": endpoint,
                "request_id": request_id or str(uuid.uuid4()),
                "timestamp": time.time(),
            }
            
            # 添加可选数据
            if params:
                # 排除敏感数据
                safe_params = self._sanitize_data(params)
                log_data["params"] = safe_params
                
            if data:
                # 排除敏感数据
                safe_data = self._sanitize_data(data)
                log_data["data"] = safe_data
                
            if headers:
                # 排除敏感数据
                safe_headers = self._sanitize_headers(headers)
                log_data["headers"] = safe_headers
                
            # 记录日志
            self.logger.info(f"API请求: {json.dumps(log_data)}")
            
        except Exception as e:
            self.logger.error(f"记录请求日志时发生异常: {str(e)}")
    
    def log_response(
        self,
        method: str,
        endpoint: str,
        status_code: int,
        response_time: float,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        """
        记录响应日志
        
        Args:
            method: HTTP方法
            endpoint: API端点
            status_code: 状态码
            response_time: 响应时间（秒）
            data: 响应数据
            headers: 响应头
            request_id: 请求ID
            error: 错误消息
        """
        try:
            # 创建日志数据
            log_data = {
                "type": "response",
                "method": method,
                "endpoint": endpoint,
                "status_code": status_code,
                "response_time": response_time,
                "request_id": request_id or str(uuid.uuid4()),
                "timestamp": time.time(),
            }
            
            # 添加可选数据
            if data:
                # 排除敏感数据
                safe_data = self._sanitize_data(data)
                log_data["data"] = safe_data
                
            if headers:
                # 排除敏感数据
                safe_headers = self._sanitize_headers(headers)
                log_data["headers"] = safe_headers
                
            if error:
                log_data["error"] = error
                
            # 根据状态码使用不同的日志级别
            if 200 <= status_code < 300:
                self.logger.info(f"API响应: {json.dumps(log_data)}")
            elif 400 <= status_code < 500:
                self.logger.warning(f"API响应: {json.dumps(log_data)}")
            else:
                self.logger.error(f"API响应: {json.dumps(log_data)}")
                
        except Exception as e:
            self.logger.error(f"记录响应日志时发生异常: {str(e)}")
    
    def _sanitize_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        清理数据，排除敏感信息
        
        Args:
            data: 原始数据
            
        Returns:
            清理后的数据
        """
        if not data:
            return {}
            
        # 创建副本
        clean_data = data.copy()
        
        # 敏感字段列表
        sensitive_fields = [
            "password", "token", "access_token", "refresh_token", 
            "secret", "api_key", "private_key", "auth_token",
            "credential", "secret_key", "auth_secret", "sso_token"
        ]
        
        # 排除敏感字段
        for field in sensitive_fields:
            if field in clean_data:
                clean_data[field] = "******"
                
        return clean_data
    
    def _sanitize_headers(self, headers: Dict[str, Any]) -> Dict[str, Any]:
        """
        清理请求/响应头，排除敏感信息
        
        Args:
            headers: 原始请求/响应头
            
        Returns:
            清理后的请求/响应头
        """
        if not headers:
            return {}
            
        # 创建副本
        clean_headers = headers.copy()
        
        # 敏感头列表
        sensitive_headers = [
            "Authorization", "Cookie", "Set-Cookie", 
            "X-API-Key", "Api-Key", "X-Auth-Token"
        ]
        
        # 排除敏感头
        for header in sensitive_headers:
            if header in clean_headers:
                clean_headers[header] = "******"
                
        return clean_headers


class APIMonitor:
    """
    API监控器，集成指标收集和日志记录
    """
    
    def __init__(
        self,
        enabled: bool = True,
        metrics_capacity: int = 1000,
        logger_name: str = "user_center_sdk.api",
    ):
        """
        初始化API监控器
        
        Args:
            enabled: 是否启用监控
            metrics_capacity: 指标历史记录容量
            logger_name: 日志记录器名称
        """
        self.enabled = enabled
        self.metrics_collector = MetricsCollector(metrics_capacity) if enabled else None
        self.request_logger = RequestLogger(logger_name) if enabled else None
        
    def is_enabled(self) -> bool:
        """
        检查监控是否启用
        
        Returns:
            是否启用
        """
        return self.enabled and self.metrics_collector is not None and self.request_logger is not None
    
    def record_request_start(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        记录请求开始
        
        Args:
            method: HTTP方法
            endpoint: API端点
            params: 查询参数
            data: 请求体数据
            headers: 请求头
            
        Returns:
            请求ID
        """
        if not self.is_enabled():
            return str(uuid.uuid4())
            
        request_id = str(uuid.uuid4())
        
        # 记录日志
        self.request_logger.log_request(
            method=method,
            endpoint=endpoint,
            params=params,
            data=data,
            headers=headers,
            request_id=request_id,
        )
        
        return request_id
    
    def record_request_end(
        self,
        method: str,
        endpoint: str,
        status_code: int,
        start_time: float,
        request_id: str,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, Any]] = None,
        success: bool = True,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """
        记录请求结束
        
        Args:
            method: HTTP方法
            endpoint: API端点
            status_code: 状态码
            start_time: 请求开始时间
            request_id: 请求ID
            data: 响应数据
            headers: 响应头
            success: 是否成功
            error_code: 错误代码
            error_message: 错误消息
        """
        if not self.is_enabled():
            return
            
        # 计算响应时间
        response_time = time.time() - start_time
        
        # 记录日志
        self.request_logger.log_response(
            method=method,
            endpoint=endpoint,
            status_code=status_code,
            response_time=response_time,
            data=data,
            headers=headers,
            request_id=request_id,
            error=error_message,
        )
        
        # 记录指标
        self.metrics_collector.record_request(
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            response_time=response_time,
            success=success,
            error_code=error_code,
            error_message=error_message,
            request_id=request_id,
        )
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        获取指标统计数据
        
        Returns:
            指标统计数据
        """
        if not self.is_enabled():
            return {"enabled": False}
            
        return {
            "enabled": True,
            **self.metrics_collector.get_metrics(),
        }
    
    def reset_metrics(self) -> None:
        """
        重置指标
        """
        if not self.is_enabled():
            return
            
        self.metrics_collector.reset()
    
    def get_recent_requests(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        获取最近的请求记录
        
        Args:
            limit: 最大记录数
            
        Returns:
            最近的请求记录
        """
        if not self.is_enabled():
            return []
            
        return self.metrics_collector.get_recent_requests(limit)
    
    def get_endpoint_metrics(self, endpoint: str, method: str) -> Dict[str, Any]:
        """
        获取特定端点的指标
        
        Args:
            endpoint: API端点
            method: HTTP方法
            
        Returns:
            端点指标
        """
        if not self.is_enabled():
            return {}
            
        return self.metrics_collector.get_endpoint_metrics(endpoint, method)
    
    def record_request(
        self,
        method: str,
        endpoint: str,
        response=None,
        cache_hit: bool = False,
        request_data: Optional[Dict[str, Any]] = None,
        request_headers: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        """
        记录完整的API请求和响应

        Args:
            method: HTTP方法
            endpoint: API端点
            response: API响应对象
            cache_hit: 是否命中缓存
            request_data: 请求数据
            request_headers: 请求头
            error: 错误信息
        """
        if not self.is_enabled():
            return

        # 如果没有有效的响应对象，则返回
        if response is None:
            return

        # 从响应对象提取信息
        status_code = getattr(response, "status_code", 0)
        success = getattr(response, "success", False)
        response_data = getattr(response, "data", {})
        response_headers = getattr(response, "headers", {})
        request_id = getattr(response, "request_id", str(uuid.uuid4()))
        
        # 获取响应时间信息
        request_time = getattr(response, "request_time", time.time() - 0.1)
        response_time = getattr(response, "response_time", time.time())
        
        # 计算响应时间差
        response_time_diff = response_time - request_time if request_time else 0.0
        
        # 构建错误代码和错误消息
        error_code = None
        error_message = None
        
        if not success:
            # 从响应中提取错误信息
            errors = getattr(response, "errors", [])
            if errors and isinstance(errors, list) and len(errors) > 0:
                first_error = errors[0]
                if isinstance(first_error, dict):
                    error_code = first_error.get("code", "UNKNOWN_ERROR")
                    error_message = first_error.get("message", str(error) if error else "未知错误")
            elif error:
                error_code = "API_ERROR"
                error_message = str(error)
            elif hasattr(response, "message") and response.message:
                error_code = "API_ERROR"
                error_message = response.message
                
        # 记录请求日志
        if request_headers or request_data:
            self.request_logger.log_request(
                method=method,
                endpoint=endpoint,
                params={} if not request_data else request_data,
                headers=request_headers or {},
                request_id=request_id
            )
            
        # 记录响应日志
        self.request_logger.log_response(
            method=method,
            endpoint=endpoint,
            status_code=status_code,
            response_time=response_time_diff,
            data=response_data,
            headers=response_headers,
            request_id=request_id,
            error=error_message
        )
        
        # 记录指标
        self.metrics_collector.record_request(
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            response_time=response_time_diff,
            success=success,
            error_code=error_code,
            error_message=error_message,
            request_id=request_id
        )

    def set_test_metrics(self, metrics: Dict[str, Any]) -> None:
        """
        仅用于测试：手动设置API指标
        
        Args:
            metrics: 包含要设置的指标的字典
        """
        if not self.is_enabled():
            return
            
        self.metrics_collector.set_test_metrics(metrics)
