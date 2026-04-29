from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from auth.providers import AuthError, VerifiedIdentity

TEST_EMAIL = "ok@example.com"
TEST_OTHER_EMAIL = "other@example.com"


class _FakeVerifier:
    def __init__(self, name="google", email=TEST_EMAIL, raises=False, email_unverified=False):
        self.name = name
        self._email = email
        self._raises = raises
        self._email_unverified = email_unverified

    def verify(self, id_token: str):
        if self._raises:
            raise AuthError("invalid token")
        if self._email_unverified:
            raise AuthError("email not verified by Google")
        return VerifiedIdentity(email=self._email, provider=self.name, subject="sub-123")


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client.apps.googleusercontent.com")
    monkeypatch.setenv("ALLOWED_EMAILS", TEST_EMAIL)
    monkeypatch.setenv("SESSION_SECRET", "test-secret-do-not-use-in-prod")
    monkeypatch.setenv("SESSION_COOKIE_TTL_SECONDS", "3600")
    monkeypatch.setenv("COOKIE_SECURE", "0")
    monkeypatch.setenv("TARGET_URL", "http://backend:9000/prompt")
    monkeypatch.setenv("TARGET_TOKEN", "")
    monkeypatch.setenv("ALLOWED_ORIGIN", "")
    monkeypatch.setenv("INSTANCE_NAME", "TestBot")
    monkeypatch.setenv("INSTANCE_COLOR", "#ff0000")
    monkeypatch.setenv("SPEECH_LANG", "de-CH")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "10000")
    monkeypatch.setenv("AUTH_LOGIN_RATE_LIMIT_PER_MINUTE", "10000")


def _reload_app(login: bool = True, verifier: _FakeVerifier | None = None):
    """
    Reload server module to pick up env, install a fake verifier, and (by default)
    log a TestClient in so cookies + CSRF header are set.
    """
    import importlib

    import server

    importlib.reload(server)
    fake = verifier or _FakeVerifier()
    server.PROVIDERS["google"] = fake
    client = TestClient(server.app)
    if login:
        _do_login(client)
    return client


def _do_login(client: TestClient, provider: str = "google", id_token: str = "any") -> int:
    res = client.post(f"/auth/login/{provider}", json={"id_token": id_token})
    if res.status_code == 200:
        # Wire CSRF header for subsequent state-changing requests.
        csrf = client.cookies.get("vg_csrf")
        if csrf:
            client.headers.update({"X-CSRF-Token": csrf})
    return res.status_code


def _mock_target(json_body=None, status_code=200, raise_error=False):
    if json_body is None:
        json_body = {"response": "ok"}

    if raise_error:
        mock_post = AsyncMock(side_effect=httpx.RequestError("connection failed"))
    else:
        mock_response = httpx.Response(status_code, json=json_body)
        mock_post = AsyncMock(return_value=mock_response)

    mock_client = AsyncMock()
    mock_client.post = mock_post
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    return patch("httpx.AsyncClient", return_value=mock_client)


class TestConfigEndpoint:
    def test_returns_instance_config(self):
        client = _reload_app()
        res = client.get("/config")
        assert res.status_code == 200
        data = res.json()
        assert data["name"] == "TestBot"
        assert data["color"] == "#ff0000"
        assert data["lang"] == "de-CH"
        assert "de-CH" in data["langs"]

    def test_speech_langs_configurable(self, monkeypatch):
        monkeypatch.setenv("SPEECH_LANGS", "de-CH,en-US")
        client = _reload_app()
        data = client.get("/config").json()
        assert data["langs"] == ["de-CH", "en-US"]

    def test_default_lang_always_in_langs_list(self, monkeypatch):
        monkeypatch.setenv("SPEECH_LANG", "pt-PT")
        monkeypatch.setenv("SPEECH_LANGS", "de-CH,en-US")
        client = _reload_app()
        data = client.get("/config").json()
        assert data["langs"][0] == "pt-PT"

    def test_exposes_google_client_id_and_providers(self):
        client = _reload_app()
        data = client.get("/config").json()
        assert data["googleClientId"] == "test-client.apps.googleusercontent.com"
        assert data["providers"] == ["google"]


