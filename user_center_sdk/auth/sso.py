"""
用户中心SDK的单点登录(SSO)和跨应用登录模块
"""

import base64
import json
import time
import uuid
from typing import Dict, Any, Optional, Tuple

import jwt

from ..utils.http import HttpClient
from ..utils.response import ApiResponse


class SSOClient:
    """
    单点登录客户端，提供跨应用登录态保持功能
    """

    def __init__(self, http_client: HttpClient):
        """
        初始化单点登录客户端

        Args:
            http_client: HTTP客户端
        """
        self.http_client = http_client
        self._app_id = None
        self._app_secret = None

    def set_app_credentials(self, app_id: str, app_secret: str) -> None:
        """
        设置应用凭证

        Args:
            app_id: 应用ID
            app_secret: 应用密钥
        """
        self._app_id = app_id
        self._app_secret = app_secret

    def generate_sso_token(self, redirect_url: str = None) -> ApiResponse:
        """
        生成SSO令牌，用于跨应用登录

        Args:
            redirect_url: 登录成功后的重定向URL

        Returns:
            API响应，包含SSO令牌和授权URL
        """
        # 确保已设置应用凭证
        if not self._app_id or not self._app_secret:
            return ApiResponse(
                success=False,
                status_code=400,
                data={},
                message="未设置应用凭证，请先调用set_app_credentials方法",
                headers={},
            )

        # 确保已登录
        if not self.http_client.access_token:
            return ApiResponse(
                success=False,
                status_code=401,
                data={},
                message="用户未登录，无法生成SSO令牌",
                headers={},
            )

        # 构建请求数据
        data = {
            "app_id": self._app_id,
            "redirect_url": redirect_url,
        }

        # 发送请求
        response = self.http_client.post("sso/generate_token/", data=data)
        return response

    def validate_sso_token(self, sso_token: str) -> ApiResponse:
        """
        验证SSO令牌

        Args:
            sso_token: SSO令牌

        Returns:
            API响应，包含令牌信息和用户信息
        """
        # 确保已设置应用凭证
        if not self._app_id or not self._app_secret:
            return ApiResponse(
                success=False,
                status_code=400,
                data={},
                message="未设置应用凭证，请先调用set_app_credentials方法",
                headers={},
            )

        # 构建请求数据
        data = {
            "app_id": self._app_id,
            "sso_token": sso_token,
        }

        # 发送请求
        response = self.http_client.post("sso/validate_token/", data=data)

        # 如果验证成功，设置访问令牌和刷新令牌
        if response.success and "access" in response.data and "refresh" in response.data:
            self.http_client.set_tokens(
                access_token=response.data["access"],
                refresh_token=response.data["refresh"],
            )

        return response

    def create_auth_url(self, redirect_url: str, state: str = None) -> str:
        """
        创建授权URL，用于将用户重定向到用户中心进行登录

        Args:
            redirect_url: 登录成功后的重定向URL
            state: 状态参数，用于防止CSRF攻击

        Returns:
            授权URL
        """
        # 确保已设置应用凭证
        if not self._app_id:
            raise ValueError("未设置应用凭证，请先调用set_app_credentials方法")

        # 生成状态参数（如果未提供）
        if not state:
            state = str(uuid.uuid4())

        # 构建授权URL
        base_url = self.http_client.config.api_base_url.replace("/api/v1/", "")
        auth_url = f"{base_url}/sso/authorize/"
        auth_url += f"?app_id={self._app_id}&redirect_url={redirect_url}&state={state}"

        return auth_url

    def exchange_code_for_token(self, code: str, redirect_url: str) -> ApiResponse:
        """
        使用授权码交换访问令牌

        Args:
            code: 授权码
            redirect_url: 重定向URL，必须与请求授权码时使用的URL一致

        Returns:
            API响应，包含访问令牌和刷新令牌
        """
        # 确保已设置应用凭证
        if not self._app_id or not self._app_secret:
            return ApiResponse(
                success=False,
                status_code=400,
                data={},
                message="未设置应用凭证，请先调用set_app_credentials方法",
                headers={},
            )

        # 构建请求数据
        data = {
            "app_id": self._app_id,
            "app_secret": self._app_secret,
            "code": code,
            "redirect_url": redirect_url,
        }

        # 发送请求
        response = self.http_client.post("sso/token/", data=data)

        # 如果交换成功，设置访问令牌和刷新令牌
        if response.success and "access" in response.data and "refresh" in response.data:
            self.http_client.set_tokens(
                access_token=response.data["access"],
                refresh_token=response.data["refresh"],
            )

        return response

    def get_login_status(self) -> ApiResponse:
        """
        获取当前登录状态

        Returns:
            API响应，包含登录状态和用户信息
        """
        return self.http_client.get("sso/status/")

    def create_cross_app_token(self, target_app_id: str, expiration: int = 300) -> str:
        """
        创建跨应用令牌，用于在不同应用间共享登录态

        Args:
            target_app_id: 目标应用ID
            expiration: 令牌有效期（秒），默认5分钟

        Returns:
            跨应用令牌
        """
        # 确保已登录
        if not self.http_client.access_token:
            raise ValueError("用户未登录，无法创建跨应用令牌")

        # 创建令牌负载
        payload = {
            "iss": self._app_id,  # 发行者（当前应用ID）
            "aud": target_app_id,  # 受众（目标应用ID）
            "exp": int(time.time()) + expiration,  # 过期时间
            "iat": int(time.time()),  # 发行时间
            "jti": str(uuid.uuid4()),  # 令牌ID
            "access_token": self.http_client.access_token,
            "refresh_token": self.http_client.refresh_token,
        }

        # 使用应用密钥签名令牌
        token = jwt.encode(payload, self._app_secret, algorithm="HS256")
        
        return token

    def validate_cross_app_token(self, token: str, source_app_id: str, source_app_secret: str) -> Tuple[bool, Dict[str, Any]]:
        """
        验证跨应用令牌

        Args:
            token: 跨应用令牌
            source_app_id: 源应用ID
            source_app_secret: 源应用密钥

        Returns:
            (是否有效, 令牌负载)
        """
        try:
            # 解码并验证令牌
            payload = jwt.decode(
                token,
                source_app_secret,
                algorithms=["HS256"],
                audience=self._app_id,
                issuer=source_app_id,
            )

            # 检查令牌是否已过期
            if "exp" in payload and payload["exp"] < time.time():
                return False, {"error": "令牌已过期"}

            # 设置令牌
            if "access_token" in payload and "refresh_token" in payload:
                self.http_client.set_tokens(
                    access_token=payload["access_token"],
                    refresh_token=payload["refresh_token"],
                )

            return True, payload
        except jwt.InvalidTokenError as e:
            return False, {"error": f"无效的令牌: {str(e)}"}
        except Exception as e:
            return False, {"error": f"验证令牌时发生错误: {str(e)}"}

    def create_login_url_with_token(self, target_url: str) -> str:
        """
        创建带有令牌的登录URL，用于在不同应用间无缝切换

        Args:
            target_url: 目标URL

        Returns:
            带有令牌的URL
        """
        # 确保已登录
        if not self.http_client.access_token:
            raise ValueError("用户未登录，无法创建带令牌的URL")

        # 创建令牌数据
        token_data = {
            "access_token": self.http_client.access_token,
            "refresh_token": self.http_client.refresh_token,
            "exp": int(time.time()) + 300,  # 5分钟有效期
        }

        # 编码令牌数据
        token_json = json.dumps(token_data)
        token_bytes = token_json.encode("utf-8")
        token_b64 = base64.urlsafe_b64encode(token_bytes).decode("utf-8")

        # 构建URL
        separator = "&" if "?" in target_url else "?"
        url = f"{target_url}{separator}sso_token={token_b64}"

        return url
        
    def login_with_sso_token(self, token: str) -> ApiResponse:
        """
        使用SSO令牌登录
        
        Args:
            token: SSO令牌
            
        Returns:
            API响应，包含登录状态和用户信息
        """
        # 确保已设置应用凭证
        if not self._app_id or not self._app_secret:
            return ApiResponse(
                success=False,
                status_code=400,
                data={},
                message="未设置应用凭证，请先调用set_app_credentials方法",
                headers={},
            )
            
        # 构建请求数据
        data = {
            "app_id": self._app_id,
            "sso_token": token,
        }
        
        # 发送请求
        response = self.http_client.post("sso/login_with_token/", data=data)
        
        # 如果登录成功，设置访问令牌和刷新令牌
        if response.success and "access_token" in response.data and "refresh_token" in response.data:
            self.http_client.set_tokens(
                access_token=response.data["access_token"],
                refresh_token=response.data["refresh_token"],
            )
            
        return response
