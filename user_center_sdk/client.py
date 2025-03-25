"""
用户中心SDK的主客户端类
"""

import logging
import time
from typing import Dict, Any, Optional, List, Union, Tuple

from .auth.client import AuthClient
from .auth.sso import SSOClient
from .users.client import UsersClient
from .points.client import PointsClient
from .vip.client import VipClient
from .utils.config import Config
from .utils.http import HttpClient
from .utils.monitoring import APIMonitor
from .utils.response import ApiResponse

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
        enable_monitoring: bool = True,
        metrics_capacity: int = 1000,
        enable_circuit_breaker: bool = True,
        connection_pool_size: int = 10,
        connection_timeout: int = 5,
        read_timeout: int = 30,
        enable_performance_tracking: bool = True,
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
            enable_monitoring: 是否启用API监控
            metrics_capacity: API监控指标容量
            enable_circuit_breaker: 是否启用断路器模式
            connection_pool_size: 连接池大小
            connection_timeout: 连接超时时间（秒）
            read_timeout: 读取超时时间（秒）
            enable_performance_tracking: 是否启用性能跟踪
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
            circuit_breaker_enabled=enable_circuit_breaker,
            pool_connections=connection_pool_size,
            connect_timeout=connection_timeout,
            read_timeout=read_timeout,
            enable_performance_tracking=enable_performance_tracking,
        )

        # 初始化API监控
        self.api_monitor = APIMonitor(
            enabled=enable_monitoring,
            metrics_capacity=metrics_capacity,
            logger_name="user_center_sdk.api"
        )

        # 初始化HTTP客户端
        self.http_client = HttpClient(
            config=self.config,
            access_token=access_token,
            refresh_token=refresh_token,
            api_monitor=self.api_monitor,
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
        
    def create_sso_url(self, redirect_url: str, state: str = None, force_login: bool = False, scope: str = None) -> str:
        """
        创建SSO授权URL，用于将用户重定向到用户中心进行登录

        Args:
            redirect_url: 登录成功后的重定向URL
            state: 状态参数，用于防止CSRF攻击
            force_login: 是否强制重新登录，即使用户已经登录
            scope: 请求的权限范围，多个权限用空格分隔

        Returns:
            SSO授权URL
        """
        return self.sso.get_login_url(
            redirect_url=redirect_url, 
            state=state, 
            force_login=force_login, 
            scope=scope
        )
        
    def handle_sso_callback(self, code: str, redirect_url: str) -> Dict[str, Any]:
        """
        处理SSO回调，使用授权码交换访问令牌

        Args:
            code: 授权码
            redirect_url: 重定向URL，必须与请求授权码时使用的URL一致

        Returns:
            包含访问令牌和用户信息的字典
        """
        response = self.sso.exchange_code(code, redirect_url)
        if response.success:
            # 自动设置令牌
            if 'access_token' in response.data and 'refresh_token' in response.data:
                self.set_tokens(response.data['access_token'], response.data['refresh_token'])
            return response.data
        else:
            raise ValueError(f"处理SSO回调失败: {response.message}")
            
    def get_user_info(self) -> Dict[str, Any]:
        """
        获取当前登录用户的信息

        Returns:
            用户信息字典
        """
        response = self.sso.get_user_info()
        if response.success:
            return response.data
        return {}
    
    def is_token_valid(self) -> bool:
        """
        检查当前的访问令牌是否有效

        Returns:
            令牌是否有效
        """
        response = self.sso.validate_token()
        return response.success
    
    def logout(self) -> bool:
        """
        退出登录，清除令牌

        Returns:
            操作是否成功
        """
        response = self.sso.logout()
        if response.success:
            # 清除本地令牌
            self.clear_tokens()
            return True
        return False
    
    def generate_sso_token(self, user_id: str, expiration: int = 3600) -> str:
        """
        为指定用户生成SSO令牌，用于跨应用登录

        Args:
            user_id: 用户ID
            expiration: 令牌有效期（秒）

        Returns:
            SSO令牌
        """
        response = self.sso.generate_sso_token(user_id, expiration)
        if response.success:
            return response.data.get('token', '')
        raise ValueError(f"生成SSO令牌失败: {response.message}")
    
    def validate_sso_token(self, token: str) -> Tuple[bool, Dict[str, Any]]:
        """
        验证SSO令牌

        Args:
            token: SSO令牌

        Returns:
            元组，包含验证结果和令牌载荷
        """
        response = self.sso.validate_sso_token(token)
        if response.success:
            return True, response.data
        return False, {'error': response.message}
    
    def login_with_sso_token(self, token: str) -> bool:
        """
        使用SSO令牌登录

        Args:
            token: SSO令牌

        Returns:
            登录是否成功
        """
        response = self.sso.login_with_sso_token(token)
        if response.success:
            # 设置令牌
            if 'access_token' in response.data and 'refresh_token' in response.data:
                self.set_tokens(response.data['access_token'], response.data['refresh_token'])
            return True
        return False
    
    def create_cross_app_token(self, target_app_id: str, expiration: int = 300) -> str:
        """
        创建跨应用令牌，用于在不同应用间共享登录态

        Args:
            target_app_id: 目标应用ID
            expiration: 令牌有效期（秒）

        Returns:
            跨应用令牌
        """
        # 确保已设置应用凭证
        if not hasattr(self.sso, 'create_cross_app_token'):
            raise NotImplementedError("当前SSOClient不支持create_cross_app_token方法")
            
        try:
            # 尝试使用新的create_cross_app_token方法
            result = self.sso.create_cross_app_token(target_app_id, expiration)
            # 检查返回类型
            if isinstance(result, str):
                return result
            elif hasattr(result, 'success') and result.success:
                return result.data.get('token', '')
            else:
                raise ValueError(f"创建跨应用令牌失败: {getattr(result, 'message', '未知错误')}")
        except (TypeError, AttributeError):
            # 如果失败，尝试使用generate_sso_token方法
            response = self.sso.generate_sso_token()
            if response.success:
                return response.data.get('token', '')
            raise ValueError(f"创建跨应用令牌失败: {response.message}")
        
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
        # 调用SSOClient的validate_cross_app_token方法
        if hasattr(self.sso, 'validate_cross_app_token'):
            valid, payload = self.sso.validate_cross_app_token(token, source_app_id, source_app_secret)
            if valid:
                return payload
            else:
                raise ValueError(f"验证跨应用令牌失败: {payload.get('error', '未知错误')}")
        else:
            # 兼容旧版本，使用validate_sso_token方法
            response = self.sso.validate_sso_token(token)
            if response.success:
                return response.data
            else:
                raise ValueError(f"验证跨应用令牌失败: {response.message}")
            
    def create_login_url_with_token(self, target_url: str, expiration: int = 300) -> str:
        """
        创建带有令牌的登录URL，用于在不同应用间无缝切换

        Args:
            target_url: 目标URL
            expiration: 令牌有效期（秒）

        Returns:
            带有令牌的URL
        """
        # 首先检查SSOClient是否支持create_login_url_with_token方法
        if hasattr(self.sso, 'create_login_url_with_token'):
            return self.sso.create_login_url_with_token(target_url)
            
        # 否则尝试获取令牌并自行构建URL
        # 尝试获取令牌
        token = ""
        try:
            token_result = self.create_cross_app_token("", expiration)
            if isinstance(token_result, str):
                token = token_result
        except (ValueError, TypeError, NotImplementedError):
            # 如果失败，尝试直接调用generate_sso_token
            try:
                response = self.sso.generate_sso_token()
                if hasattr(response, 'success') and response.success:
                    token = response.data.get('token', '')
            except Exception as e:
                logger.error(f"生成SSO令牌失败: {str(e)}")
            
        if not token:
            raise ValueError("无法生成SSO令牌")
            
        if '?' in target_url:
            return f"{target_url}&sso_token={token}"
        else:
            return f"{target_url}?sso_token={token}"
    
    def get_authorized_applications(self) -> List[Dict[str, Any]]:
        """
        获取用户授权的应用列表

        Returns:
            应用列表
        """
        # 由于SSOClient没有get_authorized_applications方法，我们尝试直接调用API
        try:
            response = self.http_client.get("sso/authorized_applications/")
            if response.success:
                return response.data.get('applications', [])
            return []
        except Exception as e:
            logger.error(f"获取授权应用列表失败: {str(e)}")
            return []
    
    def revoke_application_access(self, app_id: str) -> bool:
        """
        撤销应用的访问权限

        Args:
            app_id: 应用ID

        Returns:
            操作是否成功
        """
        # 由于SSOClient没有revoke_application_access方法，我们尝试直接调用API
        try:
            response = self.http_client.post("sso/revoke_access/", data={"app_id": app_id})
            return response.success
        except Exception as e:
            logger.error(f"撤销应用访问权限失败: {str(e)}")
            return False

    def get_api_metrics(self) -> Dict[str, Any]:
        """
        获取API调用指标统计数据

        Returns:
            API调用指标统计
        """
        return self.api_monitor.get_metrics() if self.api_monitor.is_enabled() else {}
    
    def reset_api_metrics(self) -> None:
        """
        重置API调用指标统计
        """
        if self.api_monitor.is_enabled():
            self.api_monitor.reset_metrics()
    
    def get_recent_api_requests(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        获取最近的API请求记录

        Args:
            limit: 最大记录数
            
        Returns:
            最近的API请求记录
        """
        return self.api_monitor.get_recent_requests(limit) if self.api_monitor.is_enabled() else []
    
    def get_endpoint_metrics(self, endpoint: str, method: str = 'GET') -> Dict[str, Any]:
        """
        获取特定端点的API调用指标

        Args:
            endpoint: API端点
            method: HTTP方法
            
        Returns:
            特定端点的API调用指标
        """
        return self.api_monitor.get_endpoint_metrics(endpoint, method) if self.api_monitor.is_enabled() else {}
    
    def set_monitoring_enabled(self, enabled: bool) -> None:
        """
        设置是否启用API监控

        Args:
            enabled: 是否启用
        """
        if hasattr(self.api_monitor, 'enabled'):
            self.api_monitor.enabled = enabled
