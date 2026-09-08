"""Greedy Snake 数据库模型。"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Score(Base):
    __tablename__ = "scores"
    # 排行榜核心查询：按难度取分数最高的前 N 条
    __table_args__ = (Index("ix_scores_difficulty_score", "difficulty", "score"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(32))                  # 玩家昵称
    difficulty: Mapped[str] = mapped_column(String(10))            # easy / medium / hard
    score: Mapped[int] = mapped_column(Integer)                    # 得分
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)   # 存活秒数
    food_eaten: Mapped[int] = mapped_column(Integer, default=0)         # 食物数
    moves: Mapped[int] = mapped_column(Integer, default=0)              # 步数
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )


class User(Base):
    """玩家账号；数据库中只保存密码哈希，不保存明文密码。"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nickname: Mapped[str] = mapped_column(String(12), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AuthSession(Base):
    """登录会话；只保存令牌摘要，数据库泄露时令牌不能被直接使用。"""

    __tablename__ = "auth_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
