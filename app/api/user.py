from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.schemas.user_schema import UserRequest,UserAuthResponse,UserInfoResponse,UserUpdateRequest,UserChangePwdRequest
from app.service import user_service


from app.model.user import User

router = APIRouter(
    prefix="/api/users",
    tags=["users"]
)
#用户注册：参数（用户名+密码）-》验证参数-》检查用户是否存在（存在报错：用户已存在）-》创建用户-》创建token-》响应结果》
@router.post("/register")
async def register(userdata:UserRequest,db:AsyncSession=Depends(get_db)):
    existing_user=await user_service.get_user_by_username(db,userdata.username)
    if existing_user:
        raise HTTPException(status_code=400, detail="用户名已存在")
    user=await user_service.create_user(db,userdata)
    token=await user_service.create_token(db,user.id)
    response_data=UserAuthResponse(token=token,user_info=UserInfoResponse.model_validate(user))
    return response_data

#用户登录：参数（用户名+密码）-》验证参数-》检查用户是否存在（不存在报错：用户名或密码错误）-》验证密码（错误报错：用户名或密码错误）-》创建token-》响应结果
@router.post("/login")
async def login_user(userdata:UserRequest,db:AsyncSession=Depends(get_db)):
    user=await user_service.authenticate_user(db,userdata.username,userdata.password)
    if not user:
        raise HTTPException(status_code=400,detail="用户名或密码错误")
    token = await user_service.create_token(db, user.id)
    response_data=UserAuthResponse(token=token,user_info=UserInfoResponse.model_validate(user))
    return response_data

#获取用户信息：参数（token）-》验证token（错误报错：无效或过期的token）-》响应结果
@router.get("/info")
async def get_user_info(user:User=Depends(user_service.get_current_user)):
    return UserInfoResponse.model_validate(user)

#更新用户信息：参数（token+用户输入的数据）-》验证token（错误报错：无效或过期的token）-》更新用户信息-》响应结果
@router.put("/update")
async def update_user_info(user_data:UserUpdateRequest,user:User=Depends(user_service.get_current_user),db:AsyncSession=Depends(get_db)):
    user=await user_service.update_user(db,user_data,user.username)
    return UserInfoResponse.model_validate(user)

#修改用户密码：参数（token+旧密码+新密码）-》验证token（错误报错：无效或过期的token）-》验证旧密码（错误报错：旧密码错误）-》更新新密码-》响应结果
@router.put("/password")
async def change_password(password_data:UserChangePwdRequest,user:User=Depends(user_service.get_current_user),db:AsyncSession=Depends(get_db)):
    res_change_pwd=await user_service.change_password(db,password_data,user)
    if not res_change_pwd:
        raise HTTPException(status_code=400,detail="旧密码错误，修改密码失败")
    return {"message":"修改密码成功"}






















