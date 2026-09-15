from datetime import datetime
from typing import Optional

from sqlalchemy import (
    DateTime,
    String,
    Index,
    Integer,
    ForeignKey,
    func
)

from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class User(Base):

    __tablename__ = 'user'

    __table_args__ = (
        Index("username_UNIQUE", "username"),
        Index("phone_UNIQUE", "phone")
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="用户id"
    )

    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False
    )

    password: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    gender: Mapped[Optional[str]] = mapped_column(
        String(30),
        nullable=True
    )

    bio: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        default="三年之约"
    )

    phone: Mapped[Optional[str]] = mapped_column(
        String(20),
        unique=True,
        nullable=True
    )

    create_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=func.now()
    )

    def __repr__(self):

        return f"<User(id={self.id}, username={self.username})>"


class UserToken(Base):

    __tablename__ = "user_token"

    __table_args__ = (
        Index("token_UNIQUE", "token"),
        Index('fk_user_id_idx', 'user_id')
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user.id"),
        nullable=False
    )

    token: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=func.now()
    )

    def __repr__(self):

        return f"<UserToken(id={self.id}, user_id={self.user_id})>"