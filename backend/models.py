"""成绩表模型。"""
from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, func
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
