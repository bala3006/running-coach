import json

from mcp.server import MCPServer

from running_coach.integrations import get_recent_runs
from running_coach.training import summarize_runs

server = MCPServer("running-coach-strava", instructions="Read-only access to recent Strava running activity.")


@server.tool(description="Get running activities from Strava for the last 1 to 90 days. Read-only.")
async def recent_runs(days: int = 30) -> str:
    """Return recent running activities with distance, duration, date, and available heart rate."""
    try:
        runs = await get_recent_runs(days)
        return json.dumps(
            {"summary": summarize_runs(runs), "activities": runs}, ensure_ascii=False
        )
    except Exception as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


if __name__ == "__main__":
    server.run(transport="stdio")
