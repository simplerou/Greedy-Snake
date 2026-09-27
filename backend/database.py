"""数据库连接配置。

使用 MySQL。连接串优先取环境变量 DATABASE_URL，其次读项目根目录的 .env：

    mysql+pymysql://用户名:密码@主机:端口/数据库名?charset=utf8mb4

两者都没配置时回落到本机默认值（root@localhost:3306/greedy_snake），
方便不做任何配置的本地开发。

在 .env 里填入与线上部署相同的 DATABASE_URL，本地启动 uvicorn 时就会直接读写云端库，
与线上玩家共享同一份全球榜单。连接串里的 ssl_ca 路径在本机不存在时（例如部署到
Linux 容器）会自动改用 certifi 自带的 CA 证书，所以同一条连接串在本地和线上都可用。
"""
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger("uvicorn.error")

# 项目根目录（backend/ 的上一级）
ROOT = Path(__file__).resolve().parent.parent

# 读取项目根目录的 .env（已设置的环境变量优先）
load_dotenv(ROOT / ".env")

# 未配置 DATABASE_URL 时的回落值：本机 MySQL 的 greedy_snake 库
DEFAULT_DATABASE_URL = "mysql+pymysql://root@localhost:3306/greedy_snake?charset=utf8mb4"

# 环境变量为空字符串时也视为未设置
RAW_DATABASE_URL = os.getenv("DATABASE_URL") or DEFAULT_DATABASE_URL


def _resolve_ssl_ca(url: URL) -> URL:
    """连接串要求 TLS 但 ssl_ca 指向的文件不存在时，回退到 certifi 的 CA 证书。

    TiDB 等云数据库强制 TLS，而 CA 路径是本机相关的：本地写 Windows 路径、
    Render 容器里只有系统证书，同一条连接串无法两处通用。这里做一次兜底，
    保证线上不会因为一个不存在的路径而连接失败。
    """
    query = url.query
    if not any(key.startswith("ssl") for key in query):
        return url  # 未启用 TLS，不做处理
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


_RESOLVED_URL = _resolve_ssl_ca(make_url(RAW_DATABASE_URL))
DATABASE_URL = _RESOLVED_URL.render_as_string(hide_password=False)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,   # 每次取连接前先 ping，避免 MySQL 8 小时断连
    pool_recycle=3600,    # 连接每小时回收
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def _add_missing_columns(base) -> None:
    """给已存在的表补上模型里新增的列（只增不改）。

    create_all 只负责建新表，不会修改已有表的结构——代码升级后模型多了列，
    老库会因为缺列而查询直接报错。这里做一次增量同步：缺哪列补哪列，
    已存在的列一律不动，也绝不删列或改类型。

    只处理可空列：往已有数据的表里加非空列必须提供默认值，那种情况交给人工迁移，
    这里只打日志提醒，不做危险操作。
    """
    inspector = inspect(engine)

    for table in base.metadata.sorted_tables:
        table_name = table.name
        if not inspector.has_table(table_name):
            continue

        existing = {column["name"] for column in inspector.get_columns(table_name)}
        for column in table.columns:
            if column.name in existing:
                continue

            if not column.nullable:
                logger.warning(
                    "表 %s 缺少非空列 %s，需要手动迁移（本次已跳过）", table_name, column.name
                )
                continue

            column_type = column.type.compile(engine.dialect)
            with engine.begin() as conn:
                conn.execute(
                    text(f"ALTER TABLE `{table_name}` ADD COLUMN `{column.name}` {column_type}")
                )
            logger.info("已为表 %s 补上列 %s (%s)", table_name, column.name, column_type)


def init_db() -> None:
    """建表，并给已有表补上模型新增的列。

    需要先在 MySQL 里创建数据库：

        CREATE DATABASE greedy_snake CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

    或者直接跑 `python backend/setup_db.py`，它把连接服务器、建库、建表一次做完。

    数据库暂时连不上时不抛出异常：让服务照常启动，相关接口由 main.py 的
    异常处理器统一返回 503 提示，而不是整个服务起不来。
    """
    try:
        from .models import Base  # 作为包运行（uvicorn backend.main:app）
    except ImportError:
        from models import Base  # 作为脚本运行（python backend/setup_db.py）

    try:
        Base.metadata.create_all(engine)
        _add_missing_columns(Base)
    except OperationalError as error:
        logger.warning("数据库初始化失败，账号与排行榜接口将不可用: %s", error)
        return

    logger.info(
        "数据库已就绪（%s）: %s:%s/%s",
        engine.dialect.name,
        _RESOLVED_URL.host,
        _RESOLVED_URL.port,
        _RESOLVED_URL.database,
    )
