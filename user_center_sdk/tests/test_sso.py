"""
用户中心SDK的SSO功能测试
"""

import base64
import json
import time
import unittest
from unittest.mock import MagicMock, patch

import jwt

from user_center_sdk import UserCenterClient
from user_center_sdk.auth.sso import SSOClient
from user_center_sdk.utils.http import HttpClient, ApiResponse


class TestSSOClient(unittest.TestCase):
    """测试SSO客户端功能"""

    def setUp(self):
        """设置测试环境"""
        self.http_client = MagicMock(spec=HttpClient)
        self.sso_client = SSOClient(self.http_client)
        self.sso_client.set_app_credentials("test_app_id", "test_app_secret")
        
        # 模拟HTTP响应
        self.mock_response = ApiResponse(
            success=True,
            data={
                "access_token": "mock_access_token",
                "refresh_token": "mock_refresh_token",
                "expires_in": 3600,
                "token_type": "Bearer",
                "user_id": "test_user_id",
            },
            message="Success",
            status_code=200,
        )
        
        self.http_client.post.return_value = self.mock_response

    def test_set_app_credentials(self):
        """测试设置应用凭证"""
        self.sso_client.set_app_credentials("new_app_id", "new_app_secret")
        self.assertEqual(self.sso_client._app_id, "new_app_id")
        self.assertEqual(self.sso_client._app_secret, "new_app_secret")

    def test_generate_sso_token(self):
        """测试生成SSO令牌"""
        redirect_url = "http://example.com/callback"
        response = self.sso_client.generate_sso_token(redirect_url)
        
        self.http_client.post.assert_called_once_with(
            "/sso/token/generate",
            data={
                "app_id": "test_app_id",
                "redirect_url": redirect_url,
            },
        )
        
        self.assertTrue(response.success)
        self.assertEqual(response.data, self.mock_response.data)

    def test_validate_sso_token(self):
        """测试验证SSO令牌"""
        token = "mock_sso_token"
        response = self.sso_client.validate_sso_token(token)
        
        self.http_client.post.assert_called_once_with(
            "/sso/token/validate",
            data={
                "app_id": "test_app_id",
                "token": token,
            },
        )
        
        self.assertTrue(response.success)
        self.assertEqual(response.data, self.mock_response.data)

    def test_create_auth_url(self):
        """测试创建授权URL"""
        redirect_url = "http://example.com/callback"
        state = "test_state"
        
        auth_url = self.sso_client.create_auth_url(redirect_url, state)
        
        expected_url = (
            f"{self.http_client.config.api_base_url}sso/authorize?"
            f"app_id=test_app_id&redirect_uri={redirect_url}&state={state}"
        )
        
        self.assertEqual(auth_url, expected_url)

    def test_exchange_code_for_token(self):
        """测试使用授权码交换令牌"""
        code = "test_code"
        redirect_url = "http://example.com/callback"
        
        response = self.sso_client.exchange_code_for_token(code, redirect_url)
        
        self.http_client.post.assert_called_once_with(
            "/sso/token",
            data={
                "app_id": "test_app_id",
                "app_secret": "test_app_secret",
                "code": code,
                "redirect_uri": redirect_url,
            },
        )
        
        self.assertTrue(response.success)
        self.assertEqual(response.data, self.mock_response.data)

    @patch("user_center_sdk.auth.sso.jwt.encode")
    def test_create_cross_app_token(self, mock_jwt_encode):
        """测试创建跨应用令牌"""
        target_app_id = "target_app_id"
        mock_jwt_encode.return_value = "mock_jwt_token"
        
        # 设置访问令牌和刷新令牌
        self.http_client.access_token = "test_access_token"
        self.http_client.refresh_token = "test_refresh_token"
        
        token = self.sso_client.create_cross_app_token(target_app_id)
        
        # 验证JWT编码调用
        mock_jwt_encode.assert_called_once()
        call_args = mock_jwt_encode.call_args[0]
        payload = call_args[0]
        
        self.assertEqual(payload["iss"], "test_app_id")
        self.assertEqual(payload["aud"], target_app_id)
        self.assertEqual(payload["access_token"], "test_access_token")
        self.assertEqual(payload["refresh_token"], "test_refresh_token")
        self.assertTrue("exp" in payload)
        
        self.assertEqual(token, "mock_jwt_token")

    @patch("user_center_sdk.auth.sso.jwt.decode")
    def test_validate_cross_app_token(self, mock_jwt_decode):
        """测试验证跨应用令牌"""
        token = "mock_jwt_token"
        source_app_id = "source_app_id"
        source_app_secret = "source_app_secret"
        
        # 模拟JWT解码结果
        mock_payload = {
            "iss": source_app_id,
            "aud": "test_app_id",
            "access_token": "source_access_token",
            "refresh_token": "source_refresh_token",
            "exp": int(time.time()) + 3600,
        }
        mock_jwt_decode.return_value = mock_payload
        
        valid, payload = self.sso_client.validate_cross_app_token(
            token, source_app_id, source_app_secret
        )
        
        # 验证JWT解码调用
        mock_jwt_decode.assert_called_once_with(
            token,
            key=source_app_secret,
            algorithms=["HS256"],
            audience="test_app_id",
            issuer=source_app_id,
        )
        
        self.assertTrue(valid)
        self.assertEqual(payload, mock_payload)
        
        # 验证令牌已设置到HTTP客户端
        self.assertEqual(self.http_client.access_token, "source_access_token")
        self.assertEqual(self.http_client.refresh_token, "source_refresh_token")

    def test_create_login_url_with_token(self):
        """测试创建带有令牌的登录URL"""
        target_url = "http://example.com/dashboard"
        
        # 设置访问令牌和刷新令牌
        self.http_client.access_token = "test_access_token"
        self.http_client.refresh_token = "test_refresh_token"
        
        with patch("user_center_sdk.auth.sso.base64.urlsafe_b64encode") as mock_b64encode:
            # 模拟base64编码结果
            mock_b64encode.return_value = b"encoded_token_data"
            
            url = self.sso_client.create_login_url_with_token(target_url)
            
            # 验证base64编码调用
            mock_b64encode.assert_called_once()
            
            expected_url = f"{target_url}?sso_token=encoded_token_data"
            self.assertEqual(url, expected_url)


