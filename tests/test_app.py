import uuid

from fastapi.testclient import TestClient

import running_coach.app as app_module
from running_coach.db import get_history


def test_chat_uses_and_persists_local_session(monkeypatch, tmp_path) -> None:
    session_id = uuid.uuid4()
    monkeypatch.setenv("RUNNING_COACH_DB", str(tmp_path / "coach.sqlite3"))

    async def fake_chat(message, language, tamil_voice, history):
        assert message == "How should I recover?"
        assert language == "en-ta"
        assert tamil_voice is True
        assert history == []
        return "Easy movement and sleep are a good start."

    monkeypatch.setattr(app_module, "chat_with_ollama", fake_chat)
    response = TestClient(app_module.app).post(
        "/api/chat",
        json={"message": "How should I recover?", "session_id": str(session_id)},
    )

    assert response.status_code == 200
    assert response.json()["session_id"] == str(session_id)
    assert get_history(str(session_id))[-1]["content"] == "Easy movement and sleep are a good start."


def test_oauth_callback_rejects_invalid_state() -> None:
    response = TestClient(app_module.app).get(
        "/api/integrations/strava/callback?code=fake&state=wrong"
    )

    assert response.status_code == 400


def test_architecture_page_is_served() -> None:
    response = TestClient(app_module.app).get("/architecture")

    assert response.status_code == 200
    assert "Coach Eklavya" in response.text
    assert "MCP integrations" in response.text


def test_home_uses_updated_branding() -> None:
    response = TestClient(app_module.app).get("/")

    assert response.status_code == 200
    assert "Thunai AI" in response.text
    assert "COACH EKLAVYA" in response.text
    assert "YOUR COACH" not in response.text
