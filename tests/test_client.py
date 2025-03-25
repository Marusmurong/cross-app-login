"""
用户中心SDK客户端的单元测试
"""

import unittest
from unittest.mock import patch, MagicMock
import sys

# 在导入SDK之前，模拟Django设置
sys.modules['django.conf'] = MagicMock()
sys.modules['django.conf.settings'] = MagicMock(USER_CENTER_SDK={})

# 直接导入客户端类
from user_center_sdk.client import UserCenterClient
from user_center_sdk.utils.response import ApiResponse


class TestUserCenterClient(unittest.TestCase):
    """
    用户中心SDK客户端的单元测试
    """

    def setUp(self):
        """
        测试前的准备工作
        """
        self.client = UserCenterClient(
            api_base_url="http://test-api.example.com/api/v1/",
            api_key="test_api_key",
            auto_refresh_token=True,
        )

    def test_init(self):
        """
        测试客户端初始化
        """
        self.assertEqual(self.client.config.api_base_url, "http://test-api.example.com/api/v1/")
        self.assertEqual(self.client.config.api_key, "test_api_key")
        self.assertTrue(self.client.config.auto_refresh_token)
        self.assertIsNotNone(self.client.http_client)
        self.assertIsNotNone(self.client.auth)
        self.assertIsNotNone(self.client.users)
        self.assertIsNotNone(self.client.points)
        self.assertIsNotNone(self.client.vip)

    def test_set_tokens(self):
        """
        测试设置令牌
        """
        self.client.set_tokens("test_access_token", "test_refresh_token")
        self.assertEqual(self.client.http_client.access_token, "test_access_token")
        self.assertEqual(self.client.http_client.refresh_token, "test_refresh_token")

    def test_clear_tokens(self):
        """
        测试清除令牌
        """
        self.client.set_tokens("test_access_token", "test_refresh_token")
        self.client.clear_tokens()
        self.assertIsNone(self.client.http_client.access_token)
        self.assertIsNone(self.client.http_client.refresh_token)

    def test_get_config(self):
        """
        测试获取配置
        """
        config = self.client.get_config()
        self.assertEqual(config["api_base_url"], "http://test-api.example.com/api/v1/")
        self.assertEqual(config["api_key"], "test_api_key")
        self.assertTrue(config["auto_refresh_token"])


