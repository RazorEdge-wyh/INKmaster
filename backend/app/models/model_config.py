"""ModelConfig — stores encrypted AI provider credentials."""

import uuid
from sqlalchemy import String, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class ModelConfig(Base):
    __tablename__ = "model_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    provider: Mapped[str] = mapped_column(String(50), nullable=False)  # 供应商：deepseek / openai / anthropic
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)  # 模型名称
    api_base: Mapped[str] = mapped_column(String(300), nullable=True)  # API 地址
    encrypted_api_key: Mapped[str] = mapped_column(String(500), nullable=False, default="")  # 加密后的 API Key
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)  # 是否启用
