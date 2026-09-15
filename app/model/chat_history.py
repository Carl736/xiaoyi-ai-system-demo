from datetime import datetime

from sqlalchemy import (
    DateTime,
    Integer,
    ForeignKey,
    Index,
    Text,
    func,
)

from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class ChatHistory(Base):
    __tablename__ = "chat_history"

    __table_args__ = (
        Index("user_id_idx", "user_id"),
    )

    # 聊天记录自己的 ID
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True
    )

    # 哪个用户产生的聊天记录
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user.id"),
        nullable=False
    )

    # 用户的问题
    question: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    # AI 的回答
    answer: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    # 创建时间
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now()
    )