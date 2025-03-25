"""
用户中心SDK的Django集成示例
"""

# 在Django项目的settings.py中添加以下配置
SETTINGS_EXAMPLE = """
# 用户中心SDK配置
USER_CENTER_SDK = {
    'API_BASE_URL': 'http://localhost:5200/api/v1/',
    'API_KEY': 'usercenter2025',
    'DEFAULT_TIMEOUT': 10,
    'MAX_RETRIES': 3,
    'CACHE_ENABLED': True,
    'CACHE_TIMEOUT': 300,
    'AUTO_REFRESH_TOKEN': True,
}

# 将用户中心SDK中间件添加到MIDDLEWARE中
MIDDLEWARE = [
    # ...其他中间件...
    'user_center_sdk.django.UserCenterAuthMiddleware',
    # ...其他中间件...
]

# 登录URL，用于login_required装饰器
LOGIN_URL = '/login/'

# VIP升级URL，用于vip_required装饰器
VIP_UPGRADE_URL = '/vip/upgrade/'
"""

# 在Django视图中使用SDK的示例
VIEWS_EXAMPLE = """
from django.shortcuts import render, redirect
from django.http import HttpRequest, HttpResponse
from django.contrib import messages

# 导入用户中心SDK的装饰器
from user_center_sdk.django import login_required, vip_required


def login_view(request: HttpRequest) -> HttpResponse:
    """
    登录视图
    """
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        # 使用用户中心SDK进行登录
        response = request.user_center.auth.login(
            username=username,
            password=password,
        )
        
        if response.success:
            # 登录成功，将令牌保存到会话中
            request.session['user_center_access_token'] = response.data.get('access')
            request.session['user_center_refresh_token'] = response.data.get('refresh')
            
            # 重定向到首页
            next_url = request.GET.get('next', '/')
            return redirect(next_url)
        else:
            # 登录失败，显示错误消息
            messages.error(request, f'登录失败: {response.message}')
    
    return render(request, 'login.html')


def logout_view(request: HttpRequest) -> HttpResponse:
    """
    登出视图
    """
    # 使用用户中心SDK进行登出
    request.user_center.auth.logout()
    
    # 清除会话中的令牌
    if 'user_center_access_token' in request.session:
        del request.session['user_center_access_token']
    if 'user_center_refresh_token' in request.session:
        del request.session['user_center_refresh_token']
    
    # 重定向到登录页面
    return redirect('login')


@login_required
def profile_view(request: HttpRequest) -> HttpResponse:
    """
    用户资料视图，需要登录
    """
    # 获取用户资料
    profile_response = request.user_center.users.get_profile()
    
    if profile_response.success:
        # 获取成功，渲染用户资料页面
        return render(request, 'profile.html', {
            'profile': profile_response.data,
        })
    else:
        # 获取失败，显示错误消息
        messages.error(request, f'获取用户资料失败: {profile_response.message}')
        return redirect('login')


@login_required
def update_profile_view(request: HttpRequest) -> HttpResponse:
    """
    更新用户资料视图，需要登录
    """
    if request.method == 'POST':
        # 获取表单数据
        nickname = request.POST.get('nickname')
        bio = request.POST.get('bio')
        
        # 使用用户中心SDK更新用户资料
        response = request.user_center.users.update_profile(
            nickname=nickname,
            bio=bio,
        )
        
        if response.success:
            # 更新成功，显示成功消息
            messages.success(request, '用户资料更新成功')
        else:
            # 更新失败，显示错误消息
            messages.error(request, f'用户资料更新失败: {response.message}')
    
    # 重定向到用户资料页面
    return redirect('profile')


@vip_required
def vip_content_view(request: HttpRequest) -> HttpResponse:
    """
    VIP内容视图，需要VIP权限
    """
    # 获取VIP权益
    benefits_response = request.user_center.vip.get_vip_benefits()
    
    if benefits_response.success:
        # 获取成功，渲染VIP内容页面
        return render(request, 'vip_content.html', {
            'benefits': benefits_response.data,
        })
    else:
        # 获取失败，显示错误消息
        messages.error(request, f'获取VIP权益失败: {benefits_response.message}')
        return redirect('home')


@vip_required(vip_level=2)
def premium_content_view(request: HttpRequest) -> HttpResponse:
    """
    高级VIP内容视图，需要VIP等级2及以上
    """
    # 渲染高级VIP内容页面
    return render(request, 'premium_content.html')
"""

