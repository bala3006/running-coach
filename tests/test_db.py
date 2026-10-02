from running_coach.db import get_history, save_exchange


def test_exchange_is_persisted_and_sessions_are_isolated(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("RUNNING_COACH_DB", str(tmp_path / "coach.sqlite3"))

    save_exchange("session-a", "How was my week?", "Let's review your runs.")

    assert get_history("session-a") == [
        {"role": "user", "content": "How was my week?"},
        {"role": "assistant", "content": "Let's review your runs."},
    ]
    assert get_history("session-b") == []
