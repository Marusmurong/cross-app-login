# 用户中心SDK跨应用登录集成指南

本指南将帮助您快速集成用户中心SDK的跨应用登录功能，实现应用间的无缝登录体验。

## 1. 安装

```bash
pip install user-center-sdk
```

## 2. 基本配置

### 2.1 Django设置

在Django项目的`settings.py`中添加以下配置：

```python
# 用户中心SDK配置
USER_CENTER_SDK = {
    # 基础配置
    "API_BASE_URL": "https://user-center-api.example.com/api/v1/",  # 用户中心API基础URL
    "API_KEY": "your_api_key",  # API密钥
    
    # 应用凭证（用于跨应用登录）
    "APP_ID": "your_app_id",  # 应用ID
    "APP_SECRET": "your_app_secret",  # 应用密钥
    
    # SSO配置
    "SSO_ENABLED": True,  # 是否启用SSO
    "SSO_AUTO_REDIRECT": False,  # 是否自动重定向到登录页面（未登录时）
    "SSO_CALLBACK_PATH": "/auth/callback/",  # SSO回调路径
    
    # 信任的应用列表（用于跨应用令牌验证）
    "TRUSTED_APPS": {
        "app_b_id": "app_b_secret",  # 应用B的ID和密钥
        # 可添加更多信任的应用
    },
    
    # 可选配置
    "DEFAULT_TIMEOUT": 10,  # 请求超时时间（秒）
    "MAX_RETRIES": 3,  # 最大重试次数
    "CACHE_ENABLED": True,  # 是否启用缓存
    "CACHE_TIMEOUT": 300,  # 缓存超时时间（秒）
    "AUTO_REFRESH_TOKEN": True,  # 是否自动刷新令牌
}

# 添加中间件
MIDDLEWARE = [
    # ...其他中间件...
    'user_center_sdk.django.UserCenterAuthMiddleware',  # 用户认证中间件
    'user_center_sdk.django.UserCenterSSOMiddleware',   # SSO中间件
]
```

### 2.2 URL配置

在Django项目的`urls.py`中添加SSO回调处理：

```python
from django.urls import path
from your_app.views import sso_callback

urlpatterns = [
    # ...其他URL...
    path('auth/callback/', sso_callback, name='sso_callback'),
]
```

## 3. 快速实现

### 3.1 创建SSO回调视图

```python
from django.http import HttpRequest, HttpResponseRedirect
from django.shortcuts import redirect

def sso_callback(request: HttpRequest):
    """处理SSO回调"""
    # 从请求中获取授权码
    code = request.GET.get("code")
    
    if not code:
        return redirect("/login-error/")
    
    try:
        # 使用授权码交换访问令牌
        # 注意：用户中心客户端已通过中间件添加到请求对象中
        client = request.user_center_sso
        callback_url = request.build_absolute_uri("/auth/callback/")
        token_data = client.handle_sso_callback(code, callback_url)
        
        # 重定向到原始URL
        redirect_url = request.session.get("sso_redirect_url", "/")
        if "sso_redirect_url" in request.session:
            del request.session["sso_redirect_url"]
        
        return redirect(redirect_url)
    except Exception as e:
        # 处理错误
        return redirect(f"/login-error/?error={str(e)}")
```

### 3.2 创建登录视图

```python
def login(request: HttpRequest):
    """登录页面"""
    # 获取用户中心客户端
    client = request.user_center_sso
    
    # 创建SSO授权URL
    callback_url = request.build_absolute_uri("/auth/callback/")
    auth_url = client.create_sso_url(callback_url)
    
    # 保存重定向URL到会话
    request.session["sso_redirect_url"] = request.GET.get("next", "/")
    
    # 重定向到SSO授权URL
    return redirect(auth_url)
```

### 3.3 创建登出视图

```python
def logout(request: HttpRequest):
    """登出处理"""
    # 获取用户中心客户端
    client = request.user_center
    
    # 登出
    client.auth.logout()
    
    # 重定向到首页
    return redirect("/")
```

### 3.4 创建跨应用链接

```python
def dashboard(request: HttpRequest):
    """仪表盘页面"""
    # 获取用户中心客户端
    client = request.user_center
    
    # 获取用户资料
    profile_response = client.users.get_profile()
    
    if profile_response.success:
        # 用户已登录，创建跳转到应用B的链接
        app_b_url = "https://app-b.example.com/"
        app_b_link = client.create_login_url_with_token(app_b_url)
        
        return render(request, "dashboard.html", {
            "user": profile_response.data,
            "app_b_link": app_b_link,
        })
    else:
        # 用户未登录，重定向到登录页面
        return redirect("/login/")
```