class TestPromptEndpoint:
    def test_forwards_to_target(self):
        client = _reload_app()
        with _mock_target({"response": "Hello from backend"}):
            res = client.post("/prompt", json={"text": "hi"})
        assert res.status_code == 200
        assert res.json()["response"] == "Hello from backend"

    def test_empty_text_rejected(self):
        client = _reload_app()
        res = client.post("/prompt", json={"text": ""})
        assert res.status_code == 422

    def test_too_long_rejected(self):
        client = _reload_app()
        res = client.post("/prompt", json={"text": "a" * 5000})
        assert res.status_code == 422

    def test_missing_text_rejected(self):
        client = _reload_app()
        res = client.post("/prompt", json={})
        assert res.status_code == 422

    def test_target_unreachable_returns_502(self):
        client = _reload_app()
        with _mock_target(raise_error=True):
            res = client.post("/prompt", json={"text": "hi"})
        assert res.status_code == 502
        assert "unreachable" in res.json()["detail"].lower()

    def test_target_error_returns_502(self):
        client = _reload_app()
        with _mock_target(status_code=500, json_body={"error": "internal"}):
            res = client.post("/prompt", json={"text": "hi"})
        assert res.status_code == 502

    def test_no_target_configured(self, monkeypatch):
        monkeypatch.setenv("TARGET_URL", "")
        client = _reload_app()
        res = client.post("/prompt", json={"text": "hi"})
        assert res.status_code == 503


class TestAuthLogin:
    def test_login_accepted_when_allowlisted(self):
        client = _reload_app(login=False)
        status = _do_login(client)
        assert status == 200
        assert client.cookies.get("vg_session")
        assert client.cookies.get("vg_csrf")

    def test_login_rejected_when_not_allowlisted(self):
        client = _reload_app(login=False, verifier=_FakeVerifier(email=TEST_OTHER_EMAIL))
        status = _do_login(client)
        assert status == 403

    def test_login_rejected_when_email_not_verified(self):
        client = _reload_app(login=False, verifier=_FakeVerifier(email_unverified=True))
        status = _do_login(client)
        assert status == 401

    def test_invalid_signature_rejected(self):
        client = _reload_app(login=False, verifier=_FakeVerifier(raises=True))
        status = _do_login(client)
        assert status == 401

    def test_unknown_provider_returns_404(self):
        client = _reload_app(login=False)
        res = client.post("/auth/login/microsoft", json={"id_token": "x"})
        assert res.status_code == 404

    def test_me_returns_email_when_authenticated(self):
        client = _reload_app()
        res = client.get("/auth/me")
        assert res.status_code == 200
        assert res.json() == {"email": TEST_EMAIL, "provider": "google"}

    def test_me_unauthenticated(self):
        client = _reload_app(login=False)
        res = client.get("/auth/me")
        assert res.status_code == 401

    def test_logout_clears_cookies(self):
        client = _reload_app()
        res = client.post("/auth/logout")
        assert res.status_code == 200
        # After logout, /auth/me must reject.
        client.headers.pop("X-CSRF-Token", None)
        res = client.get("/auth/me")
        assert res.status_code == 401

    def test_providers_endpoint_lists_google(self):
        client = _reload_app(login=False)
        res = client.get("/auth/providers")
        assert res.status_code == 200
        assert res.json() == {"providers": ["google"]}


class TestSessionAuthCSRF:
    def test_session_protects_claude_with_csrf(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "key")
        client = _reload_app()
        import server

        fake, _ = _mock_anthropic("Hello!")
        server._anthropic_client = fake
        res = client.post("/claude", json={"text": "hi", "session_id": "session1x"})
        assert res.status_code == 200

    def test_missing_csrf_rejects(self):
        client = _reload_app()
        client.headers.pop("X-CSRF-Token", None)
        with _mock_target():
            res = client.post("/prompt", json={"text": "hi"})
        assert res.status_code == 403

    def test_no_session_rejects(self):
        client = _reload_app(login=False)
        with _mock_target():
            res = client.post("/prompt", json={"text": "hi"})
        assert res.status_code == 401

    def test_email_removed_from_allowlist_blocks_subsequent_requests(self):
        client = _reload_app()
        import server

        # User was logged in; now strip allowlist live.
        server._auth_config.allowed_emails.clear()
        with _mock_target():
            res = client.post("/prompt", json={"text": "hi"})
        assert res.status_code == 403

    def test_provider_binding_in_allowlist(self):
        # Allow ok@example.com only via google. Logging in via "microsoft" must be blocked
        # even though the email matches.
        import server

        client = _reload_app(login=False)
        server.PROVIDERS["microsoft"] = _FakeVerifier(name="microsoft", email=TEST_EMAIL)
        server._auth_config.allowed_emails[TEST_EMAIL] = "google"
        # Google login still works.
        assert _do_login(client, provider="google") == 200
        # But microsoft is blocked.
        client.cookies.clear()
        client.headers.pop("X-CSRF-Token", None)
        assert _do_login(client, provider="microsoft") == 403


