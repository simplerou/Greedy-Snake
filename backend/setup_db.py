"""数据库一键初始化脚本。

作用：
1. 测试能否连上 MySQL 服务器
2. 自动创建 greedy_snake 数据库（不存在时）
3. 自动建表（users / auth_sessions / scores）

用法（在项目根目录）：
    python backend/setup_db.py

连接串取自 .env 里的 DATABASE_URL，未配置时回落到本机 MySQL（root@localhost:3306）。
密码不对时可临时用环境变量覆盖：
    PowerShell:  $env:DATABASE_URL = "mysql+pymysql://root:你的密码@localhost:3306/greedy_snake?charset=utf8mb4"
"""
import sys
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import create_engine, text

try:
    from .database import DATABASE_URL
except ImportError:
    from database import DATABASE_URL

MYSQL_HINT = (
    '      $env:DATABASE_URL = '
    '"mysql+pymysql://root:你的密码@localhost:3306/greedy_snake?charset=utf8mb4"'
)


def main() -> None:
    print(f"目标连接串: {mask_password(DATABASE_URL)}")

    setup_mysql()

    print("\n✅ 数据库全部就绪！接下来在项目根目录运行:")
    print("   uvicorn backend.main:app --reload")
    print("   然后打开 http://127.0.0.1:8000/")


def setup_mysql() -> None:
    """连接 MySQL 服务器、建库、建表。"""
    parts = urlsplit(DATABASE_URL)
    server_url = f"{parts.scheme}://{parts.netloc}/?charset=utf8mb4"

    # 1. 连接服务器本身（去掉库名，保留账号），测试账号密码是否正确
    try:
        server = create_engine(server_url, pool_pre_ping=True)
        with server.connect() as conn:
            version = conn.execute(text("SELECT VERSION()")).scalar()
            print(f"[1/3] MySQL 服务器连接成功 (版本 {version})")
    except Exception as error:  # noqa: BLE001
        print("[1/3] 连接 MySQL 服务器失败！")
        print(f"      原因: {error}")
        print("      最常见原因是 root 密码不对。请设置环境变量后重试：")
        print(MYSQL_HINT)
        sys.exit(1)

    # 2. 创建数据库（不存在时）
    db_name = parts.path.lstrip("/") or "greedy_snake"
    try:
        with server.connect() as conn:
            conn.execute(
                text(
                    f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
                    "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
            )
            conn.commit()
        print(f"[2/3] 数据库 `{db_name}` 已就绪 (utf8mb4)")
    except Exception as error:  # noqa: BLE001
        print(f"[2/3] 创建数据库失败: {error}")
        sys.exit(1)
    finally:
        server.dispose()

    # 3. 建表
    create_tables("[3/3]")


def create_tables(label: str) -> None:
    """建表。

    这里直接调用 create_all 而不是复用 init_db()：后者会吞掉连接异常以保证
    Web 服务能照常启动，而初始化脚本需要把真实的失败原因暴露出来。
    """
    try:
        try:
            from .database import engine
            from .models import Base
        except ImportError:
            from database import engine
            from models import Base

        Base.metadata.create_all(engine)
    except Exception as error:  # noqa: BLE001
        print(f"{label} 建表失败: {error}")
        sys.exit(1)

    print(f"{label} 数据表创建完成（users / auth_sessions / scores）")


def mask_password(url: str) -> str:
    """隐藏连接串里的密码，避免打印到控制台。"""
    parts = urlsplit(url)
    if parts.password is None:
        return url

    username = parts.username or ""
    hostname = parts.hostname or ""
    port = f":{parts.port}" if parts.port else ""
    masked_netloc = f"{username}:***@{hostname}{port}"
    return urlunsplit((parts.scheme, masked_netloc, parts.path, parts.query, parts.fragment))


if __name__ == "__main__":
    main()
