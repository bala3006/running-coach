from collections.abc import Sequence


def summarize_runs(activities: Sequence[dict]) -> dict[str, float | int | None]:
    runs = [
        item
        for item in activities
        if item.get("distance_km", 0) > 0 and item.get("moving_time_minutes", 0) > 0
    ]
    distance_km = round(sum(float(item["distance_km"]) for item in runs), 2)
    moving_minutes = sum(float(item["moving_time_minutes"]) for item in runs)
    return {
        "run_count": len(runs),
        "distance_km": distance_km,
        "moving_time_minutes": round(moving_minutes),
        "average_pace_min_per_km": round(moving_minutes / distance_km, 2) if distance_km else None,
    }
