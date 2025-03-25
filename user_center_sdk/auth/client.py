"""
用户中心SDK的认证客户端
"""

from typing import Dict, Any, Optional

from ..utils.http import HttpClient
from ..utils.response import ApiResponse


class AuthClient:
    """
    认证客户端，提供登录、登出和令牌管理功能
    """

    def __init__(self, http_client: HttpClient):
        """
        初始化认证客户端

        Args:
            http_client: HTTP客户端
        """
        self.http_client = http_client

    def login(
        self,
        username: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        password: str = None,
    ) -> ApiResponse:
        """
        用户登录

        Args:
            username: 用户名
            email: 邮箱
            phone: 手机号
            password: 密码

        Returns:
            API响应
        """
        # 确保至少提供了一种登录方式
        if not any([username, email, phone]):
            return ApiResponse(
                success=False,
                status_code=400,
                data={},
                message="必须提供用户名、邮箱或手机号中的一种进行登录",
                headers={},
            )

        # 确保提供了密码
        if not password:
            return ApiResponse(
                success=False,
                status_code=400,
                data={},
                message="必须提供密码",
                headers={},
            )

        # 构建登录数据
        data = {"password": password}
        if username:
            data["username"] = username
        if email:
            data["email"] = email
        if phone:
            data["phone"] = phone

        # 发送登录请求
        response = self.http_client.post("user/login/", data=data)

        # 如果登录成功，保存令牌
        if response.success and "access" in response.data and "refresh" in response.data:
            self.http_client.set_tokens(
                access_token=response.data["access"],
                refresh_token=response.data["refresh"],
            )

        return response

    def logout(self) -> ApiResponse:
        """
        用户登出

        Returns:
            API响应
        """
        # 发送登出请求
        response = self.http_client.post("user/logout/")

        # 无论登出是否成功，都清除令牌
        self.http_client.clear_tokens()

        return response

    def refresh_token(self, refresh_token: Optional[str] = None) -> ApiResponse:
        """
        刷新访问令牌

        Args:
            refresh_token: 刷新令牌，如果未提供则使用当前的刷新令牌

        Returns:
            API响应
        """
        # 使用提供的刷新令牌或当前的刷新令牌
        token = refresh_token or self.http_client.refresh_token

        # 如果没有刷新令牌，返回错误
        if not token:
            return ApiResponse(
                success=False,
                status_code=400,
                data={},
                message="未提供刷新令牌",
                headers={},
            )

        # 发送刷新令牌请求
        response = self.http_client.post("user/token/refresh/", data={"refresh": token})

        # 如果刷新成功，更新令牌
        if response.success and "access" in response.data:
            self.http_client.access_token = response.data["access"]
            # 有些API会在刷新时同时返回新的刷新令牌
            if "refresh" in response.data:
                self.http_client.refresh_token = response.data["refresh"]

        return response

    def check_token(self, access_token: Optional[str] = None) -> ApiResponse:
        """
        检查访问令牌是否有效

        Args:
            access_token: 访问令牌，如果未提供则使用当前的访问令牌

        Returns:
            API响应
        """
        # 使用提供的访问令牌或当前的访问令牌
        token = access_token or self.http_client.access_token

        # 如果没有访问令牌，返回错误
        if not token:
            return ApiResponse(
                success=False,
                status_code=400,
                data={},
                message="未提供访问令牌",
                headers={},
            )

        # 临时保存当前令牌
        current_token = self.http_client.access_token

        # 设置要检查的令牌
        self.http_client.access_token = token

        # 发送检查令牌请求
        response = self.http_client.get("user/check-token/")

        # 恢复原来的令牌
        self.http_client.access_token = current_token

        return response

    def register(
        self,
        username: str,
        password: str,
        confirm_password: str,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        nickname: Optional[str] = None,
    ) -> ApiResponse:
        """
        用户注册

        Args:
            username: 用户名
            password: 密码
            confirm_password: 确认密码
            email: 邮箱
            phone: 手机号
            nickname: 昵称

        Returns:
            API响应
        """
        # 确保提供了必要的字段
        if not username or not password or not confirm_password:
            return ApiResponse(
                success=False,
                status_code=400,
                data={},
                message="用户名、密码和确认密码是必填字段",
                headers={},
            )

        # 确保密码和确认密码一致
        if password != confirm_password:
            return ApiResponse(
                success=False,
                status_code=400,
                data={},
                message="两次密码不匹配",
                headers={},
            )

        # 确保至少提供了邮箱或手机号之一
        if not email and not phone:
            return ApiResponse(
                success=False,
                status_code=400,
                data={},
                message="邮箱和手机号至少提供一个",
                headers={},
            )

        # 构建注册数据
        data = {
            "username": username,
            "password": password,
            "confirm_password": confirm_password,
        }
        if email:
            data["email"] = email
        if phone:
            data["phone"] = phone
        if nickname:
            data["nickname"] = nickname

        # 发送注册请求
        response = self.http_client.post("user/register/", data=data)

        # 如果注册成功，保存令牌
        if response.success and "access" in response.data and "refresh" in response.data:
            self.http_client.set_tokens(
                access_token=response.data["access"],
                refresh_token=response.data["refresh"],
            )

        return response

    def verify_user(self, verification_code: str) -> ApiResponse:
        """
        验证用户（邮箱或手机验证）

        Args:
            verification_code: 验证码

        Returns:
            API响应
        """
        # 发送验证请求
        return self.http_client.post("user/verify/", data={"code": verification_code})

    def resend_verification_code(self) -> ApiResponse:
        """
        重新发送验证码

        Returns:
            API响应
        """
        # 发送重新发送验证码请求
        return self.http_client.post("user/resend-verification-code/")

    def invite_register(
        self,
        username: str,
        password: str,
        confirm_password: str,
        invite_code: str,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        nickname: Optional[str] = None,
    ) -> ApiResponse:
        """
        邀请注册

        Args:
            username: 用户名
            password: 密码
            confirm_password: 确认密码
            invite_code: 邀请码
            email: 邮箱
            phone: 手机号
            nickname: 昵称

        Returns:
            API响应
        """
        # 确保提供了必要的字段
        if not username or not password or not confirm_password or not invite_code:
            return ApiResponse(
                success=False,
                status_code=400,
                data={},
                message="用户名、密码、确认密码和邀请码是必填字段",
                headers={},
            )

        # 确保密码和确认密码一致
        if password != confirm_password:
            return ApiResponse(
                success=False,
                status_code=400,
                data={},
                message="两次密码不匹配",
                headers={},
            )

        # 确保至少提供了邮箱或手机号之一
        if not email and not phone:
            return ApiResponse(
                success=False,
                status_code=400,
                data={},
                message="邮箱和手机号至少提供一个",
                headers={},
            )

        # 构建邀请注册数据
        data = {
            "username": username,
            "password": password,
            "confirm_password": confirm_password,
            "invite_code": invite_code,
        }
        if email:
            data["email"] = email
        if phone:
            data["phone"] = phone
        if nickname:
            data["nickname"] = nickname

        # 发送邀请注册请求
        response = self.http_client.post("user/invite-register/", data=data)

        # 如果注册成功，保存令牌
        if response.success and "access" in response.data and "refresh" in response.data:
            self.http_client.set_tokens(
                access_token=response.data["access"],
                refresh_token=response.data["refresh"],
            )

        return response

    def check_invite_code(self, invite_code: str) -> ApiResponse:
        """
        检查邀请码是否有效

        Args:
            invite_code: 邀请码

        Returns:
            API响应
        """
        # 发送检查邀请码请求
        return self.http_client.get("user/check-invite-code/", params={"code": invite_code})
