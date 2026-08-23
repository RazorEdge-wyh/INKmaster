"""Hook model — tracks foreshadowing / 伏笔."""

import uuid
from datetime import datetime, UTC
from sqlalchemy import String, Integer, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class Hook(Base):
    __tablename__ = "hooks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    book_id: Mapped[str] = mapped_column(String(36), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    hook_id: Mapped[str] = mapped_column(String(100), nullable=False)  # 伏笔标识
    type: Mapped[str | None] = mapped_column(String(50), default=None)  # 伏笔类型
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")  # 伏笔描述
    planted_chapter: Mapped[int | None] = mapped_column(Integer, default=None)  # 埋设章节
    expected_reveal: Mapped[int | None] = mapped_column(Integer, default=None)  # 预期揭示章节
    status: Mapped[str] = mapped_column(String(20), default="pending")  # 状态
    resolution_text: Mapped[str | None] = mapped_column(Text, default=None)  # 回收描述
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
