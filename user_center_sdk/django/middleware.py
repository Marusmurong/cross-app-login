"""
用户中心SDK的Django中间件
"""

import logging
from typing import Callable, Optional

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.utils.deprecation import MiddlewareMixin

from .. import UserCenterClient

logger = logging.getLogger(__name__)


class UserCenterAuthMiddleware(MiddlewareMixin):
    """
    用户中心认证中间件，用于自动处理用户认证和令牌刷新
    
    将用户中心客户端实例添加到请求对象中，并在需要时自动刷新令牌
    """

    def __init__(self, get_response: Callable):
        """
        初始化中间件
        
        Args:
            get_response: Django请求处理函数
        """
        super().__init__(get_response)
        self.get_response = get_response
        
        # 从Django设置中获取配置
        self.config = getattr(settings, "USER_CENTER_SDK", {})
        
        # 初始化用户中心客户端
        self.client = UserCenterClient(
            api_base_url=self.config.get("API_BASE_URL"),
            api_key=self.config.get("API_KEY"),
            timeout=self.config.get("DEFAULT_TIMEOUT"),
            max_retries=self.config.get("MAX_RETRIES"),
            cache_enabled=self.config.get("CACHE_ENABLED"),
            cache_timeout=self.config.get("CACHE_TIMEOUT"),
            auto_refresh_token=self.config.get("AUTO_REFRESH_TOKEN", True),
        )
        
        logger.debug("UserCenterAuthMiddleware initialized")

    def process_request(self, request: HttpRequest) -> Optional[HttpResponse]:
        """
        处理请求
        
        从会话中获取令牌并设置到客户端中
        
        Args:
            request: Django请求对象
            
        Returns:
            None或HttpResponse对象
        """
        # 将用户中心客户端添加到请求对象中
        request.user_center = self.client
        
        # 从会话中获取令牌
        access_token = request.session.get("user_center_access_token")
        refresh_token = request.session.get("user_center_refresh_token")
        
        # 如果有令牌，设置到客户端中
        if access_token and refresh_token:
            self.client.set_tokens(access_token, refresh_token)
            
            # 检查令牌是否有效
            response = self.client.auth.check_token()
            
            # 如果令牌无效且自动刷新令牌已启用，尝试刷新令牌
            if not response.success and self.config.get("AUTO_REFRESH_TOKEN", True):
                refresh_response = self.client.auth.refresh_token()
                
                # 如果刷新成功，更新会话中的令牌
                if refresh_response.success:
                    request.session["user_center_access_token"] = self.client.http_client.access_token
                    if self.client.http_client.refresh_token:
                        request.session["user_center_refresh_token"] = self.client.http_client.refresh_token
                    request.session.modified = True
                    logger.debug("Token refreshed successfully")
                else:
                    # 如果刷新失败，清除会话中的令牌
                    self._clear_session_tokens(request)
                    logger.warning(f"Token refresh failed: {refresh_response.message}")
        
        return None

    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        """
        处理响应
        
        如果客户端的令牌已更新，将其保存到会话中
        
        Args:
            request: Django请求对象
            response: Django响应对象
            
        Returns:
            Django响应对象
        """
        # 如果请求对象中有用户中心客户端
        if hasattr(request, "user_center"):
            client = request.user_center
            
            # 如果客户端的令牌与会话中的令牌不同，更新会话中的令牌
            if client.http_client.access_token != request.session.get("user_center_access_token"):
                if client.http_client.access_token:
                    request.session["user_center_access_token"] = client.http_client.access_token
                    request.session.modified = True
            
            if client.http_client.refresh_token != request.session.get("user_center_refresh_token"):
                if client.http_client.refresh_token:
                    request.session["user_center_refresh_token"] = client.http_client.refresh_token
                    request.session.modified = True
        
        return response

    def _clear_session_tokens(self, request: HttpRequest) -> None:
        """
        清除会话中的令牌
        
        Args:
            request: Django请求对象
        """
        if "user_center_access_token" in request.session:
            del request.session["user_center_access_token"]
        
        if "user_center_refresh_token" in request.session:
            del request.session["user_center_refresh_token"]
        
        request.session.modified = True
