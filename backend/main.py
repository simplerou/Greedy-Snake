"""Greedy Snake 后端服务。

提供全局排行榜 API，并托管项目根目录的前端静态页面。

启动（在项目根目录执行）：
    uvicorn backend.main:app --reload

接口文档：
    http://127.0.0.1:8000/docs
"""
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
import base64
import hashlib
import hmac
import logging
import os
from pathlib import Path
import re
import secrets
import threading
import time
from typing import Literal

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError, OperationalError

from .database import SessionLocal, init_db
from .models import AuthSession, Score, User

logger = logging.getLogger("uvicorn.error")

# 项目根目录（backend/ 的上一级），用于托管前端页面
ROOT = Path(__file__).resolve().parent.parent

DIFFICULTIES = {"easy", "medium", "hard"}
MAX_SCORE = 1_000_000
MAX_NAME_LEN = 12  # 与前端 normalizePlayerName 保持一致
SESSION_DAYS = 30
# 注销冷静期：发起注销后这么多天内重新登录即自动取消；期满仍未登录才清除账号
DELETION_GRACE_DAYS = 15
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1

# ── 成绩校验参数（必须与前端 web_game/snake.js 保持一致）──────────
# 每吃一个食物固定加 10 分，对应前端 `score += 10`，游戏没有其他加分项
SCORE_PER_FOOD = 10
# 各难度蛇的移动间隔下限（毫秒），对应前端 DIFFICULTIES[*].minSpeed。
# 主循环是 setTimeout(gameLoop, speed)，且 speed 只会从 startSpeed 降到 minSpeed，
# 所以走 N 步至少需要 (N-1) * minSpeed 毫秒。
MIN_TICK_MS = {"easy": 120, "medium": 50, "hard": 45}
# 给浏览器定时器抖动留的余量：把时间下限再放宽 10%，避免误伤真实成绩
TIME_TOLERANCE = 0.9

# ── 限流参数：(窗口内允许的请求数, 窗口秒数) ────────────────────
LOGIN_RATE_LIMIT = (10, 60)     # 登录：每 IP 每分钟 10 次
REGISTER_RATE_LIMIT = (5, 300)  # 注册：每 IP 5 分钟 5 次

# ── CORS ─────────────────────────────────────────────────
# 前端由本服务同源托管，正常访问根本不会触发 CORS。
# 这里只放通本地开发常见的来源；需要额外来源时用逗号分隔的
# CORS_ORIGINS 环境变量覆盖，设为空字符串则完全不启用该中间件。
DEFAULT_CORS_ORIGINS = (
    "http://127.0.0.1:8000,http://localhost:8000,"
    "http://127.0.0.1:5173,http://localhost:5173"
)
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", DEFAULT_CORS_ORIGINS).split(",")
    if origin.strip()
]


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()  # 启动时建表（需已手动创建数据库，或先跑 python backend/setup_db.py）

    # 启动时清一次冷静期满期的注销账号；数据库不可用不影响服务启动
    try:
        with SessionLocal() as session:
            purge_expired_deletions(session)
    except OperationalError as error:
        logger.warning("清理到期的注销账号失败: %s", error)

    yield


app = FastAPI(title="Greedy Snake API", lifespan=lifespan)

if CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Authorization"],
    )



@app.middleware("http")
async def revalidate_static_assets(request: Request, call_next):
    """让页面与静态资源每次回源校验。

    浏览器允许缓存但不许跳过校验（配合 etag 命中时只返回 304），
    否则前端改了 JS/CSS 之后，老玩家会继续跑缓存里的旧文件。
    """
    response = await call_next(request)
    path = request.url.path
    if path.startswith("/web_game/") or path in ("/", "/terms.html", "/privacy.html"):
        response.headers["Cache-Control"] = "no-cache"
    return response


