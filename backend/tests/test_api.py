"""后端接口测试。

覆盖认证、成绩提交、全球榜单、限流与静态资源托管的主路径和边界。

运行（在项目根目录）：
    pytest                          # 全部
    pytest -v                       # 看每个用例的名字
    pytest -k TestScoreAntiCheat    # 只跑防作弊相关
"""
import math
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from backend.main import (
    DELETION_GRACE_DAYS,
    LOGIN_RATE_LIMIT,
    MIN_TICK_MS,
    REGISTER_RATE_LIMIT,
    RESET_CODE_LENGTH,
    RESET_MAX_ATTEMPTS,
    RESET_REQUEST_RATE_LIMIT,
    SCORE_PER_FOOD,
    TIME_TOLERANCE,
    generate_reset_code,
    utcnow,
)
from backend.models import AuthSession, PasswordReset, Score, User

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

        user = body["user"]
        assert user["nickname"] == "测试玩家"
        assert user["email"] == "player@example.com"
        # 不断言 id 的具体数值：MySQL 的 AUTO_INCREMENT 不会因为清表而重置
        assert isinstance(user["id"], int) and user["id"] > 0

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

    def test_failure_message_says_account_not_email(self, client, register):
        """失败提示统一用「账号或密码不正确」。

        刻意不写「邮箱」：用户记住的是自己的账号，未必记得注册时填的是哪个
        邮箱地址，提示里出现「邮箱」反而容易让人以为输错了字段。
        """
        register()
        response = client.post(
            "/api/auth/login",
            json={"email": "player@example.com", "password": "wrong-password"},
        )
        assert response.json()["detail"] == "账号或密码不正确"


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


