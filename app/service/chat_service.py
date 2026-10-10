from typing import Optional, List

from sqlalchemy.ext.asyncio import AsyncSession

from app.model.chat_history import ChatHistory
from app.service.agent_service import run_agent


async def ask_question(
    question: str,
    db: AsyncSession,
    user_id: int,
    document_ids: Optional[List[str]] = None,
):
    """
    Chat Service

    负责：
    1. 接收用户问题
    2. 调用 Agent
    3. 返回最终答案
    """

    # run_agent 现在返回 dict（含 answer 和执行统计），
    # 这里只取出 answer 对外返回，API 层不用改。
    result = await run_agent(
        question=question,
        user_id=user_id,
        db=db,
        document_ids=document_ids,
    )

    return result["answer"]


async def save_chat(
    db: AsyncSession,
    user_id: int,
    question: str,
    answer: str,
):
    """
    保存聊天记录
    """

    chat = ChatHistory(
        user_id=user_id,
        question=question,
        answer=answer,
    )

    db.add(chat)

    await db.commit()
    await db.refresh(chat)

    return chat