"""
用户中心SDK的Flask集成示例
"""

from flask import Flask, request, jsonify, render_template, redirect, url_for, session, flash
from functools import wraps

from user_center_sdk import UserCenterClient

# 初始化Flask应用
app = Flask(__name__)
app.secret_key = "your-secret-key"  # 用于会话加密

# 初始化用户中心客户端
client = UserCenterClient(
    api_base_url="http://localhost:5200/api/v1/",
    api_key="usercenter2025",
    auto_refresh_token=True,
)


# 登录验证装饰器
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 从会话中获取令牌
        access_token = session.get("access_token")
        refresh_token = session.get("refresh_token")

        if not access_token or not refresh_token:
            # 未登录，重定向到登录页面
            return redirect(url_for("login", next=request.url))

        # 设置令牌
        client.set_tokens(access_token, refresh_token)

        # 检查令牌是否有效
        response = client.auth.check_token()
        if not response.success:
            # 尝试刷新令牌
            refresh_response = client.auth.refresh_token()
            if not refresh_response.success:
                # 刷新失败，清除会话中的令牌并重定向到登录页面
                session.pop("access_token", None)
                session.pop("refresh_token", None)
                flash("会话已过期，请重新登录")
                return redirect(url_for("login", next=request.url))
            else:
                # 刷新成功，更新会话中的令牌
                session["access_token"] = client.http_client.access_token
                session["refresh_token"] = client.http_client.refresh_token

        # 令牌有效，继续执行视图函数
        return f(*args, **kwargs)

    return decorated_function


# VIP验证装饰器
def vip_required(vip_level=None):
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            # 获取用户VIP状态
            response = client.vip.get_vip_status()
            if not response.success:
                flash("获取VIP状态失败，请稍后再试")
                return redirect(url_for("index"))

            # 检查VIP状态
            is_vip = response.data.get("is_vip", False)
            current_level = response.data.get("level", 0)

            # 如果用户不是VIP或等级不满足要求，重定向到VIP升级页面
            if not is_vip or (vip_level is not None and current_level < vip_level):
                flash("此内容需要VIP权限，请升级VIP")
                return redirect(url_for("vip_upgrade"))

            # VIP状态满足要求，继续执行视图函数
            return f(*args, **kwargs)

        return decorated_function

    return decorator


# 路由：首页
@app.route("/")
def index():
    # 检查用户是否已登录
    access_token = session.get("access_token")
    refresh_token = session.get("refresh_token")
    is_logged_in = access_token and refresh_token

    return render_template("index.html", is_logged_in=is_logged_in)


# 路由：登录页面
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        # 获取表单数据
        username = request.form.get("username")
        password = request.form.get("password")

        # 使用用户中心SDK进行登录
        response = client.auth.login(
            username=username,
            password=password,
        )

        if response.success:
            # 登录成功，将令牌保存到会话中
            session["access_token"] = response.data.get("access")
            session["refresh_token"] = response.data.get("refresh")

            # 获取重定向URL
            next_url = request.args.get("next", url_for("index"))
            return redirect(next_url)
        else:
            # 登录失败，显示错误消息
            flash(f"登录失败: {response.message}")

    return render_template("login.html")


# 路由：登出
@app.route("/logout")
def logout():
    # 从会话中获取令牌
    access_token = session.get("access_token")
    refresh_token = session.get("refresh_token")

    if access_token and refresh_token:
        # 设置令牌
        client.set_tokens(access_token, refresh_token)

        # 使用用户中心SDK进行登出
        client.auth.logout()

    # 清除会话中的令牌
    session.pop("access_token", None)
    session.pop("refresh_token", None)

    # 重定向到首页
    return redirect(url_for("index"))


# 路由：用户资料页面
@app.route("/profile")
@login_required
def profile():
    # 获取用户资料
    profile_response = client.users.get_profile()
    if not profile_response.success:
        flash(f"获取用户资料失败: {profile_response.message}")
        return redirect(url_for("index"))

    # 获取用户积分
    points_response = client.points.get_points()
    points_data = points_response.data if points_response.success else {}

    # 获取用户VIP状态
    vip_response = client.vip.get_vip_status()
    vip_data = vip_response.data if vip_response.success else {}

    return render_template(
        "profile.html",
        profile=profile_response.data,
        points=points_data,
        vip=vip_data,
    )


