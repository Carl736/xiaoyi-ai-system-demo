from datetime import datetime

from sqlalchemy import (
    DateTime,
    Integer,
    ForeignKey,
    Index,
    Text,
    func, UniqueConstraint,
)

from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base

class UserMemory(Base):
    __tablename__="user_memory"

    __table_args__ = (
        Index("user_memory_user_idx", "user_id"),
        UniqueConstraint(
            "user_id",
            "content",
            name="uq_user_memory_user_content",
        ),
    )

    id:Mapped[int] =mapped_column(
        Integer,
        primary_key=True,
        index=True
    )

    user_id:Mapped[int]=mapped_column(
        Integer,
        ForeignKey("user.id"),
        nullable=False
    )

    content:Mapped[str] =mapped_column(
        Text,
        nullable=False
    )

    created_at:Mapped[datetime]=mapped_column(
        DateTime,
        server_default=func.now()
    )