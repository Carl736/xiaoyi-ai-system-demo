#接入deepseek大模型

from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    deepseek_api_key: str = "sk-c704919ee64d46cf9269af028b866bb3"   # 直接写在这里

    class Config:
        env_file = ".env"  # 保留，但会被硬编码覆盖

settings = Settings()