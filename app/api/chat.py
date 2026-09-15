from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db

from app.schemas.chat_schema import Question

from app.service.user_service import get_current_user

from app.model.user import User

from app.service import chat_service

router = APIRouter(
    prefix="/api/chat",
    tags=["chat"]
)

@router.post("/ask")
async def ask(
    question: Question,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):

    answer = await chat_service.ask_question(
        question=question.text,
        db=db,
        user_id=user.id,
        document_ids=question.document_ids,
    )

    await chat_service.save_chat(
        db=db,
        user_id=user.id,
        question=question.text,
        answer=answer
    )

    return {
        "question": question.text,
        "answer": answer
    }

@router.get("/history")
async def history(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):

    history = await chat_service.get_chat_history(
        user.id,
        db
    )

    return history