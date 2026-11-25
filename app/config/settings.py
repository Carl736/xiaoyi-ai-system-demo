#接入deepseek大模型

from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    deepseek_api_key: str = ""  # 钥匙只从 .env 读，代码里不留

    class Config:
        env_file = ".env"  # .env 的优先级高于代码默认值

settings = Settings()