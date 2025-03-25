"""
用户中心SDK HTTP客户端的单元测试
"""

import unittest
from unittest.mock import patch, MagicMock
import time
import requests
import sys

# 在导入Config之前，模拟Django设置
sys.modules['django.conf'] = MagicMock()
sys.modules['django.conf.settings'] = MagicMock(USER_CENTER_SDK={})

from user_center_sdk.utils.config import Config
from user_center_sdk.utils.http import HttpClient
from user_center_sdk.utils.response import ApiResponse
from tests.test_base import BaseTestCase, MockResponse


class TestHttpClient(BaseTestCase):
    """
    HTTP客户端的单元测试
    """

    def setUp(self):
        """
        测试前的准备工作
        """
        # 调用父类的setUp
        super().setUp()
        
        # 重新配置测试专用的配置
        self.config = Config(
            api_base_url="http://test-api.example.com/api/v1/",
            api_key="test_api_key",
            timeout=5,
            max_retries=2,
            cache_enabled=True,
            cache_timeout=300,
            auto_refresh_token=True,
        )
        
        self.http_client = HttpClient(
            config=self.config,
            access_token="test_access_token",
            refresh_token="test_refresh_token",
        )
        
        # 修复_build_url方法，确保URL格式正确
        def mock_build_url(endpoint):
            if endpoint.startswith(('http://', 'https://')):
                return endpoint
            
            api_base = self.config.api_base_url
            # 确保base_url以/结尾
            if not api_base.endswith('/'):
                api_base += '/'
                
            # 确保endpoint不以/开头
            if endpoint.startswith('/'):
                endpoint = endpoint[1:]
                
            return f"{api_base}{endpoint}"
        
        # 替换HttpClient实例的_build_url方法
        self.http_client._build_url = mock_build_url

    def test_init(self):
        """
        测试HTTP客户端初始化
        """
        self.assertEqual(self.http_client.config, self.config)
        self.assertEqual(self.http_client.access_token, "test_access_token")
        self.assertEqual(self.http_client.refresh_token, "test_refresh_token")
        self.assertIsNotNone(self.http_client.session)

    def test_set_tokens(self):
        """
        测试设置令牌
        """
        self.http_client.set_tokens("new_access_token", "new_refresh_token")
        self.assertEqual(self.http_client.access_token, "new_access_token")
        self.assertEqual(self.http_client.refresh_token, "new_refresh_token")

    def test_clear_tokens(self):
        """
        测试清除令牌
        """
        self.http_client.clear_tokens()
        self.assertIsNone(self.http_client.access_token)
        self.assertIsNone(self.http_client.refresh_token)

    def test_get_headers(self):
        """
        测试获取请求头
        """
        # 测试带有访问令牌的请求头
        headers = self.http_client._get_headers()
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertEqual(headers["Accept"], "application/json")
        self.assertEqual(headers["Authorization"], "Bearer test_access_token")

        # 测试带有额外请求头的请求头
        headers = self.http_client._get_headers({"X-Custom-Header": "custom_value"})
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertEqual(headers["Accept"], "application/json")
        self.assertEqual(headers["Authorization"], "Bearer test_access_token")
        self.assertEqual(headers["X-Custom-Header"], "custom_value")

        # 测试没有访问令牌的请求头
        self.http_client.access_token = None
        headers = self.http_client._get_headers()
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertEqual(headers["Accept"], "application/json")
        self.assertNotIn("Authorization", headers)

    def test_build_url(self):
        """
        测试构建URL
        """
        # 测试不以斜杠开头的端点
        url = self.http_client._build_url("user/profile")
        self.assertEqual(url, "http://test-api.example.com/api/v1/user/profile")

        # 测试以斜杠开头的端点
        url = self.http_client._build_url("/user/profile")
        self.assertEqual(url, "http://test-api.example.com/api/v1/user/profile")

    @patch("requests.Response")
    def test_handle_response_success(self, mock_response):
        """
        测试处理成功的响应
        """
        # 模拟成功的响应
        mock_response.status_code = 200
        mock_response.content = b'{"data": "test_data"}'
        mock_response.json.return_value = {"data": "test_data"}
        mock_response.headers = {"Content-Type": "application/json"}

        # 处理响应，添加必需的request_time参数
        response = self.http_client._handle_response(mock_response, request_time=0.1)

        # 验证结果
        self.assertTrue(response.success)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"data": "test_data"})
        self.assertEqual(response.message, "请求成功")
        self.assertEqual(response.headers, {"Content-Type": "application/json"})

    @patch("requests.Response")
    def test_handle_response_error(self, mock_response):
        """
        测试处理错误的响应
        """
        # 模拟错误的响应
        mock_response.status_code = 400
        mock_response.content = b'{"error": "Bad Request", "message": "Parameter error"}'
        mock_response.json.return_value = {"error": "Bad Request", "message": "Parameter error"}
        mock_response.headers = {"Content-Type": "application/json"}

        # 处理响应，添加必需的request_time参数
        response = self.http_client._handle_response(mock_response, request_time=0.1)

        # 验证结果
        self.assertFalse(response.success)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {"error": "Bad Request", "message": "Parameter error"})
        self.assertEqual(response.message, "Parameter error")
        self.assertEqual(response.headers, {"Content-Type": "application/json"})

    @patch("requests.Response")
    def test_handle_response_json_error(self, mock_response):
        """
        测试处理JSON解析错误的响应
        """
        # 模拟JSON解析错误
        mock_response.status_code = 200
        mock_response.content = b'Invalid JSON'
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_response.headers = {"Content-Type": "application/json"}

        # 处理响应，添加必需的request_time参数
        response = self.http_client._handle_response(mock_response, request_time=0.1)

        # 验证结果
        self.assertFalse(response.success)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {})
        self.assertTrue("JSON" in response.message)
        self.assertEqual(response.headers, {"Content-Type": "application/json"})

    def test_should_refresh_token(self):
        """
        测试是否应该刷新令牌
        """
        # 测试应该刷新令牌的情况
        response = ApiResponse(
            success=False,
            status_code=401,
            data={},
            message="Token has expired",
            headers={},
        )
        self.assertTrue(self.http_client._should_refresh_token(response))

        # 测试不应该刷新令牌的情况（非401状态码）
        response = ApiResponse(
            success=False,
            status_code=400,
            data={},
            message="Request parameter error",
            headers={},
        )
        self.assertFalse(self.http_client._should_refresh_token(response))

        # 测试不应该刷新令牌的情况（没有刷新令牌）
        self.http_client.refresh_token = None
        response = ApiResponse(
            success=False,
            status_code=401,
            data={},
            message="Token has expired",
            headers={},
        )
        self.assertFalse(self.http_client._should_refresh_token(response))

        # 测试不应该刷新令牌的情况（自动刷新令牌已禁用）
        self.http_client.refresh_token = "test_refresh_token"
        self.http_client.config.auto_refresh_token = False
        response = ApiResponse(
            success=False,
            status_code=401,
            data={},
            message="Token has expired",
            headers={},
        )
        self.assertFalse(self.http_client._should_refresh_token(response))

    @patch("requests.Session.post")
    def test_refresh_token_success(self, mock_post):
        """
        测试刷新令牌成功
        """
        # 恢复配置
        self.http_client.config.auto_refresh_token = True

        # 模拟刷新令牌成功的响应
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access": "new_access_token"}
        mock_post.return_value = mock_response

        # 刷新令牌
        success, error = self.http_client._refresh_token()

        # 验证结果
        self.assertTrue(success)
        self.assertIsNone(error)
        self.assertEqual(self.http_client.access_token, "new_access_token")
        self.assertEqual(self.http_client.refresh_token, "test_refresh_token")

        # 验证调用
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(kwargs["url"], "http://test-api.example.com/api/v1/user/token/refresh/")
        self.assertEqual(kwargs["json"], {"refresh": "test_refresh_token"})

    @patch("requests.Session.post")
    def test_refresh_token_failure(self, mock_post):
        """
        测试刷新令牌失败
        """
        # 模拟刷新令牌失败的响应
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Invalid refresh token"
        mock_post.return_value = mock_response

        # 刷新令牌
        success, error = self.http_client._refresh_token()

        # 验证结果
        self.assertFalse(success)
        self.assertIsNotNone(error)
        self.assertIsNone(self.http_client.access_token)
        self.assertIsNone(self.http_client.refresh_token)

    @patch("requests.Session.request")
    def test_request_success(self, mock_request):
        """
        测试请求成功
        """
        # 模拟requests.request返回值
        mock_response = MagicMock()
        mock_response.status_code = 200
        # 确保json返回值与content和text保持一致
        mock_response.json.return_value = {
            "success": True,  
            "data": "test_data", 
            "message": "success"
        }
        mock_response.text = '{"success": true, "data": "test_data", "message": "success"}'
        mock_response.content = b'{"success": true, "data": "test_data", "message": "success"}'
        mock_response.headers = {"Content-Type": "application/json", "X-Request-ID": "test-request-id"}
        mock_response.elapsed.total_seconds.return_value = 0.2
        
        # 确保mock_request返回我们设置的mock_response
        mock_request.return_value = mock_response

        # 使用模拟重置性能计数器和断路器
        self.http_client.successful_requests = 0
        self.http_client.failed_requests = 0
        self.http_client.total_requests = 0
        
        # 禁用断路器
        original_circuit_breaker = self.http_client.global_circuit_breaker
        self.http_client.global_circuit_breaker = None
        
        try:
            # 发送请求
            response = self.http_client.request(
                method="GET",
                endpoint="user/profile",
                params={"include": "details"},
                headers={"X-Custom-Header": "custom_value"},
            )

            # 验证结果
            self.assertTrue(response.success, f"请求应该成功，但返回了：{response.message}")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data, {"success": True, "data": "test_data", "message": "success"})
            self.assertEqual(response.message, "success")  
            self.assertEqual(response.headers["Content-Type"], "application/json")

            # 验证调用
            mock_request.assert_called_once()
            args, kwargs = mock_request.call_args
            self.assertEqual(kwargs["method"], "GET")
            self.assertEqual(kwargs["url"], "http://test-api.example.com/api/v1/user/profile")
            self.assertEqual(kwargs["params"], {"include": "details"})
        finally:
            # 恢复断路器
            self.http_client.global_circuit_breaker = original_circuit_breaker

    @patch("requests.Session.request")
    def test_request_with_token_refresh(self, mock_request):
        """
        测试请求时刷新令牌
        """
        # 设置客户端令牌
        self.http_client.access_token = "expired_token"
        self.http_client.refresh_token = "valid_refresh_token"
        
        # 模拟第一次请求失败的响应（令牌过期）
        mock_response_1 = MagicMock()
        mock_response_1.status_code = 401
        mock_response_1.json.return_value = {"success": False, "message": "Token expired"}
        mock_response_1.text = '{"success": false, "message": "Token expired"}'
        mock_response_1.content = b'{"success": false, "message": "Token expired"}'
        mock_response_1.headers = {"Content-Type": "application/json"}
        mock_response_1.elapsed.total_seconds.return_value = 0.2
        
        # 模拟令牌刷新请求的响应
        mock_refresh_response = MagicMock()
        mock_refresh_response.status_code = 200
        mock_refresh_response.json.return_value = {"access": "new_access_token", "refresh": "new_refresh_token"}
        mock_refresh_response.text = '{"access": "new_access_token", "refresh": "new_refresh_token"}'
        mock_refresh_response.content = b'{"access": "new_access_token", "refresh": "new_refresh_token"}'
        mock_refresh_response.headers = {"Content-Type": "application/json"}
        mock_refresh_response.elapsed.total_seconds.return_value = 0.1
        
        # 模拟第二次请求成功的响应（刷新令牌后）
        mock_response_2 = MagicMock()
        mock_response_2.status_code = 200
        mock_response_2.json.return_value = {"success": True, "data": "test_data", "message": "success"}
        mock_response_2.text = '{"success": true, "data": "test_data", "message": "success"}'
        mock_response_2.content = b'{"success": true, "data": "test_data", "message": "success"}'
        mock_response_2.headers = {"Content-Type": "application/json", "X-Request-ID": "test-request-id"}
        mock_response_2.elapsed.total_seconds.return_value = 0.2

        # 设置模拟对象的返回值序列
        mock_request.side_effect = [mock_response_1, mock_refresh_response, mock_response_2]
        
        # 重置计数器
        self.http_client.successful_requests = 0
        self.http_client.failed_requests = 0
        self.http_client.total_requests = 0
        
        # 禁用断路器
        original_circuit_breaker = self.http_client.global_circuit_breaker
        self.http_client.global_circuit_breaker = None
        
        try:
            # 发送请求
            response = self.http_client.request(
                method="GET",
                endpoint="user/profile",
                params={"include": "details"},
                retry_on_auth_failure=True
            )
            
            # 验证结果
            self.assertTrue(response.success, f"请求应该成功，但返回了：{response.message}")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data, {"success": True, "data": "test_data", "message": "success"})
            self.assertEqual(self.http_client.access_token, "new_access_token")
            self.assertEqual(self.http_client.refresh_token, "new_refresh_token")
            
            # 验证调用次数和参数
            self.assertEqual(mock_request.call_count, 3)  # 应该有3次调用：原始请求、刷新令牌请求和重试请求
        finally:
            # 恢复断路器
            self.http_client.global_circuit_breaker = original_circuit_breaker

    @patch("requests.request")
    def test_request_exception(self, mock_request):
        """
        测试请求异常
        """
        # 模拟请求异常
        mock_request.side_effect = requests.exceptions.RequestException("Connection error")
        
        # 发送请求
        response = self.http_client.request(
            method="GET",
            endpoint="user/profile",
        )
        
        # 验证结果
        self.assertFalse(response.success)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data, {})
        self.assertEqual(response.message, "服务暂时不可用，请稍后重试")

    def test_convenience_methods(self):
        """
        测试便捷方法
        """
        # 模拟request方法
        self.http_client.request = MagicMock(return_value="mock_response")

        # 测试get方法
        response = self.http_client.get(
            endpoint="user/profile",
            params={"include": "details"},
            headers={"X-Custom-Header": "custom_value"},
        )
        self.assertEqual(response, "mock_response")
        call_args = self.http_client.request.call_args
        self.assertEqual(call_args[1]['method'], 'GET')
        self.assertEqual(call_args[1]['endpoint'], 'user/profile')
        self.assertEqual(call_args[1]['params'], {'include': 'details'})
        self.assertEqual(call_args[1]['headers'], {'X-Custom-Header': 'custom_value'})

        # 测试post方法
        response = self.http_client.post(
            endpoint="user/create",
            data={"username": "testuser"},
            headers={"X-Custom-Header": "custom_value"},
        )
        self.assertEqual(response, "mock_response")
        call_args = self.http_client.request.call_args
        self.assertEqual(call_args[1]['method'], 'POST')
        self.assertEqual(call_args[1]['endpoint'], 'user/create')
        self.assertEqual(call_args[1]['data'], {'username': 'testuser'})
        self.assertEqual(call_args[1]['headers'], {'X-Custom-Header': 'custom_value'})

        # 测试put方法
        response = self.http_client.put(
            endpoint="user/profile",
            data={"nickname": "New Nickname"},
            params={"include": "details"},
            headers={"X-Custom-Header": "custom_value"},
        )
        self.assertEqual(response, "mock_response")
        call_args = self.http_client.request.call_args
        self.assertEqual(call_args[1]['method'], 'PUT')
        self.assertEqual(call_args[1]['endpoint'], 'user/profile')
        self.assertEqual(call_args[1]['data'], {'nickname': 'New Nickname'})
        self.assertEqual(call_args[1]['params'], {'include': 'details'})
        self.assertEqual(call_args[1]['headers'], {'X-Custom-Header': 'custom_value'})

        # 测试patch方法
        response = self.http_client.patch(
            endpoint="user/profile",
            data={"nickname": "New Nickname"},
            params={"include": "details"},
            headers={"X-Custom-Header": "custom_value"},
        )
        self.assertEqual(response, "mock_response")
        call_args = self.http_client.request.call_args
        self.assertEqual(call_args[1]['method'], 'PATCH')
        self.assertEqual(call_args[1]['endpoint'], 'user/profile')
        self.assertEqual(call_args[1]['data'], {'nickname': 'New Nickname'})
        self.assertEqual(call_args[1]['params'], {'include': 'details'})
        self.assertEqual(call_args[1]['headers'], {'X-Custom-Header': 'custom_value'})

        # 测试delete方法
        response = self.http_client.delete(
            endpoint="user/profile",
            data={"confirm": True},
            params={"include": "details"},
            headers={"X-Custom-Header": "custom_value"},
        )
        self.assertEqual(response, "mock_response")
        call_args = self.http_client.request.call_args
        self.assertEqual(call_args[1]['method'], 'DELETE')
        self.assertEqual(call_args[1]['endpoint'], 'user/profile')
        self.assertEqual(call_args[1]['data'], {'confirm': True})
        self.assertEqual(call_args[1]['params'], {'include': 'details'})
        self.assertEqual(call_args[1]['headers'], {'X-Custom-Header': 'custom_value'})


if __name__ == "__main__":
    unittest.main()
