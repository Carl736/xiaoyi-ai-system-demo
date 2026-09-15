# app/db/init_db.py

from app.db.database import async_engine, Base

from app.model.user import User, UserToken
from app.model.chat_history import ChatHistory
from app.model.document import Document, DocumentChunk


async def init_db():

    async with async_engine.begin() as conn:

        await conn.run_sync(
            Base.metadata.create_all
        )