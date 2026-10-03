import json
from datetime import date, timedelta

import pytest

from running_coach import ollama
from running_coach.db import (
    save_race_goal,
    save_run_reflection,
    save_training_embedding,
    upsert_runs,
)


@pytest.mark.asyncio
async def test_training_context_retrieves_reflections_and_race_projection(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("RUNNING_COACH_DB", str(tmp_path / "coach.sqlite3"))
    monkeypatch.setenv("OLLAMA_EMBED_MODEL", "test-embed")
    today = date.today()
    upsert_runs(
        [
            {
                "id": "recent-5k",
                "name": "Morning run",
                "distance_km": 5,
                "moving_time_minutes": 30,
                "start_date_local": today.isoformat(),
            }
        ]
    )
    save_run_reflection("recent-5k", "Tired legs", "Poor sleep", 8, None, None)
    save_training_embedding("run", "recent-5k", "test-embed", [1, 0])
    save_race_goal("City 10K", (today + timedelta(days=30)).isoformat(), 10, 3900)

    async def fake_embed_texts(texts):
        return [[1, 0] for _ in texts]

    monkeypatch.setattr(ollama, "embed_texts", fake_embed_texts)
    context = await ollama._training_context("Why did my legs feel tired?")

    assert "How the run felt: Tired legs" in context
    assert "Poor sleep" in context
    assert "assessment within_projection" in context
    assert "do not recalculate" in context
    assert "Never say training was increased, harder than usual, or more intense than before" in context


@pytest.mark.asyncio
async def test_plain_json_tool_calls_are_executed_instead_of_shown(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("RUNNING_COACH_DB", str(tmp_path / "coach.sqlite3"))
    tools = [
        {"type": "function", "function": {"name": "sheets_training_sheet"}},
        {"type": "function", "function": {"name": "strava_recent_runs"}},
    ]
    replies = [
        {
            "message": {
                "role": "assistant",
                "content": '{"name":"sheets_training_sheet","parameters":{}}; '
                '{"name":"strava_recent_runs","parameters":{"days":1}}',
            }
        },
        {"message": {"role": "assistant", "content": "Your latest run was 18 km."}},
    ]
    requests = []
    called = []

    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    class FakeClient:
        def __init__(self, timeout):
            assert timeout == 120

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, json):
            requests.append(json)
            return FakeResponse(replies.pop(0))

    async def fake_connect(stack):
        return {"sheets": object(), "strava": object()}, tools

    async def fake_call(clients, name, arguments):
        called.append((name, arguments))
        return f"result for {name}"

    monkeypatch.setattr(ollama, "connect_mcp_servers", fake_connect)
    monkeypatch.setattr(ollama, "call_mcp_tool", fake_call)
    monkeypatch.setattr(ollama.httpx, "AsyncClient", FakeClient)

    response = await ollama.chat_with_ollama(
        "Analyze today's run for my December marathon goal.", "en", False
    )

    assert response == "Your latest run was 18 km."
    assert called == [
        ("sheets_training_sheet", {}),
        ("strava_recent_runs", {"days": 1}),
    ]
    assert requests[1]["messages"][-2]["role"] == "tool"
    assert "sheets_training_sheet" not in response


@pytest.mark.asyncio
async def test_marathon_question_returns_deterministic_strava_and_plan_analysis(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("RUNNING_COACH_DB", str(tmp_path / "coach.sqlite3"))
    tools = [
        {"type": "function", "function": {"name": "sheets_training_sheet"}},
        {"type": "function", "function": {"name": "strava_recent_runs"}},
    ]
    today = date.today()
    future_week = (today + timedelta(days=14)).strftime("%-m/%-d/%Y")
    runs = [
        {
            "name": "Today's run",
            "distance_km": 18.01,
            "moving_time_minutes": 118.82,
            "start_date_local": f"{today.isoformat()}T04:47:40Z",
            "average_heartrate": 150.4,
            "temperature_c": 32,
        },
        {
            "name": "Long run",
            "distance_km": 24.01,
            "moving_time_minutes": 179.35,
            "start_date_local": f"{(today - timedelta(days=7)).isoformat()}T05:00:00Z",
            "average_heartrate": 142.5,
        },
        {
            "name": "Half marathon",
            "distance_km": 21.01,
            "moving_time_minutes": 144.28,
            "start_date_local": f"{(today - timedelta(days=14)).isoformat()}T05:00:00Z",
        },
    ]
    sheet = {
        "sheet": "Marathon",
        "completed_count": 16,
        "rows": [
            {
                "values": ["#", "Week", "Tue", "Sat", "Mileage", "Comments", "Weekend Run"],
                "completed": False,
            },
            {
                "values": ["24", future_week, "12", "30", "58", "5 Easy 5 MP", "6:50 - 7:00"],
                "completed": False,
            },
        ],
    }
    called = []

    async def fake_connect(stack):
        return {"strava": object(), "sheets": object()}, tools

    async def fake_call(clients, name, arguments):
        called.append((name, arguments))
        if name == "strava_recent_runs":
            return json.dumps({"activities": runs})
        return json.dumps(sheet)

    monkeypatch.setattr(ollama, "connect_mcp_servers", fake_connect)
    monkeypatch.setattr(ollama, "call_mcp_tool", fake_call)

    response = await ollama.chat_with_ollama(
        "Can you get details about my today's run and whether I can do a full marathon "
        "sub 4 hours 50 minutes on 12th December?",
        "en-ta",
        True,
    )

    assert called == [
        ("strava_recent_runs", {"days": 90}),
        ("sheets_training_sheet", {}),
    ]
    assert "18.01 km" in response
    assert "6:36/km" in response
    assert "6:52.4/km" in response
    assert "ambitious stretch" in response
    assert "long run 30 km" in response
    assert "58 km planned" in response
    assert "Keep the planned taper" in response or "planned taper" in response
    assert "sheets_training_sheet" not in response