class TestAuthClient(unittest.TestCase):
    """
    认证客户端的单元测试
    """

    def setUp(self):
        """
        测试前的准备工作
        """
        self.client = UserCenterClient(
            api_base_url="http://test-api.example.com/api/v1/",
            api_key="test_api_key",
        )
        self.auth_client = self.client.auth

    @patch("user_center_sdk.utils.http.HttpClient.post")
    def test_login_success(self, mock_post):
        """
        测试登录成功
        """
        # 模拟登录成功的响应
        mock_response = ApiResponse(
            success=True,
            status_code=200,
            data={
                "access": "test_access_token",
                "refresh": "test_refresh_token",
                "user_id": "test_user_id",
            },
            message="登录成功",
            headers={},
        )
        mock_post.return_value = mock_response

        # 调用登录方法
        response = self.auth_client.login(
            username="test_user",
            password="test_password",
        )

        # 验证结果
        self.assertTrue(response.success)
        self.assertEqual(response.data["access"], "test_access_token")
        self.assertEqual(response.data["refresh"], "test_refresh_token")
        self.assertEqual(self.client.http_client.access_token, "test_access_token")
        self.assertEqual(self.client.http_client.refresh_token, "test_refresh_token")

        # 验证调用
        mock_post.assert_called_once_with(
            "user/login/",
            data={"username": "test_user", "password": "test_password"},
        )

    @patch("user_center_sdk.utils.http.HttpClient.post")
    def test_login_failure(self, mock_post):
        """
        测试登录失败
        """
        # 模拟登录失败的响应
        mock_response = ApiResponse(
            success=False,
            status_code=401,
            data={},
            message="用户名或密码错误",
            headers={},
        )
        mock_post.return_value = mock_response

        # 调用登录方法
        response = self.auth_client.login(
            username="test_user",
            password="wrong_password",
        )

        # 验证结果
        self.assertFalse(response.success)
        self.assertEqual(response.message, "用户名或密码错误")
        self.assertIsNone(self.client.http_client.access_token)
        self.assertIsNone(self.client.http_client.refresh_token)

    @patch("user_center_sdk.utils.http.HttpClient.post")
    def test_logout(self, mock_post):
        """
        测试登出
        """
        # 设置令牌
        self.client.set_tokens("test_access_token", "test_refresh_token")

        # 模拟登出响应
        mock_response = ApiResponse(
            success=True,
            status_code=200,
            data={},
            message="登出成功",
            headers={},
        )
        mock_post.return_value = mock_response

        # 调用登出方法
        response = self.auth_client.logout()

        # 验证结果
        self.assertTrue(response.success)
        self.assertEqual(response.message, "登出成功")
        self.assertIsNone(self.client.http_client.access_token)
        self.assertIsNone(self.client.http_client.refresh_token)

        # 验证调用
        mock_post.assert_called_once_with("user/logout/")

    @patch("user_center_sdk.utils.http.HttpClient.post")
    def test_refresh_token(self, mock_post):
        """
        测试刷新令牌
        """
        # 设置令牌
        self.client.set_tokens("old_access_token", "test_refresh_token")

        # 模拟刷新令牌响应
        mock_response = ApiResponse(
            success=True,
            status_code=200,
            data={
                "access": "new_access_token",
            },
            message="令牌刷新成功",
            headers={},
        )
        mock_post.return_value = mock_response

        # 调用刷新令牌方法
        response = self.auth_client.refresh_token()

        # 验证结果
        self.assertTrue(response.success)
        self.assertEqual(response.data["access"], "new_access_token")
        self.assertEqual(self.client.http_client.access_token, "new_access_token")
        self.assertEqual(self.client.http_client.refresh_token, "test_refresh_token")

        # 验证调用
        mock_post.assert_called_once_with(
            "user/token/refresh/",
            data={"refresh": "test_refresh_token"},
        )


class TestUsersClient(unittest.TestCase):
    """
    用户客户端的单元测试
    """

    def setUp(self):
        """
        测试前的准备工作
        """
        self.client = UserCenterClient(
            api_base_url="http://test-api.example.com/api/v1/",
            api_key="test_api_key",
        )
        self.users_client = self.client.users

    @patch("user_center_sdk.utils.http.HttpClient.get")
    def test_get_profile(self, mock_get):
        """
        测试获取用户资料
        """
        # 模拟获取用户资料响应
        mock_response = ApiResponse(
            success=True,
            status_code=200,
            data={
                "username": "test_user",
                "email": "test@example.com",
                "phone": "1234567890",
                "nickname": "Test User",
            },
            message="获取用户资料成功",
            headers={},
        )
        mock_get.return_value = mock_response

        # 调用获取用户资料方法
        response = self.users_client.get_profile()

        # 验证结果
        self.assertTrue(response.success)
        self.assertEqual(response.data["username"], "test_user")
        self.assertEqual(response.data["email"], "test@example.com")
        self.assertEqual(response.data["phone"], "1234567890")
        self.assertEqual(response.data["nickname"], "Test User")

        # 验证调用
        mock_get.assert_called_once_with("user/profile/")

    @patch("user_center_sdk.utils.http.HttpClient.patch")
    def test_update_profile(self, mock_patch):
        """
        测试更新用户资料
        """
        # 模拟更新用户资料响应
        mock_response = ApiResponse(
            success=True,
            status_code=200,
            data={
                "username": "test_user",
                "email": "new_email@example.com",
                "phone": "1234567890",
                "nickname": "New Nickname",
            },
            message="更新用户资料成功",
            headers={},
        )
        mock_patch.return_value = mock_response

        # 调用更新用户资料方法
        response = self.users_client.update_profile(
            email="new_email@example.com",
            nickname="New Nickname",
        )

        # 验证结果
        self.assertTrue(response.success)
        self.assertEqual(response.data["email"], "new_email@example.com")
        self.assertEqual(response.data["nickname"], "New Nickname")

        # 验证调用
        mock_patch.assert_called_once_with(
            "user/profile/",
            data={"email": "new_email@example.com", "nickname": "New Nickname"},
        )


if __name__ == "__main__":
    unittest.main()
