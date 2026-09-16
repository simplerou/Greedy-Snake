"""MySQL 数据库连接配置。

默认连接本机 root 无密码的 greedy_snake 库。
如有密码或不同配置，通过环境变量 DATABASE_URL 或项目根目录的 .env 覆盖：

    mysql+pymysql://用户名:密码@主机:端口/数据库名?charset=utf8mb4

在 .env 里填入与线上部署相同的 DATABASE_URL，即可让本地与云端共享同一份榜单。
连接串里的 ssl_ca 路径在本机不存在时（例如部署到 Linux 容器）会自动改用 certifi 自带
的 CA 证书，所以同一条连接串在本地和线上都可用。
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import sessionmaker

# 读取项目根目录的 .env（已设置的环境变量优先），便于本地直接连接云端数据库
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

RAW_DATABASE_URL = os.getenv("DATABASE_URL") or (
    # 环境变量为空字符串时也视为未设置，回落到本地默认库
    "mysql+pymysql://root@localhost:3306/greedy_snake?charset=utf8mb4"
)


def _resolve_ssl_ca(url: URL) -> URL:
    """连接串要求 TLS 但 ssl_ca 指向的文件不存在时，回退到 certifi 的 CA 证书。

    TiDB 等云数据库强制 TLS，而 CA 路径是本机相关的：本地写 Windows 路径、
    Render 容器里只有系统证书，同一条连接串无法两处通用。这里做一次兜底，
    保证线上不会因为一个不存在的路径而连接失败。
    """
    query = url.query
    if not any(key.startswith("ssl") for key in query):
        return url  # 本地 MySQL 未启用 TLS，不做处理
    # 注意 Path("") 等于当前目录，必须先判空，否则"未提供证书"会被误判为路径有效
    ssl_ca = str(query.get("ssl_ca") or "")
    if ssl_ca and Path(ssl_ca).exists():
        return url

    try:
        import certifi
    except ImportError:
        return url

    return url.update_query_dict(
        {
            "ssl_ca": certifi.where(),
            "ssl_verify_cert": "true",
            "ssl_verify_identity": "true",
        }
    )


DATABASE_URL = _resolve_ssl_ca(make_url(RAW_DATABASE_URL)).render_as_string(
    hide_password=False
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
