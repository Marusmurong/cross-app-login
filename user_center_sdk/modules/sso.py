"""
用户中心SDK的SSO客户端
提供跨应用单点登录功能
"""

import time
import json
import logging
import base64
import hashlib
import secrets
import uuid
from typing import Dict, List, Any, Optional, Tuple, Union, Callable

from ..utils.http import HttpClient
from ..utils.response import ApiResponse
from ..utils.config import Config
from ..utils.cache import cached

logger = logging.getLogger(__name__)


class SSOClient:
    """
    单点登录客户端，提供跨应用的登录态保持功能
    """
    
    def __init__(self, http_client: HttpClient, application_id: str = None):
        """
        初始化SSO客户端
        
        Args:
            http_client: HTTP客户端
            application_id: 当前应用ID，用于多应用场景
        """
        self.http = http_client
        self.application_id = application_id
        self.config = http_client.config

    @cached(prefix="sso_login_url", ttl=300)
    def get_login_url(
        self,
        redirect_url: str,
        state: str = None,
        scope: str = "basic",
        prompt: str = None,
        force_login: bool = False,
    ) -> ApiResponse:
        """
        获取SSO登录URL
        
        Args:
            redirect_url: 登录成功后的重定向URL
            state: 状态参数，会在回调时原样返回
            scope: 请求的权限范围，如"basic", "profile", "email"
            prompt: 提示用户的方式，如"login", "none"
            force_login: 是否强制登录，即使用户已经登录
            
        Returns:
            包含登录URL的响应
        """
        params = {
            "redirect_url": redirect_url,
            "scope": scope,
        }
        
        if self.application_id:
            params["application_id"] = self.application_id
            
        if state:
            params["state"] = state
            
        if prompt:
            params["prompt"] = prompt
            
        if force_login:
            params["force_login"] = "true"
            
        return self.http.get("sso/authorize", params=params)
    
    def exchange_code(self, code: str, redirect_url: str) -> ApiResponse:
        """
        使用授权码交换令牌
        
        Args:
            code: 授权码
            redirect_url: 重定向URL，必须与获取授权码时的一致
            
        Returns:
            包含访问令牌和刷新令牌的响应
        """
        data = {
            "code": code,
            "redirect_url": redirect_url,
        }
        
        if self.application_id:
            data["application_id"] = self.application_id
            
        response = self.http.post("sso/token", data=data)
        
        # 如果成功获取令牌，保存到HTTP客户端
        if response.success and "access_token" in response.data and "refresh_token" in response.data:
            self.http.set_tokens(
                access_token=response.data["access_token"],
                refresh_token=response.data["refresh_token"],
            )
            
        return response
    
    def validate_token(self, token: str = None) -> ApiResponse:
        """
        验证访问令牌
        
        Args:
            token: 要验证的访问令牌，如果为None则使用当前的访问令牌
            
        Returns:
            验证结果响应
        """
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
            
        return self.http.get("sso/validate", headers=headers)
    
    def logout(self, redirect_url: str = None) -> ApiResponse:
        """
        登出用户
        
        Args:
            redirect_url: 登出后的重定向URL
            
        Returns:
            登出结果响应
        """
        params = {}
        if redirect_url:
            params["redirect_url"] = redirect_url
            
        if self.application_id:
            params["application_id"] = self.application_id
            
        response = self.http.get("sso/logout", params=params)
        
        # 登出成功后清除令牌
        if response.success:
            self.http.clear_tokens()
            
        return response
    
    def get_user_info(self) -> ApiResponse:
        """
        获取当前用户信息
        
        Returns:
            用户信息响应
        """
        return self.http.get("sso/userinfo")
    
    def generate_sso_token(self, user_id: str, lifetime: int = 3600) -> ApiResponse:
        """
        为指定用户生成SSO令牌，用于跨应用登录
        
        Args:
            user_id: 用户ID
            lifetime: 令牌生存时间（秒）
            
        Returns:
            包含SSO令牌的响应
        """
        data = {
            "user_id": user_id,
            "lifetime": lifetime,
        }
        
        if self.application_id:
            data["application_id"] = self.application_id
            
        return self.http.post("sso/generate_token", data=data)
    
    def validate_sso_token(self, sso_token: str) -> ApiResponse:
        """
        验证SSO令牌
        
        Args:
            sso_token: SSO令牌
            
        Returns:
            验证结果响应
        """
        data = {
            "sso_token": sso_token,
        }
        
        if self.application_id:
            data["application_id"] = self.application_id
            
        return self.http.post("sso/validate_token", data=data)
    
    def login_with_sso_token(self, sso_token: str) -> ApiResponse:
        """
        使用SSO令牌登录
        
        Args:
            sso_token: SSO令牌
            
        Returns:
            登录结果响应
        """
        data = {
            "sso_token": sso_token,
        }
        
        if self.application_id:
            data["application_id"] = self.application_id
            
        response = self.http.post("sso/login_with_token", data=data)
        
        # 如果成功获取令牌，保存到HTTP客户端
        if response.success and "access_token" in response.data and "refresh_token" in response.data:
            self.http.set_tokens(
                access_token=response.data["access_token"],
                refresh_token=response.data["refresh_token"],
            )
            
        return response
    
    def get_authorized_applications(self) -> ApiResponse:
        """
        获取用户已授权的应用列表
        
        Returns:
            应用列表响应
        """
        return self.http.get("sso/authorized_applications")
    
    def revoke_application_access(self, application_id: str) -> ApiResponse:
        """
        撤销应用的访问权限
        
        Args:
            application_id: 应用ID
            
        Returns:
            撤销结果响应
        """
        data = {
            "application_id": application_id,
        }
        
        return self.http.post("sso/revoke_access", data=data)


