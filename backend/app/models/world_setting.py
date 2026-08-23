"""WorldSetting model — stores world-building data by category."""

import uuid
from datetime import datetime, UTC
from sqlalchemy import String, Text, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class WorldSetting(Base):
    __tablename__ = "world_settings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    book_id: Mapped[str] = mapped_column(String(36), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False)  # 设定分类
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="")  # 设定名称
    description: Mapped[str | None] = mapped_column(Text, default=None)  # 简介
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")  # 设定内容
    rules: Mapped[str | None] = mapped_column(Text, default=None)  # 规则（JSON）
    parent_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("world_settings.id"), default=None)  # 父级设定 ID
    sort_order: Mapped[int] = mapped_column(Integer, default=0)  # 排序序号
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    book: Mapped["Book"] = relationship("Book", back_populates="world_settings")