class _FakeTextBlock:
    type = "text"

    def __init__(self, text):
        self.text = text


class _FakeMessage:
    def __init__(self, text):
        self.content = [_FakeTextBlock(text)]


def _mock_anthropic(reply="Hi there", raise_error=False):
    if raise_error:
        create = AsyncMock(side_effect=RuntimeError("boom"))
    else:
        create = AsyncMock(return_value=_FakeMessage(reply))
    fake_client = type("C", (), {})()
    fake_client.messages = type("M", (), {"create": create})()
    return fake_client, create


class TestClaudeEndpoint:
    def test_no_api_key_returns_503(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "")
        client = _reload_app()
        res = client.post("/claude", json={"text": "hi", "session_id": "session1x"})
        assert res.status_code == 503

    def test_returns_assistant_reply(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "key")
        client = _reload_app()
        import server

        fake, _ = _mock_anthropic("Hello!")
        server._anthropic_client = fake
        res = client.post("/claude", json={"text": "hi", "session_id": "session1x"})
        assert res.status_code == 200
        assert res.json()["response"] == "Hello!"

    def test_session_history_persists(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "key")
        client = _reload_app()
        import server

        snapshots = []

        async def fake_create(**kwargs):
            snapshots.append([dict(m) for m in kwargs["messages"]])
            return _FakeMessage("reply")

        fake = type("C", (), {})()
        msgs_obj = type("M", (), {})()
        msgs_obj.create = fake_create
        fake.messages = msgs_obj
        server._anthropic_client = fake
        client.post("/claude", json={"text": "first", "session_id": "abcdefgh"})
        client.post("/claude", json={"text": "second", "session_id": "abcdefgh"})
        msgs = snapshots[1]
        assert msgs[0] == {"role": "user", "content": "first"}
        assert msgs[1] == {"role": "assistant", "content": "reply"}
        assert msgs[2] == {"role": "user", "content": "second"}

    def test_history_truncated_to_max(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "key")
        client = _reload_app()
        import server

        fake, _ = _mock_anthropic("ok")
        server._anthropic_client = fake
        for i in range(15):
            res = client.post(
                "/claude", json={"text": f"m{i}", "session_id": "trunc123"}
            )
            assert res.status_code == 200
        assert len(server._sessions["trunc123"]["messages"]) <= server.SESSION_MAX_MESSAGES

    def test_sessions_isolated(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "key")
        client = _reload_app()
        import server

        snapshots = []

        async def fake_create(**kwargs):
            snapshots.append([dict(m) for m in kwargs["messages"]])
            return _FakeMessage("ok")

        fake = type("C", (), {})()
        msgs_obj = type("M", (), {})()
        msgs_obj.create = fake_create
        fake.messages = msgs_obj
        server._anthropic_client = fake
        client.post("/claude", json={"text": "a-msg", "session_id": "sessionAA"})
        client.post("/claude", json={"text": "b-msg", "session_id": "sessionBB"})
        assert snapshots[1] == [{"role": "user", "content": "b-msg"}]

    def test_api_error_rolls_back_history(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "key")
        client = _reload_app()
        import server

        fake, _ = _mock_anthropic(raise_error=True)
        server._anthropic_client = fake
        res = client.post("/claude", json={"text": "hi", "session_id": "errsess1"})
        assert res.status_code == 502
        assert server._sessions.get("errsess1", {"messages": []})["messages"] == []

    def test_missing_session_id_rejected(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "key")
        client = _reload_app()
        res = client.post("/claude", json={"text": "hi"})
        assert res.status_code == 422

    def test_auth_required(self):
        client = _reload_app(login=False)
        res = client.post("/claude", json={"text": "hi", "session_id": "sessshort"})
        assert res.status_code == 401


class TestStaticFiles:
    def test_index_html_served(self):
        client = _reload_app(login=False)
        res = client.get("/")
        assert res.status_code == 200
        assert "VoxGate" in res.text


