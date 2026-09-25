"""后端接口测试。

覆盖认证、成绩提交、全球榜单、限流与静态资源托管的主路径和边界。

运行（在项目根目录）：
    pytest                          # 全部
    pytest -v                       # 看每个用例的名字
    pytest -k TestScoreAntiCheat    # 只跑防作弊相关
"""
import math
from datetime import timedelta

import pytest
from sqlalchemy import select

from backend.main import (
    LOGIN_RATE_LIMIT,
    MIN_TICK_MS,
    REGISTER_RATE_LIMIT,
    SCORE_PER_FOOD,
    TIME_TOLERANCE,
    utcnow,
)
from backend.models import AuthSession, Score, User

VALID_REGISTER = {
    "nickname": "测试玩家",
    "email": "player@example.com",
    "password": "abc12345",
    "agreed": True,
}


def score_payload(**overrides) -> dict:
    """构造一份自洽的合法成绩。

    score 由 food_eaten 推导，所以想构造"分数与食物数不匹配"的非法数据，
    直接把 score 放进 overrides 覆盖即可。
    """
    food_eaten = overrides.pop("food_eaten", 8)
    moves = overrides.pop("moves", 60)

    payload = {
        "name": "前端提交的名字",
        "difficulty": "easy",
        "score": food_eaten * SCORE_PER_FOOD,
        "duration_seconds": 600,  # 默认给足时间，让绝大多数用例只被单一规则拦下
        "food_eaten": food_eaten,
        "moves": moves,
    }
    payload.update(overrides)
    return payload


class TestHealth:
    def test_returns_ok(self, client):
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestRegister:
    def test_success_returns_token_and_user(self, client):
        response = client.post("/api/auth/register", json=VALID_REGISTER)
        assert response.status_code == 201, response.text

        body = response.json()
        assert body["token_type"] == "bearer"
        assert len(body["token"]) > 20
        assert body["user"] == {
            "id": 1,
            "nickname": "测试玩家",
            "email": "player@example.com",
        }

    def test_password_is_hashed_not_stored_in_plaintext(self, client, db_session):
        client.post("/api/auth/register", json=VALID_REGISTER)
        user = db_session.scalar(select(User))

        assert user is not None
        assert user.password_hash != VALID_REGISTER["password"]
        assert user.password_hash.startswith("scrypt$")

    def test_email_is_lowercased(self, client):
        response = client.post(
            "/api/auth/register", json={**VALID_REGISTER, "email": "Mixed@Example.COM"}
        )
        assert response.status_code == 201
        assert response.json()["user"]["email"] == "mixed@example.com"

    def test_nickname_is_stripped(self, client):
        response = client.post(
            "/api/auth/register", json={**VALID_REGISTER, "nickname": "  边界玩家  "}
        )
        assert response.status_code == 201
        assert response.json()["user"]["nickname"] == "边界玩家"

    def test_nickname_of_exactly_max_length_is_accepted(self, client):
        # 12 个字正好卡在上限；前后空格必须在长度校验之前被去掉
        response = client.post(
            "/api/auth/register", json={**VALID_REGISTER, "nickname": "  abcdefghijkl  "}
        )
        assert response.status_code == 201, response.text

    def test_nickname_over_max_length_is_rejected(self, client):
        response = client.post(
            "/api/auth/register", json={**VALID_REGISTER, "nickname": "abcdefghijklm"}
        )
        assert response.status_code == 422

    def test_whitespace_only_nickname_is_rejected(self, client):
        response = client.post(
            "/api/auth/register", json={**VALID_REGISTER, "nickname": "    "}
        )
        assert response.status_code == 422
        assert "昵称" in response.json()["detail"]

    def test_whitespace_only_password_is_rejected(self, client):
        response = client.post(
            "/api/auth/register", json={**VALID_REGISTER, "password": " " * 10}
        )
        assert response.status_code == 422
        assert "密码" in response.json()["detail"]

    def test_short_password_is_rejected(self, client):
        response = client.post(
            "/api/auth/register", json={**VALID_REGISTER, "password": "abc123"}
        )
        assert response.status_code == 422

    def test_agreement_is_required(self, client):
        response = client.post(
            "/api/auth/register", json={**VALID_REGISTER, "agreed": False}
        )
        assert response.status_code == 422
        assert "同意" in response.json()["detail"]

    @pytest.mark.parametrize(
        "email", ["not-an-email", "a@b", "@example.com", "a b@example.com", "a@@b.com"]
    )
    def test_invalid_email_is_rejected(self, client, email):
        response = client.post(
            "/api/auth/register", json={**VALID_REGISTER, "email": email}
        )
        assert response.status_code == 422

    def test_duplicate_email_is_rejected(self, client, register):
        assert register().status_code == 201
        response = register(nickname="另一个人")
        assert response.status_code == 409
        assert "邮箱" in response.json()["detail"]

    def test_duplicate_email_is_case_insensitive(self, client, register):
        assert register(email="dup@example.com").status_code == 201
        response = register(nickname="另一个人", email="DUP@Example.com")
        assert response.status_code == 409

    def test_duplicate_nickname_is_rejected(self, client, register):
        assert register().status_code == 201
        response = register(email="other@example.com")
        assert response.status_code == 409
        assert "昵称" in response.json()["detail"]