class TestAccountDeletion:
    """注销是「登记 + 15 天冷静期」，不是立即删除。

    设计要点：提交申请后该账号的所有登录会话立即失效（用户被登出），
    所以下次想继续玩必须重新登录 —— 而重新登录就等于撤销注销申请。
    这样就避免了「用旧会话一直玩、却在冷静期满后被静默清除」的情况。
    """

    def test_requires_login(self, client):
        assert client.delete("/api/auth/account").status_code == 401

    def test_request_returns_grace_deadline(self, client, auth_headers):
        response = client.delete("/api/auth/account", headers=auth_headers)
        assert response.status_code == 202

        body = response.json()
        assert body["ok"] is True
        assert body["grace_days"] == DELETION_GRACE_DAYS

        deadline = datetime.fromisoformat(body["delete_after"])
        expected = utcnow() + timedelta(days=DELETION_GRACE_DAYS)
        assert abs((deadline - expected).total_seconds()) < 120

    def test_request_invalidates_every_session(self, client, auth_headers):
        assert client.delete("/api/auth/account", headers=auth_headers).status_code == 202
        # 原令牌必须立刻失效，否则用户可以继续用旧会话游玩
        assert client.get("/api/auth/me", headers=auth_headers).status_code == 401

    def test_data_survives_during_grace_period(self, client, auth_headers, db_session):
        client.delete("/api/auth/account", headers=auth_headers)

        db_session.expire_all()
        user = db_session.scalar(select(User))
        assert user is not None, "冷静期内账号不该被删除"
        assert user.deletion_requested_at is not None

    def test_login_within_grace_period_cancels_deletion(self, client, auth_headers, db_session):
        client.delete("/api/auth/account", headers=auth_headers)

        response = client.post(
            "/api/auth/login",
            json={"email": "player@example.com", "password": "abc12345"},
        )
        assert response.status_code == 200

        db_session.expire_all()
        assert db_session.scalar(select(User)).deletion_requested_at is None

    def test_scores_are_kept_when_deletion_is_cancelled(self, client, auth_headers):
        client.post("/api/scores", json=score_payload(), headers=auth_headers)
        client.delete("/api/auth/account", headers=auth_headers)
        client.post(
            "/api/auth/login",
            json={"email": "player@example.com", "password": "abc12345"},
        )

        assert len(client.get("/api/leaderboard/easy").json()) == 1

    def test_can_request_again_after_re_login(self, client, auth_headers):
        assert client.delete("/api/auth/account", headers=auth_headers).status_code == 202

        login = client.post(
            "/api/auth/login",
            json={"email": "player@example.com", "password": "abc12345"},
        )
        new_headers = {"Authorization": f"Bearer {login.json()['token']}"}

        assert client.delete("/api/auth/account", headers=new_headers).status_code == 202

    def _expire_grace_period(self, db_session):
        """把注销申请时间往前拨到冷静期之外，模拟 15 天没登录。"""
        db_session.expire_all()
        user = db_session.scalar(select(User))
        user.deletion_requested_at = utcnow() - timedelta(days=DELETION_GRACE_DAYS + 1)
        db_session.commit()

    def test_expired_grace_period_purges_account_scores_and_sessions(
        self, client, auth_headers, db_session
    ):
        """期满后账号、成绩、会话一并清除——这正是隐私政策承诺的内容。"""
        client.post("/api/scores", json=score_payload(), headers=auth_headers)
        client.delete("/api/auth/account", headers=auth_headers)
        self._expire_grace_period(db_session)

        # 登录时会顺手清理到期的注销账号
        client.post(
            "/api/auth/login",
            json={"email": "player@example.com", "password": "abc12345"},
        )

        db_session.expire_all()
        assert db_session.scalar(select(User)) is None
        assert db_session.scalars(select(Score)).all() == []
        assert db_session.scalars(select(AuthSession)).all() == []
        assert client.get("/api/leaderboard/easy").json() == []

    def test_nickname_and_email_are_freed_after_purge(self, client, register, db_session):
        """注销期满后，昵称与邮箱应该能被重新注册。"""
        created = register()
        headers = {"Authorization": f"Bearer {created.json()['token']}"}

        client.delete("/api/auth/account", headers=headers)
        self._expire_grace_period(db_session)
        client.post(
            "/api/auth/login",
            json={"email": "player@example.com", "password": "abc12345"},
        )

        # 同昵称同邮箱重新注册应当成功
        assert register().status_code == 201

    def test_account_still_playable_between_request_and_expiry_of_session(
        self, client, auth_headers
    ):
        """注销申请不会让仍在有效期的令牌变成"能登录但不能用"的怪状态。

        提交后令牌即失效，因此这里的预期是 401 —— 明确记录这个行为，
        免得以后有人改了会话逻辑却不知道这里依赖它。
        """
        client.delete("/api/auth/account", headers=auth_headers)
        assert client.get("/api/auth/me", headers=auth_headers).status_code == 401
        assert (
            client.post("/api/scores", json=score_payload(), headers=auth_headers).status_code
            == 401
        )


class TestResetCodeGeneration:
    def test_code_is_all_digits_with_expected_length(self):
        for _ in range(20):
            code = generate_reset_code()
            assert len(code) == RESET_CODE_LENGTH
            assert code.isdigit()

    def test_codes_vary(self):
        assert len({generate_reset_code() for _ in range(50)}) > 1


