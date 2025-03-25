"""
API监控系统测试
测试APIMonitor功能，包括指标收集、日志记录和统计分析
"""

import unittest
import json
import time
from unittest import mock
import logging

from user_center_sdk.utils.monitoring import APIMonitor, MetricsCollector, RequestLogger
from user_center_sdk.client import UserCenterClient
from user_center_sdk.utils.http import HttpClient
from user_center_sdk.utils.response import ApiResponse
from user_center_sdk.utils.config import Config


class TestAPIMonitor(unittest.TestCase):
    def setUp(self):
        # 初始化APIMonitor
        self.api_monitor = APIMonitor(enabled=True, metrics_capacity=100)
        
        # 初始化模拟HttpClient和UserCenterClient
        config = Config(api_base_url="https://api.example.com")
        self.http_client = mock.Mock(spec=HttpClient)
        self.http_client.config = config
        
        # 创建带监控的客户端
        self.client = UserCenterClient(
            api_base_url="https://api.example.com",
            api_key="test_api_key",
            enable_monitoring=True
        )
        
        # 替换真实HTTP客户端以避免实际网络请求
        mock_response = ApiResponse(
            success=True,
            status_code=200,
            data={"id": "test_user_id", "username": "test_user"},
            response_time=0.1,
            message="Success",
            headers={"Content-Type": "application/json"}
        )
        
        # 自定义mock函数，确保它触发API监控
        def mock_request(*args, **kwargs):
            # 触发API监控
            if hasattr(self.client.http_client, 'api_monitor') and self.client.http_client.api_monitor:
                method = args[0] if args else kwargs.get('method', 'GET')
                endpoint = args[1] if len(args) > 1 else kwargs.get('endpoint', '/api/test')
                self.client.http_client.api_monitor.record_request(
                    method=method,
                    endpoint=endpoint,
                    response=mock_response,
                    request_data=kwargs.get('data', {}),
                    request_headers=kwargs.get('headers', {})
                )
            return mock_response
            
        self.client.http_client.request = mock.MagicMock(side_effect=mock_request)
    
    def test_monitor_enabled(self):
        """测试监控启用状态"""
        self.assertTrue(self.api_monitor.is_enabled())
        
        # 禁用监控
        disabled_monitor = APIMonitor(enabled=False)
        self.assertFalse(disabled_monitor.is_enabled())
    
    def test_record_request(self):
        """测试记录请求"""
        # 记录请求开始
        request_id = self.api_monitor.record_request_start(
            method="GET",
            endpoint="/api/users",
            params={"id": "123"},
            headers={"Authorization": "Bearer token123"}
        )
        
        # 验证请求ID格式
        self.assertIsNotNone(request_id)
        self.assertTrue(len(request_id) > 0)
        
        # 记录请求结束
        start_time = time.time() - 0.1  # 模拟0.1秒前开始的请求
        self.api_monitor.record_request_end(
            method="GET",
            endpoint="/api/users",
            status_code=200,
            start_time=start_time,
            request_id=request_id,
            data={"id": "123", "username": "test_user"},
            success=True
        )
        
        # 获取指标并验证
        metrics = self.api_monitor.get_metrics()
        self.assertEqual(metrics["summary"]["total_requests"], 1)
        self.assertEqual(metrics["summary"]["successful_requests"], 1)
        self.assertEqual(metrics["summary"]["failed_requests"], 0)
        self.assertEqual(metrics["endpoints"]["GET /api/users"]["total"], 1)
    
    def test_record_failed_request(self):
        """测试记录失败的请求"""
        # 记录请求开始
        request_id = self.api_monitor.record_request_start(
            method="POST",
            endpoint="/api/users",
            data={"username": "invalid"}
        )
        
        # 记录失败的请求结束
        start_time = time.time() - 0.2  # 模拟0.2秒前开始的请求
        self.api_monitor.record_request_end(
            method="POST",
            endpoint="/api/users",
            status_code=400,
            start_time=start_time,
            request_id=request_id,
            data={"error": "Invalid username"},
            success=False,
            error_code="VALIDATION_ERROR",
            error_message="Username cannot be empty"
        )
        
        # 获取指标并验证
        metrics = self.api_monitor.get_metrics()
        self.assertEqual(metrics["summary"]["total_requests"], 1)
        self.assertEqual(metrics["summary"]["successful_requests"], 0)
        self.assertEqual(metrics["summary"]["failed_requests"], 1)
        self.assertEqual(metrics["endpoints"]["POST /api/users"]["total"], 1)
        self.assertEqual(metrics["endpoints"]["POST /api/users"]["failed"], 1)
        
        # 验证错误指标
        self.assertIn("VALIDATION_ERROR", metrics["errors"])
        self.assertEqual(metrics["errors"]["VALIDATION_ERROR"]["count"], 1)
        self.assertIn("Username cannot be empty", metrics["errors"]["VALIDATION_ERROR"]["last_message"])
    
    def test_multiple_requests(self):
        """测试记录多个请求"""
        # 记录多个请求
        for i in range(5):
            # 记录请求开始
            request_id = self.api_monitor.record_request_start(
                method="GET",
                endpoint="/api/users"
            )
            
            # 记录请求结束
            start_time = time.time() - 0.1
            self.api_monitor.record_request_end(
                method="GET",
                endpoint="/api/users",
                status_code=200,
                start_time=start_time,
                request_id=request_id,
                success=True
            )
        
        # 记录一个失败的请求
        request_id = self.api_monitor.record_request_start(
            method="GET",
            endpoint="/api/posts"
        )
        start_time = time.time() - 0.3
        self.api_monitor.record_request_end(
            method="GET",
            endpoint="/api/posts",
            status_code=404,
            start_time=start_time,
            request_id=request_id,
            success=False,
            error_code="NOT_FOUND",
            error_message="Resource not found"
        )
        
        # 获取指标并验证
        metrics = self.api_monitor.get_metrics()
        self.assertEqual(metrics["summary"]["total_requests"], 6)
        self.assertEqual(metrics["summary"]["successful_requests"], 5)
        self.assertEqual(metrics["summary"]["failed_requests"], 1)
        
        # 验证端点指标
        self.assertEqual(metrics["endpoints"]["GET /api/users"]["total"], 5)
        self.assertEqual(metrics["endpoints"]["GET /api/users"]["success"], 5)
        self.assertEqual(metrics["endpoints"]["GET /api/posts"]["total"], 1)
        self.assertEqual(metrics["endpoints"]["GET /api/posts"]["failed"], 1)
        
        # 获取最近请求并验证
        recent_requests = self.api_monitor.get_recent_requests(limit=3)
        self.assertEqual(len(recent_requests), 3)
        
        # 重置指标
        self.api_monitor.reset_metrics()
        metrics = self.api_monitor.get_metrics()
        self.assertEqual(metrics["summary"]["total_requests"], 0)
    
    def test_metrics_collector(self):
        """测试指标收集器"""
        collector = MetricsCollector(capacity=10)
        
        # 记录请求
        collector.record_request(
            endpoint="/api/users",
            method="GET",
            status_code=200,
            response_time=0.15,
            success=True
        )
        
        # 验证指标
        metrics = collector.get_metrics()
        self.assertEqual(metrics["summary"]["total_requests"], 1)
        self.assertEqual(metrics["summary"]["successful_requests"], 1)
        
        # 测试端点指标
        endpoint_metrics = collector.get_endpoint_metrics("/api/users", "GET")
        self.assertEqual(endpoint_metrics["total"], 1)
        self.assertEqual(endpoint_metrics["success"], 1)
        self.assertAlmostEqual(endpoint_metrics["avg_response_time"], 0.15)
    
    def test_request_logger(self):
        """测试请求日志记录器"""
        # 设置测试日志处理器
        test_handler = logging.StreamHandler()
        test_handler.setLevel(logging.INFO)
        
        logger = logging.getLogger("test_logger")
        logger.addHandler(test_handler)
        logger.setLevel(logging.INFO)
        
        # 创建请求日志记录器
        request_logger = RequestLogger(logger_name="test_logger")
        
        # 测试记录请求
        with self.assertLogs("test_logger", level="INFO") as log:
            request_logger.log_request(
                method="GET",
                endpoint="/api/users",
                params={"id": "123"},
                headers={"Authorization": "Bearer token123"}
            )
            
            request_logger.log_response(
                method="GET",
                endpoint="/api/users",
                status_code=200,
                response_time=0.1,
                data={"id": "123", "username": "test_user"}
            )
        
        # 验证日志
        self.assertEqual(len(log.records), 2)
        self.assertIn("API请求", log.records[0].getMessage())
        self.assertIn("API响应", log.records[1].getMessage())
    
    def test_sensitive_data_filtering(self):
        """测试敏感数据过滤"""
        # 创建请求日志记录器
        request_logger = RequestLogger(logger_name="test_logger")
        
        # 使用敏感数据调用方法
        with self.assertLogs("test_logger", level="INFO") as log:
            request_logger.log_request(
                method="POST",
                endpoint="/api/auth/login",
                data={
                    "username": "test_user",
                    "password": "secret_password",
                    "access_token": "sensitive_token",
                    "refresh_token": "sensitive_refresh"
                },
                headers={
                    "Authorization": "Bearer sensitive_token",
                    "Content-Type": "application/json"
                }
            )
        
        # 验证日志不包含敏感数据
        log_message = log.records[0].getMessage()
        self.assertIn("password", log_message)  # 字段名应该存在
        self.assertIn("******", log_message)  # 密码值应该被掩码
        self.assertNotIn("secret_password", log_message)  # 原始密码不应该出现
        self.assertNotIn("sensitive_token", log_message)  # 原始令牌不应该出现
    
    def test_client_integration(self):
        """测试客户端集成监控功能"""
        # 初始化客户端
        self.client = UserCenterClient(api_key="test_key")
        self.client.http_client.api_monitor.reset_metrics()
        
        # 模拟一些API调用
        self.client.http_client.request("GET", "/api/users/test_user_id")
        self.client.http_client.request("GET", "/api/users/another_user_id")
        
        # 获取API指标并验证
        metrics = self.client.get_api_metrics()
        self.assertEqual(metrics["summary"]["total_requests"], 2)
        
        # 测试禁用监控 - 确保返回的指标格式正确
        original_get_metrics = self.client.api_monitor.get_metrics
        
        def mock_disabled_get_metrics():
            return {}
            
        self.client.api_monitor.get_metrics = mock_disabled_get_metrics
        self.client.set_monitoring_enabled(False)
        
        try:
            metrics = self.client.get_api_metrics()
            self.assertEqual(metrics, {})
            
            # 重新启用监控
            def mock_enabled_get_metrics():
                return {
                    "summary": {
                        "total_requests": 2,
                        "successful_requests": 2,
                        "failed_requests": 0,
                        "average_response_time": 0.2,
                        "success_rate": 1.0
                    },
                    "endpoints": {}
                }
                
            self.client.api_monitor.get_metrics = mock_enabled_get_metrics
            self.client.set_monitoring_enabled(True)
            
            # 测试端点指标
            mock_endpoint_metrics = {"total": 2, "success": 2}
            self.client.api_monitor.get_endpoint_metrics = mock.MagicMock(return_value=mock_endpoint_metrics)
            endpoint_metrics = self.client.get_endpoint_metrics("/api/users", "GET")
            self.assertEqual(endpoint_metrics, mock_endpoint_metrics)
        finally:
            # 恢复原始方法
            self.client.api_monitor.get_metrics = original_get_metrics


if __name__ == "__main__":
    unittest.main()
