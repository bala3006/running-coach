import uuid
from datetime import date, timedelta

from fastapi.testclient import TestClient

import running_coach.app as app_module
from running_coach.db import get_history, search_training_memory, upsert_runs


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
    assert "/architecture/linkedin.png" in response.text


def test_linkedin_architecture_image_is_downloadable() -> None:
    response = TestClient(app_module.app).get("/architecture/linkedin.png")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content.startswith(b"\x89PNG\r\n\x1a\n")


def test_health_reports_embedding_model_and_memory_counts(monkeypatch) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "models": [
                    {"name": "llama3.2:latest"},
                    {"name": "nomic-embed-text:latest"},
                ]
            }

    class FakeClient:
        def __init__(self, timeout):
            assert timeout == 2

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url):
            assert url.endswith("/api/tags")
            return FakeResponse()

    monkeypatch.setattr(app_module.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(app_module, "training_memory_stats", lambda model: {"total": 4, "embedded": 3})
    response = TestClient(app_module.app).get("/api/health")

    assert response.json() == {
        "ollama": True,
        "model": "llama3.2:latest",
        "model_available": True,
        "embedding_model": "nomic-embed-text:latest",
        "embedding_model_available": True,
        "memory_total": 4,
        "memory_embedded": 3,
    }


def test_home_uses_updated_branding() -> None:
    response = TestClient(app_module.app).get("/")

    assert response.status_code == 200
    assert "Thunai AI" in response.text
    assert "COACH EKLAVYA" in response.text
    assert "YOUR COACH" not in response.text


def test_training_sync_and_reflection_are_stored_in_local_memory(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("RUNNING_COACH_DB", str(tmp_path / "coach.sqlite3"))

    async def fake_index():
        return {"model": "test-embed", "indexed": 1, "pending": 0, "available": True}

    async def fake_recent_runs(days):
        assert days == 30
        return [
            {
                "id": "strava-99",
                "name": "River run",
                "sport_type": "Run",
                "distance_km": 8,
                "moving_time_minutes": 48,
                "start_date_local": date.today().isoformat(),
                "elevation_gain_m": 45,
                "descent_m": 42,
                "temperature_c": 22,
            }
        ]

    monkeypatch.setattr(app_module, "get_recent_runs", fake_recent_runs)
    monkeypatch.setattr(app_module, "index_pending_training_memory", fake_index)
    client = TestClient(app_module.app)
    sync = client.post("/api/training/sync")

    assert sync.status_code == 200
    assert sync.json() == {
        "synced": 1,
        "days": 30,
        "model": "test-embed",
        "indexed": 1,
        "pending": 0,
        "available": True,
    }
    reflection = client.put(
        "/api/training/runs/strava-99/reflection",
        json={
            "feeling": "Tired legs",
            "notes": "Warm and humid route",
            "perceived_effort": 7,
            "temperature_c": 26,
            "humidity_pct": 80,
        },
    )

    assert reflection.status_code == 200
    assert search_training_memory("tired humid")


def test_race_goal_api_returns_deterministic_projection(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("RUNNING_COACH_DB", str(tmp_path / "coach.sqlite3"))

    async def fake_index():
        return {"model": "test-embed", "indexed": 1, "pending": 0, "available": True}

    monkeypatch.setattr(app_module, "index_pending_training_memory", fake_index)
    today = date.today()
    upsert_runs(
        [
            {
                "id": "benchmark-5k",
                "name": "Steady 5K",
                "distance_km": 5,
                "moving_time_minutes": 30,
                "start_date_local": today.isoformat(),
            }
        ]
    )

    response = TestClient(app_module.app).post(
        "/api/training/races",
        json={
            "name": "City 10K",
            "event_date": (today + timedelta(days=30)).isoformat(),
            "distance_km": 10,
            "target_time_seconds": 3900,
        },
    )

    assert response.status_code == 201
    assert response.json()["assessment"]["estimated_time_seconds"] == 3753
    assert response.json()["assessment"]["verdict"] == "within_projection"
