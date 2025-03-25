"""
使用用户中心SDK访问API文档的示例
"""

import requests
from user_center_sdk import UserCenterClient


def access_api_docs():
    """
    演示如何使用SDK访问API文档
    """
    # 初始化客户端
    client = UserCenterClient(
        api_base_url="http://localhost:5200/api/v1/",
        api_key="usercenter2025",
    )

    # 构建API文档URL
    base_url = client.config.api_base_url.rstrip("/").replace("/api/v1", "")
    
    # 可用的API文档路径
    doc_paths = {
        "Swagger UI": f"{base_url}/docs/swagger/?api_key={client.config.api_key}",
        "ReDoc": f"{base_url}/docs/redoc/?api_key={client.config.api_key}",
        "Swagger JSON": f"{base_url}/docs/swagger.json?api_key={client.config.api_key}",
    }
    
    print("API文档访问URLs:")
    for name, url in doc_paths.items():
        print(f"{name}: {url}")
    
    # 尝试访问Swagger JSON文档
    try:
        swagger_json_url = doc_paths["Swagger JSON"]
        print(f"\n尝试访问Swagger JSON文档: {swagger_json_url}")
        
        response = requests.get(swagger_json_url)
        if response.status_code == 200:
            swagger_data = response.json()
            
            # 打印API信息
            info = swagger_data.get("info", {})
            print(f"\nAPI信息:")
            print(f"标题: {info.get('title', 'N/A')}")
            print(f"版本: {info.get('version', 'N/A')}")
            print(f"描述: {info.get('description', 'N/A')}")
            
            # 打印可用的API路径
            paths = swagger_data.get("paths", {})
            print(f"\n可用的API路径 ({len(paths)} 个):")
            for path, methods in list(paths.items())[:10]:  # 只显示前10个路径
                print(f"- {path}")
                for method, details in methods.items():
                    print(f"  - {method.upper()}: {details.get('summary', 'N/A')}")
            
            if len(paths) > 10:
                print(f"... 还有 {len(paths) - 10} 个路径未显示")
        else:
            print(f"访问失败，状态码: {response.status_code}")
            print(f"响应内容: {response.text[:200]}...")
    
    except Exception as e:
        print(f"访问API文档时发生错误: {str(e)}")


if __name__ == "__main__":
    access_api_docs()
