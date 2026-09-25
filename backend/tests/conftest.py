"""pytest 共享配置。

必须在导入 backend.* 之前设置 DATABASE_URL——database.py 在模块导入阶段就会读取
它并创建 engine，晚一步就来不及了。这里放在所有 import 的最前面。

load_dotenv 默认不覆盖已存在的环境变量，所以先设置即可压过 .env，
测试永远不会碰到开发用的 greedy_snake.db。
"""
import os
import shutil
import tempfile
from pathlib import Path

_TMP_DIR = Path(tempfile.mkdtemp(prefix="greedy-snake-tests-"))
os.environ["DATABASE_URL"] = f"sqlite:///{(_TMP_DIR / 'test.db').as_posix()}"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend.database import SessionLocal, engine, init_db  # noqa: E402
from backend.main import app, login_limiter, register_limiter  # noqa: E402
from backend.models import Base  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_rate_limiters():
    """每个用例重置限流计数。

    限流器是进程级单例，不重置的话前一个用例的注册/登录会吃掉额度，
    后面用例会莫名其妙收到 429。限流本身另有专门的用例覆盖。
    """
    login_limiter.reset()
    register_limiter.reset()
    yield


@pytest.fixture(scope="session", autouse=True)
def _database():
    """整个测试会话共用一个临时库，结束后连同目录一起删掉。"""
    init_db()
    yield
    engine.dispose()
    shutil.rmtree(_TMP_DIR, ignore_errors=True)


@pytest.fixture(autouse=True)
def _clean_tables():
    """每个用例开始前清空所有表，避免用例互相污染。

    按 sorted_tables 的逆序删，先删子表再删父表，否则会撞上外键约束
    （SQLite 的 PRAGMA foreign_keys 在 database.py 里已被打开）。
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
