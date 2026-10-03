from collections.abc import Sequence
from datetime import date, datetime, timedelta
import re


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


def parse_marathon_goal_request(message: str, as_of: date | None = None) -> dict | None:
    if "marathon" not in message.lower():
        return None
    target = re.search(
        r"\b(?:sub\s*|under\s+|below\s+)(?P<hours>\d{1,2})\s*(?:hours?|hrs?|h)\s*(?P<minutes>\d{1,2})\s*(?:minutes?|mins?|m)\b",
        message,
        re.IGNORECASE,
    )
    if target:
        target_seconds = int(target["hours"]) * 3600 + int(target["minutes"]) * 60
    else:
        target = re.search(
            r"\b(?:sub\s*|under\s+|below\s+)(?P<hours>\d{1,2}):(?P<minutes>[0-5]\d)\b",
            message,
            re.IGNORECASE,
        )
        if not target:
            return None
        target_seconds = int(target["hours"]) * 3600 + int(target["minutes"]) * 60

    month_names = (
        "January|February|March|April|May|June|July|August|September|October|"
        "November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec"
    )
    event_match = re.search(
        rf"\b(?P<day>\d{{1,2}})(?:st|nd|rd|th)?\s+(?P<month>{month_names})\b(?:,?\s+(?P<year>20\d{{2}}))?",
        message,
        re.IGNORECASE,
    )
    if not event_match:
        event_match = re.search(
            rf"\b(?P<month>{month_names})\s+(?P<day>\d{{1,2}})(?:st|nd|rd|th)?\b(?:,?\s+(?P<year>20\d{{2}}))?",
            message,
            re.IGNORECASE,
        )
    if not event_match:
        return None

    today = as_of or date.today()
    month = datetime.strptime(event_match["month"][:3].title(), "%b").month
    year = int(event_match["year"]) if event_match["year"] else today.year
    try:
        event_day = date(year, month, int(event_match["day"]))
    except ValueError:
        return None
    if event_match["year"] is None and event_day < today:
        event_day = date(year + 1, month, int(event_match["day"]))
    return {
        "distance_km": 42.195,
        "target_time_seconds": target_seconds,
        "event_date": event_day.isoformat(),
    }


def analyze_marathon_goal(
    activities: Sequence[dict],
    target_time_seconds: int,
    event_date: str,
    as_of: date | None = None,
) -> dict:
    today = as_of or date.today()
    event_day = date.fromisoformat(event_date)
    cutoff = today - timedelta(days=90)
    recent = []
    for activity in activities:
        started_at = activity.get("start_date_local")
        if not started_at:
            continue
        try:
            run_day = datetime.fromisoformat(started_at.replace("Z", "+00:00")).date()
        except (AttributeError, ValueError):
            continue
        if cutoff <= run_day <= today and activity.get("distance_km", 0) > 0:
            recent.append((run_day, activity))

    distance_km = sum(float(run["distance_km"]) for _, run in recent)
    weekly_totals: dict[str, float] = {}
    for run_day, run in recent:
        iso_year, iso_week, _ = run_day.isocalendar()
        key = f"{iso_year}-W{iso_week:02}"
        weekly_totals[key] = weekly_totals.get(key, 0) + float(run["distance_km"])

    def with_date(entry: tuple[date, dict] | None) -> dict | None:
        if not entry:
            return None
        run_day, run = entry
        distance = float(run["distance_km"])
        minutes = float(run.get("moving_time_minutes") or 0)
        if minutes <= 0:
            return None
        return {
            "date": run_day.isoformat(),
            "name": run.get("name") or "Run",
            "distance_km": distance,
            "moving_time_minutes": minutes,
            "pace_seconds_per_km": round(minutes * 60 / distance),
            "average_heartrate": run.get("average_heartrate"),
            "temperature_c": run.get("temperature_c"),
            "elevation_gain_m": run.get("elevation_gain_m"),
        }

    today_entries = [entry for entry in recent if entry[0] == today]
    today_run = with_date(max(today_entries, key=lambda entry: entry[1]["distance_km"])) if today_entries else None
    longest_entry = max(recent, key=lambda entry: entry[1]["distance_km"]) if recent else None
    longest_run = with_date(longest_entry)
    mid_distance_entries = [
        entry for entry in recent
        if 18 <= float(entry[1]["distance_km"]) < float(longest_run["distance_km"] if longest_run else 0)
    ]
    mid_distance_entry = (
        max(mid_distance_entries, key=lambda entry: entry[1]["distance_km"])
        if mid_distance_entries
        else None
    )

    selected = []
    for entry in (today_run, longest_run, with_date(mid_distance_entry)):
        if entry and not any(existing["date"] == entry["date"] and existing["distance_km"] == entry["distance_km"] for existing in selected):
            predicted = round(
                entry["moving_time_minutes"]
                * 60
                * (42.195 / entry["distance_km"]) ** 1.06
            )
            selected.append({**entry, "projected_marathon_seconds": predicted})

    best_projection = min(
        (item["projected_marathon_seconds"] for item in selected),
        default=None,
    )
    target_pace = round(target_time_seconds / 42.195, 1)
    return {
        "event_date": event_day.isoformat(),
        "days_until_event": (event_day - today).days,
        "target_time_seconds": target_time_seconds,
        "target_pace_seconds_per_km": target_pace,
        "run_count_90d": len(recent),
        "distance_90d_km": round(distance_km, 1),
        "average_weekly_distance_90d_km": round(distance_km * 7 / 90, 1),
        "recent_weekly_distance_km": [
            {"week": week, "distance_km": round(total, 1)}
            for week, total in sorted(weekly_totals.items())[-8:]
        ],
        "today_run": today_run,
        "longest_run": longest_run,
        "projections": selected,
        "best_projection_seconds": best_projection,
        "assessment": (
            "insufficient_data"
            if not selected
            else "within_projection"
            if best_projection <= target_time_seconds
            else "stretch_target"
        ),
    }