class TestSecurityHeaders:
    def test_csp_and_headers_set(self):
        client = _reload_app(login=False)
        res = client.get("/config")
        assert "content-security-policy" in {k.lower() for k in res.headers}
        assert res.headers["X-Content-Type-Options"] == "nosniff"
        assert res.headers["X-Frame-Options"] == "DENY"
        assert "strict-origin" in res.headers["Referrer-Policy"]
        assert "microphone=(self)" in res.headers["Permissions-Policy"]

    def test_csp_blocks_inline_script(self):
        client = _reload_app(login=False)
        res = client.get("/config")
        csp = res.headers["Content-Security-Policy"]
        assert "'unsafe-inline'" not in csp.split("script-src")[1].split(";")[0]

    def test_csp_allows_google_identity_services(self):
        client = _reload_app(login=False)
        csp = client.get("/config").headers["Content-Security-Policy"]
        assert "https://accounts.google.com/gsi/client" in csp
        assert "frame-src https://accounts.google.com/gsi/" in csp


class TestSessionIdValidation:
    def test_short_session_id_rejected(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "key")
        client = _reload_app()
        res = client.post("/claude", json={"text": "hi", "session_id": "abc"})
        assert res.status_code == 422

    def test_session_id_with_control_chars_rejected(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "key")
        client = _reload_app()
        res = client.post(
            "/claude", json={"text": "hi", "session_id": "abcdefgh\n\rdroptable"}
        )
        assert res.status_code == 422

    def test_overlong_session_id_rejected(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "key")
        client = _reload_app()
        res = client.post(
            "/claude", json={"text": "hi", "session_id": "a" * 200}
        )
        assert res.status_code == 422


class TestRateLimit:
    def test_rate_limit_triggers_429(self, monkeypatch):
        monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "3")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "key")
        client = _reload_app()
        import server

        fake, _ = _mock_anthropic("ok")
        server._anthropic_client = fake
        for _ in range(3):
            res = client.post(
                "/claude", json={"text": "hi", "session_id": "ratelmt1"}
            )
            assert res.status_code == 200
        res = client.post("/claude", json={"text": "hi", "session_id": "ratelmt1"})
        assert res.status_code == 429

    def test_login_rate_limit(self, monkeypatch):
        monkeypatch.setenv("AUTH_LOGIN_RATE_LIMIT_PER_MINUTE", "2")
        client = _reload_app(login=False)
        for _ in range(2):
            assert _do_login(client) == 200
            client.cookies.clear()
            client.headers.pop("X-CSRF-Token", None)
        res = client.post("/auth/login/google", json={"id_token": "x"})
        assert res.status_code == 429


class TestSessionTTL:
    def test_expired_sessions_evicted(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "key")
        monkeypatch.setenv("SESSION_TTL_SECONDS", "1")
        client = _reload_app()
        import server

        fake, _ = _mock_anthropic("ok")
        server._anthropic_client = fake
        client.post("/claude", json={"text": "hi", "session_id": "ttltest1"})
        assert "ttltest1" in server._sessions
        server._sessions["ttltest1"]["last_seen"] -= 10
        client.post("/claude", json={"text": "again", "session_id": "ttltest2"})
        assert "ttltest1" not in server._sessions
        assert "ttltest2" in server._sessions

    def test_max_sessions_cap(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "key")
        monkeypatch.setenv("MAX_SESSIONS", "3")
        client = _reload_app()
        import server

        fake, _ = _mock_anthropic("ok")
        server._anthropic_client = fake
        for i in range(5):
            sid = f"capacity{i}"
            client.post("/claude", json={"text": "hi", "session_id": sid})
            server._sessions[sid]["last_seen"] -= (5 - i)
        assert len(server._sessions) <= 3


class TestSessionSecretAutogen:
    def test_auto_generates_session_secret_when_empty(self, monkeypatch):
        monkeypatch.setenv("SESSION_SECRET", "")
        _reload_app(login=False)
        import server

        assert len(server.SESSION_SECRET) >= 32

    def test_explicit_secret_wins_over_autogen(self, monkeypatch):
        monkeypatch.setenv("SESSION_SECRET", "my-very-secret-value")
        _reload_app(login=False)
        import server

        assert server.SESSION_SECRET == "my-very-secret-value"


