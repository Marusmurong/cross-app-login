"""
用户中心SDK的Django SSO中间件
"""

import base64
import json
import logging
import time
from typing import Callable, Optional

from django.conf import settings
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.utils.deprecation import MiddlewareMixin

from .. import UserCenterClient

logger = logging.getLogger(__name__)


class UserCenterSSOMiddleware(MiddlewareMixin):
    """
    用户中心SSO中间件，用于处理跨应用登录态保持
    
    自动检测SSO令牌，处理授权回调，并在应用间共享登录态
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
        
        # 获取SSO相关配置
        self.app_id = self.config.get("APP_ID")
        self.app_secret = self.config.get("APP_SECRET")
        self.sso_enabled = self.config.get("SSO_ENABLED", True)
        self.auto_redirect = self.config.get("SSO_AUTO_REDIRECT", False)
        self.sso_login_url = self.config.get("SSO_LOGIN_URL")
        self.sso_callback_path = self.config.get("SSO_CALLBACK_PATH", "/auth/callback/")
        self.trusted_apps = self.config.get("TRUSTED_APPS", {})
        
        # 初始化用户中心客户端
        self.client = UserCenterClient(
            api_base_url=self.config.get("API_BASE_URL"),
            api_key=self.config.get("API_KEY"),
            timeout=self.config.get("DEFAULT_TIMEOUT"),
            max_retries=self.config.get("MAX_RETRIES"),
            cache_enabled=self.config.get("CACHE_ENABLED"),
            cache_timeout=self.config.get("CACHE_TIMEOUT"),
            auto_refresh_token=self.config.get("AUTO_REFRESH_TOKEN", True),
            app_id=self.app_id,
            app_secret=self.app_secret,
        )
        
        logger.debug("UserCenterSSOMiddleware initialized")

    def process_request(self, request: HttpRequest) -> Optional[HttpResponse]:
        """
        处理请求
        
        检测SSO令牌，处理授权回调，并在应用间共享登录态
        
        Args:
            request: Django请求对象
            
        Returns:
            None或HttpResponse对象
        """
        # 如果SSO未启用，直接返回
        if not self.sso_enabled:
            return None
            
        # 将用户中心客户端添加到请求对象中
        request.user_center_sso = self.client
        
        # 从会话中获取令牌
        access_token = request.session.get("user_center_access_token")
        refresh_token = request.session.get("user_center_refresh_token")
        
        # 如果有令牌，设置到客户端中
        if access_token and refresh_token:
            self.client.set_tokens(access_token, refresh_token)
        
        # 处理SSO回调
        if request.path == self.sso_callback_path and "code" in request.GET:
            return self._handle_sso_callback(request)
            
        # 检查URL中是否有SSO令牌
        sso_token = request.GET.get("sso_token")
        if sso_token:
            return self._handle_sso_token(request, sso_token)
            
        # 检查请求头中是否有跨应用令牌
        cross_app_token = request.headers.get("X-User-Center-Token")
        if cross_app_token:
            return self._handle_cross_app_token(request, cross_app_token)
            
        # 如果启用了自动重定向且用户未登录，重定向到SSO登录页面
        if self.auto_redirect and not access_token and request.path != self.sso_callback_path:
            # 排除静态文件和API请求
            if not request.path.startswith("/static/") and not request.path.startswith("/api/"):
                return self._redirect_to_sso(request)
        
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
        # 如果请求对象中有用户中心SSO客户端
        if hasattr(request, "user_center_sso"):
            client = request.user_center_sso
            
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
        
    def _handle_sso_callback(self, request: HttpRequest) -> HttpResponse:
        """
        处理SSO回调
        
        Args:
            request: Django请求对象
            
        Returns:
            HttpResponse对象
        """
        code = request.GET.get("code")
        state = request.GET.get("state")
        redirect_url = request.session.get("sso_redirect_url", "/")
        
        try:
            # 使用授权码交换访问令牌
            response_data = self.client.handle_sso_callback(code, request.build_absolute_uri(self.sso_callback_path))
            
            # 保存令牌到会话
            request.session["user_center_access_token"] = self.client.http_client.access_token
            request.session["user_center_refresh_token"] = self.client.http_client.refresh_token
            request.session.modified = True
            
            # 清除会话中的重定向URL
            if "sso_redirect_url" in request.session:
                del request.session["sso_redirect_url"]
                
            logger.info(f"SSO callback handled successfully, redirecting to {redirect_url}")
            
            # 重定向到原始URL
            return HttpResponseRedirect(redirect_url)
        except Exception as e:
            logger.error(f"Error handling SSO callback: {str(e)}")
            # 重定向到错误页面或首页
            return HttpResponseRedirect("/")
            
    def _handle_sso_token(self, request: HttpRequest, sso_token: str) -> Optional[HttpResponse]:
        """
        处理SSO令牌
        
        Args:
            request: Django请求对象
            sso_token: SSO令牌
            
        Returns:
            None或HttpResponse对象
        """
        try:
            # 解码令牌
            token_bytes = base64.urlsafe_b64decode(sso_token)
            token_json = token_bytes.decode("utf-8")
            token_data = json.loads(token_json)
            
            # 检查令牌是否过期
            if "exp" in token_data and token_data["exp"] < time.time():
                logger.warning("SSO token has expired")
                return None
                
            # 设置令牌
            if "access_token" in token_data and "refresh_token" in token_data:
                self.client.set_tokens(token_data["access_token"], token_data["refresh_token"])
                
                # 保存令牌到会话
                request.session["user_center_access_token"] = token_data["access_token"]
                request.session["user_center_refresh_token"] = token_data["refresh_token"]
                request.session.modified = True
                
                logger.info("SSO token processed successfully")
                
                # 重定向到没有令牌参数的URL
                redirect_url = request.get_full_path().split("?")[0]
                return HttpResponseRedirect(redirect_url)
        except Exception as e:
            logger.error(f"Error processing SSO token: {str(e)}")
            
        return None
        
    def _handle_cross_app_token(self, request: HttpRequest, token: str) -> None:
        """
        处理跨应用令牌
        
        Args:
            request: Django请求对象
            token: 跨应用令牌
        """
        # 从请求头中获取源应用ID
        source_app_id = request.headers.get("X-User-Center-App-ID")
        
        # 如果没有源应用ID或源应用不在信任列表中，直接返回
        if not source_app_id or source_app_id not in self.trusted_apps:
            logger.warning(f"Untrusted app ID: {source_app_id}")
            return None
            
        # 获取源应用密钥
        source_app_secret = self.trusted_apps.get(source_app_id)
        
        try:
            # 验证跨应用令牌
            payload = self.client.validate_cross_app_token(token, source_app_id, source_app_secret)
            
            # 保存令牌到会话
            request.session["user_center_access_token"] = self.client.http_client.access_token
            request.session["user_center_refresh_token"] = self.client.http_client.refresh_token
            request.session.modified = True
            
            logger.info(f"Cross-app token from {source_app_id} processed successfully")
        except Exception as e:
            logger.error(f"Error processing cross-app token: {str(e)}")
            
        return None
        
    def _redirect_to_sso(self, request: HttpRequest) -> HttpResponse:
        """
        重定向到SSO登录页面
        
        Args:
            request: Django请求对象
            
        Returns:
            HttpResponseRedirect对象
        """
        # 如果没有配置SSO登录URL，使用默认URL
        if not self.sso_login_url:
            # 保存当前URL到会话
            request.session["sso_redirect_url"] = request.get_full_path()
            request.session.modified = True
            
            # 创建SSO授权URL
            callback_url = request.build_absolute_uri(self.sso_callback_path)
            auth_url = self.client.create_sso_url(callback_url)
            
            logger.info(f"Redirecting to SSO login page: {auth_url}")
            
            return HttpResponseRedirect(auth_url)
        else:
            # 使用配置的SSO登录URL
            return HttpResponseRedirect(self.sso_login_url)