class JWTHelper:
    """
    JWT帮助类，用于处理JWT令牌
    """
    
    @staticmethod
    def decode_jwt_payload(token: str) -> Dict[str, Any]:
        """
        解码JWT令牌的payload部分（不验证签名）
        
        Args:
            token: JWT令牌
            
        Returns:
            payload内容
        """
        try:
            # 分割令牌
            parts = token.split(".")
            if len(parts) != 3:
                logger.warning(f"无效的JWT令牌格式: {token[:10]}...")
                return {}
            
            # 解码payload
            payload_b64 = parts[1]
            # 添加填充
            padding = 4 - (len(payload_b64) % 4)
            if padding < 4:
                payload_b64 += "=" * padding
                
            payload_bytes = base64.urlsafe_b64decode(payload_b64)
            payload = json.loads(payload_bytes.decode("utf-8"))
            
            return payload
        except Exception as e:
            logger.exception(f"解析JWT令牌失败: {str(e)}")
            return {}
    
    @staticmethod
    def is_token_expired(token: str, buffer_seconds: int = 30) -> bool:
        """
        检查JWT令牌是否已过期
        
        Args:
            token: JWT令牌
            buffer_seconds: 缓冲时间（秒），提前这么多秒认为令牌过期
            
        Returns:
            是否已过期
        """
        payload = JWTHelper.decode_jwt_payload(token)
        exp = payload.get("exp", 0)
        
        # 检查是否过期
        return time.time() + buffer_seconds >= exp
    
    @staticmethod
    def get_token_lifetime(token: str) -> int:
        """
        获取JWT令牌的剩余生存时间（秒）
        
        Args:
            token: JWT令牌
            
        Returns:
            剩余生存时间（秒），如果已过期则返回0
        """
        payload = JWTHelper.decode_jwt_payload(token)
        exp = payload.get("exp", 0)
        
        remaining = exp - time.time()
        return max(0, int(remaining))


