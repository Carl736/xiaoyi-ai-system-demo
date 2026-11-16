#接入deepseek大模型

from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    deepseek_api_key: str = "sk-f9edcb7bec9443298b2cc65f7f700227"   # 直接写在这里

    class Config:
        env_file = ".env"  # 保留，但会被硬编码覆盖

settings = Settings()