class TestLogin:
    def test_success(self, client, register):
        register()
        response = client.post(
            "/api/auth/login",
            json={"email": "player@example.com", "password": "abc12345"},
        )
        assert response.status_code == 200
        assert response.json()["user"]["nickname"] == "测试玩家"
        assert response.json()["token"]

    def test_email_is_case_insensitive(self, client, register):
        register()
        response = client.post(
            "/api/auth/login",
            json={"email": "PLAYER@EXAMPLE.COM", "password": "abc12345"},
        )
        assert response.status_code == 200

    def test_wrong_password_is_rejected(self, client, register):
        register()
        response = client.post(
            "/api/auth/login",
            json={"email": "player@example.com", "password": "wrong-password"},
        )
        assert response.status_code == 401

    def test_unknown_email_is_rejected(self, client):
        response = client.post(
            "/api/auth/login",
            json={"email": "nobody@example.com", "password": "abc12345"},
        )
        assert response.status_code == 401

    def test_error_message_does_not_reveal_which_field_is_wrong(self, client, register):
        """两种失败原因的提示必须一致，否则可以用来枚举已注册邮箱。"""
        register()
        wrong_password = client.post(
            "/api/auth/login",
            json={"email": "player@example.com", "password": "wrong-password"},
        )
        unknown_email = client.post(
            "/api/auth/login",
            json={"email": "nobody@example.com", "password": "abc12345"},
        )
        assert wrong_password.json()["detail"] == unknown_email.json()["detail"]


