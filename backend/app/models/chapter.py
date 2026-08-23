"""Chapter model — stores generated chapter content."""

import uuid
from datetime import datetime, UTC
from sqlalchemy import String, Text, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class Chapter(Base):
    __tablename__ = "chapters"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    book_id: Mapped[str] = mapped_column(String(36), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False)  # 章节序号
    title: Mapped[str] = mapped_column(String(300), nullable=False, default="")  # 章节标题
    content: Mapped[str | None] = mapped_column(Text, default=None)  # 正文内容
    summary: Mapped[str | None] = mapped_column(Text, default=None)  # 章节摘要
    word_count: Mapped[int] = mapped_column(Integer, default=0)  # 字数
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")  # 状态
    source: Mapped[str] = mapped_column(String(20), default="ai")  # 来源：ai / manual
    has_hook: Mapped[int] = mapped_column(Integer, default=0)  # 是否包含钩子（0/1）
    hook_type: Mapped[str | None] = mapped_column(String(50), default=None)  # 钩子类型
    audit_status: Mapped[str | None] = mapped_column(String(30), default=None)  # 连续性审核状态
    audit_issues: Mapped[str | None] = mapped_column(Text, default=None)  # 审核问题（JSON）
    token_usage: Mapped[str | None] = mapped_column(Text, default=None)  # Token 用量（JSON）
    sort_order: Mapped[int] = mapped_column(Integer, default=0)  # 排序序号
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    book: Mapped["Book"] = relationship("Book", back_populates="chapters")
