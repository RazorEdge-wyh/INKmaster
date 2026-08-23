"""INKmaster — Unified application configuration."""

import sys
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

if getattr(sys, "frozen", False):
    # PyInstaller 打包后：exe 所在目录
    BASE_DIR = Path(sys.executable).parent
else:
    # 开发环境：backend/app/ 的上两级（项目根目录）
    BASE_DIR = Path(__file__).parent.parent

ROOT_DIR = BASE_DIR
DATA_DIR = BASE_DIR / "data"
BOOKS_DIR = DATA_DIR / "books"

if getattr(sys, "frozen", False):
    STATIC_DIR = Path(sys._MEIPASS) / "app" / "static"
else:
    STATIC_DIR = Path(__file__).parent / "static"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- 数据库 ---
    database_url: str = f"sqlite+aiosqlite:///{DATA_DIR / 'inkmaster.db'}"
    encryption_key: str = ""

    # --- 服务器 ---
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = True
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # --- AI 供应商默认值 ---
    default_provider: str = "deepseek"
    default_model: str = "deepseek-chat"

    # DeepSeek
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"

    # OpenAI
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"

    # Anthropic
    anthropic_api_key: str = ""
    anthropic_base_url: str = "https://api.anthropic.com"

    # --- 写作引擎 ---
    default_target_words: int = 500000
    default_chapter_words: int = 3500
    max_audit_retries: int = 3


settings = Settings()

DATA_DIR.mkdir(parents=True, exist_ok=True)
BOOKS_DIR.mkdir(parents=True, exist_ok=True)
