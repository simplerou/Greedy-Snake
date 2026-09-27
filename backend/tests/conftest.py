"""pytest 共享配置。

测试跑在**独立的 MySQL 测试库**（库名必须带 `_test` 后缀）上，与开发库隔离。

必须在导入 backend.* 之前设置 DATABASE_URL——backend/database.py 在模块导入阶段
就会创建 engine，晚一步就来不及了。load_dotenv 默认不覆盖已存在的环境变量，
所以这里先设置就能压过 .env。

两道保险：
1. 库名不以 `_test` 结尾 → 直接拒绝运行（见下方 RuntimeError）。
   测试会逐用例清表，万一 DATABASE_URL 被误配成开发库或线上库，这个检查能拦住清库。
2. 测试库不存在时自动创建，但只创建那个 `_test` 库，不碰其他库。

连接串的账号密码沿用 .env 里配的那份（只把库名换成 _test），
这样仓库里不需要再存一份凭据。用完了可用 TEST_DATABASE_URL 环境变量整体覆盖。
"""
import os
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

# 自己先读一遍 .env，取到应用实际使用的连接串（此时还没导入 backend.*）
from dotenv import load_dotenv  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

_BASE_URL = os.getenv("DATABASE_URL") or (
    "mysql+pymysql://root@localhost:3306/greedy_snake?charset=utf8mb4"
)


def _derive_test_url(base_url: str) -> str:
    """把连接串的库名换成 greedy_snake_test，其余（含账号密码）保持不变。"""
    parts = urlsplit(base_url)
    return urlunsplit((parts.scheme, parts.netloc, "/greedy_snake_test", parts.query, ""))


TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL") or _derive_test_url(_BASE_URL)
TEST_DB_NAME = urlsplit(TEST_DATABASE_URL).path.lstrip("/").split("?")[0]

if not TEST_DB_NAME.endswith("_test"):
    raise RuntimeError(
        f"测试库名必须以 _test 结尾，当前为 {TEST_DB_NAME!r}。\n"
        "测试会逐个用例清空所有表，这条检查是为了防止误清开发库或线上库的数据。\n"
        "确实要用别的库名，请显式设置 TEST_DATABASE_URL 并自行承担风险。"
    )

os.environ["DATABASE_URL"] = TEST_DATABASE_URL

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

from backend.database import SessionLocal, engine, init_db  # noqa: E402
from backend.main import (  # noqa: E402
    app,
    login_limiter,
    register_limiter,
    reset_confirm_limiter,
    reset_request_limiter,
)
from backend.models import Base  # noqa: E402


def _ensure_test_database() -> None:
    """测试库不存在时自动创建。

    create_all 只会建表、不会建库，而 MySQL 必须先有库。
    这里连到服务器本身（连接串去掉库名）执行 CREATE DATABASE IF NOT EXISTS，
    只影响 TEST_DB_NAME 这一个库。
    """
    parts = urlsplit(TEST_DATABASE_URL)
    server_url = f"{parts.scheme}://{parts.netloc}/?charset=utf8mb4"

    server_engine = create_engine(server_url, pool_pre_ping=True)
    try:
        with server_engine.connect() as conn:
            conn.execute(
                text(
                    f"CREATE DATABASE IF NOT EXISTS `{TEST_DB_NAME}` "
                    "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
            )
            conn.commit()
    finally:
        server_engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def _database():
    """整个测试会话共用一个测试库；结束后清空数据。"""
    try:
        _ensure_test_database()
    except Exception as error:  # noqa: BLE001
        pytest.exit(
            "无法准备 MySQL 测试库，测试需要 MySQL 服务运行中。\n"
            f"  测试库: {TEST_DATABASE_URL}\n"
            f"  原始错误: {error}",
            returncode=1,
        )

    init_db()
    yield

    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
    engine.dispose()


@pytest.fixture(autouse=True)
def _clean_tables():
    """每个用例开始前清空所有表，避免用例互相污染。

    按 sorted_tables 的逆序删，先删子表再删父表，否则会撞上外键约束
    （auth_sessions.user_id 有外键指向 users.id）。
    """
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
    yield


@pytest.fixture
def client():
    """带 lifespan 的测试客户端。"""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db_session():
    """直接查库用的会话，用来断言数据库里的真实状态。"""
    with SessionLocal() as session:
        yield session


@pytest.fixture(autouse=True)
def _reset_rate_limiters():
    """每个用例重置限流计数。

    限流器是进程级单例，不重置的话前一个用例的注册/登录会吃掉额度，
    后面用例会莫名其妙收到 429。限流本身另有专门的用例覆盖。
    """
    login_limiter.reset()
    register_limiter.reset()
    reset_request_limiter.reset()
    reset_confirm_limiter.reset()
    yield


@pytest.fixture
def known_reset_code(monkeypatch):
    """把找回密码的验证码固定成已知值。

    默认投递方式是写进服务端日志，测试里没必要去捞日志——
    直接替换生成函数，用例就能拿到确定的验证码。
    """
    code = "246813"
    monkeypatch.setattr("backend.main.generate_reset_code", lambda: code)
    return code


@pytest.fixture
def register(client):
    """注册辅助：默认参数即一个合法账号。"""

    def _register(
        nickname: str = "测试玩家",
        email: str = "player@example.com",
        password: str = "abc12345",
        agreed: bool = True,
        **extra,
    ):
        payload = {
            "nickname": nickname,
            "email": email,
            "password": password,
            "agreed": agreed,
        }
        payload.update(extra)
        return client.post("/api/auth/register", json=payload)

    return _register


@pytest.fixture
def auth_headers(register):
    """注册一个新账号并返回可直接用的 Authorization 头。"""
    response = register()
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}
