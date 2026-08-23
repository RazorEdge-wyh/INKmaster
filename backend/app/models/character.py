"""Character model — enhanced with InkOS dimensions."""

import uuid
from datetime import datetime, UTC
from sqlalchemy import String, Text, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class Character(Base):
    __tablename__ = "characters"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    book_id: Mapped[str] = mapped_column(String(36), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)  # 姓名
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="配角")  # 角色定位（中文）
    role_type: Mapped[str] = mapped_column(String(50), nullable=False, default="supporting")  # 角色类型（英文）
    description: Mapped[str | None] = mapped_column(Text, default=None)  # 简介
    background: Mapped[str | None] = mapped_column(Text, default=None)  # 背景故事
    notes: Mapped[str | None] = mapped_column(Text, default=None)  # 备注
    personality: Mapped[str | None] = mapped_column(Text, default=None)  # 性格
    speech_style: Mapped[str | None] = mapped_column(Text, default=None)  # 语言风格
    motivation: Mapped[str | None] = mapped_column(Text, default=None)  # 动机
    flaws: Mapped[str | None] = mapped_column(Text, default=None)  # 缺陷
    arc: Mapped[str | None] = mapped_column(Text, default=None)  # 成长弧线
    appearance: Mapped[str | None] = mapped_column(Text, default=None)  # 外貌
    abilities: Mapped[str | None] = mapped_column(Text, default=None)  # 能力
    relationships: Mapped[str | None] = mapped_column(Text, default=None)  # 人物关系（JSON）
    current_location: Mapped[str | None] = mapped_column(String(300), default=None)  # 当前位置
    known_info: Mapped[str | None] = mapped_column(Text, default=None)  # 已知信息（JSON）
    state_snapshot: Mapped[str | None] = mapped_column(Text, default=None)  # 状态快照（JSON）
    sort_order: Mapped[int] = mapped_column(Integer, default=0)  # 排序序号
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    book: Mapped["Book"] = relationship("Book", back_populates="characters")
