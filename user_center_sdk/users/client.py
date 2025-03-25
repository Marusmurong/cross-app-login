"""
用户中心SDK的用户客户端
"""

from typing import Dict, Any, Optional

from ..utils.http import HttpClient
from ..utils.response import ApiResponse


class UsersClient:
    """
    用户客户端，提供用户资料管理、密码修改等功能
    """

    def __init__(self, http_client: HttpClient):
        """
        初始化用户客户端

        Args:
            http_client: HTTP客户端
        """
        self.http_client = http_client

    def get_profile(self) -> ApiResponse:
        """
        获取用户资料

        Returns:
            API响应
        """
        # 发送获取用户资料请求
        return self.http_client.get("user/profile/")

    def update_profile(
        self,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        nickname: Optional[str] = None,
        avatar: Optional[str] = None,
        bio: Optional[str] = None,
    ) -> ApiResponse:
        """
        更新用户资料

        Args:
            email: 邮箱
            phone: 手机号
            nickname: 昵称
            avatar: 头像URL
            bio: 个人简介

        Returns:
            API响应
        """
        # 构建更新数据
        data = {}
        if email is not None:
            data["email"] = email
        if phone is not None:
            data["phone"] = phone
        if nickname is not None:
            data["nickname"] = nickname
        if avatar is not None:
            data["avatar"] = avatar
        if bio is not None:
            data["bio"] = bio

        # 如果没有要更新的数据，返回错误
        if not data:
            return ApiResponse(
                success=False,
                status_code=400,
                data={},
                message="未提供要更新的字段",
                headers={},
            )

        # 发送更新用户资料请求
        return self.http_client.patch("user/profile/", data=data)

    def change_password(
        self,
        old_password: str,
        new_password: str,
        confirm_password: str,
    ) -> ApiResponse:
        """
        修改密码

        Args:
            old_password: 旧密码
            new_password: 新密码
            confirm_password: 确认新密码

        Returns:
            API响应
        """
        # 确保提供了所有必要的字段
        if not old_password or not new_password or not confirm_password:
            return ApiResponse(
                success=False,
                status_code=400,
                data={},
                message="旧密码、新密码和确认密码是必填字段",
                headers={},
            )

        # 确保新密码和确认密码一致
        if new_password != confirm_password:
            return ApiResponse(
                success=False,
                status_code=400,
                data={},
                message="新密码和确认密码不匹配",
                headers={},
            )

        # 构建修改密码数据
        data = {
            "old_password": old_password,
            "new_password": new_password,
            "confirm_password": confirm_password,
        }

        # 发送修改密码请求
        return self.http_client.post("user/change-password/", data=data)

    def get_third_party_accounts(self) -> ApiResponse:
        """
        获取第三方账号列表

        Returns:
            API响应
        """
        # 发送获取第三方账号列表请求
        return self.http_client.get("user/third-party-accounts/")

    def get_invited_users(self) -> ApiResponse:
        """
        获取已邀请用户列表

        Returns:
            API响应
        """
        # 发送获取已邀请用户列表请求
        return self.http_client.get("user/invited-users/")