class TestPasswordReset:
    """找回密码：邮箱拿验证码 -> 用验证码设置新密码。

    验证码默认写进服务端日志，用例通过 known_reset_code 固定成已知值，
    不必去捞日志。
    """

    EMAIL = "player@example.com"
    OLD_PASSWORD = "abc12345"
    NEW_PASSWORD = "newpass123"

    def _request(self, client, email=EMAIL):
        return client.post("/api/auth/password-reset/request", json={"email": email})

    def _confirm(self, client, code, password=NEW_PASSWORD, email=EMAIL):
        return client.post(
            "/api/auth/password-reset/confirm",
            json={"email": email, "code": code, "new_password": password},
        )

    def _login(self, client, password, email=EMAIL):
        return client.post("/api/auth/login", json={"email": email, "password": password})

    def test_request_does_not_reveal_whether_email_exists(
        self, client, register, known_reset_code
    ):
        register()  # 已注册

        known = self._request(client, self.EMAIL)
        unknown = self._request(client, "nobody@example.com")
        malformed = self._request(client, "not-an-email")

        assert known.status_code == unknown.status_code == malformed.status_code == 202
        # 三者响应必须完全一致，否则可以用来枚举邮箱。
        # 返回体验证码的开发模式下这一点尤其要紧：如果只有已注册的邮箱才带 code，
        # 「有没有 code」就等于「邮箱是否注册」。所以未注册时后端会返回一个
        # 不落库的假验证码，结构完全一致（验证码固定后可直接比对整个响应体）。
        assert known.json() == unknown.json() == malformed.json()
        assert known.json()["code"] == known_reset_code

    def test_unknown_email_creates_no_code(self, client, db_session):
        self._request(client, "nobody@example.com")
        assert db_session.scalars(select(PasswordReset)).all() == []

    def test_only_the_latest_code_stays_active(self, client, register, db_session):
        register()
        self._request(client)
        self._request(client)

        db_session.expire_all()
        records = db_session.scalars(select(PasswordReset)).all()
        assert len(records) == 2
        assert sum(1 for record in records if record.used_at is None) == 1

    def test_code_is_not_stored_in_plaintext(self, client, register, db_session, known_reset_code):
        register()
        self._request(client)

        db_session.expire_all()
        record = db_session.scalar(select(PasswordReset))
        assert record.code_hash != known_reset_code
        assert len(record.code_hash) == 64  # sha256 十六进制摘要

    def test_correct_code_sets_new_password(self, client, register, known_reset_code):
        register()
        self._request(client)

        assert self._confirm(client, known_reset_code).status_code == 200
        assert self._login(client, self.NEW_PASSWORD).status_code == 200
        assert self._login(client, self.OLD_PASSWORD).status_code == 401

    def test_reset_invalidates_all_existing_sessions(self, client, auth_headers, known_reset_code, db_session):
        self._request(client)
        assert client.get("/api/auth/me", headers=auth_headers).status_code == 200

        assert self._confirm(client, known_reset_code).status_code == 200

        db_session.expire_all()
        assert db_session.scalars(select(AuthSession)).all() == []
        assert client.get("/api/auth/me", headers=auth_headers).status_code == 401

    def test_wrong_code_is_rejected_and_attempts_are_counted(
        self, client, register, known_reset_code, db_session
    ):
        register()
        self._request(client)

        for expected in range(1, RESET_MAX_ATTEMPTS + 1):
            assert self._confirm(client, "000000").status_code == 422

            # 必须结束事务再查：MySQL 默认 REPEATABLE READ，事务一旦开启就会一直
            # 看同一个快照，只 expire_all() 读不到别的连接刚提交的写入。
            db_session.rollback()
            assert db_session.scalar(select(PasswordReset)).attempts == expected

    def test_code_is_locked_after_too_many_attempts(self, client, register, known_reset_code):
        register()
        self._request(client)

        for _ in range(RESET_MAX_ATTEMPTS):
            self._confirm(client, "000000")

        # 达到上限后即便填对验证码也不再放行，必须重新申请
        assert self._confirm(client, known_reset_code).status_code == 422
        assert self._login(client, self.NEW_PASSWORD).status_code == 401

    def test_expired_code_is_rejected(self, client, register, known_reset_code, db_session):
        register()
        self._request(client)

        db_session.expire_all()
        record = db_session.scalar(select(PasswordReset))
        record.expires_at = utcnow() - timedelta(seconds=1)
        db_session.commit()

        assert self._confirm(client, known_reset_code).status_code == 422

    def test_code_cannot_be_reused(self, client, register, known_reset_code):
        register()
        self._request(client)

        assert self._confirm(client, known_reset_code).status_code == 200
        assert self._confirm(client, known_reset_code, password="another123").status_code == 422

    def test_new_request_invalidates_the_previous_code(self, client, register, known_reset_code, monkeypatch):
        register()
        self._request(client)

        monkeypatch.setattr("backend.main.generate_reset_code", lambda: "654321")
        self._request(client)

        assert self._confirm(client, known_reset_code).status_code == 422
        assert self._confirm(client, "654321").status_code == 200

    def test_unknown_email_cannot_reset(self, client, known_reset_code):
        assert self._confirm(client, known_reset_code, email="nobody@example.com").status_code == 422

    def test_unrequested_code_is_rejected(self, client, register, known_reset_code):
        register()  # 没有申请过验证码
        assert self._confirm(client, known_reset_code).status_code == 422

    @pytest.mark.parametrize("password", ["short", " " * 10])
    def test_weak_new_password_is_rejected(self, client, register, known_reset_code, password):
        register()
        self._request(client)
        assert self._confirm(client, known_reset_code, password=password).status_code == 422

    def test_request_is_rate_limited(self, client, register):
        register()
        for _ in range(RESET_REQUEST_RATE_LIMIT[0]):
            assert self._request(client).status_code == 202
        assert self._request(client).status_code == 429


