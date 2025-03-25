"""
用户中心SDK的积分客户端
"""

from typing import Dict, Any, Optional

from ..utils.http import HttpClient
from ..utils.response import ApiResponse


class PointsClient:
    """
    积分客户端，提供积分查询、积分历史等功能
    """

    def __init__(self, http_client: HttpClient):
        """
        初始化积分客户端

        Args:
            http_client: HTTP客户端
        """
        self.http_client = http_client

    def get_points(self) -> ApiResponse:
        """
        获取用户积分

        Returns:
            API响应
        """
        # 发送获取用户积分请求
        return self.http_client.get("points/balance/")

    def get_points_history(
        self,
        page: int = 1,
        page_size: int = 10,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        type_filter: Optional[str] = None,
    ) -> ApiResponse:
        """
        获取积分历史记录

        Args:
            page: 页码
            page_size: 每页数量
            start_date: 开始日期（格式：YYYY-MM-DD）
            end_date: 结束日期（格式：YYYY-MM-DD）
            type_filter: 类型过滤（如：earn, consume, expire）

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
        if type_filter:
            params["type"] = type_filter

        # 发送获取积分历史记录请求
        return self.http_client.get("points/history/", params=params)

    def get_points_rules(self) -> ApiResponse:
        """
        获取积分规则

        Returns:
            API响应
        """
        # 发送获取积分规则请求
        return self.http_client.get("points/rules/")

    def get_points_tasks(self) -> ApiResponse:
        """
        获取积分任务

        Returns:
            API响应
        """
        # 发送获取积分任务请求
        return self.http_client.get("points/tasks/")

    def complete_points_task(self, task_id: str) -> ApiResponse:
        """
        完成积分任务

        Args:
            task_id: 任务ID

        Returns:
            API响应
        """
        # 发送完成积分任务请求
        return self.http_client.post(f"points/tasks/{task_id}/complete/")

    def exchange_points(self, product_id: str, quantity: int = 1) -> ApiResponse:
        """
        兑换积分商品

        Args:
            product_id: 商品ID
            quantity: 数量

        Returns:
            API响应
        """
        # 构建兑换数据
        data = {
            "product_id": product_id,
            "quantity": quantity,
        }

        # 发送兑换积分商品请求
        return self.http_client.post("points/exchange/", data=data)

    def get_exchange_history(
        self,
        page: int = 1,
        page_size: int = 10,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> ApiResponse:
        """
        获取兑换历史记录

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

        # 发送获取兑换历史记录请求
        return self.http_client.get("points/exchange-history/", params=params)

    def get_points_products(
        self,
        page: int = 1,
        page_size: int = 10,
        category: Optional[str] = None,
    ) -> ApiResponse:
        """
        获取积分商品列表

        Args:
            page: 页码
            page_size: 每页数量
            category: 商品类别

        Returns:
            API响应
        """
        # 构建查询参数
        params = {
            "page": page,
            "page_size": page_size,
        }
        if category:
            params["category"] = category

        # 发送获取积分商品列表请求
        return self.http_client.get("points/products/", params=params)

    def get_points_product_detail(self, product_id: str) -> ApiResponse:
        """
        获取积分商品详情

        Args:
            product_id: 商品ID

        Returns:
            API响应
        """
        # 发送获取积分商品详情请求
        return self.http_client.get(f"points/products/{product_id}/")
