"""
用户中心SDK的Django SSO中间件
增强版 - 针对生产环境优化
"""

import base64
import json
import logging
import time
import hashlib
import secrets
from typing import Callable, Optional
from urllib.parse import urlparse, urlencode, parse_qs

from django.conf import settings
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.utils.deprecation import MiddlewareMixin

from .. import UserCenterClient

logger = logging.getLogger(__name__)


class UserCenterSSOMiddleware(MiddlewareMixin):
    """
    用户中心SSO中间件，用于处理跨应用登录态保持
    
    自动检测SSO令牌，处理授权回调，并在应用间共享登录态
    增强版 - 提供更好的性能和安全性
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
        
        # 新增配置选项
        self.token_timeout = self.config.get("SSO_TOKEN_TIMEOUT", 300)  # 令牌过期时间，默认5分钟
        self.secure_cookies = self.config.get("SSO_SECURE_COOKIES", True)  # 是否使用安全Cookie
        self.same_site = self.config.get("SSO_SAME_SITE", "Lax")  # SameSite属性
        self.csrf_protection = self.config.get("SSO_CSRF_PROTECTION", True)  # 是否启用CSRF保护
        self.exclude_paths = self.config.get("SSO_EXCLUDE_PATHS", ['/static/', '/media/', '/api/'])  # 排除路径
        
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
        
        logger.debug("UserCenterSSOMiddleware initialized with enhanced settings")

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
        
        # 检查是否为排除路径
        if self._is_excluded_path(request.path):
            return None
            
        # 从会话中获取令牌
        access_token = request.session.get("user_center_access_token")
        refresh_token = request.session.get("user_center_refresh_token")
        
        # 如果有令牌，设置到客户端中
        if access_token and refresh_token:
            self.client.set_tokens(access_token, refresh_token)
            # 设置更新后的过期时间
            request.session["user_center_token_exp"] = int(time.time()) + self.token_timeout
        
        # 检查令牌是否过期，若过期则尝试刷新
        token_exp = request.session.get("user_center_token_exp", 0)
        if token_exp and token_exp < time.time() and refresh_token:
            try:
                refresh_response = self.client.auth.refresh_token()
                if refresh_response.success:
                    request.session["user_center_access_token"] = self.client.http_client.access_token
                    if self.client.http_client.refresh_token:
                        request.session["user_center_refresh_token"] = self.client.http_client.refresh_token
                    request.session["user_center_token_exp"] = int(time.time()) + self.token_timeout
                    request.session.modified = True
                    logger.debug("Token refreshed successfully")
                else:
                    # 如果刷新失败，清除会话中的令牌
                    self._clear_session_tokens(request)
                    logger.warning(f"Token refresh failed: {refresh_response.message}")
            except Exception as e:
                logger.error(f"Token refresh error: {str(e)}")
                self._clear_session_tokens(request)
        
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
            return self._redirect_to_sso(request)
        
        return None
        
    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        """
        处理响应
        
        如果客户端的令牌已更新，将其保存到会话中并设置安全头
        
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
                    request.session["user_center_token_exp"] = int(time.time()) + self.token_timeout
                    request.session.modified = True
            
            if client.http_client.refresh_token != request.session.get("user_center_refresh_token"):
                if client.http_client.refresh_token:
                    request.session["user_center_refresh_token"] = client.http_client.refresh_token
                    request.session.modified = True
                    
            # 如果有登录状态，添加安全头，防止clickjacking和XSS攻击
            if client.http_client.access_token:
                response["X-Frame-Options"] = "DENY"
                response["X-Content-Type-Options"] = "nosniff"
                
        # 应用Cookie安全设置
        if self.secure_cookies and settings.SESSION_COOKIE_NAME in response.cookies:
            response.cookies[settings.SESSION_COOKIE_NAME]["secure"] = True
            response.cookies[settings.SESSION_COOKIE_NAME]["samesite"] = self.same_site
            response.cookies[settings.SESSION_COOKIE_NAME]["httponly"] = True
        
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
        
        # CSRF保护验证
        if self.csrf_protection and state:
            session_state = request.session.get("sso_state")
            if not session_state or session_state != state:
                logger.warning("CSRF validation failed in SSO callback")
                return HttpResponseRedirect("/login-error/?error=invalid_state")
        
        try:
            # 使用授权码交换访问令牌
            response_data = self.client.handle_sso_callback(code, request.build_absolute_uri(self.sso_callback_path))
            
            # 保存令牌到会话
            request.session["user_center_access_token"] = self.client.http_client.access_token
            request.session["user_center_refresh_token"] = self.client.http_client.refresh_token
            request.session["user_center_token_exp"] = int(time.time()) + self.token_timeout
            request.session.modified = True
            
            # 清除会话中的重定向URL和state
            if "sso_redirect_url" in request.session:
                del request.session["sso_redirect_url"]
            if "sso_state" in request.session:
                del request.session["sso_state"]
                
            logger.info(f"SSO callback handled successfully, redirecting to {redirect_url}")
            
            # 重定向到原始URL
            return HttpResponseRedirect(redirect_url)
        except Exception as e:
            logger.error(f"Error handling SSO callback: {str(e)}", exc_info=True)
            # 重定向到错误页面
            return HttpResponseRedirect(f"/login-error/?error={str(e)}")
            
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
            try:
                token_bytes = base64.urlsafe_b64decode(sso_token + '=' * (4 - len(sso_token) % 4))
                token_json = token_bytes.decode("utf-8")
                token_data = json.loads(token_json)
            except Exception as e:
                logger.error(f"Error decoding SSO token: {str(e)}")
                raise ValueError("Invalid SSO token format")
            
            # 检查令牌是否过期
            if "exp" in token_data and token_data["exp"] < time.time():
                logger.warning("SSO token has expired")
                return HttpResponseRedirect("/login-error/?error=token_expired")
                
            # 验证令牌签名
            if "signature" in token_data:
                payload = {k: v for k, v in token_data.items() if k != "signature"}
                payload_str = json.dumps(payload, sort_keys=True)
                expected_signature = hashlib.sha256((payload_str + self.app_secret).encode()).hexdigest()
                
                if token_data["signature"] != expected_signature:
                    logger.warning("SSO token signature validation failed")
                    return HttpResponseRedirect("/login-error/?error=invalid_signature")
                
            # 设置令牌
            if "access_token" in token_data and "refresh_token" in token_data:
                self.client.set_tokens(token_data["access_token"], token_data["refresh_token"])
                
                # 保存令牌到会话
                request.session["user_center_access_token"] = token_data["access_token"]
                request.session["user_center_refresh_token"] = token_data["refresh_token"]
                request.session["user_center_token_exp"] = token_data.get("exp", int(time.time()) + self.token_timeout)
                request.session.modified = True
                
                logger.info("SSO token processed successfully")
                
                # 重定向到没有令牌参数的URL
                redirect_url = request.get_full_path().split("?")[0]
                query_params = parse_qs(urlparse(request.get_full_path()).query)
                query_params.pop("sso_token", None)
                
                if query_params:
                    redirect_url += "?" + urlencode(query_params, doseq=True)
                    
                return HttpResponseRedirect(redirect_url)
            else:
                logger.warning("SSO token missing required fields")
                return HttpResponseRedirect("/login-error/?error=invalid_token_content")
        except Exception as e:
            logger.error(f"Error processing SSO token: {str(e)}", exc_info=True)
            return HttpResponseRedirect(f"/login-error/?error={str(e)}")
        
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
            
            # 检查令牌是否过期
            if "exp" in payload and payload["exp"] < time.time():
                logger.warning("Cross-app token has expired")
                return None
            
            # 保存令牌到会话
            request.session["user_center_access_token"] = self.client.http_client.access_token
            request.session["user_center_refresh_token"] = self.client.http_client.refresh_token
            request.session["user_center_token_exp"] = int(time.time()) + self.token_timeout
            request.session.modified = True
            
            # 记录令牌来源
            request.session["token_source_app"] = source_app_id
            
            logger.info(f"Cross-app token from {source_app_id} processed successfully")
        except Exception as e:
            logger.error(f"Error processing cross-app token: {str(e)}", exc_info=True)
            
        return None
        
    def _redirect_to_sso(self, request: HttpRequest) -> HttpResponse:
        """
        重定向到SSO登录页面
        
        Args:
            request: Django请求对象
            
        Returns:
            HttpResponseRedirect对象
        """
        # 如果请求是AJAX请求，返回401状态码而不是重定向
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            response = HttpResponse(json.dumps({"error": "Authentication required"}), content_type="application/json", status=401)
            response["X-Login-Required"] = "true"
            return response
        
        # 保存当前URL到会话
        request.session["sso_redirect_url"] = request.get_full_path()
        
        # 生成CSRF保护的state参数
        if self.csrf_protection:
            state = secrets.token_hex(16)
            request.session["sso_state"] = state
        else:
            state = None
            
        request.session.modified = True
        
        # 如果没有配置SSO登录URL，使用默认URL
        if not self.sso_login_url:
            # 创建SSO授权URL
            callback_url = request.build_absolute_uri(self.sso_callback_path)
            auth_url = self.client.create_sso_url(callback_url, state)
            
            logger.info(f"Redirecting to SSO login page: {auth_url}")
            
            return HttpResponseRedirect(auth_url)
        else:
            # 使用配置的SSO登录URL
            login_url = self.sso_login_url
            if state:
                login_url += f"?state={state}"
                
            return HttpResponseRedirect(login_url)
    
    def _is_excluded_path(self, path: str) -> bool:
        """
        检查路径是否在排除列表中
        
        Args:
            path: 请求路径
            
        Returns:
            布尔值，表示是否排除
        """
        return any(path.startswith(excluded) for excluded in self.exclude_paths)
        
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
            
        if "user_center_token_exp" in request.session:
            del request.session["user_center_token_exp"]
            
        if "token_source_app" in request.session:
            del request.session["token_source_app"]
            
        if "sso_state" in request.session:
            del request.session["sso_state"]
        
        request.session.modified = True
