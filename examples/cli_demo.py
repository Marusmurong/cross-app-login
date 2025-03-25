#!/usr/bin/env python
"""
用户中心SDK命令行演示工具
"""

import argparse
import json
import os
import sys
from getpass import getpass

from user_center_sdk.client import UserCenterClient


class UserCenterCLI:
    """用户中心SDK命令行工具"""

    def __init__(self):
        """初始化命令行工具"""
        self.client = None
        self.token_file = os.path.expanduser("~/.user_center_tokens.json")
        self.api_base_url = os.environ.get(
            "USER_CENTER_API_BASE_URL", "http://localhost:5200/api/v1/"
        )
        self.api_key = os.environ.get("USER_CENTER_API_KEY", "usercenter2025")

    def setup_client(self):
        """设置客户端"""
        self.client = UserCenterClient(
            api_base_url=self.api_base_url,
            api_key=self.api_key,
            auto_refresh_token=True,
        )

        # 尝试从文件加载令牌
        self.load_tokens()

    def load_tokens(self):
        """从文件加载令牌"""
        if os.path.exists(self.token_file):
            try:
                with open(self.token_file, "r") as f:
                    tokens = json.load(f)
                    self.client.set_tokens(
                        tokens.get("access_token"), tokens.get("refresh_token")
                    )
                print("已从文件加载令牌")
            except Exception as e:
                print(f"加载令牌失败: {str(e)}")

    def save_tokens(self):
        """保存令牌到文件"""
        if self.client.http_client.access_token and self.client.http_client.refresh_token:
            try:
                with open(self.token_file, "w") as f:
                    json.dump(
                        {
                            "access_token": self.client.http_client.access_token,
                            "refresh_token": self.client.http_client.refresh_token,
                        },
                        f,
                    )
                print("令牌已保存到文件")
            except Exception as e:
                print(f"保存令牌失败: {str(e)}")

    def check_login(self):
        """检查是否已登录"""
        if not self.client.http_client.access_token:
            print("您尚未登录，请先登录")
            return False

        # 检查令牌是否有效
        response = self.client.auth.check_token()
        if not response.success:
            print("令牌已过期，尝试刷新...")
            refresh_response = self.client.auth.refresh_token()
            if not refresh_response.success:
                print("刷新令牌失败，请重新登录")
                self.client.clear_tokens()
                os.remove(self.token_file)
                return False
            else:
                print("令牌刷新成功")
                self.save_tokens()

        return True

    def login(self, args):
        """登录"""
        username = args.username or input("请输入用户名: ")
        password = args.password or getpass("请输入密码: ")

        response = self.client.auth.login(username=username, password=password)
        if response.success:
            print("登录成功")
            self.save_tokens()
        else:
            print(f"登录失败: {response.message}")

    def logout(self, args):
        """登出"""
        if not self.check_login():
            return

        response = self.client.auth.logout()
        if response.success:
            print("登出成功")
            self.client.clear_tokens()
            if os.path.exists(self.token_file):
                os.remove(self.token_file)
        else:
            print(f"登出失败: {response.message}")

    def get_profile(self, args):
        """获取用户资料"""
        if not self.check_login():
            return

        response = self.client.users.get_profile()
        if response.success:
            print("用户资料:")
            for key, value in response.data.items():
                print(f"  {key}: {value}")
        else:
            print(f"获取用户资料失败: {response.message}")

    def update_profile(self, args):
        """更新用户资料"""
        if not self.check_login():
            return

        profile_data = {}
        if args.nickname:
            profile_data["nickname"] = args.nickname
        if args.email:
            profile_data["email"] = args.email
        if args.phone:
            profile_data["phone"] = args.phone

        if not profile_data:
            print("请提供要更新的资料信息")
            return

        response = self.client.users.update_profile(**profile_data)
        if response.success:
            print("更新用户资料成功")
            for key, value in response.data.items():
                print(f"  {key}: {value}")
        else:
            print(f"更新用户资料失败: {response.message}")

    def change_password(self, args):
        """修改密码"""
        if not self.check_login():
            return

        old_password = args.old_password or getpass("请输入旧密码: ")
        new_password = args.new_password or getpass("请输入新密码: ")
        confirm_password = args.confirm_password or getpass("请确认新密码: ")

        response = self.client.users.change_password(
            old_password=old_password,
            new_password=new_password,
            confirm_password=confirm_password,
        )
        if response.success:
            print("密码修改成功")
        else:
            print(f"密码修改失败: {response.message}")

    def get_points(self, args):
        """获取用户积分"""
        if not self.check_login():
            return

        response = self.client.points.get_points()
        if response.success:
            print("用户积分:")
            for key, value in response.data.items():
                print(f"  {key}: {value}")
        else:
            print(f"获取用户积分失败: {response.message}")

    def get_points_history(self, args):
        """获取积分历史"""
        if not self.check_login():
            return

        response = self.client.points.get_points_history()
        if response.success:
            print("积分历史:")
            for item in response.data.get("items", []):
                print(f"  {item.get('created_at')}: {item.get('points')} 积分 - {item.get('description')}")
        else:
            print(f"获取积分历史失败: {response.message}")

    def get_vip_status(self, args):
        """获取VIP状态"""
        if not self.check_login():
            return

        response = self.client.vip.get_vip_status()
        if response.success:
            print("VIP状态:")
            for key, value in response.data.items():
                print(f"  {key}: {value}")
        else:
            print(f"获取VIP状态失败: {response.message}")

    def get_vip_benefits(self, args):
        """获取VIP权益"""
        if not self.check_login():
            return

        response = self.client.vip.get_vip_benefits()
        if response.success:
            print("VIP权益:")
            for benefit in response.data.get("benefits", []):
                print(f"  {benefit.get('name')}: {benefit.get('description')}")
        else:
            print(f"获取VIP权益失败: {response.message}")

    def get_api_docs(self, args):
        """获取API文档"""
        base_url = self.api_base_url.rstrip("/").replace("/api/v1", "")
        
        print("API文档访问URLs:")
        print(f"  Swagger UI: {base_url}/docs/swagger/?api_key={self.api_key}")
        print(f"  ReDoc: {base_url}/docs/redoc/?api_key={self.api_key}")
        print(f"  Swagger JSON: {base_url}/docs/swagger.json?api_key={self.api_key}")

    def run(self):
        """运行命令行工具"""
        parser = argparse.ArgumentParser(description="用户中心SDK命令行工具")
        subparsers = parser.add_subparsers(dest="command", help="子命令")

        # 登录命令
        login_parser = subparsers.add_parser("login", help="登录")
        login_parser.add_argument("--username", help="用户名")
        login_parser.add_argument("--password", help="密码")

        # 登出命令
        subparsers.add_parser("logout", help="登出")

        # 获取用户资料命令
        subparsers.add_parser("profile", help="获取用户资料")

        # 更新用户资料命令
        update_profile_parser = subparsers.add_parser("update-profile", help="更新用户资料")
        update_profile_parser.add_argument("--nickname", help="昵称")
        update_profile_parser.add_argument("--email", help="邮箱")
        update_profile_parser.add_argument("--phone", help="手机号")

        # 修改密码命令
        change_password_parser = subparsers.add_parser("change-password", help="修改密码")
        change_password_parser.add_argument("--old-password", help="旧密码")
        change_password_parser.add_argument("--new-password", help="新密码")
        change_password_parser.add_argument("--confirm-password", help="确认新密码")

        # 获取用户积分命令
        subparsers.add_parser("points", help="获取用户积分")

        # 获取积分历史命令
        subparsers.add_parser("points-history", help="获取积分历史")

        # 获取VIP状态命令
        subparsers.add_parser("vip-status", help="获取VIP状态")

        # 获取VIP权益命令
        subparsers.add_parser("vip-benefits", help="获取VIP权益")

        # 获取API文档命令
        subparsers.add_parser("api-docs", help="获取API文档访问链接")

        # 解析命令行参数
        args = parser.parse_args()

        # 设置客户端
        self.setup_client()

        # 执行命令
        if args.command == "login":
            self.login(args)
        elif args.command == "logout":
            self.logout(args)
        elif args.command == "profile":
            self.get_profile(args)
        elif args.command == "update-profile":
            self.update_profile(args)
        elif args.command == "change-password":
            self.change_password(args)
        elif args.command == "points":
            self.get_points(args)
        elif args.command == "points-history":
            self.get_points_history(args)
        elif args.command == "vip-status":
            self.get_vip_status(args)
        elif args.command == "vip-benefits":
            self.get_vip_benefits(args)
        elif args.command == "api-docs":
            self.get_api_docs(args)
        else:
            parser.print_help()


if __name__ == "__main__":
    cli = UserCenterCLI()
    cli.run()
