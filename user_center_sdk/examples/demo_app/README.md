# 用户中心SDK跨应用登录演示应用

这是一个简单的演示应用，展示如何使用用户中心SDK实现跨应用登录功能。

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置应用

使用快速安装脚本配置应用A：

```bash
cd app_a
python ../../scripts/setup_sso.py \
    --app-id "app_a_id" \
    --app-secret "app_a_secret" \
    --api-base-url "http://localhost:5200/api/v1/" \
    --api-key "usercenter2025" \
    --trusted-apps '{"app_b_id": "app_b_secret"}'
```

使用快速安装脚本配置应用B：

```bash
cd app_b
python ../../scripts/setup_sso.py \
    --app-id "app_b_id" \
    --app-secret "app_b_secret" \
    --api-base-url "http://localhost:5200/api/v1/" \
    --api-key "usercenter2025" \
    --trusted-apps '{"app_a_id": "app_a_secret"}'
```

### 3. 运行应用

启动应用A：

```bash
cd app_a
python manage.py runserver 8001
```

启动应用B：

```bash
cd app_b
python manage.py runserver 8002
```

### 4. 测试跨应用登录

1. 访问应用A：http://localhost:8001
2. 点击"登录"按钮
3. 在用户中心登录页面输入用户名和密码
4. 登录成功后，将自动重定向回应用A
5. 点击"访问应用B"链接
6. 验证无需登录即可访问应用B

## 目录结构

```
demo_app/
├── README.md                 # 说明文档
├── app_a/                    # 应用A
│   ├── manage.py             # Django管理脚本
│   ├── app_a/                # 应用A项目
│   │   ├── __init__.py
│   │   ├── settings.py       # 配置文件
│   │   ├── urls.py           # URL配置
│   │   ├── views.py          # 视图函数
│   │   └── wsgi.py
│   └── templates/            # 模板文件
│       ├── base.html
│       ├── home.html
│       └── dashboard.html
├── app_b/                    # 应用B
│   ├── manage.py             # Django管理脚本
│   ├── app_b/                # 应用B项目
│   │   ├── __init__.py
│   │   ├── settings.py       # 配置文件
│   │   ├── urls.py           # URL配置
│   │   ├── views.py          # 视图函数
│   │   └── wsgi.py
│   └── templates/            # 模板文件
│       ├── base.html
│       ├── home.html
│       └── dashboard.html
└── requirements.txt          # 依赖列表
```

## 关键功能

### 应用A

- 登录/登出功能
- 用户资料显示
- 创建跨应用链接到应用B
- SSO回调处理

### 应用B

- 处理来自应用A的SSO令牌
- 用户资料显示
- 创建跨应用链接到应用A
- API端点接收跨应用令牌

## 技术细节

- 使用JWT进行跨应用令牌签名和验证
- 使用Base64编码传输令牌
- 使用Django会话存储令牌
- 使用用户中心SDK中间件自动处理令牌刷新
