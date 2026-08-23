"""Truth File model — bridges InkOS truth files to SQL."""

import uuid
from datetime import datetime, UTC
from sqlalchemy import String, Integer, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class TruthFile(Base):
    __tablename__ = "truth_files"
    __table_args__ = (
        UniqueConstraint("book_id", "file_name", "snapshot_of", name="uq_truth_file_snapshot"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    book_id: Mapped[str] = mapped_column(String(36), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    file_name: Mapped[str] = mapped_column(String(100), nullable=False)  # 真相文件名
    content: Mapped[str] = mapped_column(Text, default="")  # 文件内容
    snapshot_of: Mapped[int | None] = mapped_column(Integer, default=None)  # 快照来源版本
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
