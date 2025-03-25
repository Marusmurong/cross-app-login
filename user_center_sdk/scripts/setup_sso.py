#!/usr/bin/env python
"""
用户中心SDK跨应用登录快速安装脚本

此脚本帮助快速配置Django项目以支持用户中心SDK的跨应用登录功能。
运行方式：python setup_sso.py
"""

import os
import sys
import json
import argparse
import re
from pathlib import Path


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="用户中心SDK跨应用登录快速安装脚本")
    parser.add_argument("--app-id", help="应用ID", required=True)
    parser.add_argument("--app-secret", help="应用密钥", required=True)
    parser.add_argument("--api-base-url", help="用户中心API基础URL", required=True)
    parser.add_argument("--api-key", help="API密钥", required=True)
    parser.add_argument("--project-dir", help="Django项目目录", default=".")
    parser.add_argument("--trusted-apps", help="信任的应用列表，格式为JSON字符串", default="{}")
    parser.add_argument("--auto-redirect", help="是否自动重定向到登录页面", action="store_true")
    parser.add_argument("--callback-path", help="SSO回调路径", default="/auth/callback/")
    return parser.parse_args()


def update_settings(args):
    """更新Django设置文件"""
    settings_path = Path(args.project_dir) / "settings.py"
    
    if not settings_path.exists():
        # 尝试查找settings.py文件
        settings_files = list(Path(args.project_dir).glob("**/settings.py"))
        if not settings_files:
            print("错误：找不到settings.py文件")
            return False
        settings_path = settings_files[0]
        print(f"找到settings.py文件：{settings_path}")
    
    # 读取设置文件内容
    with open(settings_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # 解析信任的应用列表
    try:
        trusted_apps = json.loads(args.trusted_apps)
    except json.JSONDecodeError:
        print("错误：信任的应用列表格式不正确，应为JSON字符串")
        return False
    
    # 格式化信任的应用列表为Python字典字符串
    trusted_apps_str = "{\n"
    for app_id, app_secret in trusted_apps.items():
        trusted_apps_str += f'        "{app_id}": "{app_secret}",\n'
    trusted_apps_str += "    }"
    
    # 构建SDK配置
    sdk_config = f"""
# 用户中心SDK配置
USER_CENTER_SDK = {{
    # 基础配置
    "API_BASE_URL": "{args.api_base_url}",
    "API_KEY": "{args.api_key}",
    
    # 应用凭证（用于跨应用登录）
    "APP_ID": "{args.app_id}",
    "APP_SECRET": "{args.app_secret}",
    
    # SSO配置
    "SSO_ENABLED": True,
    "SSO_AUTO_REDIRECT": {str(args.auto_redirect).lower()},
    "SSO_CALLBACK_PATH": "{args.callback_path}",
    
    # 信任的应用列表（用于跨应用令牌验证）
    "TRUSTED_APPS": {trusted_apps_str},
    
    # 可选配置
    "DEFAULT_TIMEOUT": 10,
    "MAX_RETRIES": 3,
    "CACHE_ENABLED": True,
    "CACHE_TIMEOUT": 300,
    "AUTO_REFRESH_TOKEN": True,
}}
"""
    
    # 检查是否已存在SDK配置
    if "USER_CENTER_SDK" in content:
        print("警告：USER_CENTER_SDK配置已存在，将被替换")
        # 替换现有配置
        pattern = r"USER_CENTER_SDK\s*=\s*\{[^}]*\}"
        content = re.sub(pattern, f"USER_CENTER_SDK = {{\n    # 配置已被setup_sso.py脚本更新", content, flags=re.DOTALL)
    
    # 添加SDK配置
    if "INSTALLED_APPS" in content:
        # 在INSTALLED_APPS后添加配置
        content = content.replace("INSTALLED_APPS", f"{sdk_config}\nINSTALLED_APPS")
    else:
        # 添加到文件末尾
        content += f"\n{sdk_config}\n"
    
    # 添加中间件
    middleware_pattern = r"MIDDLEWARE\s*=\s*\[(.*?)\]"
    middleware_match = re.search(middleware_pattern, content, re.DOTALL)
    
    if middleware_match:
        middleware_content = middleware_match.group(1)
        
        # 检查是否已存在中间件
        if "UserCenterAuthMiddleware" not in middleware_content:
            # 添加认证中间件
            new_middleware = middleware_content.rstrip() + "\n    'user_center_sdk.django.UserCenterAuthMiddleware',"
            
            # 添加SSO中间件
            if "UserCenterSSOMiddleware" not in middleware_content:
                new_middleware += "\n    'user_center_sdk.django.UserCenterSSOMiddleware',"
            
            # 替换中间件配置
            content = content.replace(middleware_content, new_middleware)
    else:
        print("警告：找不到MIDDLEWARE配置，请手动添加中间件")
    
    # 保存更新后的设置文件
    with open(settings_path, "w", encoding="utf-8") as f:
        f.write(content)
    
    print(f"已更新Django设置文件：{settings_path}")
    return True


def create_callback_view(args):
    """创建SSO回调视图"""
    views_path = Path(args.project_dir) / "views.py"
    
    if not views_path.exists():
        # 尝试查找views.py文件
        views_files = list(Path(args.project_dir).glob("**/views.py"))
        if not views_files:
            print("警告：找不到views.py文件，将创建新文件")
            # 尝试在项目目录下创建views.py
            views_path = Path(args.project_dir) / "views.py"
        else:
            views_path = views_files[0]
            print(f"找到views.py文件：{views_path}")
    
    # 回调视图代码
    callback_view = """
# 用户中心SDK SSO回调处理
from django.http import HttpRequest, HttpResponseRedirect
from django.shortcuts import redirect

def sso_callback(request: HttpRequest):
    \"\"\"处理SSO回调\"\"\"
    # 从请求中获取授权码
    code = request.GET.get("code")
    
    if not code:
        return redirect("/")
    
    try:
        # 使用授权码交换访问令牌
        client = request.user_center_sso
        callback_url = request.build_absolute_uri("{callback_path}")
        token_data = client.handle_sso_callback(code, callback_url)
        
        # 重定向到原始URL
        redirect_url = request.session.get("sso_redirect_url", "/")
        if "sso_redirect_url" in request.session:
            del request.session["sso_redirect_url"]
        
        return redirect(redirect_url)
    except Exception as e:
        # 处理错误
        print(f"SSO回调处理错误：{{str(e)}}")
        return redirect("/")

def login(request: HttpRequest):
    \"\"\"登录页面\"\"\"
    # 获取用户中心客户端
    client = request.user_center_sso
    
    # 创建SSO授权URL
    callback_url = request.build_absolute_uri("{callback_path}")
    auth_url = client.create_sso_url(callback_url)
    
    # 保存重定向URL到会话
    request.session["sso_redirect_url"] = request.GET.get("next", "/")
    
    # 重定向到SSO授权URL
    return redirect(auth_url)

def logout(request: HttpRequest):
    \"\"\"登出处理\"\"\"
    # 获取用户中心客户端
    client = request.user_center
    
    # 登出
    client.auth.logout()
    
    # 重定向到首页
    return redirect("/")
""".format(callback_path=args.callback_path)
    
    # 读取视图文件内容
    if views_path.exists():
        with open(views_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # 检查是否已存在回调视图
        if "sso_callback" in content:
            print("警告：sso_callback视图已存在，将被跳过")
            return True
        
        # 添加回调视图
        content += f"\n{callback_view}\n"
    else:
        # 创建新的视图文件
        content = f"""\"\"\"
视图模块
\"\"\"

{callback_view}
"""
    
    # 保存更新后的视图文件
    with open(views_path, "w", encoding="utf-8") as f:
        f.write(content)
    
    print(f"已创建SSO回调视图：{views_path}")
    return True


def update_urls(args):
    """更新URL配置"""
    urls_path = Path(args.project_dir) / "urls.py"
    
    if not urls_path.exists():
        # 尝试查找urls.py文件
        urls_files = list(Path(args.project_dir).glob("**/urls.py"))
        if not urls_files:
            print("错误：找不到urls.py文件")
            return False
        urls_path = urls_files[0]
        print(f"找到urls.py文件：{urls_path}")
    
    # 读取URL配置文件内容
    with open(urls_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # 检查是否已导入path
    if "from django.urls import path" not in content:
        if "from django.urls import" in content:
            # 更新导入
            content = content.replace("from django.urls import", "from django.urls import path,")
        else:
            # 添加导入
            content = "from django.urls import path\n" + content
    
    # 检查是否已导入视图
    views_import = "from .views import sso_callback, login, logout"
    if "from .views import" in content:
        if "sso_callback" not in content:
            # 更新导入
            content = content.replace("from .views import", "from .views import sso_callback, login, logout,")
    else:
        # 添加导入
        content = f"{views_import}\n" + content
    
    # 检查是否已添加URL配置
    callback_path = args.callback_path.lstrip("/")
    url_pattern = f"path('{callback_path}', sso_callback, name='sso_callback')"
    
    if url_pattern not in content:
        # 查找urlpatterns
        urlpatterns_match = re.search(r"urlpatterns\s*=\s*\[(.*?)\]", content, re.DOTALL)
        
        if urlpatterns_match:
            urlpatterns_content = urlpatterns_match.group(1)
            
            # 添加URL配置
            new_urlpatterns = urlpatterns_content.rstrip() + f"""
    # 用户中心SDK SSO回调
    path('{callback_path}', sso_callback, name='sso_callback'),
    path('login/', login, name='login'),
    path('logout/', logout, name='logout'),"""
            
            # 替换URL配置
            content = content.replace(urlpatterns_content, new_urlpatterns)
        else:
            print("警告：找不到urlpatterns配置，请手动添加URL配置")
    else:
        print("警告：SSO回调URL配置已存在，将被跳过")
    
    # 保存更新后的URL配置文件
    with open(urls_path, "w", encoding="utf-8") as f:
        f.write(content)
    
    print(f"已更新URL配置：{urls_path}")
    return True


def check_dependencies():
    """检查依赖"""
    try:
        import django
        print(f"检测到Django版本：{django.__version__}")
    except ImportError:
        print("警告：未检测到Django，请确保已安装Django")
        return False
    
    try:
        import user_center_sdk
        print(f"检测到用户中心SDK")
    except ImportError:
        print("错误：未检测到用户中心SDK，请先安装用户中心SDK")
        print("安装命令：pip install user-center-sdk")
        return False
    
    return True


def main():
    """主函数"""
    args = parse_args()
    
    print("=== 用户中心SDK跨应用登录快速安装 ===")
    
    # 检查依赖
    if not check_dependencies():
        return 1
    
    # 更新Django设置
    if not update_settings(args):
        return 1
    
    # 创建回调视图
    if not create_callback_view(args):
        return 1
    
    # 更新URL配置
    if not update_urls(args):
        return 1
    
    print("\n=== 安装完成 ===")
    print("请检查以下事项：")
    print("1. 确保在settings.py中正确配置了USER_CENTER_SDK")
    print("2. 确保在MIDDLEWARE中添加了UserCenterAuthMiddleware和UserCenterSSOMiddleware")
    print(f"3. 确保在urls.py中添加了SSO回调路径：{args.callback_path}")
    print("4. 重启Django服务器以应用更改")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
