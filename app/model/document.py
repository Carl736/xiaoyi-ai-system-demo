# app/model/document.py
from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    DateTime, Integer, ForeignKey, String, Text,
    Index, func, Enum as SQLEnum
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.db.database import Base

class DocumentStatus(str,enum.Enum):
    '''文档处理状态'''
    PENDING='pending'#待处理
    PROCESSING='processing'#处理中
    COMPLETED='completed'#已完成
    FAILED='failed'#处理失败
    DELETED='deleted'#已删除(软删除，还存在于数据库中，通过deleted=TRUN筛除不再使用)

class Document(Base):
    """文档主表"""
    __tablename__="document"
    #arg的意思是给表添加索引，索引可以加快查询速度。这里创建了三个索引，分别是根据user_id、status和created_at查询文档的速度会更快。
    __table__args__=(
        Index("idx_document_user_id", "user_id"),#意思是在document表中创建一个索引，索引名为idx_document_user_id，索引的列是user_id，这样可以加快根据user_id查询文档的速度
        Index("idx_document_status", "status"),#意思是在document表中创建一个索引，索引名为idx_document_status，索引的列是status，这样可以加快根据status查询文档的速度
        Index("idx_document_created_at", "created_at"),#意思是在document表中创建一个索引，索引名为idx_document_created_at，索引的列是created_at，这样可以加快根据created_at查询文档的速度
    )
    id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True)#auto_increment=True表示id会自动递增
    user_id:Mapped[int]=mapped_column(Integer,ForeignKey("user_id"),nullable=False)#外键关联用户表的id，表示这个文档属于哪个用户

#id 是数据库内部用的，从 1、2、3 开始，是连号的。如果对外暴露，别人就能猜到你系统里有多少用户、多少文档。
#document_id 是 UUID（比如 a3f4b2c1-...），不可预测，可以安全地暴露给前端。
    #文件信息
    filename:Mapped[str]=mapped_column(String(255),nullable=False)#文件名，String(255)表示最大长度为255个字符
    filepath:Mapped[str]=mapped_column(String(512),nullable=False)#文件路径，String(512)表示最大长度为512个字符
    file_size:Mapped[int]=mapped_column(Integer,nullable=False)#文件大小，单位为字节

    #文件元数据，对外使用uuid
    document_id:Mapped[str]=mapped_column(String(64),unique=True,nullable=False)#文档唯一标识符，String(64)表示最大长度为64个字符，unique=True表示唯一，nullable=False表示不能为空
    status:Mapped[str]=mapped_column(SQLEnum(DocumentStatus),nullable=False,default=DocumentStatus.PENDING)#文档处理状态，使用枚举类型，默认值为PENDING,SQLEnum(DocumentStatus)表示使用DocumentStatus枚举类型，nullable=False表示不能为空

    #统计信息
    total_pages:Mapped[Optional[int]]=mapped_column(Integer,nullable=True)#总页数，Optional[int]表示可以为None，nullable=True表示可以为空
    total_chunks:Mapped[Optional[int]]=mapped_column(Integer,nullable=True)#总chunk数

    #时间戳
    created_at:Mapped[datetime]=mapped_column(DateTime,server_default=func.now())#创建时间，默认值为当前时间
    updated_at:Mapped[datetime]=mapped_column(DateTime,server_default=func.now(),onupdate=func.now())#更新时间，默认值为当前时间，onupdate=func.now()表示每次更新时都会自动更新为当前时间

    #关系:一个文档有多个chunk
    chunks:Mapped[List["DocumentChunk"]]=relationship("DocumentChunk",back_populates="document",cascade="all, delete-orphan")#relationship表示文档和chunk之间的关系,back_populates表示反向关系，cascade="all, delete-orphan"表示当文档被删除时，相关的chunk也会被删除


class DocumentChunk(Base):
    """文档分块表"""
    __tablename__="document_chunk"
    __table__args__=(
        Index("idx_document_chunk_document_id", "document_id"),
        Index("index_chunk_pages", "page")
    )
#数据库自己唯一的id
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)  # auto_increment=True表示id会自动递
    document_id: Mapped[int] = mapped_column(Integer, ForeignKey("document.id"), nullable=False)  #

    # chunk信息
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # 表示当前chunk在当前文档中的第几个
    page: Mapped[int] = mapped_column(Integer, nullable=False)  # 页码
    content: Mapped[str] = mapped_column(Text, nullable=False)  # chunk内容,Text类型可以存储大文本数据
    vector_id: Mapped[Optional[int]] = mapped_column(Integer,nullable=True)  # 向量id，关联向量表的id Optional[int]表示可以为None，nullable=True表示可以为空

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())  # 创建时间，默认值为当前时间

    # 关系:属于那个文档
    document: Mapped["Document"] = relationship("Document", back_populates="chunks")  # relationship表示文档和chunk之间的关系，back_populates表示反向关系，foreign_keys表示外键
