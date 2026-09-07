"""Greedy Snake 后端服务。

提供全局排行榜 API，并托管项目根目录的前端静态页面。

启动（在项目根目录执行）：
    uvicorn backend.main:app --reload

接口文档：
    http://127.0.0.1:8000/docs
"""
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from .database import SessionLocal, init_db
from .models import Score

# 项目根目录（backend/ 的上一级），用于托管前端页面
ROOT = Path(__file__).resolve().parent.parent

DIFFICULTIES = {"easy", "medium", "hard"}
MAX_SCORE = 1_000_000
MAX_NAME_LEN = 12  # 与前端 normalizePlayerName 保持一致


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


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/scores")
def submit_score(payload: ScoreIn) -> dict:
    """提交一局成绩，返回其在全球同难度中的名次。"""
    name = payload.name.strip()[:MAX_NAME_LEN] or "匿名玩家"

    with SessionLocal() as session:
        session.add(
            Score(
                name=name,
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
