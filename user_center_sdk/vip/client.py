"""
用户中心SDK的VIP客户端
"""

from typing import Dict, Any, Optional

from ..utils.http import HttpClient
from ..utils.response import ApiResponse


class VipClient:
    """
    VIP客户端，提供VIP信息查询、订阅等功能
    """

    def __init__(self, http_client: HttpClient):
        """
        初始化VIP客户端

        Args:
            http_client: HTTP客户端
        """
        self.http_client = http_client

    def get_vip_status(self) -> ApiResponse:
        """
        获取用户VIP状态

        Returns:
            API响应
        """
        # 发送获取用户VIP状态请求
        return self.http_client.get("vip/status/")

    def get_vip_plans(self) -> ApiResponse:
        """
        获取VIP套餐列表

        Returns:
            API响应
        """
        # 发送获取VIP套餐列表请求
        return self.http_client.get("vip/plans/")

    def subscribe_vip(self, plan_id: str, payment_method: str) -> ApiResponse:
        """
        订阅VIP

        Args:
            plan_id: 套餐ID
            payment_method: 支付方式（如：alipay, wechat, credit_card）

        Returns:
            API响应
        """
        # 构建订阅数据
        data = {
            "plan_id": plan_id,
            "payment_method": payment_method,
        }

        # 发送订阅VIP请求
        return self.http_client.post("vip/subscribe/", data=data)

    def cancel_vip(self) -> ApiResponse:
        """
        取消VIP订阅

        Returns:
            API响应
        """
        # 发送取消VIP订阅请求
        return self.http_client.post("vip/cancel/")

    def get_vip_benefits(self) -> ApiResponse:
        """
        获取VIP权益列表

        Returns:
            API响应
        """
        # 发送获取VIP权益列表请求
        return self.http_client.get("vip/benefits/")

    def get_vip_history(
        self,
        page: int = 1,
        page_size: int = 10,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> ApiResponse:
        """
        获取VIP订阅历史记录

        Args:
            page: 页码
            page_size: 每页数量
            start_date: 开始日期（格式：YYYY-MM-DD）
            end_date: 结束日期（格式：YYYY-MM-DD）

        Returns:
            API响应
        """
        # 构建查询参数
        params = {
            "page": page,
            "page_size": page_size,
        }
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date

        # 发送获取VIP订阅历史记录请求
        return self.http_client.get("vip/history/", params=params)

    def get_vip_invoices(
        self,
        page: int = 1,
        page_size: int = 10,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> ApiResponse:
        """
        获取VIP发票列表

        Args:
            page: 页码
            page_size: 每页数量
            start_date: 开始日期（格式：YYYY-MM-DD）
            end_date: 结束日期（格式：YYYY-MM-DD）

        Returns:
            API响应
        """
        # 构建查询参数
        params = {
            "page": page,
            "page_size": page_size,
        }
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date

        # 发送获取VIP发票列表请求
        return self.http_client.get("vip/invoices/", params=params)

    def request_invoice(self, invoice_type: str, invoice_title: str, tax_id: str) -> ApiResponse:
        """
        申请发票

        Args:
            invoice_type: 发票类型（如：personal, company）
            invoice_title: 发票抬头
            tax_id: 税号（企业发票必填）

        Returns:
            API响应
        """
        # 构建申请发票数据
        data = {
            "invoice_type": invoice_type,
            "invoice_title": invoice_title,
            "tax_id": tax_id,
        }

        # 发送申请发票请求
        return self.http_client.post("vip/request-invoice/", data=data)

    def check_vip_privilege(self, privilege_code: str) -> ApiResponse:
        """
        检查VIP特权是否可用

        Args:
            privilege_code: 特权代码

        Returns:
            API响应
        """
        # 发送检查VIP特权请求
        return self.http_client.get(f"vip/check-privilege/{privilege_code}/")

    def use_vip_privilege(self, privilege_code: str) -> ApiResponse:
        """
        使用VIP特权

        Args:
            privilege_code: 特权代码

        Returns:
            API响应
        """
        # 发送使用VIP特权请求
        return self.http_client.post(f"vip/use-privilege/{privilege_code}/")
