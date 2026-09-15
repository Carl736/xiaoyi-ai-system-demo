import asyncio

from app.db.init_db import init_db


asyncio.run(init_db())