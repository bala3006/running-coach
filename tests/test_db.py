from running_coach.db import (
    get_history,
    list_race_goals,
    list_unembedded_training_documents,
    list_runs,
    save_exchange,
    save_race_goal,
    save_run_reflection,
    save_training_embedding,
    search_training_memory,
    training_memory_stats,
    upsert_runs,
)


def test_exchange_is_persisted_and_sessions_are_isolated(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("RUNNING_COACH_DB", str(tmp_path / "coach.sqlite3"))

    save_exchange("session-a", "How was my week?", "Let's review your runs.")

    assert get_history("session-a") == [
        {"role": "user", "content": "How was my week?"},
        {"role": "assistant", "content": "Let's review your runs."},
    ]
    assert get_history("session-b") == []


def test_synced_runs_keep_reflections_and_are_searchable(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("RUNNING_COACH_DB", str(tmp_path / "coach.sqlite3"))
    run = {
        "id": "strava-42",
        "name": "Warm humid run",
        "sport_type": "Run",
        "distance_km": 8.0,
        "moving_time_minutes": 48,
        "start_date_local": "2026-10-01T07:00:00Z",
        "elevation_gain_m": 120,
        "descent_m": 115,
        "temperature_c": 28,
        "humidity_pct": 82,
    }

    assert upsert_runs([run]) == 1
    save_run_reflection("strava-42", "Tired legs", "Humidity felt tough", 7, 28, 82)
    run["temperature_c"] = None
    run["humidity_pct"] = None
    upsert_runs([run])

    saved = list_runs()[0]
    assert saved["temperature_c"] == 28
    assert saved["humidity_pct"] == 82
    assert saved["feeling"] == "Tired legs"
    results = search_training_memory("tired humid legs")
    assert len(results) == 1
    assert "Elevation gain: 120.0 m" in results[0]["content"]
    assert "Descent: 115.0 m" in results[0]["content"]
    assert "Humidity felt tough" in results[0]["content"]


def test_race_goals_are_stored_and_searchable(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("RUNNING_COACH_DB", str(tmp_path / "coach.sqlite3"))

    goal_id = save_race_goal("City Half", "2027-03-14", 21.0975, 7200)

    assert list_race_goals()[0] == {
        "id": goal_id,
        "name": "City Half",
        "event_date": "2027-03-14",
        "distance_km": 21.0975,
        "target_time_seconds": 7200,
        "created_at": list_race_goals()[0]["created_at"],
    }
    assert search_training_memory("half race City")


def test_semantic_retrieval_finds_meaning_without_keyword_overlap(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("RUNNING_COACH_DB", str(tmp_path / "coach.sqlite3"))
    upsert_runs(
        [
            {
                "id": "hill-run",
                "name": "Hill session",
                "distance_km": 7,
                "moving_time_minutes": 45,
                "start_date_local": "2026-10-01",
            },
            {
                "id": "easy-run",
                "name": "Easy path",
                "distance_km": 5,
                "moving_time_minutes": 35,
                "start_date_local": "2026-10-02",
            },
        ]
    )
    save_run_reflection("hill-run", "", "My quadriceps were exhausted afterward", None, None, None)
    save_run_reflection("easy-run", "", "Felt relaxed today", None, None, None)
    assert len(list_unembedded_training_documents("test-embed")) == 2
    save_training_embedding("run", "hill-run", "test-embed", [1, 0])
    save_training_embedding("run", "easy-run", "test-embed", [0, 1])

    results = search_training_memory("fatigue", query_embedding=[1, 0], embedding_model="test-embed")

    assert results[0]["source_id"] == "hill-run"
    assert "vector" not in results[0]
    assert training_memory_stats("test-embed") == {"total": 2, "embedded": 2}
    upsert_runs(
        [
            {
                "id": "hill-run",
                "name": "Hill session",
                "distance_km": 7,
                "moving_time_minutes": 45,
                "start_date_local": "2026-10-01",
            }
        ]
    )
    assert training_memory_stats("test-embed")["embedded"] == 2


def test_changed_training_document_is_queued_for_reembedding(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("RUNNING_COACH_DB", str(tmp_path / "coach.sqlite3"))
    upsert_runs(
        [{"id": "run-1", "name": "Run", "distance_km": 5, "moving_time_minutes": 30}]
    )
    save_training_embedding("run", "run-1", "test-embed", [1, 0])
    save_run_reflection("run-1", "Tired", "Hard hills", 8, None, None)

    assert [item["source_id"] for item in list_unembedded_training_documents("test-embed")] == [
        "run-1"
    ]
