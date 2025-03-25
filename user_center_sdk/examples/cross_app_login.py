#!/usr/bin/env python
"""
用户中心SDK跨应用登录示例

此示例展示了如何在两个不同的应用之间实现登录态保持。
"""

import os
import json
import base64
from urllib.parse import urlencode

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.views.decorators.http import require_http_methods

from user_center_sdk import UserCenterClient


# 应用A的配置
APP_A_CONFIG = {
    "APP_ID": "app_a_id",
    "APP_SECRET": "app_a_secret",
    "API_BASE_URL": "http://localhost:5200/api/v1/",
    "TRUSTED_APPS": {
        "app_b_id": "app_b_secret",  # 信任应用B
    }
}

# 应用B的配置
APP_B_CONFIG = {
    "APP_ID": "app_b_id",
    "APP_SECRET": "app_b_secret",
    "API_BASE_URL": "http://localhost:5200/api/v1/",
    "TRUSTED_APPS": {
        "app_a_id": "app_a_secret",  # 信任应用A
    }
}


# ===== 应用A的视图 =====

def app_a_home(request: HttpRequest) -> HttpResponse:
    """
    应用A的首页
    """
    # 从会话中获取令牌
    access_token = request.session.get("user_center_access_token")
    refresh_token = request.session.get("user_center_refresh_token")
    
    # 初始化用户中心客户端
    client = UserCenterClient(
        api_base_url=APP_A_CONFIG["API_BASE_URL"],
        app_id=APP_A_CONFIG["APP_ID"],
        app_secret=APP_A_CONFIG["APP_SECRET"],
    )
    
    # 如果有令牌，设置到客户端中
    if access_token and refresh_token:
        client.set_tokens(access_token, refresh_token)
    
    # 获取用户资料
    profile_response = client.users.get_profile()
    
    if profile_response.success:
        # 用户已登录，显示用户资料和跳转到应用B的链接
        user_data = profile_response.data
        
        # 创建带有令牌的应用B链接
        app_b_url = "http://app-b.example.com/"
        app_b_link = client.create_login_url_with_token(app_b_url)
        
        # 创建跨应用令牌（用于API调用）
        cross_app_token = client.create_cross_app_token("app_b_id")
        
        return JsonResponse({
            "logged_in": True,
            "user": user_data,
            "app_b_link": app_b_link,
            "cross_app_token": cross_app_token,
        })
    else:
        # 用户未登录，显示登录链接
        login_url = "/login/"
        return JsonResponse({
            "logged_in": False,
            "login_url": login_url,
        })

def app_a_login(request: HttpRequest) -> HttpResponse:
    """
    应用A的登录页面
    """
    # 初始化用户中心客户端
    client = UserCenterClient(
        api_base_url=APP_A_CONFIG["API_BASE_URL"],
        app_id=APP_A_CONFIG["APP_ID"],
        app_secret=APP_A_CONFIG["APP_SECRET"],
    )
    
    # 创建SSO授权URL
    callback_url = request.build_absolute_uri("/auth/callback/")
    auth_url = client.create_sso_url(callback_url)
    
    # 保存重定向URL到会话
    request.session["sso_redirect_url"] = request.GET.get("next", "/")
    
    # 重定向到SSO授权URL
    return redirect(auth_url)

def app_a_callback(request: HttpRequest) -> HttpResponse:
    """
    应用A的SSO回调处理
    """
    # 从请求中获取授权码
    code = request.GET.get("code")
    
    if not code:
        return JsonResponse({"error": "Missing authorization code"}, status=400)
    
    # 初始化用户中心客户端
    client = UserCenterClient(
        api_base_url=APP_A_CONFIG["API_BASE_URL"],
        app_id=APP_A_CONFIG["APP_ID"],
        app_secret=APP_A_CONFIG["APP_SECRET"],
    )
    
    try:
        # 使用授权码交换访问令牌
        callback_url = request.build_absolute_uri("/auth/callback/")
        token_data = client.handle_sso_callback(code, callback_url)
        
        # 保存令牌到会话
        request.session["user_center_access_token"] = client.http_client.access_token
        request.session["user_center_refresh_token"] = client.http_client.refresh_token
        
        # 重定向到原始URL
        redirect_url = request.session.get("sso_redirect_url", "/")
        if "sso_redirect_url" in request.session:
            del request.session["sso_redirect_url"]
        
        return redirect(redirect_url)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)

