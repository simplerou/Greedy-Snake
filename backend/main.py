"""Greedy Snake 后端服务。

提供全局排行榜 API，并托管项目根目录的前端静态页面。

启动（在项目根目录执行）：
    uvicorn backend.main:app --reload

接口文档：
    http://127.0.0.1:8000/docs
"""
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
import base64
import hashlib
import hmac
from pathlib import Path
import re
import secrets
from typing import Literal

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from .database import SessionLocal, init_db
from .models import AuthSession, Score, User

# 项目根目录（backend/ 的上一级），用于托管前端页面
ROOT = Path(__file__).resolve().parent.parent

DIFFICULTIES = {"easy", "medium", "hard"}
MAX_SCORE = 1_000_000
MAX_NAME_LEN = 12  # 与前端 normalizePlayerName 保持一致
SESSION_DAYS = 30
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()  # 启动时建表（需已手动创建数据库）
    yield


app = FastAPI(title="Greedy Snake API", lifespan=lifespan)

# 允许跨域：前端开发和部署可能在不同端口/域名
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


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
    nickname: str = Field(min_length=1, max_length=12)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=128)


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


def create_session(session, user: User) -> str:
    token = secrets.token_urlsafe(32)
    session.add(
        AuthSession(
            user_id=user.id,
            token_hash=token_digest(token),
            expires_at=datetime.utcnow() + timedelta(days=SESSION_DAYS),
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
    if not auth_session or auth_session.expires_at <= datetime.utcnow():
        if auth_session:
            session.delete(auth_session)
            session.commit()
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")

    user = session.get(User, auth_session.user_id)
    if not user:
        raise HTTPException(status_code=401, detail="账号不存在")
    return user, auth_session


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/auth/register", response_model=AuthOut, status_code=201)
def register(payload: RegisterIn) -> AuthOut:
    nickname = payload.nickname.strip()
    if not nickname:
        raise HTTPException(status_code=422, detail="昵称不能为空")
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

        return AuthOut(token=token, user=UserOut(id=user.id, nickname=user.nickname, email=user.email))


@app.post("/api/auth/login", response_model=AuthOut)
def login(payload: LoginIn) -> AuthOut:
    email = normalize_email(payload.email)

    with SessionLocal() as session:
        user = session.scalar(select(User).where(User.email == email))
        if not user or not verify_password(payload.password, user.password_hash):
            raise HTTPException(status_code=401, detail="邮箱或密码不正确")

        session.execute(delete(AuthSession).where(AuthSession.expires_at <= datetime.utcnow()))
        token = create_session(session, user)
        session.commit()
        return AuthOut(token=token, user=UserOut(id=user.id, nickname=user.nickname, email=user.email))


@app.get("/api/auth/me", response_model=UserOut)
def current_user(authorization: str | None = Header(default=None)) -> UserOut:
    with SessionLocal() as session:
        user, _ = get_current_user(session, authorization)
        return UserOut(id=user.id, nickname=user.nickname, email=user.email)


@app.post("/api/auth/logout", status_code=204)
def logout(authorization: str | None = Header(default=None)) -> None:
    with SessionLocal() as session:
        _, auth_session = get_current_user(session, authorization)
        session.delete(auth_session)
        session.commit()


@app.post("/api/scores")
def submit_score(
    payload: ScoreIn,
    authorization: str | None = Header(default=None),
) -> dict:
    """提交一局成绩，返回其在全球同难度中的名次。"""
    with SessionLocal() as session:
        user, _ = get_current_user(session, authorization)
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


app.mount(
    "/web_game",
    StaticFiles(directory=str(ROOT / "web_game"), html=True),
    name="web_game",
)