class TestConfigEndpointFields:
    def test_returns_max_length(self):
        client = _reload_app(login=False)
        data = client.get("/config").json()
        assert data["maxLength"] == 4000

    def test_max_length_overridable(self, monkeypatch):
        monkeypatch.setenv("MAX_PROMPT_LENGTH", "100")
        client = _reload_app(login=False)
        assert client.get("/config").json()["maxLength"] == 100


class TestPromptBoundaries:
    def test_exactly_max_length_accepted(self):
        client = _reload_app()
        with _mock_target():
            res = client.post("/prompt", json={"text": "a" * 4000})
        assert res.status_code == 200

    def test_one_over_max_rejected(self):
        client = _reload_app()
        res = client.post("/prompt", json={"text": "a" * 4001})
        assert res.status_code == 422


class TestStaticAssets:
    @pytest.mark.parametrize(
        "path,fragment",
        [
            ("/app.js", "instanceConfig"),
            ("/styles.css", ":root"),
            ("/manifest.json", "name"),
            ("/sw.js", ""),
            ("/icon.svg", "<svg"),
        ],
    )
    def test_pwa_asset_served(self, path, fragment):
        client = _reload_app(login=False)
        res = client.get(path)
        assert res.status_code == 200
        if fragment:
            assert fragment in res.text


class TestCORS:
    def test_allowed_origin_passes_through(self, monkeypatch):
        monkeypatch.setenv("ALLOWED_ORIGIN", "https://allowed.example.com")
        client = _reload_app(login=False)
        res = client.options(
            "/config",
            headers={
                "Origin": "https://allowed.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert res.headers.get("access-control-allow-origin") == "https://allowed.example.com"

    def test_other_origin_blocked(self, monkeypatch):
        monkeypatch.setenv("ALLOWED_ORIGIN", "https://allowed.example.com")
        client = _reload_app(login=False)
        res = client.options(
            "/config",
            headers={
                "Origin": "https://attacker.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert res.headers.get("access-control-allow-origin") != "https://attacker.example.com"


class TestProxyHeaderTrust:
    def test_xff_ignored_by_default(self, monkeypatch):
        monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "2")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "key")
        client = _reload_app()
        import server

        fake, _ = _mock_anthropic("ok")
        server._anthropic_client = fake
        for xff in ["1.1.1.1", "2.2.2.2", "3.3.3.3"]:
            client.post(
                "/claude",
                json={"text": "hi", "session_id": "xfftest1"},
                headers={"X-Forwarded-For": xff},
            )
        res = client.post(
            "/claude",
            json={"text": "hi", "session_id": "xfftest1"},
            headers={"X-Forwarded-For": "4.4.4.4"},
        )
        assert res.status_code == 429

    def test_xff_used_when_trusted(self, monkeypatch):
        monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "2")
        monkeypatch.setenv("TRUST_PROXY_HEADERS", "1")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "key")
        client = _reload_app()
        import server

        fake, _ = _mock_anthropic("ok")
        server._anthropic_client = fake
        for xff in ["1.1.1.1", "2.2.2.2", "3.3.3.3", "4.4.4.4"]:
            res = client.post(
                "/claude",
                json={"text": "hi", "session_id": "xfftest2"},
                headers={"X-Forwarded-For": xff},
            )
            assert res.status_code == 200


class TestRateLimitIsolation:
    def test_static_assets_not_rate_limited(self, monkeypatch):
        monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "2")
        client = _reload_app(login=False)
        for _ in range(10):
            assert client.get("/config").status_code == 200


class TestAnthropicResponseHandling:
    def test_ignores_non_text_content_blocks(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "key")
        client = _reload_app()
        import server

        class ToolBlock:
            type = "tool_use"

        class TextBlock:
            type = "text"
            text = "real reply"

        msg = type("M", (), {"content": [ToolBlock(), TextBlock()]})()
        fake = type("C", (), {})()
        msgs_obj = type("M2", (), {})()
        msgs_obj.create = AsyncMock(return_value=msg)
        fake.messages = msgs_obj
        server._anthropic_client = fake
        res = client.post(
            "/claude", json={"text": "hi", "session_id": "tooltest1"}
        )
        assert res.status_code == 200
        assert res.json()["response"] == "real reply"

    def test_empty_content_yields_empty_string(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "key")
        client = _reload_app()
        import server

        msg = type("M", (), {"content": []})()
        fake = type("C", (), {})()
        msgs_obj = type("M2", (), {})()
        msgs_obj.create = AsyncMock(return_value=msg)
        fake.messages = msgs_obj
        server._anthropic_client = fake
        res = client.post(
            "/claude", json={"text": "hi", "session_id": "emptyrep1"}
        )
        assert res.status_code == 200
        assert res.json()["response"] == ""