# 路由：修改密码页面
@app.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        # 获取表单数据
        old_password = request.form.get("old_password")
        new_password = request.form.get("new_password")
        confirm_password = request.form.get("confirm_password")

        # 使用用户中心SDK修改密码
        response = client.users.change_password(
            old_password=old_password,
            new_password=new_password,
            confirm_password=confirm_password,
        )

        if response.success:
            # 修改成功，显示成功消息
            flash("密码修改成功")
            return redirect(url_for("profile"))
        else:
            # 修改失败，显示错误消息
            flash(f"密码修改失败: {response.message}")

    return render_template("change_password.html")


# 路由：VIP内容页面
@app.route("/vip/content")
@vip_required()
def vip_content():
    # 获取VIP权益
    benefits_response = client.vip.get_vip_benefits()
    benefits = benefits_response.data if benefits_response.success else {}

    return render_template("vip_content.html", benefits=benefits)


# 路由：高级VIP内容页面
@app.route("/vip/premium")
@vip_required(vip_level=2)
def premium_content():
    return render_template("premium_content.html")


# 路由：VIP升级页面
@app.route("/vip/upgrade")
@login_required
def vip_upgrade():
    # 获取VIP套餐列表
    plans_response = client.vip.get_vip_plans()
    plans = plans_response.data if plans_response.success else {}

    return render_template("vip_upgrade.html", plans=plans)


# 路由：积分商城页面
@app.route("/points/shop")
@login_required
def points_shop():
    # 获取积分商品列表
    products_response = client.points.get_points_products()
    products = products_response.data if products_response.success else {}

    return render_template("points_shop.html", products=products)


# API路由：获取用户资料
@app.route("/api/profile")
@login_required
def api_profile():
    # 获取用户资料
    response = client.users.get_profile()
    return jsonify({
        "success": response.success,
        "message": response.message,
        "data": response.data,
    })


# API路由：获取用户积分
@app.route("/api/points")
@login_required
def api_points():
    # 获取用户积分
    response = client.points.get_points()
    return jsonify({
        "success": response.success,
        "message": response.message,
        "data": response.data,
    })


# API路由：获取用户VIP状态
@app.route("/api/vip/status")
@login_required
def api_vip_status():
    # 获取用户VIP状态
    response = client.vip.get_vip_status()
    return jsonify({
        "success": response.success,
        "message": response.message,
        "data": response.data,
    })


# 启动应用
if __name__ == "__main__":
    # 创建模板目录
    import os
    os.makedirs("templates", exist_ok=True)

    # 创建模板文件
    with open("templates/index.html", "w") as f:
        f.write("""
<!DOCTYPE html>
<html>
<head>
    <title>用户中心SDK示例</title>
</head>
<body>
    <h1>用户中心SDK示例</h1>
    
    {% with messages = get_flashed_messages() %}
        {% if messages %}
            <div class="messages">
                {% for message in messages %}
                    <p>{{ message }}</p>
                {% endfor %}
            </div>
        {% endif %}
    {% endwith %}
    
    {% if is_logged_in %}
        <p>您已登录</p>
        <ul>
            <li><a href="{{ url_for('profile') }}">用户资料</a></li>
            <li><a href="{{ url_for('change_password') }}">修改密码</a></li>
            <li><a href="{{ url_for('vip_content') }}">VIP内容</a></li>
            <li><a href="{{ url_for('premium_content') }}">高级VIP内容</a></li>
            <li><a href="{{ url_for('points_shop') }}">积分商城</a></li>
            <li><a href="{{ url_for('logout') }}">登出</a></li>
        </ul>
    {% else %}
        <p>您尚未登录</p>
        <a href="{{ url_for('login') }}">登录</a>
    {% endif %}
</body>
</html>
        """)

    with open("templates/login.html", "w") as f:
        f.write("""
<!DOCTYPE html>
<html>
<head>
    <title>登录 - 用户中心SDK示例</title>
</head>
<body>
    <h1>登录</h1>
    
    {% with messages = get_flashed_messages() %}
        {% if messages %}
            <div class="messages">
                {% for message in messages %}
                    <p>{{ message }}</p>
                {% endfor %}
            </div>
        {% endif %}
    {% endwith %}
    
    <form method="post">
        <div>
            <label for="username">用户名:</label>
            <input type="text" id="username" name="username" required>
        </div>
        <div>
            <label for="password">密码:</label>
            <input type="password" id="password" name="password" required>
        </div>
        <button type="submit">登录</button>
    </form>
    
    <p><a href="{{ url_for('index') }}">返回首页</a></p>
</body>
</html>
        """)

    # 启动Flask应用
    app.run(debug=True, port=5000)
