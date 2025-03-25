"""
用户中心SDK的主客户端类
"""

import logging
from typing import Dict, Any, Optional

from .auth.client import AuthClient
from .auth.sso import SSOClient
from .users.client import UsersClient
from .points.client import PointsClient
from .vip.client import VipClient
from .utils.config import Config
from .utils.http import HttpClient

logger = logging.getLogger(__name__)


class UserCenterClient:
    """
    用户中心SDK的主客户端类，提供对所有API功能的访问
    """

    def __init__(
        self,
        api_base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
        timeout: Optional[int] = None,
        max_retries: Optional[int] = None,
        cache_enabled: Optional[bool] = None,
        cache_timeout: Optional[int] = None,
        auto_refresh_token: Optional[bool] = None,
        app_id: Optional[str] = None,
        app_secret: Optional[str] = None,
    ):
        """
        初始化用户中心客户端

        Args:
            api_base_url: 用户中心API的基础URL，如果未提供则从Django设置中获取
            api_key: 用于API文档访问的API密钥，如果未提供则从Django设置中获取
            access_token: 访问令牌，用于已登录用户的请求
            refresh_token: 刷新令牌，用于刷新过期的访问令牌
            timeout: 请求超时时间（秒）
            max_retries: 最大重试次数
            cache_enabled: 是否启用缓存
            cache_timeout: 缓存超时时间（秒）
            auto_refresh_token: 是否自动刷新令牌
            app_id: 应用ID，用于跨应用登录
            app_secret: 应用密钥，用于跨应用登录
        """
        # 初始化配置
        self.config = Config(
            api_base_url=api_base_url,
            api_key=api_key,
            timeout=timeout,
            max_retries=max_retries,
            cache_enabled=cache_enabled,
            cache_timeout=cache_timeout,
            auto_refresh_token=auto_refresh_token,
        )

        # 初始化HTTP客户端
        self.http_client = HttpClient(
            config=self.config,
            access_token=access_token,
            refresh_token=refresh_token,
        )

        # 初始化各个模块的客户端
        self.auth = AuthClient(self.http_client)
        self.users = UsersClient(self.http_client)
        self.points = PointsClient(self.http_client)
        self.vip = VipClient(self.http_client)
        
        # 初始化SSO客户端
        self.sso = SSOClient(self.http_client)
        if app_id and app_secret:
            self.sso.set_app_credentials(app_id, app_secret)

        logger.debug(f"UserCenterClient initialized with base URL: {self.config.api_base_url}")

    def set_tokens(self, access_token: str, refresh_token: str) -> None:
        """
        设置访问令牌和刷新令牌

        Args:
            access_token: 访问令牌
            refresh_token: 刷新令牌
        """
        self.http_client.set_tokens(access_token, refresh_token)

    def clear_tokens(self) -> None:
        """
        清除访问令牌和刷新令牌
        """
        self.http_client.clear_tokens()

    def get_config(self) -> Dict[str, Any]:
        """
        获取当前配置

        Returns:
            当前配置的字典表示
        """
        return self.config.to_dict()
        
    def set_app_credentials(self, app_id: str, app_secret: str) -> None:
        """
        设置应用凭证，用于跨应用登录

        Args:
            app_id: 应用ID
            app_secret: 应用密钥
        """
        self.sso.set_app_credentials(app_id, app_secret)
        
    def create_sso_url(self, redirect_url: str, state: str = None) -> str:
        """
        创建SSO授权URL，用于将用户重定向到用户中心进行登录

        Args:
            redirect_url: 登录成功后的重定向URL
            state: 状态参数，用于防止CSRF攻击

        Returns:
            SSO授权URL
        """
        return self.sso.create_auth_url(redirect_url, state)
        
    def handle_sso_callback(self, code: str, redirect_url: str) -> Dict[str, Any]:
        """
        处理SSO回调，使用授权码交换访问令牌

        Args:
            code: 授权码
            redirect_url: 重定向URL，必须与请求授权码时使用的URL一致

        Returns:
            包含访问令牌和用户信息的字典
        """
        response = self.sso.exchange_code_for_token(code, redirect_url)
        if response.success:
            return response.data
        else:
            raise ValueError(f"处理SSO回调失败: {response.message}")
            
    def create_cross_app_token(self, target_app_id: str) -> str:
        """
        创建跨应用令牌，用于在不同应用间共享登录态

        Args:
            target_app_id: 目标应用ID

        Returns:
            跨应用令牌
        """
        return self.sso.create_cross_app_token(target_app_id)
        
    def validate_cross_app_token(self, token: str, source_app_id: str, source_app_secret: str) -> Dict[str, Any]:
        """
        验证跨应用令牌

        Args:
            token: 跨应用令牌
            source_app_id: 源应用ID
            source_app_secret: 源应用密钥

        Returns:
            包含令牌信息和用户信息的字典
        """
        valid, payload = self.sso.validate_cross_app_token(token, source_app_id, source_app_secret)
        if valid:
            return payload
        else:
            raise ValueError(f"验证跨应用令牌失败: {payload.get('error', '未知错误')}")
            
    def create_login_url_with_token(self, target_url: str) -> str:
        """
        创建带有令牌的登录URL，用于在不同应用间无缝切换

        Args:
            target_url: 目标URL

        Returns:
            带有令牌的URL
        """
        return self.sso.create_login_url_with_token(target_url)
