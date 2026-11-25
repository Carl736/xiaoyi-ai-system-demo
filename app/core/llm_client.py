from openai import AsyncOpenAI
from app.config import settings
client = AsyncOpenAI(
    api_key=settings.settings.deepseek_api_key,
    base_url="https://api.deepseek.com/v1"
)