def app_a_logout(request: HttpRequest) -> HttpResponse:
    """
    应用A的登出处理
    """
    # 从会话中获取令牌
    access_token = request.session.get("user_center_access_token")
    refresh_token = request.session.get("user_center_refresh_token")
    
    # 初始化用户中心客户端
    client = UserCenterClient(
        api_base_url=APP_A_CONFIG["API_BASE_URL"],
        app_id=APP_A_CONFIG["APP_ID"],
        app_secret=APP_A_CONFIG["APP_SECRET"],
    )
    
    # 如果有令牌，设置到客户端中并登出
    if access_token and refresh_token:
        client.set_tokens(access_token, refresh_token)
        client.auth.logout()
    
    # 清除会话中的令牌
    if "user_center_access_token" in request.session:
        del request.session["user_center_access_token"]
    if "user_center_refresh_token" in request.session:
        del request.session["user_center_refresh_token"]
    
    # 重定向到首页
    return redirect("/")


# ===== 应用B的视图 =====

def app_b_home(request: HttpRequest) -> HttpResponse:
    """
    应用B的首页
    """
    # 从会话中获取令牌
    access_token = request.session.get("user_center_access_token")
    refresh_token = request.session.get("user_center_refresh_token")
    
    # 初始化用户中心客户端
    client = UserCenterClient(
        api_base_url=APP_B_CONFIG["API_BASE_URL"],
        app_id=APP_B_CONFIG["APP_ID"],
        app_secret=APP_B_CONFIG["APP_SECRET"],
    )
    
    # 如果有令牌，设置到客户端中
    if access_token and refresh_token:
        client.set_tokens(access_token, refresh_token)
    
    # 获取用户资料
    profile_response = client.users.get_profile()
    
    if profile_response.success:
        # 用户已登录，显示用户资料和跳转到应用A的链接
        user_data = profile_response.data
        
        # 创建带有令牌的应用A链接
        app_a_url = "http://app-a.example.com/"
        app_a_link = client.create_login_url_with_token(app_a_url)
        
        return JsonResponse({
            "logged_in": True,
            "user": user_data,
            "app_a_link": app_a_link,
        })
    else:
        # 用户未登录，显示登录链接
        login_url = "/login/"
        return JsonResponse({
            "logged_in": False,
            "login_url": login_url,
        })

def app_b_process_sso_token(request: HttpRequest) -> HttpResponse:
    """
    应用B处理从应用A传递的SSO令牌
    """
    # 从请求中获取SSO令牌
    sso_token = request.GET.get("sso_token")
    
    if not sso_token:
        return JsonResponse({"error": "Missing SSO token"}, status=400)
    
    try:
        # 解码令牌
        token_bytes = base64.urlsafe_b64decode(sso_token)
        token_json = token_bytes.decode("utf-8")
        token_data = json.loads(token_json)
        
        # 初始化用户中心客户端
        client = UserCenterClient(
            api_base_url=APP_B_CONFIG["API_BASE_URL"],
            app_id=APP_B_CONFIG["APP_ID"],
            app_secret=APP_B_CONFIG["APP_SECRET"],
        )
        
        # 设置令牌
        client.set_tokens(token_data["access_token"], token_data["refresh_token"])
        
        # 保存令牌到会话
        request.session["user_center_access_token"] = token_data["access_token"]
        request.session["user_center_refresh_token"] = token_data["refresh_token"]
        
        # 重定向到首页
        return redirect("/")
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)