class TestUserCenterClientSSO(unittest.TestCase):
    """测试UserCenterClient的SSO功能集成"""

    def setUp(self):
        """设置测试环境"""
        self.client = UserCenterClient(
            api_base_url="http://example.com/api/v1/",
            app_id="test_app_id",
            app_secret="test_app_secret",
        )
        
        # 模拟SSO客户端方法
        self.client.sso.create_auth_url = MagicMock(return_value="mock_auth_url")
        self.client.sso.exchange_code_for_token = MagicMock(
            return_value=ApiResponse(
                success=True,
                data={
                    "access_token": "mock_access_token",
                    "refresh_token": "mock_refresh_token",
                },
                message="Success",
                status_code=200,
            )
        )
        self.client.sso.create_cross_app_token = MagicMock(return_value="mock_cross_app_token")
        self.client.sso.validate_cross_app_token = MagicMock(
            return_value=(True, {"user_id": "test_user_id"})
        )
        self.client.sso.create_login_url_with_token = MagicMock(return_value="mock_login_url")

    def test_set_app_credentials(self):
        """测试设置应用凭证"""
        self.client.set_app_credentials("new_app_id", "new_app_secret")
        self.client.sso.set_app_credentials.assert_called_once_with("new_app_id", "new_app_secret")

    def test_create_sso_url(self):
        """测试创建SSO URL"""
        redirect_url = "http://example.com/callback"
        state = "test_state"
        
        url = self.client.create_sso_url(redirect_url, state)
        
        self.client.sso.create_auth_url.assert_called_once_with(redirect_url, state)
        self.assertEqual(url, "mock_auth_url")

    def test_handle_sso_callback(self):
        """测试处理SSO回调"""
        code = "test_code"
        redirect_url = "http://example.com/callback"
        
        data = self.client.handle_sso_callback(code, redirect_url)
        
        self.client.sso.exchange_code_for_token.assert_called_once_with(code, redirect_url)
        self.assertEqual(
            data,
            {
                "access_token": "mock_access_token",
                "refresh_token": "mock_refresh_token",
            },
        )

    def test_create_cross_app_token(self):
        """测试创建跨应用令牌"""
        target_app_id = "target_app_id"
        
        token = self.client.create_cross_app_token(target_app_id)
        
        self.client.sso.create_cross_app_token.assert_called_once_with(target_app_id)
        self.assertEqual(token, "mock_cross_app_token")

    def test_validate_cross_app_token(self):
        """测试验证跨应用令牌"""
        token = "test_token"
        source_app_id = "source_app_id"
        source_app_secret = "source_app_secret"
        
        payload = self.client.validate_cross_app_token(token, source_app_id, source_app_secret)
        
        self.client.sso.validate_cross_app_token.assert_called_once_with(
            token, source_app_id, source_app_secret
        )
        self.assertEqual(payload, {"user_id": "test_user_id"})

    def test_create_login_url_with_token(self):
        """测试创建带有令牌的登录URL"""
        target_url = "http://example.com/dashboard"
        
        url = self.client.create_login_url_with_token(target_url)
        
        self.client.sso.create_login_url_with_token.assert_called_once_with(target_url)
        self.assertEqual(url, "mock_login_url")


if __name__ == "__main__":
    unittest.main()