@app.exception_handler(OperationalError)
async def database_unavailable(request: Request, exc: OperationalError) -> JSONResponse:
    """数据库连不上或处于只读时给出可读提示。

    否则 FastAPI 会返回 500 纯文本，前端拿不到 detail，只能显示笼统的兜底文案。
    """
    code = exc.orig.args[0] if getattr(exc, "orig", None) and exc.orig.args else None
    if code == 1290:  # ER_OPTION_PREVENTS_STATEMENT，常见于实例欠费锁定或维护中
        detail = "数据库当前处于只读状态，暂时无法写入数据，请稍后再试。"
    else:
        detail = "数据库暂时不可用，请稍后再试。"

    logger.warning("数据库操作失败 (%s): %s", request.url.path, exc.orig)
    return JSONResponse(status_code=503, content={"detail": detail})


class ScoreIn(BaseModel):
    name: str = Field(default="匿名玩家", max_length=32)
    difficulty: Literal["easy", "medium", "hard"]
    score: int = Field(ge=0, le=MAX_SCORE)
    duration_seconds: int = Field(default=0, ge=0)
    food_eaten: int = Field(default=0, ge=0)
    moves: int = Field(default=0, ge=0)


class ScoreOut(BaseModel):
    name: str
    score: int
    created_at: datetime


class RegisterIn(BaseModel):
    # 长度上限在去掉首尾空格之后校验，否则"  合法昵称  "会被误判超长
    nickname: str = Field(max_length=MAX_NAME_LEN)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=128)
    # 是否已同意用户协议与隐私政策；默认 False，由接口给出中文提示
    agreed: bool = False

    @field_validator("nickname", mode="before")
    @classmethod
    def strip_nickname(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=128)


class UserOut(BaseModel):
    id: int
    nickname: str
    email: str


class AuthOut(BaseModel):
    token: str
    token_type: str = "bearer"
    user: UserOut


def normalize_email(value: str) -> str:
    email = value.strip().lower()
    if not EMAIL_PATTERN.fullmatch(email):
        raise HTTPException(status_code=422, detail="邮箱格式不正确")
    return email