@require_http_methods(["POST"])
def app_b_api_endpoint(request: HttpRequest) -> HttpResponse:
    """
    应用B的API端点，接受来自应用A的跨应用令牌
    """
    # 从请求头中获取跨应用令牌和应用ID
    cross_app_token = request.headers.get("X-User-Center-Token")
    app_id = request.headers.get("X-User-Center-App-ID")
    
    if not cross_app_token or not app_id:
        return JsonResponse({"error": "Missing token or app ID"}, status=400)
    
    # 检查应用ID是否在信任列表中
    if app_id not in APP_B_CONFIG["TRUSTED_APPS"]:
        return JsonResponse({"error": "Untrusted app ID"}, status=403)
    
    # 获取应用密钥
    app_secret = APP_B_CONFIG["TRUSTED_APPS"][app_id]
    
    # 初始化用户中心客户端
    client = UserCenterClient(
        api_base_url=APP_B_CONFIG["API_BASE_URL"],
        app_id=APP_B_CONFIG["APP_ID"],
        app_secret=APP_B_CONFIG["APP_SECRET"],
    )
    
    try:
        # 验证跨应用令牌
        payload = client.validate_cross_app_token(cross_app_token, app_id, app_secret)
        
        # 使用验证后的令牌调用用户中心API
        profile_response = client.users.get_profile()
        
        if profile_response.success:
            return JsonResponse({
                "success": True,
                "message": "Cross-app authentication successful",
                "user": profile_response.data,
            })
        else:
            return JsonResponse({
                "success": False,
                "message": profile_response.message,
            }, status=401)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


# ===== Django配置示例 =====

"""
# 在应用A的settings.py中添加以下配置
USER_CENTER_SDK = {
    "API_BASE_URL": "http://localhost:5200/api/v1/",
    "API_KEY": "usercenter2025",
    "APP_ID": "app_a_id",
    "APP_SECRET": "app_a_secret",
    "SSO_ENABLED": True,
    "SSO_AUTO_REDIRECT": False,
    "SSO_CALLBACK_PATH": "/auth/callback/",
    "TRUSTED_APPS": {
        "app_b_id": "app_b_secret",  # 信任应用B
    }
}

MIDDLEWARE = [
    # ...其他中间件...
    'user_center_sdk.django.UserCenterAuthMiddleware',
    'user_center_sdk.django.UserCenterSSOMiddleware',
]

# 在应用A的urls.py中添加以下URL配置
urlpatterns = [
    path('', app_a_home, name='home'),
    path('login/', app_a_login, name='login'),
    path('logout/', app_a_logout, name='logout'),
    path('auth/callback/', app_a_callback, name='auth_callback'),
]
"""

"""
# 在应用B的settings.py中添加以下配置
USER_CENTER_SDK = {
    "API_BASE_URL": "http://localhost:5200/api/v1/",
    "API_KEY": "usercenter2025",
    "APP_ID": "app_b_id",
    "APP_SECRET": "app_b_secret",
    "SSO_ENABLED": True,
    "SSO_AUTO_REDIRECT": False,
    "SSO_CALLBACK_PATH": "/auth/callback/",
    "TRUSTED_APPS": {
        "app_a_id": "app_a_secret",  # 信任应用A
    }
}

MIDDLEWARE = [
    # ...其他中间件...
    'user_center_sdk.django.UserCenterAuthMiddleware',
    'user_center_sdk.django.UserCenterSSOMiddleware',
]

# 在应用B的urls.py中添加以下URL配置
urlpatterns = [
    path('', app_b_home, name='home'),
    path('process_token/', app_b_process_sso_token, name='process_token'),
    path('api/endpoint/', app_b_api_endpoint, name='api_endpoint'),
]
"""


# ===== 主函数 =====

if __name__ == "__main__":
    print("这是一个Django示例，请在Django应用中使用上述代码。")
    print("请参考注释中的配置示例，将相关代码添加到您的Django应用中。")
