"""Outline model — stores structured outline as JSON."""

import uuid
from datetime import datetime, UTC
from sqlalchemy import String, Text, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class Outline(Base):
    __tablename__ = "outlines"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    book_id: Mapped[str] = mapped_column(String(36), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False, default="")  # 大纲标题
    type: Mapped[str] = mapped_column(String(50), nullable=False, default="full")  # 大纲类型
    step_name: Mapped[str | None] = mapped_column(String(50), default=None)  # 生成步骤名
    content: Mapped[str] = mapped_column(Text, nullable=False, default="{}")  # 大纲内容（JSON）
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")  # 状态
    sort_order: Mapped[int] = mapped_column(Integer, default=0)  # 排序序号
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    book: Mapped["Book"] = relationship("Book", back_populates="outlines")
