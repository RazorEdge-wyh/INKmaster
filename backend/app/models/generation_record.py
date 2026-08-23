"""GenerationRecord — audit trail for AI API calls."""

import uuid
from datetime import datetime, UTC
from sqlalchemy import String, Text, Integer, Float, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class GenerationRecord(Base):
    __tablename__ = "generation_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    book_id: Mapped[str] = mapped_column(String(36), ForeignKey("books.id", ondelete="CASCADE"), nullable=False)  # 所属书籍
    step_name: Mapped[str] = mapped_column(String(100), nullable=False)  # 生成步骤名
    provider: Mapped[str] = mapped_column(String(50), nullable=False)  # AI 供应商
    model: Mapped[str] = mapped_column(String(100), nullable=False)  # 模型名称
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)  # 输入 Token 数
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)  # 输出 Token 数
    cost: Mapped[float] = mapped_column(Float, default=0.0)  # 费用
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)  # 耗时（毫秒）
    success: Mapped[bool] = mapped_column(default=True)  # 是否成功
    error_message: Mapped[str] = mapped_column(Text, nullable=True)  # 错误信息
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
