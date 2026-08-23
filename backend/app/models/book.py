"""Book model — top-level project container."""

import uuid
from datetime import datetime, UTC
from sqlalchemy import String, Text, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class Book(Base):
    __tablename__ = "books"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String(200), nullable=False, default="未命名书籍")  # 书名
    concept: Mapped[str] = mapped_column(Text, nullable=False, default="")  # 核心创意
    genre: Mapped[str] = mapped_column(String(100), nullable=False, default="玄幻")  # 题材
    description: Mapped[str | None] = mapped_column(Text, default=None)  # 简介
    author: Mapped[str | None] = mapped_column(String(200), default=None)  # 作者
    tags: Mapped[str | None] = mapped_column(Text, default=None)  # 标签
    cover_image: Mapped[str | None] = mapped_column(String(500), default=None)  # 封面图路径
    total_chapters: Mapped[int] = mapped_column(Integer, default=0)  # 已生成章节数
    total_words: Mapped[int] = mapped_column(Integer, default=0)  # 总字数
    target_words: Mapped[int] = mapped_column(Integer, default=500000)  # 目标字数
    chapter_word_count: Mapped[int] = mapped_column(Integer, default=3500)  # 单章目标字数
    platform: Mapped[str] = mapped_column(String(50), default="other")  # 发布平台
    language: Mapped[str] = mapped_column(String(10), default="zh")  # 语言
    fanfic_mode: Mapped[str | None] = mapped_column(String(20), default=None)  # 同人模式
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")  # 状态
    pipeline_progress: Mapped[int] = mapped_column(default=0)  # 创作流水线进度
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    # 关联关系（删除书籍时级联删除子对象）
    characters: Mapped[list["Character"]] = relationship("Character", back_populates="book", cascade="all, delete-orphan")
    world_settings: Mapped[list["WorldSetting"]] = relationship("WorldSetting", back_populates="book", cascade="all, delete-orphan")
    outlines: Mapped[list["Outline"]] = relationship("Outline", back_populates="book", cascade="all, delete-orphan")
    chapters: Mapped[list["Chapter"]] = relationship("Chapter", back_populates="book", cascade="all, delete-orphan")
