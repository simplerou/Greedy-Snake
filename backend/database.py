"""数据库连接配置。

默认使用 SQLite——数据库文件落在项目根目录的 greedy_snake.db，
不需要安装或启动任何数据库服务，克隆下来就能直接跑通全部功能。

想改用 MySQL（或线上共享榜单）时，通过环境变量 DATABASE_URL 或项目根目录的 .env 覆盖：

    mysql+pymysql://用户名:密码@主机:端口/数据库名?charset=utf8mb4

在 .env 里填入与线上部署相同的 DATABASE_URL，本地启动 uvicorn 时就会直接读写云端库，
与线上玩家共享同一份全球榜单。连接串里的 ssl_ca 路径在本机不存在时（例如部署到
Linux 容器）会自动改用 certifi 自带的 CA 证书，所以同一条连接串在本地和线上都可用。
"""
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, event
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger("uvicorn.error")

# 项目根目录（backend/ 的上一级）
ROOT = Path(__file__).resolve().parent.parent

# 读取项目根目录的 .env（已设置的环境变量优先）
load_dotenv(ROOT / ".env")

# SQLite 数据库文件路径（默认库）
SQLITE_PATH = ROOT / "greedy_snake.db"

# 环境变量为空字符串时也视为未设置，回落到默认的 SQLite。
# 注意路径用 posix 形式（D:/a/b.db），Windows 反斜杠在连接串里会被转义。
RAW_DATABASE_URL = os.getenv("DATABASE_URL") or f"sqlite:///{SQLITE_PATH.as_posix()}"


def _resolve_ssl_ca(url: URL) -> URL:
    """连接串要求 TLS 但 ssl_ca 指向的文件不存在时，回退到 certifi 的 CA 证书。

    TiDB 等云数据库强制 TLS，而 CA 路径是本机相关的：本地写 Windows 路径、
    Render 容器里只有系统证书，同一条连接串无法两处通用。这里做一次兜底，
    保证线上不会因为一个不存在的路径而连接失败。
    """
    query = url.query
    if not any(key.startswith("ssl") for key in query):
        return url  # 本地 MySQL / SQLite 未启用 TLS，不做处理
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
IS_SQLITE = _RESOLVED_URL.get_backend_name() == "sqlite"

# SQLite 默认只允许创建连接的那个线程使用它，而 FastAPI 的同步接口跑在线程池里，
# 同一个连接可能被换到别的线程执行，会报 "SQLite objects created in a thread..."。
# 这里关掉该检查，由连接池自身保证不会有两个线程同时用一个连接。
_CONNECT_ARGS = {"check_same_thread": False} if IS_SQLITE else {}

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,   # 每次取连接前先 ping，避免 MySQL 8 小时断连
    pool_recycle=3600,    # 连接每小时回收
    connect_args=_CONNECT_ARGS,
)

if IS_SQLITE:

    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
        """SQLite 默认不校验外键，打开它才能让 ondelete=CASCADE 真正生效。"""
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    """建表（已存在则跳过）。

    SQLite 会自动创建数据库文件，无需任何准备；MySQL 需先手动创建数据库：

        CREATE DATABASE greedy_snake CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

    数据库暂时连不上时不抛出异常：让服务照常启动，相关接口由 main.py 的
    异常处理器统一返回 503 提示，而不是整个服务起不来。
    """
    try:
        from .models import Base  # 作为包运行（uvicorn backend.main:app）
    except ImportError:
        from models import Base  # 作为脚本运行（python backend/setup_db.py）

    try:
        Base.metadata.create_all(engine)
    except OperationalError as error:
        logger.warning("数据库初始化失败，账号与排行榜接口将不可用: %s", error)
        return

    if IS_SQLITE:
        logger.info("数据库已就绪（SQLite）: %s", _RESOLVED_URL.database)
    else:
        logger.info(
            "数据库已就绪（%s）: %s:%s/%s",
            engine.dialect.name,
            _RESOLVED_URL.host,
            _RESOLVED_URL.port,
            _RESOLVED_URL.database,
        )
