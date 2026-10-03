from datetime import date

from running_coach.training import (
    analyze_marathon_goal,
    parse_marathon_goal_request,
    project_race_goal,
    summarize_runs,
)


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


def test_race_projection_compares_target_with_recent_comparable_run() -> None:
    result = project_race_goal(
        [
            {
                "name": "5K steady",
                "distance_km": 5,
                "moving_time_minutes": 30,
                "start_date_local": "2026-09-20T07:00:00Z",
            }
        ],
        distance_km=10,
        target_time_seconds=3900,
        event_date="2026-11-01",
        as_of=date(2026, 10, 1),
    )

    assert result["verdict"] == "within_projection"
    assert result["estimated_time_seconds"] == 3753
    assert result["basis_run"]["name"] == "5K steady"
    assert result["distance_fit"] == "long extrapolation"


def test_race_projection_needs_recent_comparable_data() -> None:
    result = project_race_goal(
        [
            {
                "distance_km": 5,
                "moving_time_minutes": 30,
                "start_date_local": "2026-01-01T07:00:00Z",
            }
        ],
        distance_km=21.1,
        target_time_seconds=7200,
        event_date="2026-11-01",
        as_of=date(2026, 10, 1),
    )

    assert result["verdict"] == "insufficient_data"
    assert result["estimated_time_seconds"] is None


def test_marathon_request_parses_sub_time_and_december_date() -> None:
    request = parse_marathon_goal_request(
        "Can I run a full marathon sub 4hrs 50mins on 12th December?",
        as_of=date(2026, 10, 3),
    )

    assert request == {
        "distance_km": 42.195,
        "target_time_seconds": 17400,
        "event_date": "2026-12-12",
    }


def test_marathon_analysis_returns_today_long_run_and_target_pace() -> None:
    runs = [
        {
            "name": "Today's run",
            "distance_km": 18.01,
            "moving_time_minutes": 118.82,
            "start_date_local": "2026-10-03T04:47:40Z",
            "average_heartrate": 150.4,
            "temperature_c": 32,
        },
        {
            "name": "Long run",
            "distance_km": 24.01,
            "moving_time_minutes": 179.35,
            "start_date_local": "2026-09-26T05:00:00Z",
            "average_heartrate": 142.5,
        },
        {
            "name": "Half marathon",
            "distance_km": 21.01,
            "moving_time_minutes": 144.28,
            "start_date_local": "2026-09-19T05:00:00Z",
        },
    ]

    result = analyze_marathon_goal(
        runs,
        target_time_seconds=17400,
        event_date="2026-12-12",
        as_of=date(2026, 10, 3),
    )

    assert result["target_pace_seconds_per_km"] == 412.4
    assert result["today_run"]["distance_km"] == 18.01
    assert result["longest_run"]["distance_km"] == 24.01
    assert result["projections"][0]["projected_marathon_seconds"] == 17578
    assert result["assessment"] == "stretch_target"