## 4. 高级功能

### 4.1 使用装饰器保护视图

```python
from user_center_sdk.django.decorators import login_required

@login_required
def protected_view(request):
    """受保护的视图"""
    # 只有已登录用户才能访问
    return render(request, "protected.html")
```

### 4.2 API端点接收跨应用令牌

```python
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

@require_http_methods(["POST"])
def api_endpoint(request: HttpRequest):
    """API端点，接受来自其他应用的跨应用令牌"""
    # 从请求头中获取跨应用令牌和应用ID
    cross_app_token = request.headers.get("X-User-Center-Token")
    app_id = request.headers.get("X-User-Center-App-ID")
    
    if not cross_app_token or not app_id:
        return JsonResponse({"error": "Missing token or app ID"}, status=400)
    
    try:
        # 验证跨应用令牌
        client = request.user_center_sso
        trusted_apps = getattr(request, "USER_CENTER_SDK", {}).get("TRUSTED_APPS", {})
        
        if app_id not in trusted_apps:
            return JsonResponse({"error": "Untrusted app ID"}, status=403)
            
        app_secret = trusted_apps[app_id]
        payload = client.validate_cross_app_token(cross_app_token, app_id, app_secret)
        
        # 处理请求
        return JsonResponse({
            "success": True,
            "message": "Cross-app authentication successful",
            "user_id": payload.get("user_id"),
        })
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)
```

## 5. 测试跨应用登录

### 5.1 测试SSO登录流程

1. 用户访问应用A
2. 用户点击登录按钮，重定向到SSO登录页面
3. 用户登录成功后，重定向回应用A
4. 验证用户已成功登录应用A

### 5.2 测试跨应用跳转

1. 用户在应用A中登录
2. 用户点击跳转到应用B的链接
3. 验证用户无需登录即可访问应用B

### 5.3 自动化测试

```python
from django.test import TestCase, Client
from unittest.mock import patch

class SSOTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        
    @patch('user_center_sdk.UserCenterClient.handle_sso_callback')
    def test_sso_callback(self, mock_handle_callback):
        # 模拟SSO回调
        mock_handle_callback.return_value = {"access_token": "test_token"}
        
        # 发送请求
        response = self.client.get('/auth/callback/?code=test_code')
        
        # 验证重定向
        self.assertEqual(response.status_code, 302)
        
    @patch('user_center_sdk.UserCenterClient.create_login_url_with_token')
    def test_cross_app_link(self, mock_create_link):
        # 模拟创建跨应用链接
        mock_create_link.return_value = "https://app-b.example.com/?sso_token=test_token"
        
        # 登录
        self.client.session['user_center_access_token'] = 'test_token'
        self.client.session['user_center_refresh_token'] = 'test_refresh_token'
        self.client.session.save()
        
        # 访问仪表盘
        response = self.client.get('/dashboard/')
        
        # 验证链接
        self.assertContains(response, "https://app-b.example.com/?sso_token=test_token")
```

## 6. 故障排除

### 6.1 常见问题

1. **令牌验证失败**
   - 检查应用ID和密钥是否正确
   - 确保信任的应用列表配置正确

2. **SSO回调处理失败**
   - 检查回调URL是否与请求授权码时使用的URL一致
   - 确保授权码未过期（通常只有几分钟有效期）

3. **跨应用跳转后未登录**
   - 检查目标应用是否正确配置了SSO中间件
   - 确保目标应用信任源应用

### 6.2 日志调试

在`settings.py`中添加日志配置：

```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'user_center_sdk': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
    },
}
```

## 7. 安全最佳实践

1. **使用HTTPS**：所有涉及令牌传输的请求都应使用HTTPS
2. **设置适当的令牌过期时间**：跨应用令牌的过期时间不宜过长
3. **验证应用来源**：始终验证令牌的颁发者和接收者
4. **限制信任的应用**：只信任必要的应用
5. **定期轮换密钥**：定期更新应用密钥

## 8. 快速检查清单

- [ ] 安装用户中心SDK
- [ ] 在`settings.py`中添加SDK配置
- [ ] 添加认证和SSO中间件
- [ ] 创建SSO回调处理视图
- [ ] 配置信任的应用列表
- [ ] 实现登录和登出视图
- [ ] 测试SSO登录流程
- [ ] 测试跨应用跳转
- [ ] 配置日志记录
- [ ] 检查安全设置
