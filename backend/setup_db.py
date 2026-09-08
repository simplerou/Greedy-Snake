"""数据库一键初始化脚本。

作用：
1. 测试能否连上 MySQL 服务器
2. 自动创建 greedy_snake 数据库（不存在时）
3. 自动建表（scores）

用法（在项目根目录）：
    python backend/setup_db.py

如果连接被拒绝，说明密码不对，先设置环境变量再运行：
    PowerShell:  $env:DATABASE_URL = "mysql+pymysql://root:你的密码@localhost:3306/greedy_snake?charset=utf8mb4"
"""
import os
import sys
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import create_engine, text

try:
    from .database import DATABASE_URL
except ImportError:
    from database import DATABASE_URL


def main() -> None:
    print(f"目标连接串: {mask_password(DATABASE_URL)}")

    # 1. 连接服务器本身（去掉库名，保留账号），测试账号密码是否正确
    parts = urlsplit(DATABASE_URL)
    server_url = f"{parts.scheme}://{parts.netloc}/?charset=utf8mb4"

    try:
        server = create_engine(server_url, pool_pre_ping=True)
        with server.connect() as conn:
            version = conn.execute(text("SELECT VERSION()")).scalar()
            print(f"[1/3] MySQL 服务器连接成功 (版本 {version})")
    except Exception as error:  # noqa: BLE001
        print("[1/3] 连接 MySQL 服务器失败！")
        print(f"      原因: {error}")
        print("      最常见原因是 root 密码不对。请设置环境变量后重试：")
        print('      $env:DATABASE_URL = "mysql+pymysql://root:你的密码@localhost:3306/greedy_snake?charset=utf8mb4"')
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

    # 3. 建表
    try:
        try:
            from .database import init_db
        except ImportError:
            from database import init_db

        init_db()
        print("[3/3] 数据表创建完成（scores）")
    except Exception as error:  # noqa: BLE001
        print(f"[3/3] 建表失败: {error}")
        sys.exit(1)

    print("\n✅ 数据库全部就绪！接下来在项目根目录运行:")
    print("   uvicorn backend.main:app --reload")
    print("   然后打开 http://127.0.0.1:8000/")


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