class TestHistoryTruncationKeepsPairs:
    def test_trimmed_history_starts_with_user(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "key")
        client = _reload_app()
        import server

        fake, _ = _mock_anthropic("a")
        server._anthropic_client = fake
        for i in range(15):
            client.post(
                "/claude", json={"text": f"m{i}", "session_id": "pairtest1"}
            )
        history = server._sessions["pairtest1"]["messages"]
        assert history[0]["role"] == "user"
        assert len(history) % 2 == 0


class TestPromptForwardsTokenAndStripsResponse:
    def test_target_token_added(self, monkeypatch):
        monkeypatch.setenv("TARGET_TOKEN", "downstream-secret")
        client = _reload_app()
        captured = {}

        def fake_post(url, json, headers):
            captured["headers"] = headers
            captured["json"] = json
            return httpx.Response(200, json={"response": "ok"})

        async def async_post(*args, **kwargs):
            return fake_post(*args, **kwargs)

        with patch("httpx.AsyncClient") as cm:
            instance = AsyncMock()
            instance.post = async_post
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=None)
            cm.return_value = instance
            res = client.post("/prompt", json={"text": "hi"})

        assert res.status_code == 200
        assert captured["headers"]["Authorization"] == "Bearer downstream-secret"
        assert captured["json"] == {"text": "hi"}

    def test_non_json_response_falls_back_to_text(self):
        client = _reload_app()
        mock_response = httpx.Response(200, text="plain text answer")
        mock_post = AsyncMock(return_value=mock_response)
        mock_client = AsyncMock()
        mock_client.post = mock_post
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        with patch("httpx.AsyncClient", return_value=mock_client):
            res = client.post("/prompt", json={"text": "hi"})
        assert res.status_code == 200
        assert res.json()["response"] == "plain text answer"


class TestAllowlistParsing:
    def test_provider_binding_parsed(self, monkeypatch):
        monkeypatch.setenv(
            "ALLOWED_EMAILS", "alice@example.com:google,bob@example.com"
        )
        _reload_app(login=False)
        import server

        assert server.ALLOWED_EMAILS == {
            "alice@example.com": "google",
            "bob@example.com": None,
        }

    def test_emails_lowercased_and_trimmed(self, monkeypatch):
        monkeypatch.setenv("ALLOWED_EMAILS", "  Alice@Example.COM  , BOB@x.io ")
        _reload_app(login=False)
        import server

        assert "alice@example.com" in server.ALLOWED_EMAILS
        assert "bob@x.io" in server.ALLOWED_EMAILS

    def test_multi_colon_entry_rejected(self, monkeypatch):
        # `email:provider:extra` is malformed and should not silently lock the user out.
        monkeypatch.setenv(
            "ALLOWED_EMAILS", "alice@example.com:google:extra,bob@example.com"
        )
        _reload_app(login=False)
        import server

        assert "alice@example.com" not in server.ALLOWED_EMAILS
        assert "bob@example.com" in server.ALLOWED_EMAILS


