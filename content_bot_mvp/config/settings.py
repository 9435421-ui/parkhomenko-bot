from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    CONTENT_BOT_TOKEN: str
    OPENROUTER_API_KEY: str
    ADMIN_TELEGRAM_ID: int

    DB_PATH: str = "database/content.db"

    # Текст дисклеймера
    DEFAULT_DISCLAIMER: str = "Информация носит ознакомительный характер и не является публичной офертой."

    # Брендинг
    BRAND_NAME: str = "ТОРИОН"
    MAIN_BOT_USERNAME: str = "@torion_bot"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()