# 在Django模板中使用SDK的示例
TEMPLATE_EXAMPLE = """
<!-- 用户资料页面示例 -->
<!DOCTYPE html>
<html>
<head>
    <title>用户资料</title>
</head>
<body>
    <h1>用户资料</h1>
    
    <div>
        <p><strong>用户名:</strong> {{ profile.username }}</p>
        <p><strong>邮箱:</strong> {{ profile.email }}</p>
        <p><strong>手机号:</strong> {{ profile.phone }}</p>
        <p><strong>昵称:</strong> {{ profile.nickname }}</p>
        <p><strong>个人简介:</strong> {{ profile.bio }}</p>
    </div>
    
    <h2>修改资料</h2>
    <form method="post" action="{% url 'update_profile' %}">
        {% csrf_token %}
        <div>
            <label for="nickname">昵称:</label>
            <input type="text" id="nickname" name="nickname" value="{{ profile.nickname }}">
        </div>
        <div>
            <label for="bio">个人简介:</label>
            <textarea id="bio" name="bio">{{ profile.bio }}</textarea>
        </div>
        <button type="submit">保存</button>
    </form>
    
    <h2>积分信息</h2>
    <div id="points-info">
        <!-- 使用JavaScript获取积分信息 -->
    </div>
    
    <h2>VIP状态</h2>
    <div id="vip-status">
        <!-- 使用JavaScript获取VIP状态 -->
    </div>
    
    <script>
        // 使用JavaScript获取积分信息
        fetch('/api/points/')
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    document.getElementById('points-info').innerHTML = `
                        <p><strong>积分:</strong> ${data.data.points}</p>
                        <p><strong>等级:</strong> ${data.data.level}</p>
                    `;
                } else {
                    document.getElementById('points-info').innerHTML = `
                        <p>获取积分信息失败: ${data.message}</p>
                    `;
                }
            });
        
        // 使用JavaScript获取VIP状态
        fetch('/api/vip/status/')
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    const isVip = data.data.is_vip;
                    if (isVip) {
                        document.getElementById('vip-status').innerHTML = `
                            <p><strong>VIP状态:</strong> 是</p>
                            <p><strong>VIP等级:</strong> ${data.data.level}</p>
                            <p><strong>到期时间:</strong> ${data.data.expire_date}</p>
                        `;
                    } else {
                        document.getElementById('vip-status').innerHTML = `
                            <p><strong>VIP状态:</strong> 否</p>
                            <p><a href="/vip/upgrade/">升级为VIP</a></p>
                        `;
                    }
                } else {
                    document.getElementById('vip-status').innerHTML = `
                        <p>获取VIP状态失败: ${data.message}</p>
                    `;
                }
            });
    </script>
</body>
</html>
"""

# 在Django URL配置中的示例
URLS_EXAMPLE = """
from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    path('profile/update/', views.update_profile_view, name='update_profile'),
    path('vip/content/', views.vip_content_view, name='vip_content'),
    path('vip/premium/', views.premium_content_view, name='premium_content'),
]
"""

# 在Django API视图中使用SDK的示例
API_VIEWS_EXAMPLE = """
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from user_center_sdk.django import login_required


@login_required
@require_http_methods(["GET"])
def points_api_view(request):
    """
    积分API视图
    """
    # 获取用户积分
    response = request.user_center.points.get_points()
    
    # 返回JSON响应
    return JsonResponse({
        'success': response.success,
        'message': response.message,
        'data': response.data,
    })


@login_required
@require_http_methods(["GET"])
def vip_status_api_view(request):
    """
    VIP状态API视图
    """
    # 获取用户VIP状态
    response = request.user_center.vip.get_vip_status()
    
    # 返回JSON响应
    return JsonResponse({
        'success': response.success,
        'message': response.message,
        'data': response.data,
    })
"""

# 在Django API URL配置中的示例
API_URLS_EXAMPLE = """
from django.urls import path
from . import api_views

urlpatterns = [
    path('points/', api_views.points_api_view, name='api_points'),
    path('vip/status/', api_views.vip_status_api_view, name='api_vip_status'),
]
"""
