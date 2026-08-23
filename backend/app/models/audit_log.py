"""Audit Log model — tracks continuity audit results per chapter."""

import uuid
from datetime import datetime, UTC
from sqlalchemy import String, Integer, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    book_id: Mapped[str] = mapped_column(String(36), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False)  # 章节序号
    dimension: Mapped[str | None] = mapped_column(String(100), default=None)  # 审核维度
    severity: Mapped[str] = mapped_column(String(20), default="warning")  # 严重程度
    description: Mapped[str | None] = mapped_column(Text, default=None)  # 问题描述
    suggestion: Mapped[str | None] = mapped_column(Text, default=None)  # 修改建议
    status: Mapped[str] = mapped_column(String(20), default="open")  # 处理状态
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
