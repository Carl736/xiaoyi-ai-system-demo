from pydantic import BaseModel
from typing import Optional
from datetime import datetime

#校验前端传进来的json
#控制后端返回给前端的json

#注册时前端需要传的数据
class UserRequest(BaseModel):
    username:str
    password:str

#返回用户信息时允许暴露的字段
class UserInfoResponse(BaseModel):

    id:int

    username:str

    gender:Optional[str]=None

    bio:Optional[str]=None

    phone:Optional[str]=None

    create_at:datetime

    class Config:
        from_attributes = True


#注册和登陆成功后的完整返回结构
class UserAuthResponse(BaseModel):

    token:str

    user_info:UserInfoResponse


#用户更新个人资料的时候允许修改的字段
class UserUpdateRequest(BaseModel):

    gender:Optional[str]=None

    bio:Optional[str]=None

    phone:Optional[str]=None

#修改密码时需要提供的数据
class UserChangePwdRequest(BaseModel):

    old_password:str

    new_password:str