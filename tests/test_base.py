"""
测试基类，提供所有测试用例的通用功能和模拟环境
"""

import unittest
from unittest import mock
import json
import time
import sys
from typing import Dict, Any, Optional, List

# 在导入任何SDK模块之前，正确模拟Django设置
mock_settings = mock.MagicMock()
mock_settings.USER_CENTER_SDK = {
    'API_BASE_URL': 'https://api.example.com/api/v1/',
    'API_KEY': 'test_api_key',
    'TIMEOUT': 10,
    'MAX_RETRIES': 3,
    'CACHE_ENABLED': True,
    'CACHE_TIMEOUT': 300,
    'AUTO_REFRESH_TOKEN': True
}

sys.modules['django.conf'] = mock.MagicMock()
sys.modules['django.conf.settings'] = mock_settings

from user_center_sdk.utils.http import HttpClient
from user_center_sdk.utils.config import Config
from user_center_sdk.utils.response import ApiResponse


class MockResponse:
    """模拟requests.Response对象"""
    
    def __init__(self, status_code: int, json_data: Dict[str, Any], headers: Optional[Dict[str, str]] = None):
        self.status_code = status_code
        self._json_data = json_data
        self.headers = headers or {"Content-Type": "application/json"}
        self.content = json.dumps(json_data).encode('utf-8')
        
    def json(self):
        return self._json_data
        
    def raise_for_status(self):
        if 400 <= self.status_code < 600:
            raise Exception(f"HTTP错误: {self.status_code}")


class BaseTestCase(unittest.TestCase):
    """测试基类，提供通用的模拟和断言功能"""
    
    def setUp(self):
        """准备测试环境"""
        # 创建配置对象
        self.config = Config(
            api_base_url="https://api.example.com/api/v1/",
            api_key="test_api_key",
            timeout=10,
            max_retries=3,
            cache_enabled=True,
            cache_timeout=300,
            auto_refresh_token=True
        )
        
        # 模拟HTTP客户端
        self.http_client = mock.MagicMock(spec=HttpClient)
        self.http_client.config = self.config
        
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
            
        self.http_client._build_url.side_effect = mock_build_url
        
        # 设置请求方法的默认返回值
        api_response = ApiResponse(
            success=True,
            status_code=200,
            data={"message": "success"},
            message="操作成功",
            headers={"Content-Type": "application/json"},
            response_time=0.1
        )
        self.http_client.request.return_value = api_response
        self.http_client.get.return_value = api_response
        self.http_client.post.return_value = api_response
        self.http_client.put.return_value = api_response
        self.http_client.delete.return_value = api_response
        
    def create_api_response(self, 
                           success: bool = True, 
                           status_code: int = 200, 
                           data: Dict[str, Any] = None, 
                           message: str = "操作成功", 
                           headers: Dict[str, str] = None, 
                           response_time: float = 0.1) -> ApiResponse:
        """创建API响应对象"""
        return ApiResponse(
            success=success,
            status_code=status_code,
            data=data or {},
            message=message,
            headers=headers or {"Content-Type": "application/json"},
            response_time=response_time
        )
