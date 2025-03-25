# 用户中心SDK跨应用登录集成指南 (v1.1.0)

本指南将帮助您快速集成用户中心SDK的跨应用登录功能，实现应用间的无缝登录体验。

## 版本更新说明

**v1.1.0更新**：
- 修复了SSO客户端的多个测试问题
- 改进了跨应用令牌验证机制
- 增强了API监控功能，支持更灵活的请求记录
- 优化了令牌共享和验证的安全性

## 1. 安装

```bash
pip install user-center-sdk==1.1.0
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

## 4. 跨应用登录集成

### 4.1 概述

跨应用登录功能允许用户在一个应用（源应用）登录后，无需重新登录即可访问其他应用（目标应用）。此功能基于JWT令牌和SSO机制实现。

关键特性：
- **令牌共享机制**：在不同应用间安全地共享访问令牌和刷新令牌
- **跨应用令牌验证**：确保一个应用生成的令牌可以被其他应用验证
- **单点登录(SSO)支持**：统一的登录入口和会话管理
- **安全性保障**：防止令牌被盗用，确保数据传输安全

### 4.2 创建跨应用令牌

当用户需要从一个应用跳转到另一个应用时，源应用需要生成一个跨应用令牌：

```python
# 在源应用中创建跨应用令牌
target_app_id = "app_b"  # 目标应用ID
cross_app_token = client.create_cross_app_token(target_app_id)

# 构建跳转URL
redirect_url = f"https://app-b.example.com/auth/sso?token={cross_app_token}"
```

### 4.3 验证跨应用令牌

目标应用接收到跨应用令牌后，需要验证其有效性：

```python
# 在目标应用中验证跨应用令牌
source_app_id = "app_a"  # 源应用ID
source_app_secret = settings.USER_CENTER_SDK["TRUSTED_APPS"].get(source_app_id)

# 验证令牌
valid, payload = client.validate_cross_app_token(
    token=cross_app_token,
    source_app_id=source_app_id,
    source_app_secret=source_app_secret
)

if valid:
    # 令牌有效，允许用户访问
    user_id = payload.get("user_id")
    # 处理用户登录逻辑...
else:
    # 令牌无效，拒绝访问
    # 重定向到登录页面...
```

## 8. API监控集成

SDK现已增强API监控功能，可以记录所有API请求和响应，帮助您跟踪和分析API使用情况。

### 8.1 配置API监控

在配置文件中启用API监控：

```python
# 用户中心SDK配置
USER_CENTER_SDK = {
    # ...其他配置...
    
    # API监控配置
    "API_MONITORING": {
        "ENABLED": True,  # 是否启用API监控
        "LOG_LEVEL": "INFO",  # 日志级别
        "STORE_REQUESTS": True,  # 是否存储请求内容
        "STORE_RESPONSES": True,  # 是否存储响应内容
        "EXCLUDE_PATHS": ["/health-check"],  # 排除监控的路径
    },
}
```

### 8.2 访问API监控数据

您可以通过管理后台访问API监控数据：

- API请求历史：`/admin/api_monitor/request/`
- API端点统计：`/admin/api_monitor/endpoint/`
- API服务状态：`/admin/api_monitor/dashboard/`

### 8.3 API文档访问

用户中心提供了Swagger和ReDoc风格的API文档，您可以通过以下路径访问：

- Swagger UI：`/docs/swagger/`
- ReDoc：`/docs/redoc/`
- Swagger JSON：`/docs/swagger.json`

可以使用API密钥访问文档：`?api_key=usercenter2025`

## 9. 故障排除与问题解决

### 9.1 常见问题

#### SSO客户端初始化失败

如果您遇到SSO客户端初始化失败的问题，请确保：

1. 正确设置了应用凭证：
```python
client.sso.set_app_credentials("your_app_id", "your_app_secret")
```

2. 检查API基础URL是否正确配置，包含协议和末尾斜杠：
```python
# 正确: "https://user-center-api.example.com/api/v1/"
# 错误: "user-center-api.example.com/api/v1"
```

#### 跨应用令牌验证失败

如果跨应用令牌验证失败，请检查：

1. 源应用ID和密钥是否正确
2. 令牌是否已过期
3. 令牌的签发者(iss)和受众(aud)是否匹配

### 9.2 获取帮助

如遇问题，请通过以下方式获取帮助：

- GitHub Issues: https://github.com/Marusmurong/cross-app-login/issues
- 邮件支持: support@usercenter.example.com
