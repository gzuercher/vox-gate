from subprocess import CompletedProcess
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _clear_token(monkeypatch):
    monkeypatch.setenv("API_TOKEN", "")
    monkeypatch.setenv("ALLOWED_ORIGIN", "")


def _reload_app():
    import importlib

    import server

    importlib.reload(server)
    return TestClient(server.app)


def _mock_claude(stdout="ok", returncode=0):
    return patch(
        "subprocess.run",
        return_value=CompletedProcess([], returncode, stdout=stdout, stderr=""),
    )


class TestPromptEndpoint:
    def test_prompt_returns_claude_response(self):
        client = _reload_app()
        with _mock_claude(stdout="Hello from Claude"):
            res = client.post("/prompt", json={"text": "hi"})
        assert res.status_code == 200
        assert res.json()["response"] == "Hello from Claude"

    def test_prompt_empty_text_rejected(self):
        client = _reload_app()
        res = client.post("/prompt", json={"text": ""})
        assert res.status_code == 422

    def test_prompt_too_long_rejected(self):
        client = _reload_app()
        res = client.post("/prompt", json={"text": "a" * 5000})
        assert res.status_code == 422

    def test_prompt_missing_text_rejected(self):
        client = _reload_app()
        res = client.post("/prompt", json={})
        assert res.status_code == 422

    def test_claude_error_returns_500(self):
        client = _reload_app()
        with _mock_claude(returncode=1):
            res = client.post("/prompt", json={"text": "hi"})
        assert res.status_code == 500
        assert "error" in res.json()["detail"].lower()

    def test_stderr_not_leaked(self):
        client = _reload_app()
        with patch(
            "subprocess.run",
            return_value=CompletedProcess([], 1, stdout="", stderr="secret debug info"),
        ):
            res = client.post("/prompt", json={"text": "hi"})
        assert "secret" not in res.text


class TestAuth:
    def test_no_token_required_when_unset(self):
        client = _reload_app()
        with _mock_claude():
            res = client.post("/prompt", json={"text": "hi"})
        assert res.status_code == 200

    def test_valid_token_accepted(self, monkeypatch):
        monkeypatch.setenv("API_TOKEN", "secret123")
        client = _reload_app()
        with _mock_claude():
            res = client.post(
                "/prompt",
                json={"text": "hi"},
                headers={"Authorization": "Bearer secret123"},
            )
        assert res.status_code == 200

    def test_wrong_token_rejected(self, monkeypatch):
        monkeypatch.setenv("API_TOKEN", "secret123")
        client = _reload_app()
        res = client.post(
            "/prompt",
            json={"text": "hi"},
            headers={"Authorization": "Bearer wrong"},
        )
        assert res.status_code == 401

    def test_missing_token_rejected_when_required(self, monkeypatch):
        monkeypatch.setenv("API_TOKEN", "secret123")
        client = _reload_app()
        res = client.post("/prompt", json={"text": "hi"})
        assert res.status_code == 401


class TestStaticFiles:
    def test_index_html_served(self):
        client = _reload_app()
        res = client.get("/")
        assert res.status_code == 200
        assert "VoiceClaude" in res.text
