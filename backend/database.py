"""MySQL 数据库连接配置。

默认连接本机 root 无密码的 greedy_snake 库。
如有密码或不同配置，通过环境变量 DATABASE_URL 覆盖：

    mysql+pymysql://用户名:密码@主机:端口/数据库名?charset=utf8mb4
"""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "mysql+pymysql://root@localhost:3306/greedy_snake?charset=utf8mb4",
)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,   # 每次取连接前先 ping，避免 MySQL 8 小时断连
    pool_recycle=3600,    # 连接每小时回收
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    """建表（已存在则跳过）。需要先手动创建数据库：

    CREATE DATABASE greedy_snake CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
    """
    try:
        from .models import Base  # 作为包运行（uvicorn backend.main:app）
    except ImportError:
        from models import Base  # 作为脚本运行（python backend/setup_db.py）

    Base.metadata.create_all(engine)
