from typing import List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.model.chat_history import ChatHistory

async def get_chat_history(
        user_id:int,
        db:AsyncSession,
        limit:int=6,
)->List[ChatHistory]:
    """
    获取用户最近的聊天记录。

    limit 表示最多获取多少条历史消息记录。
    例如：
        limit=6
        表示获取最近 6 次问答。
    """
    stmt=(
        select(ChatHistory)
        .where(ChatHistory.user_id==user_id)
        .order_by(ChatHistory.created_at.desc())
        .limit(limit)
    )

    result=await db.execute(stmt)

    history=result.scalars().all()
    # 数据库是倒序：
    #
    # 最新
    # ↓
    # 第6次
    # 第5次
    # 第4次
    # ...
    #
    # 但 LLM 需要按照真实对话顺序阅读：
    #
    # 第1次
    # 第2次
    # 第3次
    # ...
    # 第6次
    #
    return list(reversed(history))