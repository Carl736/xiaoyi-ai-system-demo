from datetime import datetime

from sqlalchemy import (
    DateTime,
    Integer,
    ForeignKey,

    Text,
    func,
    UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column
from app.db.database import Base

class ChatSummary(Base):
    __tablename__="chat_summary"

    __table_args__=(
        UniqueConstraint(
            "user_id",
            name="uq_user_chat_summary"#保证同一个user_id在chat_summary中最多有一行
        ),
    )

    id:Mapped[int]=mapped_column(
        Integer,
        primary_key=True,
        index=True
    )

    user_id:Mapped[int]=mapped_column(
        Integer,
        ForeignKey("user.id"),
        nullable=False
    )

    covered_through_chat_id:Mapped[int | None]=mapped_column(
        Integer,
        ForeignKey("chat_history.id"),
        nullable=True
    )
    content:Mapped[str]=mapped_column(
        Text,
        nullable=False
    )

    updated_at:Mapped[datetime]=mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now()
    )