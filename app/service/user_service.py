import uuid
from datetime import datetime, timedelta
from starlette import status
from fastapi import HTTPException, Header, Depends
from fastapi.security import HTTPBearer,HTTPAuthorizationCredentials

from sqlalchemy import select, update

from app.db.database import get_db
from app.utils import pwd_security
from sqlalchemy.ext.asyncio import AsyncSession
from app.model.user import User, UserToken
from app.schemas.user_schema import UserRequest, UserInfoResponse, UserAuthResponse, UserUpdateRequest,UserChangePwdRequest

async def get_user_by_username(db:AsyncSession,username:str):
    stmt=select(User).where(User.username==username)
    result=await db.execute(stmt)
    return result.scalar_one_or_none()
async def create_user(db:AsyncSession,user_data:UserRequest):
    #先对密码加密，再去新增用户
    hash_pwd=pwd_security.get_hash_password(user_data.password)
    user=User(
        username=user_data.username,
        password=hash_pwd
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user
async def create_token(db:AsyncSession,user_id:int):
    token=str(uuid.uuid4())
    exprir_at=datetime.now()+timedelta(days=7,hours=2)
    stmt=select(UserToken).where(UserToken.user_id==user_id)
    result=await db.execute(stmt)
    user_token=result.scalar_one_or_none()
    #如果有则更新
    if user_token:
        user_token.token=token
        user_token.expires_at=exprir_at
    #如果没有则创建·
    else:
        user_token=UserToken(
            user_id=user_id,
            token=token,
            expires_at=exprir_at
        )
        db.add(user_token)
    await db.commit()
    return token

async def authenticate_user(db:AsyncSession,username:str,password:str):
    user=await get_user_by_username(db,username)
    if not user:
        return None
    if not pwd_security.verify_password(password,user.password):
        return None
    return user

async def get_user_by_token(db:AsyncSession,token:str):
    stmt=select(UserToken).where(UserToken.token==token)
    result=await db.execute(stmt)
    do_token=result.scalar_one_or_none()

    if not do_token or do_token.expires_at<datetime.now():
        return None
    stmt=select(User).where(User.id==do_token.user_id)
    result=await db.execute(stmt)
    db_user=result.scalar_one_or_none()
    return db_user


security=HTTPBearer()
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
):
    token = credentials.credentials

    if not token:
        raise HTTPException(
            status_code=401,
            detail="Token 为空"
        )

    user = await get_user_by_token(
        db=db,
        token=token
    )

    if not user:
        raise HTTPException(
            status_code=401,
            detail="无效令牌，可能已过期"
        )

    return user
async def update_user(db:AsyncSession,user_data:UserUpdateRequest,user_name:str):
    # user_data是一个pythandantic类型，我把它变成字典**解包出来
    # 没有设置值的不更新
    stmt = update(User).where(User.username == user_name).values(**user_data.model_dump(
        exclude_unset=True,
        exclude_none=True  # 设置值的才会被提取并更新数据库
    ))
    result = await db.execute(stmt)
    await db.commit()
    # 获取更新后的用户
    updated_user = await get_user_by_username(db, user_name)
    return updated_user

async def change_password(db:AsyncSession,password_data:UserChangePwdRequest,user:User):
    #验证旧密码
    if not pwd_security.verify_password(password_data.old_password,user.password):
        return False
    #更新新密码
    new_hash_pwd=pwd_security.get_hash_password(password_data.new_password)
    stmt=update(User).where(User.username==user.username).values(password=new_hash_pwd)
    await db.execute(stmt)
    await db.commit()
    return True