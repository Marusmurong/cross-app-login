# 用户中心系统

这是一个基于Django和Django REST Framework构建的用户中心系统，提供用户管理、积分系统、VIP会员功能和跨应用登录态保持功能。

## 功能特性

### 用户管理
- 用户注册、登录、注销
- JWT认证
- 用户资料管理
- 第三方账号绑定
- 密码修改

### 积分系统
- 积分记录管理
- 积分规则配置
- 积分增减操作
- 积分统计

### VIP系统
- VIP等级管理
- VIP订阅管理
- VIP状态查询

### 跨应用登录态保持
- 令牌共享机制：在不同应用间安全地共享访问令牌和刷新令牌
- 跨应用令牌验证：确保一个应用生成的令牌可以被其他应用验证
- 单点登录(SSO)支持：统一的登录入口和会话管理
- 安全性保障：防止令牌被盗用，确保数据传输安全

## 技术栈

- **Django**: Web框架
- **Django REST Framework (DRF)**: RESTful API框架
- **PostgreSQL**: 数据库
- **Redis**: 缓存和令牌管理
- **djangorestframework-simplejwt**: JWT认证
- **django-cors-headers**: 跨域资源共享
- **PyJWT**: 用于跨应用令牌的生成和验证

## 安装和配置

### 环境要求
- Python 3.8+
- PostgreSQL
- Redis

### 安装步骤

1. 克隆代码库
```bash
git clone <repository-url>
cd user_center
```

2. 创建虚拟环境并安装依赖
```bash
python -m venv venv
source venv/bin/activate  # 在Windows上使用 venv\Scripts\activate
pip install -r requirements.txt
```

3. 配置环境变量
创建`.env`文件，并设置以下变量：
```
DEBUG=True
SECRET_KEY=your-secret-key
DATABASE_URL=postgres://user:password@localhost:5432/user_center
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
```

4. 运行数据库迁移
```bash
python manage.py migrate
```

5. 创建超级用户
```bash
python manage.py createsuperuser
```

6. 启动开发服务器
```bash
python manage.py runserver
```

## API文档

启动服务器后，可以通过以下URL访问API文档：
```
http://localhost:8000/docs/
```

## API端点

### 用户相关
- `POST /api/v1/user/register/`: 用户注册
- `POST /api/v1/user/login/`: 用户登录
- `POST /api/v1/user/logout/`: 用户注销
- `POST /api/v1/user/token/refresh/`: 刷新JWT令牌
- `GET /api/v1/user/profile/`: 获取用户资料
- `PUT /api/v1/user/profile/`: 更新用户资料
- `POST /api/v1/user/change-password/`: 修改密码

### 积分相关
- `GET /api/v1/points/records/`: 获取积分记录
- `GET /api/v1/points/summary/`: 获取积分统计
- `POST /api/v1/points/add/`: (管理员) 添加积分
- `POST /api/v1/points/deduct/`: (管理员) 扣减积分
- `GET /api/v1/points/rules/`: 获取积分规则

### VIP相关
- `GET /api/v1/vip/status/`: 获取VIP状态
- `GET /api/v1/vip/levels/`: 获取VIP等级列表
- `GET /api/v1/vip/subscriptions/`: 获取VIP订阅记录
- `POST /api/v1/vip/subscribe/`: (管理员) 订阅VIP

### SSO和跨应用登录相关
- `GET /api/v1/sso/authorize/`: 获取授权页面
- `POST /api/v1/sso/token/`: 使用授权码交换令牌
- `POST /api/v1/sso/token/generate/`: 生成SSO令牌
- `POST /api/v1/sso/token/validate/`: 验证SSO令牌

## 开发指南

### 添加新的积分规则

1. 通过管理员后台添加新的积分规则
2. 在业务代码中使用积分服务添加积分记录：

```python
from points.services import add_points_by_rule

# 使用规则代码添加积分
add_points_by_rule(user, 'sign_in', site_code='main')
```

### 添加新的VIP等级

通过管理员后台添加新的VIP等级，设置相应的价格和功能特性。

### 集成跨应用登录功能

1. 安装用户中心SDK
```bash
pip install user-center-sdk
```

2. 在Django设置中添加配置
```python
# 用户中心SDK配置
USER_CENTER_SDK = {
    "API_BASE_URL": "https://user-center-api.example.com/api/v1/",
    "API_KEY": "your_api_key",
    "APP_ID": "your_app_id",
    "APP_SECRET": "your_app_secret",
    "SSO_ENABLED": True,
    "TRUSTED_APPS": {
        "other_app_id": "other_app_secret",
    }
}

MIDDLEWARE = [
    # ...其他中间件...
    'user_center_sdk.django.UserCenterAuthMiddleware',
    'user_center_sdk.django.UserCenterSSOMiddleware',
]
```

3. 使用快速安装脚本
```bash
python -m user_center_sdk.scripts.setup_sso --app-id "your_app_id" --app-secret "your_app_secret" --api-base-url "https://user-center-api.example.com/api/v1/" --api-key "your_api_key"
```

4. 查看完整的集成指南
```
docs/sso_integration_guide.md
```

## 许可证

[MIT License](LICENSE)
