"""
用户中心SDK的Django装饰器
"""

import functools
from typing import Callable, Optional

from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse


def login_required(
    function: Optional[Callable] = None,
    login_url: Optional[str] = None,
    redirect_field_name: str = "next",
):
    """
    用户中心登录验证装饰器
    
    用于验证用户是否已登录，如果未登录则重定向到登录页面
    
    Args:
        function: 被装饰的函数
        login_url: 登录页面URL，如果未提供则使用Django设置中的LOGIN_URL
        redirect_field_name: 重定向字段名
        
    Returns:
        装饰后的函数
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            # 检查用户是否已登录
            if not hasattr(request, "user_center"):
                raise RuntimeError(
                    "UserCenterAuthMiddleware未启用，请在MIDDLEWARE设置中添加"
                    "'user_center_sdk.django.UserCenterAuthMiddleware'"
                )
            
            # 获取用户资料，检查是否已登录
            profile_response = request.user_center.users.get_profile()
            
            if profile_response.success:
                # 用户已登录，继续执行视图函数
                return view_func(request, *args, **kwargs)
            else:
                # 用户未登录，重定向到登录页面
                resolved_login_url = login_url or reverse("login")
                
                # 构建重定向URL
                from django.http import QueryDict
                query = QueryDict("", mutable=True)
                query[redirect_field_name] = request.get_full_path()
                redirect_url = f"{resolved_login_url}?{query.urlencode()}"
                
                return redirect(redirect_url)
                
        return _wrapped_view
    
    if function:
        return decorator(function)
    return decorator


def vip_required(
    function: Optional[Callable] = None,
    vip_level: Optional[int] = None,
    redirect_url: Optional[str] = None,
):
    """
    用户中心VIP验证装饰器
    
    用于验证用户是否是VIP，如果不是则重定向到指定页面
    
    Args:
        function: 被装饰的函数
        vip_level: 所需的VIP等级，如果未提供则只验证是否是VIP
        redirect_url: 重定向URL，如果未提供则使用Django设置中的VIP_UPGRADE_URL
        
    Returns:
        装饰后的函数
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            # 检查用户中心客户端是否可用
            if not hasattr(request, "user_center"):
                raise RuntimeError(
                    "UserCenterAuthMiddleware未启用，请在MIDDLEWARE设置中添加"
                    "'user_center_sdk.django.UserCenterAuthMiddleware'"
                )
            
            # 获取用户VIP状态
            vip_response = request.user_center.vip.get_vip_status()
            
            if vip_response.success:
                # 检查VIP状态
                is_vip = vip_response.data.get("is_vip", False)
                current_level = vip_response.data.get("level", 0)
                
                # 如果用户是VIP且等级满足要求，继续执行视图函数
                if is_vip and (vip_level is None or current_level >= vip_level):
                    return view_func(request, *args, **kwargs)
            
            # 用户不是VIP或等级不满足要求，重定向到指定页面
            from django.conf import settings
            resolved_redirect_url = redirect_url or getattr(settings, "VIP_UPGRADE_URL", "/vip/upgrade/")
            
            return redirect(resolved_redirect_url)
                
        return _wrapped_view
    
    if function:
        return decorator(function)
    return decorator
