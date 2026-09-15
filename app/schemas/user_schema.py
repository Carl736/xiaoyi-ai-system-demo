from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class UserRequest(BaseModel):
    username:str
    password:str


class UserInfoResponse(BaseModel):

    id:int

    username:str

    gender:Optional[str]=None

    bio:Optional[str]=None

    phone:Optional[str]=None

    create_at:datetime

    class Config:
        from_attributes = True


class UserAuthResponse(BaseModel):

    token:str

    user_info:UserInfoResponse


class UserUpdateRequest(BaseModel):

    gender:Optional[str]=None

    bio:Optional[str]=None

    phone:Optional[str]=None


class UserChangePwdRequest(BaseModel):

    old_password:str

    new_password:str