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
    # 成绩归属的账号。历史数据（本列加入之前提交的）为空，改名时会被认领。
    # 榜单仍按 name 显示，所以这个外键只用于「我的战绩」与改名时的归属迁移，
    # 不参与排行榜查询。
    #
    # 注意：老库由 _add_missing_columns 补列，只会加上可空列、不会带上外键约束，
    # 因此新旧库在这一点上不完全一致；归属正确性由应用层保证。
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
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
    # 注销申请时间。为空表示账号正常；有值表示处于注销冷静期内。
    # 冷静期的判定与清理逻辑见 main.py 的 purge_expired_deletions()。
    deletion_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, index=True
    )


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
    # 登录时的设备信息，只用于「登录设备」页面展示，方便玩家辨认是不是自己的设备。
    # 这两列加入之前创建的会话为空，页面上按「未知设备」显示。
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)  # 兼容 IPv6


class PasswordReset(Base):
    """找回密码用的验证码。

    同样只保存哈希：数据库泄露时验证码不能直接被使用。
    一条记录只用一次（用 used_at 标记），并记录 attempts 用于防爆破——
    申请新验证码时会把该账号此前所有未使用的记录一并作废，
    因此同一时刻最多只有一条有效验证码。
    """

    __tablename__ = "password_resets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    code_hash: Mapped[str] = mapped_column(String(64), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