class SecureStateManager:
    """
    安全状态管理器，用于生成和验证状态参数
    防止CSRF攻击
    """
    
    def __init__(self, secret_key: str = None, ttl: int = 3600):
        """
        初始化安全状态管理器
        
        Args:
            secret_key: 密钥，用于签名状态参数
            ttl: 状态参数的生存时间（秒）
        """
        self.secret_key = secret_key or secrets.token_hex(16)
        self.ttl = ttl
    
    def generate_state(self, data: Dict[str, Any] = None) -> str:
        """
        生成安全的状态参数
        
        Args:
            data: 要包含在状态参数中的数据
            
        Returns:
            状态参数
        """
        # 创建状态数据
        state_data = {
            "ts": int(time.time()),
            "nonce": uuid.uuid4().hex,
        }
        
        if data:
            state_data["data"] = data
            
        # 序列化
        state_json = json.dumps(state_data)
        
        # 计算签名
        signature = self._sign(state_json)
        
        # 编码
        state_b64 = base64.urlsafe_b64encode(state_json.encode()).decode()
        
        # 组合
        return f"{state_b64}.{signature}"
    
    def validate_state(self, state: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        验证状态参数
        
        Args:
            state: 状态参数
            
        Returns:
            (是否有效, 状态数据)
        """
        try:
            # 分割
            parts = state.split(".")
            if len(parts) != 2:
                logger.warning("无效的状态参数格式")
                return False, None
            
            state_b64, signature = parts
            
            # 解码
            state_json = base64.urlsafe_b64decode(state_b64).decode()
            
            # 验证签名
            expected_signature = self._sign(state_json)
            if not secrets.compare_digest(signature, expected_signature):
                logger.warning("状态参数签名无效")
                return False, None
            
            # 解析数据
            state_data = json.loads(state_json)
            
            # 验证时间戳
            ts = state_data.get("ts", 0)
            if time.time() - ts > self.ttl:
                logger.warning("状态参数已过期")
                return False, None
                
            return True, state_data.get("data", {})
            
        except Exception as e:
            logger.exception(f"验证状态参数失败: {str(e)}")
            return False, None
    
    def _sign(self, data: str) -> str:
        """
        对数据进行签名
        
        Args:
            data: 要签名的数据
            
        Returns:
            签名
        """
        return hashlib.sha256(f"{data}.{self.secret_key}".encode()).hexdigest()


class SSOSessionManager:
    """
    SSO会话管理器，用于管理和同步多个应用的会话
    """
    
    def __init__(self, sso_client: SSOClient, storage: Dict[str, Any] = None):
        """
        初始化SSO会话管理器
        
        Args:
            sso_client: SSO客户端
            storage: 会话存储，如果为None则使用内存存储
        """
        self.sso_client = sso_client
        self.storage = storage or {}
        self.refresh_callbacks: List[Callable] = []
        self.logout_callbacks: List[Callable] = []
    
    def save_tokens(self, access_token: str, refresh_token: str) -> None:
        """
        保存令牌
        
        Args:
            access_token: 访问令牌
            refresh_token: 刷新令牌
        """
        self.storage["access_token"] = access_token
        self.storage["refresh_token"] = refresh_token
        self.storage["saved_at"] = time.time()
        
        # 同步到HTTP客户端
        self.sso_client.http.set_tokens(access_token, refresh_token)
    
    def get_tokens(self) -> Tuple[Optional[str], Optional[str]]:
        """
        获取令牌
        
        Returns:
            (访问令牌, 刷新令牌)
        """
        return self.storage.get("access_token"), self.storage.get("refresh_token")
    
    def clear_tokens(self) -> None:
        """
        清除令牌
        """
        if "access_token" in self.storage:
            del self.storage["access_token"]
        if "refresh_token" in self.storage:
            del self.storage["refresh_token"]
        if "saved_at" in self.storage:
            del self.storage["saved_at"]
            
        # 同步到HTTP客户端
        self.sso_client.http.clear_tokens()
        
        # 调用登出回调
        for callback in self.logout_callbacks:
            try:
                callback()
            except Exception as e:
                logger.exception(f"调用登出回调时发生异常: {str(e)}")
    
    def is_logged_in(self) -> bool:
        """
        检查用户是否已登录
        
        Returns:
            是否已登录
        """
        access_token, _ = self.get_tokens()
        
        if not access_token:
            return False
            
        # 检查令牌是否已过期
        return not JWTHelper.is_token_expired(access_token)
    
    def refresh_session(self) -> bool:
        """
        刷新会话
        
        Returns:
            是否刷新成功
        """
        _, refresh_token = self.get_tokens()
        
        if not refresh_token:
            return False
            
        # 使用令牌刷新接口进行刷新
        # 设置令牌到HTTP客户端
        self.sso_client.http.set_tokens(None, refresh_token)
        
        # 调用刷新接口
        success, _ = self.sso_client.http._refresh_token()
        
        if success:
            # 更新存储的令牌
            self.save_tokens(self.sso_client.http.access_token, self.sso_client.http.refresh_token)
            
            # 调用刷新回调
            for callback in self.refresh_callbacks:
                try:
                    callback()
                except Exception as e:
                    logger.exception(f"调用刷新回调时发生异常: {str(e)}")
                    
            return True
        else:
            # 刷新失败，清除令牌
            self.clear_tokens()
            return False
    
    def register_refresh_callback(self, callback: Callable) -> None:
        """
        注册刷新回调
        
        Args:
            callback: 回调函数
        """
        self.refresh_callbacks.append(callback)
    
    def register_logout_callback(self, callback: Callable) -> None:
        """
        注册登出回调
        
        Args:
            callback: 回调函数
        """
        self.logout_callbacks.append(callback)
    
    def auto_refresh(self, buffer_seconds: int = 300) -> bool:
        """
        自动刷新会话（如果接近过期）
        
        Args:
            buffer_seconds: 缓冲时间（秒），提前这么多秒刷新令牌
            
        Returns:
            是否刷新成功
        """
        access_token, _ = self.get_tokens()
        
        if not access_token:
            return False
            
        # 检查令牌是否需要刷新
        if JWTHelper.is_token_expired(access_token, buffer_seconds):
            return self.refresh_session()
            
        return True
    
    def validate_session(self) -> Tuple[bool, Dict[str, Any]]:
        """
        验证当前会话
        
        Returns:
            (是否有效, 用户信息)
        """
        # 首先检查令牌是否存在
        access_token, _ = self.get_tokens()
        
        if not access_token:
            return False, {}
            
        # 自动刷新接近过期的令牌
        self.auto_refresh()
            
        # 调用验证接口
        response = self.sso_client.validate_token()
        
        if response.success:
            return True, response.data
        
        # 验证失败，尝试刷新
        if response.status_code == 401 and self.refresh_session():
            # 刷新成功，重新验证
            response = self.sso_client.validate_token()
            return response.success, response.data if response.success else {}
            
        # 会话无效
        self.clear_tokens()
        return False, {}