class TestCookieSecurity:
    def test_session_cookie_attributes(self):
        client = _reload_app(login=False)
        res = client.post("/auth/login/google", json={"id_token": "x"})
        assert res.status_code == 200
        # httpx exposes raw Set-Cookie via res.headers (case-insensitive multimap).
        cookies = res.headers.get_list("set-cookie")
        session_cookie = next((c for c in cookies if c.startswith("vg_session=")), "")
        csrf_cookie = next((c for c in cookies if c.startswith("vg_csrf=")), "")
        assert session_cookie, "vg_session cookie not set"
        assert csrf_cookie, "vg_csrf cookie not set"
        # Session cookie must be HttpOnly and SameSite=Strict; CSRF cookie must NOT
        # be HttpOnly (frontend has to read it) but must still be SameSite=Strict.
        assert "httponly" in session_cookie.lower()
        assert "samesite=strict" in session_cookie.lower()
        assert "httponly" not in csrf_cookie.lower()
        assert "samesite=strict" in csrf_cookie.lower()

    def test_session_cookie_secure_when_configured(self, monkeypatch):
        monkeypatch.setenv("COOKIE_SECURE", "1")
        client = _reload_app(login=False)
        res = client.post("/auth/login/google", json={"id_token": "x"})
        cookies = res.headers.get_list("set-cookie")
        session_cookie = next(c for c in cookies if c.startswith("vg_session="))
        assert "Secure" in session_cookie

    def test_tampered_session_cookie_rejected(self):
        client = _reload_app()
        good = client.cookies.get("vg_session")
        assert good
        # Flip a character in the middle of the signed blob — the HMAC should
        # no longer verify, regardless of which segment we hit.
        mid = len(good) // 2
        bad = good[:mid] + ("A" if good[mid] != "A" else "B") + good[mid + 1:]
        # Bypass the cookie jar entirely so there's no chance of the original
        # cookie being sent alongside our forged one.
        client.cookies.clear()
        res = client.get(
            "/auth/me",
            headers={"Cookie": f"vg_session={bad}"},
        )
        assert res.status_code == 401

    def test_logout_clears_both_cookies(self):
        client = _reload_app()
        res = client.post("/auth/logout")
        assert res.status_code == 200
        cookies = res.headers.get_list("set-cookie")
        # Cleared cookies are typically Max-Age=0 or expires in the past.
        cleared = "\n".join(cookies).lower()
        assert "vg_session=" in cleared
        assert "vg_csrf=" in cleared
        assert "max-age=0" in cleared or "expires=thu, 01 jan 1970" in cleared


class TestOriginCheck:
    def test_login_blocked_from_foreign_origin(self, monkeypatch):
        monkeypatch.setenv("ALLOWED_ORIGIN", "https://app.example.com")
        client = _reload_app(login=False)
        res = client.post(
            "/auth/login/google",
            json={"id_token": "x"},
            headers={"Origin": "https://attacker.example.com"},
        )
        assert res.status_code == 403

    def test_login_accepted_from_allowed_origin(self, monkeypatch):
        monkeypatch.setenv("ALLOWED_ORIGIN", "https://app.example.com")
        client = _reload_app(login=False)
        res = client.post(
            "/auth/login/google",
            json={"id_token": "x"},
            headers={"Origin": "https://app.example.com"},
        )
        assert res.status_code == 200

    def test_login_falls_back_to_referer_when_no_origin(self, monkeypatch):
        monkeypatch.setenv("ALLOWED_ORIGIN", "https://app.example.com")
        client = _reload_app(login=False)
        res = client.post(
            "/auth/login/google",
            json={"id_token": "x"},
            headers={"Referer": "https://app.example.com/some/path?x=1"},
        )
        assert res.status_code == 200

    def test_login_unrestricted_when_allowed_origin_empty(self):
        # Default test fixture: ALLOWED_ORIGIN is "". Origin check is a no-op.
        client = _reload_app(login=False)
        res = client.post(
            "/auth/login/google",
            json={"id_token": "x"},
            headers={"Origin": "https://anywhere.example.com"},
        )
        assert res.status_code == 200

    def test_logout_blocked_from_foreign_origin(self, monkeypatch):
        monkeypatch.setenv("ALLOWED_ORIGIN", "https://app.example.com")
        client = _reload_app(login=False)
        # Log in with the right origin first.
        client.post(
            "/auth/login/google",
            json={"id_token": "x"},
            headers={"Origin": "https://app.example.com"},
        )
        csrf = client.cookies.get("vg_csrf")
        client.headers.update({"X-CSRF-Token": csrf})
        # Cross-site logout attempt.
        res = client.post(
            "/auth/logout",
            headers={"Origin": "https://attacker.example.com"},
        )
        assert res.status_code == 403


class TestLogoutCSRF:
    def test_logout_requires_csrf_when_logged_in(self):
        client = _reload_app()
        client.headers.pop("X-CSRF-Token", None)
        res = client.post("/auth/logout")
        assert res.status_code == 403

    def test_logout_idempotent_when_not_logged_in(self):
        client = _reload_app(login=False)
        res = client.post("/auth/logout")
        assert res.status_code == 200

    def test_logout_with_valid_csrf_succeeds(self):
        client = _reload_app()
        res = client.post("/auth/logout")
        assert res.status_code == 200
        # Subsequent /auth/me should now reject.
        res = client.get("/auth/me")
        assert res.status_code == 401
