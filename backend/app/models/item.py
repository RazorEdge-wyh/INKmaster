"""Item model — 物品与道具."""

import uuid
from datetime import datetime, UTC
from sqlalchemy import String, Integer, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class Item(Base):
    __tablename__ = "items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    book_id: Mapped[str] = mapped_column(String(36), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)  # 物品名称
    item_type: Mapped[str] = mapped_column(String(50), default="other")  # 物品类型
    acquisition_cost: Mapped[str | None] = mapped_column(Text, default=None)  # 获取代价
    usage_limit: Mapped[str | None] = mapped_column(Text, default=None)  # 使用限制
    hidden_property: Mapped[str | None] = mapped_column(Text, default=None)  # 隐藏属性
    conflict_potential: Mapped[str | None] = mapped_column(Text, default=None)  # 冲突潜力
    description: Mapped[str | None] = mapped_column(Text, default=None)  # 描述
    quantity: Mapped[int] = mapped_column(Integer, default=1)  # 数量
    current_holder: Mapped[str | None] = mapped_column(String(255), default=None)  # 当前持有者
    first_use_chapter: Mapped[int | None] = mapped_column(Integer, default=None)  # 首次使用章节
    usage_count: Mapped[int] = mapped_column(Integer, default=0)  # 使用次数
    sort_order: Mapped[int] = mapped_column(Integer, default=0)  # 排序序号
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
