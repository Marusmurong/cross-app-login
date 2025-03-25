"""
用户中心SDK的基本使用示例
"""

from user_center_sdk import UserCenterClient


def main():
    """
    演示用户中心SDK的基本使用
    """
    # 初始化客户端
    client = UserCenterClient(
        api_base_url="http://localhost:5200/api/v1/",
        api_key="usercenter2025",
        auto_refresh_token=True,
    )

    # 用户登录
    login_response = client.auth.login(
        username="test_user",
        password="test_password",
    )

    if login_response.success:
        print(f"登录成功！用户ID: {login_response.data.get('user_id')}")
        print(f"访问令牌: {login_response.data.get('access')[:20]}...")
        print(f"刷新令牌: {login_response.data.get('refresh')[:20]}...")

        # 获取用户资料
        profile_response = client.users.get_profile()
        if profile_response.success:
            print("\n用户资料:")
            print(f"用户名: {profile_response.data.get('username')}")
            print(f"邮箱: {profile_response.data.get('email')}")
            print(f"手机号: {profile_response.data.get('phone')}")
            print(f"昵称: {profile_response.data.get('nickname')}")
        else:
            print(f"获取用户资料失败: {profile_response.message}")

        # 获取用户积分
        points_response = client.points.get_points()
        if points_response.success:
            print(f"\n用户积分: {points_response.data.get('points')}")
            print(f"积分等级: {points_response.data.get('level')}")
        else:
            print(f"获取用户积分失败: {points_response.message}")

        # 获取用户VIP状态
        vip_response = client.vip.get_vip_status()
        if vip_response.success:
            is_vip = vip_response.data.get("is_vip", False)
            print(f"\nVIP状态: {'是' if is_vip else '否'}")
            if is_vip:
                print(f"VIP等级: {vip_response.data.get('level')}")
                print(f"到期时间: {vip_response.data.get('expire_date')}")
        else:
            print(f"获取用户VIP状态失败: {vip_response.message}")

        # 修改密码示例
        # change_password_response = client.users.change_password(
        #     old_password="test_password",
        #     new_password="new_password",
        #     confirm_password="new_password",
        # )
        # if change_password_response.success:
        #     print("\n密码修改成功！")
        # else:
        #     print(f"密码修改失败: {change_password_response.message}")

        # 登出
        logout_response = client.auth.logout()
        if logout_response.success:
            print("\n登出成功！")
        else:
            print(f"登出失败: {logout_response.message}")
    else:
        print(f"登录失败: {login_response.message}")


if __name__ == "__main__":
    main()