def password_digest(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=32,
    )
    encoded_salt = base64.urlsafe_b64encode(salt).decode("ascii")
    encoded_digest = base64.urlsafe_b64encode(digest).decode("ascii")
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${encoded_salt}${encoded_digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, n, r, p, encoded_salt, encoded_digest = stored.split("$", 5)
        if algorithm != "scrypt":
            return False
        salt = base64.urlsafe_b64decode(encoded_salt)
        expected = base64.urlsafe_b64decode(encoded_digest)
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected),
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def utcnow() -> datetime:
    """当前的 UTC 时间（不带时区信息）。

    AuthSession.expires_at 是 naive DateTime 列，所以这里刻意保持 naive，
    只把已废弃的 datetime.utcnow() 换成等价写法，行为完全一致。
    （datetime.utcnow() 自 Python 3.12 起标记废弃，未来版本会移除。）
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


def create_session(session, user: User) -> str:
    token = secrets.token_urlsafe(32)
    session.add(
        AuthSession(
            user_id=user.id,
            token_hash=token_digest(token),
            expires_at=utcnow() + timedelta(days=SESSION_DAYS),
        )
    )
    return token


def get_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="请先登录")
    scheme, separator, token = authorization.partition(" ")
    if not separator or scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="登录凭证格式不正确")
    return token


def get_current_user(session, authorization: str | None) -> tuple[User, AuthSession]:
    token = get_bearer_token(authorization)
    auth_session = session.scalar(
        select(AuthSession).where(AuthSession.token_hash == token_digest(token))
    )
    if not auth_session or auth_session.expires_at <= utcnow():
        if auth_session:
            session.delete(auth_session)
            session.commit()
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")

    user = session.get(User, auth_session.user_id)
    if not user:
        raise HTTPException(status_code=401, detail="账号不存在")
    return user, auth_session


def deletion_deadline(user: User) -> datetime | None:
    """账号处于注销冷静期时返回清除时间，正常账号返回 None。"""
    if user.deletion_requested_at is None:
        return None
    return user.deletion_requested_at + timedelta(days=DELETION_GRACE_DAYS)


def to_user_out(user: User) -> UserOut:
    """账号对外的统一表示形式。

    刻意不暴露 deletion_requested_at：提交注销申请时该账号的所有会话都会失效，
    客户端拿不到有效令牌，也就无从查询这个状态。冷静期的信息只通过
    DELETE /api/auth/account 的返回告诉用户一次即可。
    """
    return UserOut(id=user.id, nickname=user.nickname, email=user.email)


def purge_expired_deletions(session) -> int:
    """清除冷静期已过、期间又没有重新登录的账号，返回清除数量。

    重新登录会直接把 deletion_requested_at 清空（见 login），所以这里筛出来的
    就是真正满期未归的账号。成绩是按昵称存的（scores 表没有指向 users 的外键），
    必须显式删；会话也显式按 user_id 删，不依赖外键级联，行为更明确。
    """
    deadline = utcnow() - timedelta(days=DELETION_GRACE_DAYS)
    expired = session.scalars(
        select(User).where(
            User.deletion_requested_at.is_not(None),
            User.deletion_requested_at <= deadline,
        )
    ).all()

    for user in expired:
        session.execute(delete(Score).where(Score.name == user.nickname))
        session.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
        session.delete(user)

    if expired:
        session.commit()
        logger.info("已清除 %d 个冷静期满期未登录的账号", len(expired))

    return len(expired)


class SlidingWindowLimiter:
    """进程内的滑动窗口限流。

    只适用于单实例部署（本机开发、Render 免费实例都没问题）。
    多实例部署时每个实例各算各的，实际额度会被放大若干倍，
    那种场景需要换成 Redis 之类的外部共享存储。

    用单调时钟（time.monotonic）而不是墙上时钟，避免系统改时间导致窗口错乱。
    """

    def __init__(self, max_requests: int, window_seconds: float) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()
        self._since_sweep = 0

    def allow(self, key: str) -> bool:
        """记录一次请求；窗口内已超上限则返回 False 且不计数。"""
        now = time.monotonic()
        with self._lock:
            self._sweep(now)

            bucket = self._hits[key]
            cutoff = now - self.window_seconds
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()

            if len(bucket) >= self.max_requests:
                return False

            bucket.append(now)
            return True

    def reset(self) -> None:
        """清空全部计数（供测试使用）。"""
        with self._lock:
            self._hits.clear()
            self._since_sweep = 0

    def _sweep(self, now: float) -> None:
        """每隔若干次请求清理一次过期时间桶，防止被大量不同 IP 撑爆内存。"""
        self._since_sweep += 1
        if self._since_sweep < 1000:
            return
        self._since_sweep = 0

        cutoff = now - self.window_seconds
        for key in [k for k, v in self._hits.items() if not v or v[-1] <= cutoff]:
            del self._hits[key]


login_limiter = SlidingWindowLimiter(*LOGIN_RATE_LIMIT)
register_limiter = SlidingWindowLimiter(*REGISTER_RATE_LIMIT)


def enforce_rate_limit(request: Request, limiter: SlidingWindowLimiter, message: str) -> None:
    """按来源 IP 限流，超限抛 429。"""
    client_ip = request.client.host if request.client else "unknown"
    if not limiter.allow(client_ip):
        raise HTTPException(status_code=429, detail=message)


def check_score_consistency(payload: ScoreIn) -> None:
    """校验一局成绩的各字段是否自洽，挡住明显伪造的提交。

    纯前端游戏没法彻底防作弊——有心人改了 snake.js 就能伪造任意数据。
    这里的目标只是让"随手改个数字就能霸榜"不再成立，把作弊成本抬上去。

    三条规则都直接对应前端 web_game/snake.js 的真实行为：
    1. 得分 = 食物数 × 10（前端 `score += 10`，游戏没有其他加分项）
    2. 食物数不会超过移动步数（每次进食都发生在一次移动里）
    3. 移动步数受主循环间隔约束，走 N 步至少需要 (N-1) × 该难度的最小间隔毫秒数
    """
    if payload.score != payload.food_eaten * SCORE_PER_FOOD:
        raise HTTPException(
            status_code=422,
            detail=f"成绩不合法：得分应与食物数匹配（每个食物 {SCORE_PER_FOOD} 分）",
        )

    if payload.food_eaten > payload.moves:
        raise HTTPException(
            status_code=422,
            detail="成绩不合法：吃到的食物数不可能超过移动步数",
        )

    min_ms = (payload.moves - 1) * MIN_TICK_MS[payload.difficulty] * TIME_TOLERANCE
    if payload.duration_seconds * 1000 < min_ms:
        raise HTTPException(
            status_code=422,
            detail="成绩不合法：移动步数与存活时间对不上",
        )


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/auth/register", response_model=AuthOut, status_code=201)
def register(payload: RegisterIn, request: Request) -> AuthOut:
    enforce_rate_limit(request, register_limiter, "注册过于频繁，请稍后再试")

    # 直接调用 API 的请求同样必须带上同意标记，避免绕过前端勾选
    if not payload.agreed:
        raise HTTPException(status_code=422, detail="请先阅读并同意《用户协议》与《隐私政策》")

    nickname = payload.nickname
    if not nickname:
        raise HTTPException(status_code=422, detail="昵称不能为空或全是空格")
    if not payload.password.strip():
        # 空格也算字符，只按长度校验会让整串空格的密码通过
        raise HTTPException(status_code=422, detail="密码不能全是空格")
    email = normalize_email(payload.email)

    with SessionLocal() as session:
        if session.scalar(select(User.id).where(User.email == email)):
            raise HTTPException(status_code=409, detail="该邮箱已注册")
        if session.scalar(select(User.id).where(User.nickname == nickname)):
            raise HTTPException(status_code=409, detail="该昵称已被使用")

        user = User(
            nickname=nickname,
            email=email,
            password_hash=password_digest(payload.password),
        )
        session.add(user)
        try:
            session.flush()
            token = create_session(session, user)
            session.commit()
        except IntegrityError as error:
            session.rollback()
            raise HTTPException(status_code=409, detail="邮箱或昵称已被使用") from error

        return AuthOut(token=token, user=to_user_out(user))


@app.post("/api/auth/login", response_model=AuthOut)
def login(payload: LoginIn, request: Request) -> AuthOut:
    enforce_rate_limit(request, login_limiter, "登录尝试过于频繁，请稍后再试")

    email = normalize_email(payload.email)

    with SessionLocal() as session:
        # 顺手清掉冷静期满期未登录的账号，避免它们继续占着昵称与邮箱
        purge_expired_deletions(session)

        user = session.scalar(select(User).where(User.email == email))
        if not user or not verify_password(payload.password, user.password_hash):
            raise HTTPException(status_code=401, detail="邮箱或密码不正确")

        # 冷静期内重新登录 = 撤销注销申请
        if user.deletion_requested_at is not None:
            logger.info("账号 %s 在冷静期内重新登录，已撤销注销申请", user.nickname)
            user.deletion_requested_at = None

        session.execute(delete(AuthSession).where(AuthSession.expires_at <= utcnow()))
        token = create_session(session, user)
        session.commit()
        return AuthOut(token=token, user=to_user_out(user))


@app.get("/api/auth/me", response_model=UserOut)
def current_user(authorization: str | None = Header(default=None)) -> UserOut:
    with SessionLocal() as session:
        user, _ = get_current_user(session, authorization)
        return to_user_out(user)


@app.post("/api/auth/logout", status_code=204)
def logout(authorization: str | None = Header(default=None)) -> None:
    with SessionLocal() as session:
        _, auth_session = get_current_user(session, authorization)
        session.delete(auth_session)
        session.commit()


@app.delete("/api/auth/account", status_code=202)
def request_account_deletion(authorization: str | None = Header(default=None)) -> dict:
    """发起注销账号。

    只登记申请并进入冷静期，不会立刻删数据——留出反悔的余地。
    冷静期内重新登录即自动撤销；期满仍未登录才会真正清除账号、登录会话与历史成绩
    （清理在服务启动与每次登录时进行）。

    提交后该账号的所有登录会话会立即失效，客户端应清掉本地令牌——
    这样用户下次想继续玩就必须重新登录，也就顺带撤销了注销申请，
    不会出现"用旧会话一直玩、却在冷静期满后被静默清除"的情况。

    重复调用只会刷新申请时间，不报错。
    """
    with SessionLocal() as session:
        user, _ = get_current_user(session, authorization)
        user.deletion_requested_at = utcnow()
        session.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
        session.commit()
        deadline = deletion_deadline(user)

    return {
        "ok": True,
        "grace_days": DELETION_GRACE_DAYS,
        "delete_after": deadline,
    }


@app.post("/api/scores")
def submit_score(
    payload: ScoreIn,
    authorization: str | None = Header(default=None),
) -> dict:
    """提交一局成绩，返回其在全球同难度中的名次。"""
    with SessionLocal() as session:
        user, _ = get_current_user(session, authorization)
        # 先鉴权再校验：未登录直接 401，不给未授权请求探测校验规则的机会
        check_score_consistency(payload)
        session.add(
            Score(
                name=user.nickname,
                difficulty=payload.difficulty,
                score=payload.score,
                duration_seconds=payload.duration_seconds,
                food_eaten=payload.food_eaten,
                moves=payload.moves,
            )
        )
        session.commit()

        better = session.scalar(
            select(func.count())
            .select_from(Score)
            .where(
                Score.difficulty == payload.difficulty,
                Score.score > payload.score,
            )
        )

    return {"ok": True, "rank": (better or 0) + 1}


@app.get("/api/leaderboard/{difficulty}", response_model=list[ScoreOut])
def leaderboard(difficulty: str, limit: int = 10) -> list[Score]:
    """获取指定难度的全球 Top N（默认 10）。"""
    if difficulty not in DIFFICULTIES:
        raise HTTPException(status_code=404, detail="未知难度")

    limit = max(1, min(limit, 50))

    with SessionLocal() as session:
        rows = session.execute(
            select(Score)
            .where(Score.difficulty == difficulty)
            .order_by(Score.score.desc(), Score.created_at.asc())
            .limit(limit)
        ).scalars().all()

    return rows


# ── 前端静态托管（放在所有 API 路由之后）─────────────
# 只挂载需要的文件/目录，避免把整个仓库（含 .git）暴露到公网
from fastapi.responses import FileResponse  # noqa: E402


@app.get("/", include_in_schema=False)
def home() -> FileResponse:
    return FileResponse(ROOT / "index.html", media_type="text/html")


@app.get("/README.md", include_in_schema=False)
def readme() -> FileResponse:
    return FileResponse(ROOT / "README.md", media_type="text/markdown")


@app.get("/terms.html", include_in_schema=False)
def terms() -> FileResponse:
    """用户协议，注册时需勾选同意。"""
    return FileResponse(ROOT / "terms.html", media_type="text/html")


@app.get("/privacy.html", include_in_schema=False)
def privacy() -> FileResponse:
    """隐私政策，注册时需勾选同意。"""
    return FileResponse(ROOT / "privacy.html", media_type="text/html")


app.mount(
    "/web_game",
    StaticFiles(directory=str(ROOT / "web_game"), html=True),
    name="web_game",
)
