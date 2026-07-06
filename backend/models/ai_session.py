"""AI 会话持久化模型 — AiSession + AiSessionMessage

- AiSession: 会话主表，按 session_id 标识
- AiSessionMessage: 消息明细，按 seq 排序
- 复合索引 (session_id, seq) 加速加载
"""
from datetime import datetime

from sqlalchemy import String, Text, DateTime, ForeignKey, Integer, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class AiSession(Base):
    __tablename__ = "ai_sessions"

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    last_active: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)
    title: Mapped[str] = mapped_column(String(255), default="", comment="自定义会话标题")

    messages: Mapped[list["AiSessionMessage"]] = relationship(
        back_populates="session", cascade="all, delete-orphan",
        order_by="AiSessionMessage.seq"
    )


class AiSessionMessage(Base):
    __tablename__ = "ai_session_messages"
    __table_args__ = (
        Index("idx_session_id_seq", "session_id", "seq"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("ai_sessions.session_id", ondelete="CASCADE"))
    seq: Mapped[int] = mapped_column(Integer, nullable=False, comment="消息序号，按序排列")
    role: Mapped[str] = mapped_column(String(16), nullable=False, comment="user / assistant / tool_call / tool_result")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    session: Mapped["AiSession"] = relationship(back_populates="messages")