class TestCurrentUserAndLogout:
    def test_me_returns_current_user(self, client, auth_headers):
        response = client.get("/api/auth/me", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["nickname"] == "测试玩家"

    def test_me_without_token_is_rejected(self, client):
        assert client.get("/api/auth/me").status_code == 401

    @pytest.mark.parametrize("header", ["", "Token abc", "Bearer", "Bearer   "])
    def test_malformed_authorization_header_is_rejected(self, client, header):
        response = client.get("/api/auth/me", headers={"Authorization": header})
        assert response.status_code == 401

    def test_logout_invalidates_the_token(self, client, auth_headers):
        assert client.post("/api/auth/logout", headers=auth_headers).status_code == 204
        assert client.get("/api/auth/me", headers=auth_headers).status_code == 401

    def test_logout_without_token_is_rejected(self, client):
        assert client.post("/api/auth/logout").status_code == 401

    def test_expired_token_is_rejected_and_purged(self, client, auth_headers, db_session):
        """过期会话必须失效，并顺手从库里清掉（原来这条路径没有任何覆盖）。"""
        auth_session = db_session.scalar(select(AuthSession))
        assert auth_session is not None

        auth_session.expires_at = utcnow() - timedelta(seconds=1)
        db_session.commit()

        assert client.get("/api/auth/me", headers=auth_headers).status_code == 401

        db_session.expire_all()
        assert db_session.scalar(select(AuthSession)) is None


class TestSubmitScore:
    def test_requires_login(self, client):
        response = client.post("/api/scores", json=score_payload())
        assert response.status_code == 401

    def test_first_score_ranks_first(self, client, auth_headers):
        response = client.post("/api/scores", json=score_payload(), headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == {"ok": True, "rank": 1}

    def test_rank_counts_only_higher_scores(self, client, register):
        first = register(nickname="甲", email="a@example.com")
        second = register(nickname="乙", email="b@example.com")
        headers_a = {"Authorization": f"Bearer {first.json()['token']}"}
        headers_b = {"Authorization": f"Bearer {second.json()['token']}"}

        post = lambda headers, score: client.post(  # noqa: E731
            "/api/scores",
            json=score_payload(food_eaten=score // SCORE_PER_FOOD, moves=score // SCORE_PER_FOOD + 5),
            headers=headers,
        ).json()["rank"]

        assert post(headers_a, 300) == 1
        assert post(headers_b, 100) == 2
        assert post(headers_b, 500) == 1

    def test_rank_is_computed_per_difficulty(self, client, auth_headers):
        client.post(
            "/api/scores",
            json=score_payload(difficulty="hard", food_eaten=50, moves=60),
            headers=auth_headers,
        )
        response = client.post(
            "/api/scores",
            json=score_payload(difficulty="easy", food_eaten=1, moves=5),
            headers=auth_headers,
        )
        assert response.json()["rank"] == 1

    def test_stored_name_comes_from_the_account_not_the_payload(self, client, auth_headers, db_session):
        client.post(
            "/api/scores",
            json=score_payload(name="冒名顶替"),
            headers=auth_headers,
        )
        assert db_session.scalar(select(Score)).name == "测试玩家"

    @pytest.mark.parametrize("difficulty", ["Easy", "nope", ""])
    def test_unknown_difficulty_is_rejected(self, client, auth_headers, difficulty):
        response = client.post(
            "/api/scores",
            json=score_payload(difficulty=difficulty),
            headers=auth_headers,
        )
        assert response.status_code == 422

    @pytest.mark.parametrize("score", [-1, 1_000_001])
    def test_out_of_range_score_is_rejected(self, client, auth_headers, score):
        response = client.post(
            "/api/scores", json=score_payload(score=score), headers=auth_headers
        )
        assert response.status_code == 422


class TestScoreAntiCheat:
    """成绩一致性校验。

    回归用例：修复前，一个刚注册的账号提交 food_eaten=0 / moves=1 /
    score=999999 会直接拿到全球榜第一名。
    """

    def test_demonstrated_exploit_is_rejected(self, client, auth_headers):
        response = client.post(
            "/api/scores",
            json={
                "name": "cheater",
                "difficulty": "easy",
                "score": 999_999,
                "duration_seconds": 5,
                "food_eaten": 0,
                "moves": 1,
            },
            headers=auth_headers,
        )
        assert response.status_code == 422
        # 关键：榜单必须仍然是空的，脏数据不能落库
        assert client.get("/api/leaderboard/easy").json() == []

    def test_score_must_match_food_count(self, client, auth_headers):
        response = client.post(
            "/api/scores",
            json=score_payload(food_eaten=8, moves=60, score=999),
            headers=auth_headers,
        )
        assert response.status_code == 422
        assert "食物" in response.json()["detail"]

    def test_food_count_cannot_exceed_moves(self, client, auth_headers):
        response = client.post(
            "/api/scores",
            json=score_payload(food_eaten=50, moves=10, duration_seconds=600),
            headers=auth_headers,
        )
        assert response.status_code == 422
        assert "步数" in response.json()["detail"]

    def test_too_many_moves_for_elapsed_time_is_rejected(self, client, auth_headers):
        # 1 秒走 999 步；hard 难度光移动至少需要 999 × 45ms ≈ 45 秒
        response = client.post(
            "/api/scores",
            json=score_payload(
                difficulty="hard", food_eaten=1000, moves=1000, duration_seconds=1
            ),
            headers=auth_headers,
        )
        assert response.status_code == 422
        assert "时间" in response.json()["detail"]

    def test_consistent_payload_is_accepted(self, client, auth_headers):
        assert (
            client.post("/api/scores", json=score_payload(), headers=auth_headers).status_code
            == 200
        )

    def test_score_zero_with_no_food_is_accepted(self, client, auth_headers):
        response = client.post(
            "/api/scores",
            json=score_payload(food_eaten=0, moves=0, duration_seconds=1),
            headers=auth_headers,
        )
        assert response.status_code == 200

    def test_exactly_at_the_time_floor_is_accepted(self, client, auth_headers):
        """恰好卡在下限上的成绩必须放行，否则会误伤真实玩家。"""
        moves = 61
        min_ms = (moves - 1) * MIN_TICK_MS["hard"] * TIME_TOLERANCE
        response = client.post(
            "/api/scores",
            json=score_payload(
                difficulty="hard",
                food_eaten=6,
                moves=moves,
                duration_seconds=math.ceil(min_ms / 1000),
            ),
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text

    def test_just_below_the_time_floor_is_rejected(self, client, auth_headers):
        moves = 61
        min_ms = (moves - 1) * MIN_TICK_MS["hard"] * TIME_TOLERANCE
        seconds = int(min_ms // 1000)
        assert seconds * 1000 < min_ms, "用例前提：取整后必须确实低于下限"

        response = client.post(
            "/api/scores",
            json=score_payload(
                difficulty="hard", food_eaten=6, moves=moves, duration_seconds=seconds
            ),
            headers=auth_headers,
        )
        assert response.status_code == 422


class TestLeaderboard:
    def test_empty_by_default(self, client):
        response = client.get("/api/leaderboard/easy")
        assert response.status_code == 200
        assert response.json() == []

    def test_unknown_difficulty_returns_404(self, client):
        assert client.get("/api/leaderboard/impossible").status_code == 404

    def test_sorted_by_score_descending(self, client, auth_headers):
        for eaten in (5, 30, 10):
            client.post(
                "/api/scores",
                json=score_payload(food_eaten=eaten, moves=eaten + 10),
                headers=auth_headers,
            )

        scores = [row["score"] for row in client.get("/api/leaderboard/easy").json()]
        assert scores == [300, 100, 50]

    def test_only_returns_the_requested_difficulty(self, client, auth_headers):
        client.post(
            "/api/scores",
            json=score_payload(difficulty="hard", food_eaten=7, moves=20),
            headers=auth_headers,
        )
        assert client.get("/api/leaderboard/easy").json() == []
        assert len(client.get("/api/leaderboard/hard").json()) == 1

    @pytest.mark.parametrize("limit,expected", [(0, 1), (2, 2), (999, 50)])
    def test_limit_is_clamped_to_1_through_50(self, client, db_session, limit, expected):
        for index in range(55):
            db_session.add(
                Score(
                    name="压测玩家",
                    difficulty="easy",
                    score=index * SCORE_PER_FOOD,
                    duration_seconds=600,
                    food_eaten=index,
                    moves=index + 10,
                )
            )
        db_session.commit()

        rows = client.get(f"/api/leaderboard/easy?limit={limit}").json()
        assert len(rows) == expected


class TestRateLimit:
    def test_login_is_limited_per_ip(self, client):
        payload = {"email": "nobody@example.com", "password": "abc12345"}

        for _ in range(LOGIN_RATE_LIMIT[0]):
            assert client.post("/api/auth/login", json=payload).status_code == 401

        response = client.post("/api/auth/login", json=payload)
        assert response.status_code == 429
        assert "频繁" in response.json()["detail"]

    def test_register_is_limited_per_ip(self, client):
        # 昵称和邮箱都要换，否则第二次就会先撞上昵称重复（409），测不到限流
        for index in range(REGISTER_RATE_LIMIT[0]):
            response = client.post(
                "/api/auth/register",
                json={
                    **VALID_REGISTER,
                    "nickname": f"玩家{index}",
                    "email": f"user{index}@example.com",
                },
            )
            assert response.status_code == 201, response.text

        response = client.post(
            "/api/auth/register",
            json={
                **VALID_REGISTER,
                "nickname": "超限玩家",
                "email": "one-too-many@example.com",
            },
        )
        assert response.status_code == 429

    def test_limiting_login_does_not_affect_other_endpoints(self, client):
        payload = {"email": "nobody@example.com", "password": "abc12345"}
        for _ in range(LOGIN_RATE_LIMIT[0]):
            client.post("/api/auth/login", json=payload)

        assert client.get("/api/health").status_code == 200
        assert client.get("/api/leaderboard/easy").status_code == 200


class TestCors:
    def test_allowed_origin_gets_cors_header(self, client):
        response = client.get("/api/health", headers={"Origin": "http://localhost:8000"})
        assert response.headers.get("access-control-allow-origin") == "http://localhost:8000"

    def test_unknown_origin_gets_no_cors_header(self, client):
        response = client.get("/api/health", headers={"Origin": "https://evil.example.com"})
        assert "access-control-allow-origin" not in response.headers


class TestStaticAssets:
    @pytest.mark.parametrize(
        "path",
        [
            "/",
            "/terms.html",
            "/privacy.html",
            "/README.md",
            "/web_game/page/home.html",
            "/web_game/snake.js",
            "/web_game/style.css",
        ],
    )
    def test_asset_is_served(self, client, path):
        assert client.get(path).status_code == 200

    def test_pages_are_revalidated_on_every_load(self, client):
        assert client.get("/").headers["cache-control"] == "no-cache"

    @pytest.mark.parametrize(
        "path", ["/backend/main.py", "/.env", "/.git/config", "/backend/database.py"]
    )
    def test_backend_internals_are_not_exposed(self, client, path):
        assert client.get(path).status_code == 404
