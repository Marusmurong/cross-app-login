"""
用户中心SDK的FastAPI集成示例
"""

from fastapi import FastAPI, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any
import jwt
import uvicorn

from user_center_sdk import UserCenterClient

# 初始化FastAPI应用
app = FastAPI(
    title="用户中心SDK FastAPI示例",
    description="展示如何在FastAPI应用中集成用户中心SDK",
    version="1.0.0",
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化用户中心客户端
client = UserCenterClient(
    api_base_url="http://localhost:5200/api/v1/",
    api_key="usercenter2025",
    auto_refresh_token=True,
)

# 初始化安全依赖
security = HTTPBearer()


# 请求模型
class LoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str
    confirm_password: str


class ProfileUpdateRequest(BaseModel):
    nickname: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    avatar: Optional[str] = None


# 响应模型
class StandardResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None


# 用户依赖
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    获取当前用户，验证令牌有效性
    """
    try:
        token = credentials.credentials
        # 设置令牌
        client.http_client.access_token = token
        
        # 检查令牌是否有效
        response = client.auth.check_token()
        if not response.success:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的令牌或令牌已过期",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # 解析令牌获取用户ID
        try:
            payload = jwt.decode(token, options={"verify_signature": False})
            user_id = payload.get("user_id")
            if not user_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="无效的令牌内容",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            return user_id
        except jwt.PyJWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无法解析令牌",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"认证失败: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


# VIP用户依赖
async def get_vip_user(user_id: str = Depends(get_current_user)):
    """
    获取VIP用户，验证用户是否为VIP
    """
    # 获取用户VIP状态
    response = client.vip.get_vip_status()
    if not response.success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取VIP状态失败: {response.message}",
        )
    
    # 检查VIP状态
    is_vip = response.data.get("is_vip", False)
    if not is_vip:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="此操作需要VIP权限",
        )
    
    return user_id


# 高级VIP用户依赖
async def get_premium_user(user_id: str = Depends(get_current_user)):
    """
    获取高级VIP用户，验证用户是否为高级VIP
    """
    # 获取用户VIP状态
    response = client.vip.get_vip_status()
    if not response.success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取VIP状态失败: {response.message}",
        )
    
    # 检查VIP状态
    is_vip = response.data.get("is_vip", False)
    level = response.data.get("level", 0)
    
    if not is_vip or level < 2:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="此操作需要高级VIP权限",
        )
    
    return user_id


# 中间件：刷新令牌
@app.middleware("http")
async def refresh_token_middleware(request: Request, call_next):
    """
    刷新令牌中间件，自动刷新过期的令牌
    """
    response = await call_next(request)
    
    # 检查响应状态码是否为401（未授权）
    if response.status_code == 401:
        # 获取请求头中的授权信息
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            # 提取令牌
            token = auth_header.replace("Bearer ", "")
            
            # 设置令牌
            client.http_client.access_token = token
            
            # 尝试刷新令牌
            refresh_response = client.auth.refresh_token()
            if refresh_response.success:
                # 刷新成功，返回新令牌
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={
                        "success": False,
                        "message": "令牌已过期，已自动刷新",
                        "data": {
                            "access_token": client.http_client.access_token,
                        },
                    },
                )
    
    return response


# 路由：健康检查
@app.get("/health", response_model=StandardResponse)
async def health_check():
    """
    健康检查接口
    """
    return StandardResponse(
        success=True,
        message="服务正常运行",
        data={"status": "ok"},
    )


# 路由：登录
@app.post("/auth/login", response_model=StandardResponse)
async def login(request: LoginRequest):
    """
    用户登录接口
    """
    # 使用用户中心SDK进行登录
    response = client.auth.login(
        username=request.username,
        password=request.password,
    )
    
    if response.success:
        return StandardResponse(
            success=True,
            message="登录成功",
            data={
                "access_token": response.data.get("access"),
                "refresh_token": response.data.get("refresh"),
                "token_type": "bearer",
            },
        )
    else:
        return StandardResponse(
            success=False,
            message=response.message,
            data=None,
        )


# 路由：登出
@app.post("/auth/logout", response_model=StandardResponse)
async def logout(user_id: str = Depends(get_current_user)):
    """
    用户登出接口
    """
    # 使用用户中心SDK进行登出
    response = client.auth.logout()
    
    if response.success:
        return StandardResponse(
            success=True,
            message="登出成功",
            data=None,
        )
    else:
        return StandardResponse(
            success=False,
            message=response.message,
            data=None,
        )


# 路由：刷新令牌
@app.post("/auth/refresh", response_model=StandardResponse)
async def refresh_token(request: Request):
    """
    刷新令牌接口
    """
    # 获取请求头中的授权信息
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少授权信息",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 提取令牌
    token = auth_header.replace("Bearer ", "")
    
    # 设置令牌
    client.http_client.access_token = token
    
    # 使用用户中心SDK刷新令牌
    response = client.auth.refresh_token()
    
    if response.success:
        return StandardResponse(
            success=True,
            message="令牌刷新成功",
            data={
                "access_token": response.data.get("access"),
                "token_type": "bearer",
            },
        )
    else:
        return StandardResponse(
            success=False,
            message=response.message,
            data=None,
        )


# 路由：获取用户资料
@app.get("/users/profile", response_model=StandardResponse)
async def get_profile(user_id: str = Depends(get_current_user)):
    """
    获取用户资料接口
    """
    # 使用用户中心SDK获取用户资料
    response = client.users.get_profile()
    
    if response.success:
        return StandardResponse(
            success=True,
            message="获取用户资料成功",
            data=response.data,
        )
    else:
        return StandardResponse(
            success=False,
            message=response.message,
            data=None,
        )


# 路由：更新用户资料
@app.put("/users/profile", response_model=StandardResponse)
async def update_profile(
    request: ProfileUpdateRequest,
    user_id: str = Depends(get_current_user),
):
    """
    更新用户资料接口
    """
    # 使用用户中心SDK更新用户资料
    response = client.users.update_profile(**request.dict(exclude_none=True))
    
    if response.success:
        return StandardResponse(
            success=True,
            message="更新用户资料成功",
            data=response.data,
        )
    else:
        return StandardResponse(
            success=False,
            message=response.message,
            data=None,
        )


# 路由：修改密码
@app.post("/users/change-password", response_model=StandardResponse)
async def change_password(
    request: ChangePasswordRequest,
    user_id: str = Depends(get_current_user),
):
    """
    修改密码接口
    """
    # 使用用户中心SDK修改密码
    response = client.users.change_password(
        old_password=request.old_password,
        new_password=request.new_password,
        confirm_password=request.confirm_password,
    )
    
    if response.success:
        return StandardResponse(
            success=True,
            message="密码修改成功",
            data=None,
        )
    else:
        return StandardResponse(
            success=False,
            message=response.message,
            data=None,
        )


# 路由：获取用户积分
@app.get("/points", response_model=StandardResponse)
async def get_points(user_id: str = Depends(get_current_user)):
    """
    获取用户积分接口
    """
    # 使用用户中心SDK获取用户积分
    response = client.points.get_points()
    
    if response.success:
        return StandardResponse(
            success=True,
            message="获取用户积分成功",
            data=response.data,
        )
    else:
        return StandardResponse(
            success=False,
            message=response.message,
            data=None,
        )


# 路由：获取积分历史
@app.get("/points/history", response_model=StandardResponse)
async def get_points_history(user_id: str = Depends(get_current_user)):
    """
    获取积分历史接口
    """
    # 使用用户中心SDK获取积分历史
    response = client.points.get_points_history()
    
    if response.success:
        return StandardResponse(
            success=True,
            message="获取积分历史成功",
            data=response.data,
        )
    else:
        return StandardResponse(
            success=False,
            message=response.message,
            data=None,
        )


# 路由：获取积分商品
@app.get("/points/products", response_model=StandardResponse)
async def get_points_products(user_id: str = Depends(get_current_user)):
    """
    获取积分商品接口
    """
    # 使用用户中心SDK获取积分商品
    response = client.points.get_points_products()
    
    if response.success:
        return StandardResponse(
            success=True,
            message="获取积分商品成功",
            data=response.data,
        )
    else:
        return StandardResponse(
            success=False,
            message=response.message,
            data=None,
        )


# 路由：获取VIP状态
@app.get("/vip/status", response_model=StandardResponse)
async def get_vip_status(user_id: str = Depends(get_current_user)):
    """
    获取VIP状态接口
    """
    # 使用用户中心SDK获取VIP状态
    response = client.vip.get_vip_status()
    
    if response.success:
        return StandardResponse(
            success=True,
            message="获取VIP状态成功",
            data=response.data,
        )
    else:
        return StandardResponse(
            success=False,
            message=response.message,
            data=None,
        )


# 路由：获取VIP权益
@app.get("/vip/benefits", response_model=StandardResponse)
async def get_vip_benefits(user_id: str = Depends(get_vip_user)):
    """
    获取VIP权益接口
    """
    # 使用用户中心SDK获取VIP权益
    response = client.vip.get_vip_benefits()
    
    if response.success:
        return StandardResponse(
            success=True,
            message="获取VIP权益成功",
            data=response.data,
        )
    else:
        return StandardResponse(
            success=False,
            message=response.message,
            data=None,
        )


# 路由：获取VIP套餐
@app.get("/vip/plans", response_model=StandardResponse)
async def get_vip_plans(user_id: str = Depends(get_current_user)):
    """
    获取VIP套餐接口
    """
    # 使用用户中心SDK获取VIP套餐
    response = client.vip.get_vip_plans()
    
    if response.success:
        return StandardResponse(
            success=True,
            message="获取VIP套餐成功",
            data=response.data,
        )
    else:
        return StandardResponse(
            success=False,
            message=response.message,
            data=None,
        )


# 路由：高级VIP专属内容
@app.get("/vip/premium", response_model=StandardResponse)
async def get_premium_content(user_id: str = Depends(get_premium_user)):
    """
    获取高级VIP专属内容接口
    """
    return StandardResponse(
        success=True,
        message="获取高级VIP专属内容成功",
        data={
            "content": "这是高级VIP专属内容，只有VIP等级大于等于2的用户才能访问",
            "user_id": user_id,
        },
    )


# 路由：API文档重定向
@app.get("/docs", include_in_schema=False)
async def api_docs_redirect():
    """
    API文档重定向
    """
    return RedirectResponse(url="/docs")


# 启动应用
if __name__ == "__main__":
    uvicorn.run("fastapi_example:app", host="0.0.0.0", port=8000, reload=True)