def project_race_goal(
    activities: Sequence[dict],
    distance_km: float,
    target_time_seconds: int,
    event_date: str,
    as_of: date | None = None,
) -> dict:
    today = as_of or date.today()
    event_day = date.fromisoformat(event_date)
    cutoff = today - timedelta(days=90)
    candidates = []
    for run in activities:
        distance = float(run.get("distance_km") or 0)
        minutes = float(run.get("moving_time_minutes") or 0)
        started_at = run.get("start_date_local")
        if not started_at or distance < 3 or minutes <= 0:
            continue
        try:
            run_day = datetime.fromisoformat(started_at.replace("Z", "+00:00")).date()
        except ValueError:
            continue
        if not cutoff <= run_day <= today:
            continue
        if distance_km / distance > 2:
            continue
        predicted_seconds = round(minutes * 60 * (distance_km / distance) ** 1.06)
        candidates.append((predicted_seconds, run))

    if event_day < today:
        verdict = "event_passed"
    elif not candidates:
        verdict = "insufficient_data"
    else:
        estimate, _ = min(candidates, key=lambda item: item[0])
        verdict = "within_projection" if target_time_seconds >= estimate else "stretch_target"

    if not candidates:
        return {
            "verdict": verdict,
            "estimated_time_seconds": None,
            "target_time_seconds": target_time_seconds,
            "basis_run": None,
            "days_until_event": (event_day - today).days,
            "caveat": "A comparable run of at least 3 km from the last 90 days is needed.",
        }

    estimate, basis_run = min(candidates, key=lambda item: item[0])
    source_distance = float(basis_run["distance_km"])
    extrapolation = distance_km / source_distance
    distance_fit = (
        "close"
        if extrapolation <= 1.25
        else "moderate"
        if extrapolation <= 1.5
        else "long extrapolation"
    )
    return {
        "verdict": verdict,
        "estimated_time_seconds": estimate,
        "target_time_seconds": target_time_seconds,
        "basis_run": {
            "name": basis_run.get("name") or "Run",
            "date": basis_run.get("start_date_local"),
            "distance_km": source_distance,
            "moving_time_minutes": float(basis_run["moving_time_minutes"]),
        },
        "distance_fit": distance_fit,
        "days_until_event": (event_day - today).days,
        "caveat": (
            "This is a rough Riegel projection from a recent training activity, not a race result or guarantee. "
            "Training consistency, course, weather, and how hard the source run was can change the outcome."
        ),
    }
