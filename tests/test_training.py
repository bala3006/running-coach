from running_coach.training import summarize_runs


def test_run_summary_calculates_total_distance_and_average_pace() -> None:
    summary = summarize_runs(
        [
            {"distance_km": 5, "moving_time_minutes": 30},
            {"distance_km": 10, "moving_time_minutes": 55},
            {"distance_km": 0, "moving_time_minutes": 15},
        ]
    )

    assert summary == {
        "run_count": 2,
        "distance_km": 15,
        "moving_time_minutes": 85,
        "average_pace_min_per_km": 5.67,
    }


def test_run_summary_handles_empty_activity_list() -> None:
    assert summarize_runs([]) == {
        "run_count": 0,
        "distance_km": 0,
        "moving_time_minutes": 0,
        "average_pace_min_per_km": None,
    }