class TestResetCodeExposure:
    """验证码直接显示在页面上（开发模式）。

    未配置 SMTP 时后端会把验证码一并放进响应，页面就能直接展示，省去翻服务端日志。
    这是个明显的安全折衷——能调这个接口就能拿到任意账号的验证码——所以判定逻辑
    必须盯紧：配了 SMTP 或显式关闭时，必须立刻停止返回。
    """

    EMAIL = "player@example.com"
    NEW_PASSWORD = "newpass123"

    def _request(self, client, email=EMAIL):
        return client.post("/api/auth/password-reset/request", json={"email": email})

    def _confirm(self, client, code, email=EMAIL):
        return client.post(
            "/api/auth/password-reset/confirm",
            json={"email": email, "code": code, "new_password": self.NEW_PASSWORD},
        )

    def test_exposed_by_default_without_smtp(
        self, client, register, known_reset_code, monkeypatch
    ):
        """默认配置（未配 SMTP）下返回验证码，而且这个码真能改密码。"""
        monkeypatch.delenv("SMTP_HOST", raising=False)
        monkeypatch.delenv("EXPOSE_RESET_CODE", raising=False)
        register()

        body = self._request(client).json()
        assert body["delivery"] == "console"
        assert body["code"] == known_reset_code

        assert self._confirm(client, body["code"]).status_code == 200

    def test_unregistered_email_gets_useless_code(self, client, monkeypatch, db_session):
        """未注册的邮箱同样拿到一个验证码，但它没落库、必然用不了。

        否则「响应里带不带 code」就等于「邮箱注册过没有」，枚举口子会重新打开。
        """
        monkeypatch.setattr("backend.main.generate_reset_code", lambda: "111111")

        body = self._request(client, "nobody@example.com").json()
        assert body.get("code") == "111111"

        assert self._confirm(client, "111111", email="nobody@example.com").status_code == 422
        assert db_session.scalars(select(PasswordReset)).all() == []

    def test_hidden_when_smtp_is_configured(
        self, client, register, known_reset_code, monkeypatch
    ):
        """配了 SMTP 说明是正式环境，一律不返回验证码。"""
        register()
        monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
        monkeypatch.delenv("EXPOSE_RESET_CODE", raising=False)
        # 别真去连 SMTP（会等到超时），投递本身不是这个用例的关注点
        monkeypatch.setattr("backend.main._send_reset_code", lambda *args, **kwargs: None)

        body = self._request(client).json()
        assert body["delivery"] == "smtp"
        assert "code" not in body

    @pytest.mark.parametrize("value", ["0", "false", "no", "off"])
    def test_hidden_when_explicitly_disabled(self, client, register, monkeypatch, value):
        register()
        monkeypatch.setenv("EXPOSE_RESET_CODE", value)
        assert "code" not in self._request(client).json()

    def test_can_be_forced_on_explicitly(
        self, client, register, known_reset_code, monkeypatch
    ):
        """显式打开时即便配了 SMTP 也会返回——给线上排查用，清楚风险再用。"""
        register()
        monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
        monkeypatch.setenv("EXPOSE_RESET_CODE", "1")
        monkeypatch.setattr("backend.main._send_reset_code", lambda *args, **kwargs: None)

        assert self._request(client).json()["code"] == known_reset_code


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
